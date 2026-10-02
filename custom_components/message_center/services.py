"""Intake and commands: notify.message_center, send, discard, snooze, forward, list.

Registered in ``async_setup`` so that they exist independently of the config
entry; without a loaded entry every call is rejected with ``not_ready``.
Intake is open to everyone; the interventions need the right to control the
center's entities, checked by Home Assistant.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.json import json_bytes
from homeassistant.helpers.service import (
    async_set_service_schema,
    verify_domain_control,
)
import voluptuous as vol

from .center import MessageCenter, NotReadyError, PriorityNotAllowedError
from .const import (
    DOMAIN,
    KEY_MAX_LENGTH,
    MESSAGE_MAX_LENGTH,
    MINUTES_MAX,
    NOTE_MAX_LENGTH,
    PRIORITY_MAX,
    PRIORITY_MIN,
    TITLE_MAX_LENGTH,
)
from .lifecycle import NotFoundError, StoreFullError

NOTIFY_SERVICE = "message_center"
SERVICE_SEND = "send"
SERVICE_DISCARD = "discard"
SERVICE_SNOOZE = "snooze"
SERVICE_FORWARD = "forward"
SERVICE_LIST = "list"

DEFAULT_TITLE = "Mitteilung"


def _storable(value: Any) -> Any:
    """Refuse a text or extra data that the store could not write as JSON.

    Checked with the serialiser Home Assistant's stores write with, and as
    deep inside a file as the data of a message lies there (nesting has a
    limit). So one such value cannot make every later write fail. The error
    names no value.
    """
    try:
        json_bytes({"data": {"messages": {"id": {"data": value}}}})
    except TypeError:  # what the store's writer catches as not serialisable
        raise vol.Invalid("value cannot be stored as JSON") from None
    return value


TITLE = vol.All(cv.string, vol.Length(min=1, max=TITLE_MAX_LENGTH), _storable)
TEXT = vol.All(cv.string, vol.Length(min=1, max=MESSAGE_MAX_LENGTH), _storable)
DATA = vol.All(vol.Schema({str: object}), _storable)

NOTIFY_SCHEMA = vol.Schema(
    {
        vol.Required("message"): TEXT,
        vol.Optional("title"): TITLE,
        vol.Optional("target"): object,
        vol.Optional("data"): DATA,
    }
)

SEND_SCHEMA = vol.Schema(
    {
        vol.Required("title"): TITLE,
        vol.Required("message"): TEXT,
        vol.Optional("data"): DATA,
        vol.Optional("kind"): cv.string,
        vol.Optional("priority"): vol.All(
            vol.Coerce(int), vol.Range(min=PRIORITY_MIN, max=PRIORITY_MAX)
        ),
        vol.Optional("key"): vol.All(
            cv.string, vol.Length(min=1, max=KEY_MAX_LENGTH), _storable
        ),
    }
)

DISCARD_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional("message_id"): cv.string,
            vol.Optional("origin"): cv.string,
            vol.Optional("title"): TITLE,
        }
    ),
    cv.has_at_least_one_key("message_id", "title"),
)

SNOOZE_SCHEMA = vol.Schema(
    {
        vol.Required("message_id"): cv.string,
        vol.Required("minutes"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=MINUTES_MAX)
        ),
    }
)

FORWARD_SCHEMA = vol.Schema(
    {
        vol.Required("message_id"): cv.string,
        vol.Optional("note"): vol.All(
            cv.string, vol.Length(max=NOTE_MAX_LENGTH), _storable
        ),
    }
)

LIST_SCHEMA = vol.Schema({vol.Optional("include_history", default=False): cv.boolean})


def _center(hass: HomeAssistant) -> MessageCenter:
    """Return the running center or reject with ``not_ready``."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        center = getattr(entry, "runtime_data", None)
        if entry.state is ConfigEntryState.LOADED and isinstance(center, MessageCenter):
            return center
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="not_ready",
        translation_placeholders={"reason": "not set up"},
    )


def _kind_id(center: MessageCenter, value: str | None) -> str | None:
    """Accept a kind by id or by name."""
    if value is None:
        return None
    if value in center.kinds:
        return value
    for kind_id, kind in center.kinds.items():
        if kind.name.casefold() == value.casefold():
            return kind_id
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_field",
        translation_placeholders={"field": "kind", "reason": f"unknown kind {value}"},
    )


