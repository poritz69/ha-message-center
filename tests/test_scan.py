"""Tests for the search for notifications in the house."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import load_yaml
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.message_center.const import DOMAIN
from custom_components.message_center.scan import (
    TITLE_HINT_MAX_LENGTH,
    display_title,
    find_calls,
    scan_files,
    suggest_title,
    title_hints,
)

from .conftest import kind_data

ACTIONS: list[dict[str, Any]] = [
    {
        "choose": [
            {
                "conditions": [],
                "sequence": [
                    {
                        "action": "notify.send_message",
                        "target": {"entity_id": "notify.handy"},
                        "data": {"message": "Feuchte zu hoch\n\n{{ x }} %"},
                    }
                ],
            }
        ],
        "default": [
            {
                "action": "notify.mobile_app_handy",
                "data": {"title": "Fenster offen", "message": "Bitte schließen."},
            }
        ],
    },
    {"action": "notify.message_center", "data": {"title": "Schon da", "message": "x"}},
    {"action": "persistent_notification.create", "data": {"message": "nur in HA"}},
    {"action": "light.turn_on", "target": {"entity_id": "light.flur"}},
    {
        "action": "notify.mobile_app_handy",
        "data": {"title": "Akku {{ p }} %", "message": "x"},
    },
    {"action": "notify.mobile_app_handy", "data": {"title": "{{ t }}", "message": "x"}},
]


async def scan(hass: HomeAssistant, hass_ws_client: WebSocketGenerator) -> dict:
    """Run the search through the page's command."""
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/scan"})
    reply = await client.receive_json()
    assert reply["success"], reply
    return reply["result"]


