"""Tests for the origin of a message: the automation behind the call."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er, label_registry as lr
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import kind_data
from .test_services import message_id_of

AUTOMATION = {
    "automation": [
        {
            "id": "klima_feuchte",
            "alias": "Klima Feuchte Büro",
            "triggers": [{"trigger": "event", "event_type": "test_go"}],
            "actions": [
                {
                    "action": "notify.message_center",
                    "data": {"title": "Feuchte: Büro", "message": "72 %"},
                }
            ],
        }
    ]
}


async def fire_automation(hass: HomeAssistant) -> None:
    """Trigger the test automation and wait."""
    hass.bus.async_fire("test_go")
    await hass.async_block_till_done()
    await hass.async_block_till_done()


async def test_origin_is_the_automation_with_labels(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """A message from an automation carries its entity id, name and labels."""
    assert await async_setup_component(hass, "automation", AUTOMATION)
    await hass.async_block_till_done()
    label = lr.async_get(hass).async_create("Klima")
    er.async_get(hass).async_update_entity(
        "automation.klima_feuchte_buro", labels={label.label_id}
    )
    await fire_automation(hass)

    assert len(phone) == 1
    assert phone[0].data["data"]["tag"] == message_id_of(
        hass, "Feuchte: Büro", "automation.klima_feuchte_buro"
    )
    new = hass.states.get("sensor.message_center_new").attributes["items"][0]
    assert new["origin"] == "automation.klima_feuchte_buro"
    assert new["origin_name"] == "Klima Feuchte Büro"
    center = center_entry.runtime_data
    entry = next(iter(center.unknown.values()))
    assert entry["labels"] == ["Klima"]


async def test_kind_bound_to_automation(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """A kind bound to the automation matches; from elsewhere it does not."""
    entry = make_entry(
        kinds=[kind_data(origin="automation.klima_feuchte_buro", priority=2)]
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert await async_setup_component(hass, "automation", AUTOMATION)
    await hass.async_block_till_done()
    await fire_automation(hass)
    assert hass.states.get("sensor.message_center_new").state == "0"

    await hass.services.async_call(
        "notify",
        "message_center",
        {"title": "Feuchte: Büro", "message": "x"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.message_center_new").state == "1"
    assert len(phone) == 2


SCRIPT = {
    "script": {
        "melde_feuchte": {
            "alias": "Melde Feuchte",
            "sequence": [
                {
                    "action": "notify.message_center",
                    "data": {"title": "Feuchte: Büro", "message": "72 %"},
                }
            ],
        }
    }
}

AUTOMATION_WITH_SCRIPT = {
    "automation": [
        {
            "id": "klima_skript",
            "alias": "Klima über Skript",
            "triggers": [{"trigger": "event", "event_type": "test_go"}],
            "actions": [{"action": "script.melde_feuchte"}],
        }
    ]
}


async def test_script_started_by_an_automation_counts_as_the_automation(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """A script run by an automation sends under the automation's name."""
    assert await async_setup_component(hass, "script", SCRIPT)
    assert await async_setup_component(hass, "automation", AUTOMATION_WITH_SCRIPT)
    await hass.async_block_till_done()
    await fire_automation(hass)

    assert len(phone) == 1
    assert phone[0].data["data"]["tag"] == message_id_of(
        hass, "Feuchte: Büro", "automation.klima_uber_skript"
    )
    new = hass.states.get("sensor.message_center_new").attributes["items"][0]
    assert new["origin_name"] == "Klima über Skript"


async def test_script_started_by_hand_is_its_own_origin(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """Without an automation behind it, the script itself is the origin."""
    assert await async_setup_component(hass, "script", SCRIPT)
    await hass.async_block_till_done()
    await hass.services.async_call("script", "melde_feuchte", blocking=True)
    await hass.async_block_till_done()

    assert len(phone) == 1
    assert phone[0].data["data"]["tag"] == message_id_of(
        hass, "Feuchte: Büro", "script.melde_feuchte"
    )
