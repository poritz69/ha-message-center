"""Message kinds and groups with the matching of incoming messages.

Pure logic: kinds and groups are built from config subentries by the center.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Self

from .const import DEFAULT_TITLE, PLACEHOLDER
from .models import UNKNOWN_ORIGIN


class TitleMode(StrEnum):
    """How the title condition of a kind is compared.

    ``ANY`` takes every title: "all messages of this automation". It is only
    valid together with an origin, see ``origin_allows_any``.
    """

    EXACT = "exact"
    PREFIX = "prefix"
    CONTAINS = "contains"
    ANY = "any"


_MODE_RANK: dict[TitleMode, int] = {
    TitleMode.EXACT: 3,
    TitleMode.PREFIX: 2,
    TitleMode.CONTAINS: 1,
    TitleMode.ANY: 0,
}


def origin_allows_any(origin: str | None) -> bool:
    """Return True when a kind for every title may be bound to this origin.

    Without an origin, or for messages whose origin is unknown, such a kind
    would take every message there is.
    """
    return bool(origin) and origin != UNKNOWN_ORIGIN


@dataclass(slots=True)
class Group:
    """A group of kinds with defaults for new kinds."""

    group_id: str
    name: str
    icon: str | None = None
    priority: int = 1
    spacing: int = 0
    expires_after: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialise for the subentry."""
        return {
            "name": self.name,
            "icon": self.icon,
            "priority": self.priority,
            "spacing": self.spacing,
            "expires_after": self.expires_after,
        }

    @classmethod
    def from_dict(cls, group_id: str, data: dict[str, Any]) -> Self:
        """Build from subentry data."""
        return cls(
            group_id=group_id,
            name=data["name"],
            icon=data.get("icon"),
            priority=int(data.get("priority", 1)),
            spacing=int(data.get("spacing", 0)),
            expires_after=int(data.get("expires_after", 0)),
        )


@dataclass(slots=True)
class Kind:
    """A message kind: matching condition and handling."""

    kind_id: str
    name: str
    title_mode: TitleMode
    title_value: str
    origin: str | None = None
    group_id: str | None = None
    priority: int = 1
    no_hold: bool = False
    spacing: int = 0
    expires_after: int = 0
    light: bool | None = None
    active: bool = True
    order: int = 0

    def matches(self, origin: str, title: str) -> bool:
        """Return True when origin and title satisfy the conditions."""
        if not self.active:
            return False
        if self.origin is not None and self.origin != origin:
            return False
        if self.title_mode is TitleMode.ANY:
            return origin_allows_any(self.origin)
        haystack = title.casefold()
        needle = self.title_value.casefold()
        if self.title_mode is TitleMode.EXACT:
            return haystack == needle
        if self.title_mode is TitleMode.PREFIX:
            return haystack.startswith(needle)
        return needle in haystack

    @property
    def specificity(self) -> tuple[int, int, int, int]:
        """Higher wins: specific origin, stricter mode, longer value, earlier order."""
        return (
            1 if self.origin is not None else 0,
            _MODE_RANK[self.title_mode],
            len(self.title_value),
            -self.order,
        )

    @property
    def condition_key(self) -> tuple[str | None, str, str]:
        """The condition as it is compared: two kinds with the same key are doubles.

        Origin, mode and the text without regard to case and surrounding
        spaces; "any title" has no text.
        """
        return condition_key(self.origin, self.title_mode, self.title_value)

    def to_dict(self) -> dict[str, Any]:
        """Serialise for the subentry."""
        return {
            "name": self.name,
            "origin": self.origin,
            "title_mode": self.title_mode.value,
            "title_value": self.title_value,
            "group_id": self.group_id,
            "priority": self.priority,
            "no_hold": self.no_hold,
            "spacing": self.spacing,
            "expires_after": self.expires_after,
            "light": self.light,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, kind_id: str, data: dict[str, Any], order: int = 0) -> Self:
        """Build from subentry data."""
        return cls(
            kind_id=kind_id,
            name=data["name"],
            origin=data.get("origin") or None,
            title_mode=TitleMode(data.get("title_mode", TitleMode.EXACT)),
            title_value=data.get("title_value", ""),
            group_id=data.get("group_id") or None,
            priority=int(data.get("priority", 1)),
            no_hold=bool(data.get("no_hold", False)),
            spacing=int(data.get("spacing", 0)),
            expires_after=int(data.get("expires_after", 0)),
            light=data.get("light"),
            active=bool(data.get("active", True)),
            order=order,
        )


