"""Tests for what a tap on the push opens and the note on unclassified messages.

Option ``tap_target``: "home" (default) leaves the tap to the Companion App,
"center" opens the page with the message. A message no kind takes carries a
note at the end of its pushed text and opens the dialog to classify it,
whatever the option says. A target the sender set itself always wins.
"""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.util import slugify
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockUser,
    async_mock_service,
)

from custom_components.message_center.models import MessageState
from custom_components.message_center.store import STORAGE_KEY

from .conftest import PHONE_ACTION, PHONE_NAME, RECIPIENT, kind_data, night_rule_data
from .test_assignment import Page, kind_payload, page  # noqa: F401
from .test_delivery import repeat, setup
from .test_services import NOTE, TEXT, TITLE, message_id_of, notify

NEW_TITLE = "Wäsche fertig"  # no kind takes it
NOTE_EN = NOTE.strip()
NOTE_DE = "⚠ Noch nicht eingeordnet – bitte im Message Center bewerten"  # noqa: RUF001
APPLE = {
    "action": PHONE_ACTION,
    "name": PHONE_NAME,
    "platform": "ios",
    "type": "mobile_app",
}


def pushed(call: ServiceCall) -> tuple[str, dict[str, Any]]:
    """Text and data of one push."""
    return call.data["message"], call.data["data"]


def targets(data: dict[str, Any]) -> dict[str, Any]:
    """Return the tap targets a push carries."""
    return {k: data[k] for k in ("clickAction", "url") if k in data}


