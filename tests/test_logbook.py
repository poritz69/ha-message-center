"""Tests for the logbook texts of the four events (never the message text)."""

from __future__ import annotations

from collections.abc import Callable
import json
from types import SimpleNamespace
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)

from custom_components.message_center.const import (
    DOMAIN,
    EVENT_DELIVERED,
    EVENT_DISCARDED,
    EVENT_FORWARDED,
    EVENT_SNOOZED,
)
from custom_components.message_center.logbook import async_describe_events

from .conftest import PHONE_ACTION
from .test_delivery import setup
from .test_services import TEXT, TITLE, message_id_of, notify

NOTE = "Bitte zusammenfassen"


async def test_logbook_describes_the_four_events_without_text(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """Delivered, forwarded, snoozed and discarded: origin and title, never the text."""
    describers: dict[str, Callable[[Any], dict[str, Any]]] = {}

    def collect(domain: str, event_type: str, describe: Callable[..., Any]) -> None:
        assert domain == DOMAIN
        describers[event_type] = describe

    async_describe_events(hass, collect)
    captured = {
        event_type: async_capture_events(hass, event_type)
        for event_type in (
            EVENT_DELIVERED,
            EVENT_FORWARDED,
            EVENT_SNOOZED,
            EVENT_DISCARDED,
        )
    }

    await notify(hass)
    await hass.services.async_call(
        DOMAIN,
        "forward",
        {"message_id": message_id_of(hass), "note": NOTE},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "snooze",
        {"message_id": message_id_of(hass), "minutes": 5},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, "discard", {"message_id": message_id_of(hass)}, blocking=True
    )
    await hass.async_block_till_done()

    texts: dict[str, str] = {}
    for event_type, events in captured.items():
        assert len(events) == 1, event_type
        entry = describers[event_type](SimpleNamespace(data=events[0].data))
        assert entry["name"] == "Message Center"
        texts[event_type] = entry["message"]

    assert (
        texts[EVENT_DELIVERED] == f"delivered '{TITLE}' from unknown to {PHONE_ACTION}"
    )
    assert texts[EVENT_FORWARDED] == (
        f"forwarded '{TITLE}' from unknown to the assistant (action)"
    )
    assert texts[EVENT_SNOOZED] == f"snoozed '{TITLE}' from unknown for 5 min (action)"
    assert texts[EVENT_DISCARDED] == f"discarded '{TITLE}' from unknown (action)"
    for text in texts.values():
        assert TEXT not in text
        assert NOTE not in text


def describers(hass: HomeAssistant) -> dict[str, Callable[[Any], dict[str, Any]]]:
    """Return the logbook describers by event type."""
    found: dict[str, Callable[[Any], dict[str, Any]]] = {}

    def collect(domain: str, event_type: str, describe: Callable[..., Any]) -> None:
        found[event_type] = describe

    async_describe_events(hass, collect)
    return found


async def test_logbook_hides_the_title_with_the_option(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """With "titles not in history and attributes" no logbook line shows the title.

    The forwarded event keeps the real title and text for whoever handles
    it; the logbook takes the title as the attributes show it instead.
    """
    describe = describers(hass)
    captured = {
        event_type: async_capture_events(hass, event_type)
        for event_type in (
            EVENT_DELIVERED,
            EVENT_FORWARDED,
            EVENT_SNOOZED,
            EVENT_DISCARDED,
        )
    }
    await setup(hass, make_entry, options={"hide_titles": True})
    await notify(hass)
    await hass.services.async_call(
        DOMAIN,
        "forward",
        {"message_id": message_id_of(hass), "note": NOTE},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "snooze",
        {"message_id": message_id_of(hass), "minutes": 5},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, "discard", {"message_id": message_id_of(hass)}, blocking=True
    )
    await hass.async_block_till_done()

    for event_type, events in captured.items():
        assert len(events) == 1, event_type
        text = describe[event_type](SimpleNamespace(data=events[0].data))["message"]
        assert TITLE not in text, event_type
        assert "'unknown/unknown' from unknown" in text, event_type
        if event_type != EVENT_FORWARDED:
            assert TITLE not in json.dumps(events[0].data, ensure_ascii=False)
    forwarded = captured[EVENT_FORWARDED][0].data
    assert forwarded["title"] == TITLE and forwarded["message"] == TEXT
    assert forwarded["display_title"] == "unknown/unknown"
