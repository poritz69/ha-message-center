// Tests of the notes the search over the house shows for a call: a call
// without a title is called after its automation, so it needs no title
// unless the automation sends several messages; two or more calls without
// a title would replace each other, so each should get one. Run with "npm test".
import { test } from "node:test";
import assert from "node:assert/strict";
import { fill } from "../src/kind-logic";
import { makeT } from "../src/i18n";
import { scanNote } from "../src/scan-logic";
import type { ScanItem } from "../src/types";

const item = (o: Partial<ScanItem> = {}): ScanItem => ({
  source: "automation", entity_id: "automation.washing", name: "Washing machine", origin: "automation.washing", blueprint: null,
  edit_url: null, service: "notify.mobile_app_alex", target: "notify.mobile_app_alex", status: "direct", title: null,
  title_template: false, first_line: "The laundry is done", suggestion: { mode: "any" }, multiple: false, file: "automations.yaml",
  line: 3, kind: null, ...o,
});

test("a call without a title in an automation that sends one message needs no title", () => {
  assert.deepEqual(scanNote(item()), { key: "scan_untitled_one", name: "Washing machine" });
  // also once it goes through the center
  assert.deepEqual(scanNote(item({ status: "center" })), { key: "scan_untitled_one", name: "Washing machine" });
});

test("in an automation that sends several messages it should get a title of its own", () => {
  assert.deepEqual(scanNote(item({ multiple: true, suggestion: { mode: "exact", value: "Washing machine" } })),
    { key: "scan_untitled_many", name: "Washing machine" });
});

test("several calls without a title would replace each other: each should get a title, the first line suggested", () => {
  const clash = item({ multiple: true, untitled_clash: true, title_hint: "The laundry is done",
    suggestion: { mode: "exact", value: "Washing machine" } });
  assert.deepEqual(scanNote(clash), { key: "scan_untitled_clash", name: "Washing machine", line: "The laundry is done" });
  // without a fitting line (none, computed, too long, or the same as another call's) there is no example
  assert.deepEqual(scanNote({ ...clash, first_line: null, title_hint: null }), { key: "scan_untitled_clash_noline", name: "Washing machine" });
  assert.deepEqual(scanNote({ ...clash, first_line: "{% if is_state('binary_sensor.f', 'on') %}", title_hint: null }),
    { key: "scan_untitled_clash_noline", name: "Washing machine" });
  assert.deepEqual(scanNote({ ...clash, first_line: "{{ states('sensor.h') }} % humidity", title_hint: null }),
    { key: "scan_untitled_clash_noline", name: "Washing machine" });
  // the line itself is never taken as the example: only the center's hint
  assert.deepEqual(scanNote({ ...clash, title_hint: undefined }), { key: "scan_untitled_clash_noline", name: "Washing machine" });
  // in a script too
  assert.deepEqual(scanNote({ ...clash, source: "script", origin: null, suggestion: null, name: "Tell" }),
    { key: "scan_untitled_clash", name: "Tell", line: "The laundry is done" });
  // a call with a title in such an automation needs nothing
  assert.equal(scanNote({ ...clash, title: "Laundry done", suggestion: { mode: "exact", value: "Laundry done" } }), null);
});

test("the note on several calls without a title, in German and English", () => {
  const values = { name: "Feuchte Bad", line: "Feuchte im Bad hoch" };
  assert.equal(fill(makeT("de")("scan_untitled_clash"), values),
    "Mehrere Meldungen von „Feuchte Bad“ haben keinen eigenen Titel. Sie würden sich auf dem Handy gegenseitig ersetzen. "
    + "Gib diesem Aufruf einen eigenen Titel, zum Beispiel die erste Zeile seines Textes: „Feuchte im Bad hoch“. "
    + "Danach erneut suchen und für jeden neuen Titel eine Meldungsart anlegen.");
  assert.equal(fill(makeT("en")("scan_untitled_clash"), values),
    "Several messages of “Feuchte Bad” have no title of their own. They would replace each other on the phone. "
    + "Give this call a title of its own, for example the first line of its text: “Feuchte im Bad hoch”. "
    + "Then search again and add a message kind for each new title.");
  assert.equal(fill(makeT("de")("scan_untitled_clash_noline"), values),
    "Mehrere Meldungen von „Feuchte Bad“ haben keinen eigenen Titel. Sie würden sich auf dem Handy gegenseitig ersetzen. "
    + "Gib diesem Aufruf einen eigenen Titel. Danach erneut suchen und für jeden neuen Titel eine Meldungsart anlegen.");
  assert.equal(fill(makeT("en")("scan_untitled_clash_noline"), values),
    "Several messages of “Feuchte Bad” have no title of their own. They would replace each other on the phone. "
    + "Give this call a title of its own. Then search again and add a message kind for each new title.");
});

test("in a script it is called after the automation that starts the script", () => {
  assert.deepEqual(scanNote(item({ source: "script", entity_id: "script.tell", name: "Tell", origin: null, suggestion: null })),
    { key: "scan_untitled_script" });
});

test("in a script the note names the automation that starts it, or else the script", () => {
  // a script started by hand or from a dashboard is the origin itself
  assert.equal(makeT("de")("scan_untitled_script"),
    "Ohne Titel heißt die Meldung wie die Automation, die das Skript startet, sonst wie das Skript.");
  assert.equal(makeT("en")("scan_untitled_script"),
    "Without a title the message is called after the automation that starts the script, or else after the script.");
});

test("a computed title without a fixed beginning: the condition is up to the user", () => {
  assert.deepEqual(scanNote(item({ title: "{{ title }}", title_template: true, suggestion: null })), { key: "scan_title_computed" });
});

test("nothing to note for a title with a suggestion or a notification in the UI", () => {
  assert.equal(scanNote(item({ title: "Laundry done", suggestion: { mode: "any" } })), null);
  assert.equal(scanNote(item({ title: "Laundry done", multiple: true, suggestion: { mode: "exact", value: "Laundry done" } })), null);
  assert.equal(scanNote(item({ status: "persistent", suggestion: null })), null);
});

test("the notes no longer ask for the first line as a title", () => {
  const de = makeT("de");
  const en = makeT("en");
  assert.equal(fill(de("scan_untitled_one"), { name: "Waschmaschine" }),
    "Ohne Titel heißt die Meldung wie die Automation: „Waschmaschine“. Ein eigener Titel ist nicht nötig.");
  assert.equal(fill(en("scan_untitled_one"), { name: "Washing machine" }),
    "Without a title the message is called after the automation: “Washing machine”. It needs no title of its own.");
  assert.ok(de("scan_untitled_many").includes("{name}") && en("scan_untitled_many").includes("{name}"));
  for (const t of [de, en]) {
    assert.equal(t("scan_title_own"), "scan_title_own");
    assert.equal(t("scan_change_title"), "scan_change_title");
    assert.equal(t("scan_change_title_free"), "scan_change_title_free");
  }
});
