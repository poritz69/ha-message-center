"""Tests for the chosen scripts and the light pulse "always"."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_mock_service,
)

from custom_components.message_center.const import DOMAIN, MAX_EFFECT_CONTEXTS

from .conftest import PHONE_ACTION, kind_data
from .test_delivery import setup
from .test_light_and_buttons import ALARM_OPTIONS, LAMPS, lamps, record_switching
from .test_origin import AUTOMATION, fire_automation
from .test_services import TEXT, TITLE, message_id_of, notify


def events_of(hass: HomeAssistant, kind: str) -> list[dict[str, Any]]:
    """Events of one kind under the test message."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    msg = entry.runtime_data.book.messages[message_id_of(hass)]
    return [e for e in msg.events if e["kind"] == kind]


async def test_forward_runs_the_chosen_script_with_variables(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Forwarding ("to assistant") runs the script with title, text, note and origin."""
    script = async_mock_service(hass, "script", "an_ki")
    await setup(hass, make_entry, options={"forward_script": "script.an_ki"})
    await notify(hass)
    await hass.services.async_call(
        DOMAIN,
        "forward",
        {"message_id": message_id_of(hass), "note": "Bitte prüfen"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(script) == 1
    data = script[0].data
    assert data["title"] == TITLE
    assert data["text"] == TEXT
    assert data["note"] == "Bitte prüfen"
    assert data["origin"] == "unknown"
    assert data["message_id"] == message_id_of(hass)
    assert [e["detail"] for e in events_of(hass, "script")] == ["script.an_ki"]


async def test_missing_or_failing_script_is_noted_not_fatal(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """A missing script does not break forwarding; the failure is noted."""
    await setup(hass, make_entry, options={"forward_script": "script.gibt_es_nicht"})
    await notify(hass)
    await hass.services.async_call(
        DOMAIN, "forward", {"message_id": message_id_of(hass)}, blocking=True
    )
    await hass.async_block_till_done()
    failed = events_of(hass, "script_failed")
    assert len(failed) == 1
    assert failed[0]["detail"].startswith("script.gibt_es_nicht: ServiceNotFound")


async def test_failing_script_logs_only_the_error_class(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The text of a script's error may carry the message: the log gets the class."""
    caplog.set_level(logging.INFO, logger="custom_components.message_center")

    async def failing(call: ServiceCall) -> None:
        raise HomeAssistantError(
            f"kann {call.data['title']} / {call.data['text']} nicht"
        )

    hass.services.async_register("script", "kaputt", failing)
    await setup(hass, make_entry, options={"forward_script": "script.kaputt"})
    await notify(hass)
    await hass.services.async_call(
        DOMAIN, "forward", {"message_id": message_id_of(hass)}, blocking=True
    )
    await hass.async_block_till_done()
    assert "Script script.kaputt (forward) failed: HomeAssistantError" in caplog.text
    assert TITLE not in caplog.text
    assert TEXT not in caplog.text
    assert [e["detail"] for e in events_of(hass, "script_failed")] == [
        "script.kaputt: HomeAssistantError"
    ]


async def test_effect_script_runs_on_first_delivery(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """The script of the priority runs once per cycle when delivered."""
    script = async_mock_service(hass, "script", "lautsprecher")

    async def failing(call: ServiceCall) -> None:
        raise HomeAssistantError("kaputt")

    hass.services.async_register("script", "kaputt", failing)
    await setup(
        hass,
        make_entry,
        kinds=[kind_data(priority=2, spacing=60)],
        options={
            "effect_script_2": "script.lautsprecher",
            "effect_script_1": "script.kaputt",
        },
    )
    await notify(hass)
    await hass.async_block_till_done()
    assert len(script) == 1
    assert script[0].data["priority"] == 2
    assert script[0].data["title"] == TITLE
    await notify(hass)  # bundled repeat within the spacing: no second run
    await hass.async_block_till_done()
    assert len(script) == 1
    assert [e["detail"] for e in events_of(hass, "script")] == ["script.lautsprecher"]

    # a failing script of another priority is noted under that message
    await hass.services.async_call(
        DOMAIN,
        "send",
        {"title": "Anderes", "message": "x", "priority": 1},
        blocking=True,
    )
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    msg = entry.runtime_data.book.messages[message_id_of(hass, "Anderes")]
    assert [e["kind"] for e in msg.events] == ["script_failed"]
    assert msg.state.value == "delivered"


async def test_test_push_reports_the_script(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any, hass_ws_client: Any
) -> None:
    """The test button runs the priority's script and reports it."""
    script = async_mock_service(hass, "script", "lautsprecher")
    await setup(hass, make_entry, options={"effect_script_1": "script.lautsprecher"})
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/test", "priority": 1})
    reply = await client.receive_json()
    assert reply["result"]["script"] == "script.lautsprecher"
    assert reply["result"]["script_error"] is None
    assert len(script) == 1
    assert script[0].data["priority"] == 1


async def test_always_targets_pulse_on_then_off(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """An "always" lamp that is off goes on and off; a lit one off and on."""
    blink = await lamps(hass, on=["light.flur"])  # light.kueche is off
    await setup(
        hass,
        make_entry,
        kinds=[kind_data(priority=2)],
        options={"lights": LAMPS, "lights_always": ["light.kueche"]},
    )
    await notify(hass)
    await hass.async_block_till_done()
    assert [e["detail"] for e in events_of(hass, "light")] == [
        "light.flur, light.kueche"
    ]
    calls = [(c.service, c.data["entity_id"]) for c in blink]
    assert ("turn_off", ["light.flur"]) in calls
    assert ("turn_on", ["light.kueche"]) in calls
    assert calls.count(("turn_on", ["light.flur"])) == 1
    assert calls.count(("turn_off", ["light.kueche"])) == 1
    assert len(calls) == 4


async def test_option_schema_rejects_non_scripts(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any, hass_ws_client: Any
) -> None:
    """Only script entities are accepted; empty clears the choice."""
    await setup(hass, make_entry)
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": f"{DOMAIN}/options", "options": {"forward_script": "light.x"}}
    )
    reply = await client.receive_json()
    assert reply["error"]["code"] == "invalid_format"
    await client.send_json(
        {"id": 2, "type": f"{DOMAIN}/options", "options": {"forward_script": ""}}
    )
    reply = await client.receive_json()
    assert reply["success"]
    assert reply["result"]["options"]["forward_script"] is None


# ----- no feedback through the center's own effects -----------------------------


def braked_phone(hass: HomeAssistant, *, after: int = 5) -> list[ServiceCall]:
    """Register a phone whose notify action pulls the brake after ``after`` pushes.

    A message that an effect script sends through the center used to start
    the script again without end. The brake clears the scripts and lamps and
    ends a running alarm so that such a test fails instead of hanging.
    Replaces the fixture ``phone``.
    """
    calls: list[ServiceCall] = []

    async def record(call: ServiceCall) -> None:
        calls.append(call)
        if len(calls) >= after:
            center = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
            center.effect_scripts.clear()
            center.forward_script = None
            center.lights.clear()
            center.alarm_lights.clear()
            hass.async_create_task(center.async_stop_alarm(source="brake"))

    hass.services.async_register("notify", PHONE_ACTION, record)
    return calls


def sending_script(name: str, title: str, **data: Any) -> dict[str, Any]:
    """Return a script that sends through the center, as an effect script might."""
    return {
        name: {
            "alias": name,
            "sequence": [
                {
                    "action": "notify.message_center",
                    "data": {"title": title, "message": "aus dem Skript", **data},
                }
            ],
        }
    }


async def settle(hass: HomeAssistant) -> None:
    """Wait for scripts and automations started by a delivery."""
    for _ in range(3):
        await hass.async_block_till_done()


def messages(hass: HomeAssistant) -> dict[str, Any]:
    """Return the book's messages by id."""
    return hass.config_entries.async_entries(DOMAIN)[0].runtime_data.book.messages


def by_title(hass: HomeAssistant, title: str) -> Any:
    """Return the one message with that title."""
    found = [m for m in messages(hass).values() if m.title == title]
    assert len(found) == 1, [m.title for m in messages(hass).values()]
    return found[0]


async def test_message_from_effect_script_starts_no_effect_and_no_pulse(
    hass: HomeAssistant, make_entry: Any
) -> None:
    """Same title, spacing 0: the script's own message is delivered, nothing more.

    It is pushed, but it starts neither the effect script again (noted as
    ``script_skipped``) nor a light pulse (``light_skipped`` with the reason
    ``effect``). Before: a new generation and a new push at machine speed.
    """
    phone = braked_phone(hass)
    blink = await lamps(hass, on=LAMPS)
    started = async_capture_events(hass, "script_started")
    assert await async_setup_component(
        hass, "script", {"script": sending_script("wirkung", "{{ title }}")}
    )
    await setup(
        hass,
        make_entry,
        kinds=[kind_data(priority=2)],
        options={"effect_script_2": "script.wirkung", "lights": LAMPS},
    )
    await notify(hass)
    await settle(hass)
    assert len(phone) == 2
    assert len(started) == 1
    assert [c.service for c in blink] == ["turn_off", "turn_on"]
    # the script's message has the script as origin, so it is a message of its own
    msg = messages(hass)[message_id_of(hass, TITLE, "script.wirkung")]
    assert msg.state.value == "delivered"
    assert msg.from_effect is True
    assert [(e["kind"], e["detail"]) for e in msg.events] == [
        ("light_skipped", "effect"),
        ("script_skipped", "script.wirkung"),
    ]
    assert messages(hass)[message_id_of(hass)].from_effect is False


async def test_effect_loop_with_changing_title_is_cut(
    hass: HomeAssistant, make_entry: Any
) -> None:
    """A title that changes every round never bundles; the mark still cuts it."""
    phone = braked_phone(hass)
    started = async_capture_events(hass, "script_started")
    assert await async_setup_component(
        hass, "script", {"script": sending_script("wirkung", "{{ title }}x")}
    )
    await setup(
        hass,
        make_entry,
        kinds=[kind_data(spacing=60)],
        options={"effect_script_1": "script.wirkung"},
    )
    await notify(hass)
    await settle(hass)
    assert len(phone) == 2
    assert len(started) == 1
    assert sorted(messages(hass)) == sorted(
        [message_id_of(hass, f"{TITLE}x", "script.wirkung"), message_id_of(hass)]
    )
    assert [e["kind"] for e in by_title(hass, f"{TITLE}x").events] == ["script_skipped"]


async def test_effect_loop_with_an_automation_as_sender_is_cut(
    hass: HomeAssistant, make_entry: Any
) -> None:
    """The context counts, not the origin: the script's message is the automation's."""
    phone = braked_phone(hass)
    started = async_capture_events(hass, "script_started")
    assert await async_setup_component(
        hass, "script", {"script": sending_script("wirkung", "{{ title }}")}
    )
    assert await async_setup_component(hass, "automation", AUTOMATION)
    await setup(hass, make_entry, options={"effect_script_1": "script.wirkung"})
    await fire_automation(hass)
    await settle(hass)
    assert len(phone) == 2
    assert len(started) == 1
    msg = messages(hass)[message_id_of(hass, TITLE, "automation.klima_feuchte_buro")]
    assert msg.generation == 2
    assert [e["kind"] for e in msg.events] == ["script_skipped"]


async def test_effect_loop_through_an_automation_is_cut(
    hass: HomeAssistant, make_entry: Any
) -> None:
    """The script fires an event, an automation sends: known by the parent context."""
    phone = braked_phone(hass)
    started = async_capture_events(hass, "script_started")
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "wirkung": {
                    "alias": "wirkung",
                    "sequence": [{"event": "wirkung_fertig"}],
                }
            }
        },
    )
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "nachlauf",
                    "alias": "Nachlauf",
                    "triggers": [{"trigger": "event", "event_type": "wirkung_fertig"}],
                    "actions": [
                        {
                            "action": "notify.message_center",
                            "data": {"title": "Nachlauf", "message": "läuft"},
                        }
                    ],
                }
            ]
        },
    )
    await setup(hass, make_entry, options={"effect_script_1": "script.wirkung"})
    await notify(hass)
    await settle(hass)
    assert len(phone) == 2
    assert len(started) == 1
    msg = by_title(hass, "Nachlauf")
    assert msg.origin == "automation.nachlauf"
    assert msg.from_effect is True
    assert [e["kind"] for e in msg.events] == ["script_skipped"]


