"""Shared test fixtures: a phone with the Companion App and a set-up center."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, storage
from homeassistant.util.file import WriteError
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.message_center.const import (
    CONF_RECIPIENTS,
    DOMAIN,
    SUBENTRY_GROUP,
    SUBENTRY_KIND,
    SUBENTRY_RULE,
)

PHONE_ACTION = "mobile_app_phone_alex"
PHONE_NAME = "Phone Alex"
RECIPIENT = {
    "action": PHONE_ACTION,
    "name": PHONE_NAME,
    "platform": "android",
    "type": "mobile_app",
}


# Home Assistant's own reader and writer, taken before ``hass_storage`` replaces them
REAL_LOAD = storage.Store._async_load
REAL_WRITE = storage.Store._async_write_data


def stored(key: str, data: dict[str, Any], *, version: int = 1) -> dict[str, Any]:
    """Return a store file as Home Assistant writes it (version 1 unless given)."""
    return {"version": version, "minor_version": 1, "key": key, "data": data}


def store_0_10_5(now: datetime) -> dict[str, Any]:
    """Return the data of a working store exactly as version 0.10.5 wrote it.

    Made up, but with every field of that format and none that came later: a
    delivered message of a kind with spacing, a message a night rule holds,
    the phase of that rule and the pair noted as "new". Saved at ``now``.
    """
    sent = (now - timedelta(minutes=30)).isoformat()
    held = (now - timedelta(minutes=5)).isoformat()
    until = (now + timedelta(hours=11, minutes=55)).isoformat()
    return {
        "messages": {
            "unknown:Lüften: Bad": {
                "origin": "unknown",
                "origin_name": None,
                "labels": [],
                "key": "Lüften: Bad",
                "kind_id": "01M3WVETH28HF75X7MYS01X005",
                "group_id": None,
                "title": "Lüften: Bad",
                "message": "Fenster öffnen.",
                "data": {"image": "/local/bad.jpg"},
                "priority": 1,
                "state": "delivered",
                "reason": {
                    "kind": "delivered",
                    "until": None,
                    "detail": None,
                    "entity_id": None,
                },
                "generation": 1,
                "revision": 1,
                "count": 1,
                "spacing": 360,
                "no_hold": False,
                "accepted_at": sent,
                "updated_at": sent,
                "expires_at": None,
                "snoozed_until": None,
                "delivered_at": sent,
                "ended_at": sent,
                "forwarded_at": None,
                "cycle_started_at": sent,
                "light_done": False,
                "context_id": "01M3WVETJB344WFDG2TJDAGNR3",
                "user_id": "0f6e1c0a5b7d4e0f9a3c2b1d4e5f6a7b",
                "recipients": {
                    PHONE_ACTION: {
                        "state": "delivered",
                        "attempts": 0,
                        "first_failed_at": None,
                        "last_error": None,
                        "next_try": None,
                        "delivered_at": sent,
                        "delivered_revision": 1,
                        "delivered_count": 1,
                    }
                },
                "events": [],
            },
            "unknown:Feuchte: Büro": {
                "origin": "unknown",
                "origin_name": None,
                "labels": [],
                "key": "Feuchte: Büro",
                "kind_id": None,
                "group_id": None,
                "title": "Feuchte: Büro",
                "message": "Bitte lüften, 72 %.",
                "data": {},
                "priority": 1,
                "state": "waiting",
                "reason": {
                    "kind": "rule",
                    "until": until,
                    "detail": "Nacht",
                    "entity_id": None,
                },
                "generation": 1,
                "revision": 1,
                "count": 1,
                "spacing": 0,
                "no_hold": False,
                "accepted_at": held,
                "updated_at": held,
                "expires_at": None,
                "snoozed_until": None,
                "delivered_at": None,
                "ended_at": None,
                "forwarded_at": None,
                "cycle_started_at": None,
                "light_done": False,
                "context_id": "01M3WVETJDYK7DD2D3FSV4Y42H",
                "user_id": None,
                "recipients": {},
                "events": [],
            },
        },
        "spacing": {"unknown:Lüften: Bad": sent},
        "rules": {
            "phases": {
                "01M3WVF037GXG1JD5X7HYREGWR": {
                    "since": held,
                    "max_until": until,
                    "unknown": False,
                }
            },
            "notified_expired": [],
        },
        "extra": {
            "unknown": {
                "unknown:Feuchte: Büro": {
                    "origin": "unknown",
                    "origin_name": None,
                    "labels": [],
                    "title": "Feuchte: Büro",
                    "count": 1,
                    "first_seen": held,
                    "last_seen": held,
                }
            }
        },
        "saved_at": now.isoformat(),
    }


@contextmanager
def failing_writes(*keys: str, error: type[Exception] = WriteError) -> Iterator[None]:
    """Let Home Assistant fail to write the named stores (all when none is named).

    The error is raised where a full or read-only disk raises it: in
    ``Store._async_write_data``, below the place where Home Assistant catches
    it and only logs. ``Store.async_save`` returns normally, as on a real
    system, and nothing reaches ``hass_storage``.
    """
    write = storage.Store._async_write_data  # the writer of hass_storage

    async def _write(store: storage.Store, data: dict[str, Any]) -> None:
        if keys and store.key not in keys:
            await write(store, data)
            return
        raise error("No space left on device")

    with patch.object(storage.Store, "_async_write_data", _write):
        yield


@contextmanager
def slow_writes() -> Iterator[None]:
    """Let every write of a store take a moment, as a disk does.

    The writer of ``hass_storage`` writes without giving way. A push started
    before the write would then still find its state in the store when it
    reaches the phone. On a real system the write runs in another thread and
    such a push is faster. So the writer gives way a few times first.
    """
    write = storage.Store._async_write_data  # the writer of hass_storage

    async def _write(store: storage.Store, data: dict[str, Any]) -> None:
        for _ in range(5):
            await asyncio.sleep(0)
        await write(store, data)

    with patch.object(storage.Store, "_async_write_data", _write):
        yield


@pytest.fixture
def real_storage(hass: HomeAssistant, tmp_path: Path) -> Iterator[Path]:
    """Let the stores read and write real files; return their folder.

    ``hass_storage`` replaces the reader and the writer of every store. This
    puts Home Assistant's own back, so that a test runs through everything
    below ``Store.async_save`` and ``Store.async_load`` as on a real system.
    """
    assert storage.Store._async_load is not REAL_LOAD  # else nothing to put back
    with (
        patch.object(hass.config, "config_dir", str(tmp_path)),
        patch.object(storage.Store, "_async_load", REAL_LOAD),
        patch.object(storage.Store, "_async_write_data", REAL_WRITE),
    ):
        yield tmp_path / storage.STORAGE_DIR


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow the in-memory Home Assistant to load custom_components."""


