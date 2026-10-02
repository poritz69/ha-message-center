"""The page in the sidebar: a custom panel served by the integration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PANEL_URL_PATH = "message-center"
STATIC_URL = f"/{DOMAIN}/frontend"
FRONTEND_DIR = Path(__file__).parent / "frontend"
PANEL_FILE = "message-center-panel.js"
ICONS_FILE = "message-center-icons.js"
SIDEBAR_ICON = "message-center:logo"
DATA_ICONS_URL = f"{DOMAIN}_icons_url"
DATA_PANEL_REGISTERED = f"{DOMAIN}_panel_registered"


async def async_register_panel(
    hass: HomeAssistant, version: str, *, show: bool
) -> None:
    """Serve the page's code and add the sidebar entry (administrators only)."""
    if not hass.data.get(DATA_PANEL_REGISTERED):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=False)]
        )
        hass.data[DATA_PANEL_REGISTERED] = True
    _register_icons(hass, version)
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title="Message Center",
        sidebar_icon=SIDEBAR_ICON,
        frontend_url_path=PANEL_URL_PATH,
        config={
            "_panel_custom": {
                "name": "message-center-panel",
                "module_url": f"{STATIC_URL}/{PANEL_FILE}?v={version}",
                "embed_iframe": False,
                "trust_external": False,
            }
        },
        require_admin=True,
        show_in_sidebar=show,
        update=True,
    )


def _register_icons(hass: HomeAssistant, version: str) -> None:
    """Let the frontend load the small module that provides the sidebar logo.

    Home Assistant's sidebar only takes icon names. The module registers the
    icon set "message-center" (window.customIcons), so the name
    "message-center:logo" resolves to the logo. Loaded once per version.
    """
    url = f"{STATIC_URL}/{ICONS_FILE}?v={version}"
    previous = hass.data.get(DATA_ICONS_URL)
    if previous == url:
        return
    if previous:
        frontend.remove_extra_js_url(hass, previous)
    frontend.add_extra_js_url(hass, url)
    hass.data[DATA_ICONS_URL] = url


def async_remove_panel(hass: HomeAssistant) -> None:
    """Remove the sidebar entry and the icon module."""
    frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
    if url := hass.data.pop(DATA_ICONS_URL, None):
        frontend.remove_extra_js_url(hass, url)
