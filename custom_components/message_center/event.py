"""Event entity "Delivered" mirroring the delivered event."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .center import MessageCenter, MessageCenterConfigEntry
from .entity import MessageCenterEntity

# The entities only show the center's state; nothing is polled.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MessageCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the event entity."""
    async_add_entities([DeliveredEventEntity(entry.runtime_data)])


class DeliveredEventEntity(MessageCenterEntity, EventEntity):
    """Fires once per push cycle on the first delivered recipient."""

    def __init__(self, center: MessageCenter) -> None:
        """Create the entity."""
        super().__init__(center, "delivered")
        self._attr_event_types = ["delivered"]

    async def async_added_to_hass(self) -> None:
        """Subscribe to delivered events only (no redraw on every change)."""
        await EventEntity.async_added_to_hass(self)
        self.async_on_remove(self.center.add_delivered_listener(self._on_delivered))

    @callback
    def _on_delivered(self, data: dict[str, Any]) -> None:
        self._trigger_event("delivered", data)
        self.async_write_ha_state()
