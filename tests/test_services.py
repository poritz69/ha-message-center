"""Tests for the intake and the actions."""

from __future__ import annotations

from typing import Any

from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)
import voluptuous as vol

from custom_components.message_center.const import (
    DOMAIN,
    EVENT_DELIVERED,
    EVENT_DISCARDED,
    EVENT_FORWARDED,
    EVENT_SNOOZED,
)

from .conftest import PHONE_ACTION, kind_data

TITLE = "Feuchte: Büro"
TEXT = "Bitte lüften, 72 %."
# what the push of a message no kind takes carries after its text (English system)
NOTE = "\n\n⚠ Not classified yet – please classify it in Message Center"  # noqa: RUF001


def message_id_of(
    hass: HomeAssistant, key: str = TITLE, origin: str = "unknown"
) -> str:
    """Id of a message as the running center's book computes it."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    return entry.runtime_data.book.message_id(origin, key)


async def notify(hass: HomeAssistant, **data: Any) -> None:
    """Call notify.message_center with defaults."""
    payload: dict[str, Any] = {"title": TITLE, "message": TEXT}
    payload.update(data)
    payload = {k: v for k, v in payload.items() if v is not None}
    await hass.services.async_call("notify", "message_center", payload, blocking=True)
    await hass.async_block_till_done()


def open_items(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Items of the open sensor."""
    return list(hass.states.get("sensor.message_center_open").attributes["items"])