async def test_test_button_script_message_starts_no_effect_script(
    hass: HomeAssistant, make_entry: Any, hass_ws_client: Any
) -> None:
    """The test button's script sends through the center: delivered, no script."""
    phone = braked_phone(hass)
    started = async_capture_events(hass, "script_started")
    assert await async_setup_component(
        hass, "script", {"script": sending_script("wirkung", "Aus dem Test")}
    )
    await setup(hass, make_entry, options={"effect_script_1": "script.wirkung"})
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/test", "priority": 1})
    reply = await client.receive_json()
    assert reply["result"]["script_error"] is None
    await settle(hass)
    assert len(phone) == 2  # the test push and the script's message
    assert len(started) == 1
    msg = by_title(hass, "Aus dem Test")
    assert msg.from_effect is True
    assert [e["kind"] for e in msg.events] == ["script_skipped"]


async def test_forward_reply_from_an_effect_chain_starts_no_effect_script(
    hass: HomeAssistant, make_entry: Any
) -> None:
    """Effect script forwards, the forward script answers through the center: cut."""
    phone = braked_phone(hass)
    started = async_capture_events(hass, "script_started")
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "wirkung": {
                    "alias": "wirkung",
                    "sequence": [
                        {
                            "action": f"{DOMAIN}.forward",
                            "data": {"message_id": "{{ message_id }}", "note": "ki"},
                        }
                    ],
                },
                **sending_script("antwort", "Antwort"),
            }
        },
    )
    await setup(
        hass,
        make_entry,
        options={
            "effect_script_1": "script.wirkung",
            "forward_script": "script.antwort",
        },
    )
    await notify(hass)
    await settle(hass)
    assert len(phone) == 2
    assert [e.data["entity_id"] for e in started] == [
        "script.wirkung",
        "script.antwort",
    ]
    assert [e["kind"] for e in messages(hass)[message_id_of(hass)].events] == [
        "forwarded",
        "script",
        "script",
    ]
    reply = by_title(hass, "Antwort")
    assert reply.state.value == "delivered"
    assert [e["kind"] for e in reply.events] == ["script_skipped"]


