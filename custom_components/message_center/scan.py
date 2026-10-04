"""Find notifications in Home Assistant: automations, scripts and files.

A help for setting up: the page shows where the house still notifies a phone
directly, so that these places can be pointed to ``notify.message_center``,
and offers to create a message kind for each of them.

Two sources are searched, both read-only and on request only:

* the automations and scripts Home Assistant has loaded, including those from
  YAML packages and blueprints. Their steps carry the file and line they were
  read from, so the exact place can be shown.
* text files in the configuration directory (YAML, Python, JSON, ...), for
  everything that is not an automation or script: AppDaemon apps, pyscript,
  ``alert`` entries, YAML dashboards.

What cannot be seen: integrations that send by themselves and apps (add-ons)
whose files live outside the configuration directory.

Nothing is stored. Of a message only the title and the first line are
reported (the whole text only tells calls without a title apart), as Home
Assistant has loaded them: templates are not rendered, ``!secret`` and
blueprint inputs are already filled in.
Of a line in a file only the file, the line number and the action names it
mentions are reported, never the line itself.

The same reading tells the page which messages one automation or script
sends (``origin_messages``): one, so that a kind for all of its messages
fits, or several, so that the title has to tell them apart. Several
different messages are several, whether their titles differ or only their
texts: each call without a title is a message of its own.

A message without a title is called after its origin, by the name of the
origin's state (an own name given in the entity settings wins over the
alias); the search uses the same name. Two calls without a title would
therefore replace each other on the phone: each needs a title of its own.
"""

from __future__ import annotations

from collections.abc import Iterator
import os
from pathlib import Path
import re
from typing import Any

from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLACEHOLDER, TITLE_MAX_LENGTH
from .kinds import Kind, match_kind, origin_allows_any

STATUS_DIRECT = "direct"  # goes to a phone or service directly: to be changed
STATUS_CENTER = "center"  # already goes through the message center
STATUS_PERSISTENT = "persistent"  # a notification in the Home Assistant UI

CENTER_ACTIONS = ("notify.message_center", f"{DOMAIN}.send")
PERSISTENT_ACTIONS = (
    "persistent_notification.create",
    "notify.persistent_notification",
)
DEVICE_ACTION = "mobile_app"

# also "notify/mobile_app_x": AppDaemon writes actions with a slash
_NAMES = re.compile(
    r"\b(?:notify[./][a-z0-9_]+|persistent_notification[./]create"
    r"|message_center[./]send)\b"
)

# Text search: where to look and where not
SKIP_DIRS = frozenset(
    {
        ".storage",
        ".git",
        ".cloud",
        ".venv",
        "custom_components",
        "deps",
        "tts",
        "www",
        "backups",
        "blueprints",
        "node_modules",
        "__pycache__",
        "image",
        "media",
    }
)
TEXT_SUFFIXES = frozenset(
    {".yaml", ".yml", ".py", ".json", ".js", ".sh", ".conf", ".txt", ".jinja", ".j2"}
)
SKIP_FILES = frozenset({"secrets.yaml"})
MAX_FILE_BYTES = 1_000_000
MAX_FILES = 3000
MAX_HITS = 300
# a step found in an automation covers the text hits in the lines of its block
COVER_LINES = 40
MIN_PREFIX = 3
# a first line longer than this is no good example for a title on the phone
TITLE_HINT_MAX_LENGTH = 60
# where the steps of an automation and of a script are
STEP_KEYS = {"automation": ("actions", "action"), "script": ("sequence",)}
_STATEMENTS = re.compile(r"\{%.*%\}", re.DOTALL)
_EXPRESSIONS = re.compile(r"\{\{.*?\}\}", re.DOTALL)
_PLACEHOLDERS = re.compile(r"…(?:\s*…)+")


def _is_template(text: str) -> bool:
    return "{{" in text or "{%" in text


def display_title(title: str) -> str:
    """Show a title with its computed parts as a placeholder.

    Everything from the first statement (``{% … %}``) to the last is one
    computed part, each expression (``{{ … }}``) another; placeholders next
    to each other become one.
    """
    text = _EXPRESSIONS.sub(PLACEHOLDER, _STATEMENTS.sub(PLACEHOLDER, title))
    return _PLACEHOLDERS.sub(PLACEHOLDER, text).strip() or PLACEHOLDER


def _status(names: list[str]) -> str:
    """Status of a call or a line from the action names it mentions."""
    rest = [n for n in names if n not in CENTER_ACTIONS]
    if not rest:
        return STATUS_CENTER
    if all(n in PERSISTENT_ACTIONS for n in rest):
        return STATUS_PERSISTENT
    return STATUS_DIRECT


