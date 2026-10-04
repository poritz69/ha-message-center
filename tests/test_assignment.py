"""Tests for assigning messages to kinds.

"All messages of this automation", duplicate conditions, orphaned kinds,
messages without a title, what an automation sends and what a condition
matches.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import CoreState, HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator
import voluptuous as vol

from custom_components.message_center.const import DOMAIN
from custom_components.message_center.scan import sent_messages

from .conftest import kind_data
from .test_delivery import setup, tick
from .test_services import TEXT, message_id_of, notify

WASH = "automation.waschmaschine"
WINDOW = "automation.fenster"
ROOM = "automation.raumklima"
MAIL = "automation.briefkasten"
VIA = "automation.uber_skript"


def trigger(event: str) -> list[dict[str, Any]]:
    """Trigger on a test event."""
    return [{"trigger": "event", "event_type": event}]


AUTOMATIONS = {
    "automation": [
        {
            "id": "waschmaschine",
            "alias": "Waschmaschine",
            "triggers": trigger("test_wash"),
            "actions": [
                {
                    "action": "notify.message_center",
                    "data": {"title": "Wäsche fertig", "message": "Bitte ausräumen."},
                },
                # the same message in a second place is still one message
                {
                    "if": [{"condition": "template", "value_template": "{{ false }}"}],
                    "then": [
                        {
                            "action": "notify.message_center",
                            "data": {
                                "title": "wäsche fertig",
                                "message": "Noch einmal.",
                            },
                        }
                    ],
                },
            ],
        },
        {
            "id": "fenster",
            "alias": "Fenster",
            "triggers": trigger("test_window"),
            "actions": [
                {
                    "choose": [
                        {
                            "conditions": [
                                {
                                    "condition": "template",
                                    "value_template": "{{ trigger.event.data.open }}",
                                }
                            ],
                            "sequence": [
                                {
                                    "action": "notify.message_center",
                                    "data": {"title": "Fenster offen", "message": "x"},
                                }
                            ],
                        }
                    ],
                    "default": [
                        {
                            "action": "message_center.send",
                            "data": {"title": "Fenster zu", "message": "x"},
                        }
                    ],
                },
                # a direct push is not a message of the center
                {
                    "if": [{"condition": "template", "value_template": "{{ false }}"}],
                    "then": [
                        {
                            "action": "notify.mobile_app_phone_alex",
                            "data": {"title": "Direkt", "message": "x"},
                        }
                    ],
                },
            ],
        },
        {
            "id": "raumklima",
            "alias": "Raumklima",
            "triggers": trigger("test_room"),
            "actions": [
                {
                    "action": "notify.message_center",
                    "data": {
                        "title": "Raum {{ trigger.event.data.room }}: lüften",
                        "message": "x",
                    },
                }
            ],
        },
        {
            "id": "briefkasten",
            "alias": "Briefkasten",
            "triggers": trigger("test_mail"),
            "actions": [
                {"action": "notify.message_center", "data": {"message": "Post ist da."}}
            ],
        },
        {
            "id": "ueber_skript",
            "alias": "Über Skript",
            "triggers": trigger("test_via"),
            "actions": [
                {
                    "action": "script.melden",
                    "data": {"title": "{{ trigger.event.data.title }}"},
                }
            ],
        },
    ]
}

SCRIPTS = {
    "script": {
        "melden": {
            "alias": "Melden",
            "sequence": [
                {
                    "action": "notify.message_center",
                    "data": {"title": "{{ title }}", "message": "aus dem Skript"},
                }
            ],
        }
    }
}


async def senders(hass: HomeAssistant) -> None:
    """Load the test automations and the script they may start."""
    assert await async_setup_component(hass, "script", SCRIPTS)
    assert await async_setup_component(hass, "automation", AUTOMATIONS)
    await hass.async_block_till_done()


async def fire(hass: HomeAssistant, event: str, **data: Any) -> None:
    """Fire a test event and wait for the automation and its message."""
    hass.bus.async_fire(event, data)
    for _ in range(3):
        await hass.async_block_till_done()


class Page:
    """The page's side of the WebSocket: one command, its answer.

    Connects at the first command: the web server must not start before
    Message Center has registered its panel.
    """

    def __init__(self, connect: Any) -> None:
        """Keep the way to connect."""
        self.connect = connect
        self.client: Any = None
        self.n = 0

    async def __call__(self, command: str, **data: Any) -> dict[str, Any]:
        """Send one command and return its reply."""
        if self.client is None:
            self.client = await self.connect()
        self.n += 1
        await self.client.send_json(
            {"id": self.n, "type": f"{DOMAIN}/{command}", **data}
        )
        while True:
            reply = await self.client.receive_json()
            if reply.get("id") == self.n and reply.get("type") == "result":
                return reply

    async def ok(self, command: str, **data: Any) -> Any:
        """Send one command that must succeed; return its result."""
        reply = await self(command, **data)
        assert reply["success"], reply
        return reply["result"]


@pytest.fixture
def page(hass: HomeAssistant, hass_ws_client: WebSocketGenerator) -> Page:
    """Return the connection of an administrator."""
    return Page(lambda: hass_ws_client(hass))


def kind_payload(**overrides: Any) -> dict[str, Any]:
    """Return the data of a kind as the page saves it."""
    data: dict[str, Any] = {
        "name": "Feuchte",
        "origin": None,
        "title_mode": "prefix",
        "title_value": "Feuchte",
        "group_id": None,
        "priority": 1,
    }
    data.update(overrides)
    return data


def kind_ids(entry: MockConfigEntry) -> dict[str, str]:
    """Subentry ids of the kinds by name."""
    return {
        sub.data["name"]: sid
        for sid, sub in entry.subentries.items()
        if sub.subentry_type == "kind"
    }


# ----- the condition "all messages of this automation" -------------------------


async def test_kind_any_needs_an_origin_and_keeps_no_text(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    page: Page,
) -> None:
    """Allow "any title" for an automation or script only; drop its text."""
    for origin in (None, "", "unknown"):
        reply = await page(
            "save",
            kind="kind",
            data=kind_payload(origin=origin, title_mode="any", title_value=""),
        )
        assert not reply["success"]
        assert reply["error"]["code"] == "invalid_format"

    result = await page.ok(
        "save",
        kind="kind",
        data=kind_payload(
            name="Wäsche", origin=WASH, title_mode="any", title_value="x"
        ),
    )
    stored = center_entry.subentries[result["subentry_id"]].data
    assert stored["title_mode"] == "any"
    assert stored["title_value"] == ""
    # without the text field at all
    await page.ok(
        "save",
        kind="kind",
        data={"name": "Post", "origin": MAIL, "title_mode": "any", "priority": 1},
    )
    # the other modes still need their text
    reply = await page(
        "save", kind="kind", data=kind_payload(title_mode="exact", title_value="")
    )
    assert reply["error"]["code"] == "invalid_format"


async def test_kind_any_takes_every_message_of_the_automation(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Every title of the automation gets the kind; other origins do not."""
    await setup(
        hass,
        make_entry,
        kinds=[kind_data(name="Klima", origin=ROOM, title_mode="any", priority=2)],
    )
    await senders(hass)
    await fire(hass, "test_room", room="Bad")
    await fire(hass, "test_room", room="Küche")
    await notify(hass, title="Raum Bad: lüften")
    center = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    kinds = {
        (m.origin, m.title): center.kind_name(m) for m in center.book.messages.values()
    }
    assert kinds == {
        (ROOM, "Raum Bad: lüften"): "Klima",
        (ROOM, "Raum Küche: lüften"): "Klima",
        ("unknown", "Raum Bad: lüften"): None,
    }
    assert [u["origin"] for u in center.unknown_items()] == ["unknown"]


