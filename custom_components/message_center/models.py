"""Data model of the message center: messages, recipients, reasons, origin.

Everything here is plain Python without Home Assistant imports so that the
state machine in lifecycle.py can be tested on its own. Timestamps are
timezone-aware datetimes in UTC and are serialised as ISO strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
import hashlib
from typing import Any, Self

UNKNOWN_ORIGIN = "unknown"


MAX_EVENTS = 20


class MessageState(StrEnum):
    """States of a message."""

    WAITING = "waiting"
    SENDING = "sending"
    RETRYING = "retrying"
    DELIVERED = "delivered"
    UNCLEAR = "unclear"
    DISCARDED = "discarded"
    FAILED = "failed"


END_STATES: frozenset[MessageState] = frozenset(
    {MessageState.DELIVERED, MessageState.DISCARDED, MessageState.FAILED}
)
OPEN_STATES: frozenset[MessageState] = frozenset(
    {
        MessageState.WAITING,
        MessageState.SENDING,
        MessageState.RETRYING,
        MessageState.UNCLEAR,
    }
)
DISTURBED_STATES: frozenset[MessageState] = frozenset(
    {MessageState.RETRYING, MessageState.UNCLEAR, MessageState.FAILED}
)


class RecipientState(StrEnum):
    """Delivery state of one recipient within a push cycle."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


class ReasonKind(StrEnum):
    """Why a message is in its state. Rendered to text by the entity layer."""

    EVALUATING = "evaluating"
    SENDING = "sending"
    RULE = "rule"
    RULE_UNKNOWN = "rule_unknown"
    SPACING = "spacing"
    SNOOZED = "snoozed"
    RETRY = "retry"
    RESTART = "restart"
    GAP = "gap"
    DISCARDED = "discarded"
    EXPIRED = "expired"
    RULE_DISCARDED = "rule_discarded"
    MAX_WAIT = "max_wait"
    DELIVERED = "delivered"
    NO_RECIPIENT = "no_recipient"


