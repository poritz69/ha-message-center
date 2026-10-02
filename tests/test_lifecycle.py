"""Tests for the state machine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.message_center.const import MAX_PENDING_HISTORY
from custom_components.message_center.lifecycle import (
    AcceptAction,
    Decision,
    HoldKind,
    MessageBook,
    NotFoundError,
    ResultOutcome,
    RuleVerdict,
    StoreFullError,
    next_retry,
    retry_delay,
)
from custom_components.message_center.models import (
    Message,
    MessageState,
    Reason,
    ReasonKind,
    RecipientState,
    message_id,
)

T0 = datetime(2026, 9, 29, 22, 0, tzinfo=UTC)
ORIGIN = "automation.klima_feuchte_buero"
TITLE = "Feuchte: Büro"
# a fixed salt, so that ids can be compared across books in these tests
SALT = "5f0c1e9a7b3d4e2f8a6b0c1d2e3f4a5b"
MID = message_id(SALT, ORIGIN, TITLE)


def at(minutes: float) -> datetime:
    """Return T0 plus the given minutes."""
    return T0 + timedelta(minutes=minutes)


def arrive(
    book: MessageBook,
    now: datetime,
    *,
    origin: str = ORIGIN,
    title: str = TITLE,
    message: str = "Bitte lüften",
    priority: int = 1,
    **kwargs: object,
) -> Message:
    """Take a message with defaults and return it."""
    return book.accept(
        origin=origin,
        key=title,
        title=title,
        message=message,
        priority=priority,
        now=now,
        **kwargs,  # type: ignore[arg-type]
    ).message


def deliver_all(book: MessageBook, msg: Message, now: datetime) -> None:
    """Start a cycle for one recipient and deliver it."""
    book.start_cycle(msg, ["notify.mobile_app_a"], now)
    book.record_result(
        msg, "notify.mobile_app_a", success=True, revision=msg.revision, now=now
    )


# ----- intake ------------------------------------------------------------------


def test_intake_creates_and_counts() -> None:
    """A new origin and title is created; repeats raise the counter while open."""
    book = MessageBook(salt=SALT)
    result = book.accept(
        origin=ORIGIN,
        key=TITLE,
        title=TITLE,
        message="Bitte lüften",
        priority=1,
        now=T0,
    )
    assert result.action is AcceptAction.CREATED
    msg = result.message
    assert msg.state is MessageState.WAITING
    assert msg.id == MID
    assert (msg.generation, msg.revision, msg.count) == (1, 1, 1)

    again = book.accept(
        origin=ORIGIN,
        key=TITLE,
        title=TITLE,
        message="Bitte lüften",
        priority=1,
        now=at(1),
    )
    assert again.action is AcceptAction.UPDATED
    assert again.message is msg
    assert msg.count == 2
    assert msg.revision == 1


def test_from_effect_holds_only_while_every_arrival_has_it() -> None:
    """A message from an effect of the center is marked; a real arrival clears it.

    Open or bundled: the mark stays only when the existing message and the
    new arrival both carry it, so a real message keeps its effect. A new
    generation takes the mark of its own arrival.
    """
    book = MessageBook(salt=SALT)
    msg = arrive(book, at(0), from_effect=True)
    assert msg.from_effect is True
    assert arrive(book, at(1), from_effect=True).from_effect is True
    assert arrive(book, at(2)).from_effect is False
    assert arrive(book, at(3), from_effect=True).from_effect is False

    real = arrive(book, at(10), title="Echt")
    assert real.from_effect is False
    assert arrive(book, at(11), from_effect=True).from_effect is False

    deliver_all(book, msg, at(20))
    again = arrive(book, at(21), from_effect=True)
    assert again.generation == 2
    assert again.from_effect is True


def test_changed_text_bumps_revision() -> None:
    """Changed text is a new revision of the same generation."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    arrive(book, at(1), message="Neuer Text")
    assert msg.revision == 2
    assert msg.message == "Neuer Text"
    assert msg.generation == 1


def test_bundling_within_spacing_after_delivery() -> None:
    """Delivered + repeat within spacing: counter up, silent replace, no new cycle."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0, spacing=360)
    deliver_all(book, msg, T0)
    assert msg.state is MessageState.DELIVERED

    result = book.accept(
        origin=ORIGIN,
        key=TITLE,
        title=TITLE,
        message="Bitte lüften",
        priority=1,
        now=at(300),
        spacing=360,
    )
    assert result.action is AcceptAction.BUNDLED
    assert msg.state is MessageState.DELIVERED
    assert msg.count == 2
    assert book.evaluate(msg, at(300)) is Decision.REPLACE
    assert book.recipients_to_replace(msg) == ["notify.mobile_app_a"]
    book.mark_replaced(msg, "notify.mobile_app_a", revision=1, count=2)
    assert book.evaluate(msg, at(300)) is Decision.NONE


def test_new_generation_after_spacing() -> None:
    """Delivered + repeat after spacing: new generation, old one to history."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0, spacing=60)
    deliver_all(book, msg, T0)
    new = arrive(book, at(61), spacing=60)
    assert new is not msg
    assert new.generation == 2
    assert new.count == 1
    assert book.evaluate(new, at(61)) is Decision.SEND
    history = book.drain_history()
    assert len(history) == 1
    assert history[0]["state"] == "delivered"


def test_spacing_zero_means_new_cycle_every_time() -> None:
    """Without spacing every arrival after delivery is a new generation."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    deliver_all(book, msg, T0)
    new = arrive(book, at(1))
    assert new.generation == 2
    assert book.evaluate(new, at(1)) is Decision.SEND


def test_new_generation_waits_when_previous_was_discarded() -> None:
    """Previous generation gone → the new one waits for the spacing."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0, spacing=360)
    deliver_all(book, msg, T0)
    msg.state = MessageState.DISCARDED  # simulate a discarded previous generation
    new = arrive(book, at(120), spacing=360)
    assert book.evaluate(new, at(120)) is Decision.WAIT
    assert new.reason.kind is ReasonKind.SPACING
    assert new.reason.until == at(360)
    assert book.due_waits(at(360)) == [new]
    assert book.evaluate(new, at(360)) is Decision.SEND


def test_store_full_rejects_new_but_allows_repeat() -> None:
    """At the limit, new messages are rejected while repeats still count."""
    book = MessageBook(salt=SALT, max_open=2)
    arrive(book, T0, title="a")
    arrive(book, T0, title="b")
    with pytest.raises(StoreFullError):
        arrive(book, T0, title="c")
    assert arrive(book, at(1), title="a").count == 2


