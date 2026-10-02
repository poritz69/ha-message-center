"""Tests for rules, retries, spacing, restart and expiry through the running center."""

from __future__ import annotations

import asyncio
import copy
from datetime import timedelta
import json
import logging
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir, storage
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.message_center.center import MessageCenter
from custom_components.message_center.const import (
    DOMAIN,
    EVENT_DELIVERED,
    EVENT_DISCARDED,
    EVENT_SNOOZED,
)
from custom_components.message_center.models import MessageState, ReasonKind
from custom_components.message_center.store import HISTORY_KEY, STORAGE_KEY

from .conftest import (
    PHONE_ACTION,
    RECIPIENT,
    kind_data,
    night_rule_data,
    slow_writes,
)
from .test_services import TEXT, TITLE, message_id_of, notify, open_items


async def tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, **delta: float
) -> None:
    """Advance time and fire the timers, twice for timers re-armed by the first."""
    freezer.tick(timedelta(**delta))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()


async def settle() -> None:
    """Let started tasks run as far as they get; a push that hangs stays out."""
    for _ in range(50):
        await asyncio.sleep(0)


async def advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, **delta: float
) -> None:
    """Advance time and fire the timers without waiting for a push that hangs.

    Firing the timers also fires the time limit of a push that is under way,
    once the clock is ahead of it. Tests with a hanging push therefore run
    with ``no_push_timeout``.
    """
    freezer.tick(timedelta(**delta))
    async_fire_time_changed(hass, dt_util.utcnow())
    await settle()


def no_push_timeout() -> Any:
    """Keep the time limit of a push out of reach of the advanced clock."""
    return patch("custom_components.message_center.delivery.PUSH_TIMEOUT", 10**6)


def saved_message(hass_storage: dict[str, Any]) -> tuple[str | None, list[str]]:
    """State and recipients of the test message as the working store has them.

    Found by its key: the store may be read while the center is still
    starting and its book, which knows the ids, is not there yet.
    """
    saved = next(
        (
            raw
            for raw in hass_storage[STORAGE_KEY]["data"]["messages"].values()
            if raw["key"] == TITLE
        ),
        {},
    )
    return saved.get("state"), list(saved.get("recipients", {}))


async def setup(hass: HomeAssistant, make_entry: Any, **kw: Any) -> MockConfigEntry:
    """Set up a center with the given rules, kinds and options."""
    entry = make_entry(**kw)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def failing_phone(hass: HomeAssistant) -> list[ServiceCall]:
    """Let the phone fail every push; return the calls it got."""
    calls: list[ServiceCall] = []

    async def failing(call: ServiceCall) -> None:
        calls.append(call)
        raise HomeAssistantError("boom")

    hass.services.async_register("notify", PHONE_ACTION, failing)
    return calls


def rule_id(hass: HomeAssistant) -> str:
    """Id of the first rule subentry."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    return next(
        sid for sid, sub in entry.subentries.items() if sub.subentry_type == "rule"
    )


async def test_night_rule_holds_and_releases(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Night mode on: level 1 waits with reason; off: it is delivered."""
    hass.states.async_set("input_boolean.night_mode", "on")
    await setup(hass, make_entry, rules=[night_rule_data()])
    assert hass.states.get("sensor.message_center_active_rules").state == "1"

    await notify(hass)
    assert phone == []
    item = open_items(hass)[0]
    assert item["state"] == "waiting"
    assert item["reason"].startswith("held back: Nacht until")

    hass.states.async_set("input_boolean.night_mode", "off")
    await hass.async_block_till_done()
    assert len(phone) == 1
    assert open_items(hass) == []
    assert hass.states.get("sensor.message_center_active_rules").state == "0"


