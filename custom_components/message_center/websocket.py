"""WebSocket commands for the page.

Internal interface between the page and the center, administrators only.
Not a published contract; other integrations and automations use the actions
and entities.
"""

from __future__ import annotations

from datetime import datetime
from types import MappingProxyType
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .center import MessageCenter, NotReadyError
from .const import (
    ALARM_CHANNELS,
    ALARM_INTERVAL_MS_MAX,
    ALARM_INTERVAL_MS_MIN,
    ALARM_MAX_SECONDS_MAX,
    ALARM_TEST_SECONDS_MAX,
    CONF_ALARM_CHANNEL,
    CONF_ALARM_INTERVAL_MS,
    CONF_ALARM_LIGHTS,
    CONF_ALARM_MAX_SECONDS,
    CONF_ALARM_TEST_SECONDS,
    CONF_ALARM_TTS,
    CONF_ALLOW_ALARM,
    CONF_BUTTON_FORWARD,
    CONF_BUTTON_SNOOZE,
    CONF_EFFECT_SCRIPTS,
    CONF_FORWARD_SCRIPT,
    CONF_GUIDE_DISMISSED,
    CONF_HIDE_TITLES,
    CONF_HISTORY_DAYS,
    CONF_LIGHT_SPACING,
    CONF_LIGHTS,
    CONF_LIGHTS_ALWAYS,
    CONF_PULSE_MS,
    CONF_RECIPIENTS,
    CONF_SIDEBAR,
    CONF_SILENT_REPEAT,
    CONF_SNOOZE_INPUT,
    CONF_SNOOZE_MINUTES,
    CONF_SNOOZE_MINUTES_2,
    DOMAIN,
    HISTORY_DAYS_MAX,
    LIGHT_DOMAINS,
    LIGHT_SPACING_MAX,
    PULSE_MS_MAX,
    PULSE_MS_MIN,
    SNOOZE_MINUTES_MAX,
    SUBENTRY_GROUP,
    SUBENTRY_KIND,
    SUBENTRY_RULE,
)
from .delivery import discover_mobile_apps
from .kinds import TitleMode
from .lifecycle import NotFoundError
from .models import Message
from .rules import Effect
from .scan import async_scan

KIND_SCHEMA = {
    vol.Required("name"): vol.All(str, vol.Length(min=1, max=60)),
    vol.Optional("origin"): vol.Any(None, str),
    vol.Required("title_mode"): vol.In([m.value for m in TitleMode]),
    vol.Required("title_value"): vol.All(str, vol.Length(min=1, max=200)),
    vol.Optional("group_id"): vol.Any(None, str),
    vol.Required("priority"): vol.All(int, vol.Range(min=1, max=3)),
    vol.Optional("no_hold", default=False): bool,
    vol.Optional("spacing", default=0): vol.All(int, vol.Range(min=0, max=10080)),
    vol.Optional("expires_after", default=0): vol.All(int, vol.Range(min=0, max=10080)),
    vol.Optional("light"): vol.Any(None, bool),
    vol.Optional("active", default=True): bool,
}

GROUP_SCHEMA = {
    vol.Required("name"): vol.All(str, vol.Length(min=1, max=60)),
    vol.Optional("icon"): vol.Any(None, str),
    vol.Optional("priority", default=1): vol.All(int, vol.Range(min=1, max=3)),
    vol.Optional("spacing", default=0): vol.All(int, vol.Range(min=0, max=10080)),
    vol.Optional("expires_after", default=0): vol.All(int, vol.Range(min=0, max=10080)),
}

RULE_SCHEMA = {
    vol.Required("name"): vol.All(str, vol.Length(min=1, max=60)),
    vol.Required("entity_id"): str,
    vol.Required("state"): str,
    vol.Optional("effect_1", default=Effect.HOLD.value): vol.In(
        [e.value for e in Effect]
    ),
    vol.Optional("effect_2", default=Effect.HOLD.value): vol.In(
        [e.value for e in Effect]
    ),
    vol.Optional("effect_3", default=Effect.PASS.value): vol.In(
        [e.value for e in Effect]
    ),
    vol.Optional("max_hours", default=12): vol.All(int, vol.Range(min=1, max=168)),
}