def test_expiry_counts_from_last_arrival() -> None:
    """Each arrival with expiry moves the deadline while the message is open."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0, expires_after=30)
    assert msg.expires_at == at(30)
    arrive(book, at(20), expires_after=30)
    assert msg.expires_at == at(50)


# ----- evaluate ----------------------------------------------------------------


def test_evaluate_sends_when_nothing_holds() -> None:
    """Without rule or spacing the decision is to send."""
    book = MessageBook(salt=SALT)
    assert book.evaluate(arrive(book, T0), T0) is Decision.SEND


def test_rule_holds_discards_and_no_hold_ignores() -> None:
    """A rule verdict holds or discards; no_hold ignores it."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    hold = RuleVerdict(
        HoldKind.HOLD, Reason(ReasonKind.RULE, until=at(600), detail="Nacht")
    )
    assert book.evaluate(msg, T0, hold) is Decision.WAIT
    assert msg.reason.detail == "Nacht"

    free = arrive(book, T0, title="Alarm", no_hold=True)
    assert book.evaluate(free, T0, hold) is Decision.SEND

    discard = RuleVerdict(HoldKind.DISCARD, Reason(ReasonKind.RULE, detail="Urlaub"))
    assert book.evaluate(msg, at(1), discard) is Decision.ENDED
    assert msg.state is MessageState.DISCARDED
    assert msg.reason.kind is ReasonKind.RULE_DISCARDED


def test_expired_message_is_discarded() -> None:
    """An expired waiting message is discarded instead of sent."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0, expires_after=10)
    assert book.evaluate(msg, at(10)) is Decision.ENDED
    assert msg.reason.kind is ReasonKind.EXPIRED


def test_rule_end_before_spacing_waits_for_spacing() -> None:
    """Rule ends before the spacing → waits until the spacing ends."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0, spacing=60)
    deliver_all(book, msg, T0)
    msg.state = MessageState.FAILED
    msg2 = arrive(book, at(30), spacing=60)
    hold = RuleVerdict(
        HoldKind.HOLD, Reason(ReasonKind.RULE, until=at(45), detail="Nacht")
    )
    assert book.evaluate(msg2, at(30), hold) is Decision.WAIT
    assert book.evaluate(msg2, at(45)) is Decision.WAIT
    assert msg2.reason.kind is ReasonKind.SPACING
    assert book.evaluate(msg2, at(60)) is Decision.SEND


# ----- push cycle and retries ----------------------------------------------


def test_retry_schedule() -> None:
    """1, 5 and 15 minutes after the first failure, then hourly."""
    assert [retry_delay(n) for n in (1, 2, 3, 4, 5)] == [
        timedelta(minutes=1),
        timedelta(minutes=5),
        timedelta(minutes=15),
        timedelta(minutes=75),
        timedelta(minutes=135),
    ]


def test_partial_success_retries_only_failed_recipient() -> None:
    """A delivered, B fails → retrying; B is retried alone; success → delivered."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    book.start_cycle(msg, ["a", "b"], T0)
    first = book.record_result(msg, "a", success=True, revision=1, now=T0)
    assert first.first_delivery and not first.cycle_ended
    book.record_result(
        msg, "b", success=False, revision=1, now=T0, error="ServiceNotFound"
    )
    assert msg.state is MessageState.RETRYING
    assert msg.recipients["b"].next_try == at(1)
    assert book.due_retries(at(0.5)) == []
    assert book.due_retries(at(1)) == [(msg, "b")]
    book.record_result(msg, "b", success=False, revision=1, now=at(1))
    assert msg.recipients["b"].next_try == at(5)
    done = book.record_result(msg, "b", success=True, revision=1, now=at(5))
    assert done.cycle_ended and not done.first_delivery
    assert msg.state is MessageState.DELIVERED
    assert msg.failed_recipients == []
    assert book.spacing[MID] == T0


def test_recipient_gives_up_after_24_hours() -> None:
    """After 24 hours of failure the recipient is failed, the message delivered."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    book.start_cycle(msg, ["a", "b"], T0)
    book.record_result(msg, "a", success=True, revision=1, now=T0)
    now = T0
    while msg.recipients["b"].state is RecipientState.PENDING:
        now = msg.recipients["b"].next_try or now
        book.record_result(msg, "b", success=False, revision=1, now=now, error="x")
    assert msg.recipients["b"].state is RecipientState.FAILED
    assert now < T0 + timedelta(hours=24)
    assert msg.state is MessageState.DELIVERED
    assert msg.failed_recipients == ["b"]


def test_no_recipient_delivered_means_failed() -> None:
    """No recipient reached → failed; no recipients at all → failed at once."""
    book = MessageBook(salt=SALT)
    bad = arrive(book, T0)
    book.start_cycle(bad, ["a"], T0)
    now = T0
    while bad.state in (MessageState.SENDING, MessageState.RETRYING):
        now = bad.recipients["a"].next_try or now
        book.record_result(bad, "a", success=False, revision=1, now=now)
    assert bad.state is MessageState.FAILED
    assert bad.reason.kind is ReasonKind.NO_RECIPIENT
    empty = arrive(book, T0, title="x")
    book.start_cycle(empty, [], T0)
    assert empty.state is MessageState.FAILED


def test_late_result_after_discard_changes_nothing() -> None:
    """A result arriving after discard is ignored."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    book.start_cycle(msg, ["a"], T0)
    book.discard(MID, at(1))
    assert msg.state is MessageState.DISCARDED
    late = book.record_result(msg, "a", success=True, revision=1, now=at(2))
    assert late.outcome is ResultOutcome.LATE
    assert msg.state is MessageState.DISCARDED


def test_new_text_during_sending_is_replaced_after_delivery() -> None:
    """A newer revision stored mid-cycle is replaced after delivery."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    book.start_cycle(msg, ["a"], T0)
    arrive(book, at(0.1), message="neu")
    book.record_result(msg, "a", success=True, revision=1, now=at(0.2))
    assert book.recipients_to_replace(msg) == ["a"]