def condition_key(
    origin: str | None, title_mode: str, title_value: str
) -> tuple[str | None, str, str]:
    """Key of a title condition, see ``Kind.condition_key``."""
    mode = TitleMode(title_mode)
    text = "" if mode is TitleMode.ANY else title_value.strip().casefold()
    return (origin or None, mode.value, text)


def covers(outer: Kind, inner: Kind) -> bool:
    """Return True when every message the inner condition matches matches the outer one.

    Activity and order aside: only origin and title condition are compared.
    """
    if outer.origin is not None and outer.origin != inner.origin:
        return False
    if outer.title_mode is TitleMode.ANY:
        return origin_allows_any(outer.origin)
    if inner.title_mode is TitleMode.ANY:
        return False
    big = outer.title_value.casefold()
    small = inner.title_value.casefold()
    if outer.title_mode is TitleMode.CONTAINS:
        return big in small
    if outer.title_mode is TitleMode.PREFIX:
        return inner.title_mode is not TitleMode.CONTAINS and small.startswith(big)
    return inner.title_mode is TitleMode.EXACT and small == big


def _best(kinds: list[Kind], origin: str, title: str) -> Kind | None:
    candidates = [kind for kind in kinds if kind.matches(origin, title)]
    if not candidates:
        return None
    return max(candidates, key=lambda kind: kind.specificity)


def match_kind(
    kinds: list[Kind], origin: str, title: str, *, untitled: bool = False
) -> Kind | None:
    """Return the most specific active kind matching origin and title.

    ``untitled``: the message came without a title and is called after its
    origin. Up to 0.11.1b1 such a message was called "Mitteilung"; a kind
    made for that title still takes it when no kind matches its new one.
    """
    kind = _best(kinds, origin, title)
    if kind is None and untitled and title != DEFAULT_TITLE:
        kind = _best(kinds, origin, DEFAULT_TITLE)
    return kind


def surely_matches(kind: Kind, origin: str, title: str, *, computed: bool) -> bool:
    """Return True when a kind takes every message of a title read from a configuration.

    A fixed title is the title of its messages. A computed one shows its
    computed parts as ``PLACEHOLDER``, so only its fixed parts are known:
    "begins with" takes it when its fixed beginning does, "contains" when
    one of its fixed parts does, "exact" never for sure.
    """
    if not computed:
        return kind.matches(origin, title)
    if not kind.active or (kind.origin is not None and kind.origin != origin):
        return False
    if kind.title_mode is TitleMode.ANY:
        return origin_allows_any(kind.origin)
    needle = kind.title_value.casefold()
    parts = title.casefold().split(PLACEHOLDER)
    if kind.title_mode is TitleMode.PREFIX:
        return parts[0].startswith(needle)
    if kind.title_mode is TitleMode.CONTAINS:
        return any(needle in part for part in parts)
    return False


def _taken_by(
    kinds: list[Kind], candidate: Kind | None, origin: str, title: str
) -> dict[str, str] | None:
    """Name the kind other than the candidate that would take a pair, if any."""
    winner = match_kind(kinds, origin, title)
    if winner is None or winner is candidate:
        return None
    return {"kind_id": winner.kind_id, "name": winner.name}


