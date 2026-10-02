"""Tests for the light pulse and the push buttons."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Context, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError, Unauthorized, UnknownUser
from homeassistant.helpers import storage
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_mock_service,
)

from custom_components.message_center.center import MessageCenter
from custom_components.message_center.const import (
    DOMAIN,
    EVENT_DELIVERED,
    EVENT_SNOOZED,
)
from custom_components.message_center.store import HISTORY_KEY

from .conftest import PHONE_ACTION, PHONE_NAME, kind_data
from .test_delivery import failing_phone, no_push_timeout, settle, setup, tick
from .test_services import TEXT, TITLE, message_id_of, notify, open_items

LAMPS = ["light.flur", "light.kueche"]


@pytest.fixture(autouse=True)
def no_pulse_delays(monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not wait for real seconds between blink and re-assert or switch off/on."""
    monkeypatch.setattr("custom_components.message_center.center.DEFAULT_PULSE_MS", 0)


async def lamps(hass: HomeAssistant, on: list[str]) -> list[ServiceCall]:
    """Create lamp states and capture light.turn_off / turn_on calls (in order)."""
    for entity_id in LAMPS:
        hass.states.async_set(entity_id, "on" if entity_id in on else "off")
    calls: list[ServiceCall] = []

    async def record(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("light", "turn_off", record)
    hass.services.async_register("light", "turn_on", record)
    return calls


async def test_level_2_blinks_lamps_that_are_on(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Level 2: one pulse per cycle on lamps that are on; silent replace: no pulse."""
    blink = await lamps(hass, on=["light.flur"])
    await setup(
        hass,
        make_entry,
        kinds=[kind_data(priority=2, spacing=60)],
        options={"lights": LAMPS},
    )
    await notify(hass)
    await hass.async_block_till_done()
    assert len(phone) == 1
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    light_events = [
        e
        for e in entry.runtime_data.book.messages[message_id_of(hass)].events
        if e["kind"] == "light"
    ]
    assert [e["detail"] for e in light_events] == ["light.flur"]
    # off, then on again; only the lamp that was on
    assert [(c.service, c.data) for c in blink] == [
        ("turn_off", {"entity_id": ["light.flur"]}),
        ("turn_on", {"entity_id": ["light.flur"]}),
    ]

    await notify(
        hass
    )  # within the kind's spacing: silent replace, same cycle, no pulse
    await hass.async_block_till_done()
    assert len(blink) == 2


async def test_level_1_no_pulse_unless_kind_says_always(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Level 1 does not blink; a kind with light=always does; light=never never."""
    blink = await lamps(hass, on=LAMPS)
    await setup(
        hass,
        make_entry,
        kinds=[
            kind_data(name="Immer", title_value="Immer", light=True),
            kind_data(name="Nie", title_value="Nie", priority=2, light=False),
            kind_data(),
        ],
        options={"lights": LAMPS},
    )
    await notify(hass)
    assert len(phone) == 1
    assert blink == []
    await notify(hass, title="Nie")
    assert len(phone) == 2
    assert blink == []
    await notify(hass, title="Immer")
    await hass.async_block_till_done()
    assert len(phone) == 3
    assert len(blink) == 2  # off and on
    assert blink[0].data["entity_id"] == LAMPS


async def test_pulse_spacing_switch_and_no_lamps(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Spacing 60 s: one pulse a minute; the switch turns it off; no lamp, no pulse."""
    blink = await lamps(hass, on=LAMPS)
    await setup(
        hass,
        make_entry,
        kinds=[kind_data(priority=2)],
        options={"lights": LAMPS, "light_spacing": 60},
    )
    pulses = lambda: [c for c in blink if c.service == "turn_off"]  # noqa: E731
    await notify(hass, title="Feuchte 1")
    await notify(hass, title="Feuchte 2")
    await hass.async_block_till_done()
    assert len(pulses()) == 1  # second message within 60 s: no pulse
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    second = entry.runtime_data.book.messages[message_id_of(hass, "Feuchte 2")]
    assert second.events[-1]["kind"] == "light_skipped"
    assert second.events[-1]["detail"] == "spacing"
    await tick(hass, freezer, seconds=61)
    await notify(hass, title="Feuchte 3")
    await hass.async_block_till_done()
    assert len(pulses()) == 2

    switch = hass.states.get("switch.message_center_light_pulse")
    assert switch is not None and switch.state == "on"
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.message_center_light_pulse"},
        blocking=True,
    )
    await tick(hass, freezer, seconds=61)
    await notify(hass, title="Feuchte 4")
    await hass.async_block_till_done()
    assert len(pulses()) == 2
    assert hass.states.get("switch.message_center_light_pulse").state == "off"

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.message_center_light_pulse"},
        blocking=True,
    )
    for entity_id in LAMPS:
        hass.states.async_set(entity_id, "off")
    await tick(hass, freezer, seconds=61)
    await notify(hass, title="Feuchte 5")
    await hass.async_block_till_done()
    assert len(phone) == 5
    assert len(pulses()) == 2  # all lamps off: nothing to blink
    fifth = entry.runtime_data.book.messages[message_id_of(hass, "Feuchte 5")]
    assert fifth.events[-1]["detail"] == "nothing_on"


async def test_light_error_does_not_touch_the_push(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """A failing lamp is logged; the message is still delivered."""
    for entity_id in LAMPS:
        hass.states.async_set(entity_id, "on")

    async def broken(call: ServiceCall) -> None:
        raise RuntimeError("lamp gone")

    hass.services.async_register("light", "turn_off", broken)
    hass.services.async_register("light", "turn_on", broken)
    await setup(
        hass, make_entry, kinds=[kind_data(priority=2)], options={"lights": LAMPS}
    )
    await notify(hass)
    await hass.async_block_till_done()
    assert len(phone) == 1
    assert hass.states.get("sensor.message_center_open").state == "0"


async def test_push_buttons_snooze_and_forward(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """The buttons on the push snooze with the typed minutes and forward with a note."""
    await notify(hass)
    actions = phone[0].data["data"]["actions"]
    assert [a["title"] for a in actions] == ["Later 30 min", "To assistant"]
    assert actions[0]["action"] == f"message_center_snooze|30|{message_id_of(hass)}"
    assert "behavior" not in actions[0]  # one tap, fixed duration

    alex = await hass.auth.async_create_user("Alex", group_ids=["system-users"])
    user = Context(user_id=alex.id)
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": actions[0]["action"]},
        context=user,
    )
    await hass.async_block_till_done()
    items = open_items(hass)
    assert items[0]["state"] == "waiting"
    assert items[0]["reason"].startswith("snoozed until")
    center = center_entry.runtime_data
    events = center.book.messages[message_id_of(hass)].events
    assert [(e["kind"], e["source"], e["detail"]) for e in events] == [
        ("snoozed", "phone", "30 min")
    ]

    forwarded = async_capture_events(hass, f"{DOMAIN}_forwarded")
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": actions[1]["action"], "reply_text": "please check"},
        context=user,
    )
    await hass.async_block_till_done()
    assert len(forwarded) == 1
    assert forwarded[0].data["note"] == "please check"
    assert forwarded[0].data["title"] == TITLE
    assert forwarded[0].context.user_id == alex.id
    assert events[-1] == {
        "at": events[-1]["at"],
        "kind": "forwarded",
        "source": "phone",
        "detail": "please check",
    }

    # unknown ids and foreign actions are ignored
    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": "message_center_snooze|30|nope"}
    )
    hass.bus.async_fire("mobile_app_notification_action", {"action": "OTHER"})
    await hass.async_block_till_done()
    assert len(forwarded) == 1


async def test_push_buttons_can_be_turned_off_separately(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Each button has its own option; with both off there are no buttons of ours."""
    await setup(hass, make_entry, options={"button_snooze": False})
    await notify(hass)
    assert [a["title"] for a in phone[0].data["data"]["actions"]] == ["To assistant"]

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    hass.config_entries.async_update_entry(
        entry, options={"button_snooze": False, "button_forward": False}
    )
    await hass.async_block_till_done()
    await notify(hass, title="Zwei")
    assert "actions" not in phone[1].data["data"]


async def test_switches_pulse_off_and_on(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Switches and lights are both pulsed off and on; only those that are on."""
    hass.states.async_set("light.flur", "on")
    hass.states.async_set("switch.stehlampe", "on")
    hass.states.async_set("switch.aus", "off")
    await setup(
        hass,
        make_entry,
        kinds=[kind_data(priority=2)],
        options={"lights": ["light.flur", "switch.stehlampe", "switch.aus"]},
    )
    # after setup: the integration's own switch platform registered the real
    # switch services, the mocks must replace them
    light_off = async_mock_service(hass, "light", "turn_off")
    light_on = async_mock_service(hass, "light", "turn_on")
    off = async_mock_service(hass, "switch", "turn_off")
    on = async_mock_service(hass, "switch", "turn_on")
    await notify(hass)
    await hass.async_block_till_done()
    assert light_off[0].data["entity_id"] == ["light.flur"]
    assert light_on[0].data["entity_id"] == ["light.flur"]
    assert off[0].data["entity_id"] == ["switch.stehlampe"]
    assert on[0].data["entity_id"] == ["switch.stehlampe"]


async def test_second_later_button_and_typed_minutes(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """A second "later" duration gives a third button; typed input replaces both."""
    await setup(hass, make_entry, options={"snooze_minutes_2": 120})
    await notify(hass)
    actions = phone[0].data["data"]["actions"]
    assert [a["title"] for a in actions] == [
        "Later 30 min",
        "Later 2 h",
        "To assistant",
    ]
    assert actions[1]["action"] == f"message_center_snooze|120|{message_id_of(hass)}"

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    hass.config_entries.async_update_entry(
        entry, options={"snooze_minutes_2": 120, "snooze_input": True}
    )
    await hass.async_block_till_done()
    await notify(hass, title="Zwei")
    actions = phone[1].data["data"]["actions"]
    assert [a["title"] for a in actions] == ["Later", "To assistant"]
    assert actions[0]["behavior"] == "textInput"
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": actions[0]["action"], "reply_text": "5"},
    )
    await hass.async_block_till_done()
    item = next(i for i in open_items(hass) if i["title"] == "Zwei")
    assert item["reason"].startswith("snoozed until")


async def test_no_spacing_by_default(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Without a spacing every level-2 message pulses."""
    blink = await lamps(hass, on=LAMPS)
    await setup(
        hass, make_entry, kinds=[kind_data(priority=2)], options={"lights": LAMPS}
    )
    await notify(hass, title="Feuchte 1")
    await notify(hass, title="Feuchte 2")
    await hass.async_block_till_done()
    assert len([c for c in blink if c.service == "turn_off"]) == 2


async def test_test_push_from_the_settings_tab(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_ws_client: Any,
    hass_admin_user: Any,
) -> None:
    """A test push goes to every recipient without buttons, record or history.

    Push and pulse run under a context of the center's own below the
    administrator's: the user is the administrator, the parent is set.
    """
    blink = await lamps(hass, on=["light.flur"])
    await setup(hass, make_entry, options={"lights": LAMPS})
    client = await hass_ws_client(hass)
    for n, priority in enumerate((1, 2, 3), start=1):
        await client.send_json(
            {"id": n, "type": f"{DOMAIN}/test", "priority": priority}
        )
        reply = await client.receive_json()
        assert reply["success"], reply
        assert reply["result"]["sent"] == [PHONE_NAME]
        assert reply["result"]["failed"] == []
        assert reply["result"]["lights"] == (["light.flur"] if priority == 2 else [])
    await hass.async_block_till_done()
    assert len(phone) == 3
    assert phone[0].data["title"] == "Test priority 1 · Notice"
    assert "actions" not in phone[0].data["data"]
    assert phone[2].data["data"]["channel"] == "alarm_stream"
    assert [c.service for c in blink] == ["turn_off", "turn_on"]
    for call in phone + blink:
        assert call.context.user_id == hass_admin_user.id
        assert call.context.parent_id is not None
    assert hass.states.get("sensor.message_center_open").state == "0"
    assert hass.states.get("sensor.message_center_new").state == "0"
    assert hass.states.get("sensor.message_center_last_delivery").state == "unknown"


def record_switching(hass: HomeAssistant) -> list[ServiceCall]:
    """Capture light and switch turn_on/turn_off calls in order (after setup)."""
    calls: list[ServiceCall] = []

    async def record(call: ServiceCall) -> None:
        calls.append(call)

    for domain in ("light", "switch"):
        for service in ("turn_on", "turn_off"):
            hass.services.async_register(domain, service, record)
    return calls


ALARM_OPTIONS = {
    "alarm_lights": ["light.flur", "switch.stehlampe"],
    "alarm_interval_ms": 100,
    "alarm_max_seconds": 5,
    "alarm_test_seconds": 1,
}


async def test_alarm_light_runs_until_the_push_button_ends_it(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Priority 3: all on, then off/on in step; "end alarm" restores the old states."""
    hass.states.async_set("light.flur", "on")
    hass.states.async_set("switch.stehlampe", "off")
    await setup(hass, make_entry, kinds=[kind_data(priority=3)], options=ALARM_OPTIONS)
    calls = record_switching(hass)
    await notify(hass)
    actions = phone[0].data["data"]["actions"]
    assert [a["title"] for a in actions] == [
        "Later 30 min",
        "To assistant",
        "End alarm",
    ]
    assert phone[0].data["data"]["channel"] == "alarm_stream"
    assert hass.states.get("switch.message_center_alarm").state == "on"
    await asyncio.sleep(0.35)
    assert len(calls) >= 4  # all on, then toggles
    assert calls[0].service == "turn_on"
    assert calls[0].data["transition"] == 0

    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": actions[2]["action"]}
    )
    await hass.async_block_till_done()
    assert hass.states.get("switch.message_center_alarm").state == "off"
    # restored: the lamp that was on is on, the switch that was off is off
    final = {}
    for call in calls:
        for entity_id in call.data["entity_id"]:
            final[entity_id] = call.service
    assert final == {"light.flur": "turn_on", "switch.stehlampe": "turn_off"}
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    events = entry.runtime_data.book.messages[message_id_of(hass)].events
    assert events[0]["kind"] == "alarm_light"


async def test_alarm_button_keeps_its_place_before_own_and_later_buttons(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Priority 3 with a second "later" duration and own buttons: alarm button third.

    The buttons behind it are kept for the iPhone; the center used to cut
    its own list to two before adding the alarm button, so "to assistant"
    was lost on every platform, and own buttons pushed the alarm button
    back to the fourth place or further, invisible on Android.
    """
    await setup(
        hass,
        make_entry,
        kinds=[kind_data(priority=3)],
        options={**ALARM_OPTIONS, "snooze_minutes_2": 120},
    )
    await notify(hass)
    actions = phone[0].data["data"]["actions"]
    assert [a["title"] for a in actions] == [
        "Later 30 min",
        "Later 2 h",
        "End alarm",
        "To assistant",
    ]
    own = {"action": "OWN", "title": "Own"}
    await notify(hass, title="Feuchte: Bad", data={"actions": [own]})
    actions = phone[1].data["data"]["actions"]
    assert [a["title"] for a in actions] == [
        "Own",
        "Later 30 min",
        "End alarm",
        "Later 2 h",
        "To assistant",
    ]
    mid = message_id_of(hass, "Feuchte: Bad")
    assert actions[2]["action"] == f"message_center_alarm_off|{mid}"
    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": actions[2]["action"]}
    )
    await hass.async_block_till_done()
    assert hass.states.get("switch.message_center_alarm").state == "off"


async def test_alarm_light_started_while_stopping_is_ended(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """A level-3 push back while the center stops starts no alarm light that lasts.

    The stop first ends the running alarm light and waits while the lamps
    are restored. A push coming back in that moment used to start the light
    again, and the flag that silences the center came only after that: the
    light ran on for up to its maximum, and nothing could end it, switch,
    page and push button belonging to the center that follows.
    """
    hass.states.async_set("light.flur", "on")
    hass.states.async_set("switch.stehlampe", "off")
    entry = await setup(
        hass, make_entry, kinds=[kind_data(priority=3)], options=ALARM_OPTIONS
    )
    record_switching(hass)
    old = entry.runtime_data
    await notify(hass)
    assert old.alarm_active

    calls: list[ServiceCall] = []
    release = asyncio.Event()
    delivered = asyncio.Event()
    started: list[bool] = []
    restore = MessageCenter._async_restore

    async def hanging(call: ServiceCall) -> None:
        calls.append(call)
        await release.wait()

    @callback
    def seen(event: Any) -> None:
        delivered.set()

    async def releasing(
        self: MessageCenter, before: dict[str, str], context: Context
    ) -> None:
        # the stop waits for this: the push comes back and is recorded meanwhile
        release.set()
        async with asyncio.timeout(2):
            await delivered.wait()
        started.append(self.alarm_active)
        await restore(self, before, context)

    hass.services.async_register("notify", PHONE_ACTION, hanging)
    hass.bus.async_listen_once(EVENT_DELIVERED, seen)
    with no_push_timeout():
        await hass.services.async_call(
            "notify",
            "message_center",
            {"title": "Feuchte: Bad", "message": TEXT},
            blocking=True,
        )
        await settle()
        assert len(calls) == 1
        with patch.object(MessageCenter, "_async_restore", releasing):
            assert await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
    assert started[0]  # the window was open: the light was started once more
    assert not old.alarm_active
    assert old._alarm_task is None
    new = entry.runtime_data
    assert new is not old
    assert not new.alarm_active
    assert len(calls) == 1


async def test_alarm_test_ends_by_itself_and_switch_ends_early(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_ws_client: Any,
    hass_admin_user: Any,
) -> None:
    """The priority-3 test runs for the test duration; the switch can end it early.

    The alarm steps and the restoring run under a context of the center's
    own below the administrator's.
    """
    hass.states.async_set("light.flur", "off")
    hass.states.async_set("switch.stehlampe", "on")
    await setup(hass, make_entry, options=ALARM_OPTIONS)
    calls = record_switching(hass)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/test", "priority": 3})
    reply = await client.receive_json()
    assert reply["result"]["lights"] == ["light.flur", "switch.stehlampe"]
    assert hass.states.get("switch.message_center_alarm").state == "on"
    await asyncio.sleep(2.5)  # test duration plus the settle second before restoring
    await hass.async_block_till_done()
    assert hass.states.get("switch.message_center_alarm").state == "off"
    final = {}
    for call in calls:
        for entity_id in call.data["entity_id"]:
            final[entity_id] = call.service
    assert final == {"light.flur": "turn_off", "switch.stehlampe": "turn_on"}
    for call in calls:
        assert call.context.user_id == hass_admin_user.id
        assert call.context.parent_id is not None
    assert hass.states.get("sensor.message_center_open").state == "0"

    calls.clear()
    # start by hand (the switch entity calls the same method; the recorder above
    # replaced the real switch services, so call the center directly)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await entry.runtime_data.async_start_alarm(source="switch")
    assert hass.states.get("switch.message_center_alarm").state == "on"
    await client.send_json({"id": 2, "type": f"{DOMAIN}/alarm_off"})
    assert (await client.receive_json())["result"] == {"ended": True}
    assert hass.states.get("switch.message_center_alarm").state == "off"
    await client.send_json({"id": 3, "type": f"{DOMAIN}/alarm_off"})
    assert (await client.receive_json())["result"] == {"ended": False}


async def test_silent_repeat_option(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Option silent_repeat: a repeat within the spacing replaces the push silently."""
    await setup(
        hass,
        make_entry,
        kinds=[kind_data(spacing=60)],
        options={"silent_repeat": True},
    )
    await notify(hass)
    await notify(hass)
    assert len(phone) == 2
    assert phone[1].data["data"]["alert_once"] is True
    assert phone[1].data["title"].startswith("2x ")


async def test_alarm_channel_and_announcement(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """The Android alarm channel is an option; alarm_tts adds a spoken push."""
    await setup(
        hass,
        make_entry,
        kinds=[kind_data(priority=3)],
        options={"alarm_channel": "message_center_alarm", "alarm_tts": True},
    )
    await notify(hass)
    await hass.async_block_till_done()
    assert len(phone) == 2
    assert phone[0].data["data"]["channel"] == "message_center_alarm"
    assert phone[0].data["data"]["importance"] == "high"
    assert phone[1].data["message"] == "TTS"
    assert phone[1].data["data"] == {
        "tts_text": "Alarm: Feuchte: Büro",
        "media_stream": "alarm_stream_max",
    }


async def test_announcement_is_not_started_by_the_stopping_center(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """A level-3 push back while the stop writes the history: no announcement.

    Whether to announce used to be decided outside the lock, before the
    stop had set its flag under it: the stopped center spoke the alarm,
    while the center that follows showed the message as unclear.
    """
    await setup(
        hass, make_entry, kinds=[kind_data(priority=3)], options={"alarm_tts": True}
    )
    calls: list[ServiceCall] = []
    release = asyncio.Event()
    write = storage.Store._async_write_data

    async def hanging(call: ServiceCall) -> None:
        calls.append(call)
        await release.wait()

    async def releasing(store: storage.Store, data: dict[str, Any]) -> None:
        if store.key == HISTORY_KEY:
            # the stop writes under the lock: the push comes back meanwhile
            release.set()
            await settle()
        await write(store, data)

    hass.services.async_register("notify", PHONE_ACTION, hanging)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    with no_push_timeout():
        await hass.services.async_call(
            "notify", "message_center", {"title": TITLE, "message": TEXT}, blocking=True
        )
        await settle()
        assert len(calls) == 1
        with patch.object(storage.Store, "_async_write_data", releasing):
            assert await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
    assert release.is_set()
    assert [call.data["message"] for call in calls] == [TEXT]
    assert open_items(hass)[0]["state"] == "unclear"


async def test_snooze_button_runs_in_the_phone_users_context(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """A tap on "later" is handled in the context of the user of that phone."""
    snoozed = async_capture_events(hass, EVENT_SNOOZED)
    await notify(hass)
    alex = await hass.auth.async_create_user("Alex", group_ids=["system-users"])
    user = Context(user_id=alex.id)
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": phone[0].data["data"]["actions"][0]["action"]},
        context=user,
    )
    await hass.async_block_till_done()
    assert len(snoozed) == 1
    assert snoozed[0].context.id == user.id
    assert snoozed[0].context.user_id == alex.id
    assert snoozed[0].data["user_id"] == alex.id
    assert snoozed[0].data["source"] == "phone"


async def test_buttons_of_a_read_only_user_are_ignored(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_read_only_user: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The buttons "later" and "to assistant" check the right of the actions.

    A user who may only read is ignored, logged without title or id; the
    message stays as it was and nothing is forwarded.
    """
    caplog.set_level(logging.INFO, logger="custom_components.message_center")
    snoozed = async_capture_events(hass, EVENT_SNOOZED)
    forwarded = async_capture_events(hass, f"{DOMAIN}_forwarded")
    await notify(hass)
    actions = phone[0].data["data"]["actions"]
    reader = Context(user_id=hass_read_only_user.id)
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": actions[0]["action"]},
        context=reader,
    )
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": actions[1]["action"], "reply_text": "please check"},
        context=reader,
    )
    await hass.async_block_till_done()
    assert snoozed == []
    assert forwarded == []
    msg = center_entry.runtime_data.book.messages[message_id_of(hass)]
    assert msg.state.value == "delivered"
    assert msg.snoozed_until is None
    assert msg.events == []
    assert "Push button message_center_snooze ignored: Unauthorized" in caplog.text
    assert "Push button message_center_forward ignored: Unauthorized" in caplog.text
    assert TITLE not in caplog.text
    assert message_id_of(hass) not in caplog.text


async def test_buttons_of_an_unknown_user_are_ignored(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A phone whose user was deleted cannot snooze, as with the actions."""
    caplog.set_level(logging.INFO, logger="custom_components.message_center")
    snoozed = async_capture_events(hass, EVENT_SNOOZED)
    await notify(hass)
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": phone[0].data["data"]["actions"][0]["action"]},
        context=Context(user_id="deleted-user"),
    )
    await hass.async_block_till_done()
    assert snoozed == []
    assert "Push button message_center_snooze ignored: UnknownUser" in caplog.text


async def test_buttons_of_a_deactivated_user_are_ignored(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_owner_user: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A deactivated user's phone still reaches HA; its taps change nothing.

    The owner fixture makes Alex an ordinary user (the owner cannot be
    deactivated).
    """
    caplog.set_level(logging.INFO, logger="custom_components.message_center")
    snoozed = async_capture_events(hass, EVENT_SNOOZED)
    await notify(hass)
    alex = await hass.auth.async_create_user("Alex", group_ids=["system-users"])
    await hass.auth.async_deactivate_user(alex)
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": phone[0].data["data"]["actions"][0]["action"]},
        context=Context(user_id=alex.id),
    )
    await hass.async_block_till_done()
    assert snoozed == []
    assert "Push button message_center_snooze ignored: Unauthorized" in caplog.text


async def test_read_only_user_may_still_end_the_alarm(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_read_only_user: Any,
) -> None:
    """Ending a running alarm harms nothing: every recipient may do it."""
    hass.states.async_set("light.flur", "on")
    hass.states.async_set("switch.stehlampe", "off")
    await setup(hass, make_entry, kinds=[kind_data(priority=3)], options=ALARM_OPTIONS)
    record_switching(hass)
    await notify(hass)
    assert hass.states.get("switch.message_center_alarm").state == "on"
    actions = phone[0].data["data"]["actions"]
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": actions[2]["action"]},
        context=Context(user_id=hass_read_only_user.id),
    )
    await hass.async_block_till_done()
    assert hass.states.get("switch.message_center_alarm").state == "off"


def refusing(
    hass: HomeAssistant,
    user_id: str,
    *,
    domains: tuple[str, ...] = ("light", "switch"),
    error: type[Unauthorized] = Unauthorized,
) -> list[ServiceCall]:
    """Light and switch services that refuse one user, as Home Assistant does.

    Home Assistant checks the right to the target entities itself before a
    lamp is switched; here the check is stood in for. Every call is recorded.
    Only the ``domains`` named refuse; ``error`` is what they raise.
    """
    calls: list[ServiceCall] = []

    async def switching(call: ServiceCall) -> None:
        calls.append(call)
        if call.context.user_id == user_id and call.domain in domains:
            raise error(context=call.context, user_id=user_id)

    for domain in ("light", "switch"):
        for service in ("turn_on", "turn_off"):
            hass.services.async_register(domain, service, switching)
    return calls


async def send_level_2(hass: HomeAssistant, context: Context) -> None:
    """Send a level-2 message in that context and wait."""
    await hass.services.async_call(
        DOMAIN,
        "send",
        {"title": TITLE, "message": "x", "priority": 2},
        blocking=True,
        context=context,
    )
    await hass.async_block_till_done()


async def test_light_pulse_carries_the_senders_context(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any, hass_admin_user: Any
) -> None:
    """The pulse runs with the user and, as parent, the call of the sender."""
    blink = await lamps(hass, on=LAMPS)
    await setup(hass, make_entry, options={"lights": LAMPS})
    context = Context(user_id=hass_admin_user.id)
    await send_level_2(hass, context)
    assert len(phone) == 1
    assert [c.service for c in blink] == ["turn_off", "turn_on"]
    for call in blink:
        assert call.context.user_id == hass_admin_user.id
        assert call.context.parent_id == context.id


async def test_light_from_automation_keeps_working(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Without a user the pulse runs as before, under the intake call as parent."""
    blink = await lamps(hass, on=LAMPS)
    await setup(
        hass, make_entry, kinds=[kind_data(priority=2)], options={"lights": LAMPS}
    )
    await notify(hass)
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    msg = entry.runtime_data.book.messages[message_id_of(hass)]
    assert [c.service for c in blink] == ["turn_off", "turn_on"]
    for call in blink:
        assert call.context.user_id is None
        assert call.context.parent_id == msg.context_id


async def test_light_refused_for_a_sender_without_the_right(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_read_only_user: Any,
) -> None:
    """Home Assistant refuses the lamps: the push goes out, ``light_failed`` is noted.

    ``send`` is open to every user; the right to the lamps is checked where
    they are switched. The second command of the pulse is not tried.
    """
    for entity_id in LAMPS:
        hass.states.async_set(entity_id, "on")
    calls = refusing(hass, hass_read_only_user.id)
    await setup(hass, make_entry, options={"lights": LAMPS})
    await send_level_2(hass, Context(user_id=hass_read_only_user.id))
    assert len(phone) == 1
    assert [c.service for c in calls] == ["turn_off"]
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    msg = entry.runtime_data.book.messages[message_id_of(hass)]
    assert msg.state.value == "delivered"
    assert [(e["kind"], e["detail"]) for e in msg.events] == [
        ("light", "light.flur, light.kueche"),
        ("light_failed", "light.flur, light.kueche"),
    ]


async def test_alarm_light_carries_the_senders_context(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any, hass_admin_user: Any
) -> None:
    """Alarm steps and the restoring afterwards run in the sender's context."""
    hass.states.async_set("light.flur", "on")
    hass.states.async_set("switch.stehlampe", "off")
    await setup(hass, make_entry, kinds=[kind_data(priority=3)], options=ALARM_OPTIONS)
    calls = record_switching(hass)
    context = Context(user_id=hass_admin_user.id)
    await hass.services.async_call(
        "notify",
        "message_center",
        {"title": TITLE, "message": TEXT},
        blocking=True,
        context=context,
    )
    await hass.async_block_till_done()
    await asyncio.sleep(0.25)
    assert len(calls) >= 3
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await entry.runtime_data.async_stop_alarm()
    final = {}
    for call in calls:
        for entity_id in call.data["entity_id"]:
            final[entity_id] = call.service
    assert final == {"light.flur": "turn_on", "switch.stehlampe": "turn_off"}
    for call in calls:
        assert call.context.user_id == hass_admin_user.id
        assert call.context.parent_id == context.id


async def test_alarm_refused_for_the_sender_ends_at_once(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_read_only_user: Any,
) -> None:
    """A refused first command ends the alarm instead of warning at every step."""
    hass.states.async_set("light.flur", "on")
    hass.states.async_set("switch.stehlampe", "off")
    await setup(hass, make_entry, kinds=[kind_data(priority=3)], options=ALARM_OPTIONS)
    calls = refusing(hass, hass_read_only_user.id)
    await hass.services.async_call(
        "notify",
        "message_center",
        {"title": TITLE, "message": TEXT},
        blocking=True,
        context=Context(user_id=hass_read_only_user.id),
    )
    await hass.async_block_till_done()
    assert len(phone) == 1
    assert phone[0].data["data"]["channel"] == "alarm_stream"
    await asyncio.sleep(0.35)  # three alarm steps
    assert [(c.domain, c.service) for c in calls] == [("light", "turn_on")]
    assert hass.states.get("switch.message_center_alarm").state == "off"
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    msg = entry.runtime_data.book.messages[message_id_of(hass)]
    assert msg.state.value == "delivered"
    assert [(e["kind"], e["detail"]) for e in msg.events] == [
        ("alarm_light", "light.flur, switch.stehlampe"),
        ("light_failed", "light.flur, switch.stehlampe"),
    ]


async def test_alarm_refused_in_one_domain_restores_the_other(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_read_only_user: Any,
) -> None:
    """Lamps switched before the refusal of the other domain are put back.

    The first step switches the lights, then the switches; a right to the
    lights alone (a hand-made policy) left the lights on before.
    """
    hass.states.async_set("light.flur", "off")
    hass.states.async_set("switch.stehlampe", "off")
    await setup(hass, make_entry, kinds=[kind_data(priority=3)], options=ALARM_OPTIONS)
    calls = refusing(hass, hass_read_only_user.id, domains=("switch",))
    await hass.services.async_call(
        "notify",
        "message_center",
        {"title": TITLE, "message": TEXT},
        blocking=True,
        context=Context(user_id=hass_read_only_user.id),
    )
    await hass.async_block_till_done()
    assert len(phone) == 1
    await asyncio.sleep(1.3)  # the settle second before restoring, then the step
    assert hass.states.get("switch.message_center_alarm").state == "off"
    assert [(c.domain, c.service, c.data["entity_id"]) for c in calls] == [
        ("light", "turn_on", ["light.flur"]),
        ("switch", "turn_on", ["switch.stehlampe"]),
        ("light", "turn_off", ["light.flur"]),
    ]
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    msg = entry.runtime_data.book.messages[message_id_of(hass)]
    assert [e["kind"] for e in msg.events] == ["alarm_light", "light_failed"]


async def test_light_refused_for_a_deleted_sender(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """A stored sender that no longer exists: Home Assistant raises ``UnknownUser``.

    It is a kind of ``Unauthorized``, so the pulse ends the same way: push
    out, ``light_failed`` noted, no warning at every command.
    """
    for entity_id in LAMPS:
        hass.states.async_set(entity_id, "on")
    calls = refusing(hass, "geloeschter-nutzer", error=UnknownUser)
    await setup(hass, make_entry, options={"lights": LAMPS})
    await send_level_2(hass, Context(user_id="geloeschter-nutzer"))
    assert len(phone) == 1
    assert [c.service for c in calls] == ["turn_off"]
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    msg = entry.runtime_data.book.messages[message_id_of(hass)]
    assert msg.state.value == "delivered"
    assert [e["kind"] for e in msg.events] == ["light", "light_failed"]


async def test_alarm_switch_passes_the_callers_context(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any, hass_admin_user: Any
) -> None:
    """The switch "Alarm" hands the context of whoever flipped it to the lamps."""
    blink = await lamps(hass, on=["light.flur"])
    await setup(
        hass,
        make_entry,
        options={**ALARM_OPTIONS, "alarm_lights": ["light.flur"]},
    )
    context = Context(user_id=hass_admin_user.id)
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.message_center_alarm"},
        blocking=True,
        context=context,
    )
    await asyncio.sleep(0.25)
    assert hass.states.get("switch.message_center_alarm").state == "on"
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.message_center_alarm"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(blink) >= 3
    assert blink[-1].service == "turn_on"  # restored: it was on
    for call in blink:
        assert call.context.user_id == hass_admin_user.id
        assert call.context.parent_id == context.id


async def test_old_button_ids_still_work_the_actions_take_the_new_id_only(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """A button on a push from before 0.11 carries origin:key and is understood.

    The old id is mapped to the new one for a while, at the push buttons
    only: discard, snooze and forward take the new id.
    """
    await notify(hass)
    center = center_entry.runtime_data
    msg = center.book.messages[message_id_of(hass)]
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": f"message_center_snooze|45|unknown:{TITLE}"},
    )
    await hass.async_block_till_done()
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": f"message_center_forward|unknown:{TITLE}", "reply_text": "ok?"},
    )
    await hass.async_block_till_done()
    assert [(e["kind"], e["detail"]) for e in msg.events] == [
        ("snoozed", "45 min"),
        ("forwarded", "ok?"),
    ]
    for action, data in (
        ("snooze", {"minutes": 5}),
        ("forward", {}),
    ):
        with pytest.raises(ServiceValidationError) as err:
            await hass.services.async_call(
                DOMAIN,
                action,
                {"message_id": f"unknown:{TITLE}", **data},
                blocking=True,
            )
        assert err.value.translation_key == "not_found"
    assert await hass.services.async_call(
        DOMAIN,
        "discard",
        {"message_id": f"unknown:{TITLE}"},
        blocking=True,
        return_response=True,
    ) == {"result": "done", "discarded": 0}
    assert len(msg.events) == 2


async def test_ignored_push_button_logs_no_title(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A button for a message that is gone: the log names the button and the error."""
    caplog.set_level(logging.INFO, logger="custom_components.message_center")
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": f"message_center_snooze|30|unknown:{TITLE}"},
    )
    await hass.async_block_till_done()
    assert "Push button message_center_snooze ignored: NotFoundError" in caplog.text
    assert TITLE not in caplog.text


async def test_task_names_carry_no_title_and_no_id(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Home Assistant logs task names at shutdown: nothing of the message in them.

    Run through: a failed push, its retry, the delivery, a repeat within the
    spacing that replaces the push, a button and a forward.
    """
    names: list[str] = []
    launch = MessageCenter._launch

    def recording(self: MessageCenter, coro: Any, name: str) -> None:
        names.append(name)
        launch(self, coro, name)

    monkeypatch.setattr(MessageCenter, "_launch", recording)
    await setup(hass, make_entry, kinds=[kind_data(spacing=360)])
    failed = await failing_phone(hass)
    await notify(hass)
    await tick(hass, freezer, seconds=61)
    assert len(failed) == 2
    phone = async_mock_service(hass, "notify", PHONE_ACTION)
    await tick(hass, freezer, minutes=5)
    assert len(phone) == 1
    await notify(hass)  # within the spacing: replaces the push
    assert phone[1].data["title"] == f"2x {TITLE}"
    actions = phone[0].data["data"]["actions"]
    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": actions[1]["action"]}
    )
    await hass.async_block_till_done()
    await hass.services.async_call(
        DOMAIN, "forward", {"message_id": message_id_of(hass)}, blocking=True
    )
    await hass.async_block_till_done()
    assert {"cycle", "retry", "replace", "button"} <= set(names)
    for name in names:
        assert TITLE not in name, name
        assert message_id_of(hass) not in name, name
