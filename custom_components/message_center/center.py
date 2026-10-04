"""Runtime of the message center: intake, rules, delivery, stores, Home Assistant.

One instance per config entry. Every change to the book runs under one lock
and is written to the store before the caller gets an answer.
Pushes run outside the lock in tracked tasks; their results are recorded
under the lock again. The order is always the same: decide and
reserve the recipients under the lock, write the store, then push at once,
before issues, timer and listeners are looked after. So "sending" is on disk
before the first push leaves, and a restart in between finds the message and
marks it unclear instead of sending it again.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
import contextlib
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import (
    ACTION_ALARM_OFF,
    ACTION_FORWARD,
    ACTION_SNOOZE,
    ALARM_SETTLE_SECONDS,
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
    CONF_HIDE_TITLES,
    CONF_HISTORY_DAYS,
    CONF_LIGHT_SPACING,
    CONF_LIGHTS,
    CONF_LIGHTS_ALWAYS,
    CONF_PULSE_MS,
    CONF_RECIPIENTS,
    CONF_SILENT_REPEAT,
    CONF_SNOOZE_INPUT,
    CONF_SNOOZE_MINUTES,
    CONF_SNOOZE_MINUTES_2,
    CONF_TAP_TARGET,
    DEFAULT_ALARM_CHANNEL,
    DEFAULT_ALARM_INTERVAL_MS,
    DEFAULT_ALARM_MAX_SECONDS,
    DEFAULT_ALARM_TEST_SECONDS,
    DEFAULT_HISTORY_DAYS,
    DEFAULT_LIGHT_SPACING,
    DEFAULT_PULSE_MS,
    DEFAULT_SNOOZE_MINUTES,
    DEFAULT_TAP_TARGET,
    DEFAULT_TITLE,
    DOMAIN,
    EVENT_DELIVERED,
    EVENT_DISCARDED,
    EVENT_FORWARDED,
    EVENT_NOTIFICATION_ACTION,
    EVENT_SNOOZED,
    HOUSEKEEPING_INTERVAL,
    LIGHT_TIMEOUT,
    MAX_EFFECT_CONTEXTS,
    MAX_SEEN_TITLES,
    MAX_UNKNOWN,
    PANEL_URL_PATH,
    PLATFORM_ANDROID,
    RECIPIENT_REPAIR_AFTER,
    SCRIPT_TIMEOUT,
    SNOOZE_MINUTES_MAX,
    STORE_RETRY_INTERVAL,
    SUBENTRY_GROUP,
    SUBENTRY_KIND,
    SUBENTRY_RULE,
    TAP_TARGET_CENTER,
    TAP_TARGETS,
    TEST_ORIGIN,
    TITLE_MAX_LENGTH,
)
from .delivery import (
    Recipient,
    async_push,
    async_push_tts,
    error_trace,
    phone_user_id,
)
from .kinds import Group, Kind, match_kind
from .lifecycle import (
    RULE_REASONS,
    AcceptAction,
    Attempt,
    Decision,
    MessageBook,
    NotFoundError,
    StoreFullError,
)
from .models import (
    DISTURBED_STATES,
    Message,
    MessageState,
    RecipientState,
)
from .origin import Origin, resolve_origin
from .rules import Effect, RuleBook, RuleConfig
from .store import (
    HistoryStore,
    MessageStore,
    StoreNotWritableError,
    StoreWriteTimeoutError,
)
from .texts import (
    button_texts,
    duration_text,
    failing_text,
    reason_text,
    test_texts,
    unclassified_note,
)

_LOGGER = logging.getLogger(__name__)

type MessageCenterConfigEntry = ConfigEntry[MessageCenter]

ISSUE_STORE = "store_not_writable"
ISSUE_HISTORY = "history_not_writable"
ISSUE_STORE_FULL = "store_full"
ISSUE_UNCLEAR = "unclear_messages"
NOTIFICATION_FAILED = f"{DOMAIN}_failed_deliveries"


class NotReadyError(Exception):
    """The center cannot accept messages."""


class PriorityNotAllowedError(Exception):
    """Priority 3 via ``send`` is not enabled in the options."""


def rule_from_subentry(subentry_id: str, data: dict[str, Any]) -> RuleConfig:
    """Build a delivery rule from a config subentry."""
    return RuleConfig(
        rule_id=subentry_id,
        name=data["name"],
        entity_id=data["entity_id"],
        state=data["state"],
        max_hours=int(data.get("max_hours", 12)),
        effects={
            1: Effect(data.get("effect_1", Effect.HOLD)),
            2: Effect(data.get("effect_2", Effect.HOLD)),
            3: Effect(data.get("effect_3", Effect.PASS)),
        },
    )


class MessageCenter:
    """The running message center of one config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Create the runtime; nothing is loaded until ``async_start``."""
        self.hass = hass
        self.entry = entry
        self.book = MessageBook()
        self.rules = RuleBook()
        self.store = MessageStore(hass)
        self.history = HistoryStore(hass)
        self.recipients: list[Recipient] = []
        self.kinds: dict[str, Kind] = {}
        self.groups: dict[str, Group] = {}
        self.unknown: dict[str, dict[str, Any]] = {}
        self.history_days = DEFAULT_HISTORY_DAYS
        self.hide_titles = False
        self.allow_alarm = False
        self.lights: list[str] = []
        self.lights_always: list[str] = []  # pulse even when off
        self.forward_script: str | None = None  # runs when a message is forwarded
        self.effect_scripts: dict[int, str] = {}  # priority -> script entity
        self.light_enabled = True  # the switch "light pulse"
        self.pulse_ms = DEFAULT_PULSE_MS
        self.light_spacing = DEFAULT_LIGHT_SPACING
        self._last_light: datetime | None = None
        self.alarm_lights: list[str] = []
        self.alarm_interval_ms = DEFAULT_ALARM_INTERVAL_MS
        self.alarm_max_seconds = DEFAULT_ALARM_MAX_SECONDS
        self.alarm_test_seconds = DEFAULT_ALARM_TEST_SECONDS
        self.alarm_channel = DEFAULT_ALARM_CHANNEL
        self.alarm_tts = False
        self.alarm_until: datetime | None = None  # alarm light running until
        self._alarm_task: asyncio.Task[None] | None = None
        self.button_snooze = True
        self.button_forward = True
        self.silent_repeat = False  # repeats: replace without sound
        self.snooze_minutes = DEFAULT_SNOOZE_MINUTES
        self.snooze_minutes_2 = 0  # second "later" button, 0 = none
        self.snooze_input = False  # typed minutes instead of fixed durations
        self.tap_target = DEFAULT_TAP_TARGET  # what a tap on the push opens
        self.ready = False
        self.ready_reason = "starting"
        self.last_delivery: tuple[datetime, str, str] | None = None
        self.delivered_today = 0
        self._lock = asyncio.Lock()
        self._pending: list[Attempt] = []  # reserved under the lock, not yet pushed
        self._listeners: list[CALLBACK_TYPE] = []
        self._delivered_listeners: list[Callable[[dict[str, Any]], None]] = []
        self._unsub: list[CALLBACK_TYPE] = []
        self._unsub_rules: CALLBACK_TYPE | None = None
        self._timer: CALLBACK_TYPE | None = None
        self._timer_at: datetime | None = None
        self._recipient_issues: set[str] = set()
        # ids of the contexts the center acts under itself, see _own_effect
        self._effect_contexts: dict[str, None] = {}
        self._commits = 0  # finished write attempts, see _async_require_ready
        # next write the store is owed: not writable, or an intake taken back
        self._store_retry: datetime | None = None
        self._store_hangs = False  # the last write ran into the time limit
        self._history_failing = False  # the last write of the history failed
        self._history_dropped = 0  # pending end states dropped, as far as logged
        self._stopped = False  # after ``async_stop``: nothing is written or started
        self.language = hass.config.language

    # ----- lifecycle ---------------------------------------------------------

    async def async_start(self) -> None:
        """Load stores, reconcile after the start and begin watching."""
        self.load_config()
        saved_at = await self.store.async_load(self.book, self.rules)
        self.unknown = dict(self.store.extra.get("unknown", {}))
        await self.history.async_load()
        # left pending by a restart: into the history now; a history the center
        # before could not write is written once, so that its issue goes
        if self.book.history or ir.async_get(self.hass).async_get_issue(
            DOMAIN, ISSUE_HISTORY
        ):
            async with self._lock:
                await self._async_write_history()
        now = dt_util.utcnow()
        self._restore_delivery_stats(now)
        # read, then follow at once: a change while the book below is written
        # waits for the lock and is not missed
        self._observe_rule_entities(now)
        self._track_rule_entities()
        try:
            self.book.on_restart(now, saved_at)
            self.ready = True
            self.ready_reason = "ready"
            async with self._lock:
                self._reevaluate_open(now)
                await self._commit(now, raise_error=False)
                self._launch_pending()
                self._update_issues(now)
        except BaseException:
            # not started, never stopped: a change must not reach this center
            self._untrack_rule_entities()
            raise

        self._unsub.append(
            async_track_time_interval(
                self.hass, self._on_housekeeping, HOUSEKEEPING_INTERVAL
            )
        )
        self._unsub.append(
            self.hass.bus.async_listen(
                EVENT_NOTIFICATION_ACTION, self._on_notification_action
            )
        )
        self._schedule()

    def _restore_delivery_stats(self, now: datetime) -> None:
        """Rebuild "last delivery" and "delivered today" from the stores.

        Counted is one delivery per message delivered today; repeated cycles
        of the same message before the restart are not stored separately.
        """
        today = dt_util.as_local(now).date()
        latest: tuple[datetime, str, str] | None = None
        count = 0
        messages = [
            *self.book.messages.values(),
            *(self.history_message(e) for e in self.history.entries),
        ]
        for msg in messages:
            at = msg.delivered_at
            if at is None:
                continue
            if dt_util.as_local(at).date() == today:
                count += 1
            if latest is None or at > latest[0]:
                latest = (at, msg.origin_name or msg.origin, self.display_title(msg))
        self.last_delivery = latest
        self.delivered_today = count

    async def async_stop(self) -> None:
        """Stop timers, end a running alarm light and write the history.

        A push that is out stays out; its task is not waited for. One that
        comes back before the flag below is set still counts: it is recorded
        and written. From the flag on this center writes, schedules, starts
        and acts no more: the store belongs to the center that follows,
        which finds the message as sending and shows it as unclear.
        A caller that waits for the lock behind the stop is rejected
        (``_require_running``).
        """
        await self.async_stop_alarm()
        for unsub in self._unsub:
            unsub()
        self._unsub.clear()
        self._untrack_rule_entities()
        self._cancel_timer()
        async with self._lock:
            pending = bool(self.book.history)
            if await self._async_write_history() and pending:
                await self._commit(dt_util.utcnow(), raise_error=False)
            self._stopped = True
        # a push back while the alarm light above was ended, or while the
        # lock was held, may have armed the timer or started the light again
        self._cancel_timer()
        await self.async_stop_alarm()

    def load_config(self) -> None:
        """Read recipients, kinds, groups, rules and options from the config entry."""
        self.recipients = [
            Recipient.from_dict(item)
            for item in self.entry.data.get(CONF_RECIPIENTS, [])
        ]
        options = self.entry.options
        self.history_days = int(options.get(CONF_HISTORY_DAYS, DEFAULT_HISTORY_DAYS))
        self.hide_titles = bool(options.get(CONF_HIDE_TITLES, False))
        self.allow_alarm = bool(options.get(CONF_ALLOW_ALARM, False))
        self.lights_always = [str(e) for e in options.get(CONF_LIGHTS_ALWAYS, [])]
        # "always" marks lamps of the list; one saved without its lamp in
        # the list by an older page belongs to the lamps as well
        self.lights = list(
            dict.fromkeys(
                [*(str(e) for e in options.get(CONF_LIGHTS, [])), *self.lights_always]
            )
        )
        self.forward_script = str(options.get(CONF_FORWARD_SCRIPT) or "") or None
        self.effect_scripts = {
            n: str(options[key])
            for n, key in enumerate(CONF_EFFECT_SCRIPTS, start=1)
            if options.get(key)
        }
        self.pulse_ms = int(options.get(CONF_PULSE_MS, DEFAULT_PULSE_MS))
        self.light_spacing = int(options.get(CONF_LIGHT_SPACING, DEFAULT_LIGHT_SPACING))
        self.alarm_lights = [str(e) for e in options.get(CONF_ALARM_LIGHTS, [])]
        self.alarm_interval_ms = int(
            options.get(CONF_ALARM_INTERVAL_MS, DEFAULT_ALARM_INTERVAL_MS)
        )
        self.alarm_max_seconds = int(
            options.get(CONF_ALARM_MAX_SECONDS, DEFAULT_ALARM_MAX_SECONDS)
        )
        self.alarm_test_seconds = int(
            options.get(CONF_ALARM_TEST_SECONDS, DEFAULT_ALARM_TEST_SECONDS)
        )
        self.alarm_channel = str(options.get(CONF_ALARM_CHANNEL, DEFAULT_ALARM_CHANNEL))
        self.alarm_tts = bool(options.get(CONF_ALARM_TTS, False))
        self.button_snooze = bool(options.get(CONF_BUTTON_SNOOZE, True))
        self.silent_repeat = bool(options.get(CONF_SILENT_REPEAT, False))
        self.button_forward = bool(options.get(CONF_BUTTON_FORWARD, True))
        self.snooze_minutes = int(
            options.get(CONF_SNOOZE_MINUTES, DEFAULT_SNOOZE_MINUTES)
        )
        self.snooze_minutes_2 = int(options.get(CONF_SNOOZE_MINUTES_2, 0))
        self.snooze_input = bool(options.get(CONF_SNOOZE_INPUT, False))
        tap_target = str(options.get(CONF_TAP_TARGET, DEFAULT_TAP_TARGET))
        self.tap_target = (
            tap_target if tap_target in TAP_TARGETS else DEFAULT_TAP_TARGET
        )
        kinds: dict[str, Kind] = {}
        groups: dict[str, Group] = {}
        rules: list[RuleConfig] = []
        for order, (subentry_id, subentry) in enumerate(self.entry.subentries.items()):
            data = dict(subentry.data)
            if subentry.subentry_type == SUBENTRY_KIND:
                kinds[subentry_id] = Kind.from_dict(subentry_id, data, order)
            elif subentry.subentry_type == SUBENTRY_GROUP:
                groups[subentry_id] = Group.from_dict(subentry_id, data)
            elif subentry.subentry_type == SUBENTRY_RULE:
                rules.append(rule_from_subentry(subentry_id, data))
        self.kinds = kinds
        self.groups = groups
        self.rules.configure(rules)
        self._drop_known_unknowns()

    async def async_reload_config(self) -> None:
        """Apply changed kinds, groups, rules or options without a restart."""
        async with self._lock:
            self.load_config()
            now = dt_util.utcnow()
            self._observe_rule_entities(now)
            self._track_rule_entities()
            self._reevaluate_open(now)
            await self._commit(now, raise_error=False)
            self._launch_pending()
            self._update_issues(now)
            self._schedule()
            self._notify()

    def _observe_rule_entities(self, now: datetime) -> None:
        for rule in self.rules.rules.values():
            state = self.hass.states.get(rule.entity_id)
            self.rules.observe(rule.rule_id, state.state if state else None, now)

    def _track_rule_entities(self) -> None:
        self._untrack_rule_entities()
        entity_ids = sorted({rule.entity_id for rule in self.rules.rules.values()})
        if entity_ids:
            self._unsub_rules = async_track_state_change_event(
                self.hass, entity_ids, self._on_rule_state
            )

    def _untrack_rule_entities(self) -> None:
        if self._unsub_rules:
            self._unsub_rules()
            self._unsub_rules = None

    # ----- listeners ---------------------------------------------------------

    @callback
    def add_listener(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Register a callback for any change; returns the unsubscribe function."""
        self._listeners.append(listener)

        @callback
        def _remove() -> None:
            self._listeners.remove(listener)

        return _remove

    @callback
    def add_delivered_listener(
        self, listener: Callable[[dict[str, Any]], None]
    ) -> CALLBACK_TYPE:
        """Register a callback for delivered events (event entity)."""
        self._delivered_listeners.append(listener)

        @callback
        def _remove() -> None:
            self._delivered_listeners.remove(listener)

        return _remove

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    # ----- queries for entities, list and the page --------------------------

    @property
    def missing_recipients(self) -> list[str]:
        """Configured recipients whose notify action does not exist right now."""
        return [
            r.action
            for r in self.recipients
            if not self.hass.services.has_service("notify", r.action)
        ]

    def kind_name(self, msg: Message) -> str | None:
        """Name of the message's kind, if it still exists."""
        kind = self.kinds.get(msg.kind_id) if msg.kind_id else None
        return kind.name if kind else None

    def group_name(self, msg: Message) -> str | None:
        """Name of the message's group, if it still exists."""
        group = self.groups.get(msg.group_id) if msg.group_id else None
        return group.name if group else None

    def display_title(self, msg: Message) -> str:
        """Title for attributes and logbook, or origin/kind when titles are hidden."""
        if self.hide_titles:
            return f"{msg.origin}/{self.kind_name(msg) or 'unknown'}"
        return msg.title

    def message_summary(
        self, msg: Message, *, with_error: bool = False
    ) -> dict[str, Any]:
        """Attribute entry for one message (no text)."""
        item: dict[str, Any] = {
            "message_id": msg.id,
            "origin": msg.origin,
            "origin_name": msg.origin_name,
            "kind": self.kind_name(msg),
            "group": self.group_name(msg),
            "priority": msg.priority,
            "title": self.display_title(msg),
            "state": msg.state.value,
            "count": msg.count,
            "since": msg.accepted_at.isoformat(),
            "reason": reason_text(msg.reason, self.language),
            "until": msg.reason.until.isoformat() if msg.reason.until else None,
            # a retry a rule holds back has no time at which something happens:
            # it goes out when the rule ends, which stands in "until"
            "next_try": msg.next_try.isoformat()
            if msg.next_try and msg.reason.kind not in RULE_REASONS
            else None,
            "failed_recipients": msg.failed_recipients,
        }
        if with_error:
            errors = {
                name: status.last_error
                for name, status in msg.recipients.items()
                if status.last_error
            }
            item["last_error"] = errors or None
        return item

    def message_detail(self, msg: Message) -> dict[str, Any]:
        """Full entry with text for admins (list and page)."""
        item = self.message_summary(msg, with_error=True)
        item.update(
            {
                "title": msg.title,
                "message": msg.message,
                "data": msg.data,
                "labels": msg.labels,
                "generation": msg.generation,
                "revision": msg.revision,
                "accepted_at": msg.accepted_at.isoformat(),
                "updated_at": msg.updated_at.isoformat(),
                "delivered_at": msg.delivered_at.isoformat()
                if msg.delivered_at
                else None,
                "ended_at": msg.ended_at.isoformat() if msg.ended_at else None,
                "forwarded_at": msg.forwarded_at.isoformat()
                if msg.forwarded_at
                else None,
                "expires_at": msg.expires_at.isoformat() if msg.expires_at else None,
                "spacing": msg.spacing,
                "no_hold": msg.no_hold,
                "kind_id": msg.kind_id,
                "group_id": msg.group_id,
                "events": list(msg.events),
                "recipients": {
                    name: {
                        "state": status.state.value,
                        "last_error": status.last_error,
                        "attempts": status.attempts,
                        "next_try": status.next_try.isoformat()
                        if status.next_try
                        else None,
                        "delivered_at": status.delivered_at.isoformat()
                        if status.delivered_at
                        else None,
                    }
                    for name, status in msg.recipients.items()
                },
            }
        )
        return item

    def open_messages(self) -> list[Message]:
        """Open messages, oldest first."""
        return self.book.open()

    def disturbed_messages(self) -> list[Message]:
        """Messages in retrying, unclear or failed (within retention)."""
        return sorted(
            (m for m in self.book.messages.values() if m.state in DISTURBED_STATES),
            key=lambda m: m.accepted_at,
        )

    def recent_messages(self) -> list[Message]:
        """Return ended messages still in the working store, newest first."""
        return sorted(
            (m for m in self.book.messages.values() if not m.is_open),
            key=lambda m: m.ended_at or m.accepted_at,
            reverse=True,
        )

    def unknown_items(self) -> list[dict[str, Any]]:
        """Unknown origin/title pairs, most recent first."""
        return sorted(self.unknown.values(), key=lambda u: u["last_seen"], reverse=True)

    # ----- titles seen, for assigning kinds on the page ---------------------

    def _seen_records(
        self, *, with_new: bool
    ) -> Iterator[tuple[str, str | None, str, datetime | str | None]]:
        """Origin, origin name, title and last arrival of every message held.

        From the working store, the pending history and the history; with
        ``with_new`` also the pairs of "new". The arrival of a stored entry
        is left as text; ``_seen_at`` reads it where the order matters.
        """
        for msg in self.book.messages.values():
            yield msg.origin, msg.origin_name, msg.title, msg.updated_at
        for entry in (*self.book.history, *self.history.entries):
            yield (
                entry["origin"],
                entry.get("origin_name"),
                entry["title"],
                entry.get("updated_at") or entry.get("accepted_at"),
            )
        if with_new:
            for item in self.unknown.values():
                yield (
                    item["origin"],
                    item.get("origin_name"),
                    item["title"],
                    item.get("last_seen"),
                )

    @staticmethod
    def _seen_at(value: datetime | str | None) -> datetime:
        """Time of a record; one that cannot be read counts as oldest."""
        if isinstance(value, datetime):
            return value
        return (value and dt_util.parse_datetime(value)) or datetime.min.replace(
            tzinfo=dt_util.UTC
        )

    def seen_pairs(self) -> list[dict[str, Any]]:
        """Origin/title pairs of the stored messages, newest first, each once.

        From the working store, the pending history and the history. A title
        counts without regard to case and is given as it arrived last; the
        origin's name is the latest one known.
        """
        pairs: dict[tuple[str, str], dict[str, Any]] = {}
        for origin, name, title, raw in self._seen_records(with_new=False):
            at = self._seen_at(raw)
            pair = pairs.get((origin, title.casefold()))
            if pair is None:
                pairs[(origin, title.casefold())] = {
                    "origin": origin,
                    "origin_name": name,
                    "title": title,
                    "at": at,
                }
            elif at > pair["at"]:
                pair.update(title=title, at=at, origin_name=name or pair["origin_name"])
            elif pair["origin_name"] is None:
                pair["origin_name"] = name
        ordered = sorted(pairs.values(), key=lambda p: p["at"], reverse=True)
        return [
            {
                "origin": p["origin"],
                "origin_name": p["origin_name"],
                "title": p["title"],
                "last_seen": p["at"].isoformat(),
            }
            for p in ordered
        ]

    def seen_titles(self, origin: str, limit: int = MAX_SEEN_TITLES) -> list[str]:
        """Different titles of one origin, newest first, at most ``limit``.

        From the working store, the pending history, the history and "new";
        a title counts without regard to case, as it arrived last.
        """
        newest: dict[str, tuple[datetime, str]] = {}
        for found, _name, title, raw in self._seen_records(with_new=True):
            if found != origin:
                continue
            at = self._seen_at(raw)
            key = title.casefold()
            if key not in newest or at > newest[key][0]:
                newest[key] = (at, title)
        ordered = sorted(newest.values(), key=lambda item: item[0], reverse=True)
        return [title for _at, title in ordered[:limit]]

    def title_counts(self, origins: set[str]) -> dict[str, int]:
        """Count the different titles of each origin, as ``seen_titles`` finds them."""
        titles: dict[str, set[str]] = {origin: set() for origin in origins}
        for origin, _name, title, _at in self._seen_records(with_new=True):
            if origin in titles:
                titles[origin].add(title.casefold())
        return {origin: len(found) for origin, found in titles.items()}

    async def async_dismiss_unknown(self, origin: str, title: str) -> bool:
        """Drop one pair from "new, please classify"; it returns if it arrives again.

        The messages themselves stay in the history. Returns False when unknown.
        """
        async with self._lock:
            self._require_running()
            if self.unknown.pop(f"{origin}:{title}", None) is None:
                return False
            await self._commit(dt_util.utcnow(), raise_error=False)
            self._schedule()
            self._notify()
            return True

    def list_messages(self, *, include_history: bool) -> dict[str, Any]:
        """Response of ``list``, with message text for admins."""
        messages = [
            self.message_detail(msg)
            for msg in sorted(self.book.messages.values(), key=lambda m: m.accepted_at)
        ]
        if include_history:
            history = [
                self.message_detail(self.history_message(e))
                for e in self.history.entries
            ]
            return {"messages": messages, "history": history}
        return {"messages": messages}

    def history_message(self, entry: dict[str, Any]) -> Message:
        """Return a history entry as a message; one from before 0.11 gets its id."""
        msg = Message.from_dict(entry)
        if not msg.id:
            msg.id = self.book.message_id(msg.origin, msg.key)
        return msg

    # ----- intake ------------------------------------------------------------

    async def async_intake(
        self,
        *,
        title: str | None,
        message: str,
        context: Context,
        data: dict[str, Any] | None = None,
        kind_id: str | None = None,
        priority: int | None = None,
        key: str | None = None,
    ) -> dict[str, Any]:
        """Take a message from notify or send.

        A message without a title is called after its origin, the
        automation or script that sent it, and "Mitteilung" when the origin
        is not known. Key, id and kind follow that title; a kind made for
        "Mitteilung" before still takes it when no kind matches the new
        title (see ``match_kind``).

        A message that arrives under a context of the center's own effects,
        or under a child of one, was sent by such an effect (a script, an
        automation reacting to a pulsed lamp). It is delivered like any
        other, on the alarm channel too, but starts no effect of its own:
        no script, no light pulse, no alarm light (depth 1).
        """
        await self._async_require_ready()
        origin = resolve_origin(self.hass, context)
        untitled = not title and origin.known and bool(origin.name)
        if not title:
            title = (origin.name if untitled and origin.name else DEFAULT_TITLE)[
                :TITLE_MAX_LENGTH
            ]
        from_effect = (
            context.id in self._effect_contexts
            or context.parent_id in self._effect_contexts
        )
        kind = self.kinds.get(kind_id) if kind_id else None
        if kind is None and not kind_id:
            kind = match_kind(
                list(self.kinds.values()), origin.entity_id, title, untitled=untitled
            )
        effective_priority = kind.priority if kind else (priority or 1)
        if kind is None and priority is not None:
            effective_priority = priority
        if effective_priority >= 3 and kind is None and not self.allow_alarm:
            raise PriorityNotAllowedError
        spacing = kind.spacing if kind else 0
        expires_after = kind.expires_after if kind else 0
        no_hold = kind.no_hold if kind else False
        group_id = kind.group_id if kind else None

        async with self._lock:
            self._require_running()
            now = dt_util.utcnow()
            undo = self.book.snapshot(origin.entity_id, key or title)
            unknown = {k: dict(v) for k, v in self.unknown.items()}
            try:
                result = self.book.accept(
                    origin=origin.entity_id,
                    origin_name=origin.name,
                    labels=origin.labels,
                    key=key or title,
                    title=title,
                    message=message,
                    data=data,
                    priority=effective_priority,
                    kind_id=kind.kind_id if kind else None,
                    group_id=group_id,
                    spacing=spacing,
                    expires_after=expires_after,
                    no_hold=no_hold,
                    now=now,
                    context_id=context.id,
                    user_id=context.user_id,
                    from_effect=from_effect,
                )
            except StoreFullError:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    ISSUE_STORE_FULL,
                    is_fixable=False,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key=ISSUE_STORE_FULL,
                )
                raise
            msg = result.message
            if result.action is AcceptAction.CREATED:
                ir.async_delete_issue(self.hass, DOMAIN, ISSUE_STORE_FULL)
            if kind is None:
                self._note_unknown(origin, title, now)
            verdict = self._verdict(msg, now)
            reserved = len(self._pending)  # what follows is this intake's
            self._act(msg, self.book.evaluate(msg, now, verdict), now)
            if msg.state is MessageState.RETRYING:
                # held back by a rule this arrival passes: due at once
                self._reserve(self.book.begin_attempt(msg, now, verdict))
            try:
                await self._commit(now)
            except StoreNotWritableError as err:
                # nothing goes out, and this one message is taken back; others
                # may be mid-push
                self._drop_pending(reserved)
                self.book.rollback(undo)
                self.unknown = unknown
                self._schedule()  # the center tries the store again by itself
                self._notify()  # show "Ready" off now, not at the next change
                raise NotReadyError("store") from err
            except asyncio.CancelledError:
                # the sender is gone before the write was confirmed: not
                # accepted. The write may still land, so the book is written
                # again by the timer.
                self._drop_pending(reserved)
                self.book.rollback(undo)
                self.unknown = unknown
                self._store_retry = now
                self._schedule()
                raise
            self._launch_pending()
            self._schedule()
            self._notify()

        return {
            "result": "accepted",
            "message_id": msg.id,
            "action": result.action.value,
            "state": msg.state.value,
            "reason": reason_text(msg.reason, self.language),
        }

    def _note_unknown(self, origin: Origin, title: str, now: datetime) -> None:
        key = f"{origin.entity_id}:{title}"
        entry = self.unknown.get(key)
        if entry is None:
            entry = {
                "origin": origin.entity_id,
                "origin_name": origin.name,
                "labels": origin.labels,
                "title": title,
                "count": 0,
                "first_seen": now.isoformat(),
            }
            self.unknown[key] = entry
        entry["count"] += 1
        entry["last_seen"] = now.isoformat()
        if len(self.unknown) > MAX_UNKNOWN:
            oldest = min(self.unknown, key=lambda k: self.unknown[k]["last_seen"])
            del self.unknown[oldest]

    def _drop_known_unknowns(self) -> None:
        """Forget unknown pairs that a kind now matches."""
        kinds = list(self.kinds.values())
        for key, entry in list(self.unknown.items()):
            if match_kind(kinds, entry["origin"], entry["title"]) is not None:
                del self.unknown[key]

    # ----- commands ----------------------------------------------------------

    async def async_discard(
        self,
        *,
        message_id: str | None = None,
        origin: str | None = None,
        title: str | None = None,
        source: str = "action",
        context: Context | None = None,
    ) -> int:
        """Discard open messages; returns how many.

        ``context`` is the one of whoever intervenes (action, phone, page);
        the event carries it. Without one the call counts as an automation.
        """
        await self._async_require_ready()
        context = context or Context()
        async with self._lock:
            self._require_running()
            now = dt_util.utcnow()
            if message_id is not None:
                try:
                    discarded = [self.book.discard(message_id, now)]
                except NotFoundError:
                    discarded = []
            else:
                discarded = self.book.discard_matching(origin or "", title or "", now)
            for msg in discarded:
                msg.add_event("discarded", source, None, now)
                self._fire_intervention(EVENT_DISCARDED, msg, source, context)
            if discarded:
                await self._commit(now, raise_error=False)
                self._schedule()
                self._notify()
        return len(discarded)

    async def async_snooze(
        self,
        message_id: str,
        minutes: int,
        *,
        source: str = "action",
        context: Context | None = None,
    ) -> datetime:
        """Snooze a message; raises NotFoundError.

        ``context`` as in ``async_discard``.
        """
        await self._async_require_ready()
        context = context or Context()
        async with self._lock:
            self._require_running()
            now = dt_util.utcnow()
            msg = self.book.snooze(message_id, minutes, now)
            msg.add_event("snoozed", source, f"{minutes} min", now)
            self._fire_intervention(
                EVENT_SNOOZED, msg, source, context, minutes=minutes
            )
            await self._commit(now, raise_error=False)
            self._schedule()
            self._notify()
            assert msg.snoozed_until is not None
            return msg.snoozed_until

    async def async_send_now(self, message_id: str, *, source: str = "page") -> None:
        """Release a held, unclear or retrying message (page); raises NotFoundError.

        A retry, held back by a rule or planned for later, is pushed now to
        the recipients that are due; the rules are passed over. Unlike
        the other commands it is not rejected while the store cannot be
        written: outside the intake delivery comes first.
        """
        await self._async_require_ready(store_needed=False)
        async with self._lock:
            self._require_running()
            now = dt_util.utcnow()
            msg = self.book.send_now(message_id, now)
            msg.add_event("sent_now", source, None, now)
            if msg.state is MessageState.RETRYING:
                self._reserve(self.book.begin_attempt(msg, now, None))
            else:
                self._act(msg, self.book.evaluate(msg, now, None), now)
            await self._commit(now, raise_error=False)
            self._launch_pending()
            self._schedule()
            self._notify()

    async def async_forward(
        self,
        message_id: str,
        note: str | None,
        context: Context,
        *,
        source: str = "action",
    ) -> None:
        """Hand a message to the assistant; raises NotFoundError.

        The event runs in the context of whoever forwards; the chosen script
        under a context of the center's own below it, so that an answer the
        script sends through the center is known as the center's own effect.
        The event carries the real title and text for the assistant, and
        the title as the attributes show it (``display_title``) for the
        logbook.
        """
        await self._async_require_ready()
        async with self._lock:
            self._require_running()
            now = dt_util.utcnow()
            msg = self.book.forward(message_id, now)
            msg.add_event("forwarded", source, note, now)
            await self._commit(now, raise_error=False)
            self._schedule()
            self._notify()
        self.hass.bus.async_fire(
            EVENT_FORWARDED,
            {
                "message_id": msg.id,
                "origin": msg.origin,
                "origin_name": msg.origin_name,
                "kind": self.kind_name(msg),
                "group": self.group_name(msg),
                "priority": msg.priority,
                "title": msg.title,
                "display_title": self.display_title(msg),
                "message": msg.message,
                "note": note,
                "source": source,
                "user_id": context.user_id,
                "accepted_at": msg.accepted_at.isoformat(),
                "state": msg.state.value,
                "reason": reason_text(msg.reason, self.language),
            },
            context=context,
        )
        if self.forward_script:
            self._launch(
                self._async_run_script(
                    self.forward_script,
                    msg,
                    self._own_effect(self._context_under(context)),
                    note=note,
                    purpose="forward",
                ),
                "forward script",
            )

    def _script_variables(self, msg: Message, note: str | None) -> dict[str, Any]:
        """Variables handed to a chosen script (forward and effect scripts)."""
        return {
            "message_id": msg.id,
            "title": msg.title,
            "text": msg.message,
            "note": note,
            "origin": msg.origin,
            "origin_name": msg.origin_name,
            "kind": self.kind_name(msg),
            "group": self.group_name(msg),
            "priority": msg.priority,
            "count": msg.count,
        }

    async def _async_run_script(
        self,
        entity_id: str,
        msg: Message,
        context: Context,
        *,
        note: str | None = None,
        purpose: str = "effect",
    ) -> str | None:
        """Run a script with the message as variables; failures are noted.

        The script runs in a tracked task with a time limit, so a slow or
        missing script never holds up forwarding or delivery. The outcome is
        recorded under the message: ``script`` or ``script_failed``.
        """
        domain, _, object_id = entity_id.partition(".")
        if domain != "script" or not object_id:
            error: str | None = "not a script"
        else:
            error = None
            try:
                async with asyncio.timeout(SCRIPT_TIMEOUT):
                    await self.hass.services.async_call(
                        "script",
                        object_id,
                        self._script_variables(msg, note),
                        blocking=True,
                        context=context,
                    )
            except TimeoutError:
                error = "Timeout"
            except Exception as err:
                # the class only: the text may carry the message
                error = type(err).__name__
                _LOGGER.warning("Script %s (%s) failed: %s", entity_id, purpose, error)
        await self._async_note(
            msg,
            "script_failed" if error else "script",
            f"{entity_id}: {error}" if error else entity_id,
        )
        return error

    async def _async_note(self, msg: Message, kind: str, detail: str) -> None:
        """Record the outcome of an effect under a message that is still in the book."""
        async with self._lock:
            now = dt_util.utcnow()
            if msg.id in self.book.messages:
                msg.add_event(kind, "center", detail, now)
                await self._commit(now, raise_error=False)
                self._schedule()
                self._notify()

    # ----- evaluation and actions (under lock) -------------------------------

    def _verdict(self, msg: Message, now: datetime) -> Any:
        return self.rules.verdict(msg.priority, now)

    def _act(self, msg: Message, decision: Decision, now: datetime) -> None:
        """Turn a decision into a reserved push or replacement.

        Nothing is started here. The caller writes the store first and calls
        ``_launch_pending`` right after it, so the state a push belongs to is
        on disk before the push leaves and nothing that fails later in
        the call can keep the push back.
        """
        if decision is Decision.SEND:
            self.book.start_cycle(msg, [r.action for r in self.recipients], now)
            self._reserve(self.book.begin_attempt(msg, now))
        elif decision is Decision.REPLACE:
            self._reserve(self.book.begin_replace(msg))

    def _reserve(self, attempt: Attempt | None) -> None:
        """Note a reserved push for ``_launch_pending``."""
        if attempt is not None:
            self._pending.append(attempt)

    def _reevaluate_open(self, now: datetime) -> None:
        """Re-evaluate waiting messages in acceptance order.

        Retries are looked at with them: one that is due is reserved,
        unless the message expired or a rule holds or discards it; one that
        a rule held back is due as soon as nothing holds it any more.
        """
        for msg in self.book.open():
            verdict = self._verdict(msg, now)
            if msg.state is MessageState.WAITING:
                self._act(msg, self.book.evaluate(msg, now, verdict), now)
            elif msg.state is MessageState.RETRYING:
                self._reserve(self.book.begin_attempt(msg, now, verdict))

    def _launch_pending(self) -> None:
        """Start the pushes reserved under the lock, after the store was tried.

        A stopped center starts none: it gives the recipients back instead.
        """
        pending, self._pending = self._pending, []
        if self._stopped:
            for attempt in pending:
                self.book.release_attempt(attempt)
            return
        for attempt in pending:
            msg = attempt.message
            if attempt.replace:
                kind = "replace"
            else:
                kind = "retry" if msg.state is MessageState.RETRYING else "cycle"
            self._launch(self._async_run_attempt(attempt), kind)

    def _drop_pending(self, kept: int) -> None:
        """Give back what was reserved after the first ``kept`` ones, without pushing.

        The intake that reserved them is taken back. What was reserved
        before, by another caller, for this message or another one, is not
        this caller's to drop; the next ``_launch_pending`` starts it.
        """
        self._pending, dropped = self._pending[:kept], self._pending[kept:]
        for attempt in dropped:
            self.book.release_attempt(attempt)

    def _launch(self, coro: Any, name: str) -> None:
        """Run a push or tick as a tracked task (short-lived).

        Home Assistant logs the name when a task holds up its shutdown, so
        the name says what runs, never for which message.
        """
        self.hass.async_create_task(coro, f"{DOMAIN}: {name}", eager_start=True)

    def _recipient(self, action: str) -> Recipient:
        for recipient in self.recipients:
            if recipient.action == action:
                return recipient
        return Recipient(action=action, name=action, platform=PLATFORM_ANDROID)

    @staticmethod
    def _context_for(msg: Message) -> Context:
        """Follow-up calls carry the sender's context."""
        return Context(user_id=msg.user_id, parent_id=msg.context_id)

    @staticmethod
    def _context_under(context: Context) -> Context:
        """Return a new context below the caller's: same user, the call as parent."""
        return Context(user_id=context.user_id, parent_id=context.id)

    def _own_effect(self, context: Context) -> Context:
        """Remember the context of an effect the center starts itself.

        Effect and forward scripts, light pulse and alarm light each run under
        one such context. A message arriving under it, or under a child of
        it, comes from that effect and starts no effect of its own. Kept in
        memory only, the last few hundred: after a restart the effects that
        were running are over, and the mark on a held message is stored.
        """
        self._effect_contexts[context.id] = None
        if len(self._effect_contexts) > MAX_EFFECT_CONTEXTS:
            del self._effect_contexts[next(iter(self._effect_contexts))]
        return context

    def _fire_intervention(
        self,
        event_type: str,
        msg: Message,
        source: str,
        context: Context,
        **extra: Any,
    ) -> None:
        """Event for the logbook: who did what with which message, no text.

        It runs in the context of whoever intervened, like ``forwarded``.
        """
        self.hass.bus.async_fire(
            event_type,
            {
                "message_id": msg.id,
                "origin": msg.origin,
                "origin_name": msg.origin_name,
                "kind": self.kind_name(msg),
                "priority": msg.priority,
                "title": self.display_title(msg),
                "source": source,
                "user_id": context.user_id,
                **extra,
            },
            context=context,
        )

    def recipient_errors(self) -> dict[str, dict[str, Any]]:
        """Latest failed attempt per recipient over all stored messages."""
        result: dict[str, dict[str, Any]] = {}
        for msg in self.book.messages.values():
            for name, status in msg.recipients.items():
                if not status.last_error or status.first_failed_at is None:
                    continue
                at = status.first_failed_at
                best = result.get(name)
                if best is None or at > best["_at"]:
                    result[name] = {
                        "_at": at,
                        "error": status.last_error,
                        "at": at.isoformat(),
                        "message_id": msg.id,
                    }
        return {
            name: {k: v for k, v in e.items() if k != "_at"}
            for name, e in result.items()
        }

    async def _push(self, msg: Message, name: str, *, silent: bool) -> str | None:
        unclassified = self.unclassified(msg)
        recipient = self._recipient(name)
        tap_url = self._tap_url(msg, unclassified=unclassified)
        return await async_push(
            self.hass,
            recipient,
            msg,
            self._context_for(msg),
            group_name=self.group_name(msg),
            language=self.language,
            silent=silent and self.silent_repeat,
            actions=self._push_actions(msg),
            alarm_channel=self.alarm_channel,
            tap_url=await self._page_target(recipient, tap_url),
            note=unclassified_note(self.language) if unclassified else None,
        )

    async def _page_target(self, recipient: Recipient, url: str | None) -> str | None:
        """Keep a target on the page only for the phone of an administrator.

        The page is for administrators only. The phone of another user, or
        one whose user is not known, gets no target and opens Home Assistant
        as before; the note on an unclassified message stays.
        """
        if url is None:
            return None
        user_id = phone_user_id(self.hass, recipient.action)
        user = await self.hass.auth.async_get_user(user_id) if user_id else None
        return url if user is not None and user.is_admin else None

    def unclassified(self, msg: Message) -> bool:
        """Tell whether no kind takes the message, now, as "new" counts it.

        It got none at intake and none matches it yet. Decided at each push:
        a message classified while it waits goes out as classified.
        """
        return msg.kind_id is None and (
            match_kind(list(self.kinds.values()), msg.origin, msg.title) is None
        )

    def _tap_url(
        self, msg: Message | None, *, unclassified: bool = False
    ) -> str | None:
        """Return what a tap on the push opens; None leaves it to the app.

        An unclassified message opens the dialog to classify it, whatever
        the option says; with "center" any other opens the page on it. A
        test push (``msg`` None) opens the page itself. Only phones of
        administrators keep the target (``_page_target``).
        """
        page = f"/{PANEL_URL_PATH}"
        if msg is not None and unclassified:
            return f"{page}?classify={msg.id}"
        if self.tap_target != TAP_TARGET_CENTER:
            return None
        return page if msg is None else f"{page}?message={msg.id}"

    async def _async_announce(self, msg: Message) -> None:
        """Priority 3 with the option: read the title aloud on the Android phones."""
        text = f"Alarm: {msg.title}"
        await asyncio.gather(
            *(
                async_push_tts(self.hass, r, text, self._context_for(msg))
                for r in self.recipients
            )
        )

    def _push_actions(self, msg: Message) -> list[dict[str, Any]] | None:
        """Build the buttons "later" and "to assistant" for the push."""
        texts = button_texts(self.language, self.snooze_minutes)
        actions: list[dict[str, Any]] = []
        if self.button_snooze:
            durations = [self.snooze_minutes]
            if self.snooze_minutes_2 and not self.snooze_input:
                durations.append(self.snooze_minutes_2)
            for minutes in durations:
                duration = duration_text(minutes, self.language)
                button: dict[str, Any] = {
                    "action": f"{ACTION_SNOOZE}|{minutes}|{msg.id}",
                    "title": f"{texts['snooze']} {duration}",
                }
                if self.snooze_input:
                    button.update(
                        {
                            "title": texts["snooze"],
                            "behavior": "textInput",
                            "textInputButtonTitle": texts["ok"],
                            "textInputPlaceholder": texts["snooze_hint"],
                        }
                    )
                actions.append(button)
        if self.button_forward:
            actions.append(
                {
                    "action": f"{ACTION_FORWARD}|{msg.id}",
                    "title": texts["forward"],
                    "behavior": "textInput",
                    "textInputButtonTitle": texts["ok"],
                    "textInputPlaceholder": texts["forward_hint"],
                }
            )
        if msg.priority >= 3 and self.alarm_lights:
            # ``build_push_data`` moves it to the third place at the latest
            actions.append(
                {"action": f"{ACTION_ALARM_OFF}|{msg.id}", "title": texts["alarm_off"]}
            )
        return actions or None

    @callback
    def _on_notification_action(self, event: Event[dict[str, Any]]) -> None:
        """Handle a tapped push button in the user's context.

        A button on a push delivered before 0.11 carries the old id,
        origin:key; it is mapped to the id of today until 0.12, by when no
        such push is still on a phone. The actions do not take the old form,
        only the buttons do.
        """
        action = str(event.data.get("action") or "")
        prefix, sep, rest = action.partition("|")
        if not sep or prefix not in (ACTION_SNOOZE, ACTION_FORWARD, ACTION_ALARM_OFF):
            return
        if prefix == ACTION_ALARM_OFF:
            self._launch(self.async_stop_alarm(source="phone"), "alarm off")
            return
        minutes = self.snooze_minutes
        mid = rest
        if prefix == ACTION_SNOOZE:
            fixed, sep2, mid = rest.partition("|")
            if not sep2:
                mid = rest
            elif fixed.isdigit() and 1 <= int(fixed) <= SNOOZE_MINUTES_MAX:
                minutes = int(fixed)
        if ":" in mid:  # the old form; an origin has no ':', a key may
            # transition from 0.10.5, remove with 0.12
            origin, _, key = mid.partition(":")
            mid = self.book.message_id(origin, key)
        reply = str(event.data.get("reply_text") or "").strip()
        # half a character pair (a cut emoji) cannot be stored and, kept as a
        # note, would make every later write fail
        reply = reply.encode("utf-8", "replace").decode()
        self._launch(
            self._async_button(prefix, mid, minutes, reply, event.context), "button"
        )

    async def _async_button(
        self, prefix: str, mid: str, minutes: int, reply: str, context: Context
    ) -> None:
        refusal = await self._async_control_refusal(context)
        if refusal:
            _LOGGER.info("Push button %s ignored: %s", prefix, refusal)
            return
        try:
            if prefix == ACTION_SNOOZE:
                if reply.isdigit() and 1 <= int(reply) <= SNOOZE_MINUTES_MAX:
                    minutes = int(reply)
                await self.async_snooze(mid, minutes, source="phone", context=context)
            else:
                await self.async_forward(mid, reply or None, context, source="phone")
        except (NotFoundError, NotReadyError) as err:
            # the button and the class: the id in the event is foreign text
            _LOGGER.info("Push button %s ignored: %s", prefix, type(err).__name__)

    async def _async_control_refusal(self, context: Context) -> str | None:
        """Why the user of ``context`` may not snooze or forward, else None.

        The check Home Assistant makes for the actions: a tap without a user
        passes, a user who may control an entity of the center passes, a user
        who may only read or no longer exists is refused. A deactivated user
        is refused too: for the actions the login already stops them, the
        Companion App's webhook does not. "End alarm" does not ask: ending a
        running alarm harms nothing.
        """
        if not context.user_id:
            return None
        user = await self.hass.auth.async_get_user(context.user_id)
        if user is None:
            return "UnknownUser"
        if not user.is_active:
            return "Unauthorized"
        for entity in er.async_get(self.hass).entities.values():
            if entity.platform == DOMAIN and user.permissions.check_entity(
                entity.entity_id, POLICY_CONTROL
            ):
                return None
        return "Unauthorized"

    # ----- alarm light (priority 3) ---------------------------------------------

    @property
    def alarm_active(self) -> bool:
        """True while the alarm light runs."""
        return self._alarm_task is not None and not self._alarm_task.done()

    async def async_start_alarm(
        self,
        seconds: int | None = None,
        *,
        source: str = "center",
        context: Context | None = None,
        msg: Message | None = None,
    ) -> bool:
        """Run the alarm light: all on, then all off/on in step, until ended.

        Ended by the push button, the switch "Alarm", the page, or after
        ``seconds`` (default: the maximum from the options). Afterwards
        every lamp and switch returns to the state it had before.

        The lamps are switched in the context of whoever starts it:
        for a message the sender's stored context, else a context of the
        center's own below ``context`` (switch, test). Home Assistant checks
        the right to the lamps itself; a refusal is noted under ``msg``.
        """
        if not self.alarm_lights:
            return False
        if self.alarm_active:
            self.alarm_until = dt_util.utcnow() + timedelta(
                seconds=seconds or self.alarm_max_seconds
            )
            return True
        if msg is not None:
            context = self._context_for(msg)
        else:
            context = self._context_under(context) if context else Context()
        duration = seconds or self.alarm_max_seconds
        self.alarm_until = dt_util.utcnow() + timedelta(seconds=duration)
        # a background task: long-running, must not hold up shutdown or tests
        self._alarm_task = self.hass.async_create_background_task(
            self._async_alarm_loop(self._own_effect(context), msg),
            f"{DOMAIN}: alarm light",
            eager_start=True,
        )
        _LOGGER.info("Alarm light started by %s for up to %s s", source, duration)
        self._notify()
        return True

    async def async_stop_alarm(self, *, source: str = "center") -> bool:
        """End the alarm light and restore the lamps; False when none ran."""
        task = self._alarm_task
        if task is None or task.done():
            return False
        self.alarm_until = None
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        _LOGGER.info("Alarm light ended by %s", source)
        self._notify()
        return True

    async def _async_alarm_loop(self, context: Context, msg: Message | None) -> None:
        before = {
            entity_id: state.state
            for entity_id in self.alarm_lights
            if (state := self.hass.states.get(entity_id)) is not None
            and state.state in ("on", "off")
        }
        targets = list(before)
        switched: list[str] = []  # reached by the first step, to be restored
        try:
            if not targets:
                return
            on = True
            # the first step by domain (in sync): lamps switched before the
            # other domain is refused are restored as well
            for domain in ("light", "switch"):
                group = [e for e in targets if e.startswith(f"{domain}.")]
                if group:
                    await self._async_set_many(group, on=True, context=context)
                    switched += group
            while self.alarm_until and dt_util.utcnow() < self.alarm_until:
                await asyncio.sleep(self.alarm_interval_ms / 1000)
                on = not on
                await self._async_set_many(targets, on=on, context=context)
        except Unauthorized:
            # whoever started it may not switch these lamps: end, instead of
            # warning at every step
            _LOGGER.warning("Alarm light refused: no right to %s", targets)
            if msg is not None:  # shielded: "end alarm" may cancel the task now
                await asyncio.shield(
                    self._async_note(msg, "light_failed", ", ".join(targets))
                )
        finally:
            # runs on cancel too; restore what was on and off before
            self._alarm_task = None
            self.alarm_until = None
            if switched:
                await asyncio.shield(
                    self._async_restore({e: before[e] for e in switched}, context)
                )
            self._notify()

    async def _async_restore(self, before: dict[str, str], context: Context) -> None:
        """Wait for queued commands to finish, then put every target back."""
        await asyncio.sleep(max(self.alarm_interval_ms / 1000, ALARM_SETTLE_SECONDS))
        for wanted in ("on", "off"):
            group = [e for e, st in before.items() if st == wanted]
            if group:
                try:
                    await self._async_set_many(
                        group, on=wanted == "on", context=context
                    )
                except Unauthorized:
                    _LOGGER.warning("Alarm light not restored: no right to %s", group)

    async def _async_set_many(
        self, entities: list[str], *, on: bool, context: Context
    ) -> None:
        service = "turn_on" if on else "turn_off"
        for domain in ("light", "switch"):
            group = [e for e in entities if e.startswith(f"{domain}.")]
            if group:
                data: dict[str, Any] = {"entity_id": group}
                if domain == "light":
                    data["transition"] = 0  # no fading, or the step is invisible
                await self._async_light_call(domain, service, data, context)

    # ----- light pulse ----------------------------------------------------------

    def set_light_enabled(self, enabled: bool) -> None:
        """Set the switch "light pulse"."""
        self.light_enabled = enabled
        self._notify()

    def _light_wanted(self, msg: Message) -> bool:
        kind = self.kinds.get(msg.kind_id) if msg.kind_id else None
        if kind is not None and kind.light is not None:
            return kind.light
        return msg.priority == 2

    def _maybe_light(self, msg: Message, now: datetime) -> None:
        """One pulse per cycle on lamps that are on, at most one per minute.

        The pulse runs in the sender's context; none for a message that
        an effect of the center sent itself.
        """
        if msg.light_done or not self.light_enabled or not self.lights:
            return
        if not self._light_wanted(msg):
            return
        msg.light_done = True
        if msg.from_effect:
            msg.add_event("light_skipped", "center", "effect", now)
            return
        if (
            self.light_spacing
            and self._last_light is not None
            and now - self._last_light < timedelta(seconds=self.light_spacing)
        ):
            msg.add_event("light_skipped", "center", "spacing", now)
            return
        targets = self._pulse_targets()
        if not targets:
            msg.add_event("light_skipped", "center", "nothing_on", now)
            return
        self._last_light = now
        msg.add_event("light", "center", ", ".join(targets), now)
        context = self._own_effect(self._context_for(msg))
        self._launch(self._async_blink(targets, context, msg), "light pulse")

    def _lit_targets(self) -> list[str]:
        """Chosen lamps and switches that are on right now."""
        return [
            entity_id
            for entity_id in self.lights
            if (state := self.hass.states.get(entity_id)) and state.state == "on"
        ]

    def _dark_always_targets(self) -> list[str]:
        """Targets marked "always" that are off right now: on, then off."""
        return [
            entity_id
            for entity_id in self.lights
            if entity_id in self.lights_always
            and (state := self.hass.states.get(entity_id))
            and state.state == "off"
        ]

    def _pulse_targets(self) -> list[str]:
        """Return what pulses now: lit targets plus "always" targets that are off."""
        return self._lit_targets() + self._dark_always_targets()

    async def async_test(self, priority: int, context: Context) -> dict[str, Any]:
        """Send a test push of a priority from the settings tab (no record).

        Straight to every recipient, no buttons, not in the book or history.
        Priority 2 pulses the lamps that are on, ignoring the spacing. Push,
        script and lamps run in a context of the center's own below the
        administrator's ``context``: what the script sends back is known as
        the center's own effect. With the option "center" a tap on it opens
        the page itself, on the phones of administrators.
        """
        if not self.ready:
            raise NotReadyError(self.ready_reason)
        now = dt_util.utcnow()
        effect = self._own_effect(self._context_under(context))
        title, text = test_texts(self.language, priority)
        key = f"priority-{priority}"
        msg = Message(
            id=self.book.message_id(TEST_ORIGIN, key),
            origin=TEST_ORIGIN,
            key=key,
            title=title,
            message=text,
            priority=priority,
            accepted_at=now,
            updated_at=now,
        )
        page = self._tap_url(None)

        async def push(recipient: Recipient) -> str | None:
            return await async_push(
                self.hass,
                recipient,
                msg,
                effect,
                group_name=None,
                language=self.language,
                alarm_channel=self.alarm_channel,
                tap_url=await self._page_target(recipient, page),
            )

        results = await asyncio.gather(*(push(r) for r in self.recipients))
        if priority == 3 and self.alarm_tts:
            self._launch(self._async_announce(msg), "announce test")
        script = self.effect_scripts.get(priority)
        script_error: str | None = None
        if script:
            script_error = await self._async_run_script(script, msg, effect)
        sent = [
            r.name for r, err in zip(self.recipients, results, strict=True) if not err
        ]
        failed = [
            r.name for r, err in zip(self.recipients, results, strict=True) if err
        ]
        targets: list[str] = []
        if priority == 3 and self.alarm_lights:
            targets = list(self.alarm_lights)
            await self.async_start_alarm(
                self.alarm_test_seconds, source="test", context=context
            )
        if priority == 2 and self.light_enabled and self.lights:
            targets = self._pulse_targets()
            if targets:
                self._last_light = now
                self._launch(self._async_blink(targets, effect), "light pulse (test)")
        return {
            "sent": sent,
            "failed": failed,
            "lights": targets,
            "script": script,
            "script_error": script_error,
        }

    async def _async_blink(
        self, targets: list[str], context: Context, msg: Message | None = None
    ) -> None:
        """Pulse lamps and switches (off/on, or on/off for "always" targets).

        No blink effect: lamps of different makes render it differently
        (colours, timing), which looked chaotic in a room with mixed lamps.
        Turning a lamp on again without parameters restores its last state.
        Refuses Home Assistant the lamps to the sender, ``light_failed`` is
        noted under ``msg``.
        """
        pulses = []
        for domain in ("light", "switch"):
            entities = [e for e in targets if e.startswith(f"{domain}.")]
            lit = [
                e
                for e in entities
                if (st := self.hass.states.get(e)) and st.state == "on"
            ]
            dark = [e for e in entities if e not in lit]
            if lit:
                pulses.append(self._async_pulse(domain, lit, "turn_on", context))
            if dark:
                pulses.append(self._async_pulse(domain, dark, "turn_off", context))
        results = await asyncio.gather(*pulses, return_exceptions=True)
        if any(isinstance(r, Unauthorized) for r in results):
            _LOGGER.warning("Light pulse refused: no right to %s", targets)
            if msg is not None:
                await self._async_note(msg, "light_failed", ", ".join(targets))

    async def _async_pulse(
        self, domain: str, entities: list[str], restore: str, context: Context
    ) -> None:
        first = "turn_off" if restore == "turn_on" else "turn_on"
        data = {"entity_id": entities}
        if not await self._async_light_call(domain, first, data, context):
            return
        await asyncio.sleep(self.pulse_ms / 1000)
        if not await self._async_light_call(domain, restore, data, context):
            await asyncio.sleep(self.pulse_ms / 1000)
            await self._async_light_call(domain, restore, data, context)

    async def _async_light_call(
        self, domain: str, service: str, data: dict[str, Any], context: Context
    ) -> bool:
        """Switch lamps in the given context; False when the command failed.

        Home Assistant checks the right to the lamps itself. A refusal is
        passed on so that the caller stops instead of trying again.
        """
        try:
            await asyncio.wait_for(
                self.hass.services.async_call(
                    domain, service, data, blocking=True, context=context
                ),
                timeout=LIGHT_TIMEOUT,
            )
        except Unauthorized:
            raise
        except Exception as err:
            _LOGGER.warning(
                "Light pulse %s.%s on %s failed: %s",
                domain,
                service,
                data.get("entity_id"),
                err,
            )
            return False
        return True

    # ----- push cycle (tasks) -----------------------------------------------

    async def _async_run_attempt(self, attempt: Attempt) -> None:
        """Push to the reserved recipients, record the results, start what follows.

        The recipients were reserved and the store written before this task
        started. It only pushes, outside the lock. Under the lock again it
        records the results, looks whether a delivered push now shows an
        older text or counter, writes the store and starts that replacement.
        A replacement confirms just the revision and counter it carried and
        is followed by another one only if the message changed while it was
        out; one that failed is not repeated by itself.

        Whatever a push raises is its result, a failed attempt, and the retry
        plan moves on. Only a cancelled task gives its recipients back as due;
        an error taken for that would start the retry again every second.
        """
        msg = attempt.message
        names = list(attempt.recipients)
        try:
            outcomes = await asyncio.gather(
                *(self._push(msg, name, silent=attempt.replace) for name in names),
                return_exceptions=True,
            )
            results: list[str | None] = []
            for name, result in zip(names, outcomes, strict=True):
                if isinstance(result, BaseException):
                    _LOGGER.error(
                        "Unexpected error pushing to %s: %s", name, error_trace(result)
                    )
                    result = type(result).__name__
                results.append(result)
            async with self._lock:
                # decided under the lock: a stopped center announces nothing
                if (
                    not attempt.replace
                    and msg.priority >= 3
                    and self.alarm_tts
                    and not self._stopped
                    and any(e is None for e in results)
                ):
                    self._launch(self._async_announce(msg), "announce")
                now = dt_util.utcnow()
                for name, error in zip(names, results, strict=True):
                    outcome = self.book.finish_attempt(
                        attempt, name, success=error is None, now=now, error=error
                    )
                    if outcome.first_delivery:
                        self._on_first_delivery(msg, now)
                if not attempt.replace or (attempt.revision, attempt.count) != (
                    msg.revision,
                    msg.count,
                ):
                    self._reserve(self.book.begin_replace(msg))
                await self._commit(now, raise_error=False)
                self._launch_pending()
                self._update_issues(now)
                self._schedule()
                self._notify()
        finally:
            if attempt.recipients:  # cancelled: no result, the retry is due again
                self.book.release_attempt(attempt)
                self._schedule()

    def _on_first_delivery(self, msg: Message, now: datetime) -> None:
        """Fire the delivered event and remember the last delivery.

        Effects follow: light pulse, effect script, alarm light. A stopped
        center starts none; the result is in its book only, the center that
        follows shows the message as unclear.
        """
        if self._stopped:
            return
        data = {
            "message_id": msg.id,
            "origin": msg.origin,
            "origin_name": msg.origin_name,
            "kind": self.kind_name(msg),
            "group": self.group_name(msg),
            "priority": msg.priority,
            "title": self.display_title(msg),
            "count": msg.count,
            "recipients": msg.delivered_recipients,
        }
        self.hass.bus.async_fire(EVENT_DELIVERED, data, context=self._context_for(msg))
        self.last_delivery = (
            now,
            msg.origin_name or msg.origin,
            self.display_title(msg),
        )
        self.delivered_today += 1
        self._maybe_light(msg, now)
        if script := self.effect_scripts.get(msg.priority):
            if msg.from_effect:  # sent by an effect of the center: none again
                msg.add_event("script_skipped", "center", script, now)
            else:
                context = self._own_effect(self._context_for(msg))
                self._launch(
                    self._async_run_script(script, msg, context), "effect script"
                )
        if msg.priority >= 3 and self.alarm_lights:
            if msg.from_effect:
                # an automation reporting an alarm lamp would prolong the alarm
                # at every step and start it again when the lamps are restored
                msg.add_event("light_skipped", "center", "effect", now)
            else:
                msg.add_event(
                    "alarm_light", "center", ", ".join(self.alarm_lights), now
                )
                self._launch(self.async_start_alarm(msg=msg), "alarm start")
        for listener in list(self._delivered_listeners):
            listener(data)

    # ----- timers ------------------------------------------------------------

    @callback
    def _schedule(self) -> None:
        """Arm one timer for the next retry, wait end, expiry or rule maximum.

        While the store cannot be written the next try to write it counts too.
        A stopped center arms no timer.
        """
        if self._stopped:
            return
        now = dt_util.utcnow()
        times: list[datetime] = []
        for msg in self.book.open():
            if msg.state is MessageState.RETRYING and msg.next_try:
                times.append(msg.next_try)
            if msg.state is MessageState.WAITING and msg.reason.until:
                times.append(msg.reason.until)
            # a push under way does not expire, its result comes first
            if msg.expires_at and not self.book.expiry_waits(msg):
                times.append(msg.expires_at)
        expiry = self.rules.next_expiry(now)
        if expiry:
            times.append(expiry)
        if self._store_retry:
            times.append(self._store_retry)
        when = max(min(times), now + timedelta(seconds=1)) if times else None
        if when == self._timer_at and self._timer is not None:
            return
        self._cancel_timer()
        self._timer_at = when
        if when is not None:
            self._timer = async_track_point_in_utc_time(self.hass, self._on_timer, when)

    @callback
    def _cancel_timer(self) -> None:
        if self._timer:
            self._timer()
        self._timer = None
        self._timer_at = None

    @callback
    def _on_timer(self, _now: datetime) -> None:
        self._timer = None
        self._timer_at = None
        self._launch(self._async_tick(), "tick")

    async def _async_tick(self) -> None:
        """Handle everything that is due."""
        async with self._lock:
            if self._stopped:
                return
            now = dt_util.utcnow()
            self.book.apply_expiry(now)
            for rule in self.rules.newly_expired(now):
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    f"rule_max_duration_{rule.rule_id}",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="rule_max_duration",
                    translation_placeholders={
                        "name": rule.name,
                        "hours": str(rule.max_hours),
                    },
                )
            self._reevaluate_open(now)
            await self._commit(now, raise_error=False)
            self._launch_pending()
            self._update_issues(now)
            self._schedule()
            self._notify()

    @callback
    def _on_housekeeping(self, _now: datetime) -> None:
        self._launch(self._async_housekeeping(), "housekeeping")

    async def _async_housekeeping(self) -> None:
        """Hourly: expiry, pruning into history, history retention."""
        async with self._lock:
            if self._stopped:
                return
            now = dt_util.utcnow()
            self.book.apply_expiry(now)
            self.book.prune(now)
            if self.book.history:
                await self._async_write_history()
            self.history.prune(now, self.history_days)
            if dt_util.as_local(now).hour == 0:
                self.delivered_today = 0
            await self._commit(now, raise_error=False)
            self._update_issues(now)
            self._schedule()
            self._notify()

    @callback
    def _on_rule_state(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        new_state = event.data["new_state"]
        self._launch(
            self._async_rule_changed(entity_id, new_state.state if new_state else None),
            f"rule {entity_id}",
        )

    async def _async_rule_changed(self, entity_id: str, state: str | None) -> None:
        async with self._lock:
            if self._stopped:
                return
            now = dt_util.utcnow()
            changed = False
            for rule in self.rules.rules.values():
                if rule.entity_id == entity_id:
                    changed |= self.rules.observe(rule.rule_id, state, now)
            if changed:
                self._reevaluate_open(now)
                await self._commit(now, raise_error=False)
                self._launch_pending()
                self._update_issues(now)
                self._schedule()
                self._notify()

    # ----- persistence and issues -------------------------------------------

    async def _async_require_ready(self, *, store_needed: bool = True) -> None:
        """Raise NotReadyError unless the center can take messages and commands.

        Not ready because of the store alone: try to write right now instead
        of rejecting until a timer writes again. Callers that waited
        while somebody else tried take that result, so a burst of calls costs
        one write attempt and not one each. After a write that ran into the
        time limit nothing is tried here: the disk hangs, and every caller
        would wait for the limit under the lock. The timer tries again.

        With ``store_needed`` off a store that still cannot be written is no
        reason to reject ("send now"): the write was tried, the caller goes on.
        """
        if not self.ready and self.ready_reason == "store" and not self._store_hangs:
            seen = self._commits
            async with self._lock:
                if self._commits == seen:
                    if await self._commit(dt_util.utcnow(), raise_error=False):
                        self._notify()
                    self._schedule()
        if not self.ready and (store_needed or self.ready_reason != "store"):
            raise NotReadyError(self.ready_reason)

    def _require_running(self) -> None:
        """Under the lock: reject a caller that queued behind ``async_stop``.

        It fetched this center while it was loaded and waited for the lock.
        Served now, it would accept into a book nobody writes any more and
        hold the message for accepted; rejected, its fallback takes over.
        """
        if self._stopped:
            raise NotReadyError("stopped")

    async def _async_write_history(self) -> bool:
        """Hand the pending end states to the history store and write it.

        They stay in the book, and with it in the working store, until the
        history is confirmed on disk. Returns whether it was written.

        A history that cannot be written gets a repair issue of its own and
        is logged once; "Ready" stays on, the working store is written on.
        The book keeps at most ``MAX_PENDING_HISTORY`` end states; what
        it dropped since the last time is logged here, as a number only.
        """
        dropped = self.book.history_dropped - self._history_dropped
        if dropped:
            self._history_dropped = self.book.history_dropped
            _LOGGER.warning(
                "Pending history at its limit of %d entries: %d oldest dropped",
                self.book.max_pending,
                dropped,
            )
        self.history.add(self.book.history)
        try:
            await self.history.async_flush()
        except StoreNotWritableError as err:
            if not self._history_failing:  # once, not on every failed write
                _LOGGER.warning("History store not writable: %s", err)
            self._history_failing = True
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_HISTORY,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_HISTORY,
            )
            return False
        if self._history_failing:
            _LOGGER.info("History store writable again")
            self._history_failing = False
        ir.async_delete_issue(self.hass, DOMAIN, ISSUE_HISTORY)
        self.book.drain_history()
        return True

    async def _commit(self, now: datetime, *, raise_error: bool = True) -> bool:
        """Write the working store; on failure the center is not ready.

        Returns whether the book is on disk. Only the intake lets the error
        raise and takes its message back. Everyone else carries on and sends
        anyway: outside the intake delivery comes first, at the price that
        after a restart the message may be sent once more. After a failure
        the caller arms the timer (``_schedule``): the center then tries the
        store again by itself, also when no sender calls while it is not ready.
        A stopped center writes nothing: the store is the next center's.
        """
        if self._stopped:
            return False
        try:
            await self.store.async_save(
                self.book, now, self.rules, extra={"unknown": self.unknown}
            )
        except StoreNotWritableError as err:
            self._commits += 1
            self._store_retry = now + STORE_RETRY_INTERVAL
            self._store_hangs = isinstance(err, StoreWriteTimeoutError)
            first = self.ready_reason != "store"
            self.ready = False
            self.ready_reason = "store"
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_STORE,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key=ISSUE_STORE,
            )
            if first:  # once, not on every failed write
                _LOGGER.error("Message store not writable: %s", err)
            if raise_error:
                raise
            return False
        self._commits += 1
        self._store_retry = None
        self._store_hangs = False
        ir.async_delete_issue(self.hass, DOMAIN, ISSUE_STORE)
        if not self.ready and self.ready_reason == "store":
            _LOGGER.info("Message store writable again")
            self.ready = True
            self.ready_reason = "ready"
        return True

    @callback
    def _update_issues(self, now: datetime) -> None:
        """Repairs and the persistent notification for failing deliveries.

        A stopped center leaves them to the center that follows.
        """
        if self._stopped:
            return
        unknown_rules = self.rules.unknown_rules()
        for rule in self.rules.rules.values():
            issue_id = f"rule_entity_unavailable_{rule.rule_id}"
            if rule in unknown_rules:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    issue_id,
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="rule_entity_unavailable",
                    translation_placeholders={
                        "name": rule.name,
                        "entity_id": rule.entity_id,
                    },
                )
            else:
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            if not self.rules.is_expired(rule.rule_id, now):
                ir.async_delete_issue(
                    self.hass, DOMAIN, f"rule_max_duration_{rule.rule_id}"
                )

        failing: dict[str, datetime] = {}
        failing_messages = 0
        for msg in self.book.open():
            if msg.state is not MessageState.RETRYING:
                continue
            failing_messages += 1
            for name, status in msg.recipients.items():
                if status.state is RecipientState.PENDING and status.first_failed_at:
                    first = failing.get(name)
                    if first is None or status.first_failed_at < first:
                        failing[name] = status.first_failed_at
        for action, first in failing.items():
            if now - first >= RECIPIENT_REPAIR_AFTER:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    f"recipient_unreachable_{action}",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="recipient_unreachable",
                    translation_placeholders={"name": self._recipient(action).name},
                )
                self._recipient_issues.add(action)
        for action in list(self._recipient_issues):
            if action not in failing:
                ir.async_delete_issue(
                    self.hass, DOMAIN, f"recipient_unreachable_{action}"
                )
                self._recipient_issues.discard(action)

        if failing_messages:
            persistent_notification.async_create(
                self.hass,
                failing_text(self.language, failing_messages),
                title="Message Center",
                notification_id=NOTIFICATION_FAILED,
            )
        else:
            persistent_notification.async_dismiss(self.hass, NOTIFICATION_FAILED)

        unclear = [m for m in self.book.open() if m.state is MessageState.UNCLEAR]
        if unclear:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_UNCLEAR,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_UNCLEAR,
                translation_placeholders={"count": str(len(unclear))},
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_UNCLEAR)
