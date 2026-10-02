"""Tests for delivery rules, hold phases and maximum duration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.message_center.lifecycle import HoldKind
from custom_components.message_center.models import ReasonKind
from custom_components.message_center.rules import (
    DEFAULT_EFFECTS,
    Effect,
    RuleBook,
    RuleConfig,
)

NIGHT_START = datetime(2026, 9, 29, 23, 0, tzinfo=UTC)


def clock(hours: float) -> datetime:
    """Return NIGHT_START plus the given hours."""
    return NIGHT_START + timedelta(hours=hours)


def night_rule(**overrides: object) -> RuleConfig:
    """Build a typical night rule: on holds 1 and 2, passes 3, 12 hours."""
    data: dict[str, object] = {
        "rule_id": "night",
        "name": "Nacht",
        "entity_id": "input_boolean.night_mode",
        "state": "on",
        "max_hours": 12,
    }
    data.update(overrides)
    return RuleConfig(**data)  # type: ignore[arg-type]


def test_defaults_hold_1_and_2_pass_3() -> None:
    """The default effects hold priorities 1 and 2 and pass 3."""
    assert DEFAULT_EFFECTS == {1: Effect.HOLD, 2: Effect.HOLD, 3: Effect.PASS}


def test_phase_starts_and_ends_with_entity_state() -> None:
    """Entering the rule state holds, leaving it releases; observe reports changes."""
    book = RuleBook()
    book.configure([night_rule()])
    assert book.verdict(1, clock(0)) is None

    assert book.observe("night", "on", clock(0)) is True
    verdict = book.verdict(1, clock(1))
    assert verdict is not None
    assert verdict.kind is HoldKind.HOLD
    assert verdict.reason.kind is ReasonKind.RULE
    assert verdict.reason.detail == "Nacht"
    assert verdict.reason.until == clock(12)
    assert book.verdict(3, clock(1)) is None

    assert book.observe("night", "on", clock(2)) is False
    assert book.observe("night", "off", clock(8)) is True
    assert book.verdict(1, clock(8)) is None
    assert book.active(clock(8)) == []


def test_unknown_entity_counts_as_active_with_reason() -> None:
    """Unavailable, unknown or missing entities hold with reason "mode unknown"."""
    book = RuleBook()
    book.configure([night_rule()])
    for state in ("unavailable", "unknown", None):
        fresh = RuleBook()
        fresh.configure([night_rule()])
        assert fresh.observe("night", state, clock(0)) is True
        verdict = fresh.verdict(2, clock(0.5))
        assert verdict is not None
        assert verdict.reason.kind is ReasonKind.RULE_UNKNOWN
        assert verdict.reason.entity_id == "input_boolean.night_mode"
        assert [r.rule_id for r in fresh.unknown_rules()] == ["night"]
    assert book.unknown_rules() == []


def test_outage_in_the_night_does_not_restart_the_phase() -> None:
    """Example: on since 23:00, unavailable 03:00, on 03:10 → ends 11:00."""
    book = RuleBook()
    book.configure([night_rule()])
    book.observe("night", "on", clock(0))
    assert book.observe("night", "unavailable", clock(4)) is True
    assert book.verdict(1, clock(4)).reason.kind is ReasonKind.RULE_UNKNOWN  # type: ignore[union-attr]
    assert book.observe("night", "on", clock(4 + 10 / 60)) is True
    verdict = book.verdict(1, clock(5))
    assert verdict is not None
    assert verdict.reason.kind is ReasonKind.RULE
    assert verdict.reason.until == clock(12)
    active = book.active(clock(5))
    assert len(active) == 1
    assert active[0].since == clock(0)
    assert active[0].until == clock(12)
    assert not active[0].expired


def test_expired_rule_releases_and_does_not_apply_again() -> None:
    """After the maximum the rule no longer holds until the phase ends."""
    book = RuleBook()
    book.configure([night_rule()])
    book.observe("night", "on", clock(0))
    assert book.next_expiry(clock(1)) == clock(12)
    assert book.newly_expired(clock(11)) == []
    assert book.verdict(1, clock(11.99)) is not None

    expired = book.newly_expired(clock(12))
    assert [r.rule_id for r in expired] == ["night"]
    assert book.newly_expired(clock(12.5)) == []
    assert book.verdict(1, clock(12)) is None
    assert book.is_expired("night", clock(12))
    assert book.active(clock(12))[0].expired
    assert book.next_expiry(clock(12)) is None

    # still on at 12:30: no new phase, no hold
    assert book.observe("night", "on", clock(13.5)) is False
    assert book.verdict(1, clock(13.5)) is None
    # unknown while expired: still no hold, still expired
    book.observe("night", "unavailable", clock(14))
    assert book.verdict(1, clock(14)) is None

    # phase ends, next entry starts a fresh phase with a fresh maximum
    assert book.observe("night", "off", clock(15)) is True
    assert book.observe("night", "on", clock(24)) is True
    verdict = book.verdict(1, clock(24))
    assert verdict is not None
    assert verdict.reason.until == clock(36)
    assert [r.rule_id for r in book.newly_expired(clock(36))] == ["night"]


def test_strictest_rule_decides_and_names_itself() -> None:
    """Discard beats hold; among equal effects the rule ending last decides."""
    book = RuleBook()
    holiday = RuleConfig(
        rule_id="holiday",
        name="Urlaub",
        entity_id="input_boolean.urlaub",
        state="on",
        max_hours=168,
        effects={1: Effect.DISCARD, 2: Effect.HOLD, 3: Effect.PASS},
    )
    book.configure([night_rule(), holiday])
    book.observe("night", "on", clock(0))
    book.observe("holiday", "on", clock(1))

    v1 = book.verdict(1, clock(2))
    assert v1 is not None
    assert v1.kind is HoldKind.DISCARD
    assert v1.reason.detail == "Urlaub"

    v2 = book.verdict(2, clock(2))
    assert v2 is not None
    assert v2.kind is HoldKind.HOLD
    assert v2.reason.detail == "Urlaub"
    assert v2.reason.until == clock(1 + 168)

    assert book.verdict(3, clock(2)) is None

    # night expires at 12:00, holiday keeps holding priority 2
    book.newly_expired(clock(12))
    v2_later = book.verdict(2, clock(12))
    assert v2_later is not None
    assert v2_later.reason.detail == "Urlaub"

    # holiday ends: nothing left, night is expired
    book.observe("holiday", "off", clock(13))
    assert book.verdict(2, clock(13)) is None


def test_two_rules_one_expires_other_decides() -> None:
    """When the deciding rule expires the remaining active rule takes over."""
    book = RuleBook()
    short = night_rule(rule_id="short", name="Kurz", max_hours=2)
    long = night_rule(
        rule_id="long", name="Lang", entity_id="input_boolean.gast", max_hours=10
    )
    book.configure([short, long])
    book.observe("short", "on", clock(0))
    book.observe("long", "on", clock(0))
    assert book.verdict(1, clock(1)).reason.detail == "Lang"  # type: ignore[union-attr]
    assert book.verdict(1, clock(3)).reason.detail == "Lang"  # type: ignore[union-attr]
    book.observe("long", "off", clock(4))
    assert book.verdict(1, clock(4)) is None


def test_custom_effects_can_hold_priority_3() -> None:
    """Effects are configurable per priority."""
    book = RuleBook()
    book.configure(
        [night_rule(effects={1: Effect.HOLD, 2: Effect.HOLD, 3: Effect.HOLD})]
    )
    book.observe("night", "on", clock(0))
    assert book.verdict(3, clock(1)) is not None


def test_configure_drops_phases_of_removed_rules() -> None:
    """Removing a rule removes its running phase."""
    book = RuleBook()
    book.configure([night_rule()])
    book.observe("night", "on", clock(0))
    book.configure([])
    assert book.phases == {}
    assert book.verdict(1, clock(1)) is None
    assert book.observe("night", "on", clock(1)) is False


def test_phases_survive_restart_and_keep_their_maximum() -> None:
    """Persisted phases restore with the original start and maximum."""
    book = RuleBook()
    book.configure([night_rule()])
    book.observe("night", "on", clock(0))
    book.newly_expired(clock(12))
    data = book.to_dict()

    restored = RuleBook()
    restored.configure([night_rule()])
    restored.load(data)
    assert restored.phases["night"].since == clock(0)
    assert restored.phases["night"].max_until == clock(12)
    assert restored.newly_expired(clock(13)) == []
    assert restored.to_dict() == data

    other = RuleBook()
    other.configure([night_rule(rule_id="different")])
    other.load(data)
    assert other.phases == {}