def _dt_to_str(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _dt_from_str(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@dataclass(slots=True)
class Reason:
    """A structured reason with an optional end time and detail (rule name, hours)."""

    kind: ReasonKind
    until: datetime | None = None
    detail: str | None = None
    entity_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise for the store."""
        return {
            "kind": self.kind,
            "until": _dt_to_str(self.until),
            "detail": self.detail,
            "entity_id": self.entity_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Restore from the store."""
        return cls(
            kind=ReasonKind(data["kind"]),
            until=_dt_from_str(data.get("until")),
            detail=data.get("detail"),
            entity_id=data.get("entity_id"),
        )


@dataclass(slots=True)
class RecipientStatus:
    """What happened to one recipient in the current push cycle."""

    state: RecipientState = RecipientState.PENDING
    attempts: int = 0
    first_failed_at: datetime | None = None
    last_error: str | None = None
    next_try: datetime | None = None
    delivered_at: datetime | None = None
    delivered_revision: int | None = None
    delivered_count: int | None = None
    # A push to this recipient is running. Kept in memory only: it is not
    # saved, so after a restart no recipient is left reserved.
    in_flight: bool = field(default=False, compare=False)

    @property
    def is_final(self) -> bool:
        """True when the recipient reached delivered or failed."""
        return self.state is not RecipientState.PENDING

    def to_dict(self) -> dict[str, Any]:
        """Serialise for the store."""
        return {
            "state": self.state,
            "attempts": self.attempts,
            "first_failed_at": _dt_to_str(self.first_failed_at),
            "last_error": self.last_error,
            "next_try": _dt_to_str(self.next_try),
            "delivered_at": _dt_to_str(self.delivered_at),
            "delivered_revision": self.delivered_revision,
            "delivered_count": self.delivered_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Restore from the store."""
        return cls(
            state=RecipientState(data["state"]),
            attempts=data.get("attempts", 0),
            first_failed_at=_dt_from_str(data.get("first_failed_at")),
            last_error=data.get("last_error"),
            next_try=_dt_from_str(data.get("next_try")),
            delivered_at=_dt_from_str(data.get("delivered_at")),
            delivered_revision=data.get("delivered_revision"),
            delivered_count=data.get("delivered_count"),
        )


@dataclass(slots=True)
class Message:
    """One message, unique per origin and key.

    The key is the title unless ``send`` gave an explicit one. The id is the
    book's salted hash of origin and key, see ``message_id``; it is given
    when the message is made and stored with it. Kind, group, priority,
    spacing, expiry and no_hold are copied from the matched message kind at
    intake so that later edits of the kind do not change a message that is
    already on its way.
    """

    id: str
    origin: str
    key: str
    title: str
    message: str
    priority: int
    accepted_at: datetime
    updated_at: datetime
    origin_name: str | None = None
    labels: list[str] = field(default_factory=list)
    kind_id: str | None = None
    group_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    state: MessageState = MessageState.WAITING
    reason: Reason = field(default_factory=lambda: Reason(ReasonKind.EVALUATING))
    generation: int = 1
    revision: int = 1
    count: int = 1
    spacing: int = 0
    no_hold: bool = False
    expires_at: datetime | None = None
    snoozed_until: datetime | None = None
    delivered_at: datetime | None = None
    ended_at: datetime | None = None
    forwarded_at: datetime | None = None
    cycle_started_at: datetime | None = None
    light_done: bool = False
    context_id: str | None = None
    user_id: str | None = None
    # sent by an effect of the center itself (script, light): delivered, but
    # starts no effect of its own
    from_effect: bool = False
    recipients: dict[str, RecipientStatus] = field(default_factory=dict)
    # Interventions and effects, newest last: snoozed, forwarded, discarded,
    # sent_now, light, light_skipped, light_failed, alarm_light, script,
    # script_failed, script_skipped; with source phone / page / action / center
    # (page history).
    events: list[dict[str, Any]] = field(default_factory=list)

    def add_event(
        self, kind: str, source: str, detail: str | None, now: datetime
    ) -> None:
        """Remember an intervention for the page's history (at most 20)."""
        self.events.append(
            {"at": now.isoformat(), "kind": kind, "source": source, "detail": detail}
        )
        del self.events[:-MAX_EVENTS]

    @property
    def is_open(self) -> bool:
        """True for every state that counts as open (not yet through)."""
        return self.state in OPEN_STATES

    @property
    def failed_recipients(self) -> list[str]:
        """Recipients that reached the failed state in the current cycle."""
        return [
            name
            for name, status in self.recipients.items()
            if status.state is RecipientState.FAILED
        ]

    @property
    def delivered_recipients(self) -> list[str]:
        """Recipients that were delivered in the current cycle."""
        return [
            name
            for name, status in self.recipients.items()
            if status.state is RecipientState.DELIVERED
        ]

    @property
    def next_try(self) -> datetime | None:
        """Earliest scheduled retry over all recipients, if any.

        A recipient whose push is running does not count: its next retry is
        only known once the result is in.
        """
        tries = [
            s.next_try
            for s in self.recipients.values()
            if s.next_try is not None and not s.in_flight
        ]
        return min(tries) if tries else None

    def to_dict(self) -> dict[str, Any]:
        """Serialise for the store."""
        return {
            "id": self.id,
            "origin": self.origin,
            "origin_name": self.origin_name,
            "labels": list(self.labels),
            "key": self.key,
            "kind_id": self.kind_id,
            "group_id": self.group_id,
            "title": self.title,
            "message": self.message,
            "data": dict(self.data),
            "priority": self.priority,
            "state": self.state,
            "reason": self.reason.to_dict(),
            "generation": self.generation,
            "revision": self.revision,
            "count": self.count,
            "spacing": self.spacing,
            "no_hold": self.no_hold,
            "accepted_at": _dt_to_str(self.accepted_at),
            "updated_at": _dt_to_str(self.updated_at),
            "expires_at": _dt_to_str(self.expires_at),
            "snoozed_until": _dt_to_str(self.snoozed_until),
            "delivered_at": _dt_to_str(self.delivered_at),
            "ended_at": _dt_to_str(self.ended_at),
            "forwarded_at": _dt_to_str(self.forwarded_at),
            "cycle_started_at": _dt_to_str(self.cycle_started_at),
            "light_done": self.light_done,
            "context_id": self.context_id,
            "user_id": self.user_id,
            "from_effect": self.from_effect,
            "recipients": {k: v.to_dict() for k, v in self.recipients.items()},
            "events": list(self.events),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Restore from the store.

        A history entry written before the id came has none; the id is then
        empty, and the owner fills it in where it is needed.
        """
        accepted_at = _dt_from_str(data["accepted_at"])
        updated_at = _dt_from_str(data.get("updated_at")) or accepted_at
        if accepted_at is None or updated_at is None:
            raise ValueError("message without accepted_at")
        return cls(
            id=str(data.get("id", "")),
            origin=data["origin"],
            origin_name=data.get("origin_name"),
            labels=list(data.get("labels", [])),
            key=data["key"],
            kind_id=data.get("kind_id"),
            group_id=data.get("group_id"),
            title=data["title"],
            message=data["message"],
            data=dict(data.get("data", {})),
            priority=data["priority"],
            state=MessageState(data["state"]),
            reason=Reason.from_dict(data["reason"]),
            generation=data.get("generation", 1),
            revision=data.get("revision", 1),
            count=data.get("count", 1),
            spacing=data.get("spacing", 0),
            no_hold=data.get("no_hold", False),
            accepted_at=accepted_at,
            updated_at=updated_at,
            expires_at=_dt_from_str(data.get("expires_at")),
            snoozed_until=_dt_from_str(data.get("snoozed_until")),
            delivered_at=_dt_from_str(data.get("delivered_at")),
            ended_at=_dt_from_str(data.get("ended_at")),
            forwarded_at=_dt_from_str(data.get("forwarded_at")),
            cycle_started_at=_dt_from_str(data.get("cycle_started_at")),
            light_done=data.get("light_done", False),
            context_id=data.get("context_id"),
            user_id=data.get("user_id"),
            from_effect=data.get("from_effect", False),
            recipients={
                k: RecipientStatus.from_dict(v)
                for k, v in data.get("recipients", {}).items()
            },
            events=list(data.get("events", [])),
        )


def message_id(salt: str, origin: str, key: str) -> str:
    """Build the id of a message: 16 hex characters of a salted SHA-256.

    Stable for the same origin and key as long as the salt stays, so a
    repeat finds its message and replaces its push; opaque, because without
    the salt no guessed title can be checked against it. Each
    part goes in with its length, so no pair of origin and key runs into
    another. Neither ':' nor '|' can occur, which the push buttons rely on.
    """
    digest = hashlib.sha256()
    for part in (salt, origin, key):
        raw = part.encode()
        digest.update(len(raw).to_bytes(4) + raw)
    return digest.hexdigest()[:16]