def test_repeat_during_retrying_only_counts() -> None:
    """A repeat while retrying keeps the plan and raises the counter."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    book.start_cycle(msg, ["a"], T0)
    book.record_result(msg, "a", success=False, revision=1, now=T0)
    plan = msg.recipients["a"].next_try
    arrive(book, at(0.5))
    assert msg.state is MessageState.RETRYING
    assert msg.count == 2
    assert msg.recipients["a"].next_try == plan
    assert book.evaluate(msg, at(0.5)) is Decision.NONE


def test_repeated_message_one_recipient_down_scenario() -> None:
    """Same message every 15 min with spacing 360, one recipient down for 2 h.

    Expected: one push cycle, retries only on the failed recipient, counter
    rises, no second cycle before 360 minutes after the first delivery.
    """
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0, spacing=360)
    assert book.evaluate(msg, T0) is Decision.SEND
    book.start_cycle(msg, ["a", "b"], T0)
    book.record_result(msg, "a", success=True, revision=1, now=T0)
    book.record_result(msg, "b", success=False, revision=1, now=T0, error="down")
    cycles = 1
    second_cycle_at = None
    for step in range(1, 25):
        now = at(15 * step)
        current = arrive(book, now, spacing=360)
        decision = book.evaluate(current, now)
        if decision is Decision.SEND:
            cycles += 1
            second_cycle_at = now
            book.start_cycle(current, ["a", "b"], now)
            book.record_result(current, "a", success=True, revision=1, now=now)
            book.record_result(current, "b", success=True, revision=1, now=now)
        for due_msg, recipient in book.due_retries(now):
            book.record_result(
                due_msg, recipient, success=now >= at(120), revision=1, now=now
            )
    assert cycles == 2
    assert second_cycle_at == at(360)
    assert msg.count == 24
    assert msg.recipients["a"].attempts == 0


# ----- attempts: one at a time, plan by time, rules and expiry ------------------


HOLD = RuleVerdict(
    HoldKind.HOLD, Reason(ReasonKind.RULE, until=at(600), detail="Nacht")
)
DISCARD = RuleVerdict(HoldKind.DISCARD, Reason(ReasonKind.RULE, detail="Urlaub"))
RULE_REASONS = [ReasonKind.RULE, ReasonKind.RULE_UNKNOWN]


def hold(kind: ReasonKind, effect: HoldKind = HoldKind.HOLD) -> RuleVerdict:
    """Verdict of a rule that is active, or whose entity cannot be read."""
    entity_id = "input_boolean.nacht" if kind is ReasonKind.RULE_UNKNOWN else None
    return RuleVerdict(
        effect, Reason(kind, until=at(600), detail="Nacht", entity_id=entity_id)
    )


def failing(book: MessageBook, recipients: list[str], **kwargs: object) -> Message:
    """Take a message and let its first push fail for every recipient at T0."""
    msg = arrive(book, T0, **kwargs)
    book.start_cycle(msg, recipients, T0)
    first = book.begin_attempt(msg, T0)
    assert first is not None
    for name in recipients:
        book.finish_attempt(first, name, success=False, now=T0, error="down")
    assert msg.state is MessageState.RETRYING
    return msg


def failing_apart(book: MessageBook, **kwargs: object) -> Message:
    """Take a message; "a" failed at T0, "b" half a minute later."""
    msg = arrive(book, T0, **kwargs)
    book.start_cycle(msg, ["a", "b"], T0)
    first = book.begin_attempt(msg, T0)
    assert first is not None
    book.finish_attempt(first, "a", success=False, now=T0, error="down")
    book.finish_attempt(first, "b", success=False, now=at(0.5), error="down")
    assert msg.recipients["b"].next_try == at(1.5)
    return msg


def partly_delivered(book: MessageBook, **kwargs: object) -> Message:
    """Take a message; "a" has it at T0, "b" failed and is retried."""
    msg = arrive(book, T0, **kwargs)
    book.start_cycle(msg, ["a", "b"], T0)
    first = book.begin_attempt(msg, T0)
    assert first is not None
    book.finish_attempt(first, "a", success=True, now=T0)
    book.finish_attempt(first, "b", success=False, now=T0, error="down")
    assert msg.state is MessageState.RETRYING
    return msg


def test_first_attempt_reserves_every_recipient() -> None:
    """The first push of a cycle takes all recipients and notes what it sends."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    assert book.begin_attempt(msg, T0) is None  # waiting: no cycle yet
    book.start_cycle(msg, ["a", "b"], T0)
    attempt = book.begin_attempt(msg, T0)
    assert attempt is not None
    assert list(attempt.recipients) == ["a", "b"]
    assert (attempt.revision, attempt.count, attempt.replace) == (1, 1, False)
    assert attempt.recipients["a"] is msg.recipients["a"]
    assert book.begin_attempt(msg, T0) is None  # both are on their way

    arrive(book, at(0.1), message="neu")  # the push carries the older text
    done = book.finish_attempt(attempt, "a", success=True, now=at(0.2))
    assert done.first_delivery
    assert msg.recipients["a"].delivered_revision == 1
    assert book.recipients_to_replace(msg) == ["a"]


def test_attempt_in_flight_is_not_due_again() -> None:
    """A retry that is still running is neither due nor on the timer."""
    book = MessageBook(salt=SALT)
    msg = failing(book, ["a"])
    status = msg.recipients["a"]
    assert msg.next_try == at(1)

    attempt = book.begin_attempt(msg, at(1))
    assert attempt is not None
    assert list(attempt.recipients) == ["a"]
    assert book.begin_attempt(msg, at(1)) is None
    assert book.begin_attempt(msg, at(1.5)) is None
    assert book.due_retries(at(1.5)) == []
    assert msg.next_try is None

    book.finish_attempt(attempt, "a", success=False, now=at(1.2), error="down")
    assert status.attempts == 2
    assert status.next_try == at(5)
    assert msg.next_try == at(5)
    assert book.due_retries(at(5)) == [(msg, "a")]


def test_attempt_in_flight_only_blocks_that_recipient() -> None:
    """Another recipient of the same message is retried at its own time."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    book.start_cycle(msg, ["a", "b"], T0)
    first = book.begin_attempt(msg, T0)
    assert first is not None
    book.finish_attempt(first, "a", success=False, now=T0)
    book.finish_attempt(first, "b", success=False, now=at(0.5))
    assert msg.recipients["b"].next_try == at(1.5)

    running = book.begin_attempt(msg, at(1))
    assert running is not None
    assert list(running.recipients) == ["a"]
    assert msg.next_try == at(1.5)
    other = book.begin_attempt(msg, at(1.5))
    assert other is not None
    assert list(other.recipients) == ["b"]


def test_released_attempt_is_due_again() -> None:
    """A push that never reported (cancelled) gives its recipients back."""
    book = MessageBook(salt=SALT)
    msg = failing(book, ["a"])
    attempt = book.begin_attempt(msg, at(1))
    assert attempt is not None
    book.release_attempt(attempt)
    assert msg.recipients["a"].attempts == 1
    assert book.due_retries(at(1)) == [(msg, "a")]
    again = book.begin_attempt(msg, at(1))
    assert again is not None
    assert list(again.recipients) == ["a"]


def test_result_of_an_older_cycle_is_late() -> None:
    """A result counts only for the recipient state its push was started for."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    book.start_cycle(msg, ["a"], T0)
    old = book.begin_attempt(msg, T0)
    assert old is not None
    book.snooze(MID, 5, at(1))
    assert book.evaluate(msg, at(6)) is Decision.SEND
    book.start_cycle(msg, ["a"], at(6))
    new = book.begin_attempt(msg, at(6))
    assert new is not None  # the old push does not block the new cycle

    late = book.finish_attempt(old, "a", success=True, now=at(6.1))
    assert late.outcome is ResultOutcome.LATE
    assert msg.state is MessageState.SENDING
    assert book.begin_attempt(msg, at(6.1)) is None  # the new one still runs
    done = book.finish_attempt(new, "a", success=True, now=at(6.2))
    assert done.first_delivery and done.cycle_ended


def test_running_mark_is_not_saved_and_survives_a_rollback() -> None:
    """The mark lives in memory only and stays on the object through a rollback."""
    book = MessageBook(salt=SALT)
    msg = failing(book, ["a"])
    status = msg.recipients["a"]
    undo = book.snapshot(ORIGIN, TITLE)
    attempt = book.begin_attempt(msg, at(1))
    assert attempt is not None
    assert "in_flight" not in status.to_dict()
    other = MessageBook(salt=SALT)
    other.load(book.to_dict())
    restored = other.get(MID)
    assert restored is not None
    assert other.due_retries(at(1)) == [(restored, "a")]  # as after a restart

    book.rollback(undo)  # an intake that could not be stored
    assert msg.recipients["a"] is status
    assert book.begin_attempt(msg, at(1)) is None  # the push is still out
    book.finish_attempt(attempt, "a", success=True, now=at(1.1))
    assert msg.state is MessageState.DELIVERED


