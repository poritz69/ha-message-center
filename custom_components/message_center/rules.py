"""Delivery rules with hold phases and maximum duration.

A rule watches one entity. While the entity is in the rule state, or its state
is unknown, the rule is in a hold phase and its effect per priority applies:
pass, hold or discard. A phase begins on the first entry and ends only when
the entity takes another known state; switching between the rule state and
unknown does not end it. When the phase lasts longer than the maximum, the
rule is expired: it no longer applies until the phase ends.

This module is pure logic. The caller feeds in entity states and times and
persists the phases through ``to_dict``/``load``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Self

from .lifecycle import HoldKind, RuleVerdict
from .models import Reason, ReasonKind

UNKNOWN_STATES: frozenset[str | None] = frozenset({None, "unknown", "unavailable"})


class Effect(StrEnum):
    """What a rule does with a message of a given priority."""

    PASS = "pass"
    HOLD = "hold"
    DISCARD = "discard"


STRICTNESS: dict[Effect, int] = {Effect.PASS: 0, Effect.HOLD: 1, Effect.DISCARD: 2}

DEFAULT_EFFECTS: dict[int, Effect] = {1: Effect.HOLD, 2: Effect.HOLD, 3: Effect.PASS}


@dataclass(slots=True)
class RuleConfig:
    """Configuration of one delivery rule (from a config subentry)."""

    rule_id: str
    name: str
    entity_id: str
    state: str
    max_hours: int
    effects: dict[int, Effect] = field(default_factory=lambda: dict(DEFAULT_EFFECTS))

    def effect_for(self, priority: int) -> Effect:
        """Effect for a priority; unknown priorities are held."""
        return self.effects.get(priority, Effect.HOLD)


@dataclass(slots=True)
class RulePhase:
    """A running hold phase of a rule."""

    since: datetime
    max_until: datetime
    unknown: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialise for the store."""
        return {
            "since": self.since.isoformat(),
            "max_until": self.max_until.isoformat(),
            "unknown": self.unknown,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Restore from the store."""
        return cls(
            since=datetime.fromisoformat(data["since"]),
            max_until=datetime.fromisoformat(data["max_until"]),
            unknown=data.get("unknown", False),
        )


@dataclass(slots=True)
class ActiveRule:
    """What the entity "Active rules" shows per rule."""

    rule_id: str
    name: str
    entity_id: str
    since: datetime
    until: datetime
    expired: bool
    unknown: bool


class RuleBook:
    """All delivery rules with their phases."""

    def __init__(self) -> None:
        """Create an empty rule book."""
        self.rules: dict[str, RuleConfig] = {}
        self.phases: dict[str, RulePhase] = {}
        self._notified_expired: set[str] = set()

    # ----- configuration -----------------------------------------------------

    def configure(self, rules: list[RuleConfig]) -> None:
        """Replace the rule configuration; phases of removed rules are dropped."""
        self.rules = {rule.rule_id: rule for rule in rules}
        for rule_id in list(self.phases):
            if rule_id not in self.rules:
                del self.phases[rule_id]
                self._notified_expired.discard(rule_id)

    # ----- observation -------------------------------------------------------

    def observe(self, rule_id: str, state: str | None, now: datetime) -> bool:
        """Feed the current state of a rule's entity.

        Returns True when waiting messages must be re-evaluated, that is when a
        phase ended or a rule became unknown or known again.
        """
        rule = self.rules.get(rule_id)
        if rule is None:
            return False
        unknown = state in UNKNOWN_STATES
        in_rule_state = state == rule.state
        phase = self.phases.get(rule_id)

        if unknown or in_rule_state:
            if phase is None:
                self.phases[rule_id] = RulePhase(
                    since=now,
                    max_until=now + timedelta(hours=rule.max_hours),
                    unknown=unknown,
                )
                return True
            changed = phase.unknown != unknown
            phase.unknown = unknown
            return changed

        if phase is not None:
            del self.phases[rule_id]
            self._notified_expired.discard(rule_id)
            return True
        return False

    # ----- evaluation --------------------------------------------------------

    def is_expired(self, rule_id: str, now: datetime) -> bool:
        """Return True when the rule's phase has passed its maximum duration."""
        phase = self.phases.get(rule_id)
        return phase is not None and now >= phase.max_until

    def verdict(self, priority: int, now: datetime) -> RuleVerdict | None:
        """Strictest effect of all active, not expired rules.

        Returns None when nothing holds the message. The reason names the
        deciding rule; among equally strict rules the one ending last decides.
        """
        deciding: tuple[RuleConfig, RulePhase, Effect] | None = None
        for rule_id, phase in self.phases.items():
            rule = self.rules.get(rule_id)
            if rule is None or now >= phase.max_until:
                continue
            effect = rule.effect_for(priority)
            if effect is Effect.PASS:
                continue
            if deciding is None:
                deciding = (rule, phase, effect)
                continue
            _, best_phase, best_effect = deciding
            if STRICTNESS[effect] > STRICTNESS[best_effect] or (
                effect is best_effect and phase.max_until > best_phase.max_until
            ):
                deciding = (rule, phase, effect)
        if deciding is None:
            return None
        rule, phase, effect = deciding
        kind = HoldKind.DISCARD if effect is Effect.DISCARD else HoldKind.HOLD
        reason = Reason(
            ReasonKind.RULE_UNKNOWN if phase.unknown else ReasonKind.RULE,
            until=phase.max_until,
            detail=rule.name,
            entity_id=rule.entity_id if phase.unknown else None,
        )
        return RuleVerdict(kind, reason)

    def active(self, now: datetime) -> list[ActiveRule]:
        """All rules currently in a phase, for the "Active rules" entity."""
        result: list[ActiveRule] = []
        for rule_id, phase in self.phases.items():
            rule = self.rules.get(rule_id)
            if rule is None:
                continue
            result.append(
                ActiveRule(
                    rule_id=rule_id,
                    name=rule.name,
                    entity_id=rule.entity_id,
                    since=phase.since,
                    until=phase.max_until,
                    expired=now >= phase.max_until,
                    unknown=phase.unknown,
                )
            )
        return result

    def next_expiry(self, now: datetime) -> datetime | None:
        """Earliest maximum end of a running, not yet expired phase."""
        ends = [p.max_until for p in self.phases.values() if p.max_until > now]
        return min(ends) if ends else None

    def newly_expired(self, now: datetime) -> list[RuleConfig]:
        """Rules whose phase crossed the maximum since the last call.

        Used to release held messages and raise the repair once.
        """
        result: list[RuleConfig] = []
        for rule_id, phase in self.phases.items():
            rule = self.rules.get(rule_id)
            if rule is None or now < phase.max_until:
                continue
            if rule_id not in self._notified_expired:
                self._notified_expired.add(rule_id)
                result.append(rule)
        return result

    def unknown_rules(self) -> list[RuleConfig]:
        """Rules whose entity cannot be read, for the repair."""
        return [
            self.rules[rule_id]
            for rule_id, phase in self.phases.items()
            if phase.unknown and rule_id in self.rules
        ]

    # ----- persistence -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise the phases (the configuration lives in the config entry)."""
        return {
            "phases": {
                rule_id: phase.to_dict() for rule_id, phase in self.phases.items()
            },
            "notified_expired": sorted(self._notified_expired),
        }

    def load(self, data: dict[str, Any]) -> None:
        """Restore phases; phases of rules that no longer exist are dropped."""
        self.phases = {
            rule_id: RulePhase.from_dict(raw)
            for rule_id, raw in data.get("phases", {}).items()
            if rule_id in self.rules
        }
        self._notified_expired = {
            rule_id
            for rule_id in data.get("notified_expired", [])
            if rule_id in self.phases
        }