@pytest.fixture
def phone(hass: HomeAssistant, hass_admin_user: Any) -> list[ServiceCall]:
    """Create a Companion App device with a notify action; return its calls.

    The phone belongs to an administrator, as the app registers it.
    """
    mobile_entry = MockConfigEntry(
        domain="mobile_app", data={"user_id": hass_admin_user.id}
    )
    mobile_entry.add_to_hass(hass)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=mobile_entry.entry_id,
        identifiers={("mobile_app", "phone-1")},
        name=PHONE_NAME,
        manufacturer="Example",
        model="Phone",
    )
    return async_mock_service(hass, "notify", PHONE_ACTION)


def night_rule_data(**overrides: Any) -> dict[str, Any]:
    """Subentry data of a night rule holding 1 and 2 for 12 hours."""
    data: dict[str, Any] = {
        "name": "Nacht",
        "entity_id": "input_boolean.night_mode",
        "state": "on",
        "effect_1": "hold",
        "effect_2": "hold",
        "effect_3": "pass",
        "max_hours": 12,
    }
    data.update(overrides)
    return data


def kind_data(**overrides: Any) -> dict[str, Any]:
    """Subentry data of a message kind: prefix 'Feuchte' from any origin, level 1."""
    data: dict[str, Any] = {
        "name": "Feuchte",
        "origin": None,
        "title_mode": "prefix",
        "title_value": "Feuchte",
        "group_id": None,
        "priority": 1,
        "no_hold": False,
        "spacing": 0,
        "expires_after": 0,
        "light": None,
        "active": True,
    }
    data.update(overrides)
    return data


@pytest.fixture
def make_entry() -> Callable[..., MockConfigEntry]:
    """Return a factory for a config entry with recipients, rules, kinds and groups."""

    def _make(
        recipients: list[dict[str, Any]] | None = None,
        rules: list[dict[str, Any]] | None = None,
        kinds: list[dict[str, Any]] | None = None,
        groups: list[dict[str, Any]] | None = None,
        options: dict[str, Any] | None = None,
    ) -> MockConfigEntry:
        subentries = []
        for group in groups or []:
            subentries.append(
                {
                    "data": group,
                    "subentry_type": SUBENTRY_GROUP,
                    "title": group["name"],
                    "unique_id": group.get("unique_id"),
                }
            )
        for kind in kinds or []:
            subentries.append(
                {
                    "data": kind,
                    "subentry_type": SUBENTRY_KIND,
                    "title": kind["name"],
                    "unique_id": kind.get("unique_id"),
                }
            )
        for rule in rules or []:
            subentries.append(
                {
                    "data": rule,
                    "subentry_type": SUBENTRY_RULE,
                    "title": rule["name"],
                    "unique_id": None,
                }
            )
        return MockConfigEntry(
            domain=DOMAIN,
            title="Message Center",
            data={CONF_RECIPIENTS: [RECIPIENT] if recipients is None else recipients},
            options=options or {},
            subentries_data=subentries,
        )

    return _make


@pytest.fixture
async def center_entry(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Callable[..., MockConfigEntry],
) -> MockConfigEntry:
    """Set up a message center with one phone and no rules."""
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