def test_plan_follows_the_time_not_the_number_of_attempts() -> None:
    """1, 5, 15 minutes after the first failure, then hourly, whatever is counted."""
    assert [next_retry(T0, at(m)) for m in (0, 0.5, 1, 4.9, 5, 15, 74, 75)] == [
        at(1),
        at(1),
        at(5),
        at(5),
        at(15),
        at(75),
        at(75),
        at(135),
    ]
    assert next_retry(T0, at(23 * 60 + 14)) == at(23 * 60 + 15)
    assert next_retry(T0, at(23 * 60 + 15)) is None
    assert next_retry(T0, T0 + timedelta(days=3)) is None

    book = MessageBook(salt=SALT)
    msg = failing(book, ["a"])
    status = msg.recipients["a"]
    # the same result booked several times moves nothing (it used to cost a step)
    for _ in range(5):
        book.record_result(msg, "a", success=False, revision=1, now=at(1.1))
    assert status.attempts == 6
    assert status.next_try == at(5)
    # attempts left out (restart, rule) do not push the plan back either
    book.record_result(msg, "a", success=False, revision=1, now=at(200))
    assert status.next_try == at(255)
    assert status.state is RecipientState.PENDING


def test_recipient_gives_up_24_hours_after_the_first_failure() -> None:
    """A failure with no plan time left before 24 hours ends the recipient."""
    book = MessageBook(salt=SALT)
    msg = partly_delivered(book)
    book.record_result(msg, "b", success=False, revision=1, now=at(1))
    assert msg.recipients["b"].state is RecipientState.PENDING
    book.record_result(
        msg, "b", success=False, revision=1, now=T0 + timedelta(hours=23, minutes=20)
    )
    assert msg.recipients["b"].state is RecipientState.FAILED
    assert msg.recipients["b"].attempts == 3
    assert msg.state is MessageState.DELIVERED
    assert msg.failed_recipients == ["b"]


def test_expiry_ends_retrying_partly_delivered() -> None:
    """An expired message stops retrying; delivered to one counts as delivered."""
    book = MessageBook(salt=SALT)
    msg = partly_delivered(book, expires_after=30)
    assert book.apply_expiry(at(29)) == []
    assert book.apply_expiry(at(31)) == [msg]
    assert msg.state is MessageState.DELIVERED
    assert msg.failed_recipients == ["b"]
    assert msg.next_try is None
    assert book.due_retries(at(75)) == []
    assert book.begin_attempt(msg, at(75)) is None


def test_expiry_ends_retrying_nobody_reached() -> None:
    """Expired with nobody reached: discarded with the reason expired."""
    book = MessageBook(salt=SALT)
    msg = failing(book, ["a"], expires_after=30)
    assert book.apply_expiry(at(31)) == [msg]
    assert msg.state is MessageState.DISCARDED
    assert msg.reason.kind is ReasonKind.EXPIRED
    assert msg.recipients["a"].state is RecipientState.FAILED
    assert msg.ended_at == at(31)


def test_expiry_is_checked_before_every_attempt() -> None:
    """A due retry of an expired message is not sent, also without a tick before."""
    book = MessageBook(salt=SALT)
    msg = failing(book, ["a"], expires_after=3)
    assert book.begin_attempt(msg, at(5)) is None
    assert msg.state is MessageState.DISCARDED
    assert msg.reason.kind is ReasonKind.EXPIRED


def test_retry_under_way_is_left_to_its_result_by_the_expiry() -> None:
    """A retry that is out when the message expires decides first.

    Reaching the phone, it counts as delivered. The message used to end as
    discarded, expired, with the push on the phone and no delivered event.
    Failing, it is not tried again: the expiry closes the cycle after it.
    """
    book = MessageBook(salt=SALT)
    msg = failing(book, ["a"], expires_after=3)
    assert not book.expiry_waits(msg)
    attempt = book.begin_attempt(msg, at(1))
    assert attempt is not None
    assert book.expiry_waits(msg)
    assert book.apply_expiry(at(4)) == []  # while the retry is out
    assert msg.state is MessageState.RETRYING
    assert book.begin_attempt(msg, at(4)) is None
    done = book.finish_attempt(attempt, "a", success=True, now=at(4.1))
    assert done.first_delivery and done.cycle_ended
    assert msg.state is MessageState.DELIVERED
    assert msg.recipients["a"].delivered_at == at(4.1)

    lost = failing(book, ["a"], title="verloren", expires_after=3)
    attempt = book.begin_attempt(lost, at(1))
    assert attempt is not None
    assert book.apply_expiry(at(4)) == []
    book.finish_attempt(attempt, "a", success=False, now=at(4.1), error="down")
    assert lost.state is MessageState.RETRYING
    assert not book.expiry_waits(lost)
    assert book.begin_attempt(lost, at(5)) is None  # expired: no further push
    assert lost.state is MessageState.DISCARDED
    assert lost.reason.kind is ReasonKind.EXPIRED


def test_expiry_fails_idle_recipients_while_another_retry_is_out() -> None:
    """Only the recipient whose push is out waits for its result."""
    book = MessageBook(salt=SALT)
    msg = failing_apart(book, expires_after=3)
    running = book.begin_attempt(msg, at(1))
    assert running is not None
    assert list(running.recipients) == ["a"]

    assert book.apply_expiry(at(4)) == []
    assert msg.state is MessageState.RETRYING
    assert msg.recipients["b"].state is RecipientState.FAILED
    assert msg.next_try is None
    assert book.due_retries(at(4)) == []
    assert book.begin_attempt(msg, at(4)) is None  # "b" is not pushed any more
    done = book.finish_attempt(running, "a", success=True, now=at(4.1))
    assert done.first_delivery and done.cycle_ended
    assert msg.state is MessageState.DELIVERED
    assert msg.failed_recipients == ["b"]


def test_max_wait_ends_retrying() -> None:
    """Seven days without any delivery end a message that is still retrying."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    start = T0 + timedelta(days=6, hours=23)
    book.start_cycle(msg, ["a"], start)
    book.record_result(msg, "a", success=False, revision=1, now=start)
    assert book.apply_expiry(T0 + timedelta(days=7)) == [msg]
    assert msg.state is MessageState.DISCARDED
    assert msg.reason.kind is ReasonKind.MAX_WAIT


def test_max_wait_leaves_a_partly_delivered_message_to_its_plan() -> None:
    """The maximum wait ends only what nobody has; a partial delivery counts.

    Delivered to "a", the message is not discarded after seven days. The plan
    of "b" ends it: given up after 24 hours, delivered with "b" failed.
    """
    book = MessageBook(salt=SALT)
    msg = partly_delivered(book)
    week = T0 + timedelta(days=7)
    assert book.apply_expiry(week) == []
    assert msg.state is MessageState.RETRYING
    attempt = book.begin_attempt(msg, week)
    assert attempt is not None
    assert list(attempt.recipients) == ["b"]
    done = book.finish_attempt(attempt, "b", success=False, now=week, error="down")
    assert done.cycle_ended
    assert msg.state is MessageState.DELIVERED
    assert msg.failed_recipients == ["b"]


def test_first_push_is_not_expired_under_way() -> None:
    """Sending is left alone: the result of the push decides, then the expiry."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0, expires_after=1)
    assert not book.expiry_waits(msg)  # waiting: the expiry applies
    book.start_cycle(msg, ["a"], at(0.9))
    attempt = book.begin_attempt(msg, at(0.9))
    assert attempt is not None
    assert book.expiry_waits(msg)
    assert book.apply_expiry(at(1)) == []
    assert msg.state is MessageState.SENDING