def _call_name(step: dict[str, Any]) -> str | None:
    """Return the notifying action of a step, or None when it is something else."""
    name = step.get("action", step.get("service"))
    if isinstance(name, str):
        name = name.strip()
        if (
            name.startswith("notify.")
            or name in PERSISTENT_ACTIONS
            or name in CENTER_ACTIONS
        ):
            return name
    if step.get("domain") == DEVICE_ACTION and step.get("type") == "notify":
        return DEVICE_ACTION
    return None


def find_calls(node: Any) -> Iterator[tuple[dict[str, Any], str]]:
    """Yield every notifying step below a node, however deeply it is nested."""
    if isinstance(node, dict):
        if (name := _call_name(node)) is not None:
            yield node, name
        for value in node.values():
            yield from find_calls(value)
    elif isinstance(node, list):
        for value in node:
            yield from find_calls(value)


def _as_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_line(message: str | None) -> str | None:
    if not message:
        return None
    for line in message.splitlines():
        if line.strip():
            return line.strip()
    return None


def suggest_title(title: str | None) -> dict[str, str] | None:
    """Suggest a title condition for a message kind from the title of a call.

    A fixed title is taken as it is. Of a computed one the fixed beginning is
    used, if there is one. Without a title there is nothing to suggest here:
    such a message is called after its automation, see ``scan_suggestion``.
    The first line of the text is no title.
    """
    if not title:
        return None
    if not _is_template(title):
        return {"mode": "exact", "value": title[:TITLE_MAX_LENGTH]}
    prefix = re.split(r"\{\{|\{%", title, maxsplit=1)[0].strip()
    if len(prefix) >= MIN_PREFIX:
        return {"mode": "prefix", "value": prefix[:TITLE_MAX_LENGTH]}
    return None


def _shown_line(text: str | None) -> str | None:
    """Return the first line of a text as shown: computed parts as "…", cut."""
    line = _first_line(text)
    if line is None:
        return None
    return (display_title(line) if _is_template(line) else line)[:TITLE_MAX_LENGTH]


def _text_key(text: str | None) -> str:
    """Return the whole text of a call without a title as it tells the message apart."""
    return (text or "").strip().casefold()


def sent_messages(
    calls: list[tuple[str | None, str | None]], name: str
) -> list[dict[str, Any]]:
    """Return the different messages these calls send, in their order.

    ``calls`` holds the whole title and the whole text of each call as
    written, None where there is none. A fixed title counts once (case
    aside), whatever the texts; a computed one is one message, however many
    titles it makes, and counts once per template text, read as a whole.
    A call without a title is a message of its own, told apart by its text
    (the same text twice is one message, case aside): all of them are
    called after the automation or script (``name``, the ``display``), so
    on the phone they would replace each other, see ``untitled_clash``.
    ``display`` shows a computed title with its computed parts as a
    placeholder; ``first_line`` is the first line of the text of a call
    without a title, shown the same way, else None. ``title``, ``display``
    and ``first_line`` are cut to the length of a title.
    """
    untitled = name[:TITLE_MAX_LENGTH]
    messages: dict[tuple[bool, str], dict[str, Any]] = {}
    for title, text in calls:
        if title is None:
            messages.setdefault(
                (False, _text_key(text)),
                {
                    "title": None,
                    "template": False,
                    "display": untitled,
                    "first_line": _shown_line(text),
                },
            )
            continue
        template = _is_template(title)
        shown = display_title(title) if template else title
        messages.setdefault(
            (True, title.casefold()),
            {
                "title": title[:TITLE_MAX_LENGTH],
                "template": template,
                "display": shown[:TITLE_MAX_LENGTH],
                "first_line": None,
            },
        )
    return list(messages.values())


def untitled_clash(messages: list[dict[str, Any]]) -> bool:
    """Return True when two or more of these messages have no title.

    All of them would be called after their automation or script and replace
    each other on the phone: each call needs a title of its own.
    """
    return sum(1 for message in messages if message["title"] is None) > 1


