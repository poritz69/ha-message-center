"""Tests for faults: unreadable or unwritable store, restart, failing fallback."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import copy
from datetime import UTC, datetime, timedelta
import logging
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import issue_registry as ir, storage
from homeassistant.util import dt as dt_util
from homeassistant.util.file import WriteError
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.message_center.center import NotReadyError
from custom_components.message_center.const import (
    DOMAIN,
    EVENT_FORWARDED,
    EVENT_SNOOZED,
    STORE_RETRY_INTERVAL,
)
from custom_components.message_center.models import MessageState, ReasonKind
from custom_components.message_center.store import (
    HISTORY_KEY,
    STORAGE_KEY,
    StoreNotWritableError,
)

from .conftest import (
    PHONE_ACTION,
    failing_writes,
    kind_data,
    night_rule_data,
    store_0_10_5,
    stored,
)
from .test_delivery import setup, tick
from .test_diagnostics_and_blueprint import blueprint_script, clean_blueprint, run
from .test_services import TEXT, TITLE, message_id_of, notify, open_items

__all__ = ["clean_blueprint"]  # autouse fixture for the blueprint tests below

RETRY = STORE_RETRY_INTERVAL.total_seconds()
# a message as 0.10.5 wrote it (no id), for stores of version 2 made by hand
OLD_MESSAGE = store_0_10_5(datetime(2026, 1, 1, tzinfo=UTC))["messages"][
    "unknown:Lüften: Bad"
]
OPAQUE = "0123456789abcdef"


@pytest.mark.parametrize(
    ("key", "data", "version"),
    [
        (STORAGE_KEY, {"messages": "not a mapping"}, 1),
        (STORAGE_KEY, {"messages": {}, "saved_at": "yesterday"}, 1),
        (STORAGE_KEY, {"messages": {}, "pending_history": [{"origin": "x.y"}]}, 1),
        (STORAGE_KEY, {"id_salt": "s", "messages": {}, "saved_at": "yesterday"}, 2),
        (STORAGE_KEY, {"id_salt": "s", "messages": {}, "pending_history": [{}]}, 2),
        (STORAGE_KEY, {"messages": {}, "pending_history": []}, 2),  # no salt
        (STORAGE_KEY, {"id_salt": "", "messages": {}}, 2),  # empty salt
        (STORAGE_KEY, {"id_salt": "s", "messages": {OPAQUE: OLD_MESSAGE}}, 2),  # no id
        (
            STORAGE_KEY,
            {"id_salt": "s", "messages": {OPAQUE: {**OLD_MESSAGE, "id": OPAQUE}}},
            2,
        ),  # an id that is not the one of origin and key under this salt
        (
            STORAGE_KEY,
            {"id_salt": "s", "messages": {}, "pending_history": [OLD_MESSAGE]},
            2,
        ),  # a pending end state without an id
        (HISTORY_KEY, {"entries": 5}, 1),
        (HISTORY_KEY, {"entries": [{"origin": "x.y", "key": "k"}]}, 1),
    ],
)
async def test_unreadable_store_gives_a_reason_and_retries(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
    key: str,
    data: dict[str, Any],
    version: int,
) -> None:
    """A store with an unexpected format: not ready, with a reason, and a retry.

    A file of version 1 is read through the migration, one of version 2 as
    it is: a message or pending end state must carry the id its origin and
    key have under the salt, else it would live on with an id nothing finds.
    A broken history entry counts as well.
    """
    hass_storage[key] = stored(key, data, version=version)
    entry = make_entry()
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.error_reason_translation_key == "store_not_readable"
    assert key in entry.error_reason_translation_placeholders["error"]
    with pytest.raises(ServiceValidationError) as err:
        await notify(hass)
    assert err.value.translation_key == "not_ready"

    del hass_storage[key]
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    await notify(hass)
    assert len(phone) == 1


async def test_store_from_before_the_newer_fields_loads(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
) -> None:
    """A store of 0.10.5 starts, is migrated to version 2 and carried on.

    The file is a fixed one in the format of 0.10.5: one message delivered,
    one held by a rule that no longer exists. After the start every key is
    an opaque id, the pair noted as "new" is still there, and the store is
    written in version 2.
    """
    old = store_0_10_5(dt_util.utcnow())
    hass_storage[STORAGE_KEY] = stored(STORAGE_KEY, old)
    hass_storage[HISTORY_KEY] = stored(HISTORY_KEY, {"entries": []})

    await setup(hass, make_entry)
    assert len(phone) == 1  # the waiting message went out
    assert phone[0].data["title"] == TITLE
    assert hass_storage[STORAGE_KEY]["version"] == 2
    data = hass_storage[STORAGE_KEY]["data"]
    assert [m["state"] for m in data["messages"].values()] == ["delivered"] * 2
    assert data["messages"][message_id_of(hass)]["state"] == "delivered"
    assert list(data["spacing"]) == [
        message_id_of(hass, "Lüften: Bad"),
        message_id_of(hass),
    ]
    assert not any(":" in key for key in [*data["messages"], *data["spacing"]])
    assert all(raw["id"] == key for key, raw in data["messages"].items())
    assert len(data["id_salt"]) == 32
    assert data["extra"] == old["extra"]  # the pair noted as "new" is still there
    assert data["pending_history"] == []
    assert data["write_id"]
    assert hass.states.get("binary_sensor.message_center_ready").state == "on"
    assert phone[0].data["data"]["tag"] == message_id_of(hass)


async def test_migrated_store_keeps_the_spacing_and_understands_old_buttons(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
) -> None:
    """After the update a repeat within the spacing is bundled, not pushed anew.

    The spacing came over under the new id. A button on a push delivered
    before the update carries the old id and still works; the actions take
    the new id only.
    """
    hass_storage[STORAGE_KEY] = stored(STORAGE_KEY, store_0_10_5(dt_util.utcnow()))
    entry = await setup(hass, make_entry, kinds=[kind_data(spacing=360)])
    center = entry.runtime_data
    assert len(phone) == 1

    await notify(hass, title="Lüften: Bad", message="Fenster öffnen.")
    assert [call.data["title"] for call in phone] == [TITLE, "2x Lüften: Bad"]
    bundled = center.book.get(message_id_of(hass, "Lüften: Bad"))
    assert (bundled.generation, bundled.count) == (1, 2)
    assert bundled.state is MessageState.DELIVERED
    assert len(center.book.messages) == 2

    snoozed = async_capture_events(hass, EVENT_SNOOZED)
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": f"message_center_snooze|30|unknown:{TITLE}"},
    )
    await hass.async_block_till_done()
    msg = center.book.get(message_id_of(hass))
    assert msg.state is MessageState.WAITING
    assert msg.reason.kind is ReasonKind.SNOOZED
    assert [e.data["message_id"] for e in snoozed] == [message_id_of(hass)]
    assert TITLE not in snoozed[0].data["message_id"]

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "snooze",
            {"message_id": f"unknown:{TITLE}", "minutes": 5},
            blocking=True,
        )
    assert err.value.translation_key == "not_found"


async def test_history_entries_without_an_id_get_it_from_the_running_center(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
    hass_admin_user: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Entries from before the id, on disk or pending in version 1, show one.

    A history entry 0.10.5 wrote has no id: ``list`` shows it under the id
    its origin and key have in the running book, and "delivered today"
    counts it. A pending end state in a store of version 1 gets its id in
    the migration and reaches the history with it.
    """
    freezer.move_to("2026-03-04 12:00:00+00:00")
    now = dt_util.utcnow()
    old = store_0_10_5(now)
    ended = old["messages"]["unknown:Lüften: Bad"]  # delivered: an end state
    on_disk = {**ended, "key": "Lüften: Küche", "title": "Lüften: Küche"}
    pending = {**ended, "key": "Lüften: Flur", "title": "Lüften: Flur"}
    old["pending_history"] = [pending]
    hass_storage[STORAGE_KEY] = stored(STORAGE_KEY, old)
    hass_storage[HISTORY_KEY] = stored(HISTORY_KEY, {"entries": [on_disk]})

    entry = await setup(hass, make_entry)
    center = entry.runtime_data
    ids = [message_id_of(hass, key) for key in ("Lüften: Küche", "Lüften: Flur")]
    assert all(len(mid) == 16 and ":" not in mid for mid in ids)
    written = hass_storage[HISTORY_KEY]["data"]["entries"]
    assert [e.get("id") for e in written] == [None, ids[1]]
    assert written[0] == on_disk
    assert hass_storage[STORAGE_KEY]["data"]["pending_history"] == []
    response = await hass.services.async_call(
        DOMAIN,
        "list",
        {"include_history": True},
        blocking=True,
        return_response=True,
        context=Context(user_id=hass_admin_user.id),
    )
    history = response["history"]
    assert [m["message_id"] for m in history] == ids
    assert [m["title"] for m in history] == ["Lüften: Küche", "Lüften: Flur"]
    assert center.delivered_today == 4  # two in the book, two in the history


