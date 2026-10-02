"""Tests for the push data per platform and for finding the phones."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import logging
from typing import Any

from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.message_center import delivery
from custom_components.message_center.delivery import (
    Recipient,
    async_push,
    async_push_tts,
    build_push_data,
    discover_mobile_apps,
)
from custom_components.message_center.models import Message

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
MID = "3c9f1e2d4b5a6978"  # an id as the book gives it: opaque, 16 hex characters
ANDROID = Recipient(action="mobile_app_phone", name="Phone", platform="android")
APPLE = Recipient(action="mobile_app_tablet", name="Tablet", platform="ios")


def message(priority: int = 1, **data: Any) -> Message:
    """Build a message as the intake would."""
    return Message(
        id=MID,
        origin="automation.laundry",
        key="Laundry",
        title="Laundry",
        message="Finished.",
        priority=priority,
        data=data,
        accepted_at=NOW,
        updated_at=NOW,
    )


def test_android_push_data() -> None:
    """Android: tag, group and channel are set; alarm channel for priority 3 only."""
    data = build_push_data(
        message(image="/local/x.jpg", channel="own"),
        ANDROID,
        group_name="Household",
        language="en",
    )
    assert data == {
        "image": "/local/x.jpg",
        "tag": MID,
        "group": "Household",
        "channel": "message_center",
    }

    alarm = build_push_data(
        message(3), ANDROID, group_name=None, language="en", alarm_channel="own_alarm"
    )
    assert alarm["group"] == "automation.laundry"
    assert alarm["channel"] == "own_alarm"
    assert (alarm["ttl"], alarm["priority"], alarm["importance"]) == (0, "high", "high")

    silent = build_push_data(
        message(), ANDROID, group_name=None, language="en", silent=True
    )
    assert silent["alert_once"] is True


def test_apple_push_data() -> None:
    """iOS: interruption level instead of a channel; critical with sound for alarms."""
    data = build_push_data(
        message(push={"badge": 1}), APPLE, group_name=None, language="en"
    )
    assert data["push"] == {"badge": 1, "interruption-level": "active"}
    assert "channel" not in data

    alarm = build_push_data(message(3), APPLE, group_name=None, language="en")
    assert alarm["push"]["interruption-level"] == "critical"
    assert alarm["push"]["sound"] == {"name": "default", "critical": 1, "volume": 1.0}
    assert "ttl" not in alarm


def test_own_buttons_stay_in_front() -> None:
    """The caller's buttons are kept and the center's are appended."""
    own = {"action": "LAUNDRY_DONE", "title": "Done"}
    later = {"action": "message_center_snooze|30|x", "title": "Later 30 min"}
    data = build_push_data(
        message(actions=[own, "not a button"]),
        ANDROID,
        group_name=None,
        language="en",
        actions=[later],
    )
    assert data["actions"] == [own, later]


def test_alarm_button_is_among_the_first_three() -> None:
    """The alarm button stands third at the latest: Android shows three.

    In front of it the caller's own buttons, then "later", then "to
    assistant"; what is behind it is dropped nowhere, an iPhone shows it all.
    So on Android "to assistant" loses its place first, then "later", and
    the third own button only from three own buttons on.
    """
    later = {"action": f"message_center_snooze|30|{MID}", "title": "Later 30 min"}
    later_2 = {"action": f"message_center_snooze|120|{MID}", "title": "Later 2 h"}
    forward = {"action": f"message_center_forward|{MID}", "title": "To assistant"}
    alarm_off = {"action": f"message_center_alarm_off|{MID}", "title": "End alarm"}
    own = [{"action": f"OWN_{n}", "title": f"Own {n}"} for n in range(3)]

    def buttons(
        own_count: int,
        center: list[dict[str, Any]] | None = None,
        recipient: Recipient = ANDROID,
        priority: int = 3,
    ) -> list[dict[str, Any]]:
        data = build_push_data(
            message(priority, actions=own[:own_count]),
            recipient,
            group_name=None,
            language="en",
            actions=center or [later, forward, alarm_off],
        )
        return data["actions"]

    assert buttons(0) == [later, forward, alarm_off]
    assert buttons(1) == [own[0], later, alarm_off, forward]
    assert buttons(2) == [own[0], own[1], alarm_off, later, forward]
    assert buttons(3) == [own[0], own[1], alarm_off, own[2], later, forward]
    # a second "later" duration takes the place of "to assistant"
    assert buttons(0, [later, later_2, forward, alarm_off]) == [
        later,
        later_2,
        alarm_off,
        forward,
    ]
    assert buttons(1, [later, later_2, forward, alarm_off]) == [
        own[0],
        later,
        alarm_off,
        later_2,
        forward,
    ]
    # the same list on an iPhone: it shows them all, in the same order
    assert buttons(2, recipient=APPLE) == buttons(2)
    # without an alarm button nothing moves
    assert buttons(2, [later, forward], priority=1) == [own[0], own[1], later, forward]


async def test_push_errors_become_error_classes(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A push never raises: the cycle gets None or the error's class, not its text."""
    assert (
        await async_push(
            hass, ANDROID, message(), Context(), group_name=None, language="en"
        )
        == "ServiceNotFound"
    )

    async def run(handler: Any) -> str | None:
        hass.services.async_register("notify", ANDROID.action, handler)
        return await async_push(
            hass, ANDROID, message(), Context(), group_name=None, language="en"
        )

    async def refuse(call: ServiceCall) -> None:
        raise HomeAssistantError("the text of the message must not show up")

    async def crash(call: ServiceCall) -> None:
        raise RuntimeError("unexpected")

    async def hang(call: ServiceCall) -> None:
        await asyncio.sleep(1)

    async def fine(call: ServiceCall) -> None:
        return None

    assert await run(refuse) == "HomeAssistantError"
    assert await run(crash) == "RuntimeError"
    monkeypatch.setattr(delivery, "PUSH_TIMEOUT", 0.01)
    assert await run(hang) == "Timeout"
    assert await run(fine) is None


