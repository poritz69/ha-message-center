"""Tests for the diagnostics download (no message texts) and the script blueprint."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
import json
from pathlib import Path
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceNotFound
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator
import voluptuous as vol

from custom_components.message_center.const import DOMAIN

from .conftest import PHONE_ACTION, PHONE_NAME
from .test_delivery import setup
from .test_services import TEXT, TITLE, notify


@pytest.fixture(autouse=True)
def clean_blueprint(hass: HomeAssistant) -> Iterator[None]:
    """Remove the installed blueprint before and after each test (shared config dir)."""
    path = Path(
        hass.config.path("blueprints", "script", DOMAIN, "nachricht_senden.yaml")
    )
    path.unlink(missing_ok=True)
    yield
    path.unlink(missing_ok=True)


async def test_diagnostics_have_no_texts(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """The download shows state and settings but never message texts or names."""
    await notify(hass)
    data = await get_diagnostics_for_config_entry(hass, hass_client, center_entry)
    dump = json.dumps(data)
    assert data["ready"] is True
    assert data["messages"][0]["title"] == TITLE
    assert data["messages"][0]["state"] == "delivered"
    assert data["recipients"] == [
        {"action": PHONE_ACTION, "platform": "android", "type": "mobile_app"}
    ]
    assert TEXT not in dump
    assert PHONE_NAME not in dump
    assert "user_id" not in dump


async def blueprint_script(hass: HomeAssistant, fallback: str) -> None:
    """Set up a script from the installed blueprint."""
    path = Path(
        hass.config.path("blueprints", "script", DOMAIN, "nachricht_senden.yaml")
    )
    assert await hass.async_add_executor_job(path.exists)
    assert await async_setup_component(hass, "persistent_notification", {})
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "melden": {
                    "use_blueprint": {
                        "path": f"{DOMAIN}/nachricht_senden.yaml",
                        "input": {
                            "ready_entity": "binary_sensor.message_center_ready",
                            "fallback_target": fallback,
                        },
                    }
                }
            }
        },
    )
    await hass.async_block_till_done()


async def run(hass: HomeAssistant) -> dict[str, Any]:
    """Run the blueprint script and return its response."""
    response = await hass.services.async_call(
        "script",
        "melden",
        {"title": "Waschmaschine", "message": "fertig"},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()
    return response


async def test_blueprint_sends_through_the_center(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """With the center ready the message goes through it: result accepted."""
    await blueprint_script(hass, PHONE_ACTION)
    response = await run(hass)
    assert response == {"result": "accepted", "reason": ""}
    assert len(phone) == 1
    assert phone[0].data["title"] == "Waschmaschine"
    assert persistent_notification._async_get_or_create_notifications(hass) == {}


async def test_blueprint_falls_back_when_not_ready(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """Center not ready: HA notification and a raw push to the fallback target only."""
    await blueprint_script(hass, PHONE_ACTION)
    assert await hass.config_entries.async_unload(center_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.message_center_ready").state == "unavailable"

    response = await run(hass)
    assert response["result"] == "fallback"
    assert response["reason"] == "Message Center nicht bereit"
    notifications = persistent_notification._async_get_or_create_notifications(hass)
    assert len(notifications) == 1
    assert next(iter(notifications.values()))["title"] == "Waschmaschine"
    assert len(phone) == 1  # raw, straight to the phone
    assert phone[0].data == {"title": "Waschmaschine", "message": "fertig"}


async def test_blueprint_rejects_a_fallback_without_the_pattern(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """A fallback target that is not a Companion App action is not used."""
    other = async_mock_service(hass, "notify", "telegram")
    await blueprint_script(hass, "telegram")
    assert await hass.config_entries.async_unload(center_entry.entry_id)
    await hass.async_block_till_done()
    response = await run(hass)
    assert response["result"] == "fallback"
    assert other == []
    assert phone == []
    assert len(persistent_notification._async_get_or_create_notifications(hass)) == 1


async def test_blueprint_is_not_overwritten(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """An existing blueprint file in the config is left alone."""
    path = Path(
        hass.config.path("blueprints", "script", DOMAIN, "nachricht_senden.yaml")
    )
    await hass.async_add_executor_job(path.parent.mkdir, 0o755, True, True)
    await hass.async_add_executor_job(path.write_text, "# mine\n")
    await setup(hass, make_entry)
    assert await hass.async_add_executor_job(path.read_text) == "# mine\n"


async def call_script(hass: HomeAssistant, title: str = "Waschmaschine") -> Any:
    """Run the blueprint script without waiting for anything it started."""
    async with asyncio.timeout(2):
        return await hass.services.async_call(
            "script",
            "melden",
            {"title": title, "message": "fertig"},
            blocking=True,
            return_response=True,
        )


async def test_blueprint_does_not_wait_for_a_hanging_phone(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """The raw push runs on its own: a phone that hangs does not hold up the sender."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def hanging(call: ServiceCall) -> None:
        started.set()
        await release.wait()

    await blueprint_script(hass, PHONE_ACTION)
    assert await hass.config_entries.async_unload(center_entry.entry_id)
    await hass.async_block_till_done()
    hass.services.async_register("notify", PHONE_ACTION, hanging)

    response = await call_script(hass)
    assert response["result"] == "fallback"
    async with asyncio.timeout(2):
        await started.wait()  # the raw push is on its way and still hanging
    assert len(persistent_notification._async_get_or_create_notifications(hass)) == 1
    release.set()
    await hass.async_block_till_done()


