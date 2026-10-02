"""Tests for message kinds and their matching."""

from __future__ import annotations

from custom_components.message_center.kinds import (
    Group,
    Kind,
    TitleMode,
    match_kind,
)

AUTO = "automation.klima_feuchte_buero"


def kind(**overrides: object) -> Kind:
    """Build a kind with defaults."""
    data: dict[str, object] = {
        "kind_id": "k",
        "name": "Feuchte",
        "title_mode": TitleMode.PREFIX,
        "title_value": "Feuchte",
    }
    data.update(overrides)
    return Kind(**data)  # type: ignore[arg-type]


def test_title_modes_are_case_insensitive() -> None:
    """Exact, prefix and contains compare without regard to case."""
    assert kind(title_mode=TitleMode.EXACT, title_value="feuchte: büro").matches(
        AUTO, "Feuchte: Büro"
    )
    assert kind(title_mode=TitleMode.PREFIX, title_value="feuchte").matches(
        AUTO, "Feuchte: Büro"
    )
    assert kind(title_mode=TitleMode.CONTAINS, title_value="büro").matches(
        AUTO, "Feuchte: Büro"
    )
    assert not kind(title_mode=TitleMode.EXACT, title_value="Feuchte").matches(
        AUTO, "Feuchte: Büro"
    )


def test_origin_condition() -> None:
    """A kind bound to an automation matches only that automation."""
    bound = kind(origin=AUTO)
    assert bound.matches(AUTO, "Feuchte: Büro")
    assert not bound.matches("automation.other", "Feuchte: Büro")
    assert kind(origin=None).matches("automation.other", "Feuchte: Büro")


def test_inactive_kind_never_matches() -> None:
    """An inactive kind does not assign."""
    assert not kind(active=False).matches(AUTO, "Feuchte: Büro")


def test_most_specific_kind_wins() -> None:
    """Specific origin beats any, exact beats prefix beats contains, longer wins."""
    any_contains = kind(kind_id="a", title_mode=TitleMode.CONTAINS, title_value="Büro")
    any_prefix = kind(kind_id="b", title_mode=TitleMode.PREFIX, title_value="Feuchte")
    bound_contains = kind(
        kind_id="c", origin=AUTO, title_mode=TitleMode.CONTAINS, title_value="Büro"
    )
    exact = kind(kind_id="d", title_mode=TitleMode.EXACT, title_value="Feuchte: Büro")
    kinds = [any_contains, any_prefix, bound_contains, exact]
    assert match_kind(kinds, AUTO, "Feuchte: Büro") is bound_contains
    assert match_kind([any_contains, any_prefix, exact], AUTO, "Feuchte: Büro") is exact
    assert match_kind([any_contains, any_prefix], AUTO, "Feuchte: Büro") is any_prefix
    longer = kind(kind_id="e", title_mode=TitleMode.PREFIX, title_value="Feuchte: B")
    assert match_kind([any_prefix, longer], AUTO, "Feuchte: Büro") is longer
    assert match_kind(kinds, AUTO, "Lüften") is None


def test_tie_goes_to_the_earlier_kind() -> None:
    """Two equal conditions: the one created first decides."""
    first = kind(kind_id="a", order=0)
    second = kind(kind_id="b", order=1)
    assert match_kind([second, first], AUTO, "Feuchte: Büro") is first


def test_roundtrip_kind_and_group() -> None:
    """Kinds and groups survive the subentry serialisation."""
    original = kind(
        origin=AUTO, group_id="g1", priority=2, no_hold=True, spacing=360, light=False
    )
    restored = Kind.from_dict("k", original.to_dict(), order=0)
    assert restored == original
    group = Group("g1", "Klima", icon="mdi:thermometer", priority=1, spacing=60)
    assert Group.from_dict("g1", group.to_dict()) == group