def title_hints(
    calls: list[tuple[str | None, str | None]], name: str
) -> list[str | None]:
    """Return for each call without a title an example of a title, if a good one.

    ``calls`` are the whole title and text of each call, as for
    ``sent_messages``; the answer has one entry per call, None for a call
    with a title. The example is the first line of the text, when it makes
    a title that tells this message apart: it has no computed part (else
    every value would be a message of its own), it is at most
    ``TITLE_HINT_MAX_LENGTH`` long, no other message without a title begins
    with the same line, and it is neither a title of another call nor the
    name of the automation or script (case aside). Otherwise None: the page
    then asks for a title without an example. The same text twice is one
    message and keeps its line.
    """
    texts: dict[str, set[str]] = {}
    for title, text in calls:
        line = _first_line(text) if title is None else None
        if line is not None:
            texts.setdefault(line.casefold(), set()).add(_text_key(text))
    taken = {name.casefold(), *(title.casefold() for title, _ in calls if title)}
    hints: list[str | None] = []
    for title, text in calls:
        line = _first_line(text) if title is None else None
        fits = (
            line is not None
            and not _is_template(line)
            and len(line) <= TITLE_HINT_MAX_LENGTH
            and line.casefold() not in taken
            and len(texts[line.casefold()]) == 1
        )
        hints.append(line if fits else None)
    return hints


def scan_suggestion(
    item: dict[str, Any], origin: str | None, name: str, multiple: bool
) -> dict[str, str] | None:
    """Suggest the condition of a kind for one call found in an automation or script.

    An automation that sends one message gets "all messages of this
    automation" (``{"mode": "any"}``, the origin is the item's). One that
    sends several keeps the title: as it is, its fixed beginning, or for a
    call without a title the name of the automation, which becomes the
    title (the title it has today; with several such calls the page asks
    for a title of each). A script has no origin of its own (whoever starts
    it is), so its suggestion always follows the title. A notification in
    the Home Assistant UI does not go through the center: its title only.
    """
    if item["status"] == STATUS_PERSISTENT:
        return suggest_title(item["title"])
    if origin is not None and not multiple:
        return {"mode": "any"}
    if item["title"] is None:
        if origin is None:
            return None
        return {"mode": "exact", "value": name[:TITLE_MAX_LENGTH]}
    return suggest_title(item["title"])


def _location(step: Any, config_dir: str) -> tuple[str | None, int | None]:
    """File (relative to the configuration directory) and line of a step."""
    file = getattr(step, "__config_file__", None)
    line = getattr(step, "__line__", None)
    if not isinstance(file, str):
        return None, None
    try:
        file = str(Path(file).relative_to(config_dir))
    except ValueError:
        file = Path(file).name
    return file, line if isinstance(line, int) else None


def _call_data(step: dict[str, Any], name: str) -> tuple[dict[str, Any], list[str]]:
    """Return the data and the targets of a notifying step."""
    if name == DEVICE_ACTION:
        return step, []
    raw = step.get("data") or step.get("data_template") or {}
    data = raw if isinstance(raw, dict) else {}
    target = step.get("target")
    targets = _as_list(target.get("entity_id")) if isinstance(target, dict) else []
    targets += _as_list(step.get("entity_id")) + _as_list(data.get("entity_id"))
    return data, targets


def call_parts(step: dict[str, Any], name: str) -> tuple[str | None, str | None]:
    """Return the whole title and the whole text of a notifying step as written."""
    data = _call_data(step, name)[0]
    return _text(data.get("title")), _text(data.get("message"))


def describe_call(step: dict[str, Any], name: str, config_dir: str) -> dict[str, Any]:
    """Turn one notifying step into an entry for the page."""
    data, targets = _call_data(step, name)
    title = _text(data.get("title"))
    first_line = _first_line(_text(data.get("message")))
    file, line = _location(step, config_dir)
    return {
        "service": name,
        "target": " → ".join([name, ", ".join(targets)] if targets else [name]),
        "status": _status([name, *targets]),
        "title": title[:TITLE_MAX_LENGTH] if title else None,
        "title_template": bool(title and _is_template(title)),
        "first_line": first_line[:TITLE_MAX_LENGTH] if first_line else None,
        "suggestion": suggest_title(title),
        "file": file,
        "line": line,
    }


def _entities(hass: HomeAssistant, domain: str) -> list[Any]:
    component = hass.data.get(domain)
    return list(getattr(component, "entities", []))


def _entity_calls(entity: Any, domain: str) -> Iterator[tuple[dict[str, Any], str]]:
    """Yield the notifying steps of a loaded automation or script."""
    raw = getattr(entity, "raw_config", None)
    if isinstance(raw, dict):
        yield from find_calls([raw.get(key) for key in STEP_KEYS[domain]])


def _entity_name(hass: HomeAssistant, entity: Any) -> str:
    """Name of an automation or script as its messages carry it.

    The name of its state, as the origin of a message is named: an own name
    given in the entity settings wins over the alias.
    """
    state = hass.states.get(entity.entity_id)
    if state is not None:
        return state.name
    return str(entity.name or entity.entity_id)