@pytest.mark.parametrize("kind", RULE_REASONS)
def test_retry_waits_while_a_rule_holds(kind: ReasonKind) -> None:
    """A due retry under a hold rule is not sent and moves to the next plan time.

    The same with a rule whose entity cannot be read.
    """
    held = hold(kind)
    book = MessageBook(salt=SALT)
    msg = partly_delivered(book)
    status = msg.recipients["b"]
    assert book.begin_attempt(msg, at(0.5), held) is None  # not due: nothing changes
    assert msg.reason.kind is ReasonKind.RETRY
    assert status.next_try == at(1)

    assert book.begin_attempt(msg, at(1), held) is None
    assert msg.state is MessageState.RETRYING
    assert msg.reason == held.reason
    assert status.next_try == at(5)
    assert (status.attempts, status.last_error) == (1, "down")
    assert status.in_flight is False
    assert msg.recipients["a"].state is RecipientState.DELIVERED

    assert book.begin_attempt(msg, at(5), held) is None
    assert status.next_try == at(15)
    assert book.begin_attempt(msg, at(20), held) is None  # a late tick
    assert status.next_try == at(75)
    assert status.attempts == 1


@pytest.mark.parametrize("kind", RULE_REASONS)
def test_held_retry_is_due_when_the_hold_ends(kind: ReasonKind) -> None:
    """At the end of the hold phase the retry goes out, not at the next plan time."""
    book = MessageBook(salt=SALT)
    msg = partly_delivered(book)
    status = msg.recipients["b"]
    assert book.begin_attempt(msg, at(15), hold(kind)) is None
    assert status.next_try == at(75)

    other = RuleVerdict(
        HoldKind.HOLD, Reason(ReasonKind.RULE, until=at(300), detail="Urlaub")
    )
    assert book.begin_attempt(msg, at(20), other) is None  # still held: new reason
    assert msg.reason == other.reason
    assert status.next_try == at(75)

    attempt = book.begin_attempt(msg, at(30))
    assert attempt is not None
    assert list(attempt.recipients) == ["b"]
    assert msg.reason.kind is ReasonKind.RETRY
    book.finish_attempt(attempt, "b", success=False, now=at(30), error="down")
    assert status.attempts == 2
    assert status.next_try == at(75)  # back on the plan, no burst of retries
    assert msg.reason == Reason(ReasonKind.RETRY, until=at(75))


@pytest.mark.parametrize("kind", RULE_REASONS)
def test_result_of_a_running_retry_keeps_the_reason_of_the_rule(
    kind: ReasonKind,
) -> None:
    """A retry started before the rule reports while the message is held back."""
    held = hold(kind)
    book = MessageBook(salt=SALT)
    msg = failing_apart(book)
    running = book.begin_attempt(msg, at(1))
    assert running is not None
    assert book.begin_attempt(msg, at(1.5), held) is None  # "b" is held back
    assert msg.reason == held.reason
    book.finish_attempt(running, "a", success=False, now=at(1.6), error="down")
    assert msg.state is MessageState.RETRYING
    assert msg.reason == held.reason
    assert msg.recipients["a"].next_try == at(5)


def test_retry_that_was_not_held_keeps_its_plan_time() -> None:
    """Without a hold before, a missing verdict does not make a retry due."""
    book = MessageBook(salt=SALT)
    msg = partly_delivered(book)
    assert book.begin_attempt(msg, at(0.5)) is None
    assert msg.recipients["b"].next_try == at(1)


def test_held_retry_gives_up_after_24_hours() -> None:
    """The 24 hours of a recipient run on while a rule holds the retry."""
    book = MessageBook(salt=SALT)
    msg = partly_delivered(book)
    assert book.begin_attempt(msg, T0 + timedelta(hours=23, minutes=20), HOLD) is None
    assert msg.recipients["b"].state is RecipientState.FAILED
    assert msg.state is MessageState.DELIVERED
    assert msg.failed_recipients == ["b"]


def test_retry_passes_a_rule_with_no_hold() -> None:
    """A message that rules do not hold is retried while a rule is active."""
    book = MessageBook(salt=SALT)
    msg = partly_delivered(book, no_hold=True)
    attempt = book.begin_attempt(msg, at(1), HOLD)
    assert attempt is not None
    assert list(attempt.recipients) == ["b"]
    assert msg.reason.kind is ReasonKind.RETRY


def test_rule_that_discards_closes_the_cycle() -> None:
    """Discard at a retry: delivered to one stays delivered, else discarded."""
    book = MessageBook(salt=SALT)
    partly = partly_delivered(book)
    assert book.begin_attempt(partly, at(0.5), DISCARD) is None  # not due yet
    assert partly.state is MessageState.RETRYING
    assert book.begin_attempt(partly, at(1), DISCARD) is None
    assert partly.state is MessageState.DELIVERED
    assert partly.failed_recipients == ["b"]

    nobody = failing(book, ["a"], title="niemand")
    assert book.begin_attempt(nobody, at(1), DISCARD) is None
    assert nobody.state is MessageState.DISCARDED
    assert nobody.reason.kind is ReasonKind.RULE_DISCARDED
    assert book.due_retries(at(5)) == []

    held = failing(book, ["a"], title="gehalten")
    assert book.begin_attempt(held, at(1), HOLD) is None
    assert book.begin_attempt(held, at(2), DISCARD) is None  # like a waiting one
    assert held.state is MessageState.DISCARDED
    assert held.reason.kind is ReasonKind.RULE_DISCARDED


def test_rule_that_discards_leaves_a_retry_under_way_to_its_result() -> None:
    """A push that is out is not failed by the rule; the idle recipient is."""
    book = MessageBook(salt=SALT)
    msg = failing_apart(book)
    running = book.begin_attempt(msg, at(1))
    assert running is not None
    assert book.begin_attempt(msg, at(1.5), DISCARD) is None
    assert msg.state is MessageState.RETRYING
    assert msg.recipients["b"].state is RecipientState.FAILED
    assert msg.recipients["a"].state is RecipientState.PENDING
    done = book.finish_attempt(running, "a", success=True, now=at(1.6))
    assert done.first_delivery and done.cycle_ended
    assert msg.state is MessageState.DELIVERED
    assert msg.failed_recipients == ["b"]

    other = failing_apart(book, title="niemand")
    running = book.begin_attempt(other, at(1))
    assert running is not None
    assert book.begin_attempt(other, at(1.5), DISCARD) is None
    book.finish_attempt(running, "a", success=False, now=at(1.6), error="down")
    assert other.state is MessageState.RETRYING
    assert book.begin_attempt(other, at(5), DISCARD) is None  # the next plan time
    assert other.state is MessageState.DISCARDED
    assert other.reason.kind is ReasonKind.RULE_DISCARDED


