"""Message Center: one central place for the notifications of a home.

The notify intake and the actions are registered in ``async_setup`` so that
they exist independently of the config entry; the runtime is
created per entry.
"""

from __future__ import annotations

from pathlib import Path
import shutil

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .center import MessageCenter, MessageCenterConfigEntry
from .const import CONF_SIDEBAR, DOMAIN
from .panel import async_register_panel, async_remove_panel
from .services import async_register_services
from .store import HistoryStore, MessageStore, StoreNotReadableError
from .websocket import async_register_websocket

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.EVENT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the intake, the actions and the page's commands."""
    async_register_services(hass)
    async_register_websocket(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: MessageCenterConfigEntry
) -> bool:
    """Start the message center for this entry."""
    center = MessageCenter(hass, entry)
    try:
        await center.async_start()
    except StoreNotReadableError as err:
        # nothing is running yet; Home Assistant shows the reason and retries
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="store_not_readable",
            translation_placeholders={"error": str(err)},
        ) from err
    entry.runtime_data = center
    await hass.async_add_executor_job(_install_blueprint, hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_register_panel(
        hass, _version(hass), show=bool(entry.options.get(CONF_SIDEBAR, True))
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


BLUEPRINT_FILE = "nachricht_senden.yaml"


def _install_blueprint(hass: HomeAssistant) -> None:
    """Copy the script blueprint "send with fallback" into the config.

    Only when it is missing; an existing file is never overwritten.
    """
    source = Path(__file__).parent / "blueprints" / "script" / BLUEPRINT_FILE
    target = Path(hass.config.path("blueprints", "script", DOMAIN, BLUEPRINT_FILE))
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _version(hass: HomeAssistant) -> str:
    """Version string for cache busting of the page's code."""
    from homeassistant.loader import async_get_loaded_integration

    integration = async_get_loaded_integration(hass, DOMAIN)
    return str(integration.version or "0")


async def _async_update_listener(
    hass: HomeAssistant, entry: MessageCenterConfigEntry
) -> None:
    """Apply changed recipients, kinds, groups, rules and options without a restart.

    Recipients used to force a reload of the entry. Applying them live keeps the
    page's subscription alive; open messages keep the recipients they started with.
    """
    center = entry.runtime_data
    await center.async_reload_config()
    await async_register_panel(
        hass, _version(hass), show=bool(entry.options.get(CONF_SIDEBAR, True))
    )


async def async_unload_entry(
    hass: HomeAssistant, entry: MessageCenterConfigEntry
) -> bool:
    """Stop the message center."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        async_remove_panel(hass)
        await entry.runtime_data.async_stop()
    return unloaded


async def async_remove_entry(
    hass: HomeAssistant, entry: MessageCenterConfigEntry
) -> None:
    """Delete the stored messages and the history together with the entry.

    They contain message texts; nothing of that may stay behind when the
    integration is removed. The blueprint file is the user's and stays.
    """
    await MessageStore(hass).async_remove()
    await HistoryStore(hass).async_remove()
