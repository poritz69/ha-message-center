"""Tests for message kinds and their matching."""

from __future__ import annotations

from custom_components.message_center.kinds import (
    Group,
    Kind,
    TitleMode,
    covers,
    match_kind,
    surely_matches,
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


def test_any_matches_every_title_of_its_origin_only() -> None:
    """Take any title for "all messages of this automation", from that origin only."""
    every = kind(origin=AUTO, title_mode=TitleMode.ANY, title_value="")
    assert every.matches(AUTO, "Feuchte: Büro")
    assert every.matches(AUTO, "Etwas ganz anderes")
    assert not every.matches("automation.other", "Feuchte: Büro")
    assert not kind(
        origin=AUTO, title_mode=TitleMode.ANY, title_value="", active=False
    ).matches(AUTO, "x")
    # without an origin, or for messages of unknown origin, it would take
    # everything: such a kind matches nothing
    assert not kind(origin=None, title_mode=TitleMode.ANY, title_value="").matches(
        AUTO, "x"
    )
    assert not kind(origin="unknown", title_mode=TitleMode.ANY, title_value="").matches(
        "unknown", "x"
    )


def test_any_ranks_below_contains() -> None:
    """The origin still comes first; within it any title is the weakest condition."""
    every = kind(kind_id="a", origin=AUTO, title_mode=TitleMode.ANY, title_value="")
    bound_contains = kind(
        kind_id="b", origin=AUTO, title_mode=TitleMode.CONTAINS, title_value="x"
    )
    free_exact = kind(
        kind_id="c", title_mode=TitleMode.EXACT, title_value="Feuchte: Büro"
    )
    assert match_kind([every, bound_contains], AUTO, "x y") is bound_contains
    assert match_kind([every, bound_contains], AUTO, "Feuchte: Büro") is every
    assert match_kind([free_exact, every], AUTO, "Feuchte: Büro") is every
    assert every.specificity < bound_contains.specificity


def test_roundtrip_kind_with_any() -> None:
    """A kind for all messages of an automation survives the serialisation."""
    original = kind(origin=AUTO, title_mode=TitleMode.ANY, title_value="")
    assert original.to_dict()["title_mode"] == "any"
    assert Kind.from_dict("k", original.to_dict()) == original


def test_condition_key_ignores_case_spaces_and_the_text_of_any() -> None:
    """Two kinds have the same condition when origin, mode and text agree."""
    assert kind(title_value=" feuchte ").condition_key == (
        None,
        "prefix",
        "feuchte",
    )
    assert (
        kind(title_value="Feuchte").condition_key
        == kind(title_value="FEUCHTE ").condition_key
    )
    assert kind(
        origin=AUTO, title_mode=TitleMode.ANY, title_value="x"
    ).condition_key == (
        AUTO,
        "any",
        "",
    )
    assert kind(title_mode=TitleMode.EXACT).condition_key != kind().condition_key
    assert kind(origin=AUTO).condition_key != kind().condition_key


def test_covers() -> None:
    """One condition covers another when every message of the other matches it."""
    every = kind(origin=AUTO, title_mode=TitleMode.ANY, title_value="")
    prefix = kind(title_mode=TitleMode.PREFIX, title_value="Feuchte")
    exact = kind(origin=AUTO, title_mode=TitleMode.EXACT, title_value="Feuchte: Büro")
    contains = kind(title_mode=TitleMode.CONTAINS, title_value="büro")
    assert covers(every, exact)
    assert not covers(exact, every)
    assert covers(prefix, exact)  # any origin covers one origin
    assert not covers(exact, prefix)
    assert covers(contains, exact)
    assert covers(contains, kind(title_mode=TitleMode.PREFIX, title_value="Büro 2"))
    assert not covers(prefix, contains)
    assert not covers(every, prefix)  # prefix is not bound to the automation
    assert covers(
        kind(title_mode=TitleMode.PREFIX, title_value="Feu"),
        kind(title_mode=TitleMode.PREFIX, title_value="feuchte"),
    )
    assert covers(
        kind(title_mode=TitleMode.CONTAINS, title_value="eucht"),
        kind(title_mode=TitleMode.CONTAINS, title_value="Feuchte"),
    )
    assert not covers(kind(origin="automation.other"), exact)


def test_untitled_message_falls_back_to_a_kind_for_mitteilung() -> None:
    """A message called after its automation finds a kind for "Mitteilung" last.

    Only a message that came without a title, and only when no kind matches
    its title.
    """
    old = kind(
        kind_id="old", origin=AUTO, title_mode=TitleMode.EXACT, title_value="Mitteilung"
    )
    new = kind(kind_id="new", origin=AUTO, title_mode=TitleMode.ANY, title_value="")
    assert match_kind([old], AUTO, "Klima", untitled=True) is old
    assert match_kind([old], AUTO, "Klima") is None
    assert match_kind([old, new], AUTO, "Klima", untitled=True) is new
    assert match_kind([old], "automation.andere", "Klima", untitled=True) is None


def test_surely_matches_a_title_read_from_a_configuration() -> None:
    """Of a computed title only its fixed parts count; "exact" is never sure."""
    shown = "Raum …: lüften"
    assert surely_matches(
        kind(title_mode=TitleMode.PREFIX, title_value="raum"),
        AUTO,
        shown,
        computed=True,
    )
    assert surely_matches(
        kind(title_mode=TitleMode.CONTAINS, title_value="LÜFTEN"),
        AUTO,
        shown,
        computed=True,
    )
    assert not surely_matches(
        kind(title_mode=TitleMode.PREFIX, title_value="lüften"),
        AUTO,
        shown,
        computed=True,
    )
    assert not surely_matches(
        kind(title_mode=TitleMode.EXACT, title_value="Raum"), AUTO, shown, computed=True
    )
    assert not surely_matches(
        kind(title_mode=TitleMode.PREFIX, title_value="raum"),
        AUTO,
        "… Raum",
        computed=True,
    )
    every = kind(origin=AUTO, title_mode=TitleMode.ANY, title_value="")
    assert surely_matches(every, AUTO, "…", computed=True)
    assert not surely_matches(every, "automation.andere", "…", computed=True)
    assert not surely_matches(
        kind(title_mode=TitleMode.PREFIX, title_value="raum", active=False),
        AUTO,
        shown,
        computed=True,
    )
    # a fixed title is compared as it is
    assert surely_matches(
        kind(title_mode=TitleMode.EXACT, title_value="Raum"),
        AUTO,
        "raum",
        computed=False,
    )
