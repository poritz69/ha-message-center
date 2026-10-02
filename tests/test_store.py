"""Tests for the working store and the history store."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import threading
from typing import Any
from unittest.mock import patch

from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.json import SerializationError
from homeassistant.helpers.storage import Store
from homeassistant.util.file import WriteError
import pytest

from custom_components.message_center.lifecycle import MessageBook
from custom_components.message_center.models import Message, message_id
from custom_components.message_center.store import (
    HISTORY_KEY,
    HISTORY_MAX_ENTRIES,
    STORAGE_KEY,
    STORAGE_VERSION,
    HistoryStore,
    MessageStore,
    StoreNotReadableError,
    StoreNotWritableError,
    StoreWriteTimeoutError,
)

from .conftest import failing_writes, store_0_10_5, stored

T0 = datetime(2026, 9, 29, 22, 0, tzinfo=UTC)
ORIGIN = "automation.klima"
# a fixed salt, so that entries and ids can be compared across books
SALT = "9a8b7c6d5e4f30211f2e3d4c5b6a7988"


def mid(key: str) -> str:
    """Id of a message of the made-up origin under the fixed salt."""
    return message_id(SALT, ORIGIN, key)


def entry(key: str, *, generation: int = 1, **fields: Any) -> dict[str, Any]:
    """Return a history entry: a whole ended message of the made-up origin."""
    msg = book_with(key).messages[mid(key)]
    msg.generation = generation
    msg.ended_at = T0
    return {**msg.to_dict(), **fields}


def ended_message() -> dict[str, Any]:
    """Return an end state as the book hands it to the history: a whole message."""
    return entry("old")


def book_with(key: str) -> MessageBook:
    """Return a book holding one message of the made-up origin."""
    book = MessageBook(salt=SALT)
    book.accept(origin=ORIGIN, key=key, title=key, message="M", priority=1, now=T0)
    return book


def confirmed_write(
    hass: HomeAssistant, kind: str
) -> tuple[Store[dict[str, Any]], Callable[[], Awaitable[None]]]:
    """Return Home Assistant's store and the confirmed write of ours on top."""
    if kind == "history":
        history = HistoryStore(hass)
        return history._store, history.async_flush
    store = MessageStore(hass)
    return store._store, lambda: store.async_save(MessageBook(), T0)


async def test_save_and_load_roundtrip(hass: HomeAssistant, hass_storage: dict) -> None:
    """The book and saved_at survive a save/load cycle."""
    book = MessageBook()
    book.accept(
        origin="automation.klima",
        key="T",
        title="T",
        message="M",
        priority=1,
        now=T0,
    )
    store = MessageStore(hass)
    await store.async_save(book, T0)
    assert STORAGE_KEY in hass_storage
    assert hass_storage[STORAGE_KEY]["data"]["saved_at"] == T0.isoformat()

    other = MessageBook()
    saved_at = await MessageStore(hass).async_load(other)
    assert saved_at == T0
    assert other.to_dict() == book.to_dict()


async def test_load_empty_store(hass: HomeAssistant, hass_storage: dict) -> None:
    """A missing file yields an empty book and no saved_at."""
    book = MessageBook()
    assert await MessageStore(hass).async_load(book) is None
    assert book.messages == {}


async def test_save_timeout_raises(hass: HomeAssistant, hass_storage: dict) -> None:
    """A write that exceeds the limit is reported as not writable."""
    book = MessageBook()
    store = MessageStore(hass)
    release = asyncio.Event()

    async def slow_save(_data: Any) -> None:
        await release.wait()

    with (
        patch("custom_components.message_center.store.SAVE_TIMEOUT", 0.01),
        patch.object(store._store, "async_save", slow_save),
        pytest.raises(StoreWriteTimeoutError),
    ):
        await store.async_save(book, T0)
    release.set()  # the write itself is not cut off, let it end


@pytest.mark.parametrize("kind", ["working", "history"])
async def test_read_back_within_the_limit(
    hass: HomeAssistant, hass_storage: dict, kind: str
) -> None:
    """Reading back counts towards the same limit as the write."""
    inner, write = confirmed_write(hass, kind)

    async def slow_load() -> None:
        await asyncio.sleep(10)

    with (
        patch("custom_components.message_center.store.SAVE_TIMEOUT", 0.01),
        patch.object(inner, "async_load", slow_load),
        pytest.raises(StoreWriteTimeoutError),
    ):
        async with asyncio.timeout(2):
            await write()


