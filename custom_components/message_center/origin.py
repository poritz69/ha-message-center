"""Where a message comes from: the automation or script behind a call.

Home Assistant gives every service call a context. An automation run sets
its own context on the calls it makes and writes its state with the same
context, so the automation can be found by comparing context ids. A script
started by an automation carries the automation's context id as parent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er, label_registry as lr

from .models import UNKNOWN_ORIGIN

ORIGIN_DOMAINS = ("automation", "script")


@dataclass(slots=True)
class Origin:
    """The resolved origin of a message."""

    entity_id: str = UNKNOWN_ORIGIN
    name: str | None = None
    labels: list[str] = field(default_factory=list)

    @property
    def known(self) -> bool:
        """True when an automation or script was found."""
        return self.entity_id != UNKNOWN_ORIGIN


def resolve_origin(hass: HomeAssistant, context: Context | None) -> Origin:
    """Find the automation or script whose run made this call."""
    if context is None:
        return Origin()
    wanted = {context.id}
    if context.parent_id:
        wanted.add(context.parent_id)
    for domain in ORIGIN_DOMAINS:
        for state in hass.states.async_all(domain):
            if state.context.id in wanted:
                return _describe(hass, state.entity_id, state.name)
    return Origin()


def _describe(hass: HomeAssistant, entity_id: str, name: str) -> Origin:
    labels: list[str] = []
    entry = er.async_get(hass).async_get(entity_id)
    if entry is not None:
        label_registry = lr.async_get(hass)
        for label_id in sorted(entry.labels):
            label = label_registry.async_get_label(label_id)
            labels.append(label.name if label else label_id)
    return Origin(entity_id=entity_id, name=name, labels=labels)