async def test_scan_finds_nested_calls_with_status_and_suggestions(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Calls are found at any depth; each gets a status, a title and a kind."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "a1",
                    "alias": "Klima melden",
                    "triggers": [{"trigger": "event", "event_type": "x"}],
                    "actions": ACTIONS,
                }
            ]
        },
    )
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "sag_bescheid": {
                    "alias": "Sag Bescheid",
                    "sequence": [
                        {
                            "action": "notify.mobile_app_handy",
                            "data": {"title": "Vom Skript", "message": "x"},
                        }
                    ],
                }
            }
        },
    )
    entry = make_entry(
        kinds=[
            kind_data(name="Fenster", title_mode="exact", title_value="Fenster offen")
        ]
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await scan(hass, hass_ws_client)
    found = result["found"]
    by_title = {(i["title"] or i["first_line"]): i for i in found}

    humid = by_title["Feuchte zu hoch"]
    assert humid["source"] == "automation"
    assert humid["entity_id"] == "automation.klima_melden"
    assert humid["name"] == "Klima melden"
    assert humid["target"] == "notify.send_message → notify.handy"
    assert humid["status"] == "direct"
    assert humid["title"] is None
    assert humid["first_line"] == "Feuchte zu hoch"
    # the automation sends several messages; one without a title is called
    # after the automation, not after its first line
    assert humid["multiple"] is True
    assert humid["suggestion"] == {"mode": "exact", "value": "Klima melden"}
    assert humid["kind"] is None

    window = by_title["Fenster offen"]
    assert window["status"] == "direct"
    assert window["kind"] == "Fenster"

    assert by_title["Schon da"]["status"] == "center"
    assert by_title["nur in HA"]["status"] == "persistent"
    battery = by_title["Akku {{ p }} %"]
    assert battery["title_template"] is True
    assert battery["suggestion"] == {"mode": "prefix", "value": "Akku"}
    assert by_title["{{ t }}"]["suggestion"] is None

    script = by_title["Vom Skript"]
    assert script["source"] == "script"
    assert script["entity_id"] == "script.sag_bescheid"
    assert script["origin"] is None  # depends on who starts the script
    assert script["multiple"] is False
    # without a known origin there is no "all messages of": the title decides
    assert script["suggestion"] == {"mode": "exact", "value": "Vom Skript"}

    assert not any(i["service"].startswith("light.") for i in found)
    assert len(found) == 7
    assert result["counts"]["automations"] == 1
    assert result["counts"]["scripts"] == 1
    assert result["counts"]["direct"] >= 5


async def test_scan_reports_file_and_line(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: Any,
    hass_ws_client: WebSocketGenerator,
    tmp_path: Path,
) -> None:
    """Steps read from YAML carry the file and the line of the call."""
    file = tmp_path / "klima_paket.yaml"
    file.write_text(
        "automation:\n"
        "  - alias: Aus der Datei\n"
        "    triggers:\n"
        "      - trigger: event\n"
        "        event_type: x\n"
        "    actions:\n"
        "      - action: notify.send_message\n"
        "        target:\n"
        "          entity_id: notify.handy\n"
        "        data:\n"
        "          message: Hallo\n",
        encoding="utf-8",
    )
    config = await hass.async_add_executor_job(load_yaml, str(file))
    assert await async_setup_component(hass, "automation", config)
    await hass.async_block_till_done()

    result = await scan(hass, hass_ws_client)
    item = next(i for i in result["found"] if i["name"] == "Aus der Datei")
    assert item["file"] == "klima_paket.yaml"
    assert item["line"] == 7
    assert item["edit_url"] is None  # not in automations.yaml: no UI editor


def test_scan_files_finds_other_places_and_skips_covered(tmp_path: Path) -> None:
    """The text search adds other files; steps already found are left out."""
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages" / "klima.yaml").write_text(
        "automation:\n  - alias: x\n    actions:\n"
        "      - action: notify.send_message\n        target:\n"
        "          entity_id: notify.handy\n",
        encoding="utf-8",
    )
    (tmp_path / "apps").mkdir()
    (tmp_path / "apps" / "hallo.py").write_text(
        'import x\nself.call_service("notify/mobile_app_handy", message="Hi")\n',
        encoding="utf-8",
    )
    (tmp_path / "fertig.yaml").write_text(
        "- action: notify.message_center\n", encoding="utf-8"
    )
    (tmp_path / "secrets.yaml").write_text("x: notify.geheim\n", encoding="utf-8")
    (tmp_path / "alt.yaml.bak-2026").write_text("notify.alt\n", encoding="utf-8")
    (tmp_path / "custom_components").mkdir()
    (tmp_path / "custom_components" / "x.py").write_text("notify.x\n", encoding="utf-8")

    hits, files = scan_files(str(tmp_path), {"packages/klima.yaml": [4]})
    assert files == 3  # klima.yaml, hallo.py, fertig.yaml
    assert sorted((h["file"], h["line"], h["status"]) for h in hits) == [
        ("apps/hallo.py", 2, "direct"),
        ("fertig.yaml", 1, "center"),
    ]
    # without the cover both lines of the package show up
    hits, _ = scan_files(str(tmp_path), {})
    assert [h["line"] for h in hits if h["file"] == "packages/klima.yaml"] == [4, 6]


def test_scan_files_returns_names_not_the_raw_line(tmp_path: Path) -> None:
    """A file hit names file, line and the actions found, never the line itself.

    The line may carry a password, a token or the text of a message; the
    page is for administrators, but nothing of that belongs there.
    """
    (tmp_path / "configuration.yaml").write_text(
        "shell_command:\n"
        "  push: curl -s -u admin:hunter2 https://x.invalid/api/services/"
        "notify/mobile_app_x\n"
        "  hook: curl https://hooks.example.invalid/api/services/"
        "notify/mobile_app_x?token=KURZTOKEN123\n",
        encoding="utf-8",
    )
    (tmp_path / "run.sh").write_text(
        'curl -H "Authorization: Bearer abc123" https://x.invalid/api/services/'
        "notify/mobile_app_x -d '{}'\n"
        "# notify.mobile_app_x and notify/mobile_app_x again\n",
        encoding="utf-8",
    )
    (tmp_path / "apps").mkdir()
    (tmp_path / "apps" / "hallo.py").write_text(
        'self.call_service("notify/mobile_app_handy", message="Hi")\n',
        encoding="utf-8",
    )

    hits, _ = scan_files(str(tmp_path), {})
    assert sorted((h["file"], h["line"], h["text"]) for h in hits) == [
        ("apps/hallo.py", 1, "notify.mobile_app_handy"),
        ("configuration.yaml", 2, "notify.mobile_app_x"),
        ("configuration.yaml", 3, "notify.mobile_app_x"),
        ("run.sh", 1, "notify.mobile_app_x"),
        ("run.sh", 2, "notify.mobile_app_x"),
    ]
    for secret in ("hunter2", "Bearer", "abc123", "KURZTOKEN123", "Hi", "curl"):
        assert not any(secret in h["text"] for h in hits)


