"""Sensors "Open", "Disturbed", "Active rules" and "Last delivery"."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .center import MessageCenter, MessageCenterConfigEntry
from .entity import MessageCenterEntity

# The entities only show the center's state; nothing is polled.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MessageCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the sensors."""
    center = entry.runtime_data
    async_add_entities(
        [
            OpenSensor(center),
            DisturbedSensor(center),
            NewSensor(center),
            ActiveRulesSensor(center),
            LastDeliverySensor(center),
        ]
    )


class OpenSensor(MessageCenterEntity, SensorEntity):
    """Number of unfinished messages with their reasons."""

    def __init__(self, center: MessageCenter) -> None:
        """Create the entity."""
        super().__init__(center, "open")

    @property
    def native_value(self) -> int:
        """Count of unfinished messages."""
        return len(self.center.open_messages())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """One item per message, without text."""
        return {
            "items": [
                self.center.message_summary(m) for m in self.center.open_messages()
            ]
        }


class DisturbedSensor(MessageCenterEntity, SensorEntity):
    """Number of messages in retrying, unclear or failed."""

    def __init__(self, center: MessageCenter) -> None:
        """Create the entity."""
        super().__init__(center, "disturbed")

    @property
    def native_value(self) -> int:
        """Count of disturbed messages."""
        return len(self.center.disturbed_messages())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Items with their last error class."""
        return {
            "items": [
                self.center.message_summary(m, with_error=True)
                for m in self.center.disturbed_messages()
            ]
        }


class NewSensor(MessageCenterEntity, SensorEntity):
    """Number of unknown origin/title pairs waiting to be classified."""

    def __init__(self, center: MessageCenter) -> None:
        """Create the entity."""
        super().__init__(center, "new")

    @property
    def native_value(self) -> int:
        """Count of unknown pairs."""
        return len(self.center.unknown)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Origin, title, count and last arrival per pair."""
        return {
            "items": [
                {
                    "origin": item["origin"],
                    "origin_name": item.get("origin_name"),
                    "title": item["title"] if not self.center.hide_titles else None,
                    "count": item["count"],
                    "last_seen": item["last_seen"],
                }
                for item in self.center.unknown_items()
            ]
        }


class ActiveRulesSensor(MessageCenterEntity, SensorEntity):
    """Rules currently in a hold phase."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, center: MessageCenter) -> None:
        """Create the entity."""
        super().__init__(center, "active_rules")

    @property
    def native_value(self) -> int:
        """Count of active rules."""
        return len(self.center.rules.active(dt_util.utcnow()))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Name, entity, start, latest end and expiry per rule."""
        return {
            "rules": [
                {
                    "name": rule.name,
                    "entity_id": rule.entity_id,
                    "since": rule.since.isoformat(),
                    "until": rule.until.isoformat(),
                    "expired": rule.expired,
                    "unknown": rule.unknown,
                }
                for rule in self.center.rules.active(dt_util.utcnow())
            ]
        }


class LastDeliverySensor(MessageCenterEntity, SensorEntity):
    """Time of the last delivery."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, center: MessageCenter) -> None:
        """Create the entity."""
        super().__init__(center, "last_delivery")

    @property
    def native_value(self) -> datetime | None:
        """Timestamp of the last delivery."""
        return self.center.last_delivery[0] if self.center.last_delivery else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Origin and title of the last delivery."""
        if not self.center.last_delivery:
            return {}
        _, origin, title = self.center.last_delivery
        return {"origin": origin, "title": title}
