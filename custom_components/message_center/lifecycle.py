"""State machine of the message center.

The MessageBook keeps every message in memory and applies the transitions
between its states. It never talks to Home Assistant: the delivery layer feeds
in the results of push attempts and acts on the decisions returned here. All
times are passed in by the caller, which keeps the behaviour fully testable.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, fields, replace
from datetime import datetime, timedelta
from enum import StrEnum
import secrets
from typing import Any

from .const import (
    END_STATE_RETENTION,
    MAX_OPEN_MESSAGES,
    MAX_PENDING_HISTORY,
    MAX_WAIT,
    RECIPIENT_GIVE_UP,
    RESTART_GAP,
    RETRY_DELAYS,
    RETRY_INTERVAL,
    SPACING_RETENTION,
)
from .models import (
    END_STATES,
    Message,
    MessageState,
    Reason,
    ReasonKind,
    RecipientState,
    RecipientStatus,
    message_id,
)


class StoreFullError(Exception):
    """The limit of open messages is reached."""


class NotFoundError(Exception):
    """No matching message for discard, snooze or forward."""


class AcceptAction(StrEnum):
    """What an intake did with the message (result field ``action``)."""

    CREATED = "created"
    UPDATED = "updated"
    BUNDLED = "bundled"


@dataclass(slots=True)
class AcceptResult:
    """Outcome of ``accept``."""

    action: AcceptAction
    message: Message


class HoldKind(StrEnum):
    """Effect of the delivery rules on a message."""

    HOLD = "hold"
    DISCARD = "discard"


@dataclass(slots=True)
class RuleVerdict:
    """What the delivery rules say about a message right now."""

    kind: HoldKind
    reason: Reason


class Decision(StrEnum):
    """What the delivery layer has to do after ``evaluate``."""

    SEND = "send"
    REPLACE = "replace"
    WAIT = "wait"
    NONE = "none"
    ENDED = "ended"


class ResultOutcome(StrEnum):
    """How a delivery result was taken."""

    RECORDED = "recorded"
    LATE = "late"


@dataclass(slots=True)
class DeliveryOutcome:
    """Outcome of ``record_result``."""

    outcome: ResultOutcome
    first_delivery: bool = False
    cycle_ended: bool = False


@dataclass(slots=True)
class Attempt:
    """One push under way: the reserved recipients and the version it carries.

    ``recipients`` holds the recipient states that are still reserved; a
    recorded result takes its recipient out. ``revision`` and ``count`` are
    what the push shows, noted when it was reserved. ``replace`` marks the
    replacement of a delivered push instead of a delivery.
    """

    message: Message
    recipients: dict[str, RecipientStatus]
    revision: int
    count: int
    replace: bool = False


@dataclass(slots=True)
class RestartResult:
    """Messages touched by ``on_restart``."""

    unclear: list[Message] = field(default_factory=list)
    waiting: list[Message] = field(default_factory=list)
    ended: list[Message] = field(default_factory=list)


@dataclass(slots=True)
class IntakeUndo:
    """What ``rollback`` needs to take one intake back."""

    mid: str
    message: Message | None
    values: dict[str, Any]
    recipients: dict[str, RecipientStatus]
    spacing: datetime | None
    pending: int
    dropped: int


def retry_delay(attempts: int) -> timedelta:
    """Delay after the first failure of the n-th time in the retry plan.

    1, 5 and 15 minutes, then hourly.
    """
    if attempts <= len(RETRY_DELAYS):
        return RETRY_DELAYS[attempts - 1]
    return RETRY_DELAYS[-1] + RETRY_INTERVAL * (attempts - len(RETRY_DELAYS))


def next_retry(first_failed_at: datetime, now: datetime) -> datetime | None:
    """Next time of the retry plan after ``now``; None once it is given up.

    The plan hangs on the time of the first failure, not on the number of
    attempts. A result booked twice, an attempt left out while
    a rule held the message and a gap over a restart do not shift it.
    """
    attempt = 1
    while (delay := retry_delay(attempt)) < RECIPIENT_GIVE_UP:
        if first_failed_at + delay > now:
            return first_failed_at + delay
        attempt += 1
    return None


# reasons of a message that a delivery rule holds back
RULE_REASONS = (ReasonKind.RULE, ReasonKind.RULE_UNKNOWN)


class MessageBook:
    """All messages of the message center with their transitions.

    Messages and spacing are keyed by the message id, a hash over origin and
    key with the book's salt (``message_id``). The salt is made once for a
    new book and stored with it, so the ids stay the same over restarts.
    """

    def __init__(
        self,
        *,
        salt: str | None = None,
        max_open: int = MAX_OPEN_MESSAGES,
        max_pending: int = MAX_PENDING_HISTORY,
    ) -> None:
        """Create an empty book, with a new salt unless one is given."""
        self.salt = salt or secrets.token_hex(16)
        self.max_open = max_open
        self.max_pending = max_pending
        self.messages: dict[str, Message] = {}
        self.spacing: dict[str, datetime] = {}
        # end states on their way to the history store, saved with the book;
        # never more than max_pending, the oldest go and are counted
        self.history: list[dict[str, Any]] = []
        self.history_dropped = 0

    # ----- queries -----------------------------------------------------------

    def message_id(self, origin: str, key: str) -> str:
        """Return the id a message of this origin and key has in this book."""
        return message_id(self.salt, origin, key)

    def get(self, mid: str) -> Message | None:
        """Return the message with this id, in any state."""
        return self.messages.get(mid)

    def open(self) -> list[Message]:
        """All open messages, in acceptance order."""
        return sorted(
            (m for m in self.messages.values() if m.is_open),
            key=lambda m: m.accepted_at,
        )

    def spacing_until(self, msg: Message) -> datetime | None:
        """End of the minimum spacing for this message, if one applies."""
        if not msg.spacing:
            return None
        last = self.spacing.get(msg.id)
        if last is None:
            return None
        return last + timedelta(minutes=msg.spacing)

    # ----- intake ------------------------------------------------------------

    def accept(
        self,
        *,
        origin: str,
        key: str,
        title: str,
        message: str,
        priority: int,
        now: datetime,
        data: dict[str, Any] | None = None,
        origin_name: str | None = None,
        labels: Iterable[str] = (),
        kind_id: str | None = None,
        group_id: str | None = None,
        spacing: int = 0,
        expires_after: int = 0,
        no_hold: bool = False,
        context_id: str | None = None,
        user_id: str | None = None,
        from_effect: bool = False,
    ) -> AcceptResult:
        """Take an incoming message.

        The same origin and key increase the counter of an existing message.
        A delivered message within its spacing is bundled: counter up, push
        replaced silently. Otherwise a new generation starts. Raises
        StoreFullError when a new message would exceed the open limit.

        ``from_effect`` marks an arrival sent by an effect of the center
        itself. An existing message keeps the mark only when every arrival
        carried it, so a real message keeps its effect.
        """
        mid = self.message_id(origin, key)
        existing = self.messages.get(mid)
        expires_at = now + timedelta(minutes=expires_after) if expires_after else None

        if existing is not None and (
            existing.is_open
            or (
                existing.state is MessageState.DELIVERED
                and existing.spacing
                and (until := self.spacing_until(existing)) is not None
                and until > now
            )
        ):
            existing.count += 1
            existing.updated_at = now
            changed = existing.title != title or existing.message != message
            if changed:
                existing.revision += 1
                existing.title = title
                existing.message = message
            existing.data = dict(data or {})
            existing.priority = priority
            existing.kind_id = kind_id
            existing.group_id = group_id
            existing.no_hold = no_hold
            existing.from_effect = existing.from_effect and from_effect
            if spacing:
                existing.spacing = spacing
            if expires_at is not None and existing.is_open:
                existing.expires_at = expires_at
            if existing.state is MessageState.UNCLEAR:
                # a new arrival replaces the unclear message and runs normally
                existing.state = MessageState.WAITING
                existing.reason = Reason(ReasonKind.EVALUATING)
                existing.recipients = {}
            if existing.state is MessageState.DELIVERED:
                return AcceptResult(AcceptAction.BUNDLED, existing)
            return AcceptResult(AcceptAction.UPDATED, existing)

        if sum(1 for m in self.messages.values() if m.is_open) >= self.max_open:
            raise StoreFullError

        generation = 1
        if existing is not None:
            generation = existing.generation + 1
            self._to_history(existing)

        msg = Message(
            id=mid,
            origin=origin,
            origin_name=origin_name,
            labels=list(labels),
            key=key,
            kind_id=kind_id,
            group_id=group_id,
            title=title,
            message=message,
            data=dict(data or {}),
            priority=priority,
            accepted_at=now,
            updated_at=now,
            generation=generation,
            spacing=spacing,
            no_hold=no_hold,
            expires_at=expires_at,
            context_id=context_id,
            user_id=user_id,
            from_effect=from_effect,
        )
        self.messages[mid] = msg
        return AcceptResult(AcceptAction.CREATED, msg)

    def snapshot(self, origin: str, key: str) -> IntakeUndo:
        """Remember one message before an intake so that it can be taken back."""
        mid = self.message_id(origin, key)
        msg = self.messages.get(mid)
        values: dict[str, Any] = {}
        recipients: dict[str, RecipientStatus] = {}
        if msg is not None:
            for item in fields(msg):
                value = getattr(msg, item.name)
                values[item.name] = (
                    value.copy() if isinstance(value, (dict, list)) else value
                )
            recipients = {name: replace(st) for name, st in msg.recipients.items()}
        return IntakeUndo(
            mid=mid,
            message=msg,
            values=values,
            recipients=recipients,
            spacing=self.spacing.get(mid),
            pending=len(self.history),
            dropped=self.history_dropped,
        )

    def rollback(self, undo: IntakeUndo) -> None:
        """Take back what an intake did to its one message.

        The message, its recipient states and every other message stay the
        same objects: a push running meanwhile holds them and records its
        result there. Loading the whole book anew would orphan it. The
        recipient states get their fields back, except the mark of a running
        push: that belongs to the push, which gives it back itself. The
        spacing is put back although the intake does not touch it today.
        The end state the intake queued for the history is taken out again;
        one that the limit dropped meanwhile is gone, and stays counted.
        """
        msg = undo.message
        if msg is None:
            self.messages.pop(undo.mid, None)
        else:
            for name, value in undo.values.items():
                setattr(msg, name, value)
            for name, saved in undo.recipients.items():
                status = msg.recipients[name]
                for item in fields(saved):
                    if item.name != "in_flight":
                        setattr(status, item.name, getattr(saved, item.name))
            self.messages[undo.mid] = msg
        if undo.spacing is None:
            self.spacing.pop(undo.mid, None)
        else:
            self.spacing[undo.mid] = undo.spacing
        queued = len(self.history) + self.history_dropped - undo.dropped - undo.pending
        if queued:
            del self.history[-queued:]

    # ----- evaluation --------------------------------------------------------

    def evaluate(
        self, msg: Message, now: datetime, verdict: RuleVerdict | None = None
    ) -> Decision:
        """Decide what happens next with a message.

        ``verdict`` is the current effect of the delivery rules, or None when
        no rule holds the message. Messages with ``no_hold`` ignore rules.
        """
        if msg.state is MessageState.DELIVERED:
            return (
                Decision.REPLACE if self.recipients_to_replace(msg) else Decision.NONE
            )
        if msg.state in END_STATES:
            return Decision.NONE
        if self._expire_one(msg, now):
            return Decision.ENDED
        if msg.state in (MessageState.SENDING, MessageState.RETRYING):
            return Decision.NONE
        if msg.state is MessageState.UNCLEAR:
            return Decision.NONE

        if msg.snoozed_until is not None and msg.snoozed_until > now:
            msg.state = MessageState.WAITING
            msg.reason = Reason(ReasonKind.SNOOZED, until=msg.snoozed_until)
            return Decision.WAIT
        msg.snoozed_until = None

        if verdict is not None and not msg.no_hold:
            if verdict.kind is HoldKind.DISCARD:
                self._end(msg, MessageState.DISCARDED, ReasonKind.RULE_DISCARDED, now)
                return Decision.ENDED
            msg.state = MessageState.WAITING
            msg.reason = verdict.reason
            return Decision.WAIT
        until = self.spacing_until(msg)
        if until is not None and until > now:
            msg.state = MessageState.WAITING
            msg.reason = Reason(ReasonKind.SPACING, until=until)
            return Decision.WAIT
        return Decision.SEND

    # ----- push cycle --------------------------------------------------------

    def start_cycle(
        self, msg: Message, recipients: Iterable[str], now: datetime
    ) -> None:
        """Begin a push cycle for all recipients."""
        msg.state = MessageState.SENDING
        msg.reason = Reason(ReasonKind.SENDING)
        msg.recipients = {name: RecipientStatus() for name in recipients}
        msg.cycle_started_at = now
        msg.light_done = False
        msg.snoozed_until = None
        msg.ended_at = None
        self._check_cycle_end(msg, now)

    def begin_attempt(
        self, msg: Message, now: datetime, verdict: RuleVerdict | None = None
    ) -> Attempt | None:
        """Reserve the recipients whose push is due now.

        Checked in this order: the state, the expiry, for a retry the
        delivery rules, then the due recipients. None when nothing is to be
        pushed. A recipient whose push is running is never taken again.

        The first push of a cycle was released by ``evaluate``. A retry asks
        the rules anew: ``verdict`` is their current effect on the message,
        which it ignores with ``no_hold``. While a rule holds it, a due
        recipient moves on to the next time of its plan and the message
        shows the reason of the rule; its 24 hours run on. A rule that
        discards closes the cycle, unless its entity cannot be read: what is
        not known only holds, it never ends a cycle that was released before.
        Once nothing holds a retry that was held back, its recipients are due
        at once, as waiting messages are.
        """
        if self.messages.get(msg.id) is not msg:
            return None
        if msg.state not in (MessageState.SENDING, MessageState.RETRYING):
            return None
        if self._expire_one(msg, now):
            return None
        retrying = msg.state is MessageState.RETRYING
        held = retrying and msg.reason.kind in RULE_REASONS
        rule = verdict if retrying and not msg.no_hold else None
        idle = {
            name: status
            for name, status in msg.recipients.items()
            if not status.is_final and not status.in_flight
        }
        if held and rule is None:
            for status in idle.values():
                status.next_try = now
        due = [
            name
            for name, status in idle.items()
            if status.next_try is None or status.next_try <= now
        ]
        if rule is not None and (due or held):
            if (
                rule.kind is HoldKind.DISCARD
                and rule.reason.kind is not ReasonKind.RULE_UNKNOWN
            ):
                self._close_cycle(msg, ReasonKind.RULE_DISCARDED, now)
                return None
            for name in due:
                self._plan_retry(idle[name], now)
            if not self._check_cycle_end(msg, now):
                msg.reason = rule.reason
            return None
        attempt = self._reserve(msg, due)
        if attempt is not None and retrying:
            msg.reason = self._retry_reason(msg)
        return attempt

    def begin_replace(self, msg: Message) -> Attempt | None:
        """Reserve the delivered recipients that show an older version.

        None when nothing is to be replaced: every recipient is up to date,
        or a replacement to it is still running. When that one ends, the
        caller asks again and the newest text and counter follow.
        """
        if self.messages.get(msg.id) is not msg:
            return None
        if msg.state not in (MessageState.DELIVERED, MessageState.RETRYING):
            return None
        return self._reserve(msg, self.recipients_to_replace(msg), replace=True)

    @staticmethod
    def _reserve(
        msg: Message, names: list[str], *, replace: bool = False
    ) -> Attempt | None:
        """Mark the recipients as running; note the revision and counter sent."""
        if not names:
            return None
        recipients = {name: msg.recipients[name] for name in names}
        for status in recipients.values():
            status.in_flight = True
        return Attempt(msg, recipients, msg.revision, msg.count, replace)

    def finish_attempt(
        self,
        attempt: Attempt,
        recipient: str,
        *,
        success: bool,
        now: datetime,
        error: str | None = None,
    ) -> DeliveryOutcome:
        """Take the result of a reserved push and give the recipient back.

        It counts only when the message still holds the very recipient state
        that was reserved: a new cycle starts with new ones, and a result of
        the old cycle must not land there. A replacement confirms just
        the revision and counter it carried; a failed one leaves the lag
        visible.
        """
        msg = attempt.message
        status = attempt.recipients.pop(recipient)
        status.in_flight = False
        if msg.recipients.get(recipient) is not status:
            return DeliveryOutcome(ResultOutcome.LATE)
        if not attempt.replace:
            return self.record_result(
                msg,
                recipient,
                success=success,
                revision=attempt.revision,
                count=attempt.count,
                now=now,
                error=error,
            )
        if success:
            self.mark_replaced(
                msg, recipient, revision=attempt.revision, count=attempt.count
            )
        return DeliveryOutcome(ResultOutcome.RECORDED)

    @staticmethod
    def release_attempt(attempt: Attempt) -> None:
        """Give back recipients whose push ended without a result (cancelled)."""
        for status in attempt.recipients.values():
            status.in_flight = False
        attempt.recipients.clear()

    def record_result(
        self,
        msg: Message,
        recipient: str,
        *,
        success: bool,
        revision: int,
        now: datetime,
        error: str | None = None,
        count: int | None = None,
    ) -> DeliveryOutcome:
        """Take the result of one push attempt.

        The number of attempts is only counted. The next retry follows the
        time since the first failure of the recipient, see ``next_retry``.
        """
        if msg.state not in (MessageState.SENDING, MessageState.RETRYING):
            return DeliveryOutcome(ResultOutcome.LATE)
        status = msg.recipients.get(recipient)
        if status is None or status.is_final:
            return DeliveryOutcome(ResultOutcome.LATE)

        first_delivery = False
        if success:
            first_delivery = not msg.delivered_recipients
            status.state = RecipientState.DELIVERED
            status.delivered_at = now
            status.delivered_revision = revision
            status.delivered_count = count if count is not None else msg.count
            status.next_try = None
            status.last_error = None
            msg.delivered_at = now
            if first_delivery:
                # spacing counts from the first delivery of a cycle
                self.spacing[msg.id] = now
        else:
            status.attempts += 1
            status.last_error = error
            if status.first_failed_at is None:
                status.first_failed_at = now
            self._plan_retry(status, now)

        cycle_ended = self._check_cycle_end(msg, now)
        return DeliveryOutcome(ResultOutcome.RECORDED, first_delivery, cycle_ended)

    @staticmethod
    def _plan_retry(status: RecipientStatus, now: datetime) -> None:
        """Put a recipient on the next time of its plan, or give it up."""
        if status.first_failed_at is None:
            return
        status.next_try = next_retry(status.first_failed_at, now)
        if status.next_try is None:
            status.state = RecipientState.FAILED

    def _check_cycle_end(self, msg: Message, now: datetime) -> bool:
        """Close the cycle when every recipient is final; else set retrying/sending."""
        statuses = msg.recipients.values()
        if all(s.is_final for s in statuses):
            if msg.delivered_recipients:
                self._end(msg, MessageState.DELIVERED, ReasonKind.DELIVERED, now)
            else:
                self._end(msg, MessageState.FAILED, ReasonKind.NO_RECIPIENT, now)
            return True
        if any(s.attempts and not s.is_final for s in statuses):
            msg.state = MessageState.RETRYING
            if msg.reason.kind not in RULE_REASONS:  # held back: reason stays
                msg.reason = self._retry_reason(msg)
        else:
            msg.state = MessageState.SENDING
            msg.reason = Reason(ReasonKind.SENDING)
        return False

    @staticmethod
    def _retry_reason(msg: Message) -> Reason:
        """Reason of a message in retrying, with the earliest planned retry."""
        tries = [s.next_try for s in msg.recipients.values() if s.next_try is not None]
        return Reason(ReasonKind.RETRY, until=min(tries) if tries else None)

    def _close_cycle(self, msg: Message, kind: ReasonKind, now: datetime) -> bool:
        """End a cycle in retrying without further pushes.

        Pending recipients are failed. Delivered to at least one, the message
        is delivered with them as ``failed_recipients``; else it is discarded
        with the given reason.

        A recipient whose push is out is left to its result, as a first push
        is: what reaches the phone must not end up as discarded. The cycle
        then stays open, False is returned, and it is closed after the result.
        """
        under_way = False
        for status in msg.recipients.values():
            if status.is_final:
                continue
            if status.in_flight:
                under_way = True
            else:
                status.state = RecipientState.FAILED
                status.next_try = None
        if under_way:
            return False
        if msg.delivered_recipients:
            self._end(msg, MessageState.DELIVERED, ReasonKind.DELIVERED, now)
        else:
            self._end(msg, MessageState.DISCARDED, kind, now)
        return True

    def recipients_to_replace(self, msg: Message) -> list[str]:
        """Delivered recipients showing an older revision or counter.

        Without those a replacement is running to.
        """
        return [
            name
            for name, status in msg.recipients.items()
            if status.state is RecipientState.DELIVERED
            and not status.in_flight
            and (
                (
                    status.delivered_revision is not None
                    and status.delivered_revision < msg.revision
                )
                or (
                    status.delivered_count is not None
                    and status.delivered_count < msg.count
                )
            )
        ]

    def mark_replaced(
        self, msg: Message, recipient: str, *, revision: int, count: int
    ) -> None:
        """Note the revision and counter a replacement carried to a recipient.

        Only what was sent is confirmed, and never less than already noted:
        the message may have changed while the push was under way.
        """
        status = msg.recipients.get(recipient)
        if status is not None:
            status.delivered_revision = max(status.delivered_revision or 0, revision)
            status.delivered_count = max(status.delivered_count or 0, count)

    # ----- commands ----------------------------------------------------------

    def discard(self, mid: str, now: datetime) -> Message:
        """Discard an open message; delivered ones are untouched."""
        msg = self.messages.get(mid)
        if msg is None or not msg.is_open:
            raise NotFoundError
        self._end(msg, MessageState.DISCARDED, ReasonKind.DISCARDED, now)
        return msg

    def discard_matching(self, origin: str, title: str, now: datetime) -> list[Message]:
        """Discard open messages with this origin and title."""
        result: list[Message] = []
        for msg in self.open():
            if msg.origin == origin and msg.title == title:
                self._end(msg, MessageState.DISCARDED, ReasonKind.DISCARDED, now)
                result.append(msg)
        return result

    def snooze(self, mid: str, minutes: int, now: datetime) -> Message:
        """Put a message back until later."""
        msg = self.messages.get(mid)
        if msg is None or msg.state in (MessageState.DISCARDED, MessageState.FAILED):
            raise NotFoundError
        msg.snoozed_until = now + timedelta(minutes=minutes)
        msg.state = MessageState.WAITING
        msg.reason = Reason(ReasonKind.SNOOZED, until=msg.snoozed_until)
        msg.ended_at = None
        for status in msg.recipients.values():
            status.next_try = None
        return msg

    def send_now(self, mid: str, now: datetime) -> Message:
        """Release a waiting, unclear or retrying message for sending now (page).

        From then on the rules are passed over (``no_hold``). A waiting or
        unclear message is evaluated anew and starts a cycle. A message in
        retrying keeps its cycle: the recipients that have it keep it, the
        idle ones are due now, whether a rule held the retry back or its plan
        time is still ahead, and the reason is the usual one of a retry. A
        push that is out is left to its result.
        """
        msg = self.messages.get(mid)
        if msg is None or msg.state not in (
            MessageState.WAITING,
            MessageState.UNCLEAR,
            MessageState.RETRYING,
        ):
            raise NotFoundError
        msg.snoozed_until = None
        msg.no_hold = True
        if msg.state is MessageState.RETRYING:
            for status in msg.recipients.values():
                if not status.is_final and not status.in_flight:
                    status.next_try = now
            msg.reason = self._retry_reason(msg)
            return msg
        msg.state = MessageState.WAITING
        msg.reason = Reason(ReasonKind.EVALUATING)
        msg.recipients = {}
        return msg

    def forward(self, mid: str, now: datetime) -> Message:
        """Mark a message as handed to the assistant."""
        msg = self.messages.get(mid)
        if msg is None:
            raise NotFoundError
        msg.forwarded_at = now
        return msg

    # ----- time --------------------------------------------------------------

    def apply_expiry(self, now: datetime) -> list[Message]:
        """End expired messages and those waiting longer than 7 days."""
        return [msg for msg in self.open() if self._expire_one(msg, now)]

    def _expire_one(self, msg: Message, now: datetime) -> bool:
        """Apply expiry and maximum wait; True when the message ended.

        Waiting and unclear messages are discarded. A message in retrying
        stops being retried; what a recipient already has stays delivered.
        A push under way is left to its result, the first one of a cycle as
        well as a retry: see ``expiry_waits``.
        """
        if msg.state not in (
            MessageState.WAITING,
            MessageState.UNCLEAR,
            MessageState.RETRYING,
        ):
            return False
        if msg.expires_at is not None and msg.expires_at <= now:
            kind = ReasonKind.EXPIRED
        elif msg.delivered_at is None and msg.accepted_at + MAX_WAIT <= now:
            kind = ReasonKind.MAX_WAIT
        else:
            return False
        if msg.state is MessageState.RETRYING:
            return self._close_cycle(msg, kind, now)
        self._end(msg, MessageState.DISCARDED, kind, now)
        return True

    @staticmethod
    def expiry_waits(msg: Message) -> bool:
        """Return True while a push that is out comes before the expiry.

        That is the first push of a cycle and a retry under way. The caller
        arms no timer for the expiry meanwhile; it applies once the result is
        in.
        """
        return msg.state is MessageState.SENDING or (
            msg.state is MessageState.RETRYING
            and any(s.in_flight and not s.is_final for s in msg.recipients.values())
        )

    def on_restart(self, now: datetime, saved_at: datetime | None) -> RestartResult:
        """Reconcile after a start."""
        result = RestartResult(ended=self.apply_expiry(now))
        gap = now - saved_at if saved_at is not None else None
        for msg in self.open():
            if gap is None or gap > RESTART_GAP:
                hours = round(gap.total_seconds() / 3600) if gap is not None else None
                msg.state = MessageState.UNCLEAR
                msg.reason = Reason(
                    ReasonKind.GAP, detail=str(hours) if hours is not None else None
                )
                for status in msg.recipients.values():
                    status.next_try = None
                result.unclear.append(msg)
            elif msg.state is MessageState.SENDING:
                msg.state = MessageState.UNCLEAR
                msg.reason = Reason(ReasonKind.RESTART)
                for status in msg.recipients.values():
                    status.next_try = None
                result.unclear.append(msg)
            elif msg.state is MessageState.WAITING:
                result.waiting.append(msg)
        return result

    def due_retries(self, now: datetime) -> list[tuple[Message, str]]:
        """Recipients whose retry is due and not running."""
        due: list[tuple[Message, str]] = []
        for msg in self.open():
            if msg.state is not MessageState.RETRYING:
                continue
            for name, status in msg.recipients.items():
                if status.in_flight:
                    continue
                if status.next_try is not None and status.next_try <= now:
                    due.append((msg, name))
        return due

    def due_waits(self, now: datetime) -> list[Message]:
        """Return waiting messages whose spacing or snooze has ended."""
        return [
            msg
            for msg in self.open()
            if msg.state is MessageState.WAITING
            and msg.reason.kind in (ReasonKind.SPACING, ReasonKind.SNOOZED)
            and msg.reason.until is not None
            and msg.reason.until <= now
        ]

    def prune(self, now: datetime) -> None:
        """Move old end states to history, drop old spacing entries.

        A delivered message stays while its spacing runs, so that repeats can
        still be bundled onto it.
        """
        for mid, msg in list(self.messages.items()):
            if msg.is_open or msg.ended_at is None:
                continue
            if msg.ended_at + END_STATE_RETENTION > now:
                continue
            until = self.spacing_until(msg)
            if (
                msg.state is MessageState.DELIVERED
                and until is not None
                and until > now
            ):
                continue
            self._to_history(msg)
            del self.messages[mid]
        for mid, last in list(self.spacing.items()):
            if last + SPACING_RETENTION <= now:
                del self.spacing[mid]

    def _to_history(self, msg: Message) -> None:
        """Queue an end state for the history store, within the limit.

        Over the limit the oldest entries go; how many is counted for the
        center to log. The book itself logs nothing.
        """
        self.history.append(msg.to_dict())
        self._cap_history()

    def _cap_history(self) -> None:
        excess = len(self.history) - self.max_pending
        if excess > 0:
            del self.history[:excess]
            self.history_dropped += excess

    def drain_history(self) -> list[dict[str, Any]]:
        """Empty the collected end states once the history store has them."""
        entries, self.history = self.history, []
        return entries

    # ----- persistence -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise salt, messages, spacing and pending history for the store."""
        return {
            "id_salt": self.salt,
            "messages": {mid: msg.to_dict() for mid, msg in self.messages.items()},
            "spacing": {mid: ts.isoformat() for mid, ts in self.spacing.items()},
            "pending_history": list(self.history),
        }

    def load(self, data: dict[str, Any]) -> None:
        """Restore salt, messages, spacing and pending history from the store.

        Messages and pending end states are checked: a malformed one, or one
        whose id is not the one its origin and key have under the salt,
        raises here instead of living on with an id that nothing finds. More
        pending end states than the limit are cut to the newest, counted.
        """
        salt = str(data["id_salt"])
        if not salt:
            raise ValueError("store without salt")
        self.salt = salt
        messages = {
            mid: Message.from_dict(raw) for mid, raw in data.get("messages", {}).items()
        }
        for mid, msg in messages.items():
            if msg.id != mid:
                raise ValueError("message under a foreign id")
            self._check_id(msg)
        pending = list(data.get("pending_history", []))
        for entry in pending:
            self._check_id(Message.from_dict(entry))
        self.messages = messages
        self.spacing = {
            mid: datetime.fromisoformat(ts)
            for mid, ts in data.get("spacing", {}).items()
        }
        self.history = pending
        self._cap_history()

    def _check_id(self, msg: Message) -> None:
        if msg.id != self.message_id(msg.origin, msg.key):
            raise ValueError("message id does not match origin and key")

    # ----- helpers -----------------------------------------------------------

    @staticmethod
    def _end(
        msg: Message, state: MessageState, kind: ReasonKind, now: datetime
    ) -> None:
        msg.state = state
        msg.reason = Reason(kind)
        msg.ended_at = now
        msg.snoozed_until = None
        for status in msg.recipients.values():
            status.next_try = None
