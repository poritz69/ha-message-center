"""Checks of the repository files: HACS schemas, brand images, texts, versions.

The HACS GitHub action reads hacs.json and manifest.json through
raw.githubusercontent.com. These tests mirror its schemas
(custom_components/hacs/utils/validate.py) so that the files are also
checked locally. The other tests keep the README and the version numbers
in step with the code.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import struct

from awesomeversion import AwesomeVersion
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from custom_components.message_center import center, lifecycle
from custom_components.message_center.const import DOMAIN

ROOT = Path(__file__).resolve().parent.parent
INTEGRATION = ROOT / "custom_components" / DOMAIN

HACS_JSON_SCHEMA = vol.Schema(
    {
        vol.Optional("content_in_root"): bool,
        vol.Optional("country"): vol.Any(str, list),
        vol.Optional("filename"): str,
        vol.Optional("hacs"): str,
        vol.Optional("hide_default_branch"): bool,
        vol.Optional("homeassistant"): str,
        vol.Optional("persistent_directory"): str,
        vol.Optional("render_readme"): bool,
        vol.Optional("zip_release"): bool,
        vol.Required("name"): str,
    },
    extra=vol.PREVENT_EXTRA,
)

MANIFEST_SCHEMA = vol.Schema(
    {
        vol.Required("codeowners"): list,
        vol.Required("documentation"): cv.url,
        vol.Required("domain"): str,
        vol.Required("issue_tracker"): cv.url,
        vol.Required("name"): str,
        vol.Required("version"): vol.Coerce(AwesomeVersion),
    },
    extra=vol.ALLOW_EXTRA,
)


def test_hacs_json_matches_hacs_schema() -> None:
    """hacs.json has only known keys and a parsable minimum version."""
    data = json.loads((ROOT / "hacs.json").read_text())
    HACS_JSON_SCHEMA(data)
    assert AwesomeVersion(data["homeassistant"]).valid


def test_manifest_matches_hacs_schema() -> None:
    """manifest.json has the keys HACS requires and the right domain."""
    data = json.loads((INTEGRATION / "manifest.json").read_text())
    MANIFEST_SCHEMA(data)
    assert data["domain"] == DOMAIN
    assert AwesomeVersion(data["version"]).valid


def test_brand_images_have_the_expected_sizes() -> None:
    """The brand folder has a square PNG icon in 256 px and 512 px (HACS, HA 2026.3)."""
    for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
        head = (INTEGRATION / "brand" / name).read_bytes()[:24]
        assert head[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">II", head[16:24]) == (size, size)


def issue_translation_keys() -> set[str]:
    """Collect the translation keys of the repair issues the center creates."""
    source = (INTEGRATION / "center.py").read_text()
    keys: set[str] = set()
    for call in re.findall(r"ir\.async_create_issue\((.*?)\n\s*\)", source, re.S):
        literal, constant = re.search(
            r'translation_key=(?:"(\w+)"|(ISSUE_\w+))', call
        ).groups()
        keys.add(literal or getattr(center, constant))
    return keys


def test_every_repair_issue_has_a_title_and_a_description() -> None:
    """Each repair issue is translated under "issues" in both languages.

    Home Assistant looks the texts up under ``issues.<translation_key>``; a
    key filed elsewhere shows up in the repairs without title or description.
    """
    keys = issue_translation_keys()
    assert "history_not_writable" in keys
    for lang in ("en", "de"):
        data = json.loads((INTEGRATION / "translations" / f"{lang}.json").read_text())
        issues = data["issues"]
        assert keys <= set(issues), lang
        for key in keys:
            assert set(issues[key]) == {"title", "description"}, (lang, key)
            assert issues[key]["title"] and issues[key]["description"], (lang, key)


def readme_section(heading: str) -> str:
    """Return the README text under ``heading`` up to the next heading of its level."""
    text = (ROOT / "README.md").read_text()
    level = heading.split(" ", 1)[0]
    start = text.index(f"\n{heading}\n") + 1
    rest = text[start + len(heading) :]
    match = re.search(rf"\n{re.escape(level)} ", rest)
    return heading + (rest if match is None else rest[: match.start()])


def test_readme_lists_every_send_action() -> None:
    """The response of ``send`` names each value of ``action`` the code returns.

    The values are the contract (README, "message_center.send"); a value the
    code can return and the README does not name would surprise a sender.
    """
    section = readme_section(
        "### `message_center.send` (for senders that know their kind)"
    )
    line = next(line for line in section.splitlines() if '"result": "accepted"' in line)
    for action in lifecycle.AcceptAction:
        assert f'"{action.value}"' in line, action


def test_readme_notify_contract_names_only_real_error_keys() -> None:
    """``notify.message_center`` can be rejected with store_full and not_ready only.

    Wrong fields are Home Assistant's schema error before the center runs,
    and ``invalid_field`` is raised in one place: an unknown kind in ``send``.
    """
    section = readme_section("### `notify.message_center` (main way)")
    assert "invalid_field" not in section
    assert "`store_full`" in section
    assert "`not_ready`" in section


def test_guides_say_where_the_action_is_found() -> None:
    """Both guides tell where the action of Message Center is in the automation editor.

    New users look for it under *Add action*; the search there finds it by
    its name. It also finds the actions of the integration, which Home
    Assistant names "Message Center: Send" and so on, so both guides say
    which entry is meant. The guide in German, the README in English.
    """
    guide = (ROOT / "docs" / "bedienhilfe.md").read_text()
    assert (
        "Im Automationseditor bei *Aktion hinzufügen* oben nach "
        "„Message Center“ suchen. Gemeint ist der Eintrag, der nur "
        "„Message Center“ heißt, nicht „Message Center: Senden“." in guide
    )
    readme = (ROOT / "README.md").read_text()
    assert (
        "In the automation editor, search for “Message Center” at the top of "
        "*Add action*. Pick the entry called just “Message Center”, not "
        "“Message Center: Send”." in readme
    )


def test_guides_name_the_dashboard_path_of_an_own_dashboard() -> None:
    """The way to put a mode toggle on a dashboard is the one of an own dashboard.

    Home Assistant's own overview has "Edit overview" and no "Add card", so
    the guide limits the path to a dashboard of one's own, as the page does.
    """
    guide = (ROOT / "docs" / "bedienhilfe.md").read_text()
    line = next(
        line for line in guide.splitlines() if "**Ins Dashboard holen:**" in line
    )
    assert "eigenes Dashboard" in line
    assert "„Dashboard bearbeiten“ → „Karte hinzufügen“ → „Nach Entität“" in line


def test_readme_removal_names_the_created_toggles() -> None:
    """Toggles created with *Create toggle* are helpers that stay after removal."""
    readme = (ROOT / "README.md").read_text()
    section = readme.split("## Removal", 1)[1].split("\n## ", 1)[0]
    assert "*Create toggle*" in section
    assert "Settings → Devices & services → Helpers" in section


def test_versions_agree() -> None:
    """Manifest, page package and lock file carry the version of the changelog head.

    The version is part of the address of the page's code; a mismatch leaves
    the browser with the old page from its cache.
    """
    manifest = json.loads((INTEGRATION / "manifest.json").read_text())["version"]
    package = json.loads((ROOT / "frontend" / "package.json").read_text())
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text())
    assert package["version"] == manifest
    assert lock["version"] == manifest
    assert lock["packages"][""]["version"] == manifest
    changelog = (ROOT / "CHANGELOG.md").read_text()
    head = re.search(r"^## (\S+) \(\d{4}-\d{2}-\d{2}\)$", changelog, re.M)
    assert head is not None
    assert head.group(1) == manifest