def condition_matches(
    candidate: Kind,
    others: list[Kind],
    new: list[dict[str, Any]],
    seen: list[dict[str, Any]],
    *,
    configured: list[tuple[str, str, bool]] | None = None,
    probe: tuple[str, str] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Tell what a condition being edited matches among the pairs the center knows.

    ``others`` are the other active kinds, ``new`` the pairs of "new" and
    ``seen`` those of the stored messages, both newest first; a pair of
    "new" is not counted again among ``seen``. Each matched pair is listed
    (at most ``limit`` per list, the counters tell the rest) with
    ``taken_by``: the other kind that would take it, or None when the
    candidate would. ``overlaps`` are the other kinds that share a matched
    pair with the candidate, or whose condition covers or is covered by its
    condition, with the one that wins between the two and the number of
    shared pairs. ``configured`` are titles the automations involved send
    by their configuration, as origin, title and whether it is computed
    (see ``surely_matches``): a kind that takes one of them together with
    the candidate overlaps as well, before any such message arrived; they
    count for nothing else. ``probe`` asks about one pair: does the
    candidate match it, and which other kind would take it (None: the
    candidate, or nobody, and then it lands in "new").
    """
    everyone = [*others, candidate]
    shared: dict[str, int] = {}
    taken = 0
    near: dict[str, list[Kind]] = {}

    def rivals(origin: str) -> list[Kind]:
        """Return the other kinds that can match a pair of this origin, sorted once."""
        found = near.get(origin)
        if found is None:
            found = near[origin] = [
                other
                for other in others
                if other.origin is None or other.origin == origin
            ]
        return found

    def check(pairs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
        nonlocal taken
        listed: list[dict[str, Any]] = []
        count = 0
        for pair in pairs:
            origin, title = pair["origin"], pair["title"]
            if not candidate.matches(origin, title):
                continue
            count += 1
            matching = [o for o in rivals(origin) if o.matches(origin, title)]
            # as match_kind over all kinds: the candidate comes last
            winner = max([*matching, candidate], key=lambda kind: kind.specificity)
            taken_by = None
            if winner is not candidate:
                taken += 1
                taken_by = {"kind_id": winner.kind_id, "name": winner.name}
            for other in matching:
                shared[other.kind_id] = shared.get(other.kind_id, 0) + 1
            if len(listed) < limit:
                listed.append({**pair, "taken_by": taken_by})
        return listed, count

    in_config: set[str] = set()
    for origin, title, computed in configured or []:
        if surely_matches(candidate, origin, title, computed=computed):
            in_config.update(
                other.kind_id
                for other in rivals(origin)
                if surely_matches(other, origin, title, computed=computed)
            )

    in_new = {(p["origin"], p["title"].casefold()) for p in new}
    new_listed, new_count = check(new)
    seen_listed, seen_count = check(
        [p for p in seen if (p["origin"], p["title"].casefold()) not in in_new]
    )
    overlaps = [
        {
            "kind_id": other.kind_id,
            "name": other.name,
            "winner": "this" if candidate.specificity > other.specificity else "other",
            "shared": shared.get(other.kind_id, 0),
        }
        for other in others
        if shared.get(other.kind_id)
        or other.kind_id in in_config
        or covers(candidate, other)
        or covers(other, candidate)
    ]
    result: dict[str, Any] = {
        "valid": True,
        "new": new_listed,
        "new_count": new_count,
        "seen": seen_listed,
        "seen_count": seen_count,
        "taken_count": taken,
        "overlaps": overlaps[:limit],
        "overlap_count": len(overlaps),
        "probe": None,
    }
    if probe is not None:
        origin, title = probe
        result["probe"] = {
            "matches": candidate.matches(origin, title),
            "taken_by": _taken_by(everyone, candidate, origin, title),
        }
    return result


def no_matches() -> dict[str, Any]:
    """Answer for a condition that is not complete yet: it matches nothing."""
    return {
        "valid": False,
        "new": [],
        "new_count": 0,
        "seen": [],
        "seen_count": 0,
        "taken_count": 0,
        "overlaps": [],
        "overlap_count": 0,
        "probe": None,
    }
