"""Diagnostics download, cleaned of texts and personal data."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .center import MessageCenterConfigEntry
from .const import CONF_RECIPIENTS

TEXT_KEYS = {"message", "note", "data"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MessageCenterConfigEntry
) -> dict[str, Any]:
    """Return what helps to narrow down a problem, without message texts.

    Kept: options, recipients (action names), kinds, groups, rules with
    their phase, messages as summaries (title, state, reason, counters,
    events without notes), unknown pairs, counters. Left out: texts,
    notes, extra push data, user ids.
    """
    center = entry.runtime_data
    now = dt_util.utcnow()
    messages = []
    for msg in center.book.messages.values():
        item = center.message_summary(msg, with_error=True)
        item["events"] = [
            {**e, "detail": None if e["kind"] == "forwarded" else e["detail"]}
            for e in msg.events
        ]
        item["generation"] = msg.generation
        item["revision"] = msg.revision
        messages.append(item)
    return {
        "version": entry.version,
        "options": dict(entry.options),
        "recipients": [
            {k: v for k, v in r.items() if k != "name"}
            for r in entry.data.get(CONF_RECIPIENTS, [])
        ],
        "ready": center.ready,
        "ready_reason": center.ready_reason,
        "kinds": [kind.to_dict() for kind in center.kinds.values()],
        "groups": [group.to_dict() for group in center.groups.values()],
        "rules": [
            {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "entity_id": rule.entity_id,
                "state": rule.state,
                "active": rule.rule_id in {r.rule_id for r in center.rules.active(now)},
            }
            for rule in center.rules.rules.values()
        ],
        "messages": messages,
        "history_entries": len(center.history.entries),
        "unknown": [
            {"origin": u["origin"], "title": u["title"], "count": u["count"]}
            for u in center.unknown_items()
        ],
        "delivered_today": center.delivered_today,
        "last_delivery": center.last_delivery[0].isoformat()
        if center.last_delivery
        else None,
        "lights": center.lights,
        "light_enabled": center.light_enabled,
    }