async def test_notify_is_delivered_and_visible(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """A plain notify goes out with tag and group; unknown origin and kind are shown.

    No kind takes it: the push says so below the text, and a tap opens the
    dialog to classify it.
    """
    events = async_capture_events(hass, EVENT_DELIVERED)
    await notify(hass)
    assert len(phone) == 1
    call = phone[0]
    assert call.data["title"] == TITLE
    assert call.data["message"] == TEXT + NOTE
    assert call.data["data"]["tag"] == message_id_of(hass)
    assert call.data["data"]["clickAction"] == (
        f"/message-center?classify={message_id_of(hass)}"
    )
    assert call.data["data"]["group"] == "unknown"
    assert call.data["data"]["channel"] == "message_center"
    assert "subtitle" not in call.data["data"]

    assert hass.states.get("sensor.message_center_open").state == "0"
    assert hass.states.get("sensor.message_center_new").state == "1"
    new = hass.states.get("sensor.message_center_new").attributes["items"][0]
    assert new["origin"] == "unknown"
    assert new["title"] == TITLE
    assert new["count"] == 1

    assert len(events) == 1
    assert events[0].data["message_id"] == message_id_of(hass)
    assert events[0].data["kind"] is None
    assert events[0].data["recipients"] == [PHONE_ACTION]
    assert hass.states.get("sensor.message_center_last_delivery").state != "unknown"
    assert hass.states.get("event.message_center_delivered").state != "unknown"


async def test_extra_data_is_passed_through(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """Images, actions and other data of the caller reach the phone unchanged."""
    await notify(
        hass,
        data={"image": "/local/cam.jpg", "sticky": True, "actions": [{"action": "x"}]},
    )
    data = phone[0].data["data"]
    assert data["image"] == "/local/cam.jpg"
    assert data["sticky"] is True
    # the caller's buttons stay first; the center's "later" and "to assistant" follow
    assert data["actions"][0] == {"action": "x"}
    assert [a["action"].split("|")[0] for a in data["actions"][1:]] == [
        "message_center_snooze",
        "message_center_forward",
    ]
    assert data["tag"] == message_id_of(hass)


async def test_unstorable_extra_data_is_a_schema_error(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """Extra data the store cannot write is refused like any wrong field.

    Accepted, it would make every write of the store fail. The center stays
    ready, and what Home Assistant can convert (a set) is still allowed.
    """
    with pytest.raises(vol.Invalid):
        await notify(hass, data={"big": 2**70})
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "send",
            {"title": TITLE, "message": TEXT, "data": {"thing": object()}},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert phone == []
    assert open_items(hass) == []
    assert hass.states.get("binary_sensor.message_center_ready").state == "on"

    await notify(hass, data={"image": "/local/cam.jpg", "rooms": {"Büro"}})
    assert len(phone) == 1
    assert hass.states.get("binary_sensor.message_center_ready").state == "on"


HALF = "\ud83d"  # half an emoji, as templates and YAML can produce it


def nested(depth: int) -> dict[str, Any]:
    """Return extra data nested that many levels deep."""
    value: dict[str, Any] = {}
    for _ in range(depth - 1):
        value = {"a": value}
    return value


@pytest.mark.parametrize(
    ("action", "field"),
    [("notify", "title"), ("notify", "message"), ("send", "key")],
)
async def test_unstorable_text_is_a_schema_error(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    action: str,
    field: str,
) -> None:
    """A text the store cannot write is refused like unstorable extra data.

    Accepted, it would switch "Ready" off for every sender. The error names
    the field and not the text.
    """
    domain = "notify" if action == "notify" else DOMAIN
    service = "message_center" if action == "notify" else "send"
    payload = {"title": TITLE, "message": TEXT, field: f"Feuer {HALF}"}
    with pytest.raises(vol.Invalid) as err:
        await hass.services.async_call(domain, service, payload, blocking=True)
    assert field in str(err.value)
    assert "Feuer" not in str(err.value)
    await hass.async_block_till_done()
    assert phone == []
    assert open_items(hass) == []
    assert hass.states.get("binary_sensor.message_center_ready").state == "on"


async def test_unstorable_note_is_a_schema_error(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """A note the store cannot write never reaches the message.

    Forward has nothing to take back: kept as an event of the message, such a
    note would make every later write fail and reject every sender.
    """
    events = async_capture_events(hass, EVENT_FORWARDED)
    await notify(hass)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "forward",
            {"message_id": message_id_of(hass), "note": f"Bitte prüfen {HALF}"},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert events == []
    assert center_entry.runtime_data.book.messages[message_id_of(hass)].events == []

    await notify(hass, title="Zweite")
    assert len(phone) == 2
    assert hass.states.get("binary_sensor.message_center_ready").state == "on"


async def test_extra_data_nested_too_deep_for_the_store_is_a_schema_error(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """The limit is the one of the file, where the data lies some levels down."""
    await notify(hass, data=nested(250))
    assert len(phone) == 1
    with pytest.raises(vol.Invalid):
        await notify(hass, title="Zweite", data=nested(251))
    await hass.async_block_till_done()
    assert len(phone) == 1
    assert hass.states.get("binary_sensor.message_center_ready").state == "on"


async def test_repeat_bundles_with_counter(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Same message again within the kind's spacing: silent replace with counter."""
    entry = make_entry(kinds=[kind_data(spacing=360)])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await notify(hass)
    await notify(hass)
    assert len(phone) == 2
    second = phone[1].data["data"]
    assert "alert_once" not in second  # audible replace with the counter in the title
    assert phone[1].data["title"].startswith("2x ")
    assert second["tag"] == phone[0].data["data"]["tag"]
    assert hass.states.get("sensor.message_center_new").state == "0"


async def test_kind_assigns_priority_and_group(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """A matching kind sets priority, group and the push group name."""
    entry = make_entry(
        groups=[{"name": "Klima", "unique_id": "g-klima"}],
        kinds=[kind_data(priority=2, group_id="g-klima", unique_id="k-feuchte")],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    group_id = next(
        sid for sid, sub in entry.subentries.items() if sub.subentry_type == "group"
    )
    kind_id = next(
        sid for sid, sub in entry.subentries.items() if sub.subentry_type == "kind"
    )
    hass.config_entries.async_update_subentry(
        entry,
        entry.subentries[kind_id],
        data={**kind_data(priority=2), "group_id": group_id},
    )
    await hass.async_block_till_done()

    events = async_capture_events(hass, EVENT_DELIVERED)
    await notify(hass)
    assert phone[0].data["data"]["group"] == "Klima"
    assert events[0].data["kind"] == "Feuchte"
    assert events[0].data["group"] == "Klima"
    assert events[0].data["priority"] == 2


async def test_send_with_priority_3_needs_option(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Priority 3 via send is rejected unless allowed; then it carries alarm data."""
    entry = make_entry(options={"allow_alarm": False})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "send",
            {"title": "Feuer", "message": "Küche", "priority": 3},
            blocking=True,
        )
    assert err.value.translation_key == "priority_not_allowed"

    hass.config_entries.async_update_entry(entry, options={"allow_alarm": True})
    await hass.async_block_till_done()
    response = await hass.services.async_call(
        DOMAIN,
        "send",
        {"title": "Feuer", "message": "Küche", "priority": 3, "key": "feuer"},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()
    assert response["message_id"] == message_id_of(hass, "feuer")
    data = phone[-1].data["data"]
    assert data["channel"] == "alarm_stream"
    assert data["ttl"] == 0
    assert data["priority"] == "high"


async def test_send_with_kind_by_name(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Send can name a kind; the kind's settings apply."""
    entry = make_entry(kinds=[kind_data(priority=2, title_value="zzz")])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    events = async_capture_events(hass, EVENT_DELIVERED)
    await hass.services.async_call(
        DOMAIN,
        "send",
        {"title": "Egal", "message": "x", "kind": "Feuchte"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert events[0].data["kind"] == "Feuchte"
    assert events[0].data["priority"] == 2
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "send",
            {"title": "x", "message": "x", "kind": "nope"},
            blocking=True,
        )


async def test_send_reports_created_updated_bundled(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """The response names what the intake did: created, updated or bundled.

    A first arrival is created; one more while the message waits is updated
    (counter up, no second message); one more after the delivery, within the
    kind's spacing, is bundled: counter up, the push on the phone replaced,
    no new push cycle.
    """
    from .conftest import night_rule_data

    hass.states.async_set("input_boolean.night_mode", "on")
    entry = make_entry(kinds=[kind_data(spacing=360)], rules=[night_rule_data()])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async def send() -> dict[str, Any]:
        response = await hass.services.async_call(
            DOMAIN,
            "send",
            {"title": TITLE, "message": TEXT},
            blocking=True,
            return_response=True,
        )
        await hass.async_block_till_done()
        return response

    first = await send()
    assert (first["result"], first["action"], first["state"]) == (
        "accepted",
        "created",
        "waiting",
    )
    second = await send()
    assert (second["action"], second["state"]) == ("updated", "waiting")
    assert phone == []
    assert len(open_items(hass)) == 1

    hass.states.async_set("input_boolean.night_mode", "off")
    await hass.async_block_till_done()
    assert len(phone) == 1
    assert phone[0].data["title"].startswith("2x ")

    third = await send()
    assert (third["action"], third["state"]) == ("bundled", "delivered")
    assert len(phone) == 2  # the replaced push, not a new cycle
    assert phone[1].data["title"].startswith("3x ")
    assert phone[1].data["data"]["tag"] == phone[0].data["data"]["tag"]
    assert open_items(hass) == []


async def test_unknown_kind_is_rejected_with_invalid_field(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """An unknown kind is the one rejection with the key ``invalid_field``.

    Every other wrong field is Home Assistant's own schema error before the
    center runs. Nothing is stored and nothing is pushed.
    """
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "send",
            {"title": TITLE, "message": TEXT, "kind": "nope"},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert err.value.translation_key == "invalid_field"
    assert err.value.translation_placeholders["field"] == "kind"
    assert phone == []
    assert open_items(hass) == []
    assert center_entry.runtime_data.book.messages == {}
    assert hass.states.get("sensor.message_center_new").state == "0"


async def test_discard_only_open_messages(
    hass: HomeAssistant, phone: list[ServiceCall], make_entry: Any
) -> None:
    """Discard removes held messages; delivered ones and the phone stay."""
    hass.states.async_set("input_boolean.night_mode", "on")
    from .conftest import night_rule_data

    entry = make_entry(rules=[night_rule_data()])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await notify(hass)
    assert open_items(hass)[0]["state"] == "waiting"
    response = await hass.services.async_call(
        DOMAIN,
        "discard",
        {"origin": "unknown", "title": TITLE},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()
    assert response == {"result": "done", "discarded": 1}
    assert open_items(hass) == []
    assert phone == []
    response = await hass.services.async_call(
        DOMAIN,
        "discard",
        {"message_id": message_id_of(hass)},
        blocking=True,
        return_response=True,
    )
    assert response == {"result": "done", "discarded": 0}


async def test_old_form_id_is_not_found_except_for_discard(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """An id of the form ``origin:key`` (up to 0.10.5) names no message.

    ``snooze`` and ``forward`` reject it with ``not_found``; ``discard`` keeps
    its contract and answers ``discarded: 0``. The README names both.
    """
    await notify(hass)
    book = center_entry.runtime_data.book
    assert book.messages[message_id_of(hass)].state == "delivered"
    old_id = f"unknown:{TITLE}"
    for action, extra in (("snooze", {"minutes": 5}), ("forward", {})):
        with pytest.raises(ServiceValidationError) as err:
            await hass.services.async_call(
                DOMAIN, action, {"message_id": old_id, **extra}, blocking=True
            )
        assert err.value.translation_key == "not_found"
    response = await hass.services.async_call(
        DOMAIN,
        "discard",
        {"message_id": old_id},
        blocking=True,
        return_response=True,
    )
    assert response == {"result": "done", "discarded": 0}
    assert book.messages[message_id_of(hass)].state == "delivered"
    assert len(phone) == 1


async def test_snooze_resends_later(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """Snooze answers with the end time; unknown ids are rejected."""
    await notify(hass)
    response = await hass.services.async_call(
        DOMAIN,
        "snooze",
        {"message_id": message_id_of(hass), "minutes": 30},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()
    assert response["result"] == "done"
    assert open_items(hass)[0]["state"] == "waiting"
    assert open_items(hass)[0]["reason"].startswith("snoozed until")
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, "snooze", {"message_id": "nope:x", "minutes": 5}, blocking=True
        )
    assert err.value.translation_key == "not_found"


async def test_forward_fires_event_with_text(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """Forward hands text and note to the assistant event and marks the message."""
    events = async_capture_events(hass, EVENT_FORWARDED)
    await notify(hass)
    await hass.services.async_call(
        DOMAIN,
        "forward",
        {"message_id": message_id_of(hass), "note": "Was ist da los?"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["message"] == TEXT
    assert events[0].data["note"] == "Was ist da los?"
    assert events[0].data["state"] == "delivered"


async def test_validation_errors(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """Schema validation rejects bad calls."""
    with pytest.raises(vol.Invalid):
        await hass.services.async_call("notify", "message_center", {}, blocking=True)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, "send", {"title": "x", "message": "x", "priority": 4}, blocking=True
        )
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "discard", {}, blocking=True)
    assert phone == []


async def test_not_ready_without_entry(hass: HomeAssistant) -> None:
    """Without a loaded entry the intake is rejected with not_ready."""
    assert await async_setup_component(hass, DOMAIN, {})
    with pytest.raises(ServiceValidationError) as err:
        await notify(hass)
    assert err.value.translation_key == "not_ready"


async def test_list_is_admin_only(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_admin_user: Any,
    hass_read_only_user: Any,
) -> None:
    """List needs an admin context; it returns text and recipient states."""
    await notify(hass)
    for context in (Context(), Context(user_id=hass_read_only_user.id)):
        with pytest.raises(ServiceValidationError) as err:
            await hass.services.async_call(
                DOMAIN, "list", {}, blocking=True, return_response=True, context=context
            )
        assert err.value.translation_key == "not_authorized"
    response = await hass.services.async_call(
        DOMAIN,
        "list",
        {"include_history": True},
        blocking=True,
        return_response=True,
        context=Context(user_id=hass_admin_user.id),
    )
    messages = response["messages"]
    assert len(messages) == 1
    assert messages[0]["message"] == TEXT
    assert messages[0]["recipients"][PHONE_ACTION]["state"] == "delivered"
    assert response["history"] == []


async def test_follow_up_calls_carry_the_senders_context(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_admin_user: Any,
) -> None:
    """The push runs with parent_id and user_id of the intake call."""
    context = Context(user_id=hass_admin_user.id)
    await hass.services.async_call(
        "notify",
        "message_center",
        {"title": "T", "message": "M"},
        blocking=True,
        context=context,
    )
    await hass.async_block_till_done()
    assert phone[0].context.parent_id == context.id
    assert phone[0].context.user_id == hass_admin_user.id


async def test_interventions_fire_logbook_events_without_text(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """Discard and snooze fire events with origin and title, never the text."""
    snoozed = async_capture_events(hass, EVENT_SNOOZED)
    discarded = async_capture_events(hass, EVENT_DISCARDED)
    hass.states.async_set("input_boolean.night_mode", "on")
    await notify(hass)
    await hass.services.async_call(
        DOMAIN,
        "snooze",
        {"message_id": message_id_of(hass), "minutes": 5},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, "discard", {"message_id": message_id_of(hass)}, blocking=True
    )
    await hass.async_block_till_done()
    assert len(snoozed) == 1
    assert snoozed[0].data["minutes"] == 5
    assert snoozed[0].data["title"] == TITLE
    assert snoozed[0].data["source"] == "action"
    assert "message" not in snoozed[0].data
    assert len(discarded) == 1
    assert discarded[0].data["message_id"] == message_id_of(hass)
    assert "message" not in discarded[0].data


async def test_last_delivery_sensor_has_origin(
    hass: HomeAssistant, phone: list[ServiceCall], center_entry: MockConfigEntry
) -> None:
    """The published attribute is ``origin``, not ``sender``."""
    await notify(hass)
    state = hass.states.get("sensor.message_center_last_delivery")
    assert state.attributes["origin"] == "unknown"
    assert state.attributes["title"] == TITLE
    assert "sender" not in state.attributes


async def intervene(
    hass: HomeAssistant, action: str, context: Context, mid: str | None = None
) -> None:
    """Call discard, snooze or forward on the test message in that context."""
    data: dict[str, Any] = {"message_id": mid or message_id_of(hass)}
    if action == "snooze":
        data["minutes"] = 5
    await hass.services.async_call(DOMAIN, action, data, blocking=True, context=context)
    await hass.async_block_till_done()


async def test_interventions_need_the_right_to_control_the_center(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_read_only_user: Any,
) -> None:
    """A user who may not control the center's entities is refused.

    Home Assistant's own check decides; the message stays as it was and no
    event is fired. ``send`` and ``notify`` stay open to everyone.
    """
    captured = [
        async_capture_events(hass, event_type)
        for event_type in (EVENT_SNOOZED, EVENT_FORWARDED, EVENT_DISCARDED)
    ]
    context = Context(user_id=hass_read_only_user.id)
    await hass.services.async_call(
        "notify",
        "message_center",
        {"title": TITLE, "message": TEXT},
        blocking=True,
        context=context,
    )
    await hass.async_block_till_done()
    assert len(phone) == 1
    msg = center_entry.runtime_data.book.messages[message_id_of(hass)]
    before = msg.to_dict()
    for action in ("snooze", "forward", "discard"):
        with pytest.raises(Unauthorized):
            await intervene(hass, action, context)
    assert msg.to_dict() == before
    assert msg.events == []
    assert [len(events) for events in captured] == [0, 0, 0]


async def test_interventions_allowed_for_users_and_automations(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_admin_user: Any,
) -> None:
    """An administrator, a user and a call without a user all get through."""
    user = await hass.auth.async_create_user("Alex", group_ids=["system-users"])
    assert not user.is_admin
    for context in (
        Context(),
        Context(user_id=hass_admin_user.id),
        Context(user_id=user.id),
    ):
        await notify(hass)
        for action in ("snooze", "forward", "discard"):
            await intervene(hass, action, context)
        msg = center_entry.runtime_data.book.messages[message_id_of(hass)]
        assert [e["kind"] for e in msg.events] == ["snoozed", "forwarded", "discarded"]


async def test_intervention_events_carry_the_context_of_who_intervened(
    hass: HomeAssistant,
    phone: list[ServiceCall],
    center_entry: MockConfigEntry,
    hass_admin_user: Any,
) -> None:
    """Snoozed and discarded run in the context of the user acting, not the sender's.

    The logbook then shows who did it, as it does for forwarded. The event
    data name the user too.
    """
    snoozed = async_capture_events(hass, EVENT_SNOOZED)
    discarded = async_capture_events(hass, EVENT_DISCARDED)
    user = await hass.auth.async_create_user("Alex", group_ids=["system-users"])
    await hass.services.async_call(
        "notify",
        "message_center",
        {"title": TITLE, "message": TEXT},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    await hass.async_block_till_done()
    snooze_context = Context(user_id=user.id)
    await intervene(hass, "snooze", snooze_context)
    discard_context = Context(user_id=user.id)
    await intervene(hass, "discard", discard_context)

    assert snoozed[0].context.id == snooze_context.id
    assert snoozed[0].context.user_id == user.id
    assert snoozed[0].data["user_id"] == user.id
    assert discarded[0].context.id == discard_context.id
    assert discarded[0].context.user_id == user.id
    assert discarded[0].data["user_id"] == user.id


async def test_interventions_without_entry_are_not_ready_for_a_user_too(
    hass: HomeAssistant, hass_admin_user: Any
) -> None:
    """Without a loaded entry the answer is ``not_ready``, not ``Unauthorized``.

    The right is checked at the center's entities; without an entry there are
    none, and the check alone would refuse even an administrator.
    """
    assert await async_setup_component(hass, DOMAIN, {})
    context = Context(user_id=hass_admin_user.id)
    for action in ("snooze", "forward", "discard"):
        with pytest.raises(ServiceValidationError) as err:
            await intervene(hass, action, context, mid="0123456789abcdef")
        assert err.value.translation_key == "not_ready"