async def test_default_leaves_the_tap_to_the_app(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Without the option a classified message carries no target and its own text."""
    await setup(hass, make_entry, kinds=[kind_data()])
    await notify(hass)
    text, data = pushed(phone[0])
    assert text == TEXT
    assert targets(data) == {}


async def test_center_opens_the_page_with_the_message(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Option "center": Android gets clickAction, iOS url, both to this message."""
    await setup(hass, make_entry, kinds=[kind_data()], options={"tap_target": "center"})
    await notify(hass)
    text, data = pushed(phone[0])
    assert text == TEXT
    assert targets(data) == {
        "clickAction": f"/message-center?message={message_id_of(hass)}"
    }


async def test_center_on_an_iphone(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """On an iPhone the same target goes to url."""
    await setup(
        hass,
        make_entry,
        recipients=[APPLE],
        kinds=[kind_data()],
        options={"tap_target": "center"},
    )
    await notify(hass)
    assert targets(phone[0].data["data"]) == {
        "url": f"/message-center?message={message_id_of(hass)}"
    }


@pytest.mark.parametrize("option", ["home", "center"])
async def test_unclassified_message_gets_the_note_and_opens_classify(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any, option: str
) -> None:
    """No kind: note after a blank line, tap opens the dialog, whatever the option.

    The note is in the push only: the message keeps the text as it arrived.
    """
    entry = await setup(
        hass, make_entry, kinds=[kind_data()], options={"tap_target": option}
    )
    await notify(hass, title=NEW_TITLE)
    mid = message_id_of(hass, NEW_TITLE)
    text, data = pushed(phone[0])
    assert text == f"{TEXT}\n\n{NOTE_EN}"
    assert targets(data) == {"clickAction": f"/message-center?classify={mid}"}
    assert entry.runtime_data.book.messages[mid].message == TEXT


async def test_note_is_not_stored(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    hass_storage: dict[str, Any],
) -> None:
    """The working store keeps the text without the note."""
    await setup(hass, make_entry)
    await notify(hass, title=NEW_TITLE)
    assert phone[0].data["message"].endswith(NOTE_EN)
    saved = [
        raw["message"]
        for raw in hass_storage[STORAGE_KEY]["data"]["messages"].values()
        if raw["key"] == NEW_TITLE
    ]
    assert saved == [TEXT]


async def test_note_in_german(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """The note follows the language of Home Assistant."""
    hass.config.language = "de"
    await setup(hass, make_entry)
    await notify(hass, title=NEW_TITLE)
    assert phone[0].data["message"] == f"{TEXT}\n\n{NOTE_DE}"


async def test_own_target_of_the_sender_wins_also_when_unclassified(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """A target in the sender's data stays; the note is still added."""
    await setup(hass, make_entry, kinds=[kind_data()], options={"tap_target": "center"})
    await notify(hass, title=NEW_TITLE, data={"clickAction": "/lovelace/laundry"})
    await notify(hass, data={"url": "/lovelace/climate"})
    first, second = (pushed(call) for call in phone)
    assert first[0].endswith(NOTE_EN)
    assert targets(first[1]) == {"clickAction": "/lovelace/laundry"}
    assert second[0] == TEXT
    assert targets(second[1]) == {"url": "/lovelace/climate"}


async def test_repeats_keep_the_note_until_classified(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    page: Page,  # noqa: F811
) -> None:
    """Each push of an unclassified message has the note; after classifying none.

    Without a kind the spacing is 0: each arrival after a delivery starts a
    new generation with a push of its own (a replacement within one
    generation is tested below). The message that waits while it is
    classified carries no note either when it goes out: what counts is
    whether a kind takes it now.
    """
    hass.states.async_set("input_boolean.night_mode", "off")
    await setup(hass, make_entry, rules=[night_rule_data()])
    mid = message_id_of(hass, NEW_TITLE)
    await notify(hass, title=NEW_TITLE)
    await notify(hass, title=NEW_TITLE, message="Noch einmal.")
    assert [call.data["message"] for call in phone] == [
        f"{TEXT}\n\n{NOTE_EN}",
        f"Noch einmal.\n\n{NOTE_EN}",
    ]
    assert {targets(call.data["data"])["clickAction"] for call in phone} == {
        f"/message-center?classify={mid}"
    }

    # held by the night rule, classified meanwhile, delivered afterwards
    hass.states.async_set("input_boolean.night_mode", "on")
    await hass.async_block_till_done()
    await notify(hass, title=NEW_TITLE, message="Am Abend.")
    assert len(phone) == 2
    await page.ok(
        "save",
        kind="kind",
        data=kind_payload(name="Wäsche", title_mode="exact", title_value=NEW_TITLE),
    )
    await hass.async_block_till_done()
    hass.states.async_set("input_boolean.night_mode", "off")
    await hass.async_block_till_done()
    assert len(phone) == 3
    assert phone[2].data["message"] == "Am Abend."
    assert targets(phone[2].data["data"]) == {}

    await notify(hass, title=NEW_TITLE, message="Wieder.")
    assert phone[3].data["message"] == "Wieder."
    assert targets(phone[3].data["data"]) == {}


async def test_replacement_after_classifying_drops_note_and_classify_target(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    page: Page,  # noqa: F811
) -> None:
    """A push replaced after the message was classified follows the kind.

    The first push is still under way when new text arrives (same
    generation: a replacement follows) and a kind is made for the message.
    The replacement has no note and no "?classify" target; it follows the
    option again.
    """
    entry = await setup(hass, make_entry, options={"tap_target": "center"})
    calls: list[ServiceCall] = []
    release = asyncio.Event()

    async def slow(call: ServiceCall) -> None:
        calls.append(call)
        if len(calls) == 1:
            await release.wait()

    hass.services.async_register("notify", PHONE_ACTION, slow)
    mid = message_id_of(hass)
    await repeat(hass, "v1")
    await repeat(hass, "v2")
    assert [call.data["message"] for call in calls] == ["v1" + NOTE]
    assert targets(calls[0].data["data"]) == {
        "clickAction": f"/message-center?classify={mid}"
    }
    msg = entry.runtime_data.book.get(mid)
    assert msg.state is MessageState.SENDING
    assert (msg.generation, msg.revision, msg.kind_id) == (1, 2, None)

    await page.ok("save", kind="kind", data=kind_payload())
    release.set()
    await hass.async_block_till_done()
    assert len(calls) == 2
    replacement = calls[1].data
    assert (replacement["title"], replacement["message"]) == (f"2x {TITLE}", "v2")
    assert replacement["data"]["tag"] == mid
    assert targets(replacement["data"]) == {
        "clickAction": f"/message-center?message={mid}"
    }
    assert entry.runtime_data.book.get(mid).generation == 1


def other_phone(
    hass: HomeAssistant, name: str, user_id: str | None
) -> list[ServiceCall]:
    """Register one more Companion App phone of the given user; return its calls.

    The app names the phone in its registration (``device_name``); the
    device registry shows a name given by hand, which the action does not
    follow.
    """
    data: dict[str, Any] = {"device_name": name}
    if user_id:
        data["user_id"] = user_id
    entry = MockConfigEntry(domain="mobile_app", data=data)
    entry.add_to_hass(hass)
    registry = dr.async_get(hass)
    device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("mobile_app", name)},
        name=name,
        manufacturer="Example",
    )
    registry.async_update_device(device.id, name_by_user=f"{name} (hall)")
    return async_mock_service(hass, "notify", f"mobile_app_{slugify(name)}")


async def test_page_targets_only_on_phones_of_administrators(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    page: Page,  # noqa: F811
    hass_admin_user: Any,
) -> None:
    """The page is for administrators: another phone opens Home Assistant as before.

    A phone whose user is no administrator, or whose user is not known,
    gets no target of the page, neither "?classify" nor "?message" nor that
    of a test push. The note stays: it tells that the message waits to be
    classified. A phone is known by the name the app registered, also when
    the device was renamed by hand.
    """
    users = await hass.auth.async_get_group(GROUP_ID_USER)
    guest = MockUser(groups=[users]).add_to_hass(hass)
    phones = {
        "guest": other_phone(hass, "Phone Guest", guest.id),
        "spare": other_phone(hass, "Phone Spare", None),
        "tablet": other_phone(hass, "Tablet", hass_admin_user.id),
    }
    recipients = [RECIPIENT] + [
        {**RECIPIENT, "action": f"mobile_app_{name}", "name": name}
        for name in ("phone_guest", "phone_spare", "tablet")
    ]
    await setup(
        hass,
        make_entry,
        recipients=recipients,
        kinds=[kind_data()],
        options={"tap_target": "center"},
    )

    await notify(hass)
    await notify(hass, title=NEW_TITLE)
    await page.ok("test", priority=1)
    mid = message_id_of(hass)
    new = message_id_of(hass, NEW_TITLE)
    admin = [
        {"clickAction": f"/message-center?message={mid}"},
        {"clickAction": f"/message-center?classify={new}"},
        {"clickAction": "/message-center"},
    ]
    for calls in (phone, phones["tablet"]):
        assert [targets(call.data["data"]) for call in calls] == admin
    for calls in (phones["guest"], phones["spare"]):
        assert [targets(call.data["data"]) for call in calls] == [{}, {}, {}]
        assert [call.data["message"] for call in calls[:2]] == [
            TEXT,
            f"{TEXT}\n\n{NOTE_EN}",
        ]


async def test_test_push_opens_the_page_without_a_note(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    page: Page,  # noqa: F811
) -> None:
    """A test push follows the option, to the page itself; it never has the note."""
    await setup(hass, make_entry)
    await page.ok("test", priority=1)
    assert targets(phone[0].data["data"]) == {}
    assert NOTE_EN not in phone[0].data["message"]

    await page.ok("options", options={"tap_target": "center"})
    await page.ok("test", priority=1)
    assert targets(phone[1].data["data"]) == {"clickAction": "/message-center"}
    assert NOTE_EN not in phone[1].data["message"]


async def test_option_is_checked_and_applied_without_restart(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    make_entry: Any,
    page: Page,  # noqa: F811
) -> None:
    """Only "home" and "center" are taken; a change applies to the next push."""
    entry = await setup(hass, make_entry, kinds=[kind_data()])
    reply = await page("options", options={"tap_target": "phone"})
    assert not reply["success"]
    assert reply["error"]["code"] == "invalid_format"

    result = await page.ok("options", options={"tap_target": "center"})
    assert result["options"]["tap_target"] == "center"
    assert entry.options["tap_target"] == "center"
    await notify(hass)
    assert targets(phone[0].data["data"]) == {
        "clickAction": f"/message-center?message={message_id_of(hass)}"
    }

    await page.ok("options", options={"tap_target": "home"})
    await notify(hass, title=f"{TITLE} 2")
    assert targets(phone[1].data["data"]) == {}


async def test_message_with_a_kind_by_name_is_classified(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """A kind given to send counts, even when its condition does not match."""
    entry: MockConfigEntry = await setup(hass, make_entry, kinds=[kind_data()])
    await hass.services.async_call(
        "message_center",
        "send",
        {"title": NEW_TITLE, "message": TEXT, "kind": "Feuchte"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert phone[0].data["message"] == TEXT
    assert targets(phone[0].data["data"]) == {}
    assert entry.runtime_data.unknown == {}
