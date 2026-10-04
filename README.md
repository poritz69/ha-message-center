<p align="center">
  <img src="https://raw.githubusercontent.com/poritz69/ha-message-center/main/docs/images/banner-dark.png" alt="Message Center: all notifications of your home in one place. Priority 1 Notice: push. Priority 2 Important: push and light pulse. Priority 3 Alarm: alarm push and alarm light.">
</p>

<p align="center">
  <a href="https://www.hacs.xyz/"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5" alt="HACS: custom repository"></a>
  <a href="https://www.home-assistant.io/"><img src="https://img.shields.io/badge/Home%20Assistant-2026.9%2B-41BDF5" alt="Home Assistant 2026.9 or newer"></a>
  <a href="https://github.com/poritz69/ha-message-center/releases"><img src="https://img.shields.io/badge/status-beta-fe7d37" alt="Status: beta"></a>
  <a href="https://github.com/poritz69/ha-message-center/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-007ec6" alt="License: Apache 2.0"></a>
</p>

A custom integration for Home Assistant. Your automations send a title and a text to `notify.message_center`, exactly as they would to a phone. Message Center decides what happens next.

<p align="center">
  <img src="https://raw.githubusercontent.com/poritz69/ha-message-center/main/docs/images/flow.gif" alt="Animation of the card 'How a message travels': while night mode is on, a notice and an important message wait in Open and are delivered when the rule ends; an alarm passes at once and starts the alarm light." width="800">
  <br>
  <sub>How a message travels: with night mode on, a notice and an important message wait in <i>Open</i> until the rule ends. An alarm passes at once.</sub>
</p>

| Without Message Center | With Message Center |
|---|---|
| Pushes at 3 a.m. | **Held back** while night mode is on, delivered when it ends. An alarm still gets through. |
| Twenty pushes from one chatty sensor. | **Bundled** into one push that counts up: "3x Humidity high: Bathroom". |
| A failed push is lost; only the log knows. | **Retried** after 1, 5 and 15 minutes, then hourly, when Home Assistant reports a failure. |
| A hint sounds just like a water leak. | **Three priorities:** a push, a push with a light pulse, or an alarm through "do not disturb" with flashing lights. |
| Nobody knows why a message did not arrive. | **One page** in the sidebar shows every message: where it came from, what happened to it and why. |

<table>
  <tr>
    <td align="center"><img src="https://raw.githubusercontent.com/poritz69/ha-message-center/main/docs/images/phone.png" alt="Overview of Message Center on a phone" width="210"></td>
    <td align="center"><img src="https://raw.githubusercontent.com/poritz69/ha-message-center/main/docs/images/open.png" alt="Open tab: a message held back by night mode, with the buttons Send now, Discard, Later and To assistant" width="520"><br><img src="https://raw.githubusercontent.com/poritz69/ha-message-center/main/docs/images/history.png" alt="History tab: a water leak alarm with the alarm light, a snooze from the phone and a forward to the assistant" width="520"></td>
  </tr>
  <tr>
    <td align="center"><sub>Overview on a phone</sub></td>
    <td align="center"><sub><i>Open</i>: held back, with the reason and what you can do<br><i>History</i>: what happened to each message</sub></td>
  </tr>
</table>

> **Beta.** Message Center runs every day in the author's home and is open for testing before 1.0. It needs Home Assistant 2026.9.0 or newer and the Companion App on at least one phone. Something odd or unclear? Please [open an issue](https://github.com/poritz69/ha-message-center/issues).

**Quick start**

1. HACS → menu → **Custom repositories** → add `https://github.com/poritz69/ha-message-center` with type **Integration**, download *Message Center*, restart Home Assistant.
2. **Settings → Devices & services → Add integration → Message Center**, choose the phones.
3. Open **Message Center** in the sidebar and press **Search Home Assistant** on the *Message kinds* tab: it lists every automation, script and file that still notifies a phone directly. Point each of them to `notify.message_center` instead; only the action line changes.
   ```diff
      actions:
   -    - action: notify.mobile_app_alex_phone
   +    - action: notify.message_center
          data:
            title: "Humidity high: Bathroom"
            message: "Humidity in the bathroom above 70 % for 30 min. Please ventilate."
   ```