def test_rule_with_unknown_state_holds_a_retry_and_never_discards_it() -> None:
    """While the entity of a discarding rule cannot be read, a retry only waits.

    After a start the entity is often not there yet. Closing the cycle then
    could not be taken back. Once the entity shows its state, that decides.
    """
    unknown = hold(ReasonKind.RULE_UNKNOWN, HoldKind.DISCARD)
    book = MessageBook(salt=SALT)
    msg = failing(book, ["a"])
    assert book.begin_attempt(msg, at(1), unknown) is None
    assert msg.state is MessageState.RETRYING
    assert msg.reason == unknown.reason
    assert msg.recipients["a"].next_try == at(5)
    attempt = book.begin_attempt(msg, at(2))  # back, and not in the rule state
    assert attempt is not None
    assert list(attempt.recipients) == ["a"]

    other = failing(book, ["a"], title="doch")
    assert book.begin_attempt(other, at(1), unknown) is None
    assert book.begin_attempt(other, at(2), DISCARD) is None  # back in the rule state
    assert other.state is MessageState.DISCARDED
    assert other.reason.kind is ReasonKind.RULE_DISCARDED


def test_first_attempt_does_not_ask_the_rules_again() -> None:
    """The cycle was released by ``evaluate``; only retries are checked again."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    book.start_cycle(msg, ["a"], T0)
    assert book.begin_attempt(msg, T0, HOLD) is not None


def test_replace_confirms_only_what_was_sent() -> None:
    """A replacement notes what it carried, and nothing runs twice."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0, spacing=60)
    deliver_all(book, msg, T0)
    name = "notify.mobile_app_a"
    status = msg.recipients[name]
    assert book.begin_replace(msg) is None  # nothing to replace

    arrive(book, at(1), message="v2", spacing=60)
    replace = book.begin_replace(msg)
    assert replace is not None
    assert replace.replace
    assert (replace.revision, replace.count) == (2, 2)
    assert list(replace.recipients) == [name]

    arrive(book, at(2), message="v3", spacing=60)  # while the push is out
    assert book.evaluate(msg, at(2)) is Decision.NONE
    assert book.begin_replace(msg) is None  # one at a time
    book.finish_attempt(replace, name, success=True, now=at(2.1))
    assert (status.delivered_revision, status.delivered_count) == (2, 2)
    assert book.recipients_to_replace(msg) == [name]  # v3 is still owed

    again = book.begin_replace(msg)
    assert again is not None
    assert (again.revision, again.count) == (3, 3)
    book.finish_attempt(again, name, success=False, now=at(2.2), error="down")
    assert (status.delivered_revision, status.delivered_count) == (2, 2)
    assert book.recipients_to_replace(msg) == [name]  # the lag stays visible

    last = book.begin_replace(msg)
    assert last is not None
    book.finish_attempt(last, name, success=True, now=at(2.3))
    assert (status.delivered_revision, status.delivered_count) == (3, 3)
    assert book.recipients_to_replace(msg) == []
    assert book.begin_replace(msg) is None


def test_mark_replaced_never_goes_back() -> None:
    """An older version confirmed late does not lower what the recipient shows."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0, spacing=60)
    deliver_all(book, msg, T0)
    name = "notify.mobile_app_a"
    arrive(book, at(1), message="v2", spacing=60)
    arrive(book, at(2), message="v3", spacing=60)
    book.mark_replaced(msg, name, revision=3, count=3)
    book.mark_replaced(msg, name, revision=2, count=2)
    status = msg.recipients[name]
    assert (status.delivered_revision, status.delivered_count) == (3, 3)


def test_replace_runs_beside_a_retry_but_not_for_other_states() -> None:
    """Delivered recipients are replaced while another is retried; never when over."""
    book = MessageBook(salt=SALT)
    msg = partly_delivered(book)
    arrive(book, at(0.5), message="neu")
    retry = book.begin_attempt(msg, at(1))
    assert retry is not None
    replace = book.begin_replace(msg)
    assert replace is not None
    assert list(replace.recipients) == ["a"]
    assert list(retry.recipients) == ["b"]

    snoozed = arrive(book, T0, title="später", spacing=60)
    deliver_all(book, snoozed, T0)
    arrive(book, at(1), title="später", message="neu", spacing=60)
    book.snooze(snoozed.id, 30, at(2))
    assert book.begin_replace(snoozed) is None  # waiting: the next cycle sends it

    old = arrive(book, T0, title="alt")
    deliver_all(book, old, T0)
    old.count = 2  # lagging, and then replaced by a new generation
    new = arrive(book, at(1), title="alt")
    assert new is not old
    assert book.begin_replace(old) is None
    assert book.begin_attempt(old, at(1)) is None


# ----- discard, snooze, send_now, forward -------------------------------------


def test_discard_only_open_messages() -> None:
    """Discard ends open messages; delivered ones are untouched."""
    book = MessageBook(salt=SALT)
    a = arrive(book, T0, title="a")
    b = arrive(book, T0, title="b")
    deliver_all(book, b, T0)
    assert book.discard(message_id(SALT, ORIGIN, "a"), at(1)) is a
    assert a.state is MessageState.DISCARDED
    with pytest.raises(NotFoundError):
        book.discard(message_id(SALT, ORIGIN, "b"), at(1))
    assert b.state is MessageState.DELIVERED
    c = arrive(book, T0, title="c")
    assert book.discard_matching(ORIGIN, "c", at(2)) == [c]
    assert book.discard_matching(ORIGIN, "nope", at(2)) == []


def test_snooze_from_delivered_and_waiting() -> None:
    """Snooze moves a message to waiting until the time is up, then it is sent."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    deliver_all(book, msg, T0)
    book.snooze(MID, 30, at(5))
    assert msg.state is MessageState.WAITING
    assert msg.reason.until == at(35)
    arrive(book, at(10), message="neu")
    assert book.evaluate(msg, at(10)) is Decision.WAIT
    assert msg.count == 2
    assert book.due_waits(at(35)) == [msg]
    assert book.evaluate(msg, at(35)) is Decision.SEND
    with pytest.raises(NotFoundError):
        book.snooze("automation.x:nope", 5, at(36))
    book.discard(MID, at(36))
    with pytest.raises(NotFoundError):
        book.snooze(MID, 5, at(37))