async def test_independent_message_still_runs_the_effect_script(
    hass: HomeAssistant, make_entry: Any
) -> None:
    """The mark is per message: a real message after a cut one runs the script."""
    phone = braked_phone(hass)
    started = async_capture_events(hass, "script_started")
    assert await async_setup_component(
        hass, "script", {"script": sending_script("wirkung", "{{ title }}")}
    )
    await setup(hass, make_entry, options={"effect_script_1": "script.wirkung"})
    await notify(hass)
    await settle(hass)
    assert (len(phone), len(started)) == (2, 1)
    await notify(hass, title="Anderes")
    await settle(hass)
    assert (len(phone), len(started)) == (4, 2)
    real = messages(hass)[message_id_of(hass, "Anderes")]
    echo = messages(hass)[message_id_of(hass, "Anderes", "script.wirkung")]
    assert real.from_effect is False
    assert [e["kind"] for e in real.events] == ["script"]
    assert echo.from_effect is True
    assert [e["kind"] for e in echo.events] == ["script_skipped"]


async def test_automation_reacting_to_the_pulsed_lamp_starts_no_pulse(
    hass: HomeAssistant, make_entry: Any
) -> None:
    """An automation reporting a chosen lamp's switching does not pulse again.

    The lamp comes back on at the end of the pulse, the automation reports
    it, and that message would pulse the lamp once more, without end. The
    pulse runs under a context of the center's own; the automation's run has
    it as parent, so its message counts as an own effect.
    """
    phone = braked_phone(hass)
    calls: list[ServiceCall] = []

    async def switching(call: ServiceCall) -> None:
        calls.append(call)
        for entity_id in call.data["entity_id"]:
            state = "on" if call.service == "turn_on" else "off"
            hass.states.async_set(entity_id, state, context=call.context)

    hass.states.async_set("light.flur", "on")
    hass.services.async_register("light", "turn_off", switching)
    hass.services.async_register("light", "turn_on", switching)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "lampe",
                    "alias": "Lampe",
                    "triggers": [
                        {"trigger": "state", "entity_id": "light.flur", "to": "on"}
                    ],
                    "actions": [
                        {
                            "action": "notify.message_center",
                            "data": {"title": "Lampe an: Flur", "message": "an"},
                        }
                    ],
                }
            ]
        },
    )
    await setup(
        hass,
        make_entry,
        kinds=[
            kind_data(priority=2),
            kind_data(name="Lampe", title_value="Lampe", priority=2),
        ],
        options={"lights": ["light.flur"]},
    )
    await notify(hass)
    await settle(hass)
    assert len(phone) == 2
    assert [c.service for c in calls] == ["turn_off", "turn_on"]
    msg = by_title(hass, "Lampe an: Flur")
    assert msg.state.value == "delivered"
    assert msg.from_effect is True
    assert [(e["kind"], e["detail"]) for e in msg.events] == [
        ("light_skipped", "effect")
    ]