# ----- duplicate conditions -------------------------------------------------------


async def test_duplicate_condition_is_refused_with_the_existing_kind(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    page: Page,
) -> None:
    """The same origin, mode and text (case and spaces aside) cannot be saved twice.

    Inactive kinds count; another mode, text or origin is fine.
    """
    entry = await setup(
        hass,
        make_entry,
        kinds=[
            kind_data(name="Feuchte"),
            kind_data(
                name="Alt", title_mode="exact", title_value="Frost", active=False
            ),
            kind_data(name="Wäsche", origin=WASH, title_mode="any", title_value=""),
        ],
    )
    ids = kind_ids(entry)

    for data, existing in (
        (kind_payload(name="Neu", title_value=" feuchte "), "Feuchte"),
        (kind_payload(name="Neu", title_mode="exact", title_value="FROST"), "Alt"),
        (kind_payload(name="Neu", origin=WASH, title_mode="any"), "Wäsche"),
    ):
        reply = await page("save", kind="kind", data=data)
        assert not reply["success"]
        assert reply["error"]["code"] == "duplicate"
        assert reply["error"]["kind_id"] == ids[existing]
        assert reply["error"]["name"] == existing
    assert len(entry.subentries) == 3

    for n, data in enumerate(
        (
            kind_payload(title_mode="contains"),
            kind_payload(title_value="Feuchte: Bad"),
            kind_payload(origin=WASH),
            kind_payload(origin=MAIL, title_mode="any"),
        )
    ):
        await page.ok("save", kind="kind", data={**data, "name": f"Andere {n}"})

    # changing a kind into the condition of another one is refused as well
    reply = await page(
        "save",
        kind="kind",
        subentry_id=ids["Alt"],
        data=kind_payload(name="Alt", title_value="FEUCHTE"),
    )
    assert reply["error"]["code"] == "duplicate"
    assert reply["error"]["name"] == "Feuchte"


async def test_editing_a_kind_compares_without_itself(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    page: Page,
) -> None:
    """Compare a kind without itself; a pair saved twice before stays editable.

    Two kinds with the same condition from an older version are not blocked:
    as long as the condition is not changed, name, group and the rest can be
    edited (the page moves a kind to a group this way).
    """
    entry = await setup(
        hass,
        make_entry,
        kinds=[kind_data(name="Erste"), kind_data(name="Zweite")],
    )
    ids = kind_ids(entry)
    await page.ok(
        "save",
        kind="kind",
        subentry_id=ids["Erste"],
        data=kind_payload(name="Erste", title_value="feuchte", priority=2),
    )
    await page.ok(
        "save",
        kind="kind",
        subentry_id=ids["Zweite"],
        data=kind_payload(name="Zweite neu", active=False),
    )
    assert entry.subentries[ids["Zweite"]].data["name"] == "Zweite neu"


# ----- orphaned kinds -------------------------------------------------------------


