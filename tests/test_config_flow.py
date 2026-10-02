"""Tests for the config flow."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.message_center.const import CONF_RECIPIENTS, DOMAIN

from .conftest import PHONE_ACTION, PHONE_NAME, RECIPIENT


async def test_user_flow_without_phone_aborts(hass: HomeAssistant) -> None:
    """Without a Companion App device the flow explains what is missing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_mobile_app"


async def test_user_flow_creates_entry(
    hass: HomeAssistant, phone: list[ServiceCall]
) -> None:
    """The user picks phones from the device registry and the entry is created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_RECIPIENTS: [PHONE_ACTION]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Message Center"
    assert result["data"] == {CONF_RECIPIENTS: [RECIPIENT]}
    assert result["data"][CONF_RECIPIENTS][0]["name"] == PHONE_NAME


async def test_second_instance_is_aborted(
    hass: HomeAssistant, phone: list[ServiceCall]
) -> None:
    """Only one message center may exist (single_config_entry)."""
    MockConfigEntry(domain=DOMAIN, data={CONF_RECIPIENTS: [RECIPIENT]}).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_reconfigure_keeps_the_recipients_or_changes_them(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """Reconfigure shows the selection, refuses an empty one, stores a new one."""
    result = await center_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_RECIPIENTS: []}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_RECIPIENTS: "at_least_one"}
    assert center_entry.data[CONF_RECIPIENTS] == [RECIPIENT]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_RECIPIENTS: [PHONE_ACTION]}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert center_entry.data[CONF_RECIPIENTS] == [RECIPIENT]


async def test_user_flow_needs_at_least_one_recipient(
    hass: HomeAssistant, phone: list[ServiceCall]
) -> None:
    """Sending the dialog without a phone shows an error instead of an empty center."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_RECIPIENTS: []}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_RECIPIENTS: "at_least_one"}
    assert hass.config_entries.async_entries(DOMAIN) == []

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_RECIPIENTS: [PHONE_ACTION]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
