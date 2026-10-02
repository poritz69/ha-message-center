"""Tests for setting up and unloading the integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.message_center.const import DOMAIN
from custom_components.message_center.store import HISTORY_KEY, STORAGE_KEY

from .test_services import notify


async def test_setup_and_unload_entry(
    hass: HomeAssistant, center_entry: MockConfigEntry
) -> None:
    """The config entry loads with its entities and unloads cleanly."""
    assert center_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("binary_sensor.message_center_ready").state == "on"
    assert hass.states.get("sensor.message_center_open").state == "0"
    assert hass.services.has_service(DOMAIN, "send")

    assert await hass.config_entries.async_unload(center_entry.entry_id)
    await hass.async_block_till_done()
    assert center_entry.state is ConfigEntryState.NOT_LOADED
    assert hass.services.has_service(DOMAIN, "send")


async def test_removing_the_entry_deletes_the_stored_messages(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Message texts must not stay on disk when the integration is removed."""
    await notify(hass)
    await center_entry.runtime_data.history.async_flush()
    assert STORAGE_KEY in hass_storage
    assert HISTORY_KEY in hass_storage

    assert await hass.config_entries.async_remove(center_entry.entry_id)
    await hass.async_block_till_done()
    assert STORAGE_KEY not in hass_storage
    assert HISTORY_KEY not in hass_storage
    assert hass.config_entries.async_entries(DOMAIN) == []