async def test_data_a_push_cannot_be_built_from_becomes_an_error_class(
    hass: HomeAssistant,
) -> None:
    """Caller data that does not fit fails this push; it never raises either."""
    calls = async_mock_service(hass, "notify", ANDROID.action)
    later = [{"action": "later", "title": "Later"}]
    assert (
        await async_push(
            hass,
            ANDROID,
            message(actions=5),
            Context(),
            group_name=None,
            language="en",
            actions=later,
        )
        == "TypeError"
    )
    assert (
        await async_push(
            hass, APPLE, message(push="loud"), Context(), group_name=None, language="en"
        )
        == "ValueError"
    )
    assert calls == []


async def test_spoken_push_is_android_only(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The announcement goes to Android at alarm volume; iOS is skipped."""
    assert await async_push_tts(hass, APPLE, "Alarm: Water", Context()) is None

    calls = async_mock_service(hass, "notify", ANDROID.action)
    assert await async_push_tts(hass, ANDROID, "Alarm: Water", Context()) is None
    assert calls[0].data == {
        "message": "TTS",
        "data": {"tts_text": "Alarm: Water", "media_stream": "alarm_stream_max"},
    }

    async def refuse(call: ServiceCall) -> None:
        raise HomeAssistantError("no")

    async def hang(call: ServiceCall) -> None:
        await asyncio.sleep(1)

    hass.services.async_register("notify", ANDROID.action, refuse)
    assert await async_push_tts(hass, ANDROID, "x", Context()) == "HomeAssistantError"
    monkeypatch.setattr(delivery, "PUSH_TIMEOUT", 0.01)
    hass.services.async_register("notify", ANDROID.action, hang)
    assert await async_push_tts(hass, ANDROID, "x", Context()) == "Timeout"


async def test_discovery_offers_only_usable_phones(hass: HomeAssistant) -> None:
    """Found are Companion App devices that are enabled and have a notify action."""
    entry = MockConfigEntry(domain="mobile_app", data={})
    entry.add_to_hass(hass)
    registry = dr.async_get(hass)

    def device(name: str, manufacturer: str, domain: str = "mobile_app") -> str:
        return registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(domain, name)},
            name=name,
            manufacturer=manufacturer,
        ).id

    device("Tablet Kitchen", "Apple")
    device("Phone Alex", "Example")
    device("No Action", "Example")
    device("Foreign", "Example", domain="other")
    disabled = device("Old Phone", "Example")
    registry.async_update_device(disabled, disabled_by=dr.DeviceEntryDisabler.USER)
    for action in (
        "mobile_app_tablet_kitchen",
        "mobile_app_phone_alex",
        "mobile_app_foreign",
        "mobile_app_old_phone",
    ):
        async_mock_service(hass, "notify", action)

    found = discover_mobile_apps(hass)
    assert [(r.name, r.action, r.platform) for r in found] == [
        ("Phone Alex", "mobile_app_phone_alex", "android"),
        ("Tablet Kitchen", "mobile_app_tablet_kitchen", "ios"),
    ]


async def test_unexpected_push_error_logs_class_and_stack_without_content(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """An error no one expected: its class and where it happened, never its text.

    The text of a foreign exception may carry the message text; the stack
    shows the place without any value.
    """
    caplog.set_level(logging.INFO, logger="custom_components.message_center")

    async def broken(call: ServiceCall) -> None:
        raise ValueError(f"bad {call.data['message']} ({call.data['title']})")

    hass.services.async_register("notify", ANDROID.action, broken)
    assert (
        await async_push(
            hass, ANDROID, message(), Context(), group_name=None, language="en"
        )
        == "ValueError"
    )
    assert "Unexpected error pushing to mobile_app_phone: ValueError" in caplog.text
    assert 'File "' in caplog.text and "in async_push" in caplog.text
    assert "Finished." not in caplog.text
    assert "Laundry" not in caplog.text