async def test_blueprint_survives_a_missing_phone_action(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """A fallback target that no longer exists is no error for the sender.

    The separate run for the raw push fails with "action not found"; that
    shows up in the log (here: at the loop's exception handler) and nowhere else.
    """
    background: list[BaseException] = []
    hass.loop.set_exception_handler(
        lambda loop, context: background.append(context["exception"])
    )
    await blueprint_script(hass, "mobile_app_gone")
    assert await hass.config_entries.async_unload(center_entry.entry_id)
    await hass.async_block_till_done()

    response = await call_script(hass)
    await hass.async_block_till_done()
    assert response["result"] == "fallback"
    assert phone == []
    assert len(persistent_notification._async_get_or_create_notifications(hass)) == 1
    assert len(background) == 1
    assert isinstance(background[0], ServiceNotFound)
    assert background[0].service == "mobile_app_gone"


async def test_blueprint_falls_back_without_the_integration(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """Integration removed, its action gone: still a fallback, not a script error."""
    await blueprint_script(hass, PHONE_ACTION)
    assert await hass.config_entries.async_unload(center_entry.entry_id)
    await hass.async_block_till_done()
    hass.services.async_remove(DOMAIN, "send")

    response = await run(hass)
    assert response == {"result": "fallback", "reason": "Message Center nicht bereit"}
    assert len(phone) == 1
    assert phone[0].data == {"title": "Waschmaschine", "message": "fertig"}


async def test_blueprint_falls_back_when_the_center_rejects(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """Center looks ready but rejects the message: fallback with that reason."""
    await blueprint_script(hass, PHONE_ACTION)
    center_entry.runtime_data.ready = False  # the entity still says "on"
    assert hass.states.get("binary_sensor.message_center_ready").state == "on"

    response = await call_script(hass)
    await hass.async_block_till_done()
    assert response == {
        "result": "fallback",
        "reason": "Message Center hat abgelehnt oder nicht geantwortet",
    }
    assert len(phone) == 1  # raw, not through the center
    assert phone[0].data == {"title": "Waschmaschine", "message": "fertig"}


async def test_blueprint_passes_an_invalid_call_on_as_an_error(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """A call the center can never accept (title too long) is the sender's error."""
    await blueprint_script(hass, PHONE_ACTION)
    with pytest.raises(vol.Invalid):
        await call_script(hass, "T" * 150)
    await hass.async_block_till_done()
    assert phone == []
    assert persistent_notification._async_get_or_create_notifications(hass) == {}


async def test_blueprint_passes_unstorable_data_on_as_an_error(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """Extra data the center can never store is the sender's error, no fallback."""
    await blueprint_script(hass, PHONE_ACTION)
    with pytest.raises(vol.Invalid):
        async with asyncio.timeout(2):
            await hass.services.async_call(
                "script",
                "melden",
                {"title": "Waschmaschine", "message": "fertig", "data": {"n": 2**70}},
                blocking=True,
                return_response=True,
            )
    await hass.async_block_till_done()
    assert phone == []
    assert persistent_notification._async_get_or_create_notifications(hass) == {}