async def test_orphaned_kinds_are_marked(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    page: Page,
) -> None:
    """Mark a kind whose automation is neither a state nor registered as orphaned."""
    assert await async_setup_component(hass, "automation", {})
    assert await async_setup_component(hass, "script", {})
    hass.states.async_set("automation.da", "on", {"friendly_name": "Da"})
    registered = er.async_get(hass).async_get_or_create(
        "automation", "automation", "nur_registriert", suggested_object_id="registriert"
    )
    await setup(
        hass,
        make_entry,
        kinds=[
            kind_data(name="Weg", origin="automation.weg", title_mode="any"),
            kind_data(name="Da", origin="automation.da"),
            kind_data(name="Registriert", origin=registered.entity_id),
            kind_data(name="Skript weg", origin="script.weg", title_value="x"),
            kind_data(name="Frei", origin=None),
            kind_data(name="Unbekannt", origin="unknown", title_value="y"),
        ],
    )
    config = await page.ok("config")
    orphans = {k["name"]: k["orphan"] for k in config["kinds"]}
    assert orphans == {
        "Weg": True,
        "Da": False,
        "Registriert": False,
        "Skript weg": True,
        "Frei": False,
        "Unbekannt": False,
    }


async def test_no_orphans_while_home_assistant_starts(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    page: Page,
) -> None:
    """While Home Assistant starts or a domain is not loaded, nothing is orphaned.

    A YAML automation without an id has neither a state nor a registry entry
    until the automations are loaded; the page must not offer to delete its
    kind in the meantime.
    """
    await setup(
        hass,
        make_entry,
        kinds=[
            kind_data(name="Automation", origin="automation.weg", title_mode="any"),
            kind_data(name="Skript", origin="script.weg", title_value="x"),
        ],
    )

    async def orphans() -> dict[str, bool]:
        config = await page.ok("config")
        return {k["name"]: k["orphan"] for k in config["kinds"]}

    # neither automations nor scripts are loaded yet
    assert await orphans() == {"Automation": False, "Skript": False}
    assert await async_setup_component(hass, "script", {})
    assert await orphans() == {"Automation": False, "Skript": True}
    assert await async_setup_component(hass, "automation", {})
    hass.set_state(CoreState.starting)
    try:
        assert await orphans() == {"Automation": False, "Skript": False}
    finally:
        hass.set_state(CoreState.running)
    assert await orphans() == {"Automation": True, "Skript": True}


# ----- what an automation sends ---------------------------------------------------


async def test_origin_messages_read_the_automation(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    page: Page,
) -> None:
    """The calls to the center in an automation are its messages.

    The same fixed title counts once, a computed title is one message shown
    with a placeholder, a call without a title is called after the
    automation, and a direct push does not count.
    """
    await senders(hass)

    wash = await page.ok("origin_messages", origin=WASH)
    assert wash == {
        "source": "config",
        "messages": [
            {
                "title": "Wäsche fertig",
                "template": False,
                "display": "Wäsche fertig",
                "first_line": None,
            }
        ],
        "seen_titles": [],
        "multiple": False,
        "any_allowed": True,
    }

    window = await page.ok("origin_messages", origin=WINDOW)
    assert window["source"] == "config"
    assert [m["title"] for m in window["messages"]] == ["Fenster offen", "Fenster zu"]
    assert window["multiple"] is True

    room = await page.ok("origin_messages", origin=ROOM)
    assert room["messages"] == [
        {
            "title": "Raum {{ trigger.event.data.room }}: lüften",
            "template": True,
            "display": "Raum …: lüften",
            "first_line": None,
        }
    ]
    assert room["multiple"] is False

    mail = await page.ok("origin_messages", origin=MAIL)
    # one call without a title: one message, called after the automation,
    # shown with the first line of its text
    assert mail["messages"] == [
        {
            "title": None,
            "template": False,
            "display": "Briefkasten",
            "first_line": "Post ist da.",
        }
    ]
    assert mail["multiple"] is False

    script = await page.ok("origin_messages", origin="script.melden")
    assert script["source"] == "config"
    assert script["messages"][0]["template"] is True
    assert script["messages"][0]["display"] == "…"