def test_send_now_releases_a_held_message() -> None:
    """send_now makes a waiting or unclear message go out despite rules."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    hold = RuleVerdict(
        HoldKind.HOLD, Reason(ReasonKind.RULE, until=at(600), detail="Nacht")
    )
    assert book.evaluate(msg, T0, hold) is Decision.WAIT
    book.send_now(MID, at(1))
    assert book.evaluate(msg, at(1), hold) is Decision.SEND
    deliver_all(book, msg, at(1))
    with pytest.raises(NotFoundError):
        book.send_now(MID, at(2))


@pytest.mark.parametrize("kind", RULE_REASONS)
def test_send_now_releases_a_held_retry(kind: ReasonKind) -> None:
    """send_now makes a retry a rule holds back due at once; the cycle runs on.

    The recipient that has the message keeps it and gets no second push; the
    one that failed is pushed now although the rule still holds.
    """
    held = hold(kind)
    book = MessageBook(salt=SALT)
    msg = partly_delivered(book)
    assert book.begin_attempt(msg, at(1), held) is None
    assert msg.reason == held.reason
    started = msg.cycle_started_at

    assert book.send_now(MID, at(2)) is msg
    assert msg.state is MessageState.RETRYING
    assert msg.no_hold is True
    assert msg.reason == Reason(ReasonKind.RETRY, until=at(2))
    assert msg.cycle_started_at == started
    assert msg.recipients["a"].state is RecipientState.DELIVERED
    assert msg.recipients["b"].next_try == at(2)
    assert msg.recipients["b"].attempts == 1

    attempt = book.begin_attempt(msg, at(2), held)  # the rule is passed over
    assert attempt is not None
    assert list(attempt.recipients) == ["b"]
    book.finish_attempt(attempt, "b", success=True, now=at(2))
    assert msg.state is MessageState.DELIVERED
    assert msg.failed_recipients == []


def test_send_now_brings_a_planned_retry_forward() -> None:
    """send_now pushes a retry now instead of at its plan time; a push out stays."""
    book = MessageBook(salt=SALT)
    msg = partly_delivered(book)
    status = msg.recipients["b"]
    assert status.next_try == at(1)

    book.send_now(MID, at(0.5))
    assert status.next_try == at(0.5)
    assert msg.reason == Reason(ReasonKind.RETRY, until=at(0.5))
    attempt = book.begin_attempt(msg, at(0.5))
    assert attempt is not None
    assert list(attempt.recipients) == ["b"]

    book.send_now(MID, at(0.6))  # while the push is out: nothing is taken twice
    assert status.in_flight is True
    assert status.next_try == at(0.5)
    assert book.begin_attempt(msg, at(0.6)) is None
    book.finish_attempt(attempt, "b", success=False, now=at(0.6), error="down")
    assert status.next_try == at(1)  # back on the plan, which hangs on T0


def test_forward_marks_message() -> None:
    """Forward keeps the state and records the time."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    book.forward(MID, at(1))
    assert msg.forwarded_at == at(1)
    assert msg.state is MessageState.WAITING
    with pytest.raises(NotFoundError):
        book.forward("automation.x:nope", at(1))


# ----- expiry, restart, prune ----------------------------------------------


def test_max_wait_discards_after_seven_days() -> None:
    """A message never delivered within 7 days is discarded with reason max_wait."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    assert book.apply_expiry(T0 + timedelta(days=6)) == []
    assert book.apply_expiry(T0 + timedelta(days=7)) == [msg]
    assert msg.reason.kind is ReasonKind.MAX_WAIT


def test_restart_short_gap() -> None:
    """Short gap: sending → unclear, retrying continues, waiting is re-evaluated."""
    book = MessageBook(salt=SALT)
    sending = arrive(book, T0, title="s")
    book.start_cycle(sending, ["a"], T0)
    retrying = arrive(book, T0, title="r")
    book.start_cycle(retrying, ["a"], T0)
    book.record_result(retrying, "a", success=False, revision=1, now=T0)
    waiting = arrive(book, T0, title="w")
    expired = arrive(book, T0, title="e", expires_after=5)
    result = book.on_restart(at(30), saved_at=at(10))
    assert result.unclear == [sending]
    assert sending.reason.kind is ReasonKind.RESTART
    assert result.waiting == [waiting]
    assert result.ended == [expired]
    assert retrying.state is MessageState.RETRYING
    assert book.due_retries(at(30)) == [(retrying, "a")]


def test_restart_long_gap_marks_open_unclear() -> None:
    """Gap over 60 minutes: everything open becomes unclear, delivered stays."""
    book = MessageBook(salt=SALT)
    a = arrive(book, T0, title="a")
    deliver_all(book, a, T0)
    b = arrive(book, T0, title="b")
    result = book.on_restart(at(180), saved_at=at(10))
    assert result.unclear == [b]
    assert a.state is MessageState.DELIVERED
    assert b.reason.kind is ReasonKind.GAP
    assert b.reason.detail == "3"
    assert book.evaluate(b, at(180)) is Decision.NONE
    again = arrive(book, at(181), title="b")
    assert again is b
    assert book.evaluate(b, at(181)) is Decision.SEND


def test_prune_keeps_delivered_while_spacing_runs() -> None:
    """End states leave after 24 h, delivered ones only after their spacing."""
    book = MessageBook(salt=SALT)
    quick = arrive(book, T0, title="quick")
    deliver_all(book, quick, T0)
    spaced = arrive(book, T0, title="spaced", spacing=48 * 60)
    deliver_all(book, spaced, T0)
    book.prune(T0 + timedelta(hours=25))
    assert book.get(message_id(SALT, ORIGIN, "quick")) is None
    assert book.get(message_id(SALT, ORIGIN, "spaced")) is spaced
    assert [h["key"] for h in book.drain_history()] == ["quick"]
    book.prune(T0 + timedelta(hours=49))
    assert book.get(message_id(SALT, ORIGIN, "spaced")) is None
    book.prune(T0 + timedelta(days=7))
    assert book.spacing == {}


def test_roundtrip_through_dict() -> None:
    """Serialising and loading keeps every field."""
    book = MessageBook(salt=SALT)
    msg = arrive(
        book,
        T0,
        spacing=30,
        expires_after=60,
        context_id="ctx",
        user_id="u1",
        data={"image": "/x.jpg"},
        labels=["Klima"],
        origin_name="Klima Feuchte Büro",
        kind_id="k1",
        group_id="g1",
    )
    book.start_cycle(msg, ["a", "b"], T0)
    book.record_result(msg, "a", success=True, revision=1, now=T0)
    book.record_result(msg, "b", success=False, revision=1, now=T0, error="err")
    data = book.to_dict()
    other = MessageBook(salt=SALT)
    other.load(data)
    restored = other.get(MID)
    assert restored is not None
    assert restored.to_dict() == msg.to_dict()
    assert other.to_dict() == data


def test_pending_history_survives_the_roundtrip() -> None:
    """End states waiting for the history store are saved with the book."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    deliver_all(book, msg, T0)
    arrive(book, at(1))  # no spacing: a new generation, the old one is pending
    assert len(book.history) == 1
    data = book.to_dict()
    other = MessageBook(salt=SALT)
    other.load(data)
    assert other.history == book.history
    assert other.history is not book.history

    del data["pending_history"]  # written before the field existed
    other.load(data)
    assert other.history == []