def _sent_by(hass: HomeAssistant, origin: str, *, direct: bool) -> list[dict[str, Any]]:
    """Return the messages of one loaded automation or script.

    Its calls to the center, or with ``direct`` its calls past the center
    that are no notification in the Home Assistant UI.
    """
    domain = origin.partition(".")[0]
    if domain not in STEP_KEYS:
        return []
    entity = next((e for e in _entities(hass, domain) if e.entity_id == origin), None)
    if entity is None:
        return []
    calls = [
        call_parts(step, name)
        for step, name in _entity_calls(entity, domain)
        if (name not in CENTER_ACTIONS) is direct
        and not (direct and _status([name]) == STATUS_PERSISTENT)
    ]
    return sent_messages(calls, _entity_name(hass, entity))


def config_messages(hass: HomeAssistant, origin: str) -> list[dict[str, Any]]:
    """Return the messages an automation or script sends through the center.

    Read from its loaded configuration: only the calls to
    ``notify.message_center`` and ``message_center.send`` count, see
    ``sent_messages``. Empty when the origin is no loaded automation or
    script or sends nothing through the center itself (a script it starts
    does not count).
    """
    return _sent_by(hass, origin, direct=False)


def direct_messages(hass: HomeAssistant, origin: str) -> list[dict[str, Any]]:
    """Return the messages an automation or script still sends past the center.

    What it will send once these calls go through the center, as the search
    counts it: a notification in the Home Assistant UI does not count.
    """
    return _sent_by(hass, origin, direct=True)


def configured_messages(hass: HomeAssistant, origin: str) -> list[dict[str, Any]]:
    """Return the messages of an origin by its configuration.

    Its calls to the center, else its calls past the center.
    """
    return config_messages(hass, origin) or direct_messages(hass, origin)


def multiple_messages(
    messages: list[dict[str, Any]], seen_count: int
) -> tuple[str, bool]:
    """Where the answer comes from and whether an origin sends several messages.

    The configuration decides when it shows calls to the center; otherwise
    the different titles that arrived from the origin.
    """
    if messages:
        return "config", len(messages) > 1
    if seen_count:
        return "seen", seen_count > 1
    return "none", False


def origin_messages(
    hass: HomeAssistant, origin: str, seen_titles: list[str]
) -> dict[str, Any]:
    """Which messages one origin sends, for the page's kind dialog.

    ``seen_titles`` are the different titles that arrived from it, newest
    first; the center collects them. The calls to the center decide
    (``config``), else the titles that arrived (``seen``), else the calls
    that still go past the center (``direct``): an automation found by the
    search before it was changed. Each call without a title is a message of
    its own, see ``sent_messages``. ``any_allowed`` is false for an origin
    that is no automation or script ("unknown"): no "all messages of" for
    it, and the titles of all unknown senders are not its messages, so it
    has none to tell apart.
    """
    if not origin_allows_any(origin):
        return {
            "source": "none",
            "messages": [],
            "seen_titles": [],
            "multiple": False,
            "any_allowed": False,
        }
    messages = config_messages(hass, origin)
    source, multiple = multiple_messages(messages, len(seen_titles))
    if source == "none" and (messages := direct_messages(hass, origin)):
        source, multiple = "direct", len(messages) > 1
    return {
        "source": source,
        "messages": messages,
        "seen_titles": seen_titles,
        "multiple": multiple,
        "any_allowed": True,
    }


def _probe_title(
    item: dict[str, Any], suggestion: dict[str, str] | None, name: str
) -> str | None:
    """Return the title to look up the kind of a found call with, if there is one.

    The suggested text where there is one; for "all messages of" the title
    the message will have: its fixed title, the automation's name without a
    title, and for a computed one its fixed beginning, or nothing but the
    origin ("") when it has none.
    """
    if suggestion is None:
        return None
    if "value" in suggestion:
        return suggestion["value"]
    if item["title"] is None:
        return name[:TITLE_MAX_LENGTH]
    if item["title_template"]:
        own = suggest_title(item["title"])
        return own["value"] if own else ""
    return item["title"]


