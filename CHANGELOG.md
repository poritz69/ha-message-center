# Changelog

Versions follow `major.minor.patch`. Published interfaces (README, "Interfaces and their contracts") are only extended within a major version.

From 0.11.1b1 on, every version is a GitHub release. The betas before 1.0 (0.11.1bN) are public test versions: until 1.0 an interface may still change, and such a change is marked **Contract change**. From 1.0.0 on, interfaces are only extended within a major version. The versions up to 0.11.0 were development steps in the author's home without releases.

## Unreleased

- **Contract change:** a message sent to `notify.message_center` without a title is called after its automation or script (cut to 100 characters), no longer "Mitteilung"; key, `message_id` and the kind it gets follow that title. With an unknown origin it stays "Mitteilung". `send` still needs a title. The name is the one of the origin's state, so a name given in the entity settings wins over the alias. What follows from it:
  - A message kind that waits for "Mitteilung" (from one automation or from any) still takes these messages, with its priority and settings, as long as no kind matches their new title. Better change it to "all messages of this automation".
  - Once after the update, an open or delivered message without a title is not replaced by the next one: that one gets a new `message_id`, its spacing starts anew, and a second push appears next to the old one. An entry "Mitteilung" under *New* can be dismissed.
  - `message_center.discard` with `origin` and the title "Mitteilung" no longer finds these messages; the same holds for automations that filter events or attributes by that title.
  - From now on, renaming the automation (alias or entity settings) gives its untitled messages a new title and identity, with the same effects. A kind "exact ‹old name›" then no longer matches; "all messages of this automation" does.
- New title condition for message kinds: "all messages of this automation" (`any`). It takes every title of one automation or script and needs that origin; among the kinds of the same origin it is the weakest condition, below "contains".
- A message kind whose condition (origin, comparison and text, case aside) another kind already has, an inactive one too, is refused. Spaces around the text of a condition are dropped when a kind is saved.
- **Way back to 0.11.1b1:** first delete the kinds with "all messages of this automation" or change their condition. 0.11.1b1 does not know this condition and does not start while such a kind exists. The stores of messages and history are unchanged.
- The search suggests "all messages of this automation" for an automation that sends one message. For a call without a title it no longer suggests the first line of the text: such a message gets the name of its automation.
- A lamp marked "pulse even when off" pulses even if it is missing from the list of lamps for the light pulse.
- The page's dialog for a message kind says on top, in plain words, what the kind applies to. Opened from *New*, from the search or to edit, it shows origin and title greyed out; "Edit condition (advanced)" opens them. For an automation that sends one message it takes "all messages of this automation" (an existing kind is put on it with a note, applied only on saving; "Keep the previous condition" undoes it); for one that sends several, the title stays open with a hint and the messages the automation may send (fixed titles, computed ones with a placeholder, and those that arrived). For a script the dialog says "script" where it says "automation". Below, the dialog shows which messages of *New* and of the history the condition matches, warns when it matches none, and names the kind that wins an overlap. A double condition is refused with a link to the existing kind, before anything (such as a new group) is created; before a change that would send the original message back to *New*, saving asks. A new kind without a template can take an entry of *New*. Kinds whose automation no longer exists are greyed out as "orphaned" and can be deleted.

## 0.11.1b1 (2026-10-02)

First public beta. Install it through HACS as a custom repository; please report what breaks as an issue.

- **Contract change:** the push buttons *Later* and *To assistant* check the right that `snooze` and `forward` check: a tap from the phone of a user who may only read or is deactivated is ignored and logged as "Push button ‹kind› ignored: Unauthorized" ("… UnknownUser" for a deleted user, a safeguard only). The buttons still show on such a phone. *End alarm* still works from any phone.
- The page uses the quotation marks of its language around a title condition and a rule state (English “on”, not German „on“), and an English hint of the search starts with a capital letter.
- The page no longer names a fixed "minimum spacing 60 s" under a skipped light pulse; the spacing is set in the settings, so the note now reads "minimum spacing between light pulses".

## 0.11.0 (2026-10-02)

