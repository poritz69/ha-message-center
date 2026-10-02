"""Plain-text reasons for entity attributes.

Attributes are data, not translated by Home Assistant, so the text follows the
system language: German or English.
"""

from __future__ import annotations

from datetime import datetime

from .models import Reason, ReasonKind

_DE: dict[ReasonKind, str] = {
    ReasonKind.EVALUATING: "wird bewertet",
    ReasonKind.SENDING: "wird gesendet",
    ReasonKind.RULE: "zurückgehalten: {detail} bis {until}",
    ReasonKind.RULE_UNKNOWN: (
        "Modus unbekannt: {entity_id} nicht verfügbar ({detail}, bis {until})"
    ),
    ReasonKind.SPACING: "Mindestabstand bis {until}",
    ReasonKind.SNOOZED: "zurückgestellt bis {until}",
    ReasonKind.RETRY: "Zustellfehler, nächster Versuch {until}",
    ReasonKind.RESTART: "Neustart während der Zustellung, Stand unklar",
    ReasonKind.GAP: "Lücke von {detail} h, Stand nicht verlässlich",
    ReasonKind.DISCARDED: "verworfen",
    ReasonKind.EXPIRED: "verfallen",
    ReasonKind.RULE_DISCARDED: "verworfen durch Regel",
    ReasonKind.MAX_WAIT: "Höchstwartezeit überschritten",
    ReasonKind.DELIVERED: "zugestellt",
    ReasonKind.NO_RECIPIENT: "kein Empfänger erreicht",
}

_EN: dict[ReasonKind, str] = {
    ReasonKind.EVALUATING: "being evaluated",
    ReasonKind.SENDING: "sending",
    ReasonKind.RULE: "held back: {detail} until {until}",
    ReasonKind.RULE_UNKNOWN: (
        "mode unknown: {entity_id} unavailable ({detail}, until {until})"
    ),
    ReasonKind.SPACING: "minimum spacing until {until}",
    ReasonKind.SNOOZED: "snoozed until {until}",
    ReasonKind.RETRY: "delivery failed, next attempt {until}",
    ReasonKind.RESTART: "restart during delivery, state unclear",
    ReasonKind.GAP: "gap of {detail} h, state not reliable",
    ReasonKind.DISCARDED: "discarded",
    ReasonKind.EXPIRED: "expired",
    ReasonKind.RULE_DISCARDED: "discarded by rule",
    ReasonKind.MAX_WAIT: "maximum wait exceeded",
    ReasonKind.DELIVERED: "delivered",
    ReasonKind.NO_RECIPIENT: "no recipient reached",
}


def _fmt(value: datetime | None, language: str) -> str:
    if value is None:
        return "?"
    local = value.astimezone()
    return (
        local.strftime("%d.%m. %H:%M")
        if language == "de"
        else local.strftime("%b %d %H:%M")
    )


def reason_text(reason: Reason, language: str) -> str:
    """Render a reason as plain text in the given language."""
    table = _DE if language.startswith("de") else _EN
    template = table.get(reason.kind, reason.kind.value)
    return template.format(
        detail=reason.detail or "?",
        entity_id=reason.entity_id or "?",
        until=_fmt(reason.until, "de" if language.startswith("de") else "en"),
    )


_BUTTONS_DE = {
    "snooze": "Später",
    "forward": "An KI",
    "alarm_off": "Alarm beenden",
    "snooze_hint": "Minuten, leer = {minutes}",
    "forward_hint": "Notiz für die KI (optional)",
    "ok": "OK",
}

_BUTTONS_EN = {
    "snooze": "Later",
    "forward": "To assistant",
    "alarm_off": "End alarm",
    "snooze_hint": "minutes, empty = {minutes}",
    "forward_hint": "note for the assistant (optional)",
    "ok": "OK",
}


def button_texts(language: str, minutes: int) -> dict[str, str]:
    """Titles and hints of the push buttons."""
    table = _BUTTONS_DE if language.startswith("de") else _BUTTONS_EN
    return {key: text.format(minutes=minutes) for key, text in table.items()}


def duration_text(minutes: int, language: str) -> str:
    """Short duration for a button title: "30 min", "2 h", "1 Tag" / "1 day"."""
    de = language.startswith("de")
    if minutes % 1440 == 0:
        days = minutes // 1440
        return f"{days} " + (
            ("Tag" if days == 1 else "Tage") if de else ("day" if days == 1 else "days")
        )
    if minutes % 60 == 0:
        return f"{minutes // 60} h"
    return f"{minutes} min"


def failing_text(language: str, count: int) -> str:
    """Text of the notification shown while deliveries fail."""
    if language.startswith("de"):
        what = "1 Meldung konnte" if count == 1 else f"{count} Meldungen konnten"
        return (
            f"{what} noch nicht zugestellt werden. Message Center versucht es weiter."
        )
    what = "1 message" if count == 1 else f"{count} messages"
    return f"{what} could not be delivered yet. Message Center keeps retrying."


_TEST_DE = {
    1: (
        "Test Stufe 1 · Hinweis",
        "Testmeldung des Message Center, Stufe 1. Nur Push. "
        "Erscheint nicht im Verlauf.",
    ),
    2: (
        "Test Stufe 2 · Wichtig",
        "Testmeldung des Message Center, Stufe 2. Push und Lichtimpuls an den "
        "gewählten Lampen. Erscheint nicht im Verlauf.",
    ),
    3: (
        "Test Stufe 3 · Alarm",
        "Testmeldung des Message Center, Stufe 3. Alarm-Push, umgeht "
        "„Nicht stören“. Erscheint nicht im Verlauf.",
    ),
}

_TEST_EN = {
    1: (
        "Test priority 1 · Notice",
        "Test message of the Message Center, priority 1. Push only. "
        "Not kept in the history.",
    ),
    2: (
        "Test priority 2 · Important",
        "Test message of the Message Center, priority 2. Push and light pulse "
        "on the chosen lamps. Not kept in the history.",
    ),
    3: (
        "Test priority 3 · Alarm",
        "Test message of the Message Center, priority 3. Alarm push, bypasses "
        "do not disturb. Not kept in the history.",
    ),
}


def test_texts(language: str, priority: int) -> tuple[str, str]:
    """Title and text of the test message for a priority (settings tab)."""
    table = _TEST_DE if language.startswith("de") else _TEST_EN
    return table[priority]