def test_pending_history_is_capped_at_the_newest_entries() -> None:
    """Never more than the limit of pending end states; the oldest go, counted.

    The count is what the center logs. The capped state survives the store.
    """
    assert MessageBook(salt=SALT).max_pending == MAX_PENDING_HISTORY == 1000
    book = MessageBook(salt=SALT, max_pending=3)
    msg = arrive(book, T0, message="1")
    for n in range(2, 7):
        deliver_all(book, msg, at(n))
        msg = arrive(book, at(n), message=str(n))  # a new generation each time
    assert len(book.history) == 3
    assert [e["message"] for e in book.history] == ["3", "4", "5"]
    assert book.history_dropped == 2

    other = MessageBook(salt=SALT, max_pending=3)
    other.load(book.to_dict())
    assert other.history == book.history
    assert other.history_dropped == 0

    data = book.to_dict()
    data["pending_history"] = [
        dict(e, generation=n) for n, e in enumerate(book.history)
    ]
    data["pending_history"] += [
        dict(e, generation=n + 3) for n, e in enumerate(book.history)
    ]
    other = MessageBook(salt=SALT, max_pending=2)
    other.load(data)
    assert [e["generation"] for e in other.history] == [4, 5]
    assert other.history_dropped == 4


def test_rollback_at_the_pending_history_limit_takes_back_the_new_entry() -> None:
    """Taking back a new generation at the limit removes its entry, not another.

    The oldest entry the limit dropped is gone; the count stays, it was lost.
    """
    book = MessageBook(salt=SALT, max_pending=2)
    msg = arrive(book, T0)
    deliver_all(book, msg, T0)
    kept = [{"key": "first"}, {"key": "second"}]
    book.history = list(kept)

    undo = book.snapshot(ORIGIN, TITLE)
    arrive(book, at(1))
    assert [e["key"] for e in book.history] == ["second", TITLE]
    book.rollback(undo)
    assert book.get(MID) is msg
    assert book.history == kept[1:]
    assert book.history_dropped == 1


def test_malformed_pending_history_does_not_load() -> None:
    """A pending end state is checked like a message, before it can do harm."""
    book = MessageBook(salt=SALT)
    arrive(book, T0)
    data = book.to_dict()
    data["pending_history"] = [{"origin": ORIGIN}]
    with pytest.raises(KeyError):
        MessageBook(salt=SALT).load(data)


def test_rollback_of_a_new_message_leaves_the_others_alone() -> None:
    """Taking back a first arrival removes it; no other object changes."""
    book = MessageBook(salt=SALT)
    other = arrive(book, T0, title="other")
    book.start_cycle(other, ["a"], T0)
    undo = book.snapshot(ORIGIN, TITLE)
    msg = arrive(book, at(1))
    book.evaluate(msg, at(1))
    book.spacing[MID] = at(1)  # nothing does this during an intake today
    book.rollback(undo)
    assert book.get(MID) is None
    assert book.get(message_id(SALT, ORIGIN, "other")) is other
    assert other.state is MessageState.SENDING
    assert book.spacing == {}


def test_rollback_of_an_update_keeps_the_objects() -> None:
    """Taking back a repeat restores the fields of the same message object.

    A push running meanwhile holds the message and records into its
    recipient states; both must stay the ones the book holds.
    """
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0, data={"image": "/a.jpg"})
    book.start_cycle(msg, ["a", "b"], T0)
    book.record_result(msg, "b", success=False, revision=1, now=T0, error="err")
    status = msg.recipients["a"]
    before = msg.to_dict()

    undo = book.snapshot(ORIGIN, TITLE)
    again = arrive(
        book, at(1), message="Neuer Text", priority=2, data={"image": "/b.jpg"}
    )
    assert again is msg
    assert msg.count == 2
    status.attempts = 7  # nothing does this during an intake today
    status.last_error = "later"
    book.rollback(undo)
    assert book.get(MID) is msg
    assert msg.to_dict() == before
    assert msg.recipients["a"] is status
    assert (status.attempts, status.last_error) == (0, None)

    outcome = book.record_result(msg, "a", success=True, revision=1, now=at(2))
    assert outcome.first_delivery
    assert status.state is RecipientState.DELIVERED


def test_rollback_of_an_unclear_message_restores_its_recipients() -> None:
    """A repeat clears the recipients of an unclear message; rollback restores them."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    book.start_cycle(msg, ["a"], T0)
    book.on_restart(at(1), saved_at=T0)
    assert msg.state is MessageState.UNCLEAR
    before = msg.to_dict()

    undo = book.snapshot(ORIGIN, TITLE)
    arrive(book, at(2))
    book.evaluate(msg, at(2))
    assert msg.recipients == {}
    book.rollback(undo)
    assert msg.to_dict() == before


def test_rollback_of_a_new_generation_restores_the_old_one() -> None:
    """Taking back a new generation puts the old message back, not into history."""
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    deliver_all(book, msg, T0)
    kept = [{"key": "earlier"}]
    book.history = list(kept)
    spacing = dict(book.spacing)

    undo = book.snapshot(ORIGIN, TITLE)
    new = arrive(book, at(1))
    assert new is not msg
    assert len(book.history) == 2
    book.spacing[MID] = at(1)  # nothing does this during an intake today
    book.rollback(undo)
    assert book.get(MID) is msg
    assert msg.state is MessageState.DELIVERED
    assert book.history == kept
    assert book.spacing == spacing == {MID: T0}


def test_message_id_is_opaque_and_stable() -> None:
    """The id is a salted hash: stable for origin and key, nothing of the title in it.

    Same across generations and across books that share the salt, different
    under another salt; 16 hex characters, so neither ':' nor '|'.
    """
    book = MessageBook(salt=SALT)
    msg = arrive(book, T0)
    assert msg.id == MID == book.message_id(ORIGIN, TITLE)
    assert len(msg.id) == 16 and set(msg.id) <= set("0123456789abcdef")
    assert TITLE not in msg.id and ORIGIN not in msg.id
    deliver_all(book, msg, T0)
    second = arrive(book, at(1))  # no spacing: a new generation
    assert second is not msg and second.generation == 2
    assert second.id == MID and book.get(MID) is second

    assert MessageBook().message_id(ORIGIN, TITLE) != MID
    # origin and key are hashed with their lengths: no pair runs into another
    assert message_id(SALT, "a|b", "c") != message_id(SALT, "a", "b|c")
    assert message_id(SALT, "a:b", "c") != message_id(SALT, "a", "b:c")
    assert message_id(SALT, "ab", "") != message_id(SALT, "a", "b")


def test_salt_is_stored_and_a_new_book_makes_its_own() -> None:
    """The salt travels with the book; without a store a book makes one."""
    book = MessageBook(salt=SALT)
    arrive(book, T0)
    data = book.to_dict()
    assert data["id_salt"] == SALT
    assert list(data["messages"]) == [MID]
    assert data["messages"][MID]["id"] == MID
    other = MessageBook()
    assert other.salt != SALT and len(other.salt) == 32
    other.load(data)
    assert other.salt == SALT
    assert other.get(MID) is not None and other.get(MID).id == MID
    assert other.message_id(ORIGIN, TITLE) == MID