The result of a review of version 0.10.5 against its documented behaviour and the published contracts. Behaviour that the README promised and the code did not keep, in the store, the delivery cycle, rights and the message id. **Take a backup before updating:** the working store moves to a new format, and the way back to 0.10.5 is only a backup of both `.storage` files (see below).

**Store**

- Every write of the stores is confirmed by reading the file back. A full or read-only disk, which Home Assistant only logs, now turns "Ready" off and rejects new messages with `not_ready`; "accepted" means the message is on disk.
- **Contract change:** extra data that cannot be stored as JSON (numbers beyond 64 bit, objects, cyclic structures, nesting deeper than 250 levels) and texts with half a character pair are rejected by Home Assistant as a schema error before the center runs, for `notify.message_center`, `send`, `forward` and `discard`. What Home Assistant can convert (set, tuple, datetime) stays allowed. Until now such a call made every later write fail.
- Not ready because of the store: `notify`, `send`, `discard`, `snooze` and `forward` first try the store once; the center also tries every 60 seconds by itself and heals without a caller. After a write that ran into the 5-second limit, calls are rejected at once until the next write finishes in time.
- **Contract change:** when a write fails *outside* a call (a rule ends, a retry is due, a push comes back, *send now*, a start), the message is still sent; "Ready" turns off and the message may come once more after a restart. Only the calls above are rejected. The page's *send now* is no longer rejected while the store cannot be written.
- One message is taken back when its intake fails, not the whole book: pushes under way for other messages are not touched.
- Ended messages wait on disk (`pending_history`) until the history store has confirmed them; the history is written at the hourly round, at a reload and at a start, no longer up to five minutes later. Entries of the same generation replace each other instead of doubling. The page, `list` and "delivered today" show the pending history right after a start.
- A history store that cannot be written gets its own repair issue ("message history not writable", a warning): "Ready" stays on, messages are still delivered, and at most 1000 ended messages wait in the working store; beyond that the oldest are dropped, logged as a number.
- A damaged entry in `pending_history` or the history is reported as "store not readable" with the reason and a retry, instead of blocking the start for good.
- The page reports `not_ready` instead of `unknown_error` while the store cannot be written.

**Delivery cycle**

- "Sending" and the reserved recipients are on disk *before* the first push leaves, so a restart in between gives "unclear" and never a second push. This was true for retries only.
- **Contract change:** the retry plan is by time: 1, 5 and 15 minutes after the first failure of a recipient, then hourly; the next try is the next plan time after now, `attempts` only counts, and the recipient is given up when no plan time is left before 24 hours.
- **Contract change:** retries respect the delivery rules. While a rule holds the priority, a due retry waits for the rule's end and goes out then (or at the maximum duration, or at a start, or when the rule is removed); the message stays "retrying" with the rule as its reason and no `next_try`. "Do not hold" and priority 3 go through; so does the same message arriving again with priority 3 or "do not hold". A rule that discards ends the cycle before the retry: "delivered" with `failed_recipients` if a phone already has the message, otherwise "discarded" (`rule_discarded`); a discarding rule whose entity is unknown only holds a retry.
- Expiry and the maximum wait of 7 days apply to a retrying message, before each try and in the timer; partly delivered ends as "delivered" with `failed_recipients`.
- A running retry is not started twice; a cancelled one (shutdown) is due again. Per recipient only one replacement at a time; a changed text or counter is sent afterwards; a failed replacement is not repeated by itself.
- Caller data that no push can be built from (`actions` that is not a list) count as a failed attempt with the error class, instead of a loop every second. The loop after an expiry is gone too.
- Due retries go out with the first evaluation after a start. A call cancelled while the center writes (automation in mode `restart`) is not accepted.
- *Send now* on the page also works for a message in "retrying": the recipients that do not have it yet are tried at once, whether a rule held the retry back or its plan time lies ahead; the ones that have it keep it.

**Rights, context and feedback**

