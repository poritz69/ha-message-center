"""Tests for the page's WebSocket commands and the sidebar panel."""

from __future__ import annotations

from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components import frontend
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_mock_service,
)
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.message_center.const import (
    DOMAIN,
    EVENT_DISCARDED,
    EVENT_SNOOZED,
)
from custom_components.message_center.models import MessageState
from custom_components.message_center.store import STORAGE_KEY

from .conftest import PHONE_ACTION, failing_writes, night_rule_data
from .test_delivery import failing_phone, setup, tick
from .test_services import TITLE, message_id_of, notify, open_items


async def test_panel_is_registered_for_admins(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """The sidebar entry exists, needs admin and points to the served module."""
    panels = hass.data[frontend.DATA_PANELS]
    panel = panels["message-center"]
    assert panel.require_admin is True
    assert panel.sidebar_title == "Message Center"
    # the sidebar shows the logo: an own icon set, provided by an extra module
    assert panel.sidebar_icon == "message-center:logo"
    extra = hass.data[frontend.DATA_EXTRA_MODULE_URL].urls
    assert any(
        "/message_center/frontend/message-center-icons.js?v=" in u for u in extra
    )
    assert panel.config["_panel_custom"]["module_url"].startswith(
        "/message_center/frontend/message-center-panel.js?v="
    )
    assert await hass.config_entries.async_unload(center_entry.entry_id)
    await hass.async_block_till_done()
    assert "message-center" not in hass.data[frontend.DATA_PANELS]
    assert not any(
        "message-center-icons.js" in u
        for u in hass.data[frontend.DATA_EXTRA_MODULE_URL].urls
    )


async def result_for(
    client: Any, msg_id: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Read until the result for msg_id arrives; collect subscription events."""
    events: list[dict[str, Any]] = []
    while True:
        reply = await client.receive_json()
        if reply.get("type") == "event":
            events.append(reply)
            continue
        if reply.get("id") == msg_id:
            return reply, events


async def test_overview_messages_and_actions(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """The page reads numbers, messages and can act on a held message."""
    hass.states.async_set("input_boolean.night_mode", "on")
    entry = make_entry(rules=[night_rule_data()])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await notify(hass)

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/subscribe"})
    assert (await result_for(client, 1))[0]["success"]

    await client.send_json({"id": 2, "type": f"{DOMAIN}/overview"})
    overview = (await result_for(client, 2))[0]["result"]
    assert overview["ready"] is True
    assert overview["open"] == 1
    assert overview["waiting"] == 1
    assert overview["new"] == 1
    assert overview["active_rules"] == 1
    assert overview["unknown"][0]["title"] == TITLE

    await client.send_json({"id": 3, "type": f"{DOMAIN}/messages"})
    messages = (await result_for(client, 3))[0]["result"]
    assert messages["open"][0]["message_id"] == message_id_of(hass)
    assert messages["open"][0]["state"] == "waiting"
    assert messages["open"][0]["message"].startswith("Bitte")
    assert messages["recent"] == []

    await client.send_json(
        {
            "id": 4,
            "type": f"{DOMAIN}/action",
            "action": "send_now",
            "message_id": message_id_of(hass),
        }
    )
    reply, events = await result_for(client, 4)
    assert reply["success"]
    await hass.async_block_till_done()
    assert len(phone) == 1
    if not events:
        events.append(await client.receive_json())
    assert events[0]["type"] == "event"
    assert events[0]["event"] == {"changed": True}

    await client.send_json(
        {
            "id": 5,
            "type": f"{DOMAIN}/action",
            "action": "discard",
            "message_id": "nope:x",
        }
    )
    assert (await result_for(client, 5))[0]["success"]

    await client.send_json(
        {
            "id": 6,
            "type": f"{DOMAIN}/action",
            "action": "snooze",
            "message_id": "nope:x",
        }
    )
    reply, _ = await result_for(client, 6)
    assert not reply["success"]
    assert reply["error"]["code"] == "not_found"

    await client.send_json({"id": 7, "type": f"{DOMAIN}/history"})
    assert (await result_for(client, 7))[0]["result"] == {"history": []}


async def test_action_while_the_store_is_not_writable_is_not_ready(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """The page gets ``not_ready`` for its actions, not an unknown error.

    "Send now" is the exception: it sends although the store cannot be
    written, because outside the intake delivery comes first.
    """
    hass.states.async_set("input_boolean.night_mode", "on")
    entry = make_entry(rules=[night_rule_data()])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await notify(hass)
    client = await hass_ws_client(hass)

    with failing_writes(STORAGE_KEY):
        with pytest.raises(ServiceValidationError):
            await notify(hass, title="Zweite")
        for n, action in enumerate(("discard", "snooze", "forward"), 1):
            await client.send_json(
                {
                    "id": n,
                    "type": f"{DOMAIN}/action",
                    "action": action,
                    "message_id": message_id_of(hass),
                }
            )
            reply, _ = await result_for(client, n)
            assert not reply["success"]
            assert reply["error"]["code"] == "not_ready"
        await hass.async_block_till_done()
        assert phone == []

        await client.send_json(
            {
                "id": 9,
                "type": f"{DOMAIN}/action",
                "action": "send_now",
                "message_id": message_id_of(hass),
            }
        )
        assert (await result_for(client, 9))[0]["success"]
        await hass.async_block_till_done()
        assert len(phone) == 1

    # writable again: the next action tries the store itself and gets through
    await client.send_json(
        {
            "id": 10,
            "type": f"{DOMAIN}/action",
            "action": "snooze",
            "message_id": message_id_of(hass),
        }
    )
    assert (await result_for(client, 10))[0]["success"]
    assert hass.states.get("binary_sensor.message_center_ready").state == "on"


async def test_send_now_releases_a_retry_a_rule_holds_back(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    freezer: FrozenDateTimeFactory,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """The page's "send now" pushes a held retry at once, the rule still on.

    While the rule holds the retry the page shows no next attempt: nothing
    happens before the rule ends, and that end stands in the reason.
    """
    hass.states.async_set("input_boolean.night_mode", "off")
    entry = await setup(hass, make_entry, rules=[night_rule_data()])
    calls = await failing_phone(hass)
    await notify(hass)
    hass.states.async_set("input_boolean.night_mode", "on")
    await tick(hass, freezer, seconds=61)
    item = open_items(hass)[0]
    assert item["state"] == "retrying"
    assert item["reason"].startswith("held back: Nacht until")
    assert item["until"] is not None
    assert item["next_try"] is None

    good = async_mock_service(hass, "notify", PHONE_ACTION)
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/action",
            "action": "send_now",
            "message_id": message_id_of(hass),
        }
    )
    assert (await result_for(client, 1))[0]["success"]
    await hass.async_block_till_done()
    assert hass.states.get("input_boolean.night_mode").state == "on"
    assert (len(calls), len(good)) == (1, 1)
    assert open_items(hass) == []
    msg = entry.runtime_data.book.get(message_id_of(hass))
    assert msg is not None
    assert msg.state is MessageState.DELIVERED
    assert msg.no_hold is True
    assert [e["kind"] for e in msg.events] == ["sent_now"]


async def test_config_save_and_delete(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Kinds, groups and rules are saved as subentries and apply at once."""
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": f"{DOMAIN}/save", "kind": "group", "data": {"name": "Klima"}}
    )
    group_id = (await client.receive_json())["result"]["subentry_id"]
    await client.send_json(
        {
            "id": 2,
            "type": f"{DOMAIN}/save",
            "kind": "kind",
            "data": {
                "name": "Feuchte",
                "title_mode": "prefix",
                "title_value": "Feuchte",
                "group_id": group_id,
                "priority": 2,
                "spacing": 60,
            },
        }
    )
    kind_id = (await client.receive_json())["result"]["subentry_id"]
    await client.send_json(
        {
            "id": 3,
            "type": f"{DOMAIN}/save",
            "kind": "rule",
            "data": {
                "name": "Nacht",
                "entity_id": "input_boolean.night_mode",
                "state": "on",
            },
        }
    )
    rule_id = (await client.receive_json())["result"]["subentry_id"]
    assert len(center_entry.subentries) == 3

    await client.send_json({"id": 4, "type": f"{DOMAIN}/config"})
    config = (await client.receive_json())["result"]
    assert config["kinds"][0]["name"] == "Feuchte"
    assert config["groups"][0]["name"] == "Klima"
    assert config["rules"][0]["name"] == "Nacht"
    assert config["rules"][0]["active"] is True  # entity missing counts as active
    assert config["rules"][0]["unknown"] is True
    assert config["recipients"][0]["action"] == PHONE_ACTION
    assert config["recipients"][0]["configured"] is True

    # the new kind applies without a restart: message goes to group Klima, level 2
    hass.states.async_set("input_boolean.night_mode", "off")
    await hass.async_block_till_done()
    await notify(hass)
    assert phone[0].data["data"]["group"] == "Klima"
    open_state = hass.states.get("sensor.message_center_new")
    assert open_state.state == "0"

    await client.send_json(
        {
            "id": 5,
            "type": f"{DOMAIN}/save",
            "kind": "kind",
            "subentry_id": kind_id,
            "data": {
                "name": "Feuchte",
                "title_mode": "prefix",
                "title_value": "F",
                "priority": 1,
            },
        }
    )
    assert (await client.receive_json())["success"]
    assert center_entry.subentries[kind_id].data["title_value"] == "F"

    await client.send_json(
        {"id": 6, "type": f"{DOMAIN}/save", "kind": "kind", "data": {"name": "x"}}
    )
    reply = await client.receive_json()
    assert not reply["success"]
    assert reply["error"]["code"] == "invalid_format"

    for n, sid in enumerate((kind_id, group_id, rule_id), start=7):
        await client.send_json(
            {"id": n, "type": f"{DOMAIN}/delete", "subentry_id": sid}
        )
        assert (await client.receive_json())["success"]
    assert center_entry.subentries == {}
    await client.send_json(
        {"id": 10, "type": f"{DOMAIN}/delete", "subentry_id": "nope"}
    )
    assert (await client.receive_json())["error"]["code"] == "not_found"


async def test_commands_need_admin(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """A non-admin user is refused."""
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/overview"})
    reply = await client.receive_json()
    assert not reply["success"]
    assert reply["error"]["code"] == "unauthorized"


async def test_commands_without_entry(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Without a set-up center the commands answer not_ready."""
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/overview"})
    reply = await client.receive_json()
    assert reply["error"]["code"] == "not_ready"


async def test_dismiss_unknown_pair(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A pair in "new, please classify" can be dismissed; it returns when it arrives."""
    await notify(hass)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/overview"})
    overview = (await client.receive_json())["result"]
    assert [u["title"] for u in overview["unknown"]] == [TITLE]

    dismiss = {"type": f"{DOMAIN}/dismiss_unknown", "origin": "unknown", "title": TITLE}
    await client.send_json({"id": 2, **dismiss})
    assert (await client.receive_json())["success"]
    assert hass.states.get("sensor.message_center_new").state == "0"
    await client.send_json({"id": 3, **dismiss})
    assert (await client.receive_json())["error"]["code"] == "not_found"

    await notify(hass)
    assert hass.states.get("sensor.message_center_new").state == "1"


async def test_options_from_the_page(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Options apply without a restart; the sidebar entry follows its option."""
    client = await hass_ws_client(hass)
    options = {
        "history_days": 7,
        "hide_titles": True,
        "sidebar": False,
        "lights": ["light.flur"],
    }
    await client.send_json({"id": 1, "type": f"{DOMAIN}/options", "options": options})
    reply = await client.receive_json()
    assert reply["success"]
    assert reply["result"]["options"]["history_days"] == 7
    await hass.async_block_till_done()
    center = center_entry.runtime_data
    assert center.history_days == 7
    assert center.hide_titles is True
    assert center_entry.options["lights"] == ["light.flur"]
    assert hass.data[frontend.DATA_PANELS]["message-center"].show_in_sidebar is False

    for n, bad in enumerate(({"history_days": 0}, {"lights": ["sensor.x"]}), start=2):
        await client.send_json({"id": n, "type": f"{DOMAIN}/options", "options": bad})
        assert (await client.receive_json())["error"]["code"] == "invalid_format"


async def test_recipients_from_the_page(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Recipients are chosen among discovered phones; at least one; unknown refused."""
    ipad_entry = MockConfigEntry(domain="mobile_app", data={})
    ipad_entry.add_to_hass(hass)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=ipad_entry.entry_id,
        identifiers={("mobile_app", "ipad-1")},
        name="iPad",
        manufacturer="Apple",
        model="iPad",
    )
    ipad = async_mock_service(hass, "notify", "mobile_app_ipad")

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/recipients", "actions": []})
    assert (await client.receive_json())["error"]["code"] == "at_least_one"
    await client.send_json(
        {"id": 2, "type": f"{DOMAIN}/recipients", "actions": ["mobile_app_nobody"]}
    )
    assert (await client.receive_json())["error"]["code"] == "not_found"

    await client.send_json(
        {
            "id": 3,
            "type": f"{DOMAIN}/recipients",
            "actions": [PHONE_ACTION, "mobile_app_ipad"],
        }
    )
    reply = await client.receive_json()
    assert reply["success"]
    assert [r["action"] for r in reply["result"]["recipients"]] == [
        PHONE_ACTION,
        "mobile_app_ipad",
    ]
    assert reply["result"]["recipients"][1]["platform"] == "ios"
    await hass.async_block_till_done()  # applied live by the update listener
    assert [r.action for r in center_entry.runtime_data.recipients] == [
        PHONE_ACTION,
        "mobile_app_ipad",
    ]
    await notify(hass)
    assert len(phone) == 1
    assert len(ipad) == 1


async def test_config_shows_recipient_errors_and_kind_ties(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """The last failed attempt per phone; kinds that tie are marked."""
    from homeassistant.exceptions import HomeAssistantError

    from .conftest import kind_data

    async def failing(call: ServiceCall) -> None:
        raise HomeAssistantError("boom")

    hass.services.async_register("notify", PHONE_ACTION, failing)
    entry = make_entry(
        kinds=[
            kind_data(name="A", title_mode="contains", title_value="Feu"),
            kind_data(name="B", title_mode="contains", title_value="Büro"),
            kind_data(name="C", title_mode="exact", title_value="Feuchte: Büro"),
            kind_data(name="D", title_mode="contains", title_value="xyz", active=False),
        ]
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await notify(hass)

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/config"})
    config = (await client.receive_json())["result"]
    recipient = next(r for r in config["recipients"] if r["action"] == PHONE_ACTION)
    assert recipient["last_error"]["error"] == "HomeAssistantError"
    assert recipient["last_error"]["at"]
    ties = {k["name"]: k["ties"] for k in config["kinds"]}
    assert ties == {"A": [], "B": [], "C": [], "D": []}
    # two "contains" kinds of the same length can both match one title: a tie
    await client.send_json(
        {
            "id": 2,
            "type": f"{DOMAIN}/save",
            "kind": "kind",
            "data": {
                "name": "E",
                "title_mode": "contains",
                "title_value": "Bür",
                "priority": 1,
            },
        }
    )
    assert (await client.receive_json())["success"]
    await client.send_json({"id": 3, "type": f"{DOMAIN}/config"})
    config = (await client.receive_json())["result"]
    ties = {k["name"]: k["ties"] for k in config["kinds"]}
    assert ties["A"] == ["E"]
    assert ties["E"] == ["A"]
    assert ties["B"] == []


async def test_options_drop_leftovers_of_older_versions(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Saving one option works with a stale key stored and removes that key."""
    entry = make_entry(options={"pulse_seconds": 1, "pulse_ms": 400})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": f"{DOMAIN}/options", "options": {"guide_dismissed": True}}
    )
    reply = await client.receive_json()
    assert reply["success"], reply
    assert reply["result"]["options"] == {"pulse_ms": 400, "guide_dismissed": True}


async def test_page_actions_carry_the_admins_context(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: Any,
) -> None:
    """Snooze and discard from the page run in the context of the page's user."""
    snoozed = async_capture_events(hass, EVENT_SNOOZED)
    discarded = async_capture_events(hass, EVENT_DISCARDED)
    await notify(hass)
    client = await hass_ws_client(hass)
    for n, action in enumerate(("snooze", "discard"), 1):
        await client.send_json(
            {
                "id": n,
                "type": f"{DOMAIN}/action",
                "action": action,
                "message_id": message_id_of(hass),
            }
        )
        assert (await client.receive_json())["success"]
    await hass.async_block_till_done()
    for events in (snoozed, discarded):
        assert len(events) == 1
        assert events[0].context.user_id == hass_admin_user.id
        assert events[0].data["user_id"] == hass_admin_user.id
        assert events[0].data["source"] == "page"