SCHEMAS = {
    SUBENTRY_KIND: KIND_SCHEMA,
    SUBENTRY_GROUP: GROUP_SCHEMA,
    SUBENTRY_RULE: RULE_SCHEMA,
}


def _center(hass: HomeAssistant) -> MessageCenter | None:
    for entry in hass.config_entries.async_entries(DOMAIN):
        center = getattr(entry, "runtime_data", None)
        if entry.state is ConfigEntryState.LOADED and isinstance(center, MessageCenter):
            return center
    return None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _overview(center: MessageCenter) -> dict[str, Any]:
    now = dt_util.utcnow()
    open_messages = center.open_messages()
    return {
        "ready": center.ready,
        "ready_reason": center.ready_reason,
        "open": len(open_messages),
        "waiting": sum(1 for m in open_messages if m.state.value == "waiting"),
        "disturbed": len(center.disturbed_messages()),
        "new": len(center.unknown),
        "active_rules": len(center.rules.active(now)),
        "delivered_today": center.delivered_today,
        "last_delivery": (
            {
                "at": _iso(center.last_delivery[0]),
                "origin": center.last_delivery[1],
                "title": center.last_delivery[2],
            }
            if center.last_delivery
            else None
        ),
        "recipients": len(center.recipients),
        "missing_recipients": center.missing_recipients,
        "unknown": center.unknown_items(),
        "language": center.language,
        "alarm_active": center.alarm_active,
        "alarm_until": _iso(center.alarm_until),
    }


def _entries(center: MessageCenter, messages: list[Message]) -> list[dict[str, Any]]:
    return [center.message_detail(m) for m in messages]


def _subentries(center: MessageCenter, subentry_type: str) -> list[dict[str, Any]]:
    return [
        {"id": sid, **dict(sub.data)}
        for sid, sub in center.entry.subentries.items()
        if sub.subentry_type == subentry_type
    ]


def _kinds_with_ties(center: MessageCenter) -> list[dict[str, Any]]:
    """Kinds, each with the names of kinds it ties with.

    Two active kinds tie when a title can match both with the same
    specificity: same origin condition and mode, identical text for
    "exact" and "starts with", same length for "contains". Then the one
    created first wins, which the page points out.
    """
    kinds = _subentries(center, SUBENTRY_KIND)

    def signature(k: dict[str, Any]) -> tuple[Any, ...]:
        value = str(k.get("title_value", "")).casefold()
        mode = k.get("title_mode", "exact")
        return (
            k.get("origin") or None,
            mode,
            len(value) if mode == "contains" else value,
        )

    active = [k for k in kinds if k.get("active", True)]
    for kind in kinds:
        ties = [
            other["name"]
            for other in active
            if other["id"] != kind["id"]
            and kind.get("active", True)
            and signature(other) == signature(kind)
        ]
        kind["ties"] = ties
    return kinds


def _fail(
    connection: websocket_api.ActiveConnection, msg_id: int, code: str, text: str
) -> None:
    connection.send_error(msg_id, code, text)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/overview"})