def test_device_action_and_title_suggestions() -> None:
    """A mobile_app device action counts as a call; suggestions follow the title."""
    step = {
        "device_id": "abc",
        "domain": "mobile_app",
        "type": "notify",
        "message": "Hi",
    }
    assert [name for _, name in find_calls({"actions": [step]})] == ["mobile_app"]
    assert suggest_title("Fest") == {"mode": "exact", "value": "Fest"}
    assert suggest_title("Raum {{ r }}: zu warm") == {
        "mode": "prefix",
        "value": "Raum",
    }
    assert suggest_title("{{ x }}") is None
    sentence = (
        "Keller: Der Sensor meldet seit einer Stunde keinen brauchbaren "
        "Messwert, bitte prüfen."
    )
    assert suggest_title(sentence) == {"mode": "exact", "value": sentence}
    # the first line of the text is no title: the message gets the name of
    # its automation instead
    assert suggest_title(None) is None


def test_display_of_computed_titles() -> None:
    """Computed parts of a title are shown as a placeholder."""
    assert display_title("Fest") == "Fest"
    assert display_title("Raum {{ r }}: zu warm") == "Raum …: zu warm"
    assert display_title("{{ a }} {{ b }}") == "…"
    assert display_title("{% if x %}Auf{% else %}Zu{% endif %}: Tür") == "…: Tür"


async def test_scan_needs_admin(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: Any,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """The search reads configuration: administrators only."""
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/scan"})
    reply = await client.receive_json()
    assert not reply["success"]
    assert reply["error"]["code"] == "unauthorized"


async def test_scripts_from_the_own_blueprint_are_not_reported(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """The fallback push of the own blueprint is not a place that sends directly."""
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(
        entry.entry_id
    )  # installs the blueprint
    await hass.async_block_till_done()
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "melden": {
                    "use_blueprint": {
                        "path": f"{DOMAIN}/nachricht_senden.yaml",
                        "input": {
                            "ready_entity": "binary_sensor.message_center_ready",
                            "fallback_target": "mobile_app_handy",
                        },
                    }
                },
                "direkt": {
                    "sequence": [
                        {
                            "action": "notify.mobile_app_handy",
                            "data": {"title": "Direkt", "message": "x"},
                        }
                    ]
                },
            }
        },
    )
    await hass.async_block_till_done()

    result = await scan(hass, hass_ws_client)
    assert result["counts"]["scripts"] == 2
    assert [item["entity_id"] for item in result["found"]] == ["script.direkt"]
    assert result["counts"]["direct"] == 1
    path = Path(
        hass.config.path("blueprints", "script", DOMAIN, "nachricht_senden.yaml")
    )
    await hass.async_add_executor_job(path.unlink)


def notify_step(
    title: str | None,
    *,
    action: str = "notify.mobile_app_handy",
    message: str = "Erste Zeile\nmehr",
) -> dict:
    """Return a notifying step with an optional title."""
    data = {"message": message}
    if title is not None:
        data["title"] = title
    return {"action": action, "data": data}


def automation(alias: str, *steps: dict) -> dict:
    """Return an automation with the given steps."""
    return {
        "id": alias.lower().replace(" ", "_"),
        "alias": alias,
        "triggers": [{"trigger": "event", "event_type": "x"}],
        "actions": list(steps),
    }


