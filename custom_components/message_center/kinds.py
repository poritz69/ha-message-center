"""Message kinds and groups with the matching of incoming messages.

Pure logic: kinds and groups are built from config subentries by the center.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Self


class TitleMode(StrEnum):
    """How the title condition of a kind is compared."""

    EXACT = "exact"
    PREFIX = "prefix"
    CONTAINS = "contains"


_MODE_RANK: dict[TitleMode, int] = {
    TitleMode.EXACT: 3,
    TitleMode.PREFIX: 2,
    TitleMode.CONTAINS: 1,
}


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


def match_kind(kinds: list[Kind], origin: str, title: str) -> Kind | None:
    """Return the most specific active kind matching origin and title."""
    candidates = [kind for kind in kinds if kind.matches(origin, title)]
    if not candidates:
        return None
    return max(candidates, key=lambda kind: kind.specificity)