async def test_store_read_error_is_not_ready(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """A store that cannot be read at all behaves the same way."""
    entry = make_entry()
    entry.add_to_hass(hass)
    with patch(
        "custom_components.message_center.store._VersionedStore.async_load",
        side_effect=HomeAssistantError("disk"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.error_reason_translation_key == "store_not_readable"


async def test_unwritable_store_rejects_and_is_logged_once(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Store not writable: not ready, repair issue, one log line, recovery."""
    center = center_entry.runtime_data
    real_save = center.store.async_save
    center.store.async_save = AsyncMock(side_effect=StoreNotWritableError("disk full"))
    caplog.set_level(logging.INFO, logger="custom_components.message_center")

    with pytest.raises(ServiceValidationError) as err:
        await notify(hass)
    assert err.value.translation_key == "not_ready"
    await hass.async_block_till_done()
    assert phone == []
    assert open_items(hass) == []  # nothing was accepted
    ready = hass.states.get("binary_sensor.message_center_ready")
    assert ready.state == "off"
    assert ready.attributes["reason"] == "store"
    assert ir.async_get(hass).async_get_issue(DOMAIN, "store_not_writable")

    for _ in range(3):  # housekeeping and timers keep trying to write
        await center._commit(dt_util.utcnow(), raise_error=False)
    with pytest.raises(ServiceValidationError):
        await notify(hass)
    assert caplog.text.count("Message store not writable") == 1

    center.store.async_save = real_save
    await center._commit(dt_util.utcnow(), raise_error=False)
    center._notify()  # every caller of _commit does this
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.message_center_ready").state == "on"
    assert not ir.async_get(hass).async_get_issue(DOMAIN, "store_not_writable")
    assert caplog.text.count("Message store writable again") == 1
    await notify(hass)
    assert len(phone) == 1


def assert_ready(hass: HomeAssistant, *, ready: bool) -> None:
    """Check the entity "Ready", its reason and the repair issue of the store."""
    state = hass.states.get("binary_sensor.message_center_ready")
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "store_not_writable")
    if ready:
        assert state.state == "on"
        assert issue is None
    else:
        assert state.state == "off"
        assert state.attributes["reason"] == "store"
        assert issue is not None


async def test_swallowed_write_error_rejects_and_recovers(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """A write error that Home Assistant only logs: rejected, nothing sent.

    Once the store can be written again the next message is taken, without
    waiting for a timer or the hourly round.
    """
    center = center_entry.runtime_data
    before = copy.deepcopy(hass_storage[STORAGE_KEY]["data"])
    with failing_writes(STORAGE_KEY):
        with pytest.raises(ServiceValidationError) as err:
            await notify(hass)
        assert err.value.translation_key == "not_ready"
        await hass.async_block_till_done()
        assert phone == []
        assert open_items(hass) == []  # nothing was accepted
        assert center.book.messages == {}
        assert hass.states.get("sensor.message_center_new").state == "0"
        assert_ready(hass, ready=False)

        with pytest.raises(ServiceValidationError) as err:  # tried and failed again
            await notify(hass)
        assert err.value.translation_key == "not_ready"
        assert phone == []
    assert hass_storage[STORAGE_KEY]["data"] == before

    await notify(hass)
    assert len(phone) == 1
    assert_ready(hass, ready=True)
    assert list(hass_storage[STORAGE_KEY]["data"]["messages"]) == [message_id_of(hass)]


async def test_unwritable_store_at_start_is_not_ready(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Ready only once the store was written; the next message tries again."""
    entry = make_entry()
    entry.add_to_hass(hass)
    with failing_writes(STORAGE_KEY):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert_ready(hass, ready=False)
        with pytest.raises(ServiceValidationError) as err:
            await notify(hass)
        assert err.value.translation_key == "not_ready"

    await notify(hass)
    assert len(phone) == 1
    assert_ready(hass, ready=True)


async def test_nothing_accepted_is_lost_over_a_restart(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """What was answered with accepted is there after a restart, and nothing else."""
    hass.states.async_set("input_boolean.night_mode", "on")
    entry = await setup(hass, make_entry, rules=[night_rule_data()])
    await notify(hass, title="Erste")
    with failing_writes(STORAGE_KEY), pytest.raises(ServiceValidationError):
        await notify(hass, title="Zweite")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert [item["title"] for item in open_items(hass)] == ["Erste"]
    assert phone == []


async def test_rejected_repeat_leaves_the_message_as_it_was(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """A repeat that cannot be stored is taken back from the message it changed.

    Both for a delivered message, where the repeat would start a new
    generation, and for one still waiting, where it would count and update.
    """
    hass.states.async_set("input_boolean.night_mode", "off")
    entry = await setup(hass, make_entry, rules=[night_rule_data()])
    center = entry.runtime_data
    await notify(hass)
    hass.states.async_set("input_boolean.night_mode", "on")
    await hass.async_block_till_done()
    await notify(hass, title="Zweite")
    delivered, waiting = center.book.messages.values()
    assert delivered.state is MessageState.DELIVERED
    assert waiting.state is MessageState.WAITING
    before = [delivered.to_dict(), waiting.to_dict()]
    spacing = dict(center.book.spacing)

    with failing_writes(STORAGE_KEY):
        for title in (TITLE, "Zweite"):
            with pytest.raises(ServiceValidationError) as err:
                await notify(hass, title=title, message="Neuer Text")
            assert err.value.translation_key == "not_ready"
    await hass.async_block_till_done()
    assert center.book.messages[message_id_of(hass)] is delivered
    assert center.book.messages[message_id_of(hass, "Zweite")] is waiting
    assert len(center.book.messages) == 2
    assert [delivered.to_dict(), waiting.to_dict()] == before
    assert center.book.history == []
    assert center.book.spacing == spacing
    assert [u["count"] for u in center.unknown_items()] == [1, 1]
    assert hass.states.get("sensor.message_center_new").state == "2"
    assert len(phone) == 1


async def test_rejected_repeat_sends_nothing_and_reserves_nothing(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """A bundled repeat that cannot be stored does not replace the push.

    Its recipient is given back, so the next repeat replaces as usual.
    """
    entry = await setup(hass, make_entry, kinds=[kind_data(spacing=60)])
    center = entry.runtime_data
    await notify(hass)
    status = center.book.get(message_id_of(hass)).recipients[PHONE_ACTION]

    with failing_writes(STORAGE_KEY), pytest.raises(ServiceValidationError) as err:
        await notify(hass, message="Neuer Text")
    assert err.value.translation_key == "not_ready"
    await hass.async_block_till_done()
    assert len(phone) == 1
    assert center._pending == []
    assert not status.in_flight
    assert (status.delivered_revision, status.delivered_count) == (1, 1)

    await notify(hass, message="Neuer Text")
    assert [call.data["title"] for call in phone] == [TITLE, f"2x {TITLE}"]
    assert (status.delivered_revision, status.delivered_count) == (2, 2)


async def test_running_push_survives_the_rollback_of_another_message(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """Taking back a rejected message leaves a push in flight attached to the book."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow(call: ServiceCall) -> None:
        started.set()
        await release.wait()

    hass.services.async_register("notify", PHONE_ACTION, slow)
    center = center_entry.runtime_data
    await hass.services.async_call(
        "notify", "message_center", {"title": "Erste", "message": TEXT}, blocking=True
    )
    (first,) = center.open_messages()
    assert first.state is MessageState.SENDING
    async with asyncio.timeout(2):
        await started.wait()  # the push is on its way and not yet answered

    with failing_writes(STORAGE_KEY), pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            "notify",
            "message_center",
            {"title": "Zweite", "message": TEXT},
            blocking=True,
        )
    assert err.value.translation_key == "not_ready"
    release.set()
    await hass.async_block_till_done()
    assert first.state is MessageState.DELIVERED
    assert [msg is first for msg in center.book.messages.values()] == [True]
    assert open_items(hass) == []
    assert [u["title"] for u in center.unknown_items()] == ["Erste"]
    assert_ready(hass, ready=True)  # the push's own write went through


async def test_rejected_intake_leaves_the_reserved_push_of_another_message(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Taking back a rejected message gives back its own reserved push only.

    A push of another message can be left reserved, here by a "send now"
    that is cancelled during its write. It used to be given back with the
    rejected one and its message stayed in sending without a push. Now the
    next call that gets through starts it.
    """
    hass.states.async_set("input_boolean.night_mode", "on")
    entry = await setup(hass, make_entry, rules=[night_rule_data()])
    center = entry.runtime_data
    await notify(hass)
    write = storage.Store._async_write_data
    started = asyncio.Event()
    release = asyncio.Event()

    async def hanging(store: storage.Store, data: dict[str, Any]) -> None:
        if store.key == STORAGE_KEY:
            started.set()
            await release.wait()
        await write(store, data)

    with patch.object(storage.Store, "_async_write_data", hanging):
        task = hass.async_create_task(center.async_send_now(message_id_of(hass)))
        async with asyncio.timeout(2):
            await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        release.set()
        await hass.async_block_till_done()
    status = center.book.get(message_id_of(hass)).recipients[PHONE_ACTION]
    assert phone == []
    assert len(center._pending) == 1

    with failing_writes(STORAGE_KEY), pytest.raises(ServiceValidationError):
        await notify(hass, title="Zweite")
    assert len(center._pending) == 1
    assert status.in_flight

    await notify(hass, title="Dritte")  # held by the rule; its write gets through
    assert [call.data["title"] for call in phone] == [TITLE]
    assert center._pending == []
    assert center.book.get(message_id_of(hass)).state is MessageState.DELIVERED


async def leave_a_reserved_push(hass: HomeAssistant, center: Any) -> None:
    """Cancel a "send now" of the test message while its write hangs.

    Its push stays reserved in ``center._pending`` and the message in sending,
    as a shutdown during the write would leave it; the write lands after all.
    """
    write = storage.Store._async_write_data
    started = asyncio.Event()
    release = asyncio.Event()

    async def hanging(store: storage.Store, data: dict[str, Any]) -> None:
        if store.key == STORAGE_KEY:
            started.set()
            await release.wait()
        await write(store, data)

    with patch.object(storage.Store, "_async_write_data", hanging):
        task = hass.async_create_task(center.async_send_now(message_id_of(hass)))
        async with asyncio.timeout(2):
            await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        release.set()
        await hass.async_block_till_done()
    assert len(center._pending) == 1
    assert center.book.get(message_id_of(hass)).state is MessageState.SENDING


async def test_rejected_repeat_leaves_the_reserved_push_of_the_same_message(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Taking back a rejected repeat gives back only what that intake reserved.

    A push of the message itself can be left reserved, by a "send now" that
    is cancelled during its write. The repeat arriving while the store
    cannot be written used to give that push back as well: the message
    stayed in sending with nothing reserved and no push until a restart.
    """
    hass.states.async_set("input_boolean.night_mode", "on")
    entry = await setup(hass, make_entry, rules=[night_rule_data()])
    center = entry.runtime_data
    await notify(hass)
    await leave_a_reserved_push(hass, center)
    msg = center.book.get(message_id_of(hass))
    status = msg.recipients[PHONE_ACTION]
    assert phone == []

    with failing_writes(STORAGE_KEY), pytest.raises(ServiceValidationError):
        await notify(hass)  # the same message again
    assert len(center._pending) == 1
    assert status.in_flight
    assert (msg.state, msg.count) == (MessageState.SENDING, 1)

    await notify(hass, title="Zweite")  # held by the rule; its write gets through
    assert [call.data["title"] for call in phone] == [TITLE]
    assert center._pending == []
    assert msg.state is MessageState.DELIVERED


async def test_callers_queued_behind_the_stop_are_rejected(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """A caller waiting for the lock when the center stops gets "not ready".

    It fetched the center before the stop and waits for the lock behind
    ``async_stop``. The stopped center used to run its intake or command
    through: accepted into a book nobody writes any more, the push given
    back, the event fired, and "accepted" returned, so the sender held a
    message for accepted that was nowhere.
    """
    center = center_entry.runtime_data
    await notify(hass)
    mid = message_id_of(hass)
    events = async_capture_events(hass, EVENT_SNOOZED)
    before = copy.deepcopy(hass_storage[STORAGE_KEY])
    async with center._lock:
        # queued in this order: the stop first, the callers behind it
        stop = hass.async_create_task(center.async_stop())
        intake = hass.async_create_task(
            center.async_intake(title="Zweite", message=TEXT, context=Context())
        )
        snooze = hass.async_create_task(center.async_snooze(mid, 30, source="page"))
    await stop
    with pytest.raises(NotReadyError):
        await intake
    with pytest.raises(NotReadyError):
        await snooze
    assert len(phone) == 1
    assert events == []
    assert list(center.book.messages) == [mid]
    assert center.book.get(mid).snoozed_until is None
    assert center._pending == []
    assert hass_storage[STORAGE_KEY] == before


async def test_commands_try_the_store_again(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Discard, snooze and forward do not wait for a timer either."""
    hass.states.async_set("input_boolean.night_mode", "on")
    entry = await setup(hass, make_entry, rules=[night_rule_data()])
    center = entry.runtime_data
    await notify(hass)
    await notify(hass, title="Zweite")
    (second,) = (m.id for m in center.open_messages() if m.title == "Zweite")

    async def rejected_then_done(command: Callable[[], Awaitable[Any]]) -> Any:
        with failing_writes(STORAGE_KEY):
            await center._commit(dt_util.utcnow(), raise_error=False)  # e.g. a timer
            assert not center.ready
            with pytest.raises(NotReadyError):
                await command()
        result = await command()
        assert center.ready
        return result

    assert await rejected_then_done(lambda: center.async_discard(message_id=second))
    await rejected_then_done(lambda: center.async_snooze(message_id_of(hass), 5))
    await rejected_then_done(
        lambda: center.async_forward(message_id_of(hass), None, Context())
    )
    assert phone == []
    assert_ready(hass, ready=True)


async def test_send_now_delivers_although_the_store_cannot_be_written(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """The page's "send now" tries the store and sends either way.

    Outside the intake delivery comes first, also when the write that
    "send now" tries itself fails. Not ready for another reason still rejects.
    """
    hass.states.async_set("input_boolean.night_mode", "on")
    entry = await setup(hass, make_entry, rules=[night_rule_data()])
    center = entry.runtime_data
    await notify(hass)
    await notify(hass, title="Zweite")

    with failing_writes(STORAGE_KEY):
        await center._commit(dt_util.utcnow(), raise_error=False)  # e.g. a timer
        assert not center.ready
        await center.async_send_now(message_id_of(hass))
        await hass.async_block_till_done()
        assert [call.data["title"] for call in phone] == [TITLE]
        assert [item["title"] for item in open_items(hass)] == ["Zweite"]
        assert_ready(hass, ready=False)

    await center.async_send_now(message_id_of(hass, "Zweite"))  # writable again
    await hass.async_block_till_done()
    assert len(phone) == 2
    assert_ready(hass, ready=True)

    await notify(hass, title="Dritte")
    center.ready, center.ready_reason = False, "starting"
    with pytest.raises(NotReadyError):
        await center.async_send_now(message_id_of(hass, "Dritte"))
    assert len(phone) == 2


async def test_center_tries_the_store_again_by_itself(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Not ready because of the store heals without anybody calling.

    Senders using the blueprint do not call while "Ready" is off, so no call
    of theirs can try the store. The center writes again on a timer.
    """
    await blueprint_script(hass, PHONE_ACTION)
    with failing_writes(STORAGE_KEY):
        with pytest.raises(ServiceValidationError):
            await notify(hass)
        assert_ready(hass, ready=False)
        await tick(hass, freezer, seconds=RETRY)  # tried, still not writable
        assert_ready(hass, ready=False)
    assert (await run(hass))["result"] == "fallback"
    assert_ready(hass, ready=False)

    await tick(hass, freezer, seconds=RETRY)
    assert_ready(hass, ready=True)
    assert (await run(hass))["result"] == "accepted"
    assert [call.data["title"] for call in phone] == ["Waschmaschine"] * 2


async def test_hanging_store_is_not_tried_on_every_call(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """After a write that ran into the time limit, calls are rejected at once.

    Trying on every call would make each sender wait for the limit while the
    disk hangs. The timer tries again, and the write that hung cannot land
    on top of a later one.
    """
    write = storage.Store._async_write_data
    release = asyncio.Event()
    attempts = 0

    async def hanging(store: storage.Store, data: dict[str, Any]) -> None:
        nonlocal attempts
        attempts += 1
        await release.wait()
        await write(store, data)

    with patch.object(storage.Store, "_async_write_data", hanging):
        with (
            patch("custom_components.message_center.store.SAVE_TIMEOUT", 0.01),
            pytest.raises(ServiceValidationError),
        ):
            await notify(hass)
        assert attempts == 1
        assert_ready(hass, ready=False)
        for _ in range(3):
            with pytest.raises(ServiceValidationError) as err:
                async with asyncio.timeout(1):
                    await notify(hass)
            assert err.value.translation_key == "not_ready"
        assert attempts == 1
        assert phone == []

        release.set()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=RETRY))
        await hass.async_block_till_done()
    assert_ready(hass, ready=True)
    assert hass_storage[STORAGE_KEY]["data"]["messages"] == {}
    await notify(hass)
    assert len(phone) == 1


async def test_burst_while_unwritable_costs_one_write_attempt(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """Calls that wait while another one tries the store take its result."""
    with failing_writes(STORAGE_KEY), pytest.raises(ServiceValidationError):
        await notify(hass)
    attempts = 0
    release = asyncio.Event()

    async def slow_failure(store: storage.Store, data: dict[str, Any]) -> None:
        nonlocal attempts
        attempts += 1
        await release.wait()
        raise WriteError("No space left on device")

    with patch.object(storage.Store, "_async_write_data", slow_failure):
        burst = [
            hass.async_create_task(
                hass.services.async_call(
                    "notify",
                    "message_center",
                    {"title": TITLE, "message": TEXT},
                    blocking=True,
                )
            )
            for _ in range(3)
        ]
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(*burst, return_exceptions=True)
    assert [getattr(r, "translation_key", r) for r in results] == ["not_ready"] * 3
    assert attempts == 1
    assert phone == []


async def test_write_error_outside_the_intake_still_delivers(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """A rule ends while the store cannot be written: the push goes out anyway.

    Outside the intake delivery comes first; the center shows the fault.
    """
    hass.states.async_set("input_boolean.night_mode", "on")
    await setup(hass, make_entry, rules=[night_rule_data()])
    await notify(hass)
    with failing_writes(STORAGE_KEY):
        hass.states.async_set("input_boolean.night_mode", "off")
        await hass.async_block_till_done()
        assert len(phone) == 1
        assert open_items(hass) == []
        assert_ready(hass, ready=False)

    await notify(hass, title="Zweite")
    assert len(phone) == 2
    assert_ready(hass, ready=True)


async def test_write_error_does_not_stop_a_due_retry(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A retry is due while the store cannot be written: it goes out anyway."""
    calls: list[ServiceCall] = []

    async def failing(call: ServiceCall) -> None:
        calls.append(call)
        raise HomeAssistantError("boom")

    hass.services.async_register("notify", PHONE_ACTION, failing)
    await notify(hass)
    assert len(calls) == 1
    with failing_writes(STORAGE_KEY):
        await tick(hass, freezer, seconds=61)
        assert len(calls) == 2
        assert_ready(hass, ready=False)


async def test_write_error_at_start_still_delivers(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
) -> None:
    """A message waiting in the store goes out at the start, written or not."""
    hass_storage[STORAGE_KEY] = stored(STORAGE_KEY, store_0_10_5(dt_util.utcnow()))
    before = copy.deepcopy(hass_storage[STORAGE_KEY])
    with failing_writes(STORAGE_KEY):
        entry = await setup(hass, make_entry)
        assert entry.state is ConfigEntryState.LOADED
        assert [call.data["title"] for call in phone] == [TITLE]
        assert open_items(hass) == []
        assert_ready(hass, ready=False)
    assert hass_storage[STORAGE_KEY] == before


async def test_pending_history_survives_unload_and_setup(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
) -> None:
    """A generation replaced by a repeat is not lost before the hourly round."""
    entry = await setup(hass, make_entry)
    await notify(hass)
    await notify(hass, message="Zweite Runde")  # no spacing: a new generation
    assert len(phone) == 2
    # already on disk with the working store, so a crash right now loses nothing
    pending = hass_storage[STORAGE_KEY]["data"]["pending_history"]
    assert [e["message"] for e in pending] == [TEXT]
    assert HISTORY_KEY not in hass_storage

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    written = hass_storage[HISTORY_KEY]["data"]["entries"]
    assert [e["message"] for e in written] == [TEXT]
    assert hass_storage[STORAGE_KEY]["data"]["pending_history"] == []

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    center = entry.runtime_data
    assert [e["message"] for e in center.history.entries] == [TEXT]
    assert center.book.history == []


@pytest.mark.parametrize("history_written", [False, True])
async def test_pending_history_reaches_the_history_once_after_a_crash(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    history_written: bool,
) -> None:
    """No orderly stop: the pending entry is loaded again and handed over once.

    Also when the crash came between the write of the history and the write
    of the working store, so that the entry is in both files. It is handed
    over at the start, so the history shows it and "delivered today" counts
    it without waiting for the hourly round.
    """
    entry = await setup(hass, make_entry)
    await notify(hass)
    await notify(hass, message="Zweite Runde")
    crashed = copy.deepcopy(hass_storage[STORAGE_KEY])
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    hass_storage[STORAGE_KEY] = crashed
    if not history_written:
        del hass_storage[HISTORY_KEY]

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    center = entry.runtime_data
    assert center.book.history == []
    assert [e["message"] for e in center.history.entries] == [TEXT]
    assert center.delivered_today == 2
    written = hass_storage[HISTORY_KEY]["data"]["entries"]
    assert [e["message"] for e in written] == [TEXT]
    assert hass_storage[STORAGE_KEY]["data"]["pending_history"] == []

    await tick(hass, freezer, hours=1)
    written = hass_storage[HISTORY_KEY]["data"]["entries"]
    assert [e["message"] for e in written] == [TEXT]
    assert hass_storage[STORAGE_KEY]["data"]["pending_history"] == []


async def test_pending_history_waits_when_the_history_cannot_be_written_at_start(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
) -> None:
    """The start goes on without the history store; the entry stays pending."""
    entry = await setup(hass, make_entry)
    await notify(hass)
    await notify(hass, message="Zweite Runde")
    crashed = copy.deepcopy(hass_storage[STORAGE_KEY])
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    hass_storage[STORAGE_KEY] = crashed
    del hass_storage[HISTORY_KEY]

    with failing_writes(HISTORY_KEY):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert_ready(hass, ready=True)
    assert HISTORY_KEY not in hass_storage
    pending = hass_storage[STORAGE_KEY]["data"]["pending_history"]
    assert [e["message"] for e in pending] == [TEXT]


async def test_end_states_stay_pending_until_the_history_is_written(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """The hourly round keeps what the history store could not take."""
    await setup(hass, make_entry)
    await notify(hass)
    with failing_writes(HISTORY_KEY):
        await tick(hass, freezer, hours=25)
    data = hass_storage[STORAGE_KEY]["data"]
    assert data["messages"] == {}
    assert [e["title"] for e in data["pending_history"]] == [TITLE]
    assert HISTORY_KEY not in hass_storage
    assert_ready(hass, ready=True)  # the working store is fine

    await tick(hass, freezer, hours=1)
    written = hass_storage[HISTORY_KEY]["data"]["entries"]
    assert [e["title"] for e in written] == [TITLE]
    assert hass_storage[STORAGE_KEY]["data"]["pending_history"] == []


async def test_history_not_writable_raises_a_repair_issue_of_its_own(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Only the history fails: its own repair issue, "Ready" stays on.

    The working store is written on, messages are taken and delivered. Logged
    once when the history fails and once when it is written again; the issue
    goes with the next write that gets through.
    """
    caplog.set_level(logging.INFO, logger="custom_components.message_center")
    await setup(hass, make_entry)
    await notify(hass)
    with failing_writes(HISTORY_KEY):
        await tick(hass, freezer, hours=25)
        assert_ready(hass, ready=True)
        assert ir.async_get(hass).async_get_issue(DOMAIN, "history_not_writable")
        pending = hass_storage[STORAGE_KEY]["data"]["pending_history"]
        assert [e["title"] for e in pending] == [TITLE]
        await notify(hass, title="Zweite")
        assert len(phone) == 2
        await tick(hass, freezer, hours=1)
        assert ir.async_get(hass).async_get_issue(DOMAIN, "history_not_writable")
    assert caplog.text.count("History store not writable") == 1

    await tick(hass, freezer, hours=1)
    assert not ir.async_get(hass).async_get_issue(DOMAIN, "history_not_writable")
    written = hass_storage[HISTORY_KEY]["data"]["entries"]
    assert [e["title"] for e in written] == [TITLE]
    assert hass_storage[STORAGE_KEY]["data"]["pending_history"] == []
    assert caplog.text.count("History store writable again") == 1
    assert_ready(hass, ready=True)


async def test_history_not_writable_at_start_raises_the_repair_issue(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Pending history the start cannot hand over: the issue is up from the start."""
    entry = await setup(hass, make_entry)
    await notify(hass)
    await notify(hass, message="Zweite Runde")
    crashed = copy.deepcopy(hass_storage[STORAGE_KEY])
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    hass_storage[STORAGE_KEY] = crashed
    del hass_storage[HISTORY_KEY]

    with failing_writes(HISTORY_KEY):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert_ready(hass, ready=True)
    assert ir.async_get(hass).async_get_issue(DOMAIN, "history_not_writable")

    await tick(hass, freezer, hours=1)
    assert not ir.async_get(hass).async_get_issue(DOMAIN, "history_not_writable")
    written = hass_storage[HISTORY_KEY]["data"]["entries"]
    assert [e["message"] for e in written] == [TEXT]


async def test_history_not_writable_at_the_stop_raises_the_repair_issue(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
) -> None:
    """The stop cannot hand the pending history over: the issue stands, nothing is lost.

    The end states stay in the working store; the next start, with a history
    that takes them, writes them and takes the issue down.
    """
    entry = await setup(hass, make_entry)
    await notify(hass)
    await notify(hass, message="Zweite Runde")  # the first generation is pending
    with failing_writes(HISTORY_KEY):
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, "history_not_writable")
    assert HISTORY_KEY not in hass_storage
    pending = hass_storage[STORAGE_KEY]["data"]["pending_history"]
    assert [e["message"] for e in pending] == [TEXT]

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert not ir.async_get(hass).async_get_issue(DOMAIN, "history_not_writable")
    written = hass_storage[HISTORY_KEY]["data"]["entries"]
    assert [e["message"] for e in written] == [TEXT]
    assert hass_storage[STORAGE_KEY]["data"]["pending_history"] == []
    assert_ready(hass, ready=True)


async def test_history_issue_of_the_center_before_goes_with_the_next_start(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
) -> None:
    """A stop that fails to write an empty history leaves the issue; the start ends it.

    Nothing is pending, so the start has nothing to hand over; it still writes
    the history once while the issue stands, and the write that gets through
    takes it down. Without that the issue would stand until the next end state
    is written, in a quiet installation for good.
    """
    entry = await setup(hass, make_entry)
    with failing_writes(HISTORY_KEY):
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, "history_not_writable")
    assert hass_storage[STORAGE_KEY]["data"]["pending_history"] == []

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert not ir.async_get(hass).async_get_issue(DOMAIN, "history_not_writable")
    assert hass_storage[HISTORY_KEY]["data"]["entries"] == []
    assert_ready(hass, ready=True)


async def test_pending_history_is_capped_while_the_history_cannot_be_written(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Never more pending end states than the limit; the oldest go, counted.

    The count stands in the log at the next write of the history, without a
    title or text. What is kept reaches the history once it is written.
    """
    caplog.set_level(logging.INFO, logger="custom_components.message_center")
    entry = await setup(hass, make_entry)
    entry.runtime_data.book.max_pending = 3
    with failing_writes(HISTORY_KEY):
        for n in range(1, 6):
            await notify(hass, message=f"Runde {n}")  # no spacing: new generations
        pending = hass_storage[STORAGE_KEY]["data"]["pending_history"]
        assert [e["message"] for e in pending] == ["Runde 2", "Runde 3", "Runde 4"]
        assert "dropped" not in caplog.text
        await tick(hass, freezer, hours=25)  # the fifth is pruned into the list
        pending = hass_storage[STORAGE_KEY]["data"]["pending_history"]
        assert [e["message"] for e in pending] == ["Runde 3", "Runde 4", "Runde 5"]
        assert "Pending history at its limit of 3 entries: 2 oldest dropped" in (
            caplog.text
        )
        assert TITLE not in caplog.text
        assert "Runde" not in caplog.text
        assert_ready(hass, ready=True)

    await tick(hass, freezer, hours=1)
    assert caplog.text.count("oldest dropped") == 1  # nothing new to report
    written = hass_storage[HISTORY_KEY]["data"]["entries"]
    assert [e["message"] for e in written] == ["Runde 3", "Runde 4", "Runde 5"]
    assert hass_storage[STORAGE_KEY]["data"]["pending_history"] == []


async def test_half_a_character_from_the_phone_does_not_block_the_store(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """A typed reply cut in the middle of an emoji is kept in a storable form.

    As a note of the message it would otherwise make every later write fail.
    """
    events = async_capture_events(hass, EVENT_FORWARDED)
    await notify(hass)
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {
            "action": f"message_center_forward|{message_id_of(hass)}",
            "reply_text": "Bitte prüfen \ud83d",
        },
    )
    await hass.async_block_till_done()
    assert [e.data["note"] for e in events] == ["Bitte prüfen ?"]
    kept = hass_storage[STORAGE_KEY]["data"]["messages"][message_id_of(hass)]["events"]
    assert kept[-1]["detail"] == "Bitte prüfen ?"
    assert_ready(hass, ready=True)


async def test_senders_context_survives_a_restart(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_admin_user: Any,
) -> None:
    """A message held over a restart is pushed with its sender's context."""
    hass.states.async_set("input_boolean.night_mode", "on")
    entry = await setup(hass, make_entry, rules=[night_rule_data()])
    context = Context(user_id=hass_admin_user.id)
    await hass.services.async_call(
        "notify",
        "message_center",
        {"title": TITLE, "message": TEXT},
        blocking=True,
        context=context,
    )
    assert open_items(hass)[0]["state"] == "waiting"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert open_items(hass)[0]["state"] == "waiting"
    assert phone == []

    hass.states.async_set("input_boolean.night_mode", "off")
    await hass.async_block_till_done()
    assert len(phone) == 1
    assert phone[0].context.parent_id == context.id
    assert phone[0].context.user_id == hass_admin_user.id


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("de", "1 Meldung konnte noch nicht zugestellt werden."),
        ("en", "1 message could not be delivered yet."),
    ],
)
async def test_failing_deliveries_are_announced_in_the_system_language(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    language: str,
    expected: str,
) -> None:
    """The notification while deliveries fail follows the language of the system."""
    hass.config.language = language
    await setup(hass, make_entry)

    async def failing(call: ServiceCall) -> None:
        raise HomeAssistantError("boom")

    hass.services.async_register("notify", PHONE_ACTION, failing)
    await notify(hass)
    notifications = persistent_notification._async_get_or_create_notifications(hass)
    text = notifications[f"{DOMAIN}_failed_deliveries"]["message"]
    assert text.startswith(expected)
    assert TITLE not in text
    assert TEXT not in text


async def test_blueprint_survives_a_failing_raw_push(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """Center down and the fallback phone fails too: the HA notification remains."""
    calls: list[ServiceCall] = []

    async def failing(call: ServiceCall) -> None:
        calls.append(call)
        raise HomeAssistantError("phone unreachable")

    await blueprint_script(hass, PHONE_ACTION)
    assert await hass.config_entries.async_unload(center_entry.entry_id)
    await hass.async_block_till_done()
    hass.services.async_register("notify", PHONE_ACTION, failing)

    response = await run(hass)
    assert response["result"] == "fallback"
    assert len(calls) == 1
    notifications = persistent_notification._async_get_or_create_notifications(hass)
    assert len(notifications) == 1
    assert next(iter(notifications.values()))["title"] == "Waschmaschine"