async def test_origin_messages_count_each_call_without_a_title(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    page: Page,
) -> None:
    """Two calls without a title and with different texts: several messages.

    ``origin_messages`` lists both with their first lines and says
    ``multiple``; so does the entry under *New*, and the search agrees.
    """
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "feuchte_bad",
                    "alias": "Feuchte Bad",
                    "triggers": trigger("test_humid"),
                    "actions": [
                        {
                            "action": "notify.message_center",
                            "data": {"message": "Feuchte im Bad hoch\nBitte lüften."},
                        },
                        {
                            "if": [
                                {
                                    "condition": "template",
                                    "value_template": "{{ false }}",
                                }
                            ],
                            "then": [
                                {
                                    "action": "notify.message_center",
                                    "data": {"message": "Feuchte im Bad wieder normal"},
                                }
                            ],
                        },
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()

    result = await page.ok("origin_messages", origin="automation.feuchte_bad")
    assert result["source"] == "config"
    assert result["messages"] == [
        {
            "title": None,
            "template": False,
            "display": "Feuchte Bad",
            "first_line": "Feuchte im Bad hoch",
        },
        {
            "title": None,
            "template": False,
            "display": "Feuchte Bad",
            "first_line": "Feuchte im Bad wieder normal",
        },
    ]
    assert result["multiple"] is True

    await fire(hass, "test_humid")
    overview = await page.ok("overview")
    assert [(u["title"], u["multiple"]) for u in overview["unknown"]] == [
        ("Feuchte Bad", True)
    ]
    found = (await page.ok("scan"))["found"]
    assert [(i["multiple"], i["untitled_clash"]) for i in found] == [
        (True, True),
        (True, True),
    ]


async def test_origin_messages_fall_back_to_the_titles_seen(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    page: Page,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Without a call to the center in its configuration, the arrived titles decide."""
    await senders(hass)
    await fire(hass, "test_via", title="Erste")
    result = await page.ok("origin_messages", origin=VIA)
    assert result == {
        "source": "seen",
        "messages": [],
        "seen_titles": ["Erste"],
        "multiple": False,
        "any_allowed": True,
    }
    freezer.tick(timedelta(minutes=1))
    await fire(hass, "test_via", title="Zweite")
    result = await page.ok("origin_messages", origin=VIA)
    assert result["seen_titles"] == ["Zweite", "Erste"]
    assert result["multiple"] is True

    gone = await page.ok("origin_messages", origin="automation.gibt_es_nicht")
    assert gone == {
        "source": "none",
        "messages": [],
        "seen_titles": [],
        "multiple": False,
        "any_allowed": True,
    }
    # an unknown origin is no automation: no "all messages of", and the
    # titles of all unknown senders together are not its messages
    await notify(hass)
    await notify(hass, title="Akku leer")
    unknown = await page.ok("origin_messages", origin="unknown")
    assert unknown == {
        "source": "none",
        "messages": [],
        "seen_titles": [],
        "multiple": False,
        "any_allowed": False,
    }
    overview = await page.ok("overview")
    assert [u["multiple"] for u in overview["unknown"] if u["origin"] == "unknown"] == [
        False,
        False,
    ]


async def test_seen_titles_newest_first_once_each_at_most_ten(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    page: Page,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Different titles, case aside and in their newest spelling, at most ten."""
    await senders(hass)
    for n in range(11):
        freezer.tick(timedelta(seconds=10))
        await fire(hass, "test_room", room=f"r{n}")
    freezer.tick(timedelta(seconds=10))
    await fire(hass, "test_room", room="R3")
    result = await page.ok("origin_messages", origin=ROOM)
    assert result["seen_titles"] == [
        "Raum R3: lüften",
        "Raum r10: lüften",
        "Raum r9: lüften",
        "Raum r8: lüften",
        "Raum r7: lüften",
        "Raum r6: lüften",
        "Raum r5: lüften",
        "Raum r4: lüften",
        "Raum r2: lüften",
        "Raum r1: lüften",
    ]
    assert result["source"] == "config"
    assert result["multiple"] is False  # one computed title: one message


async def test_titles_seen_include_the_history(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A message that went on into the history still counts as seen."""
    await senders(hass)
    await fire(hass, "test_room", room="alt")
    # a day later the message is in the history, no longer in the book
    await tick(hass, freezer, hours=25)
    center = center_entry.runtime_data
    assert center.book.messages == {}
    assert center.book.history == []
    assert [e["title"] for e in center.history.entries] == ["Raum alt: lüften"]
    await fire(hass, "test_room", room="neu")
    assert center.seen_titles(ROOM) == ["Raum neu: lüften", "Raum alt: lüften"]
    assert [
        (p["origin"], p["title"], p["origin_name"]) for p in center.seen_pairs()
    ] == [
        (ROOM, "Raum neu: lüften", "Raumklima"),
        (ROOM, "Raum alt: lüften", "Raumklima"),
    ]
    assert center.title_counts({ROOM, MAIL}) == {ROOM: 2, MAIL: 0}


async def test_new_items_carry_multiple(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    page: Page,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Each entry of "new" says whether its automation sends several messages."""
    await senders(hass)
    await fire(hass, "test_window", open=True)
    await fire(hass, "test_wash")
    await fire(hass, "test_via", title="Eins")
    freezer.tick(timedelta(minutes=1))
    await fire(hass, "test_via", title="Zwei")
    overview = await page.ok("overview")
    multiple = {(u["origin"], u["title"]): u["multiple"] for u in overview["unknown"]}
    assert multiple == {
        (WINDOW, "Fenster offen"): True,
        (WASH, "Wäsche fertig"): False,
        (VIA, "Eins"): True,
        (VIA, "Zwei"): True,
    }
    assert {u["origin_name"] for u in overview["unknown"]} == {
        "Fenster",
        "Waschmaschine",
        "Über Skript",
    }
    # the stored pairs are not changed by it
    center = center_entry.runtime_data
    assert all("multiple" not in u for u in center.unknown.values())
    items = hass.states.get("sensor.message_center_new").attributes["items"]
    assert all("multiple" not in i for i in items)


# ----- saving a kind empties "new" ------------------------------------------------


async def test_saving_a_kind_clears_the_pairs_it_matches_from_new(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    page: Page,
) -> None:
    """A kind saved on the page takes its pairs out of "new" and the counter."""
    await senders(hass)
    await notify(hass)
    await notify(hass, title="Lüften: Bad")
    await fire(hass, "test_room", room="Bad")
    await fire(hass, "test_room", room="Flur")
    assert hass.states.get("sensor.message_center_new").state == "4"

    await page.ok("save", kind="kind", data=kind_payload())
    await hass.async_block_till_done()
    assert hass.states.get("sensor.message_center_new").state == "3"
    await page.ok(
        "save",
        kind="kind",
        data=kind_payload(name="Klima", origin=ROOM, title_mode="any"),
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.message_center_new").state == "1"
    overview = await page.ok("overview")
    assert [u["title"] for u in overview["unknown"]] == ["Lüften: Bad"]
    assert overview["new"] == 1


# ----- what a condition matches -----------------------------------------------------


async def matches_setup(hass: HomeAssistant, make_entry: Any) -> MockConfigEntry:
    """Two kinds and a few messages: one taken by a kind, one new, one by another."""
    entry = await setup(
        hass,
        make_entry,
        kinds=[
            kind_data(
                name="Fenster offen",
                origin=WINDOW,
                title_mode="exact",
                title_value="Fenster offen",
            ),
            kind_data(name="Lüften", title_mode="contains", title_value="lüften"),
            kind_data(name="Akku", title_mode="prefix", title_value="Akku"),
        ],
    )
    await senders(hass)
    await fire(hass, "test_window", open=True)
    await fire(hass, "test_window", open=False)
    await fire(hass, "test_room", room="Bad")
    return entry


async def test_kind_matches_new_and_seen_with_the_kind_that_takes_them(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    page: Page,
) -> None:
    """Which pairs of "new" and of the store a condition matches, and who gets them."""
    entry = await matches_setup(hass, make_entry)
    ids = kind_ids(entry)

    result = await page.ok(
        "kind_matches", origin=WINDOW, title_mode="any", title_value=""
    )
    assert result["valid"] is True
    assert [(i["origin"], i["title"], i["taken_by"]) for i in result["new"]] == [
        (WINDOW, "Fenster zu", None)
    ]
    assert result["new"][0]["origin_name"] == "Fenster"
    assert result["new_count"] == 1
    assert [(i["title"], i["taken_by"]) for i in result["seen"]] == [
        ("Fenster offen", {"kind_id": ids["Fenster offen"], "name": "Fenster offen"})
    ]
    assert result["seen"][0]["origin_name"] == "Fenster"
    assert result["seen_count"] == 1
    assert result["taken_count"] == 1
    assert result["overlaps"] == [
        {
            "kind_id": ids["Fenster offen"],
            "name": "Fenster offen",
            "winner": "other",
            "shared": 1,
        }
    ]
    assert result["overlap_count"] == 1
    assert result["probe"] is None

    # a stricter condition than "contains" takes the message over
    result = await page.ok(
        "kind_matches", origin=None, title_mode="prefix", title_value="raum"
    )
    assert [(i["title"], i["taken_by"]) for i in result["seen"]] == [
        ("Raum Bad: lüften", None)
    ]
    assert result["new"] == []
    assert result["taken_count"] == 0
    assert result["overlaps"] == [
        {"kind_id": ids["Lüften"], "name": "Lüften", "winner": "this", "shared": 1}
    ]


async def test_kind_matches_while_editing_and_for_the_original_message(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    page: Page,
) -> None:
    """Editing compares without the kind itself; a probe tells about one pair."""
    entry = await matches_setup(hass, make_entry)
    ids = kind_ids(entry)
    result = await page.ok(
        "kind_matches",
        origin=WINDOW,
        title_mode="exact",
        title_value="Fenster offen",
        kind_id=ids["Fenster offen"],
        probe={"origin": WINDOW, "title": "Fenster offen"},
    )
    assert [(i["title"], i["taken_by"]) for i in result["seen"]] == [
        ("Fenster offen", None)
    ]
    assert result["overlaps"] == []
    assert result["probe"] == {"matches": True, "taken_by": None}

    result = await page.ok(
        "kind_matches",
        origin=WINDOW,
        title_mode="exact",
        title_value="Fenster auf",
        kind_id=ids["Fenster offen"],
        probe={"origin": WINDOW, "title": "Fenster offen"},
    )
    assert result["seen"] == []
    assert result["probe"] == {"matches": False, "taken_by": None}

    # another kind would take the original message
    result = await page.ok(
        "kind_matches",
        origin=None,
        title_mode="contains",
        title_value="Fenster",
        probe={"origin": WINDOW, "title": "Fenster offen"},
    )
    assert result["probe"] == {
        "matches": True,
        "taken_by": {"kind_id": ids["Fenster offen"], "name": "Fenster offen"},
    }


async def test_kind_matches_overlaps_by_condition_and_invalid_input(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    page: Page,
) -> None:
    """An overlap shows without a message when one condition covers the other.

    An incomplete condition (being typed) matches nothing and says so.
    """
    entry = await matches_setup(hass, make_entry)
    ids = kind_ids(entry)
    result = await page.ok(
        "kind_matches", origin=None, title_mode="exact", title_value="Akku leer"
    )
    assert result["new"] == [] and result["seen"] == []
    assert result["overlaps"] == [
        {"kind_id": ids["Akku"], "name": "Akku", "winner": "this", "shared": 0}
    ]

    for condition in (
        {"origin": None, "title_mode": "any"},
        {"origin": "unknown", "title_mode": "any"},
        {"origin": None, "title_mode": "contains", "title_value": ""},
    ):
        result = await page.ok("kind_matches", **condition)
        assert result["valid"] is False
        assert result["new"] == result["seen"] == result["overlaps"] == []
        assert result["new_count"] == result["seen_count"] == 0


async def test_kind_matches_lists_are_limited(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    page: Page,
    freezer: FrozenDateTimeFactory,
) -> None:
    """At most 20 entries per list, newest first; the counters tell the rest."""
    for n in range(25):
        freezer.tick(timedelta(seconds=1))
        await notify(hass, title=f"Akku {n:02d}")
    result = await page.ok(
        "kind_matches", origin=None, title_mode="prefix", title_value="akku"
    )
    assert len(result["new"]) == 20
    assert result["new_count"] == 25
    assert result["new"][0]["title"] == "Akku 24"
    assert result["seen"] == []  # pairs of "new" are not listed twice
    assert result["seen_count"] == 0


async def test_page_commands_need_admin(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """The new commands read configuration and messages: administrators only."""
    page = Page(lambda: hass_ws_client(hass, hass_read_only_access_token))
    for command, data in (
        ("origin_messages", {"origin": WASH}),
        ("kind_matches", {"origin": WASH, "title_mode": "any"}),
    ):
        reply = await page(command, **data)
        assert reply["error"]["code"] == "unauthorized"


# ----- messages without a title ---------------------------------------------------


async def test_message_without_title_is_called_after_its_automation(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
) -> None:
    """The automation's name becomes the title, and with it the key and the id."""
    await senders(hass)
    await fire(hass, "test_mail")
    assert len(phone) == 1
    assert phone[0].data["title"] == "Briefkasten"
    assert phone[0].data["data"]["tag"] == message_id_of(hass, "Briefkasten", MAIL)
    center = center_entry.runtime_data
    msg = center.book.messages[message_id_of(hass, "Briefkasten", MAIL)]
    assert (msg.title, msg.key, msg.message) == (
        "Briefkasten",
        "Briefkasten",
        "Post ist da.",
    )
    new = hass.states.get("sensor.message_center_new").attributes["items"]
    assert [(i["origin"], i["title"]) for i in new] == [(MAIL, "Briefkasten")]


async def test_message_without_title_long_name_is_cut(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
) -> None:
    """A name longer than a title may be is cut to 100 characters."""
    alias = "A" * 120
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "lang",
                    "alias": alias,
                    "triggers": trigger("test_long"),
                    "actions": [
                        {"action": "notify.message_center", "data": {"message": "x"}}
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    await fire(hass, "test_long")
    assert phone[0].data["title"] == "A" * 100


async def test_message_without_title_and_origin_is_mitteilung(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
) -> None:
    """Without a known origin the title stays "Mitteilung"."""
    await notify(hass, title=None)
    assert phone[0].data["title"] == "Mitteilung"
    assert phone[0].data["data"]["tag"] == message_id_of(hass, "Mitteilung")


async def test_send_still_needs_a_title(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
) -> None:
    """``send`` is unchanged: its title is required."""
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "send", {"message": TEXT}, blocking=True)
    assert phone == []


async def test_kind_waiting_for_mitteilung_still_takes_untitled_messages(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    page: Page,
) -> None:
    """A kind made for "Mitteilung" before the title changed keeps its messages.

    Up to 0.11.1b1 a message without a title was called "Mitteilung". A kind
    that waits for that title from an automation still takes the
    automation's untitled messages, with its priority, as long as no kind
    matches their new title. A message with a title of its own is not taken
    by it.
    """
    await setup(
        hass,
        make_entry,
        kinds=[
            kind_data(
                name="Post",
                origin=MAIL,
                title_mode="exact",
                title_value="Mitteilung",
                priority=2,
            ),
            kind_data(name="Alt", title_mode="exact", title_value="Mitteilung"),
        ],
    )
    await senders(hass)
    await fire(hass, "test_mail")
    await fire(hass, "test_wash")
    center = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    taken = {
        m.title: (center.kind_name(m), m.priority)
        for m in center.book.messages.values()
    }
    assert taken == {"Briefkasten": ("Post", 2), "Wäsche fertig": (None, 1)}
    assert [(u["origin"], u["title"]) for u in center.unknown_items()] == [
        (WASH, "Wäsche fertig")
    ]
    # the search names the kind the call will get
    found = (await page.ok("scan"))["found"]
    assert {i["entity_id"]: i["kind"] for i in found}[MAIL] == "Post"


async def test_kind_for_the_new_title_wins_over_the_old_one(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """The old kind is a fallback only: a kind for the new title wins."""
    await setup(
        hass,
        make_entry,
        kinds=[
            kind_data(
                name="Post alt",
                origin=MAIL,
                title_mode="exact",
                title_value="Mitteilung",
                priority=2,
            ),
            kind_data(name="Post", origin=MAIL, title_mode="any", priority=3),
        ],
    )
    await senders(hass)
    await fire(hass, "test_mail")
    center = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    (msg,) = center.book.messages.values()
    assert (msg.title, center.kind_name(msg), msg.priority) == (
        "Briefkasten",
        "Post",
        3,
    )


# ----- the name of an automation, as its messages carry it ----------------------


async def test_name_from_the_entity_settings_is_the_title_everywhere(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    page: Page,
) -> None:
    """A name given in the entity settings names untitled messages everywhere.

    The message, ``origin_messages`` and the search use the same name: the
    one of the automation's state. A kind made from the search's suggestion
    then takes the message.
    """
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "keller",
                    "alias": "Keller",
                    "triggers": trigger("test_cellar"),
                    "actions": [
                        {
                            "action": "notify.message_center",
                            "data": {"title": "Keller nass", "message": "x"},
                        },
                        {"action": "notify.message_center", "data": {"message": "y"}},
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    er.async_get(hass).async_update_entity("automation.keller", name="Kellerraum")
    await hass.async_block_till_done()

    result = await page.ok("origin_messages", origin="automation.keller")
    assert [m["display"] for m in result["messages"]] == ["Keller nass", "Kellerraum"]
    assert result["multiple"] is True
    found = (await page.ok("scan"))["found"]
    untitled = next(i for i in found if i["title"] is None)
    assert untitled["name"] == "Kellerraum"
    suggestion = untitled["suggestion"]
    assert suggestion == {"mode": "exact", "value": "Kellerraum"}

    await page.ok(
        "save",
        kind="kind",
        data=kind_payload(
            name="Keller",
            origin="automation.keller",
            title_mode=suggestion["mode"],
            title_value=suggestion["value"],
        ),
    )
    await fire(hass, "test_cellar")
    center = center_entry.runtime_data
    taken = {m.title: center.kind_name(m) for m in center.book.messages.values()}
    assert taken == {"Keller nass": None, "Kellerraum": "Keller"}
    seen = await page.ok("origin_messages", origin="automation.keller")
    assert sorted(seen["seen_titles"]) == ["Keller nass", "Kellerraum"]


# ----- an automation that still pushes directly ---------------------------------


async def test_origin_messages_of_an_automation_that_still_pushes_directly(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    page: Page,
) -> None:
    """Without calls to the center or arrived titles, the direct pushes tell.

    They are what the automation sends once it goes through the center, as
    the search counts them: a notification in the Home Assistant UI does
    not count. The answer agrees with the search's ``multiple``.
    """

    def push(title: str, action: str = "notify.mobile_app_phone_alex") -> dict:
        return {"action": action, "data": {"title": title, "message": "x"}}

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "zwei_direkt",
                    "alias": "Zwei direkt",
                    "triggers": trigger("test_none"),
                    "actions": [
                        push("Eins"),
                        push("Zwei"),
                        push("Drei", "persistent_notification.create"),
                    ],
                },
                {
                    "id": "eine_direkt",
                    "alias": "Eine direkt",
                    "triggers": trigger("test_none"),
                    "actions": [
                        push("Eins"),
                        push("Hinweis", "notify.persistent_notification"),
                    ],
                },
            ]
        },
    )
    await hass.async_block_till_done()

    two = await page.ok("origin_messages", origin="automation.zwei_direkt")
    assert two == {
        "source": "direct",
        "messages": [
            {"title": "Eins", "template": False, "display": "Eins", "first_line": None},
            {"title": "Zwei", "template": False, "display": "Zwei", "first_line": None},
        ],
        "seen_titles": [],
        "multiple": True,
        "any_allowed": True,
    }
    one = await page.ok("origin_messages", origin="automation.eine_direkt")
    assert (one["source"], one["multiple"]) == ("direct", False)
    assert [m["title"] for m in one["messages"]] == ["Eins"]

    found = (await page.ok("scan"))["found"]
    by_origin = {
        i["entity_id"]: i["multiple"] for i in found if i["status"] == "direct"
    }
    assert by_origin == {
        "automation.zwei_direkt": True,
        "automation.eine_direkt": False,
    }


# ----- computed titles longer than a title may be --------------------------------


def test_long_computed_titles_are_shown_and_told_apart_by_their_whole_text() -> None:
    """A computed title is read as a whole, not cut to the length of a title.

    Cut, its last statement would lose its end and show as code; two
    templates that differ only after 100 characters would be one message.
    """
    head = (
        "{% if is_state('binary_sensor.fenster_kueche', 'on') %}Fenster Küche offen"
        "{% elif is_state('binary_sensor.fenster_bad', 'on') %}"
    )
    first = head + "Fenster Bad offen{% endif %}"
    second = head + "Fenster Bad gekippt{% endif %}"
    assert len(head) > 100
    messages = sent_messages([(first, "x"), (second, "x")], "Fenster")
    assert [(m["template"], m["display"]) for m in messages] == [
        (True, "…"),
        (True, "…"),
    ]
    assert all(len(m["title"]) == 100 for m in messages)
    # a fixed title once, case aside; a call without a title is a message of
    # its own, called after the automation, even next to a title of that name
    calls = [("Fest", "a"), (None, "Offen"), ("fest", "b"), ("fenster", "c")]
    assert sent_messages(calls, "Fenster") == [
        {"title": "Fest", "template": False, "display": "Fest", "first_line": None},
        {"title": None, "template": False, "display": "Fenster", "first_line": "Offen"},
        {
            "title": "fenster",
            "template": False,
            "display": "fenster",
            "first_line": None,
        },
    ]


def test_each_call_without_a_title_is_a_message_of_its_own() -> None:
    """Calls without a title differ by their text, not by their title.

    All of them are called after the automation; two with different texts
    are two messages (that would replace each other on the phone), the same
    text twice is one, case and spaces aside. Their first line is shown,
    computed parts as a placeholder, cut to the length of a title.
    """
    long_line = "Sehr lang " * 20
    calls = [
        (None, "Feuchte im Bad hoch\nBitte lüften."),
        (None, "  feuchte im bad hoch\nbitte lüften. "),
        (None, "Feuchte im Bad wieder normal"),
        (None, "{{ raum }}: Fenster offen\nseit {{ minuten }} min"),
        (None, None),
        (None, long_line),
    ]
    messages = sent_messages(calls, "Raumklima")
    assert [(m["title"], m["display"], m["first_line"]) for m in messages] == [
        (None, "Raumklima", "Feuchte im Bad hoch"),
        (None, "Raumklima", "Feuchte im Bad wieder normal"),
        (None, "Raumklima", "…: Fenster offen"),
        (None, "Raumklima", None),
        (None, "Raumklima", long_line.strip()[:100]),
    ]
    assert not any(m["template"] for m in messages)
    # one call without a title is one message
    assert len(sent_messages([(None, "Post ist da.")], "Briefkasten")) == 1


async def test_origin_messages_read_long_computed_titles_whole(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    page: Page,
) -> None:
    """The kind dialog gets no code and two messages for two long templates."""
    head = (
        "{% if is_state('binary_sensor.fenster_kueche', 'on') %}Fenster Küche offen"
        "{% elif is_state('binary_sensor.fenster_bad', 'on') %}"
    )
    steps = [
        {
            "action": "notify.message_center",
            "data": {"title": head + end + "{% endif %}", "message": "x"},
        }
        for end in ("Fenster Bad offen", "Fenster Bad gekippt")
    ]
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "fenster_lang",
                    "alias": "Fenster lang",
                    "triggers": trigger("test_none"),
                    "actions": steps,
                }
            ]
        },
    )
    await hass.async_block_till_done()
    result = await page.ok("origin_messages", origin="automation.fenster_lang")
    assert [m["display"] for m in result["messages"]] == ["…", "…"]
    assert result["multiple"] is True


