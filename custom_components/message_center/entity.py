"""Base entity: one device per config entry."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .center import MessageCenter
from .const import DOMAIN


class MessageCenterEntity(Entity):
    """Entity that redraws whenever the center changes."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, center: MessageCenter, key: str) -> None:
        """Bind the entity to the center; ``key`` is the translation key."""
        self.center = center
        self._attr_unique_id = f"{center.entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, center.entry.entry_id)},
            name="Message Center",
            manufacturer="poritz69",
            model="Message Center",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to changes of the center."""
        self.async_on_remove(self.center.add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