async def test_scan_suggests_all_messages_of_an_automation_that_sends_one(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """One message: "all messages of this automation"; several: the titles.

    A notification in the Home Assistant UI does not count, the same title
    twice is one message. A script has no origin of its own until it runs,
    so its suggestion stays with the title.
    """
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                automation(
                    "Nur eine",
                    notify_step("Wäsche fertig"),
                    notify_step(None, action="persistent_notification.create"),
                ),
                automation("Ohne Titel", notify_step(None)),
                automation(
                    "Mehrere",
                    notify_step("Erste", action="notify.message_center"),
                    notify_step(None),
                ),
                automation(
                    "Gleich zweimal", notify_step("Tür offen"), notify_step("tür offen")
                ),
            ]
        },
    )
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "ohne": {"alias": "Skript ohne Titel", "sequence": [notify_step(None)]},
                "mit": {
                    "alias": "Skript mit Titel",
                    "sequence": [notify_step("Hallo")],
                },
            }
        },
    )
    entry = make_entry(
        kinds=[
            kind_data(name="Wäsche", origin="automation.nur_eine", title_mode="any"),
            kind_data(name="Sammel", title_mode="exact", title_value="Mehrere"),
        ]
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    found = (await scan(hass, hass_ws_client))["found"]
    items = {
        (i["name"], i["title"], i["service"]): (
            i["suggestion"],
            i["multiple"],
            i["kind"],
        )
        for i in found
    }
    any_title = {"mode": "any"}
    assert items == {
        ("Nur eine", "Wäsche fertig", "notify.mobile_app_handy"): (
            any_title,
            False,
            "Wäsche",
        ),
        ("Nur eine", None, "persistent_notification.create"): (None, False, None),
        ("Ohne Titel", None, "notify.mobile_app_handy"): (any_title, False, None),
        ("Mehrere", "Erste", "notify.message_center"): (
            {"mode": "exact", "value": "Erste"},
            True,
            None,
        ),
        ("Mehrere", None, "notify.mobile_app_handy"): (
            {"mode": "exact", "value": "Mehrere"},
            True,
            "Sammel",
        ),
        ("Gleich zweimal", "Tür offen", "notify.mobile_app_handy"): (
            any_title,
            False,
            None,
        ),
        ("Gleich zweimal", "tür offen", "notify.mobile_app_handy"): (
            any_title,
            False,
            None,
        ),
        ("Skript ohne Titel", None, "notify.mobile_app_handy"): (None, False, None),
        ("Skript mit Titel", "Hallo", "notify.mobile_app_handy"): (
            {"mode": "exact", "value": "Hallo"},
            False,
            None,
        ),
    }
    origins = {i["name"]: i["origin"] for i in found}
    assert origins["Nur eine"] == "automation.nur_eine"
    assert origins["Skript ohne Titel"] is None


async def test_scan_counts_every_call_without_a_title_as_a_message_of_its_own(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Two calls without a title and with different texts are two messages.

    Both would be called after the automation and replace each other on the
    phone: the automation sends several messages, and each of these calls
    is told to get a title of its own (``untitled_clash``), with the first
    line of its text as an example (``title_hint``) where that line is fixed
    and tells the call apart. The same text twice is one message; a single
    call without a title stays "all messages of this automation". A script
    is counted the same way.
    """
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                automation(
                    "Feuchte Bad",
                    notify_step(None, message="Feuchte im Bad hoch\nBitte lüften."),
                    notify_step(None, message="Feuchte im Bad wieder normal"),
                ),
                automation(
                    "Gleicher Text",
                    notify_step(None, message="Tür offen"),
                    notify_step(None, message="tür offen"),
                ),
                automation(
                    "Einmal ohne",
                    notify_step("Mit Titel"),
                    notify_step(None, message="Ohne Titel"),
                ),
                # a computed first line is no title: every value would be a
                # message of its own; the same first line tells nothing apart
                automation(
                    "Vorlagen",
                    notify_step(
                        None,
                        message="{% if is_state('binary_sensor.f', 'on') %}"
                        "\nFenster offen{% endif %}",
                    ),
                    notify_step(None, message="{{ states('sensor.h') }} % im Bad"),
                ),
                automation(
                    "Waschmaschine",
                    notify_step(None, message="Waschmaschine\nFertig"),
                    notify_step(None, message="Waschmaschine\nFehler"),
                ),
            ]
        },
    )
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "zwei": {
                    "alias": "Zwei ohne Titel",
                    "sequence": [
                        notify_step(None, message="Eins"),
                        notify_step(None, message="Zwei"),
                    ],
                }
            }
        },
    )
    entry = make_entry(kinds=[])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    found = (await scan(hass, hass_ws_client))["found"]
    items = {
        (i["name"], i["title"], i["first_line"]): (
            i["suggestion"],
            i["multiple"],
            i["untitled_clash"],
            i["title_hint"],
        )
        for i in found
    }
    any_title = {"mode": "any"}
    named = {"mode": "exact", "value": "Feuchte Bad"}
    assert items == {
        ("Feuchte Bad", None, "Feuchte im Bad hoch"): (
            named,
            True,
            True,
            "Feuchte im Bad hoch",
        ),
        ("Feuchte Bad", None, "Feuchte im Bad wieder normal"): (
            named,
            True,
            True,
            "Feuchte im Bad wieder normal",
        ),
        ("Gleicher Text", None, "Tür offen"): (any_title, False, False, None),
        ("Gleicher Text", None, "tür offen"): (any_title, False, False, None),
        ("Einmal ohne", "Mit Titel", "Erste Zeile"): (
            {"mode": "exact", "value": "Mit Titel"},
            True,
            False,
            None,
        ),
        ("Einmal ohne", None, "Ohne Titel"): (
            {"mode": "exact", "value": "Einmal ohne"},
            True,
            False,
            None,
        ),
        ("Vorlagen", None, "{% if is_state('binary_sensor.f', 'on') %}"): (
            {"mode": "exact", "value": "Vorlagen"},
            True,
            True,
            None,
        ),
        ("Vorlagen", None, "{{ states('sensor.h') }} % im Bad"): (
            {"mode": "exact", "value": "Vorlagen"},
            True,
            True,
            None,
        ),
        ("Waschmaschine", None, "Waschmaschine"): (
            {"mode": "exact", "value": "Waschmaschine"},
            True,
            True,
            None,
        ),
        ("Zwei ohne Titel", None, "Eins"): (None, True, True, "Eins"),
        ("Zwei ohne Titel", None, "Zwei"): (None, True, True, "Zwei"),
    }
    # both calls of "Waschmaschine" begin with the same line
    assert len([i for i in found if i["name"] == "Waschmaschine"]) == 2


def test_title_hints_only_for_a_fixed_line_that_tells_the_call_apart() -> None:
    """The first line of a call without a title as an example for its title.

    Only a line without computed parts, short enough for a title on the
    phone, that no other message without a title begins with and that is
    neither a title of the automation nor its name (case aside); the same
    text twice is one message and keeps its line. Calls with a title get
    nothing.
    """
    calls = [
        ("Fenster offen", "Bitte schließen."),
        (None, "Feuchte im Bad hoch\nBitte lüften."),
        (None, "feuchte im bad hoch\nbitte lüften."),
        (None, "Waschmaschine\nFertig"),
        (None, "waschmaschine\nFehler E3"),
        (None, "{% if x %}\nTür offen{% endif %}"),
        (None, "{{ states('sensor.h') }} % im Bad"),
        (None, "Fenster offen\nim Bad"),
        (None, "Klima"),
        (None, "Sehr lang " * 7),
        (None, None),
        (None, "Strom zurück"),
    ]
    assert title_hints(calls, "Klima") == [
        None,
        "Feuchte im Bad hoch",
        "feuchte im bad hoch",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        "Strom zurück",
    ]
    assert len(("Sehr lang " * 7).strip()) > TITLE_HINT_MAX_LENGTH