async def test_automation_reacting_to_the_alarm_lamp_starts_no_new_alarm(
    hass: HomeAssistant, make_entry: Any
) -> None:
    """Also at priority 3: an automation reporting an alarm lamp ends with the alarm.

    Every "on" step of the alarm light makes the automation report, and that
    message counts as an own effect: it is pushed on the alarm channel, but
    it neither prolongs the running alarm nor starts a new one when the
    lamps are restored afterwards. Before: the alarm never ended, and the
    restoring started it again.
    """
    phone = braked_phone(hass, after=40)
    calls: list[ServiceCall] = []

    async def switching(call: ServiceCall) -> None:
        calls.append(call)
        for entity_id in call.data["entity_id"]:
            state = "on" if call.service == "turn_on" else "off"
            hass.states.async_set(entity_id, state, context=call.context)

    hass.states.async_set("light.flur", "on")
    hass.services.async_register("light", "turn_off", switching)
    hass.services.async_register("light", "turn_on", switching)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "lampe",
                    "alias": "Lampe",
                    "triggers": [
                        {"trigger": "state", "entity_id": "light.flur", "to": "on"}
                    ],
                    "actions": [
                        {
                            "action": "notify.message_center",
                            "data": {"title": "Lampe an: Flur", "message": "an"},
                        }
                    ],
                }
            ]
        },
    )
    await setup(
        hass,
        make_entry,
        kinds=[
            kind_data(priority=3),
            kind_data(name="Lampe", title_value="Lampe", priority=3),
        ],
        options={
            **ALARM_OPTIONS,
            "alarm_lights": ["light.flur"],
            "alarm_max_seconds": 1,
        },
    )
    center = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    await notify(hass)
    await settle(hass)
    assert center.alarm_active
    await asyncio.sleep(2.4)  # the alarm second, the settle second, restoring
    await settle(hass)
    assert not center.alarm_active
    assert len(phone) < 40, "the brake was pulled: the alarm went on"
    assert all(p.data["data"]["channel"] == "alarm_stream" for p in phone)
    assert [e["kind"] for e in messages(hass)[message_id_of(hass)].events] == [
        "alarm_light"
    ]
    echo = by_title(hass, "Lampe an: Flur")
    assert echo.from_effect is True
    assert echo.state.value == "delivered"
    assert [(e["kind"], e["detail"]) for e in echo.events] == [
        ("light_skipped", "effect")
    ]
    # the restoring switched the lamp on again: reported, but no new alarm
    pushes, switched = len(phone), len(calls)
    await asyncio.sleep(0.5)
    await settle(hass)
    assert not center.alarm_active
    assert (len(phone), len(calls)) == (pushes, switched)