German guides: [Bedienhilfe](https://github.com/poritz69/ha-message-center/blob/main/docs/bedienhilfe.md) (user guide) and [Pflegeanleitung](https://github.com/poritz69/ha-message-center/blob/main/docs/pflegeanleitung.md) (maintenance guide).

## Contents

- [What it does](#what-it-does)
- [Installation](#installation)
- [Setup](#setup)
- [Sending messages](#sending-messages)
- [Settings](#settings)
- [Interfaces and their contracts](#interfaces-and-their-contracts)
- [Dependencies and reduced operation](#dependencies-and-reduced-operation)
- [Limits](#limits)
- [Data and privacy](#data-and-privacy)
- [Troubleshooting](#troubleshooting)
- [Removal](#removal)
- [Design principles](#design-principles)
- [Development](#development)

## What it does

Typical uses:

- **Quiet nights.** Hints wait while night mode is on and arrive in the morning; an alarm still gets through.
- **No flood of repeats.** A sensor that reports every 15 minutes produces one push with a counter, not twenty.
- **One place to see why.** Every message shows where it came from, whether it was delivered, held or discarded, and for what reason.
- **Importance you can feel.** Important messages pulse the lights that are on; an alarm is loud and keeps the lights flashing until someone ends it.
- **Hints that go stale.** "Good time to air the room" expires instead of arriving hours late.

Message Center polls nothing. Its entities and its page change the moment something happens: a message arrives, a rule entity changes its state, a push succeeds or fails, a deadline passes.

| Term | Meaning |
|---|---|
| **Origin** | The automation a message comes from. Message Center reads it from the call itself; the sender does not state it. A script counts as the automation that started it. A call from the developer tools, the API or another integration has the origin "unknown". |
| **Message kind** | An entry that recognises one sort of message by origin and title ("exact", "begins with", "contains", or "all messages of this automation") and says how to treat it: priority, group, spacing, expiry, light pulse, "do not hold". |
| **Group** | A set of kinds for display and filtering, such as "Climate" or "Server". |
| **Priority** | 1 notice (push), 2 important (push and light pulse), 3 alarm (push that breaks through "do not disturb", plus the alarm light). |
| **Delivery rule** | While an entity is in a state, messages of a priority are passed, held or discarded. Held messages are delivered when the state ends, at the latest after the rule's maximum duration. |
| **New** | A message no kind matches. It is delivered as priority 1 under the delivery rules and listed under "New, please classify" until you create a kind for it. |

A message is identified by its origin and its title. When the same message arrives again, no second one is created: its counter goes up and the push on the phone is replaced ("2x Humidity: office"). Message Center never deletes anything from a phone, and there is no "done" or "clear": a delivered message is finished.

Message Center starts no chain reactions of its own: a message that one of its own effects sends back (a script it ran, an automation reacting to a lamp it pulsed) is delivered like any other, but starts no script, light pulse or alarm light again (see [Scripts](#scripts-own-effect-and-forwarding)).

## Installation

With [HACS](https://www.hacs.xyz/):

1. HACS → menu → **Custom repositories** → add `https://github.com/poritz69/ha-message-center` with type **Integration**.
2. Search for "Message Center" in HACS and download it.
3. Restart Home Assistant.

Without HACS: copy the folder `custom_components/message_center` into `config/custom_components/` and restart Home Assistant.

You need at least one phone or tablet with the Home Assistant Companion App, because that is where the pushes go.

## Setup

1. **Settings → Devices & services → Add integration → Message Center.** Choose the phones that receive the messages (at least one). Only one Message Center can be set up.
2. Open **Message Center** in the sidebar. The page is for administrators only, because it shows message texts. An introduction card on the overview explains the idea in five short steps; it can be hidden and shown again from the settings tab.
3. Point an automation to `notify.message_center` (see [Sending messages](#sending-messages)). In the automation editor, search for “Message Center” at the top of *Add action*. Pick the entry called just “Message Center”, not “Message Center: Send”. The button **Search Home Assistant** on the *Message kinds* tab lists the places that still notify a phone directly, and says for each whether it needs a title of its own.
4. The first message of each sort shows up under **New, please classify**. "Classify" turns it into a message kind.
5. Optionally create a delivery rule on the *Delivery rules* tab, for example: toggle "night mode" is `on` → hold priorities 1 and 2, pass priority 3, for 12 hours at most. The rule's dialog explains what such a mode is and can create the toggle (a helper `input_boolean`) for you. Message Center only creates it and never switches it: an automation or a dashboard turns it on and off.

Everything is configured in the UI. There is no YAML and nothing needs a restart.

## Sending messages

```yaml
- action: notify.message_center
  data:
    title: "Humidity: office"
    message: "62 % for more than two hours. Please ventilate."
```

`data` may carry anything the Companion App understands (image, own buttons, …) that can be stored as JSON; it is passed on unchanged apart from the keys listed under [the notify action](#notifymessage_center-main-way).

**Choose titles with care, because the title is the identity of a message.**

- Put the varying part (a room, a device) into the **title** if every room should be its own message: "Humidity: office", "Humidity: kitchen". One kind "begins with *Humidity*" then covers all rooms.
- Put it into the **text** if there should be only one message that later ones replace.
- Without a title, the message is called after its automation (or script). Only when the origin is unknown is it called "Mitteilung". The name is then its identity: renaming the automation makes later messages new ones (a kind "all messages of this automation" still takes them).
- Two or more calls without a title in one automation (with different texts) are different messages under the same name, so they replace each other on the phone: give each of them a title of its own (the field *Title* of the action in the automation editor), then create the kinds. The kind dialog and the search point this out.

If a sender needs to know whether the message was accepted, or wants a fallback when Message Center is down, use the script blueprint that ships with the integration (see [Blueprint](#blueprint-send-with-fallback)).

### Examples

An automation that reports a finished washing machine, with a picture and an own button; Message Center adds its own buttons behind it:

```yaml
- alias: Washing machine finished
  triggers:
    - trigger: state
      entity_id: sensor.washing_machine_state
      to: "finished"
  actions:
    - action: notify.message_center
      data:
        title: "Washing machine finished"
        message: "The laundry can be hung up."
        data:
          image: /local/washing_machine.jpg
          actions:
            - action: LAUNDRY_DONE
              title: "Done"
```

A sender that must not get lost uses a script made from the blueprint (here called `script.send_with_fallback`) and can read the result:

```yaml
- action: script.send_with_fallback
  data:
    title: "Water leak: cellar"
    message: "The sensor under the boiler reports water."
  response_variable: sent
# sent.result is "accepted" or "fallback"
```

Message Center never reports its own faults through itself. To notice when it stops accepting messages, watch its "Ready" entity with Home Assistant's own means:

```yaml
- alias: Message Center not ready
  triggers:
    - trigger: state
      entity_id: binary_sensor.message_center_ready
      to: "off"
      for: "00:02:00"
  actions:
    - action: persistent_notification.create
      data:
        title: "Message Center is not ready"
        message: "{{ state_attr(trigger.entity_id, 'reason') }}"
```

A script chosen as the effect of priority 2 that also announces the title on a speaker:

```yaml
announce_message:
  sequence:
    - action: tts.speak
      target:
        entity_id: tts.home_assistant_cloud
      data:
        media_player_entity_id: media_player.kitchen
        message: "{{ title }}"
```

The entity ids in these examples are placeholders; pick your own in the UI.

## Settings

All settings live on the page in the sidebar. This is a deliberate choice: the page shows the settings next to what they do, and each priority has a test button.

| Tab | What you set |
|---|---|
| **Message kinds** | Groups (name, icon, defaults) and kinds: name, origin (one automation or any), title condition, group, priority, "do not hold" (ignore delivery rules), spacing in minutes (minimum time between two push cycles of the same message), expiry in minutes (an undelivered message is discarded after that), light pulse (by priority / always / never), active. "All messages of this automation" needs a named origin. If several kinds match, the most specific one wins: a named origin before "any", "exact" before "begins with" before "contains" before "all messages of this automation", then the longer condition. Two kinds cannot have the same condition: a double condition (an inactive kind counts too) is refused with a link to the existing kind. The dialog of a kind says in plain words what it applies to. Opened from *New*, from the search or to edit, it shows origin and title greyed out (*Edit condition (advanced)* opens them) and takes "all messages of this automation" for an automation that sends one message; for one that sends several it lists the messages it may send (a call without a title by the first line of its text) and, when two or more calls have no title, asks to give each one a title. It shows which earlier messages the condition matches and which kind wins an overlap; before a change that would send the original message back to *New*, saving asks. A new kind without a template can *Take from “New”*. A kind whose automation no longer exists is shown greyed out as "orphaned"; it affects nothing and can be deleted. |
| **Delivery rules** | Name, entity, state, effect per priority (pass / hold / discard), maximum duration (1–168 h, default 12). If the entity is unavailable, the rule counts as active and a repair issue appears. The dialog explains what a mode is (a helper toggle such as "night mode", "vacation" or "away") and can create such a toggle (`input_boolean`, through Home Assistant's own helper command) and choose it for the rule. Message Center never switches it and creates no automation for it. |
| **Recipients** | Which Companion App devices receive the messages (at least one), whether they are reachable and their last error. |
| **Settings → priority → effect** | Per priority: an optional script (see [Scripts](#scripts-own-effect-and-forwarding)) and a **Test** button that sends a test push without any record. A test uses the saved settings: while the tab holds a change that is not saved, *Save* takes the place of each *Test* button. |
| **Settings → light pulse** | Lights and switches that pulse for priority 2, as one list in which each has its own switch "also when off" (then it goes briefly on and off again when it is off); off time (100–10 000 ms, default 500); minimum spacing between pulses (0–600 s, default 0). |
| **Settings → alarm** | Lights and switches for the alarm light; interval (100–5000 ms, default 1000); maximum duration (5–3600 s, default 300); test duration; Android alarm channel; spoken announcement of the title (Android). Do not choose a lamp that is itself the trigger of a message of priority 3 (an automation reporting that lamp): every step of the alarm would then produce a new message and a push for as long as the alarm runs. |
| **Settings → buttons on the push** | What a tap on the push opens (Home Assistant, the default, or Message Center with the message; see [Tapping the push](#tapping-the-push)); "Later" (one or two fixed durations, or typed minutes), "To assistant", and a script to run when a message is forwarded. |
| **Settings → options** | History retention (1–365 days, default 30); sidebar entry on/off; keep titles out of history and attributes (then also out of the events, the logbook and the push `tag`); allow priority 3 through `message_center.send`; replace repeats silently. |

The other two tabs show what is going on: **Open** (everything not finished yet, with state, reason and deadline, and the buttons *send now*, *discard*, *later*, *to assistant*) and **History** (delivered, discarded and failed messages with their interventions; its column *Time* is when a message ended, always with date and time, newest or oldest first as chosen, and the browser remembers that choice). *Send now* also works on a message that is retrying: the recipients that do not have it yet are tried at once, whether a rule holds the retry back or its next time lies ahead.

## Interfaces and their contracts

Only what is listed here is meant to be used by automations and other integrations. Everything else, including the WebSocket commands `message_center/*` behind the page (such as `message_center/origin_messages` and `message_center/kind_matches`), is internal and may change.

**`message_id`** is the handle of a message wherever it appears (responses, entity attributes, events, script variables, the push `tag`, the tap target (`clickAction`/`url`), the button ids, the page): an opaque string of 16 hexadecimal characters, stable for all generations of a message and across restarts, without `:` or `|`. It has no structure to read; the origin and the title stand next to it wherever it appears.

**Wrong fields** (missing, empty, too long, wrong type, or data that cannot be stored as JSON) are rejected by Home Assistant before Message Center runs, as a schema error ("Invalid data"), the same for every action. It carries no error code of Message Center, and in a script `continue_on_error` does not cover it. The error codes below are the rejections of Message Center itself.

### `notify.message_center` (main way)

| Field | |
|---|---|
| `message` | required, 1–2000 characters |
| `title` | optional, 1–100 characters; default: the name of its origin, as the entity settings show it (a script started by an automation counts as that automation), cut to 100 characters; "Mitteilung" when the origin is unknown |
| `data` | optional; passed on to the Companion App. Must be storable as JSON (no numbers beyond 64 bit, no cyclic structures, nesting of 250 levels at most); what Home Assistant can convert (set, tuple, datetime) is fine. A text with half a character pair (a cut emoji) is refused the same way |
| `target` | accepted and ignored: Message Center chooses the recipients |

- **Effect:** the message is classified, stored and delivered according to priority and delivery rules. The same origin and title increase the counter of the existing message.
- **Keys Message Center sets in `data`:** always `tag` (the `message_id`) and `group`; on Android always `channel` (`message_center`, or the alarm channel for priority 3) and for priority 3 also `ttl`, `priority`, `importance`; on iOS `push.interruption-level` (and a critical sound for priority 3). Its own buttons are **appended** to `actions`; the caller's buttons stay (see [Buttons on the push](#buttons-on-the-push) for the order on an alarm). The target of a tap, `clickAction` on Android and `url` on iOS, is set only when neither of the two keys in the caller's `data` holds a target (a key that is `null` or empty text holds none), and only on the phone of an administrator (see [Tapping the push](#tapping-the-push)).
- **Push text:** the push of a message no kind takes ends with a blank line and "⚠ Not classified yet – please classify it in Message Center" ("⚠ Noch nicht eingeordnet – bitte im Message Center bewerten" in a German Home Assistant). The line is in the push only; the message keeps its text everywhere else (store, history, events, scripts, the page).
- **Rights:** any user who may call actions. The caller's context is stored and passed on to the pushes, the light commands and the effect script.
- **May be repeated:** yes; a repeat counts.
- **Result:** no response data. A rejection is an error: `store_full` (200 unfinished messages) or `not_ready` (no Message Center loaded, its store cannot be written, or it is being reloaded). No error means *accepted*, that is stored and confirmed on disk; it does not mean delivered. A call that is cancelled while Message Center writes (an automation in mode `restart`) is not accepted.

### `message_center.send` (for senders that know their kind)

Fields `title` and `message` (required), `data`, and optionally:

- `kind`: name or id of a message kind. It applies even if its conditions would not match. An unknown kind is rejected with `invalid_field` (the only case of that code).
- `priority`: 1–3, used only when no kind applies. Priority 3 needs the option "allow priority 3 through send", otherwise `priority_not_allowed`.
- `key`: 1–80 characters; replaces the title as the identity of the message.

Response when requested: `{"result": "accepted", "message_id": …, "action": "created" | "updated" | "bundled", "state": …, "reason": …}`. The `action` says what the call did:

| `action` | Meaning |
|---|---|
| `created` | A new message (or a new generation of a finished one) was stored, counter 1. It is delivered or waits, as the rules say. |
| `updated` | An open message (waiting, sending, retrying, unclear) took the counter, text and data; no second message. An unclear one runs again. |
| `bundled` | The message was already delivered and its kind's spacing is still running: counter up, the push on the phone replaced ("3x …"), no new push cycle, so no light pulse or script. `state` stays `delivered`. |

Keys set in `data`, the push text, rights, repeats and rejections otherwise as `notify.message_center`: a `send` without `kind` that no kind takes gets the line at the end of the push and the target to classify it too.

### `message_center.discard`

`message_id`, or `origin` together with `title`. Discards **open** messages; delivered ones and the phone are untouched. May be repeated. Response: `{"result": "done", "discarded": n}`; `n` is 0 when nothing matched. **Rights:** the right to control an entity of Message Center (administrators and users; a user of the group "read only" gets `Unauthorized`; a call without a user, from an automation or script, is allowed). The event runs in the context of the caller.

### `message_center.snooze`

`message_id` and `minutes` (1–10080), both required. An open or delivered message waits until the time is up and is then pushed again, if rules and expiry allow. Response: `{"result": "done", "until": …}`; `not_found` when there is no such message. **Rights:** as `discard`.

### `message_center.forward`

`message_id` (required) and `note` (optional, up to 500 characters). Fires the event `message_center_forwarded` and runs the forward script if one is chosen, under a context of Message Center below the caller's. The message itself is not changed. Response: `{"result": "done"}`; `not_found` when there is no such message. **Rights:** as `discard`.

### `message_center.list`

`include_history` (optional). **Administrators only** (`not_authorized` otherwise). Returns all messages in the working store with origin, kind, group, priority, title, text, state, counter, times, reason, state per recipient (with its retry plan) and interventions; with `include_history` also the history. Response only.

### Entities

One device "Message Center" with nine entities:

| Entity | Type | State | Attributes |
|---|---|---|---|
| Ready | binary sensor (diagnostic) | on when the working store is loaded and writable (a history that cannot be written does not turn it off) | `reason`, `missing_recipients` |
| Open | sensor | number of unfinished messages | `items`: per message `message_id`, `origin`, `origin_name`, `kind`, `group`, `priority`, `title`, `state`, `count`, `since`, `reason`, `until`, `next_try`, `failed_recipients` |
| Disturbed | sensor | number of messages that are retrying, unclear or failed (failed ones for 24 h) | `items` as above plus `last_error` |
| New | sensor | number of unclassified origin/title pairs | `items`: `origin`, `origin_name`, `title`, `count`, `last_seen` |
| Active rules | sensor (diagnostic) | number of rules in a hold phase | `rules`: `name`, `entity_id`, `since`, `until`, `expired`, `unknown` |
| Last delivery | timestamp sensor (diagnostic) | time of the last delivery | `origin`, `title` |
| Light pulse | switch (configuration) | off disables the light pulse | – |
| Alarm | switch | on while the alarm light runs; turning it off ends the alarm, turning it on starts it by hand | `until` |
| Delivered | event | time of the last delivery | the data of `message_center_delivered` |

Message states are `waiting`, `sending`, `retrying`, `delivered`, `unclear`, `discarded` and `failed`. "Open" means waiting, sending, retrying or unclear. A retrying message that a delivery rule holds back shows the rule as its `reason` ("held back: ‹rule› until …") and no `next_try`: nothing happens before the rule ends, and that end stands in `until`. No attribute ever contains a message text. Entity ids are not fixed addresses: pick the entities in the UI rather than assuming their names.

### Events

| Event | When | Data |
|---|---|---|
| `message_center_delivered` | once per push cycle, at the first recipient that took the push | `message_id`, `origin`, `origin_name`, `kind`, `group`, `priority`, `title`, `count`, `recipients` |
| `message_center_discarded` | an open message was discarded by hand | `message_id`, `origin`, `origin_name`, `kind`, `priority`, `title`, `source`, `user_id` |
| `message_center_snoozed` | a message was snoozed | as above plus `minutes` |
| `message_center_forwarded` | a message was forwarded | `message_id`, `origin`, `origin_name`, `kind`, `group`, `priority`, `title`, `display_title`, `message`, `note`, `source`, `user_id`, `accepted_at`, `state`, `reason` |

`source` is `action`, `page` or `phone`. Only `message_center_forwarded` carries the text: forwarding a message is the deliberate act of handing it on; its `title` and `message` are the real ones, `display_title` is the title as the attributes show it (origin and kind when titles are kept out). `message_center_delivered` runs in the context of the sender; the other three run in the context of whoever intervened (action, page or phone), which the logbook shows. All four events appear in the logbook. Expiry, a discarding rule and the maximum wait of 7 days do not fire an event; they are visible in the history on the page. Home Assistant's recorder keeps events in its database; see [Data and privacy](#data-and-privacy).

### Buttons on the push

- **Later ‹duration›** snoozes the message for the duration on the button (default 30 minutes). A second duration or typed minutes are options.
- **To assistant** forwards the message; a note can be typed. Characters that cannot be stored (half a character pair) are replaced by "?".
- **End alarm** on priority 3 pushes when an alarm light is configured.

The order is: the caller's own buttons, then *Later* (the first, then the second duration), then *To assistant*, then *End alarm*, except that *End alarm* moves to the third place at the latest. Nothing is removed: Android shows the first three buttons, the iPhone all of them. On Android, *To assistant* is therefore the first to lose its visible place, then *Later*; from three own buttons on, the third own button stands behind *End alarm*.

Each button can be turned off. A tap is handled in the context of the user of that phone, also for *Later*. *Later* and *To assistant* check the right the actions check: the user of the phone must be active and allowed to control an entity of Message Center. A tap from the phone of a user who may only read, or who is deactivated, is ignored and logged without content; the buttons still show on that phone, so do not choose such a phone as a recipient if its user should not use them. (A deleted user is refused too, as a safeguard: Home Assistant removes the phone's registration together with the user.) *End alarm* works from any phone whose Companion App reaches Home Assistant, because ending a running alarm harms nothing.

### Tapping the push

The option *Open on tap* decides what a tap on the push opens:

- **Home Assistant** (default, `tap_target: home`): Message Center sets no target; the Companion App opens as usual.
- **Message Center** (`tap_target: center`): the page opens with this message unfolded, on the tab *Open* or in the history: `/message-center?message=<message_id>`.

A message no kind takes opens the dialog to classify it, whatever the option says: `/message-center?classify=<message_id>`. If its entry under *New* is gone by then (classified or dismissed), the page shows the message. Once a kind takes the message, its pushes, a replacement too, follow the option again; this holds for a message that waits while it is classified as well.

A sender that puts a target into `clickAction` or `url` in `data` keeps it: Message Center then sets neither key, on neither platform, also for a message no kind takes. A key that is `null` or empty text (as blueprints often pass it when no target was chosen) is no target; Message Center then sets its own. A test push from the settings tab opens the page itself with the option *Message Center*.

The page is for administrators only, so Message Center sets these targets only on the phones of administrators (the user the Companion App was registered with). The phone of another user, or one whose user it cannot tell, opens Home Assistant as before; the line on a message no kind takes shows there too.

### Scripts: own effect and forwarding

Message Center can run scripts you choose on the settings tab:

| Chosen as | Runs |
|---|---|
| effect of priority 1, 2 or 3 | at the first delivery of each push cycle of that priority, and when its test button is pressed |
| target of "To assistant" | every time a message is forwarded (action, page or phone), in addition to the event |

The script receives these variables: `message_id`, `title`, `text`, `note` (forwarding only), `origin`, `origin_name`, `kind`, `group`, `priority`, `count`. It has 30 seconds and never holds up a delivery. The outcome is noted under the message as `script` or `script_failed`. By choosing a script you hand the texts to that script.

**Depth 1.** An effect script runs in the context of the message's sender, the forward script in a context of Message Center below the caller's; the light pulse, the alarm light and the test buttons run as effects of Message Center too. A message that arrives under one of these contexts, or under a child of one (the script itself, an automation triggered by what the script or a pulsed lamp did), was caused by Message Center. It is delivered like any other, on the alarm channel for priority 3, but starts no effect script (noted as `script_skipped`), no light pulse and no alarm light (noted as `light_skipped`, "message from an own effect"). So a script that reports its work through `notify.message_center`, or the assistant's answer after a forward, reaches the phones and stops there. When the same message later arrives from outside again, it loses the mark. Not counted as an own effect: the event `message_center_delivered`, the event `message_center_forwarded` and the push itself; an automation that reacts to one of them and notifies through Message Center is not limited, nor is a chain through two or more foreign contexts or through an outside system (MQTT, Node-RED).

### Blueprint "send with fallback"

The script blueprint *Message Center: Nachricht senden (mit Rückfall)* is copied to `blueprints/script/message_center/` on setup and never overwritten. Inputs: the entity "Ready" and, optionally, a fallback target (the name of a Companion App notify action, `mobile_app_…`). Fields: `title`, `message`, `data`.

While "Ready" is on it calls `message_center.send`. If the message is not accepted (Message Center missing, not ready or rejecting), the message appears as a persistent notification in Home Assistant and, if a fallback target is set, goes there as a plain push: title and text only, no delivery rules, to that one target only. Response: `result: accepted` or `fallback`, with a `reason`.

- **The sender never waits for the phone.** The plain push runs as a separate run of the script; a phone that hangs or fails does not delay the sender or change the result. A fallback target that does not exist shows up as an error in the log.
- **A call that can never be accepted** (a title longer than 100 characters, an empty text, extra data that cannot be stored as JSON) is the sender's error: the script fails instead of falling back.
- **Updating the blueprint:** the file is never overwritten, so a newer version does not arrive by itself. Delete `blueprints/script/message_center/nachricht_senden.yaml` and restart Home Assistant; the integration then copies the current one.

## Dependencies and reduced operation

Message Center needs only Home Assistant itself and the Mobile App integration. Everything else is optional.

| Missing or failing | What happens |
|---|---|
| A push to a phone fails | Message Center sees only what the Companion App action reports: a missing action, invalid data and Home Assistant errors. A phone that is offline is usually **not** among them: for a phone reached through the app's push service (the normal case) the action gives up after 10 seconds itself, logs the error and returns as if sent. Only a device registered for local push alone that is not connected comes back as a Home Assistant error and is retried. For a failure it does see, it retries that phone 1, 5 and 15 minutes after the first failure, then hourly, until no retry time is left before 24 hours; `attempts` only counts. A persistent notification while deliveries fail; a repair issue after 15 minutes. Other phones are not affected. While a delivery rule holds the priority, a due retry waits for the rule's end (shown as the reason) and goes out then, or at the maximum duration; a kind with "do not hold" and priority 3 go through. A rule that *discards* the priority ends the cycle before the retry: *delivered* with `failed_recipients` when a phone already has the message, otherwise *discarded* (`rule_discarded`). Expiry and the maximum wait of 7 days apply to a retrying message as well. Caller data that no push can be built from (`actions` that is not a list) count as a failed attempt with the error class as `last_error`. |
| The entity of a delivery rule is unavailable | The rule counts as active (nothing slips through by accident), with the reason shown and a repair issue. The maximum duration still ends it. A waiting message is discarded if the rule says so, as always; a *retrying* message is only held while the entity is unavailable ("mode unknown"), never discarded. |
| Lights or switches for the light pulse are off or missing | No pulse; noted under the message. The push is not affected. |
| The trigger may not switch the lamps | Light commands run in the context of whoever caused them: the sender of the message for the light pulse and the alarm light, the person who turned on the switch "Alarm", the administrator who pressed a test button. Home Assistant checks the right to the lamps itself. Without that right (or when the stored user no longer exists) the lamps stay as they are, the alarm light included; the push is not affected. Noted under the message as `light_failed`, and in the log as "Light pulse refused" or "Alarm light refused". For automations and administrators nothing changes. |
| A chosen script is missing or fails | Noted under the message. The push is not affected. |
| The working store cannot be written | Every write is confirmed by reading the file back, so a full or read-only disk is seen even where Home Assistant only logs it. "Ready" turns off, a repair issue appears, and `notify`, `send`, `discard`, `snooze` and `forward` are rejected with `not_ready`. Senders that use the blueprint fall back. Each of these calls first tries the store once more; the first that succeeds makes Message Center ready again. Independent of callers it tries again every 60 seconds and heals itself. After a write that ran into the 5-second limit, calls are rejected at once, without a try, until the next write (at the latest the 60-second one) finishes in time. Anything that is due *outside* a call (a rule ends, a retry is due, a push comes back, *send now*, a start) is sent anyway: delivery comes first, at the price that such a message may be sent once more after a restart. |
| Only the history store cannot be written | "Ready" stays on; messages are taken and delivered. A repair issue "message history not writable" and one warning in the log; ended messages wait in the working store (at most 1000, see [Limits](#limits)) and are written to the history at the next attempt (hourly, at a reload, at a start). |
| The store cannot be read | The integration does not start; Home Assistant shows the reason under **Devices & services** and tries again. Messages are rejected with `not_ready` until then. This includes a working store whose id salt is missing, a message without an id and a damaged history entry. A file that is not valid JSON is moved aside by Home Assistant, which then starts with an empty store and a repair issue. |
| Home Assistant restarts | Waiting messages are re-evaluated, due retries go out with the first evaluation, and a retry a rule held back goes out when nothing holds it. A message that was being sent, and everything open after a gap of more than 60 minutes, becomes *unclear*: it is shown with a repair issue and is not sent again by itself. Send it now or discard it on the page. This holds for the first push too: "sending" is on disk before the push leaves, so a restart in between never gives a second push. Ended messages that were still waiting for the history are written to it at the start and are visible at once. |
| Message Center is reloaded or disabled | The old center writes, schedules and starts nothing more and causes no effect. A push that is under way reaches the phone but is not recorded: the new center shows the message as *unclear*. A caller that reached the old center too late is rejected with `not_ready` and falls back. |
| Message Center is not installed or not loaded | `notify.message_center` fails like any missing action. Senders that use the blueprint fall back: a notification in Home Assistant and a plain push to the fallback target. |

## Limits

- **"Delivered" means handed over, not received.** The Companion App integration catches network errors itself: its action gives up after 10 seconds, logs the error and returns normally. So Message Center cannot see whether a push reached the phone or was read, and its own time limit of 15 seconds per push is practically never reached. What it sees: a missing action, invalid data and Home Assistant errors.
- **Delivery comes before the store, outside a call.** When the working store cannot be written while a rule ends, a retry is due, a push comes back, *send now* is pressed or Message Center starts, the message is still sent; "Ready" turns off, and after a restart that message may come once more. Only `notify`, `send`, `discard`, `snooze` and `forward` are rejected. While the disk hangs, each such push is delayed by up to 5 seconds (the store is written before sending). A write that ran into the 5-second limit may still land on the disk later; the rejected message then stands there until Message Center writes again, at the latest 60 seconds after the fault ends.
- **Shutting Home Assistant down** during a write counts the write as done and leaves the file to Home Assistant's last write. A caller that is cancelled during a write leaves its attempt noted: a cancelled retry is due again at the next occasion, a cancelled first push stays in "sending" until the next start, where it becomes *unclear*. An attempt that is already running when a rule begins still goes out; only the next one is held. A cycle that ends by expiry as *delivered* no longer replaces an older counter or text on the phone.
- **Messages waiting for the history.** At most 1000 ended messages wait in the working store for a history that cannot be written; beyond that the oldest are dropped (logged as a number). Only with a history store that fails for a long time, or more than 1000 ended messages between two hourly rounds. Every write of the working store grows with them.
- **Depth 1 is a mark on the context, not a fence.** It stops effect scripts, the light pulse and the alarm light for a message that one of Message Center's own effects caused (see [Scripts](#scripts-own-effect-and-forwarding)); the message is still delivered. Automations reacting to the events `message_center_delivered` or `message_center_forwarded` or to the push itself, and chains through outside systems, are not limited. With priority 3 and an alarm lamp that is also the trigger of a message, each step of the alarm produces a new generation and a push, for the alarm duration. The mark is kept in memory only (the last 1000 contexts); a message that arrives after a restart is not marked.
- **The buttons on the push reach Home Assistant only when the phone does:** at home, through a VPN or through Home Assistant Cloud. Away from home without a connection, a tap does nothing.
- **Nothing is ever removed from a phone.** A message that has been swiped away is unknown to Message Center, and a delivered message cannot be withdrawn.
- **The search ("Search Home Assistant")** reads the loaded automations and scripts and the text files in the configuration directory. It does not see integrations that notify by themselves, nor add-ons whose files live outside the configuration directory. Titles and first lines of automations and scripts appear as Home Assistant loaded them: templates are not evaluated, `!secret` values and blueprint inputs are already filled in. For hits in files it shows the file, the line number and the action names found in that line, never the line itself (it may hold a token). It skips `secrets.yaml`, `.storage`, `custom_components`, `blueprints` and a few other folders, and stops at 3000 files of up to 1 MB and at 300 hits. Scripts made from the blueprint "send with fallback" are left out: their plain push is the fallback, not a place that still sends directly. It only reads; nothing is stored or changed.
- **Android:** a `channel` set by the caller is overridden. The alarm channel "alarm stream, full volume" does not work on every phone; the spoken announcement works on Android only. On **iOS**, critical alerts must be allowed for the app.
- **Lights:** a pulse turns a light off and on again (or on and off), which restores its last state. If someone switches such a light by hand during a pulse or an alarm, restoring may override that. Philips Hue rooms and zones accept only one command per second; choose single lights for the alarm light. The lamps are switched with the rights of whoever caused the message; a second alarm during a running one only extends its duration and keeps the first context. A refused domain (light or switch) in the first step of the alarm restores the lamps already switched.
- **Capacity:** 200 unfinished messages, 200 unclassified pairs, 20 000 history entries. A message that could not be delivered within 7 days is discarded. `list` and the diagnostics show the retry time per recipient even while a rule holds the retry; only the summary (`next_try` in the attributes, the page) leaves it out then. A caller's own push button whose action starts with `message_center_alarm_off` is treated as the alarm button and moved.
- **One Message Center per Home Assistant.** Recipients are Companion App devices only; mail, SMS and rules per recipient are planned for later.
- **The page:** dragging a kind into another group works with a mouse only.
- **No AI tools yet.** Forwarding ("To assistant") fires an event and can run a script; what that script does is up to you.

## Data and privacy

Titles and texts of messages are treated as sensitive.

- Texts are stored in Home Assistant's `.storage` (`message_center.messages`, `message_center.history`), shown on the page and returned by `message_center.list`, all for administrators only, and of course sent to the phones.
- Texts never appear in entity attributes, the logbook or repair issues, and not in any event except `message_center_forwarded`.
- Titles appear in attributes, the logbook and events. The option "keep titles out of history and attributes" replaces them there by origin and kind; it also holds for the logbook entry of a forward, the push `tag`, the tap target and the button ids, which carry only the opaque `message_id`.
- **Home Assistant's recorder stores events** in its database. `message_center_forwarded` carries the text and the note, and `mobile_app_notification_action` (the tapped button, fired by the Companion App) carries the typed note and the button id. Who does not want them there excludes the event types in `configuration.yaml`:

  ```yaml
  recorder:
    exclude:
      event_types:
        - message_center_forwarded
        - mobile_app_notification_action
  ```

- The log of Home Assistant gets error classes and fixed names only (an entity id, an action name, a count), never a title, a text, a note or a message id. Home Assistant's own line for a failed write ("Error writing config for message_center.messages") names the file, not the content.
- The diagnostics download contains no texts, notes, extra push data or user ids, but it does contain titles and the title conditions of your kinds. Read it before you share it.
- Message Center stores no credentials and contacts no service of its own; pushes go through the Companion App integration.

## Troubleshooting

| Symptom | Where to look |
|---|---|
| A message did not arrive | *Open* tab: is it waiting, and why (rule, spacing, snoozed)? *History*: was it discarded or did it expire? *Recipients*: last error of the phone. |
| A message arrived although night mode is on | Its kind has "do not hold", or it is priority 3, or the rule exceeded its maximum duration (repair issue). |
| A message shows up under "New" again | Its title changed, so the kind's title condition no longer matches, or the automation of a message without a title was renamed. "All messages of this automation" does not depend on the title. |
| A tap on the push opens Home Assistant, not the page | Check *Open on tap*. A target of the sender (`clickAction` or `url`) wins, and phones of users who are no administrators always open Home Assistant. |
| A kind is greyed out as "orphaned" | Its automation or script no longer exists. Delete the kind. |
| A delivery rule never applies | Its entity never reaches the state. Message Center does not switch the toggle of a mode, not even one it created: an automation or a dashboard must. |
| No light pulse | The lights must be on (unless marked "also when off"), the switch "Light pulse" must be on, and the kind must not say "never". The reason is noted under the message: `light_skipped` with "minimum spacing", "no lamp on" or "message from an own effect"; `light_failed` ("no right to the lamps") when the sender may not switch them. |
| A script did not run | `script_failed`: the script is missing, failed or took longer than 30 seconds. `script_skipped`: the message came from an own effect of Message Center (depth 1), see [Scripts](#scripts-own-effect-and-forwarding). |
| A retry does not happen although it is due | A delivery rule holds the priority: the reason says "held back: ‹rule› until …" and `next_try` is empty. It goes out at the rule's end, or now with *send now*. |
| "Ready" is off | Repair issue "message store not writable": check the disk and the permissions of `.storage`. Message Center tries again every 60 seconds and turns "Ready" on by itself as soon as a write succeeds; no restart needed. |
| Repair issue "message history not writable" | Only the history file fails; messages are still delivered. Check the disk and the permissions; the issue disappears with the next successful write of the history. |
| Messages are *unclear* after a restart | Send them now or discard them on the *Open* tab. |
| `discard`, `snooze` or `forward` answers `Unauthorized` | The calling user may not control the entities of Message Center (group "read only"). |

Repair issues appear under **Settings → System → Repairs**. A diagnostics download is available under **Settings → Devices & services → Message Center**.

## Removal

1. **Settings → Devices & services → Message Center → Delete.** This also deletes the stored messages and the history, so no message text stays behind.
2. Remove the integration in HACS (or delete `custom_components/message_center`) and restart Home Assistant.
3. Point your automations back to their phones, or they will fail with "action not found".
4. The blueprint in `blueprints/script/message_center/` stays; delete it if you no longer need it.
5. Toggles created with *Create toggle* in a rule's dialog are ordinary helpers and stay; delete them under **Settings → Devices & services → Helpers** if you no longer need them.

## Design principles

Message Center is built on a few principles. In short: it works on its own, is used by other integrations and automations only through its published interfaces (see [Interfaces and their contracts](#interfaces-and-their-contracts)), uses Home Assistant's own means first, shows the reason for every decision, never treats an unknown value as "off", and keeps sensitive data where it is needed. From 1.0 on, published interfaces are only ever extended; renaming or removing one needs a new major version and a notice period of at least six months.

## Development

Requires Python 3.14 (Home Assistant 2026.9 needs 3.14.2 or newer) and, for the page, Node.

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .

cd frontend && npm ci && npm run check && npm test && npm run build
```

The tests run an in-memory Home Assistant provided by `pytest-homeassistant-custom-component`. CI runs them against the minimum version from `hacs.json`, the current version from `requirements_test.txt` and the newest release of the test library, weekly and on every push. The page is written in TypeScript with Lit and bundled with esbuild; the bundle is committed, so installing needs no Node.

To look at the page without Home Assistant, `npm run preview` (in `frontend/`) builds `frontend/preview/preview.js` with example data; open `frontend/preview/index.html` through a local web server. Add `?lang=en` for English and `?theme=light` for light colours.

Changes are listed in the [changelog](CHANGELOG.md). The self-assessment against the Home Assistant quality scale is in [`quality_scale.yaml`](custom_components/message_center/quality_scale.yaml); it is not a certification by Home Assistant.

## License

Apache License 2.0, see [LICENSE](LICENSE) and [NOTICE](NOTICE).