# ----- text of a condition --------------------------------------------------------


async def test_condition_text_is_saved_without_surrounding_spaces(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    page: Page,
) -> None:
    """Spaces around the text are dropped: the double check and the matching agree.

    A text of spaces only is no text.
    """
    entry = await matches_setup(hass, make_entry)
    result = await page.ok(
        "save",
        kind="kind",
        data=kind_payload(name="Feuchte", title_mode="exact", title_value=" Feuchte "),
    )
    assert entry.subentries[result["subentry_id"]].data["title_value"] == "Feuchte"
    reply = await page(
        "save", kind="kind", data=kind_payload(name="Leer", title_value="   ")
    )
    assert reply["error"]["code"] == "invalid_format"

    spaced = await page.ok(
        "kind_matches", origin=WINDOW, title_mode="exact", title_value=" Fenster zu "
    )
    assert spaced["valid"] is True
    assert [i["title"] for i in spaced["new"]] == ["Fenster zu"]
    blank = await page.ok(
        "kind_matches", origin=None, title_mode="contains", title_value="   "
    )
    assert blank["valid"] is False


# ----- overlaps known from the configuration --------------------------------------


async def test_overlaps_from_the_configuration_before_any_message(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    page: Page,
) -> None:
    """An overlap shows before a message arrived when the automation sends the title.

    "All messages of" an automation beats every kind without an origin; a
    kind for the automation's fixed title would lose its messages unseen. Of
    a computed title only the fixed parts are known: "begins with" and
    "contains" are compared with them, "exact" is not.
    """
    entry = await setup(
        hass,
        make_entry,
        kinds=[
            kind_data(name="Wäsche", title_mode="exact", title_value="Wäsche fertig"),
            kind_data(name="Raum", title_mode="prefix", title_value="Raum"),
            kind_data(name="Lüften", title_mode="contains", title_value="lüften"),
            kind_data(name="Nur Raum", title_mode="exact", title_value="Raum"),
            kind_data(name="Fenster", title_mode="prefix", title_value="Fenster"),
        ],
    )
    ids = kind_ids(entry)
    await senders(hass)

    wash = await page.ok("kind_matches", origin=WASH, title_mode="any")
    assert wash["new"] == wash["seen"] == []
    assert wash["overlaps"] == [
        {"kind_id": ids["Wäsche"], "name": "Wäsche", "winner": "this", "shared": 0}
    ]

    room = await page.ok("kind_matches", origin=ROOM, title_mode="any")
    assert {o["name"]: o["winner"] for o in room["overlaps"]} == {
        "Raum": "this",
        "Lüften": "this",
    }

    # the other way round: a kind without origin next to "all messages of"
    await page.ok(
        "save",
        kind="kind",
        data=kind_payload(name="Waschmaschine", origin=WASH, title_mode="any"),
    )
    ids = kind_ids(entry)
    single = await page.ok(
        "kind_matches", origin=None, title_mode="prefix", title_value="Wäsche fertig"
    )
    assert single["overlaps"] == [
        {"kind_id": ids["Wäsche"], "name": "Wäsche", "winner": "other", "shared": 0},
        {
            "kind_id": ids["Waschmaschine"],
            "name": "Waschmaschine",
            "winner": "other",
            "shared": 0,
        },
    ]
    # a title the automation does not send is no overlap
    other = await page.ok(
        "kind_matches", origin=None, title_mode="exact", title_value="Wäsche nass"
    )
    assert other["overlaps"] == []