def scan_entities(
    hass: HomeAssistant, kinds: list[Kind]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Search the loaded automations and scripts."""
    config_dir = hass.config.config_dir
    found: list[dict[str, Any]] = []
    counts = {"automation": 0, "script": 0}
    for domain in STEP_KEYS:
        for entity in _entities(hass, domain):
            counts[domain] += 1
            if not isinstance(getattr(entity, "raw_config", None), dict):
                continue
            blueprint = getattr(entity, "referenced_blueprint", None)
            if isinstance(blueprint, str) and blueprint.startswith(f"{DOMAIN}/"):
                # made from the own blueprint: its plain push is the fallback
                # of the message center, not a place that still sends directly
                continue
            unique_id = getattr(entity, "unique_id", None)
            object_id = entity.entity_id.split(".", 1)[1]
            name = _entity_name(hass, entity)
            calls = list(_entity_calls(entity, domain))
            items = [describe_call(step, call, config_dir) for step, call in calls]
            # what it sends once every call goes through the center; a
            # notification in the Home Assistant UI stays where it is
            sending = [
                (index, call_parts(step, call))
                for index, ((step, call), item) in enumerate(
                    zip(calls, items, strict=True)
                )
                if item["status"] != STATUS_PERSISTENT
            ]
            parts = [part for _, part in sending]
            sent = sent_messages(parts, name)
            multiple = len(sent) > 1
            clash = untitled_clash(sent)
            # with several calls without a title: an example of a title each
            hints: dict[int, str | None] = (
                dict(
                    zip(
                        (index for index, _ in sending),
                        title_hints(parts, name),
                        strict=True,
                    )
                )
                if clash
                else {}
            )
            # a script started by an automation counts as that automation
            origin = entity.entity_id if domain == "automation" else None
            for index, item in enumerate(items):
                # the UI editor works for what lives in automations.yaml / scripts.yaml
                edit_url = None
                if item["file"] == "automations.yaml" and unique_id:
                    edit_url = f"/config/automation/edit/{unique_id}"
                elif item["file"] == "scripts.yaml":
                    edit_url = f"/config/script/edit/{object_id}"
                suggestion = scan_suggestion(item, origin, name, multiple)
                probe = _probe_title(item, suggestion, name)
                kind = (
                    match_kind(
                        kinds,
                        origin or "",
                        probe,
                        untitled=origin is not None and item["title"] is None,
                    )
                    if probe is not None
                    else None
                )
                found.append(
                    {
                        **item,
                        "suggestion": suggestion,
                        "multiple": multiple,
                        "untitled_clash": clash,
                        "title_hint": hints.get(index),
                        "source": domain,
                        "entity_id": entity.entity_id,
                        "name": name,
                        "origin": origin,
                        "blueprint": blueprint,
                        "edit_url": edit_url,
                        "kind": kind.name if kind else None,
                    }
                )
    return found, counts


def scan_files(
    config_dir: str, covered: dict[str, list[int]]
) -> tuple[list[dict[str, Any]], int]:
    """Search the text files of the configuration directory (runs in the executor).

    ``covered`` holds, per file, the lines of steps already found in automations
    and scripts; text hits inside those blocks are left out. A hit carries
    the action names found in its line, not the line: it may hold a password
    or a token; file and line lead to the place.
    """
    hits: list[dict[str, Any]] = []
    files = 0
    for root, dirs, names in os.walk(config_dir):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(names):
            path = Path(root) / name
            if (
                path.suffix.lower() not in TEXT_SUFFIXES
                or name in SKIP_FILES
                or ".bak" in name
            ):
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            files += 1
            rel = str(path.relative_to(config_dir))
            starts = covered.get(rel, [])
            for number, line in enumerate(text.splitlines(), start=1):
                names_found = [n.replace("/", ".") for n in _NAMES.findall(line)]
                if not names_found:
                    continue
                if any(start <= number <= start + COVER_LINES for start in starts):
                    continue
                hits.append(
                    {
                        "file": rel,
                        "line": number,
                        "text": ", ".join(dict.fromkeys(names_found)),
                        "status": _status(names_found),
                    }
                )
                if len(hits) >= MAX_HITS:
                    return hits, files
            if files >= MAX_FILES:
                return hits, files
    return hits, files


async def async_scan(hass: HomeAssistant, kinds: list[Kind]) -> dict[str, Any]:
    """Search automations, scripts and files; returns the result for the page."""
    found, counts = scan_entities(hass, kinds)
    covered: dict[str, list[int]] = {}
    for item in found:
        if item["file"] and item["line"]:
            covered.setdefault(item["file"], []).append(item["line"])
    files, file_count = await hass.async_add_executor_job(
        scan_files, hass.config.config_dir, covered
    )
    files.sort(key=lambda hit: (hit["file"], hit["line"]))
    return {
        "found": found,
        "files": files,
        "counts": {
            "automations": counts["automation"],
            "scripts": counts["script"],
            "files": file_count,
            "direct": sum(1 for i in found if i["status"] == STATUS_DIRECT)
            + sum(1 for f in files if f["status"] == STATUS_DIRECT),
        },
    }
