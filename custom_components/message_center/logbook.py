"""Logbook descriptions of the delivered event and the interventions.

Delivered, discarded, snoozed and forwarded appear in the logbook with origin
and title, never with the message text. The title is the one the
attributes show: with "titles not in history and attributes" it is origin
and kind instead.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
    LazyEventPartialState,
)
from homeassistant.core import HomeAssistant, callback

from .const import (
    DOMAIN,
    EVENT_DELIVERED,
    EVENT_DISCARDED,
    EVENT_FORWARDED,
    EVENT_SNOOZED,
)


def _who(data: dict[str, Any]) -> str:
    return str(data.get("origin_name") or data.get("origin") or "?")


def _source(data: dict[str, Any]) -> str:
    source = data.get("source")
    return f" ({source})" if source else ""


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[
        [str, str, Callable[[LazyEventPartialState], dict[str, Any]]], None
    ],
) -> None:
    """Describe the delivered event and the interventions."""

    @callback
    def describe_delivered(event: LazyEventPartialState) -> dict[str, Any]:
        data = event.data
        recipients = ", ".join(data.get("recipients", []))
        return {
            LOGBOOK_ENTRY_NAME: "Message Center",
            LOGBOOK_ENTRY_MESSAGE: (
                f"delivered '{data.get('title', '')}' from {_who(data)} to {recipients}"
            ),
        }

    @callback
    def describe_discarded(event: LazyEventPartialState) -> dict[str, Any]:
        data = event.data
        return {
            LOGBOOK_ENTRY_NAME: "Message Center",
            LOGBOOK_ENTRY_MESSAGE: (
                f"discarded '{data.get('title', '')}' from {_who(data)}{_source(data)}"
            ),
        }

    @callback
    def describe_snoozed(event: LazyEventPartialState) -> dict[str, Any]:
        data = event.data
        return {
            LOGBOOK_ENTRY_NAME: "Message Center",
            LOGBOOK_ENTRY_MESSAGE: (
                f"snoozed '{data.get('title', '')}' from {_who(data)} "
                f"for {data.get('minutes', '?')} min{_source(data)}"
            ),
        }

    @callback
    def describe_forwarded(event: LazyEventPartialState) -> dict[str, Any]:
        # the event carries the real title for the assistant; the logbook
        # takes the title as the attributes show it
        data = event.data
        title = data.get("display_title", data.get("title", ""))
        return {
            LOGBOOK_ENTRY_NAME: "Message Center",
            LOGBOOK_ENTRY_MESSAGE: (
                f"forwarded '{title}' from {_who(data)} to the assistant{_source(data)}"
            ),
        }

    async_describe_event(DOMAIN, EVENT_DELIVERED, describe_delivered)
    async_describe_event(DOMAIN, EVENT_DISCARDED, describe_discarded)
    async_describe_event(DOMAIN, EVENT_SNOOZED, describe_snoozed)
    async_describe_event(DOMAIN, EVENT_FORWARDED, describe_forwarded)
