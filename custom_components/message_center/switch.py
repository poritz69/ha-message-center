"""Switch "Light pulse": turn the light pulse off without editing."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .center import MessageCenter, MessageCenterConfigEntry
from .entity import MessageCenterEntity

# The switches act on the running center, not on a device; no limit needed.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MessageCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the switch."""
    async_add_entities(
        [LightPulseSwitch(entry.runtime_data), AlarmSwitch(entry.runtime_data)]
    )


class LightPulseSwitch(MessageCenterEntity, SwitchEntity, RestoreEntity):
    """On: level 2 (or kinds set to "always") blink the chosen lamps."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, center: MessageCenter) -> None:
        """Create the entity."""
        super().__init__(center, "light_pulse")

    async def async_added_to_hass(self) -> None:
        """Restore the last position; on by default."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state == STATE_OFF:
            self.center.light_enabled = False

    @property
    def is_on(self) -> bool:
        """True while the pulse is enabled."""
        return self.center.light_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the pulse."""
        self.center.set_light_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the pulse."""
        self.center.set_light_enabled(False)


class AlarmSwitch(MessageCenterEntity, SwitchEntity):
    """On while the alarm light runs; turning off ends it, turning on starts it."""

    def __init__(self, center: MessageCenter) -> None:
        """Create the entity."""
        super().__init__(center, "alarm")

    @property
    def is_on(self) -> bool:
        """True while the alarm light runs."""
        return self.center.alarm_active

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Until when it runs at most."""
        return {
            "until": self.center.alarm_until.isoformat()
            if self.center.alarm_until
            else None
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start the alarm light by hand (up to the maximum duration).

        The lamps are switched in the context of whoever flipped the switch;
        Home Assistant sets it on the entity before the call.
        """
        await self.center.async_start_alarm(source="switch", context=self._context)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """End the alarm light."""
        await self.center.async_stop_alarm(source="switch")