async def _intake(call: ServiceCall, *, with_kind: bool) -> dict[str, Any]:
    center = _center(call.hass)
    data = call.data
    try:
        return await center.async_intake(
            title=data.get("title") or DEFAULT_TITLE,
            message=data["message"],
            data=dict(data.get("data") or {}),
            context=call.context,
            kind_id=_kind_id(center, data.get("kind")) if with_kind else None,
            priority=data.get("priority") if with_kind else None,
            key=data.get("key") if with_kind else None,
        )
    except NotReadyError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_ready",
            translation_placeholders={"reason": str(err)},
        ) from err
    except PriorityNotAllowedError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="priority_not_allowed"
        ) from err
    except StoreFullError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="store_full"
        ) from err


async def _async_notify(call: ServiceCall) -> None:
    await _intake(call, with_kind=False)


async def _async_send(call: ServiceCall) -> ServiceResponse:
    response = await _intake(call, with_kind=True)
    return response if call.return_response else None


def _controlling(
    handler: Callable[[ServiceCall], Awaitable[ServiceResponse]],
) -> Callable[[ServiceCall], Awaitable[ServiceResponse]]:
    """Let only callers through who may control the center's entities.

    Home Assistant's own check: administrators, users and calls without a
    user (automations, scripts) pass, a user who may only read is refused
    with ``Unauthorized``. The check looks for an entity of the center, so
    it runs after the readiness check: without a loaded entry there is none,
    and every caller would be refused instead of told ``not_ready``.
    """
    checked = verify_domain_control(DOMAIN)(handler)

    async def wrapper(call: ServiceCall) -> ServiceResponse:
        _center(call.hass)
        return await checked(call)

    return wrapper


def _not_found(err: Exception) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN, translation_key="not_found"
    )


def _not_ready(err: Exception) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="not_ready",
        translation_placeholders={"reason": str(err)},
    )


@_controlling
async def _async_discard(call: ServiceCall) -> ServiceResponse:
    center = _center(call.hass)
    try:
        count = await center.async_discard(
            message_id=call.data.get("message_id"),
            origin=call.data.get("origin"),
            title=call.data.get("title"),
            context=call.context,
        )
    except NotReadyError as err:
        raise _not_ready(err) from err
    return {"result": "done", "discarded": count} if call.return_response else None


@_controlling
async def _async_snooze(call: ServiceCall) -> ServiceResponse:
    center = _center(call.hass)
    try:
        until = await center.async_snooze(
            call.data["message_id"], call.data["minutes"], context=call.context
        )
    except NotFoundError as err:
        raise _not_found(err) from err
    except NotReadyError as err:
        raise _not_ready(err) from err
    return (
        {"result": "done", "until": until.isoformat()} if call.return_response else None
    )


@_controlling
async def _async_forward(call: ServiceCall) -> ServiceResponse:
    center = _center(call.hass)
    try:
        await center.async_forward(
            call.data["message_id"], call.data.get("note"), call.context
        )
    except NotFoundError as err:
        raise _not_found(err) from err
    except NotReadyError as err:
        raise _not_ready(err) from err
    return {"result": "done"} if call.return_response else None


async def _async_list(call: ServiceCall) -> ServiceResponse:
    center = _center(call.hass)
    user_id = call.context.user_id
    user = await call.hass.auth.async_get_user(user_id) if user_id else None
    if user is None or not user.is_admin:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="not_authorized"
        )
    return center.list_messages(include_history=call.data["include_history"])


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register the notify intake and the actions once."""
    if hass.services.has_service(DOMAIN, SERVICE_SEND):
        return
    hass.services.async_register(
        "notify", NOTIFY_SERVICE, _async_notify, schema=NOTIFY_SCHEMA
    )
    async_set_service_schema(
        hass,
        "notify",
        NOTIFY_SERVICE,
        {
            "name": "Message Center",
            "description": (
                "Send a notification through Message Center instead of directly "
                "to a phone. Title, text and extra data are passed on; Message "
                "Center assigns the message kind, priority and delivery rules."
            ),
            "fields": {
                "message": {
                    "name": "Message",
                    "description": "The text shown on the phone.",
                    "required": True,
                    "example": "Der Sensor liefert seit 2 h keine Werte.",
                    "selector": {"text": {"multiline": True}},
                },
                "title": {
                    "name": "Title",
                    "description": (
                        "Short and neutral; also used to tell messages apart."
                    ),
                    "example": "Feuchte: Büro",
                    "selector": {"text": {}},
                },
                "data": {
                    "name": "Extra data",
                    "description": (
                        "Passed on to the phone unchanged (image, actions, ...); "
                        "must be storable as JSON."
                    ),
                    "selector": {"object": {}},
                },
            },
        },
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND,
        _async_send,
        schema=SEND_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DISCARD,
        _async_discard,
        schema=DISCARD_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SNOOZE,
        _async_snooze,
        schema=SNOOZE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_FORWARD,
        _async_forward,
        schema=FORWARD_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST,
        _async_list,
        schema=LIST_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
