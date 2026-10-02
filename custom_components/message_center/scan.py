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

Nothing is stored. Of a message only the title and the first line are read,
as Home Assistant has loaded them: templates are not rendered, ``!secret``
and blueprint inputs are already filled in.
Of a line in a file only the file, the line number and the action names it
mentions are reported, never the line itself.
"""

from __future__ import annotations

from collections.abc import Iterator
import os
from pathlib import Path
import re
from typing import Any

from homeassistant.core import HomeAssistant

from .const import DOMAIN, TITLE_MAX_LENGTH
from .kinds import Kind, match_kind

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
# a first line longer than this is a sentence, not a headline to take as title
MAX_HEADLINE = 60


def _is_template(text: str) -> bool:
    return "{{" in text or "{%" in text


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


def suggest_title(title: str | None, first_line: str | None) -> dict[str, str] | None:
    """Suggest a title condition for a message kind.

    A fixed title is taken as it is. Of a computed one the fixed beginning is
    used, if there is one. Without a title the first line of the text stands
    in, when it is short enough to be a headline: it is what the title should
    become when the call is changed. A long first line is a sentence; then
    the title is left to the user.
    """
    source = title or first_line
    if not source:
        return None
    if not _is_template(source):
        if not title and len(source) > MAX_HEADLINE:
            return None
        return {"mode": "exact", "value": source[:TITLE_MAX_LENGTH]}
    prefix = re.split(r"\{\{|\{%", source, maxsplit=1)[0].strip()
    if len(prefix) >= MIN_PREFIX:
        return {"mode": "prefix", "value": prefix[:TITLE_MAX_LENGTH]}
    return None


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


def describe_call(step: dict[str, Any], name: str, config_dir: str) -> dict[str, Any]:
    """Turn one notifying step into an entry for the page."""
    if name == DEVICE_ACTION:
        data: dict[str, Any] = step
        targets: list[str] = []
    else:
        raw = step.get("data") or step.get("data_template") or {}
        data = raw if isinstance(raw, dict) else {}
        target = step.get("target")
        targets = _as_list(target.get("entity_id")) if isinstance(target, dict) else []
        targets += _as_list(step.get("entity_id")) + _as_list(data.get("entity_id"))
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
        "suggestion": suggest_title(title, first_line),
        "file": file,
        "line": line,
    }


def _entities(hass: HomeAssistant, domain: str) -> list[Any]:
    component = hass.data.get(domain)
    return list(getattr(component, "entities", []))


def scan_entities(
    hass: HomeAssistant, kinds: list[Kind]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Search the loaded automations and scripts."""
    config_dir = hass.config.config_dir
    found: list[dict[str, Any]] = []
    counts = {"automation": 0, "script": 0}
    for domain, key in (
        ("automation", ("actions", "action")),
        ("script", ("sequence",)),
    ):
        for entity in _entities(hass, domain):
            counts[domain] += 1
            raw = getattr(entity, "raw_config", None)
            if not isinstance(raw, dict):
                continue
            blueprint = getattr(entity, "referenced_blueprint", None)
            if isinstance(blueprint, str) and blueprint.startswith(f"{DOMAIN}/"):
                # made from the own blueprint: its plain push is the fallback
                # of the message center, not a place that still sends directly
                continue
            unique_id = getattr(entity, "unique_id", None)
            object_id = entity.entity_id.split(".", 1)[1]
            for step, name in find_calls([raw.get(k) for k in key]):
                item = describe_call(step, name, config_dir)
                # the UI editor works for what lives in automations.yaml / scripts.yaml
                edit_url = None
                if item["file"] == "automations.yaml" and unique_id:
                    edit_url = f"/config/automation/edit/{unique_id}"
                elif item["file"] == "scripts.yaml":
                    edit_url = f"/config/script/edit/{object_id}"
                suggestion = item["suggestion"]
                # a script started by an automation counts as that automation
                origin = entity.entity_id if domain == "automation" else None
                kind = (
                    match_kind(kinds, origin or "", suggestion["value"])
                    if suggestion
                    else None
                )
                found.append(
                    {
                        **item,
                        "source": domain,
                        "entity_id": entity.entity_id,
                        "name": entity.name or entity.entity_id,
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
