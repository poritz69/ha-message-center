"""Binary sensor "Ready"."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .center import MessageCenterConfigEntry
from .entity import MessageCenterEntity

# The entities only show the center's state; nothing is polled.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MessageCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the ready sensor."""
    async_add_entities([ReadyBinarySensor(entry.runtime_data)])


class ReadyBinarySensor(MessageCenterEntity, BinarySensorEntity):
    """On when the store is loaded and writable."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, center: Any) -> None:
        """Create the entity."""
        super().__init__(center, "ready")

    @property
    def is_on(self) -> bool:
        """Return the readiness."""
        return self.center.ready

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Reason and missing recipients."""
        return {
            "reason": self.center.ready_reason,
            "missing_recipients": self.center.missing_recipients,
        }
