"""Persistence: the working store of messages and the history store.

The working store is written on every change with a 5-second
limit; if writing fails or exceeds the limit the caller rejects with
``not_ready``. The history store collects end states and keeps
them for a configurable number of days. Both confirm their writes: Home
Assistant's ``Store.async_save`` logs a failed write and returns normally,
so each write carries a mark that has to come back from the file.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import secrets
from typing import Any
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .lifecycle import MessageBook
from .models import Message, message_id
from .rules import RuleBook

STORAGE_KEY = f"{DOMAIN}.messages"
# 2 since 0.11: messages and spacing keyed by the salted id (1: origin:key).
# A major version, so that an older version refuses the store visibly
# instead of carrying it on under the wrong keys; back only with a backup.
STORAGE_VERSION = 2
HISTORY_KEY = f"{DOMAIN}.history"
# stays 1: entries written before 0.11 have no id and load as they are
HISTORY_VERSION = 1
SAVE_TIMEOUT = 5
HISTORY_SAVE_DELAY = 300
HISTORY_MAX_ENTRIES = 20_000


class StoreNotWritableError(Exception):
    """A store could not be written within the limit."""


class StoreWriteTimeoutError(StoreNotWritableError):
    """The limit ran out; the write may still be running and finish later."""


class StoreNotReadableError(Exception):
    """A store exists but cannot be read or has an unexpected format.

    A file that is not valid JSON never gets here: Home Assistant moves it
    aside, raises a repair issue and starts with an empty store.
    """


# what malformed content raises while it is turned into messages and phases
_FORMAT_ERRORS = (AttributeError, KeyError, TypeError, ValueError)


async def _async_save_confirmed(
    store: Store[dict[str, Any]], payload: dict[str, Any]
) -> None:
    """Write, then read back within the limit; raise StoreNotWritableError.

    Home Assistant catches the errors of the write itself (disk full, read
    only, data that is not JSON) and only logs them. So the payload gets a
    unique mark, and the write counts when the file returns that mark: after
    a write attempt ``Store.async_load`` reads the file, not a cached copy.
    While Home Assistant stops it hands back the data it keeps for its final
    write instead; that write is then left to Home Assistant.

    The write runs in a task of its own. At the limit only the waiting ends:
    a write that hangs keeps Home Assistant's write lock until it is through,
    so every later write queues behind it and cannot be overwritten by it.
    """
    write_id = uuid4().hex
    payload["write_id"] = write_id
    write = store.hass.async_create_task(
        store.async_save(payload), f"{store.key} write"
    )
    try:
        async with asyncio.timeout(SAVE_TIMEOUT):
            await asyncio.shield(write)
            written = await store.async_load()
    except TimeoutError as err:
        raise StoreWriteTimeoutError(type(err).__name__) from err
    except (OSError, HomeAssistantError) as err:
        raise StoreNotWritableError(str(err) or type(err).__name__) from err
    if not isinstance(written, dict) or written.get("write_id") != write_id:
        raise StoreNotWritableError("write not confirmed")


class _VersionedStore(Store[dict[str, Any]]):
    """Working store with the migration of older formats."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Migrate version 1 (up to 0.10.5) to version 2.

        Messages, spacing and the pending history are keyed anew under the
        salted id, and the salt is kept with them. The spacing goes with
        the messages, else it would not hold once after the update. An old
        key is origin:key, split at the first ':' (an origin has none, a key
        may). Everything else comes over as it is; a field that came later
        takes its default when it is read. What cannot be read raises here,
        and the file stays as it was.
        """
        if old_major_version != 1:
            return old_data
        salt = secrets.token_hex(16)

        def rekey(old_key: str) -> str:
            origin, _, key = old_key.partition(":")
            return message_id(salt, origin, key)

        def with_id(raw: dict[str, Any]) -> dict[str, Any]:
            return {**raw, "id": message_id(salt, raw["origin"], raw["key"])}

        messages = [with_id(raw) for raw in old_data["messages"].values()]
        data = dict(old_data)
        data["id_salt"] = salt
        data["messages"] = {raw["id"]: raw for raw in messages}
        data["spacing"] = {
            rekey(old_key): ts for old_key, ts in old_data.get("spacing", {}).items()
        }
        data["pending_history"] = [
            with_id(raw) for raw in old_data.get("pending_history", [])
        ]
        return data


class MessageStore:
    """Working store of the message book."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Create the store handle; nothing is read yet."""
        self._store = _VersionedStore(hass, STORAGE_VERSION, STORAGE_KEY, private=True)
        self.extra: dict[str, Any] = {}

    async def async_load(
        self, book: MessageBook, rules: RuleBook | None = None
    ) -> datetime | None:
        """Fill the book (and rule phases) from disk; return saved_at, if any.

        Anything else the center keeps (unknown kinds) lands in ``extra``.
        """
        try:
            data = await self._store.async_load()
        except (HomeAssistantError, OSError) as err:
            raise StoreNotReadableError(f"{STORAGE_KEY}: {err}") from err
        except _FORMAT_ERRORS as err:  # raised by the migration
            raise StoreNotReadableError(
                f"{STORAGE_KEY}: unexpected format ({type(err).__name__})"
            ) from err
        if not data:
            return None
        try:
            book.load(data)
            if rules is not None:
                rules.load(data.get("rules", {}))
            self.extra = dict(data.get("extra", {}))
            saved_at = data.get("saved_at")
            return datetime.fromisoformat(saved_at) if saved_at else None
        except _FORMAT_ERRORS as err:
            raise StoreNotReadableError(
                f"{STORAGE_KEY}: unexpected format ({type(err).__name__})"
            ) from err

    async def async_save(
        self,
        book: MessageBook,
        now: datetime,
        rules: RuleBook | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Write the book with a time limit; raise StoreNotWritableError on failure.

        Returning means the book is on disk, see ``_async_save_confirmed``.
        """
        payload = book.to_dict()
        if rules is not None:
            payload["rules"] = rules.to_dict()
        if extra is not None:
            payload["extra"] = extra
        payload["saved_at"] = now.isoformat()
        await _async_save_confirmed(self._store, payload)

    async def async_remove(self) -> None:
        """Delete the store file (the integration is being removed)."""
        await self._store.async_remove()


class HistoryStore:
    """History of ended messages with limited retention."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Create the store handle; nothing is read yet."""
        self._store = Store[dict[str, Any]](
            hass, HISTORY_VERSION, HISTORY_KEY, private=True
        )
        self.entries: list[dict[str, Any]] = []
        self.truncated = False

    async def async_load(self) -> None:
        """Read the history from disk and check every entry.

        A broken entry makes the store not readable, with the reason, rather
        than failing the start wherever the entry is read next. The center
        reads the entries once more where it uses them; even the maximum of
        entries takes a fraction of a second, so the clear failure is worth
        the second pass.
        """
        try:
            data = await self._store.async_load()
            self.entries = list(data.get("entries", [])) if data else []
            for entry in self.entries:
                Message.from_dict(entry)
        except (HomeAssistantError, OSError) as err:
            raise StoreNotReadableError(f"{HISTORY_KEY}: {err}") from err
        except _FORMAT_ERRORS as err:
            raise StoreNotReadableError(
                f"{HISTORY_KEY}: unexpected format ({type(err).__name__})"
            ) from err

    def add(self, entries: list[dict[str, Any]]) -> None:
        """Append ended messages; ``async_flush`` writes them.

        An entry that is already there replaces the older copy. After a
        crash between the write of the history and the write of the working
        store the same end states are handed over a second time.
        """
        if not entries:
            return
        known = {_identity(e): n for n, e in enumerate(self.entries)}
        for entry in entries:
            identity = _identity(entry)
            if identity in known:
                self.entries[known[identity]] = entry
            else:
                known[identity] = len(self.entries)
                self.entries.append(entry)
        self._enforce_limit()

    def prune(self, now: datetime, retention_days: int) -> int:
        """Drop entries older than the retention; return how many were removed."""
        cutoff = (now - timedelta(days=retention_days)).isoformat()
        before = len(self.entries)
        self.entries = [
            e
            for e in self.entries
            if (e.get("ended_at") or e.get("accepted_at")) >= cutoff
        ]
        removed = before - len(self.entries)
        if removed:
            self._store.async_delay_save(self._data, HISTORY_SAVE_DELAY)
        return removed

    async def async_flush(self) -> None:
        """Write now and confirm it; raise StoreNotWritableError on failure."""
        await _async_save_confirmed(self._store, self._data())

    async def async_remove(self) -> None:
        """Delete the store file (the integration is being removed)."""
        await self._store.async_remove()

    def _enforce_limit(self) -> None:
        excess = len(self.entries) - HISTORY_MAX_ENTRIES
        if excess > 0:
            del self.entries[:excess]
            self.truncated = True

    def _data(self) -> dict[str, Any]:
        return {"entries": self.entries}


def _identity(entry: dict[str, Any]) -> tuple[Any, ...]:
    """Return what makes a history entry unique: one generation of a message.

    By the id where the entry has one; entries written before the id came
    are known by origin and key.
    """
    if mid := entry.get("id"):
        return (mid, entry.get("generation", 1), entry.get("accepted_at"))
    return (
        entry.get("origin"),
        entry.get("key"),
        entry.get("generation", 1),
        entry.get("accepted_at"),
    )