async def test_message_from_effect_script_at_priority_3_gets_the_alarm_push_only(
    hass: HomeAssistant, make_entry: Any
) -> None:
    """Priority 3 from an own effect: pushed on the alarm channel, no alarm light.

    The real message starts the alarm light and the script; the script's
    message is delivered like any priority-3 message, but starts no light
    and no script of its own.
    """
    phone = braked_phone(hass)
    started = async_capture_events(hass, "script_started")
    hass.states.async_set("light.flur", "on")
    hass.states.async_set("switch.stehlampe", "off")
    assert await async_setup_component(
        hass, "script", {"script": sending_script("wirkung", "{{ title }}")}
    )
    await setup(
        hass,
        make_entry,
        kinds=[kind_data(priority=3)],
        options={**ALARM_OPTIONS, "effect_script_3": "script.wirkung"},
    )
    calls = record_switching(hass)
    center = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    await notify(hass)
    await settle(hass)
    assert len(phone) == 2
    assert [p.data["data"]["channel"] for p in phone] == ["alarm_stream"] * 2
    assert len(started) == 1
    assert center.alarm_active
    assert calls and calls[0].service == "turn_on"
    assert [e["kind"] for e in messages(hass)[message_id_of(hass)].events] == [
        "alarm_light",
        "script",
    ]
    echo = messages(hass)[message_id_of(hass, TITLE, "script.wirkung")]
    assert echo.from_effect is True
    assert echo.state.value == "delivered"
    assert [(e["kind"], e["detail"]) for e in echo.events] == [
        ("script_skipped", "script.wirkung"),
        ("light_skipped", "effect"),
    ]
    assert await center.async_stop_alarm()