@pytest.mark.parametrize("kind", ["working", "history"])
@pytest.mark.parametrize(
    "error", [HomeAssistantError("unreadable"), OSError(5, "Input/output error")]
)
async def test_read_back_error_raises(
    hass: HomeAssistant, hass_storage: dict, kind: str, error: Exception
) -> None:
    """A file that cannot be read back is not a confirmed write.

    Home Assistant raises HomeAssistantError when it cannot read the file,
    which is what a failing disk does right after the write.
    """
    inner, write = confirmed_write(hass, kind)
    with (
        patch.object(inner, "async_load", side_effect=error),
        pytest.raises(StoreNotWritableError),
    ):
        await write()


async def test_save_error_passed_on_by_home_assistant_raises(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    """An error that Home Assistant's ``async_save`` itself raises is reported.

    Home Assistant passes on only what happens before the file is written (the
    ``.storage`` folder cannot be created). The errors of the write itself are
    swallowed there; the tests below cover those.
    """
    book = MessageBook()
    store = MessageStore(hass)

    async def broken_save(_data: Any) -> None:
        raise OSError("disk full")

    with (
        patch.object(store._store, "async_save", broken_save),
        pytest.raises(StoreNotWritableError),
    ):
        await store.async_save(book, T0)


@pytest.mark.parametrize("error", [WriteError, SerializationError])
async def test_save_error_swallowed_by_home_assistant_raises(
    hass: HomeAssistant, hass_storage: dict, error: type[Exception]
) -> None:
    """A write that Home Assistant only logs is still reported as not writable."""
    store = MessageStore(hass)
    with failing_writes(error=error), pytest.raises(StoreNotWritableError):
        await store.async_save(MessageBook(), T0)
    assert STORAGE_KEY not in hass_storage


async def test_save_confirms_its_own_write(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    """An older file with the same time does not pass for the failed write."""
    book = MessageBook(salt=SALT)
    store = MessageStore(hass)
    await store.async_save(book, T0)
    first = dict(hass_storage[STORAGE_KEY]["data"])
    book.accept(
        origin="automation.klima", key="T", title="T", message="M", priority=1, now=T0
    )
    with failing_writes(), pytest.raises(StoreNotWritableError):
        await store.async_save(book, T0)
    assert hass_storage[STORAGE_KEY]["data"] == first
    assert first["saved_at"] == T0.isoformat()

    await store.async_save(book, T0)  # writable again: the next write counts
    assert list(hass_storage[STORAGE_KEY]["data"]["messages"]) == [mid("T")]


async def test_save_while_stopping_is_left_to_the_final_write(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    """While Home Assistant stops it writes once at the end; that is no failure."""
    hass.set_state(CoreState.stopping)
    await MessageStore(hass).async_save(MessageBook(), T0)
    assert STORAGE_KEY not in hass_storage


async def test_pending_history_is_saved_with_the_book(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    """End states not yet in the history store survive in the working store."""
    book = MessageBook(salt=SALT)  # the end state is one of this book's
    ended = ended_message()
    book.history.append(ended)
    await MessageStore(hass).async_save(book, T0)

    other = MessageBook()
    await MessageStore(hass).async_load(other)
    assert other.history == [ended]


async def test_load_store_without_the_newer_fields(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    """A file of 0.10.5 loads: every old field unchanged, the new ones with defaults.

    The file is a fixed one in the format of 0.10.5, not derived from what
    the book writes today. It is version 1 and goes through the migration:
    messages and spacing come back under the salted id, which the message
    now carries as a field; the mark of a message from an own effect takes
    its default. The history store keeps its version; its entries without
    an id load as they are.
    """
    old = store_0_10_5(T0)
    assert "write_id" not in old
    assert "pending_history" not in old
    hass_storage[STORAGE_KEY] = stored(STORAGE_KEY, old)
    old_entry = {k: v for k, v in entry("old").items() if k != "id"}
    hass_storage[HISTORY_KEY] = stored(HISTORY_KEY, {"entries": [old_entry]})

    other = MessageBook()
    store = MessageStore(hass)
    assert await store.async_load(other) == T0
    ids = [other.message_id("unknown", key) for key in ("Lüften: Bad", "Feuchte: Büro")]
    assert list(other.messages) == ids
    assert [m.to_dict() for m in other.messages.values()] == [
        {**raw, "from_effect": False, "id": new_id}
        for raw, new_id in zip(old["messages"].values(), ids, strict=True)
    ]
    assert list(other.spacing) == ids[:1]
    assert list(store.extra["unknown"]) == ["unknown:Feuchte: Büro"]
    assert other.history == []
    assert hass_storage[STORAGE_KEY]["version"] == STORAGE_VERSION == 2
    history = HistoryStore(hass)
    await history.async_load()
    assert history.entries == [old_entry]
    assert hass_storage[HISTORY_KEY]["version"] == 1


async def test_migration_from_version_1_rekeys_salts_and_keeps_the_rest(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    """Version 1 becomes version 2 in one step; nothing but the keys changes.

    Messages, spacing and the pending history are keyed anew under the
    salted id, the spacing with them (else the spacing would not hold once
    after the update), and the salt is kept in the store. A spacing entry
    whose message is gone is split at the first ':' only: an origin has
    none, a key may. Rules, the unknown pairs (keyed origin:title, no
    message id), saved_at and the write mark come over as they are.
    """
    old = store_0_10_5(T0)
    pending = {k: v for k, v in old["messages"]["unknown:Lüften: Bad"].items()}
    old["pending_history"] = [pending]
    old["spacing"]["automation.klima:Außenluft: Büro"] = T0.isoformat()
    old["write_id"] = "0123456789abcdef0123456789abcdef"
    hass_storage[STORAGE_KEY] = stored(STORAGE_KEY, old)

    book = MessageBook()
    store = MessageStore(hass)
    assert await store.async_load(book) == T0
    written = hass_storage[STORAGE_KEY]
    assert written["version"] == 2
    data = written["data"]
    salt = data["id_salt"]
    assert len(salt) == 32 and salt == book.salt
    ids = {
        key: message_id(salt, "unknown", key)
        for key in ("Lüften: Bad", "Feuchte: Büro")
    }
    assert all(":" not in new_id and "|" not in new_id for new_id in ids.values())
    assert data["messages"] == {
        ids[key]: {**raw, "id": ids[key]}
        for key, raw in zip(ids, old["messages"].values(), strict=True)
    }
    assert data["spacing"] == {
        ids["Lüften: Bad"]: old["spacing"]["unknown:Lüften: Bad"],
        message_id(salt, "automation.klima", "Außenluft: Büro"): T0.isoformat(),
    }
    assert data["pending_history"] == [{**pending, "id": ids["Lüften: Bad"]}]
    for key in ("rules", "extra", "saved_at", "write_id"):
        assert data[key] == old[key], key
    assert book.history == [{**pending, "id": ids["Lüften: Bad"]}]
    assert book.spacing_until(book.messages[ids["Lüften: Bad"]]) is not None
    assert all(msg.from_effect is False for msg in book.messages.values())


async def test_malformed_store_of_version_1_is_not_readable(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    """What the migration cannot read is "not readable", not a crash; the file stays."""
    bad = stored(STORAGE_KEY, {"messages": {"unknown:x": {"title": "x"}}})
    hass_storage[STORAGE_KEY] = bad
    with pytest.raises(StoreNotReadableError, match="unexpected format"):
        await MessageStore(hass).async_load(MessageBook())
    assert hass_storage[STORAGE_KEY] == bad


async def test_history_entries_are_checked_when_loaded(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    """A broken history entry is "not readable" with a reason, not a start failure."""
    hass_storage[HISTORY_KEY] = stored(
        HISTORY_KEY, {"entries": [entry("fine"), {"origin": "x.y", "key": "k"}]}
    )
    with pytest.raises(StoreNotReadableError, match="unexpected format"):
        await HistoryStore(hass).async_load()


async def test_real_write_error_is_reported_and_the_file_stays(
    hass: HomeAssistant, real_storage: Path
) -> None:
    """A full disk, through Home Assistant's own writer and reader.

    Nothing is replaced here: the write fails where it fails on a real
    system, Home Assistant logs it and returns, and the read back takes the
    file from the disk.
    """
    path = real_storage / STORAGE_KEY
    store = MessageStore(hass)
    await store.async_save(MessageBook(), T0)
    first = path.read_bytes()
    assert json.loads(first)["data"]["write_id"]

    with (
        patch("os.replace", side_effect=OSError(28, "No space left on device")),
        pytest.raises(StoreNotWritableError, match="write not confirmed"),
    ):
        await store.async_save(book_with("T"), T0)
    assert path.read_bytes() == first

    await store.async_save(book_with("T"), T0)  # writable again
    assert list(json.loads(path.read_bytes())["data"]["messages"]) == [mid("T")]
    other = MessageBook()
    assert await MessageStore(hass).async_load(other) == T0
    assert list(other.messages) == [mid("T")]


async def test_real_first_write_fails_without_a_file(
    hass: HomeAssistant, real_storage: Path
) -> None:
    """No file yet and the disk is full: not confirmed, and no file appears."""
    store = MessageStore(hass)
    with (
        patch("os.replace", side_effect=OSError(28, "No space left on device")),
        pytest.raises(StoreNotWritableError),
    ):
        await store.async_save(MessageBook(), T0)
    assert not (real_storage / STORAGE_KEY).exists()

    history = HistoryStore(hass)
    history.add([entry("a")])
    with (
        patch("os.replace", side_effect=OSError(28, "No space left on device")),
        pytest.raises(StoreNotWritableError),
    ):
        await history.async_flush()
    assert not (real_storage / HISTORY_KEY).exists()
    await history.async_flush()
    written = json.loads((real_storage / HISTORY_KEY).read_bytes())
    assert written["data"]["entries"] == [entry("a")]


async def test_late_write_cannot_overwrite_a_newer_one(
    hass: HomeAssistant, real_storage: Path
) -> None:
    """A write that hung past the limit ends before a later one starts.

    The limit ends the waiting, not the thread that writes. Were the next
    write let through at once, the old one could finish afterwards and put
    its older book over a write that was confirmed.
    """
    store = MessageStore(hass)
    write = store._store._write_prepared_data
    gate = threading.Event()
    first_done = threading.Event()
    calls = 0

    def hang_first(mode: str, json_data: str | bytes) -> None:
        nonlocal calls
        calls += 1
        if calls > 1:
            write(mode, json_data)
            return
        gate.wait(5)
        write(mode, json_data)
        first_done.set()

    try:
        with patch.object(store._store, "_write_prepared_data", hang_first):
            with (
                patch("custom_components.message_center.store.SAVE_TIMEOUT", 0.05),
                pytest.raises(StoreWriteTimeoutError),
            ):
                await store.async_save(book_with("older"), T0)
            newer = hass.async_create_task(store.async_save(book_with("newer"), T0))
            await asyncio.sleep(0.05)
            gate.set()
            await newer
            assert await hass.async_add_executor_job(first_done.wait, 5)
    finally:
        gate.set()
    written = json.loads((real_storage / STORAGE_KEY).read_bytes())
    assert list(written["data"]["messages"]) == [mid("newer")]


async def test_history_add_prune_and_flush(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    """Entries are kept for the retention and written on flush."""
    history = HistoryStore(hass)
    await history.async_load()
    assert history.entries == []

    old = entry("old", ended_at=(T0 - timedelta(days=40)).isoformat())
    new = entry("new", ended_at=(T0 - timedelta(days=5)).isoformat())
    history.add([old, new])
    assert history.prune(T0, retention_days=30) == 1
    assert [e["key"] for e in history.entries] == ["new"]

    await history.async_flush()
    assert hass_storage[HISTORY_KEY]["data"]["entries"] == [new]

    again = HistoryStore(hass)
    await again.async_load()
    assert again.entries == [new]


async def test_history_flush_reports_a_swallowed_write_error(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    """The immediate write of the history is confirmed like the working store's."""
    history = HistoryStore(hass)
    history.add([entry("a")])
    with failing_writes(), pytest.raises(StoreNotWritableError):
        await history.async_flush()
    assert HISTORY_KEY not in hass_storage
    assert history.entries == [entry("a")]  # still there for the next attempt

    await history.async_flush()
    assert hass_storage[HISTORY_KEY]["data"]["entries"] == [entry("a")]


async def test_history_add_replaces_an_entry_handed_over_twice(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    """The same generation of a message is in the history once (after a crash).

    Known by the id where an entry has one, else by origin, key, generation
    and acceptance, as entries written before the id are. Only the fallback
    is told apart here: in one book the same id means the same origin and
    key, so the branch by id cannot give another answer than the fallback.
    """
    history = HistoryStore(hass)
    history.add([entry("a"), entry("b")])
    history.add([entry("a", state="delivered"), entry("a", generation=2)])
    assert history.entries == [
        entry("a", state="delivered"),
        entry("b"),
        entry("a", generation=2),
    ]
    without = {k: v for k, v in entry("c").items() if k != "id"}
    history.add([without, {**without, "state": "failed"}])
    assert history.entries[-1] == {**without, "state": "failed"}
    assert len(history.entries) == 4


async def test_history_limit(hass: HomeAssistant, hass_storage: dict) -> None:
    """Above the maximum the oldest entries are dropped and the store notes it."""
    history = HistoryStore(hass)
    history.add([{"key": str(i), "ended_at": T0.isoformat()} for i in range(3)])
    with patch("custom_components.message_center.store.HISTORY_MAX_ENTRIES", 2):
        history.add([{"key": "x", "ended_at": T0.isoformat()}])
    assert len(history.entries) == 2
    assert history.truncated
    assert HISTORY_MAX_ENTRIES == 20_000


def test_from_effect_survives_the_round_trip_and_defaults_to_false() -> None:
    """The mark of a message from an own effect is stored; old entries load without."""
    raw = ended_message()
    assert raw["from_effect"] is False
    msg = Message.from_dict({**raw, "from_effect": True})
    assert msg.from_effect is True
    assert Message.from_dict(msg.to_dict()).from_effect is True
    del raw["from_effect"]
    assert Message.from_dict(raw).from_effect is False