- **Contract change:** `message_center.discard`, `snooze` and `forward` need the right to control an entity of Message Center (Home Assistant's own check): administrators, users and calls without a user (automations) pass, a user of the group "read only" gets `Unauthorized`. `notify`, `send` and `list` are unchanged. The push buttons do not check: they count as the right of the recipient the administrator chose.
- **Contract change:** the events `message_center_discarded` and `message_center_snoozed` run in the context of whoever intervened (action, page or phone) and carry `user_id`; the logbook shows that user.
- **Contract change:** light commands run in the context of whoever caused them (the sender for the light pulse and the alarm light, the person at the switch "Alarm", the administrator at a test button); Home Assistant checks the right to the lamps. Without the right, or with a deleted user, the lamps stay as they are and the push goes out; new note `light_failed` under the message, a warning in the log. The alarm loop ends at once instead of warning at every step; a refused domain in the first step restores what was switched. A second alarm start only extends the running one.
- **Contract change, depth 1:** a message that arrives under a context of one of the center's own effects (effect script, forward script, light pulse, alarm light, test button) or a child of it is delivered, on the alarm channel too, but starts no effect script (`script_skipped`), no light pulse and no alarm light (`light_skipped`, "message from an own effect"). The forward script runs under a context of the center below the caller's, so every answer of the assistant through the center is delivered and stops there. The same message arriving from outside again loses the mark. Stored as `from_effect`.
- The test buttons run in the administrator's context (was an empty context).

**Message id, logs, store format**

- **Contract change:** `message_id` is an opaque string of 16 hexadecimal characters (a salted hash of origin and key), stable over generations and restarts, without `:` or `|`, everywhere: responses, attributes, events, script variables, push `tag`, button ids, page. The form `origin:key` is gone; `snooze`, `forward` and the page answer `not_found` for it, `discard` answers `discarded: 0` (`discard` with `origin` and `title` stays). **Transition until 0.12:** the buttons on pushes delivered before the update still understand the old id. A message delivered before the update keeps its old `tag` on the phone, so its first repeat after the update appears once next to the old push instead of replacing it.
- **Contract change:** the option "keep titles out of history and attributes" now holds everywhere: attributes, events, the logbook (also for a forward), push `tag` and button ids carry no title. The event `message_center_forwarded` carries `display_title` (the title as the attributes show it); `title` and `message` stay real.
- **Store format 2** for `message_center.messages`: a salt `id_salt`, messages and spacing keyed by the new id, an `id` on every message. The migration from version 1 runs once at the first start. Version 0.10.5 refuses a version 2 store as "store not readable". The way back is a backup of **both** `.storage/message_center.messages` and `.storage/message_center.history`, restored together; with a new salt the history keeps its old ids. The history store stays at version 1; old entries without an id load and get theirs when read.
- Strict loading: a version 2 store without its salt, a message without or with a foreign id, a pending entry without a matching id are "store not readable" with the reason and a retry.
- Logs contain error classes and fixed names only, never a title, text, note or id: "Script ‹entity› (‹purpose›) failed: ‹class›", "Unexpected error pushing to ‹action›: ‹class›" with a trace without the text, "Push button ‹kind› ignored: ‹class›", "Message store not writable" / "writable again", "History store not writable" / "writable again", "Pending history at its limit of N entries: M oldest dropped", "Light pulse refused: no right to […]", "Alarm light refused …", "Alarm light not restored …". Task names carry no id.
- `services.yaml`: the example id for `discard` is `3c9f1e2d4b5a6978`.

**Page and small things**

- **Contract change:** on a priority 3 push with an alarm light, "End alarm" stands third at the latest: the caller's own buttons first, then "Later" (first, then second duration), then "To assistant", then "End alarm" moved up to the third place. Nothing is removed; Android shows three, the iPhone all. With a second "Later" duration the iPhone now gets "To assistant" on an alarm too.
- The search shows for hits in files only the file, the line number and the action names found in that line, no longer the line itself (it may hold a token). Titles and first lines of automations appear as Home Assistant loaded them (`!secret` and blueprint inputs filled in).
- A stopped center (reload, disable) writes, schedules and starts nothing more and causes no effect. A push under way at a reload reaches the phone but is not recorded: the new center shows "unclear". A caller that reached the old center too late is rejected with `not_ready` instead of a silent "accepted".
- A delivery rule follows its entity even when it changes during the first write at a start.
- The page shows *send now* for a message in "retrying"; while a rule holds the retry the summary shows no next try. New page texts for `light_failed`, `script_skipped` and "message from an own effect". The preview data of the page are neutral examples.

**Documentation**

- **Contract change:** the response of `message_center.send` has a third value, `action: "bundled"`: the message was already delivered and its spacing is still running; counter up, push replaced, no new push cycle. The code returned it since 0.1; the README did not name it.
- **Contract change:** `invalid_field` is the rejection of an unknown kind in `send` only. Wrong fields (missing, empty, too long, not storable) are Home Assistant's schema error "Invalid data" before the center runs, for `notify.message_center` too, which never raised `invalid_field`; in a script `continue_on_error` does not cover it.
- README: `message_id`, a "Rights" line per action, the meaning of the three `action` values, the button order, depth 1, the retry plan under rules, the store behaviour, the new repair issue, what the Companion App reports (its action gives up after 10 seconds itself and only logs, so the center's own 15-second limit is practically never reached and an offline phone is not seen unless it is registered for local push alone), the recorder keeping `message_center_forwarded` and `mobile_app_notification_action` with text and note and how to exclude them, the update to 0.11 and the way back. German guides updated to match; the maintenance guide gains the log lines, the manual check of the author addresses before a release and the backup before the update.
- Service descriptions: extra data must be storable as JSON; the interventions name the right they need.
- Blueprint "send with fallback" unchanged since 0.10.5.
- Quality scale self-assessment against the code of 0.11.0.
- 355 tests.

## 0.10.5 (2026-10-01)

Found by setting the integration up in a fresh Home Assistant:

- Fixed: the setup dialog could be sent without any recipient; every message then failed at once. The dialog and "Reconfigure" now ask for at least one.
- Removing the integration now deletes its stored messages and history. Until now the files with the message texts stayed in `.storage`.
- The search no longer reports a script made from the own blueprint as "still sends directly".
- Texts: the setup dialog no longer mentions limits that do not exist; the error for priority 3 through `send` points to the settings tab.
- The overview shows "operation" as faulty when there is no recipient.
- 153 tests.

## 0.10.4 (2026-10-01)

- Blueprint "send with fallback": the plain push to the fallback target no longer holds up the sender. It runs as a separate run of the script, so a phone that hangs, fails or no longer exists cannot delay the sender or turn the fallback into an error.
- Blueprint: `message_center.send` is only called while "Ready" is on. Without the integration the script now falls back instead of failing with "action not found".
- Existing installations keep their blueprint file (it is never overwritten). To get the new one, delete `blueprints/script/message_center/nachricht_senden.yaml` and restart Home Assistant.
- Five more tests for the blueprint (150 tests).

## 0.10.3 (2026-10-01)

- Fixed: when the store could not be written, the entity "Ready" stayed on until the next change (up to an hour), although messages were already rejected. It now turns off at once.
- A store that cannot be read, or has an unexpected format, no longer ends the setup with a generic error: Home Assistant shows the reason and tries again.
- An unwritable store is logged once, and once more when it works again, instead of on every failed write.
- The notification shown while deliveries fail follows the language of the system (German or English).
- The error for a full store names the remedy that exists: discard messages or send held ones now.
- The setup dialog explains the field "Recipients".
- Icons for all entities and actions (`icons.json`).
- `PARALLEL_UPDATES` is set in all four platforms.
- Tests: logbook texts, push data for Android and iOS, error classes of a push, the spoken alarm, finding the phones, a script started by an automation as origin, the sender's context after a restart, an unreadable and an unwritable store, a failing fallback push in the blueprint. 145 tests, 96 % coverage.
- Removed two unused helper functions. Test data uses invented names only.

## 0.10.2 (2026-10-01)

- Brand images: the logo in Home Assistant blue with the three priority dots as `brand/icon.png` and `brand/icon@2x.png`. Home Assistant (2026.3 and newer) and HACS show it for the integration; no entry in the brands repository is needed.
- Documentation: README with purpose, installation, settings, all interfaces with their contracts, dependencies, limits, data and troubleshooting; German user guide (`docs/bedienhilfe.md`) and maintenance guide (`docs/pflegeanleitung.md`).
- Changelog split by version.
- Quality scale self-assessment brought up to date with the code.
- No change in behaviour.

## 0.10.1 (2026-10-01)

- Search: a long first line of a text is a sentence, not a headline, and is no longer suggested as a title.

## 0.10.0 (2026-10-01)

- **Search Home Assistant.** A button on the message kinds tab searches the loaded automations and scripts (also from YAML packages and blueprints, at any nesting depth) and the text files of the configuration directory for notifying calls. The list names every place that still sends directly, with file and line, the target, the title or first line and what to change, and offers a message kind for it. Read-only, on request, nothing stored, administrators only.

## 0.9.2 (2026-10-01)

- Below 920 px the seven tabs show icons only, with the name of the active tab in a line below.

## 0.9.1 (2026-10-01)

- The logo appears in Home Assistant's sidebar. The sidebar only takes icon names, so the integration lets the frontend load a small module that registers the icon set `message-center`.
- Shorter tagline in the head of the page.

## 0.9.0 (2026-10-01)

- New look of the page: the head is a speech bubble like the logo, which carries three dots in the priority colours; tabs with icon and name; the overview groups its numbers into "now" and "operation"; open and history are a compact table whose rows unfold; kinds have a grip for dragging; rules show the effect per priority as three fields; priority 1 is blue everywhere; own line icons; narrow layout via container queries.

## 0.8.0 (2026-10-01)

- Own logo (a house that is also a speech bubble, by poritz69) and a head band with title and tagline.
- The overview shows a looping picture of a message's way through the center; it can be paused and respects reduced motion.

## 0.7.2 (2026-10-01)

- Fixed: the introduction could not be hidden when an option of an older version was still stored. The page now sends only the option it changes, and the server drops options that no longer exist.

## 0.7.1 (2026-10-01)

- A short explanation at the top of the tabs Open, History, Message kinds, Delivery rules and Settings.
- A kind can be dragged into another group (mouse only).

## 0.7.0 (2026-10-01)

- Scripts: a script per priority runs at the first delivery of a push cycle (options `effect_script_1` to `effect_script_3`), and a script can run whenever a message is forwarded (`forward_script`). They receive `message_id`, `title`, `text`, `note`, `origin`, `origin_name`, `kind`, `group`, `priority` and `count`; the outcome is noted under the message.
- Events `message_center_discarded` and `message_center_snoozed`; discarding, snoozing and forwarding appear in the logbook, without text. The event `message_center_forwarded` carries `source`.
- Sensor "Last delivery": the attribute is `origin` (was `sender`).
- Light pulse: chosen lights and switches can pulse even when they are off (on, then off again; option `lights_always`).
- Page: the rule form offers the known states of the entity; the history can be filtered by kind; the recipients tab shows the last error per phone; kinds that tie are marked.

## 0.6.2 (2026-10-01)

- The Android alarm channel is an option (`alarm_channel`): the alarm stream with the device's alarm tone, the same at full volume, or an own channel `message_center_alarm` whose sound and do-not-disturb exception are set in Android.
- Option `alarm_tts`: a spoken push ("Alarm: ‹title›") at full alarm volume on Android phones.
- Hint on the page: for Philips Hue choose single lights, not rooms or zones.

## 0.6.1 (2026-10-01)

- A repeat within the kind's spacing now replaces the push audibly, with the counter in the title ("2x Title"); the subtitle "2x since …" is gone. Replacing silently is the option `silent_repeat` (default off).
- Alarm light: default interval 1000 ms, light commands without transition, one settling second before the previous states are restored.

## 0.6.0 (2026-10-01)

- **Alarm light for priority 3:** an own list of lights and switches all go on, then toggle in step until the alarm is ended by the button "End alarm" on the push, the new switch "Alarm" on the device, the bar on the page, or the maximum duration. Afterwards everything returns to its previous state. The test button runs it for the test duration.
- Android alarm pushes use the Companion App's alarm stream (alarm volume, breaks through do not disturb).

## 0.5.0 (2026-09-30)

- **Script blueprint "Message Center: Nachricht senden (mit Rückfall)"**, copied to `blueprints/script/message_center/` on setup and never overwritten: sends through `message_center.send`; if the center is not ready or rejects, a Home Assistant notification plus a plain push to the optional fallback target (`mobile_app_*` only). Response `result: accepted | fallback`.
- Diagnostics download without texts, notes, extra push data or user ids.
- Introduction card on the overview; it can be hidden and shown again.
- Phones are found through the Mobile App config entries instead of a deprecated device registry mapping.

## 0.4.1 (2026-09-30)

- The off time of the light pulse is given in milliseconds (`pulse_ms`, 100–10 000, default 500).

## 0.4.0 (2026-09-30)

- A **Test** button per priority on the settings tab sends a test push to all recipients, without record, history or buttons.
- The minimum spacing between light pulses is an option (`light_spacing`, seconds, default 0 = none; it was fixed at 60 s).

## 0.3.5 (2026-09-30)

- The length of the light pulse is an option; a pulse that was skipped (spacing, no light on) is noted under the message.

## 0.3.4 (2026-09-30)

- Light pulse without the blink effect: what is on goes off for a moment and on again, which restores the previous state. Lights of different makes rendered `blink` differently.

## 0.3.3 (2026-09-30)

- Every message keeps a short list of interventions and effects (snoozed, forwarded, discarded, sent now, light pulse) with time and source; the page shows it under the message.

## 0.3.2 (2026-09-30)

- "Later" is a one-tap button with a fixed duration (`snooze_minutes`), optionally a second one (`snooze_minutes_2`); typed minutes remain available (`snooze_input`).

## 0.3.1 (2026-09-30)

- The two push buttons can be turned off separately (`button_snooze`, `button_forward`).
- Switches can be light pulse targets, too.

## 0.3.0 (2026-09-30)

- **Light pulse:** priority 2 messages, or kinds set to "always", pulse the chosen lights once per push cycle; a failing light never touches the push. Switch "Light pulse" on the device.
- **Buttons on the push:** "Later" (snooze) and "To assistant" (forward with an optional note), handled in the context of the user of the phone; the caller's own buttons stay.

## 0.2.0 (2026-09-30)

- Page: settings tab ("priority → effect", history days, sidebar entry, hide titles, allow alarm through `send`), applied without a restart.
- Page: recipients are chosen on the recipients tab; changes apply live.
- Page: pairs under "New, please classify" can be dismissed; they return when the message arrives again.

## 0.1.1 to 0.1.5 (2026-09-30)

- Page: one tab "Message kinds" shows the groups as cards with their kinds; a group can be created from the kind form; a new kind takes its group's defaults.
- Page fixes for the current Home Assistant frontend (`ha-button`, the new `ha-dialog`), typed values survive re-renders, rows wrap on narrow screens.
- "Last delivery" and "delivered today" are rebuilt from the stores after a restart.

## 0.1.0 (2026-09-29 to 2026-09-30)

- Automations call `notify.message_center` with title, text and extra data only. The center resolves the origin automation from the call context, assigns a message kind (config subentries `kind` and `group`), lists unknown origin/title pairs as "new", bundles repeats with a counter and never deletes from phones.
- Actions `send` (with `kind`, `priority`, `key`), `discard`, `snooze`, `forward` and `list` (administrators only), with validation, error codes and responses.
- Message state machine, delivery rules with hold phases and maximum duration, a working store with a 5 s write limit and a history store.
- Delivery to `notify.mobile_app_*` with tag, group, channel and alarm data for priority 3; replacement on changed text; retries after 1, 5 and 15 minutes, then hourly for 24 hours, per recipient.
- Entities Ready, Open, Disturbed, New, Active rules, Last delivery and the event entity Delivered; event `message_center_delivered`; logbook entries.
- Repair issues for an unwritable store, a full store, unclear messages after a restart, an unreadable rule entity, an exceeded maximum duration and an unreachable recipient; a persistent notification while deliveries fail.
- Sidebar page "Message Center" (custom panel, administrators only), built from TypeScript and Lit with esbuild; the bundle ships in the integration.
- Config flow picks the Companion App devices; reconfigure changes them. Only one instance.
- Minimum Home Assistant version 2026.9.0 (`hacs.json`). Translations in English and German. Apache License 2.0. Tests and CI against the minimum and the current Home Assistant version; lint and formatting with ruff.