async def test_forward_script_runs_under_a_child_of_the_callers_context(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any, hass_admin_user: Any
) -> None:
    """The forward script runs as the user, below the call; only that child is own.

    A message the user sends under the call itself is a real one; one the
    script sends under its context comes from an own effect.
    """
    script = async_mock_service(hass, "script", "an_ki")
    await setup(hass, make_entry, options={"forward_script": "script.an_ki"})
    await notify(hass)
    context = Context(user_id=hass_admin_user.id)
    await hass.services.async_call(
        DOMAIN,
        "forward",
        {"message_id": message_id_of(hass)},
        blocking=True,
        context=context,
    )
    await hass.async_block_till_done()
    assert len(script) == 1
    assert script[0].context.user_id == hass_admin_user.id
    assert script[0].context.parent_id == context.id
    for title, sender in (
        ("Vom Nutzer", context),
        (
            "Vom Skript",
            Context(user_id=hass_admin_user.id, parent_id=script[0].context.id),
        ),
    ):
        await hass.services.async_call(
            "notify",
            "message_center",
            {"title": title, "message": "x"},
            blocking=True,
            context=sender,
        )
    await hass.async_block_till_done()
    assert by_title(hass, "Vom Nutzer").from_effect is False
    assert by_title(hass, "Vom Skript").from_effect is True


async def test_forward_reply_after_the_phone_button_starts_no_effect_script(
    hass: HomeAssistant, make_entry: Any
) -> None:
    """The assistant's answer to "to assistant" from the phone is an own effect too.

    Whoever forwards (phone, page, action, script): the forward script runs
    under a context of the center's own, so its answer starts no script.
    """
    phone = braked_phone(hass)
    effect = async_mock_service(hass, "script", "wirkung")
    assert await async_setup_component(
        hass, "script", {"script": sending_script("antwort", "Antwort")}
    )
    await setup(
        hass,
        make_entry,
        options={
            "effect_script_1": "script.wirkung",
            "forward_script": "script.antwort",
        },
    )
    await notify(hass)
    await settle(hass)
    assert (len(phone), len(effect)) == (1, 1)
    alex = await hass.auth.async_create_user("Alex", group_ids=["system-users"])
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": phone[0].data["data"]["actions"][1]["action"], "reply_text": "ki"},
        context=Context(user_id=alex.id),
    )
    await settle(hass)
    assert (len(phone), len(effect)) == (2, 1)
    reply = by_title(hass, "Antwort")
    assert reply.from_effect is True
    assert reply.state.value == "delivered"
    assert [e["kind"] for e in reply.events] == ["script_skipped"]


async def test_own_effect_contexts_are_capped_oldest_first(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """The center keeps the last MAX_EFFECT_CONTEXTS contexts; the oldest go first."""
    await setup(hass, make_entry)
    center = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    contexts = [center._own_effect(Context()) for _ in range(MAX_EFFECT_CONTEXTS + 1)]
    assert len(center._effect_contexts) == MAX_EFFECT_CONTEXTS
    assert contexts[0].id not in center._effect_contexts
    assert contexts[1].id in center._effect_contexts
    assert contexts[-1].id in center._effect_contexts
    for title, sender in (("Verdraengt", contexts[0]), ("Gemerkt", contexts[-1])):
        await hass.services.async_call(
            "notify",
            "message_center",
            {"title": title, "message": "x"},
            blocking=True,
            context=sender,
        )
    await hass.async_block_till_done()
    assert by_title(hass, "Verdraengt").from_effect is False
    assert by_title(hass, "Gemerkt").from_effect is True
