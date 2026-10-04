// Tests of the notes the search over the house shows for a call: a call
// without a title is called after its automation, so it needs no title
// unless the automation sends several messages. Run with "npm test".
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
