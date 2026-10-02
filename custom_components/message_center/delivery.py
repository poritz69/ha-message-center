"""Delivery to the Companion App via ``notify.mobile_app_*``.

Builds the push data per platform, passes the caller's extra data through
unchanged, sends and silently replaces notifications, and turns failures
into an error class without message content. Nothing is ever deleted
from a phone.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import traceback
from typing import Any

from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
from homeassistant.helpers import device_registry as dr
from homeassistant.util import slugify

from .const import (
    ACTION_ALARM_OFF,
    DEFAULT_ALARM_CHANNEL,
    PLATFORM_ANDROID,
    PLATFORM_IOS,
    PUSH_CHANNEL,
    PUSH_TIMEOUT,
    RECIPIENT_ACTION,
    RECIPIENT_NAME,
    RECIPIENT_PLATFORM,
    RECIPIENT_TYPE,
    RECIPIENT_TYPE_MOBILE_APP,
)
from .models import Message

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class Recipient:
    """A configured recipient (typed for later channels)."""

    action: str
    name: str
    platform: str
    type: str = RECIPIENT_TYPE_MOBILE_APP

    @property
    def is_apple(self) -> bool:
        """True for iPhones and iPads."""
        return self.platform == PLATFORM_IOS

    def to_dict(self) -> dict[str, str]:
        """Serialise for the config entry."""
        return {
            RECIPIENT_ACTION: self.action,
            RECIPIENT_NAME: self.name,
            RECIPIENT_PLATFORM: self.platform,
            RECIPIENT_TYPE: self.type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Recipient:
        """Restore from the config entry."""
        return cls(
            action=data[RECIPIENT_ACTION],
            name=data.get(RECIPIENT_NAME, data[RECIPIENT_ACTION]),
            platform=data.get(RECIPIENT_PLATFORM, PLATFORM_ANDROID),
            type=data.get(RECIPIENT_TYPE, RECIPIENT_TYPE_MOBILE_APP),
        )


def discover_mobile_apps(hass: HomeAssistant) -> list[Recipient]:
    """Find Companion App devices in the device registry."""
    registry = dr.async_get(hass)
    found: list[Recipient] = []
    devices = [
        device
        for entry in hass.config_entries.async_entries("mobile_app")
        for device in dr.async_entries_for_config_entry(registry, entry.entry_id)
    ]
    for device in devices:
        if device.disabled:
            continue
        if not any(ident[0] == "mobile_app" for ident in device.identifiers):
            continue
        name = device.name_by_user or device.name or ""
        action = f"mobile_app_{slugify(name)}"
        if not hass.services.has_service("notify", action):
            continue
        platform = (
            PLATFORM_IOS
            if (device.manufacturer or "").lower() == "apple"
            else PLATFORM_ANDROID
        )
        found.append(Recipient(action=action, name=name, platform=platform))
    return sorted(found, key=lambda r: r.name.lower())


def error_trace(err: BaseException) -> str:
    """Class and call stack of an exception for the log, without its text.

    The text of a foreign exception may carry the message; the stack shows
    the place without any value.
    """
    stack = "".join(traceback.format_tb(err.__traceback__))
    return f"{type(err).__name__}\n{stack}".rstrip()


def build_push_data(
    msg: Message,
    recipient: Recipient,
    *,
    group_name: str | None,
    language: str,
    silent: bool = False,
    actions: list[dict[str, Any]] | None = None,
    alarm_channel: str = DEFAULT_ALARM_CHANNEL,
) -> dict[str, Any]:
    """Push data: caller's data passed through, ours layered on top.

    Buttons: the caller's own first, then the center's. "End alarm"
    stands third at the latest, because Android shows three buttons at
    most; what is behind it stays in the list for the iPhone.
    """
    data: dict[str, Any] = dict(msg.data)
    data["tag"] = msg.id
    data["group"] = group_name or msg.origin
    alarm = msg.priority >= 3
    if recipient.is_apple:
        push: dict[str, Any] = dict(data.get("push", {}))
        push["interruption-level"] = "critical" if alarm else "active"
        if alarm:
            push["sound"] = {"name": "default", "critical": 1, "volume": 1.0}
        data["push"] = push
    else:
        data["channel"] = alarm_channel if alarm else PUSH_CHANNEL
        if alarm:
            data["ttl"] = 0
            data["priority"] = "high"
            data["importance"] = "high"
        if silent:
            data["alert_once"] = True
    if actions:
        own = [a for a in data.get("actions", []) if isinstance(a, dict)]
        buttons = own + actions
        for index, button in enumerate(buttons):
            action = button.get("action")
            if isinstance(action, str) and action.startswith(ACTION_ALARM_OFF):
                if index > 2:
                    buttons.insert(2, buttons.pop(index))
                break
        data["actions"] = buttons
    return data


async def async_push(
    hass: HomeAssistant,
    recipient: Recipient,
    msg: Message,
    context: Context,
    *,
    group_name: str | None,
    language: str,
    silent: bool = False,
    actions: list[dict[str, Any]] | None = None,
    alarm_channel: str = DEFAULT_ALARM_CHANNEL,
) -> str | None:
    """Send the message to one recipient; return None or an error class.

    Building the push counts as part of it: data of the caller that does not
    fit (``actions`` that is no list) is an error of this push, not a crash.
    """
    try:
        payload = {
            # a repeat replaces the push (same tag), the counter is in the title
            "title": f"{msg.count}x {msg.title}" if msg.count > 1 else msg.title,
            "message": msg.message,
            "data": build_push_data(
                msg,
                recipient,
                group_name=group_name,
                language=language,
                silent=silent,
                actions=actions,
                alarm_channel=alarm_channel,
            ),
        }
        async with asyncio.timeout(PUSH_TIMEOUT):
            await hass.services.async_call(
                "notify", recipient.action, payload, blocking=True, context=context
            )
    except ServiceNotFound:
        return "ServiceNotFound"
    except TimeoutError:
        return "Timeout"
    except HomeAssistantError as err:
        return type(err).__name__
    except Exception as err:  # never let a push crash the cycle
        _LOGGER.error(
            "Unexpected error pushing to %s: %s", recipient.action, error_trace(err)
        )
        return type(err).__name__
    return None


async def async_push_tts(
    hass: HomeAssistant, recipient: Recipient, text: str, context: Context
) -> str | None:
    """Read a text aloud on an Android phone at full alarm volume (app TTS)."""
    if recipient.is_apple:
        return None
    payload = {
        "message": "TTS",
        "data": {"tts_text": text, "media_stream": "alarm_stream_max"},
    }
    try:
        async with asyncio.timeout(PUSH_TIMEOUT):
            await hass.services.async_call(
                "notify", recipient.action, payload, blocking=True, context=context
            )
    except HomeAssistantError as err:
        return type(err).__name__
    except TimeoutError:
        return "Timeout"
    return None