async def test_kind_with_no_hold_passes_the_night_rule(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """A kind marked 'do not hold' is delivered at night; priority 3 passes anyway."""
    hass.states.async_set("input_boolean.night_mode", "on")
    await setup(
        hass,
        make_entry,
        rules=[night_rule_data()],
        kinds=[
            kind_data(no_hold=True),
            kind_data(name="Feuer", title_value="Feuer", priority=3),
        ],
    )
    await notify(hass)
    await notify(hass, title="Feuer in der Küche")
    assert len(phone) == 2
    assert phone[1].data["data"]["channel"] == "alarm_stream"


async def test_unknown_rule_entity_holds_with_repair(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """A missing rule entity holds level 1 and raises a repair until it returns."""
    await setup(hass, make_entry, rules=[night_rule_data()])
    await notify(hass)
    assert open_items(hass)[0]["reason"].startswith(
        "mode unknown: input_boolean.night_mode"
    )
    registry = ir.async_get(hass)
    assert registry.async_get_issue(DOMAIN, "rule_entity_unavailable_" + rule_id(hass))
    hass.states.async_set("input_boolean.night_mode", "off")
    await hass.async_block_till_done()
    assert len(phone) == 1
    assert not registry.async_get_issue(
        DOMAIN, "rule_entity_unavailable_" + rule_id(hass)
    )


async def test_max_duration_releases_held_messages(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    """After 12 hours the held message is delivered and a repair is raised."""
    hass.states.async_set("input_boolean.night_mode", "on")
    await setup(hass, make_entry, rules=[night_rule_data()])
    await notify(hass)
    await tick(hass, freezer, hours=11)
    assert phone == []
    await tick(hass, freezer, hours=1, seconds=1)
    assert len(phone) == 1
    assert ir.async_get(hass).async_get_issue(
        DOMAIN, "rule_max_duration_" + rule_id(hass)
    )
    rules = hass.states.get("sensor.message_center_active_rules").attributes["rules"]
    assert rules[0]["expired"] is True


async def test_expiry_while_held(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A held message whose kind expires is discarded without a push."""
    hass.states.async_set("input_boolean.night_mode", "on")
    await setup(
        hass, make_entry, rules=[night_rule_data()], kinds=[kind_data(expires_after=5)]
    )
    await notify(hass)
    await tick(hass, freezer, minutes=5, seconds=1)
    assert phone == []
    assert open_items(hass) == []


async def test_retry_after_failure(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failing phone is retried after 1 minute; disturbed and notification show it."""
    calls: list[ServiceCall] = []

    async def failing(call: ServiceCall) -> None:
        calls.append(call)
        raise HomeAssistantError("boom")

    hass.services.async_register("notify", PHONE_ACTION, failing)
    await notify(hass)
    assert len(calls) == 1
    assert open_items(hass)[0]["state"] == "retrying"
    assert hass.states.get("sensor.message_center_disturbed").state == "1"
    item = hass.states.get("sensor.message_center_disturbed").attributes["items"][0]
    assert item["last_error"] == {PHONE_ACTION: "HomeAssistantError"}
    notifications = persistent_notification._async_get_or_create_notifications(hass)
    assert f"{DOMAIN}_failed_deliveries" in notifications

    await tick(hass, freezer, seconds=55)
    assert len(calls) == 1
    await tick(hass, freezer, seconds=5)
    assert len(calls) == 2

    good = async_mock_service(hass, "notify", PHONE_ACTION)
    await tick(hass, freezer, minutes=4)
    assert len(good) == 1
    assert open_items(hass) == []
    assert hass.states.get("sensor.message_center_disturbed").state == "0"
    notifications = persistent_notification._async_get_or_create_notifications(hass)
    assert f"{DOMAIN}_failed_deliveries" not in notifications


async def test_missing_action_is_retried_and_repaired(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A missing notify action counts as a delivery error, not as not ready."""
    hass.services.async_remove("notify", PHONE_ACTION)
    assert hass.states.get("binary_sensor.message_center_ready").state == "on"
    await notify(hass)
    assert open_items(hass)[0]["state"] == "retrying"
    assert hass.states.get("binary_sensor.message_center_ready").attributes[
        "missing_recipients"
    ] == [PHONE_ACTION]
    await tick(hass, freezer, minutes=16)
    assert ir.async_get(hass).async_get_issue(
        DOMAIN, f"recipient_unreachable_{PHONE_ACTION}"
    )
    good = async_mock_service(hass, "notify", PHONE_ACTION)
    await tick(hass, freezer, minutes=60)
    assert len(good) == 1
    assert open_items(hass) == []
    assert not ir.async_get(hass).async_get_issue(
        DOMAIN, f"recipient_unreachable_{PHONE_ACTION}"
    )


async def test_spacing_bundles_then_starts_new_cycle(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Spacing 60: a repeat within the hour is a silent replace, after it a new push."""
    await setup(hass, make_entry, kinds=[kind_data(spacing=60)])
    await notify(hass)
    await tick(hass, freezer, minutes=10)
    await notify(hass)
    assert len(phone) == 2
    assert "alert_once" not in phone[1].data["data"]  # audible unless silent_repeat
    assert phone[1].data["title"].startswith("2x ")
    assert "subtitle" not in phone[1].data["data"]
    await tick(hass, freezer, minutes=51)
    await notify(hass)
    assert len(phone) == 3
    assert "alert_once" not in phone[2].data["data"]
    assert (
        phone[2].data["title"] == "Feuchte: Büro"
    )  # new generation: counter starts over


async def test_restart_with_long_gap_marks_unclear(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
) -> None:
    """After a gap over 60 minutes open messages are unclear until they arrive again."""
    hass.states.async_set("input_boolean.night_mode", "on")
    entry = await setup(hass, make_entry, rules=[night_rule_data()])
    await notify(hass)
    assert open_items(hass)[0]["state"] == "waiting"
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    hass_storage[STORAGE_KEY]["data"]["saved_at"] = (
        dt_util.utcnow() - timedelta(hours=3)
    ).isoformat()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    item = open_items(hass)[0]
    assert item["state"] == "unclear"
    assert item["reason"].startswith("gap of 3 h")
    assert ir.async_get(hass).async_get_issue(DOMAIN, "unclear_messages")
    assert phone == []

    hass.states.async_set("input_boolean.night_mode", "off")
    await notify(hass)
    assert len(phone) == 1
    assert open_items(hass) == []
    assert not ir.async_get(hass).async_get_issue(DOMAIN, "unclear_messages")


async def test_send_now_releases_a_held_message(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """The page's 'send now' delivers a held message despite the rule."""
    hass.states.async_set("input_boolean.night_mode", "on")
    entry = await setup(hass, make_entry, rules=[night_rule_data()])
    await notify(hass)
    assert phone == []
    await entry.runtime_data.async_send_now(message_id_of(hass))
    await hass.async_block_till_done()
    assert len(phone) == 1
    assert open_items(hass) == []


async def test_restart_restores_last_delivery_and_today_count(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """After a restart the overview keeps the last delivery and the day count."""
    entry = await setup(hass, make_entry)
    await notify(hass)
    assert len(phone) == 1
    before = hass.states.get("sensor.message_center_last_delivery").state
    assert before != "unknown"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.message_center_last_delivery").state == before
    center = entry.runtime_data
    assert center.delivered_today == 1
    assert center.last_delivery[2] == TITLE


# ----- first save, then send ------------------------------------------------
#
# These tests run with ``slow_writes``: with the writer of ``hass_storage`` a
# push started before the write would pass them as well.


async def test_first_push_is_saved_as_sending_before_it_goes_out(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """When the push reaches the phone, "sending" and the recipients are on disk."""
    seen: list[tuple[str | None, list[str]]] = []

    async def handler(call: ServiceCall) -> None:
        seen.append(saved_message(hass_storage))

    hass.services.async_register("notify", PHONE_ACTION, handler)
    with slow_writes():
        await notify(hass)
    assert seen == [("sending", [PHONE_ACTION])]
    assert saved_message(hass_storage) == ("delivered", [PHONE_ACTION])


async def test_released_push_is_saved_as_sending_before_it_goes_out(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """The same holds at the end of a rule, of a snooze and for "send now"."""
    seen: list[tuple[str | None, list[str]]] = []

    async def handler(call: ServiceCall) -> None:
        seen.append(saved_message(hass_storage))

    hass.states.async_set("input_boolean.night_mode", "on")
    entry = await setup(hass, make_entry, rules=[night_rule_data()])
    center = entry.runtime_data
    hass.services.async_register("notify", PHONE_ACTION, handler)
    await notify(hass)
    assert saved_message(hass_storage) == ("waiting", [])

    with slow_writes():
        hass.states.async_set("input_boolean.night_mode", "off")  # the end of the rule
        await hass.async_block_till_done()
        assert len(seen) == 1
        await center.async_snooze(message_id_of(hass), 5)
        assert saved_message(hass_storage)[0] == "waiting"
        await tick(hass, freezer, minutes=5)  # the timer at the end of the snooze
        assert len(seen) == 2
        await center.async_snooze(message_id_of(hass), 5)
        await center.async_send_now(message_id_of(hass))
        await hass.async_block_till_done()
    assert seen == [("sending", [PHONE_ACTION])] * 3


async def test_push_released_at_the_start_is_saved_as_sending_before_it_goes_out(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
) -> None:
    """A message whose rule ended while Home Assistant was down: saved, then sent."""
    seen: list[tuple[str | None, list[str]]] = []

    async def handler(call: ServiceCall) -> None:
        seen.append(saved_message(hass_storage))

    hass.states.async_set("input_boolean.night_mode", "on")
    entry = await setup(hass, make_entry, rules=[night_rule_data()])
    hass.services.async_register("notify", PHONE_ACTION, handler)
    await notify(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert saved_message(hass_storage) == ("waiting", [])

    hass.states.async_set("input_boolean.night_mode", "off")
    with slow_writes():
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert seen == [("sending", [PHONE_ACTION])]
    assert open_items(hass) == []


async def test_push_released_by_a_changed_rule_is_saved_as_sending_before_it_goes_out(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
) -> None:
    """Taking the rule away releases what it held: saved as sending, pushed once."""
    seen: list[tuple[str | None, list[str]]] = []

    async def handler(call: ServiceCall) -> None:
        seen.append(saved_message(hass_storage))

    hass.states.async_set("input_boolean.night_mode", "on")
    entry = await setup(hass, make_entry, rules=[night_rule_data()])
    hass.services.async_register("notify", PHONE_ACTION, handler)
    await notify(hass)
    assert seen == []

    with slow_writes():
        hass.config_entries.async_remove_subentry(entry, rule_id(hass))
        await hass.async_block_till_done()
    assert seen == [("sending", [PHONE_ACTION])]
    assert entry.runtime_data._pending == []
    assert open_items(hass) == []


async def test_restart_during_first_push_is_unclear_and_not_sent_again(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Home Assistant ends while the first push is out: unclear, no second push.

    The restart runs with the store as it was on disk when the push reached
    the phone.
    """
    calls: list[ServiceCall] = []
    on_disk: list[dict[str, Any]] = []

    async def handler(call: ServiceCall) -> None:
        calls.append(call)
        on_disk.append(copy.deepcopy(hass_storage[STORAGE_KEY]))

    hass.services.async_register("notify", PHONE_ACTION, handler)
    with slow_writes():
        await notify(hass)
    assert len(calls) == 1

    assert await hass.config_entries.async_unload(center_entry.entry_id)
    await hass.async_block_till_done()
    hass_storage[STORAGE_KEY] = on_disk[0]
    assert await hass.config_entries.async_setup(center_entry.entry_id)
    await hass.async_block_till_done()

    assert len(calls) == 1
    item = open_items(hass)[0]
    assert item["state"] == "unclear"
    assert item["reason"].startswith("restart during delivery")
    assert ir.async_get(hass).async_get_issue(DOMAIN, "unclear_messages")


async def test_reload_during_first_push_leaves_the_old_center_silent(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """The entry is reloaded while the first push is out: the old center falls silent.

    The new center finds "sending" and shows the message as unclear.
    When the push of the old center then comes back, it used to record
    delivered, write its book over the new one's, arm its timer and fire
    the event. A stopped center writes, schedules, starts and acts no more.
    """
    calls: list[ServiceCall] = []
    release = asyncio.Event()

    async def hanging(call: ServiceCall) -> None:
        calls.append(call)
        await release.wait()

    hass.services.async_register("notify", PHONE_ACTION, hanging)
    events = async_capture_events(hass, EVENT_DELIVERED)
    old = center_entry.runtime_data
    with no_push_timeout():
        with slow_writes():
            await hass.services.async_call(
                "notify",
                "message_center",
                {"title": TITLE, "message": TEXT},
                blocking=True,
            )
            await settle()
        assert len(calls) == 1
        assert saved_message(hass_storage)[0] == "sending"

        assert await hass.config_entries.async_reload(center_entry.entry_id)
        await settle()
        new = center_entry.runtime_data
        assert new is not old
        assert open_items(hass)[0]["state"] == "unclear"
        assert saved_message(hass_storage)[0] == "unclear"
        release.set()
        await hass.async_block_till_done()

    assert len(calls) == 1
    assert saved_message(hass_storage)[0] == "unclear"  # not written over
    assert events == []
    assert old._timer is None
    assert old._pending == []
    assert new.book.get(message_id_of(hass)).state is MessageState.UNCLEAR
    assert open_items(hass)[0]["state"] == "unclear"
    assert ir.async_get(hass).async_get_issue(DOMAIN, "unclear_messages")
    # tasks of the old center created before the stop find the flag as well
    history = copy.deepcopy(hass_storage[HISTORY_KEY])
    await old._async_tick()
    await old._async_housekeeping()
    await old._async_rule_changed("input_boolean.night_mode", "off")
    assert saved_message(hass_storage)[0] == "unclear"
    assert hass_storage[HISTORY_KEY] == history
    assert old._timer is None


async def test_timer_armed_while_the_stop_waits_is_cancelled(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
) -> None:
    """A push back just before the stop may arm the timer: the stop takes it down.

    The stop cancels the timer before it waits for the lock. A push that
    holds the lock at that moment still counts (it came back before the
    stop) and arms the timer again, here for the retry of a failed push;
    the flag came after. The timer of the old center used to stay armed.
    """
    entry = await setup(hass, make_entry)
    old = entry.runtime_data
    calls: list[ServiceCall] = []
    release = asyncio.Event()
    stopping = asyncio.Event()
    stop = MessageCenter.async_stop

    async def hanging(call: ServiceCall) -> None:
        calls.append(call)
        await release.wait()
        raise HomeAssistantError("boom")

    async def signalling(self: MessageCenter) -> None:
        stopping.set()  # from here the stop reaches the lock without giving way
        await stop(self)

    hass.services.async_register("notify", PHONE_ACTION, hanging)
    with no_push_timeout():
        await hass.services.async_call(
            "notify", "message_center", {"title": TITLE, "message": TEXT}, blocking=True
        )
        await settle()
        assert len(calls) == 1
        with patch.object(MessageCenter, "async_stop", signalling):
            async with old._lock:
                release.set()
                await settle()  # the push is back and waits for the lock, first
                reload = hass.async_create_task(
                    hass.config_entries.async_reload(entry.entry_id)
                )
                async with asyncio.timeout(2):
                    await stopping.wait()
            assert await reload
            await hass.async_block_till_done()
    assert old._stopped
    assert old._timer is None
    assert saved_message(hass_storage)[0] == "retrying"  # back before the stop
    assert entry.runtime_data is not old
    assert entry.runtime_data._timer is not None
    assert open_items(hass)[0]["state"] == "retrying"


async def test_push_goes_out_although_a_listener_fails(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """What is reserved and saved is pushed, whatever fails in the display after it.

    The push used to be started last, behind the listeners. One of them
    raising left the message in sending, its recipient reserved and no push
    out, until some other call started it along.
    """
    center = center_entry.runtime_data

    def broken() -> None:
        raise RuntimeError("boom")

    remove = center.add_listener(broken)
    with pytest.raises(RuntimeError):
        await center.async_intake(title=TITLE, message=TEXT, context=Context())
    remove()
    await hass.async_block_till_done()
    assert len(phone) == 1
    assert center._pending == []
    assert center.book.get(message_id_of(hass)).state is MessageState.DELIVERED


async def test_cancelled_intake_is_taken_back(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """An intake cancelled while the store is written is not accepted.

    The sender never got its answer. Nothing is pushed and nothing stays
    reserved; the message arriving again starts from scratch. The write
    itself is not cancelled, so the timer writes the book once more.
    """
    center = center_entry.runtime_data
    write = storage.Store._async_write_data
    started = asyncio.Event()
    release = asyncio.Event()

    async def hanging(store: storage.Store, data: dict[str, Any]) -> None:
        if store.key == STORAGE_KEY:
            started.set()
            await release.wait()
        await write(store, data)

    with patch.object(storage.Store, "_async_write_data", hanging):
        task = hass.async_create_task(
            center.async_intake(title=TITLE, message=TEXT, context=Context())
        )
        async with asyncio.timeout(2):
            await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        release.set()
        await hass.async_block_till_done()
    assert phone == []
    assert center._pending == []
    assert center.book.get(message_id_of(hass)) is None
    assert center.unknown_items() == []
    # the write landed after all
    assert saved_message(hass_storage)[0] == "sending"
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()
    assert saved_message(hass_storage)[0] is None  # and is put right by the timer
    assert center._timer_at is None

    await notify(hass)
    assert [call.data["title"] for call in phone] == [TITLE]  # not "2x"
    assert center.book.get(message_id_of(hass)).count == 1


# ----- one attempt at a time ------------------------------------------------


async def test_slow_retry_is_not_started_twice(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A retry that takes seconds runs once, counts once and arms no timer."""
    calls: list[ServiceCall] = []
    release = asyncio.Event()

    async def slow_failure(call: ServiceCall) -> None:
        calls.append(call)
        if len(calls) > 1:
            await release.wait()
        raise HomeAssistantError("boom")

    hass.services.async_register("notify", PHONE_ACTION, slow_failure)
    center = center_entry.runtime_data
    await notify(hass)
    assert len(calls) == 1
    status = center.book.get(message_id_of(hass)).recipients[PHONE_ACTION]
    assert status.attempts == 1

    with (
        no_push_timeout(),
        patch.object(center.store, "async_save", wraps=center.store.async_save) as save,
    ):
        await advance(hass, freezer, seconds=60)
        assert len(calls) == 2  # the retry is out and does not come back
        writes = save.call_count
        for _ in range(4):
            await advance(hass, freezer, seconds=1)
        assert len(calls) == 2
        assert save.call_count == writes  # no tick, no write per second
        assert center._timer_at is None  # nothing to wait for but the result
        assert open_items(hass)[0]["next_try"] is None

        release.set()
        await hass.async_block_till_done()
    assert len(calls) == 2
    assert status.attempts == 2
    assert status.next_try - status.first_failed_at == timedelta(minutes=5)
    assert center._timer_at == status.next_try


async def test_slow_successful_retry_pushes_once(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A retry that succeeds slowly reaches the phone once."""
    calls: list[ServiceCall] = []
    release = asyncio.Event()

    async def slow(call: ServiceCall) -> None:
        calls.append(call)
        if len(calls) == 1:
            raise HomeAssistantError("boom")
        await release.wait()

    hass.services.async_register("notify", PHONE_ACTION, slow)
    await notify(hass)
    with no_push_timeout():
        await advance(hass, freezer, seconds=60)
        for _ in range(4):
            await advance(hass, freezer, seconds=1)
        assert len(calls) == 2
        release.set()
        await hass.async_block_till_done()
    assert len(calls) == 2
    assert open_items(hass) == []
    assert hass.states.get("sensor.message_center_disturbed").state == "0"


async def test_cancelled_push_gives_its_recipient_back(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A retry whose task is cancelled leaves the recipient due, not reserved."""
    calls: list[ServiceCall] = []
    hang = asyncio.Event()

    async def failing(call: ServiceCall) -> None:
        calls.append(call)
        if len(calls) == 2:
            await hang.wait()
        raise HomeAssistantError("boom")

    hass.services.async_register("notify", PHONE_ACTION, failing)
    center = center_entry.runtime_data
    await notify(hass)
    status = center.book.get(message_id_of(hass)).recipients[PHONE_ACTION]
    with no_push_timeout():
        await advance(hass, freezer, seconds=60)
        assert status.in_flight
        (task,) = (t for t in asyncio.all_tasks() if t.get_name().endswith(": retry"))
        task.cancel()
        await settle()
        assert not status.in_flight
        assert status.attempts == 1
        await tick(hass, freezer, seconds=1)
    assert len(calls) == 3
    assert status.attempts == 2


async def test_data_that_cannot_be_pushed_counts_as_a_failed_attempt(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Data of the sender the push cannot be built from fails the attempt.

    ``actions`` that is no list raised while the push was built. The first
    push then stayed in sending for good; a retry was started again every
    second, each time with a write of the store and without ever counting.
    """
    center = center_entry.runtime_data
    await notify(hass, data={"actions": 5})
    assert open_items(hass)[0]["state"] == "retrying"
    status = center.book.get(message_id_of(hass)).recipients[PHONE_ACTION]
    assert (status.attempts, status.last_error) == (1, "TypeError")

    with patch.object(
        center.store, "async_save", wraps=center.store.async_save
    ) as save:
        await tick(hass, freezer, seconds=60)
        assert status.attempts == 2
        writes = save.call_count
        for _ in range(30):
            await tick(hass, freezer, seconds=1)
        assert save.call_count == writes
    assert status.attempts == 2
    assert status.next_try - status.first_failed_at == timedelta(minutes=5)
    assert phone == []

    await notify(hass, data={"actions": [{"action": "x", "title": "X"}]})
    await tick(hass, freezer, minutes=4)
    assert len(phone) == 1
    assert open_items(hass) == []


async def test_error_while_a_push_is_prepared_counts_as_a_failed_attempt(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Whatever a push raises is its result, so the retry plan moves on.

    Only a cancelled push gives its recipient back as due. An error taken
    for that would start the retry again every second.
    """
    center = center_entry.runtime_data
    calls = await failing_phone(hass)
    await notify(hass)
    status = center.book.get(message_id_of(hass)).recipients[PHONE_ACTION]

    with (
        patch.object(center, "_push_actions", side_effect=RuntimeError("boom")),
        patch.object(center.store, "async_save", wraps=center.store.async_save) as save,
    ):
        await tick(hass, freezer, seconds=60)
        assert (status.attempts, status.last_error) == (2, "RuntimeError")
        writes = save.call_count
        for _ in range(30):
            await tick(hass, freezer, seconds=1)
        assert save.call_count == writes
    assert status.attempts == 2
    assert not status.in_flight
    assert len(calls) == 1


# ----- retries ask the rules and the expiry ---------------------------------


async def test_retry_waits_while_rule_holds(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A due retry under a rule is not sent, shows the rule and follows its end."""
    hass.states.async_set("input_boolean.night_mode", "off")
    await setup(hass, make_entry, rules=[night_rule_data()])
    calls = await failing_phone(hass)
    await notify(hass)
    assert len(calls) == 1
    assert open_items(hass)[0]["state"] == "retrying"

    hass.states.async_set("input_boolean.night_mode", "on")
    await hass.async_block_till_done()
    assert open_items(hass)[0]["reason"].startswith("delivery failed")
    await tick(hass, freezer, seconds=61)
    assert len(calls) == 1
    item = open_items(hass)[0]
    assert item["state"] == "retrying"
    assert item["reason"].startswith("held back: Nacht until")
    await tick(hass, freezer, minutes=5)
    assert len(calls) == 1
    assert open_items(hass)[0]["reason"].startswith("held back: Nacht until")

    good = async_mock_service(hass, "notify", PHONE_ACTION)
    hass.states.async_set("input_boolean.night_mode", "off")
    await hass.async_block_till_done()
    assert len(good) == 1  # at the end of the rule, not at the next plan time
    assert open_items(hass) == []


async def test_held_retry_is_released_by_a_changed_rule(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Taking the rule away sends a retry it held back at once."""
    hass.states.async_set("input_boolean.night_mode", "off")
    entry = await setup(hass, make_entry, rules=[night_rule_data()])
    calls = await failing_phone(hass)
    await notify(hass)
    hass.states.async_set("input_boolean.night_mode", "on")
    await tick(hass, freezer, seconds=61)
    assert open_items(hass)[0]["reason"].startswith("held back: Nacht until")

    good = async_mock_service(hass, "notify", PHONE_ACTION)
    hass.config_entries.async_remove_subentry(entry, rule_id(hass))
    await hass.async_block_till_done()
    assert (len(calls), len(good)) == (1, 1)
    assert open_items(hass) == []


async def test_send_now_brings_a_planned_retry_forward(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """The page's "send now" pushes a retry now, not at its plan time."""
    entry = await setup(hass, make_entry)
    calls = await failing_phone(hass)
    await notify(hass)
    assert len(calls) == 1
    item = open_items(hass)[0]
    assert item["state"] == "retrying"
    assert item["next_try"] is not None

    good = async_mock_service(hass, "notify", PHONE_ACTION)
    await entry.runtime_data.async_send_now(message_id_of(hass))
    await hass.async_block_till_done()
    assert (len(calls), len(good)) == (1, 1)
    assert open_items(hass) == []
    msg = entry.runtime_data.book.get(message_id_of(hass))
    assert msg is not None
    assert [e["kind"] for e in msg.events] == ["sent_now"]


@pytest.mark.parametrize("held", [False, True], ids=["planned", "held"])
async def test_send_now_pushes_a_retry_to_the_recipient_without_the_message(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
    held: bool,
) -> None:
    """send_now on a retry pushes once, to the recipient that has not got it.

    The one that has the message keeps it and gets no second push, whether a
    rule holds the retry back or its plan time is still ahead.
    """
    hass.states.async_set("input_boolean.night_mode", "off")
    other = dict(RECIPIENT, action="mobile_app_phone_bea", name="Phone Bea")
    entry = await setup(
        hass, make_entry, recipients=[RECIPIENT, other], rules=[night_rule_data()]
    )
    failed: list[ServiceCall] = []

    async def failing(call: ServiceCall) -> None:
        failed.append(call)
        raise HomeAssistantError("boom")

    hass.services.async_register("notify", other["action"], failing)
    await notify(hass)
    assert (len(phone), len(failed)) == (1, 1)
    if held:
        hass.states.async_set("input_boolean.night_mode", "on")
        await tick(hass, freezer, seconds=61)
    item = open_items(hass)[0]
    assert item["state"] == "retrying"
    assert (item["next_try"] is None) is held
    assert (len(phone), len(failed)) == (1, 1)

    good = async_mock_service(hass, "notify", other["action"])
    await entry.runtime_data.async_send_now(message_id_of(hass))
    await hass.async_block_till_done()
    assert (len(phone), len(failed)) == (1, 1)
    assert [call.service for call in good] == [other["action"]]
    assert open_items(hass) == []
    msg = entry.runtime_data.book.get(message_id_of(hass))
    assert msg is not None
    assert msg.state is MessageState.DELIVERED
    assert msg.failed_recipients == []
    assert msg.no_hold is True


async def test_send_now_releases_a_retry_held_for_an_unreadable_rule_entity(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A retry held because the rule's entity cannot be read goes out with send_now.

    While it is held the page shows no next attempt, as under a rule that is on.
    """
    hass.states.async_set("input_boolean.night_mode", "off")
    entry = await setup(hass, make_entry, rules=[night_rule_data()])
    calls = await failing_phone(hass)
    await notify(hass)
    hass.states.async_remove("input_boolean.night_mode")
    await tick(hass, freezer, seconds=61)
    item = open_items(hass)[0]
    assert item["state"] == "retrying"
    assert item["reason"].startswith("mode unknown: input_boolean.night_mode")
    assert item["next_try"] is None
    assert len(calls) == 1

    good = async_mock_service(hass, "notify", PHONE_ACTION)
    await entry.runtime_data.async_send_now(message_id_of(hass))
    await hass.async_block_till_done()
    assert hass.states.get("input_boolean.night_mode") is None
    assert (len(calls), len(good)) == (1, 1)
    assert open_items(hass) == []
    msg = entry.runtime_data.book.get(message_id_of(hass))
    assert msg is not None
    assert msg.no_hold is True
    assert [e["kind"] for e in msg.events] == ["sent_now"]


async def test_held_retry_is_released_by_an_arrival_the_rule_lets_pass(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Arriving again with priority 3, a retry held back goes out at once.

    A waiting message does the same. The retry used to wait for its next
    plan time, up to an hour, although nothing held it any more.
    """

    async def send(priority: int) -> None:
        await hass.services.async_call(
            DOMAIN,
            "send",
            {"title": TITLE, "message": TEXT, "priority": priority, "key": "k"},
            blocking=True,
        )
        await hass.async_block_till_done()

    hass.states.async_set("input_boolean.night_mode", "off")
    await setup(
        hass, make_entry, rules=[night_rule_data()], options={"allow_alarm": True}
    )
    calls = await failing_phone(hass)
    await send(1)
    hass.states.async_set("input_boolean.night_mode", "on")
    await tick(hass, freezer, seconds=61)
    assert open_items(hass)[0]["reason"].startswith("held back: Nacht until")

    good = async_mock_service(hass, "notify", PHONE_ACTION)
    await send(1)  # still held
    assert good == []
    assert open_items(hass)[0]["reason"].startswith("held back: Nacht until")
    await send(3)
    assert (len(calls), len(good)) == (1, 1)
    assert good[0].data["title"] == f"3x {TITLE}"
    assert open_items(hass) == []


async def test_retry_is_held_not_discarded_while_the_rule_entity_is_missing(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    """After a start without the rule's entity a due retry waits for it.

    A rule that discards used to close the cycle right at the start, before
    the entity was loaded. Now the retry is held and follows the state the
    entity shows when it is there.
    """
    hass.states.async_set("input_boolean.night_mode", "off")
    entry = await setup(hass, make_entry, rules=[night_rule_data(effect_1="discard")])
    calls = await failing_phone(hass)
    await notify(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_remove("input_boolean.night_mode")
    freezer.tick(timedelta(seconds=61))
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    item = open_items(hass)[0]
    assert item["state"] == "retrying"
    assert item["reason"].startswith("mode unknown: input_boolean.night_mode")
    assert len(calls) == 1

    good = async_mock_service(hass, "notify", PHONE_ACTION)
    hass.states.async_set("input_boolean.night_mode", "off")
    await hass.async_block_till_done()
    assert len(good) == 1
    assert open_items(hass) == []


@pytest.mark.parametrize("missing", [False, True], ids=["on", "missing"])
async def test_rule_entity_changing_during_the_start_is_seen(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
    missing: bool,
) -> None:
    """The rule's entity changes while the start writes the store: still followed.

    The start used to read the entities once and subscribe to their changes
    only after its first write. A change in between was missed, and the rule
    kept the state it had read until the next change or reload: an entity
    missing at the start left the rule unknown, its repair issue standing
    and the message held, for up to the rule's maximum.
    """
    hass.states.async_set("input_boolean.night_mode", "on")
    entry = await setup(hass, make_entry, rules=[night_rule_data()])
    await notify(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert saved_message(hass_storage) == ("waiting", [])
    if missing:
        hass.states.async_remove("input_boolean.night_mode")

    write = storage.Store._async_write_data
    flipped = False

    async def flipping(store: storage.Store, data: dict[str, Any]) -> None:
        nonlocal flipped
        if store.key == STORAGE_KEY and not flipped:
            flipped = True  # the night ends while the start writes the book
            hass.states.async_set("input_boolean.night_mode", "off")
        await write(store, data)

    with patch.object(storage.Store, "_async_write_data", flipping):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert flipped
    assert len(phone) == 1
    assert open_items(hass) == []
    assert not ir.async_get(hass).async_get_issue(
        DOMAIN, "rule_entity_unavailable_" + rule_id(hass)
    )
    assert entry.runtime_data.rules.verdict(1, dt_util.utcnow()) is None


async def test_failed_start_leaves_no_listener_on_the_rule_entities(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
) -> None:
    """A start that fails after it began to follow the entities lets go of them.

    The entities are followed before the start writes the book. Fails the
    start behind that, nothing of this center may run on: a change of the
    entity used to reach a center that never started, which sent the held
    message and wrote the store.
    """
    hass.states.async_set("input_boolean.night_mode", "on")
    entry = await setup(hass, make_entry, rules=[night_rule_data()])
    await notify(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    before = copy.deepcopy(hass_storage[STORAGE_KEY])
    centers: list[MessageCenter] = []

    def failing(self: MessageCenter, now: Any) -> None:
        centers.append(self)
        raise RuntimeError("boom")

    with patch.object(MessageCenter, "_reevaluate_open", failing):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    [center] = centers
    assert center._unsub_rules is None
    hass.states.async_set("input_boolean.night_mode", "off")
    await hass.async_block_till_done()
    assert phone == []
    assert hass_storage[STORAGE_KEY] == before


async def test_due_retry_goes_out_with_the_start(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],
) -> None:
    """A retry that is due after a restart leaves with the start itself.

    It used to wait for the timer about a second later. The store shows
    "retrying" with the recipient when the push reaches the phone.
    """
    entry = await setup(hass, make_entry)
    calls = await failing_phone(hass)
    await notify(hass)
    assert len(calls) == 1
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    seen: list[tuple[str | None, list[str]]] = []

    async def phone_sees_the_store(call: ServiceCall) -> None:
        seen.append(saved_message(hass_storage))

    hass.services.async_register("notify", PHONE_ACTION, phone_sees_the_store)
    freezer.tick(timedelta(seconds=61))
    with slow_writes():
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert seen == [("retrying", [PHONE_ACTION])]
    assert open_items(hass) == []


async def test_held_retry_follows_the_maximum_duration_of_the_rule(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A retry held back goes out when the rule runs into its maximum duration."""
    hass.states.async_set("input_boolean.night_mode", "off")
    await setup(hass, make_entry, rules=[night_rule_data()])
    calls = await failing_phone(hass)
    await notify(hass)
    hass.states.async_set("input_boolean.night_mode", "on")
    await hass.async_block_till_done()
    await tick(hass, freezer, hours=11)
    assert len(calls) == 1
    good = async_mock_service(hass, "notify", PHONE_ACTION)
    await tick(hass, freezer, hours=1, seconds=1)
    assert len(good) == 1
    assert open_items(hass) == []


async def test_retry_passes_the_rule_with_no_hold_and_priority_3(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Retries of a kind marked 'do not hold' and of priority 3 ignore the rule."""
    hass.states.async_set("input_boolean.night_mode", "off")
    await setup(
        hass,
        make_entry,
        rules=[night_rule_data()],
        kinds=[
            kind_data(no_hold=True),
            kind_data(name="Feuer", title_value="Feuer", priority=3),
        ],
    )
    calls = await failing_phone(hass)
    await notify(hass)
    await notify(hass, title="Feuer in der Küche")
    assert len(calls) == 2

    hass.states.async_set("input_boolean.night_mode", "on")
    await tick(hass, freezer, seconds=61)
    assert len(calls) == 4
    assert [i["reason"][:15] for i in open_items(hass)] == ["delivery failed"] * 2


async def test_retry_ends_when_a_rule_discards(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A rule that discards closes the cycle at the next retry instead of pushing."""
    hass.states.async_set("input_boolean.night_mode", "off")
    entry = await setup(hass, make_entry, rules=[night_rule_data(effect_1="discard")])
    calls = await failing_phone(hass)
    await notify(hass)
    hass.states.async_set("input_boolean.night_mode", "on")
    await tick(hass, freezer, seconds=61)
    assert len(calls) == 1
    assert open_items(hass) == []
    msg = entry.runtime_data.book.get(message_id_of(hass))
    assert msg.state is MessageState.DISCARDED
    assert msg.reason.kind is ReasonKind.RULE_DISCARDED
    assert hass.states.get("sensor.message_center_disturbed").state == "0"


async def test_retry_stops_when_expired(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A message in retrying expires with its kind; then nothing runs or writes.

    It used to stay in retrying with a timer on its passed expiry: a tick
    and a write of the store every second, for up to 24 hours.
    """
    entry = await setup(hass, make_entry, kinds=[kind_data(expires_after=5)])
    center = entry.runtime_data
    calls = await failing_phone(hass)
    await notify(hass)
    assert open_items(hass)[0]["state"] == "retrying"

    await tick(hass, freezer, minutes=5, seconds=1)
    assert len(calls) == 1
    assert open_items(hass) == []
    msg = center.book.get(message_id_of(hass))
    assert msg.state is MessageState.DISCARDED
    assert msg.reason.kind is ReasonKind.EXPIRED
    assert hass.states.get("sensor.message_center_disturbed").state == "0"

    with patch.object(
        center.store, "async_save", wraps=center.store.async_save
    ) as save:
        for _ in range(60):
            freezer.tick(timedelta(seconds=1))
            async_fire_time_changed(hass, dt_util.utcnow())
            await hass.async_block_till_done()
    assert save.call_count == 0
    assert center._timer_at is None
    assert len(calls) == 1


async def test_repeat_of_an_expired_retry_ends_the_cycle_at_the_intake(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A message that expired while retrying ends when it arrives again.

    Nothing is pushed, and the answer of ``send`` names the end state. The
    arrival sets no new expiry: its title matches no kind, only its key.
    """
    await setup(hass, make_entry, kinds=[kind_data(expires_after=5)])
    calls = await failing_phone(hass)
    await notify(hass)
    assert open_items(hass)[0]["state"] == "retrying"

    freezer.tick(timedelta(minutes=5, seconds=1))  # expired, no timer fired yet
    response = await hass.services.async_call(
        DOMAIN,
        "send",
        {"title": "Anderer Titel", "message": TEXT, "key": TITLE},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()
    assert response["state"] == "discarded"
    assert len(calls) == 1
    assert open_items(hass) == []


async def test_push_under_way_arms_no_timer_for_a_passed_expiry(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    """While the first push is out the expiry waits: no tick, no write per second."""
    entry = await setup(hass, make_entry, kinds=[kind_data(expires_after=5)])
    center = entry.runtime_data
    release = asyncio.Event()

    async def slow(call: ServiceCall) -> None:
        await release.wait()

    hass.services.async_register("notify", PHONE_ACTION, slow)
    with (
        no_push_timeout(),
        patch.object(center.store, "async_save", wraps=center.store.async_save) as save,
    ):
        await repeat(hass, TEXT)
        assert open_items(hass)[0]["state"] == "sending"
        writes = save.call_count
        await advance(hass, freezer, minutes=5, seconds=1)
        for _ in range(4):
            await advance(hass, freezer, seconds=1)
        assert save.call_count == writes
        assert center._timer_at is None
        assert open_items(hass)[0]["state"] == "sending"

        release.set()
        await hass.async_block_till_done()
    assert center.book.get(message_id_of(hass)).state is MessageState.DELIVERED


async def test_retry_under_way_at_the_expiry_counts_when_it_arrives(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A retry that is out when the message expires is delivered, not discarded.

    The expiry used to close the cycle under the push: the phone had the
    message, the center showed it as discarded, expired, and fired no event.
    """
    entry = await setup(hass, make_entry, kinds=[kind_data(expires_after=2)])
    center = entry.runtime_data
    events = async_capture_events(hass, EVENT_DELIVERED)
    calls: list[ServiceCall] = []
    release = asyncio.Event()

    async def slow(call: ServiceCall) -> None:
        calls.append(call)
        if len(calls) == 1:
            raise HomeAssistantError("boom")
        await release.wait()

    hass.services.async_register("notify", PHONE_ACTION, slow)
    await notify(hass)
    with (
        no_push_timeout(),
        patch.object(center.store, "async_save", wraps=center.store.async_save) as save,
    ):
        await advance(hass, freezer, seconds=60)
        assert len(calls) == 2  # the retry is out
        writes = save.call_count
        await advance(hass, freezer, seconds=61)  # past the expiry
        for _ in range(4):
            await advance(hass, freezer, seconds=1)
        assert save.call_count == writes
        assert center._timer_at is None
        assert open_items(hass)[0]["state"] == "retrying"

        release.set()
        await hass.async_block_till_done()
    msg = center.book.get(message_id_of(hass))
    assert msg.state is MessageState.DELIVERED
    assert len(events) == 1
    assert len(calls) == 2
    assert open_items(hass) == []


async def test_retry_failing_after_the_expiry_ends_the_cycle(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A retry that fails after the expiry is the last one; then nothing runs."""
    entry = await setup(hass, make_entry, kinds=[kind_data(expires_after=2)])
    center = entry.runtime_data
    calls: list[ServiceCall] = []
    release = asyncio.Event()

    async def slow_failure(call: ServiceCall) -> None:
        calls.append(call)
        if len(calls) > 1:
            await release.wait()
        raise HomeAssistantError("boom")

    hass.services.async_register("notify", PHONE_ACTION, slow_failure)
    await notify(hass)
    with no_push_timeout():
        await advance(hass, freezer, seconds=60)
        await advance(hass, freezer, seconds=61)  # past the expiry
        assert open_items(hass)[0]["state"] == "retrying"
        release.set()
        await hass.async_block_till_done()
        await tick(hass, freezer, seconds=1)
    msg = center.book.get(message_id_of(hass))
    assert msg.state is MessageState.DISCARDED
    assert msg.reason.kind is ReasonKind.EXPIRED
    assert center._timer_at is None
    assert len(calls) == 2


# ----- replacing a delivered push -------------------------------------------


async def repeat(hass: HomeAssistant, message: str) -> None:
    """Let the message arrive again without waiting for its push."""
    await hass.services.async_call(
        "notify", "message_center", {"title": TITLE, "message": message}, blocking=True
    )
    await settle()


async def test_replacements_run_one_at_a_time(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """New text while a replacement is out: one push at a time, the newest last."""
    entry = await setup(hass, make_entry, kinds=[kind_data(spacing=60)])
    book = entry.runtime_data.book
    await notify(hass)
    calls: list[ServiceCall] = []
    release = asyncio.Event()

    async def slow(call: ServiceCall) -> None:
        calls.append(call)
        if len(calls) == 1:
            await release.wait()

    hass.services.async_register("notify", PHONE_ACTION, slow)
    await repeat(hass, "v2")
    await repeat(hass, "v3")
    assert [call.data["message"] for call in calls] == ["v2"]
    msg = book.get(message_id_of(hass))
    status = msg.recipients[PHONE_ACTION]
    assert (status.delivered_revision, status.delivered_count) == (1, 1)

    release.set()
    await hass.async_block_till_done()
    assert [call.data["message"] for call in calls] == ["v2", "v3"]
    assert calls[1].data["title"] == f"3x {TITLE}"
    assert (status.delivered_revision, status.delivered_count) == (3, 3)
    assert book.recipients_to_replace(msg) == []


async def test_failed_replacement_leaves_the_lag_visible(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Only what reached the phone is confirmed; a failed replacement is not retried."""
    entry = await setup(hass, make_entry, kinds=[kind_data(spacing=60)])
    book = entry.runtime_data.book
    await notify(hass)
    calls: list[ServiceCall] = []
    release = asyncio.Event()

    async def slow_then_failing(call: ServiceCall) -> None:
        calls.append(call)
        if len(calls) == 1:
            await release.wait()
            return
        raise HomeAssistantError("boom")

    hass.services.async_register("notify", PHONE_ACTION, slow_then_failing)
    await repeat(hass, "v2")
    await repeat(hass, "v3")
    release.set()
    await hass.async_block_till_done()
    assert [call.data["message"] for call in calls] == ["v2", "v3"]
    msg = book.get(message_id_of(hass))
    status = msg.recipients[PHONE_ACTION]
    assert (status.delivered_revision, status.delivered_count) == (2, 2)
    assert book.recipients_to_replace(msg) == [PHONE_ACTION]

    good = async_mock_service(hass, "notify", PHONE_ACTION)
    await notify(hass, message="v3")  # the next arrival makes up for it
    assert [call.data["title"] for call in good] == [f"4x {TITLE}"]
    assert book.recipients_to_replace(msg) == []


async def test_new_text_during_the_first_push_follows_as_one_replacement(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Text changed while the first push is out: the new text follows, once.

    What the first push carried is noted for the recipient. The replacement
    leaves only when the result of the first push is saved.
    """
    book = center_entry.runtime_data.book
    calls: list[ServiceCall] = []
    seen: list[str | None] = []
    release = asyncio.Event()

    async def slow(call: ServiceCall) -> None:
        calls.append(call)
        seen.append(saved_message(hass_storage)[0])
        if len(calls) == 1:
            await release.wait()

    hass.services.async_register("notify", PHONE_ACTION, slow)
    with slow_writes():
        await repeat(hass, "v1")
        await repeat(hass, "v2")
        assert [call.data["message"] for call in calls] == ["v1"]
        msg = book.get(message_id_of(hass))
        status = msg.recipients[PHONE_ACTION]
        assert msg.state is MessageState.SENDING
        assert status.delivered_revision is None

        release.set()
        await hass.async_block_till_done()
    assert [call.data["message"] for call in calls] == ["v1", "v2"]
    assert calls[1].data["title"] == f"2x {TITLE}"
    assert seen == ["sending", "delivered"]
    assert (status.delivered_revision, status.delivered_count) == (2, 2)
    assert book.recipients_to_replace(msg) == []


async def test_new_text_during_a_retry_follows_as_one_replacement(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The same while a retry is out: it delivers the old text, the new one follows."""
    book = center_entry.runtime_data.book
    calls: list[ServiceCall] = []
    release = asyncio.Event()

    async def slow(call: ServiceCall) -> None:
        calls.append(call)
        if len(calls) == 1:
            raise HomeAssistantError("boom")
        if len(calls) == 2:
            await release.wait()

    hass.services.async_register("notify", PHONE_ACTION, slow)
    await notify(hass, message="v1")
    with no_push_timeout():
        await advance(hass, freezer, seconds=60)
        assert len(calls) == 2  # the retry is out
        await repeat(hass, "v2")
        assert len(calls) == 2
        release.set()
        await hass.async_block_till_done()
    assert [call.data["message"] for call in calls] == ["v1", "v1", "v2"]
    assert calls[2].data["title"] == f"2x {TITLE}"
    msg = book.get(message_id_of(hass))
    status = msg.recipients[PHONE_ACTION]
    assert msg.state is MessageState.DELIVERED
    assert (status.delivered_revision, status.delivered_count) == (2, 2)
    assert book.recipients_to_replace(msg) == []


async def test_hide_titles_keeps_the_title_out_of_everything_published(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """With the option nothing the center publishes shows the title.

    The id is opaque, so attributes of open and disturbed, the events, the
    event entity, the push tag and the buttons carry none of it. The push
    itself shows the title, of course.
    """
    hass.states.async_set("input_boolean.night_mode", "on")
    captured = {
        event_type: async_capture_events(hass, event_type)
        for event_type in (EVENT_DELIVERED, EVENT_SNOOZED, EVENT_DISCARDED)
    }
    await setup(
        hass, make_entry, rules=[night_rule_data()], options={"hide_titles": True}
    )
    await notify(hass)
    assert TITLE not in json.dumps(open_items(hass), ensure_ascii=False)
    assert open_items(hass)[0]["title"] == "unknown/unknown"

    hass.states.async_set("input_boolean.night_mode", "off")
    await hass.async_block_till_done()
    assert len(phone) == 1
    assert phone[0].data["title"] == TITLE
    data = phone[0].data["data"]
    assert TITLE not in data["tag"]
    assert all(TITLE not in action["action"] for action in data["actions"])
    for entity_id in (
        "event.message_center_delivered",
        "sensor.message_center_last_delivery",
    ):
        attributes = hass.states.get(entity_id).attributes
        assert TITLE not in json.dumps(attributes, ensure_ascii=False), entity_id

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
        assert TITLE not in json.dumps(events[0].data, ensure_ascii=False), event_type

    await failing_phone(hass)
    await notify(hass, title="Feuchte: Keller")
    disturbed = hass.states.get("sensor.message_center_disturbed")
    assert disturbed.state == "1"
    assert "Feuchte: Keller" not in json.dumps(disturbed.attributes, ensure_ascii=False)


async def test_unexpected_push_error_in_the_cycle_logs_no_content(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A push that raises past the delivery layer: class and stack, no text."""
    caplog.set_level(logging.INFO, logger="custom_components.message_center")

    async def broken(*args: Any, **kwargs: Any) -> None:
        raise ValueError(f"bad {TITLE} {TEXT}")

    with patch("custom_components.message_center.center.async_push", broken):
        await notify(hass)
    status = center_entry.runtime_data.book.get(message_id_of(hass)).recipients
    assert status[PHONE_ACTION].last_error == "ValueError"
    assert f"Unexpected error pushing to {PHONE_ACTION}: ValueError" in caplog.text
    assert 'File "' in caplog.text
    assert TITLE not in caplog.text
    assert TEXT not in caplog.text