@websocket_api.require_admin
@callback
def ws_overview(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Numbers for the overview tab and the list of unknown pairs."""
    center = _center(hass)
    if center is None:
        _fail(connection, msg["id"], "not_ready", "Message Center is not set up")
        return
    connection.send_result(msg["id"], _overview(center))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/messages"})
@websocket_api.require_admin
@callback
def ws_messages(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Open messages and recently ended ones from the working store."""
    center = _center(hass)
    if center is None:
        _fail(connection, msg["id"], "not_ready", "Message Center is not set up")
        return
    connection.send_result(
        msg["id"],
        {
            "open": _entries(center, center.open_messages()),
            "recent": _entries(center, center.recent_messages()),
        },
    )


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/history"})
@websocket_api.require_admin
@callback
def ws_history(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Entries of the history store, newest first."""
    center = _center(hass)
    if center is None:
        _fail(connection, msg["id"], "not_ready", "Message Center is not set up")
        return
    entries = [
        center.message_detail(center.history_message(e)) for e in center.history.entries
    ]
    entries.sort(key=lambda e: e["ended_at"] or e["accepted_at"], reverse=True)
    connection.send_result(msg["id"], {"history": entries})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/config"})
@websocket_api.require_admin
@callback
def ws_config(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Kinds, groups, rules (with phase state) and recipients."""
    center = _center(hass)
    if center is None:
        _fail(connection, msg["id"], "not_ready", "Message Center is not set up")
        return
    now = dt_util.utcnow()
    active = {rule.rule_id: rule for rule in center.rules.active(now)}
    rules = []
    for rule in _subentries(center, SUBENTRY_RULE):
        state = hass.states.get(rule["entity_id"])
        phase = active.get(rule["id"])
        rules.append(
            {
                **rule,
                "current_state": state.state if state else None,
                "active": phase is not None,
                "since": _iso(phase.since) if phase else None,
                "until": _iso(phase.until) if phase else None,
                "expired": phase.expired if phase else False,
                "unknown": phase.unknown if phase else False,
            }
        )
    configured = {r.action: r for r in center.recipients}
    discovered = {r.action: r for r in discover_mobile_apps(hass)}
    errors = center.recipient_errors()
    recipients = [
        {
            **recipient.to_dict(),
            "configured": action in configured,
            "available": hass.services.has_service("notify", action),
            "last_error": errors.get(action),
        }
        for action, recipient in {**discovered, **configured}.items()
    ]
    origins = sorted(
        {
            (m.origin, m.origin_name)
            for m in center.book.messages.values()
            if m.origin != "unknown"
        }
        | {(u["origin"], u.get("origin_name")) for u in center.unknown.values()}
    )
    connection.send_result(
        msg["id"],
        {
            "kinds": _kinds_with_ties(center),
            "groups": _subentries(center, SUBENTRY_GROUP),
            "rules": rules,
            "recipients": recipients,
            "origins": [{"entity_id": o, "name": n} for o, n in origins],
            "options": dict(center.entry.options),
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/save",
        vol.Required("kind"): vol.In([SUBENTRY_KIND, SUBENTRY_GROUP, SUBENTRY_RULE]),
        vol.Optional("subentry_id"): str,
        vol.Required("data"): dict,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_save(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Create or update a kind, group or rule as a subentry."""
    center = _center(hass)
    if center is None:
        _fail(connection, msg["id"], "not_ready", "Message Center is not set up")
        return
    try:
        data = vol.Schema(SCHEMAS[msg["kind"]])(msg["data"])
    except vol.Invalid as err:
        _fail(connection, msg["id"], "invalid_format", str(err))
        return
    entry = center.entry
    subentry_id = msg.get("subentry_id")
    if subentry_id:
        subentry = entry.subentries.get(subentry_id)
        if subentry is None or subentry.subentry_type != msg["kind"]:
            _fail(connection, msg["id"], "not_found", "no such entry")
            return
        hass.config_entries.async_update_subentry(
            entry, subentry, data=data, title=data["name"]
        )
    else:
        subentry = ConfigSubentry(
            data=MappingProxyType(data),
            subentry_type=msg["kind"],
            title=data["name"],
            unique_id=None,
        )
        hass.config_entries.async_add_subentry(entry, subentry)
        subentry_id = subentry.subentry_id
    await center.async_reload_config()
    connection.send_result(msg["id"], {"subentry_id": subentry_id})


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/delete", vol.Required("subentry_id"): str}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete a kind, group or rule."""
    center = _center(hass)
    if center is None:
        _fail(connection, msg["id"], "not_ready", "Message Center is not set up")
        return
    if msg["subentry_id"] not in center.entry.subentries:
        _fail(connection, msg["id"], "not_found", "no such entry")
        return
    hass.config_entries.async_remove_subentry(center.entry, msg["subentry_id"])
    await center.async_reload_config()
    connection.send_result(msg["id"], {})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/action",
        vol.Required("action"): vol.In(["discard", "snooze", "send_now", "forward"]),
        vol.Required("message_id"): str,
        vol.Optional("minutes", default=30): vol.All(int, vol.Range(min=1, max=10080)),
        vol.Optional("note"): vol.Any(None, str),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_action(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Discard, snooze, send now or forward one message from the page."""
    center = _center(hass)
    if center is None:
        _fail(connection, msg["id"], "not_ready", "Message Center is not set up")
        return
    mid = msg["message_id"]
    try:
        if msg["action"] == "discard":
            await center.async_discard(
                message_id=mid, source="page", context=connection.context(msg)
            )
        elif msg["action"] == "snooze":
            await center.async_snooze(
                mid, msg["minutes"], source="page", context=connection.context(msg)
            )
        elif msg["action"] == "send_now":
            await center.async_send_now(mid, source="page")
        else:
            await center.async_forward(
                mid, msg.get("note"), connection.context(msg), source="page"
            )
    except NotFoundError:
        _fail(connection, msg["id"], "not_found", "no such message")
        return
    except NotReadyError as err:
        _fail(connection, msg["id"], "not_ready", f"Message Center is not ready: {err}")
        return
    connection.send_result(msg["id"], {})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/dismiss_unknown",
        vol.Required("origin"): str,
        vol.Required("title"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_dismiss_unknown(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Remove one pair from "new, please classify" (page only)."""
    center = _center(hass)
    if center is None:
        _fail(connection, msg["id"], "not_ready", "Message Center is not set up")
        return
    try:
        known = await center.async_dismiss_unknown(msg["origin"], msg["title"])
    except NotReadyError as err:
        _fail(connection, msg["id"], "not_ready", f"Message Center is not ready: {err}")
        return
    if not known:
        _fail(connection, msg["id"], "not_found", "no such pair")
        return
    connection.send_result(msg["id"], {})


def _light_entity_id(value: Any) -> str:
    """Accept light and switch entity ids for the light pulse."""
    if not isinstance(value, str) or value.split(".", 1)[0] not in LIGHT_DOMAINS:
        raise vol.Invalid("expected a light or switch entity id")
    return value


def _script_entity_id(value: Any) -> str | None:
    """Accept a script entity id or empty (no script)."""
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not value.startswith("script."):
        raise vol.Invalid("expected a script entity id")
    return value


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_LIGHTS_ALWAYS): [_light_entity_id],
        vol.Optional(CONF_FORWARD_SCRIPT): _script_entity_id,
        **{vol.Optional(key): _script_entity_id for key in CONF_EFFECT_SCRIPTS},
        vol.Optional(CONF_HISTORY_DAYS): vol.All(
            int, vol.Range(min=1, max=HISTORY_DAYS_MAX)
        ),
        vol.Optional(CONF_SIDEBAR): bool,
        vol.Optional(CONF_GUIDE_DISMISSED): bool,
        vol.Optional(CONF_SILENT_REPEAT): bool,
        vol.Optional(CONF_HIDE_TITLES): bool,
        vol.Optional(CONF_ALLOW_ALARM): bool,
        vol.Optional(CONF_LIGHTS): [_light_entity_id],
        vol.Optional(CONF_PULSE_MS): vol.All(
            int, vol.Range(min=PULSE_MS_MIN, max=PULSE_MS_MAX)
        ),
        vol.Optional(CONF_LIGHT_SPACING): vol.All(
            int, vol.Range(min=0, max=LIGHT_SPACING_MAX)
        ),
        vol.Optional(CONF_ALARM_LIGHTS): [_light_entity_id],
        vol.Optional(CONF_ALARM_INTERVAL_MS): vol.All(
            int, vol.Range(min=ALARM_INTERVAL_MS_MIN, max=ALARM_INTERVAL_MS_MAX)
        ),
        vol.Optional(CONF_ALARM_MAX_SECONDS): vol.All(
            int, vol.Range(min=5, max=ALARM_MAX_SECONDS_MAX)
        ),
        vol.Optional(CONF_ALARM_TEST_SECONDS): vol.All(
            int, vol.Range(min=1, max=ALARM_TEST_SECONDS_MAX)
        ),
        vol.Optional(CONF_ALARM_CHANNEL): vol.In(ALARM_CHANNELS),
        vol.Optional(CONF_ALARM_TTS): bool,
        vol.Optional(CONF_BUTTON_SNOOZE): bool,
        vol.Optional(CONF_BUTTON_FORWARD): bool,
        vol.Optional(CONF_SNOOZE_MINUTES): vol.All(
            int, vol.Range(min=1, max=SNOOZE_MINUTES_MAX)
        ),
        vol.Optional(CONF_SNOOZE_MINUTES_2): vol.All(
            int, vol.Range(min=0, max=SNOOZE_MINUTES_MAX)
        ),
        vol.Optional(CONF_SNOOZE_INPUT): bool,
    }
)


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/options", vol.Required("options"): dict}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_options(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Change options from the page's settings tab; applied without a restart."""
    center = _center(hass)
    if center is None:
        _fail(connection, msg["id"], "not_ready", "Message Center is not set up")
        return
    try:
        data = OPTIONS_SCHEMA(msg["options"])
    except vol.Invalid as err:
        _fail(connection, msg["id"], "invalid_format", str(err))
        return
    entry = center.entry
    # keep only options that still exist; leftovers of older versions are dropped
    known = {str(key) for key in OPTIONS_SCHEMA.schema}
    kept = {k: v for k, v in entry.options.items() if k in known}
    hass.config_entries.async_update_entry(entry, options={**kept, **data})
    await center.async_reload_config()
    connection.send_result(msg["id"], {"options": dict(entry.options)})


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/recipients", vol.Required("actions"): [str]}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_recipients(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Choose the recipients from the page (discovered phones); at least one."""
    center = _center(hass)
    if center is None:
        _fail(connection, msg["id"], "not_ready", "Message Center is not set up")
        return
    known = {r.action: r for r in center.recipients}
    known.update({r.action: r for r in discover_mobile_apps(hass)})
    unknown = [a for a in msg["actions"] if a not in known]
    if unknown:
        _fail(connection, msg["id"], "not_found", f"unknown recipient: {unknown[0]}")
        return
    chosen = [known[a].to_dict() for a in dict.fromkeys(msg["actions"])]
    if not chosen:
        _fail(connection, msg["id"], "at_least_one", "choose at least one recipient")
        return
    entry = center.entry
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_RECIPIENTS: chosen}
    )
    connection.send_result(msg["id"], {"recipients": chosen})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/test",
        vol.Required("priority"): vol.All(int, vol.Range(min=1, max=3)),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_test(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Send a test push of a priority (settings tab); nothing is recorded."""
    center = _center(hass)
    if center is None:
        _fail(connection, msg["id"], "not_ready", "Message Center is not set up")
        return
    connection.send_result(
        msg["id"], await center.async_test(msg["priority"], connection.context(msg))
    )


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/alarm_off"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_alarm_off(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """End a running alarm light from the page."""
    center = _center(hass)
    if center is None:
        _fail(connection, msg["id"], "not_ready", "Message Center is not set up")
        return
    connection.send_result(
        msg["id"], {"ended": await center.async_stop_alarm(source="page")}
    )


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/scan"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_scan(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Search automations, scripts and files for notifications; read-only."""
    center = _center(hass)
    if center is None:
        _fail(connection, msg["id"], "not_ready", "Message Center is not set up")
        return
    connection.send_result(
        msg["id"], await async_scan(hass, list(center.kinds.values()))
    )


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe"})
@websocket_api.require_admin
@callback
def ws_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Push a notice on every change so the page can refresh."""
    center = _center(hass)
    if center is None:
        _fail(connection, msg["id"], "not_ready", "Message Center is not set up")
        return

    @callback
    def _changed() -> None:
        connection.send_message(
            websocket_api.event_message(msg["id"], {"changed": True})
        )

    connection.subscriptions[msg["id"]] = center.add_listener(_changed)
    connection.send_result(msg["id"])


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    """Register all commands once."""
    for handler in (
        ws_overview,
        ws_messages,
        ws_history,
        ws_config,
        ws_save,
        ws_delete,
        ws_action,
        ws_dismiss_unknown,
        ws_options,
        ws_recipients,
        ws_test,
        ws_alarm_off,
        ws_scan,
        ws_subscribe,
    ):
        websocket_api.async_register_command(hass, handler)
