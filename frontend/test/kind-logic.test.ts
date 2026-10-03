// Tests of the kind dialog's logic: the sentence on top, how the dialog
// starts from "New", the search or an existing kind, the list of possible
// messages, the double condition and the question before saving.
// Run with "npm test" (bundled by esbuild, run by node --test).
import { test } from "node:test";
import assert from "node:assert/strict";
import { makeT, tables } from "../src/i18n";
import {
  appliesTo, conditionComplete, conditionLabel, counted, duplicateIn, duplicateOf, forOrigin, kindPayload, landsInNew, modeOptions,
  possibleMessages, probeOf, startState, type Condition,
} from "../src/kind-logic";
import type { Kind, KindMatches, OriginMessages, ScanItem, UnknownItem } from "../src/types";

const de = makeT("de");
const en = makeT("en");

const WASH = "automation.waschmaschine";
const names: Record<string, string> = {
  [WASH]: "Waschmaschine", "automation.raumklima": "Raumklima", "script.melden": "Melden",
  "automation.washing": "Washing machine",
};
const nameOf = (id: string) => names[id] ?? null;
const cond = (origin: string, title_mode: Condition["title_mode"], title_value = ""): Condition => ({ origin, title_mode, title_value });

const unknownItem = (o: Partial<UnknownItem> = {}): UnknownItem => ({
  origin: WASH, origin_name: "Waschmaschine", labels: [], title: "Wäsche fertig", count: 2,
  first_seen: "2026-10-01T08:00:00+00:00", last_seen: "2026-10-01T09:00:00+00:00", multiple: false, ...o,
});

const scanItem = (o: Partial<ScanItem> = {}): ScanItem => ({
  source: "automation", entity_id: WASH, name: "Waschmaschine", origin: WASH, blueprint: null, edit_url: null,
  service: "notify.mobile_app_alex", target: "notify.mobile_app_alex", status: "direct", title: "Wäsche fertig",
  title_template: false, first_line: null, suggestion: { mode: "any" }, multiple: false, file: "automations.yaml", line: 3,
  kind: null, ...o,
});

const kind = (o: Partial<Kind> = {}): Kind => ({
  id: "k1", name: "Fenster offen", origin: "automation.fenster", title_mode: "exact", title_value: "Fenster offen",
  group_id: null, priority: 1, no_hold: false, spacing: 0, expires_after: 0, light: null, active: true, ties: [], orphan: false, ...o,
});

const om = (o: Partial<OriginMessages> = {}): OriginMessages => ({
  source: "config", messages: [{ title: "Wäsche fertig", template: false, display: "Wäsche fertig" }],
  seen_titles: [], multiple: false, any_allowed: true, ...o,
});

const several = om({
  messages: [
    { title: "Fenster offen", template: false, display: "Fenster offen" },
    { title: "Raum {{ raum }}: lüften", template: true, display: "Raum …: lüften" },
    { title: null, template: false, display: "Raumklima" },
  ],
  seen_titles: ["Raum Bad: lüften", "fenster offen"],
  multiple: true,
});

// ----- the sentence on top ---------------------------------------------------------

test("the sentence names origin and condition in German", () => {
  assert.equal(appliesTo(de, cond(WASH, "any"), nameOf), "Gilt für: alle Meldungen der Automation „Waschmaschine“");
  assert.equal(appliesTo(de, cond(WASH, "exact", "Wäsche fertig"), nameOf),
    "Gilt für: Meldungen der Automation „Waschmaschine“ mit dem Titel „Wäsche fertig“");
  assert.equal(appliesTo(de, cond("automation.raumklima", "prefix", "Raum"), nameOf),
    "Gilt für: Meldungen der Automation „Raumklima“, deren Titel mit „Raum“ beginnt");
  assert.equal(appliesTo(de, cond("", "contains", "Frost"), nameOf),
    "Gilt für: Meldungen jeder Herkunft, deren Titel „Frost“ enthält");
  assert.equal(appliesTo(de, cond("", "exact", "Akku leer"), nameOf), "Gilt für: Meldungen jeder Herkunft mit dem Titel „Akku leer“");
  assert.equal(appliesTo(de, cond("script.melden", "any"), nameOf), "Gilt für: alle Meldungen des Skripts „Melden“");
  assert.equal(appliesTo(de, cond("unknown", "exact", "Test"), nameOf), "Gilt für: Meldungen unbekannter Herkunft mit dem Titel „Test“");
  // without a known name the entity id stands in
  assert.equal(appliesTo(de, cond("automation.weg", "any"), nameOf), "Gilt für: alle Meldungen der Automation „automation.weg“");
});

test("the sentence in English", () => {
  assert.equal(appliesTo(en, cond("automation.washing", "any"), nameOf), "Applies to: all messages of the automation “Washing machine”");
  assert.equal(appliesTo(en, cond("", "exact", "Battery low"), nameOf), "Applies to: messages from any origin titled “Battery low”");
  assert.equal(appliesTo(en, cond("automation.washing", "prefix", "Room"), nameOf),
    "Applies to: messages of the automation “Washing machine” whose title starts with “Room”");
  assert.equal(appliesTo(en, cond("", "contains", "Frost"), nameOf), "Applies to: messages from any origin whose title contains “Frost”");
});

test("an incomplete condition says so", () => {
  for (const c of [cond("", "any"), cond("unknown", "any"), cond(WASH, "exact", "  ")]) {
    assert.equal(conditionComplete(c), false);
    assert.equal(appliesTo(de, c, nameOf), "Gilt für: noch nichts – bitte die Bedingung ausfüllen");
  }
  assert.equal(appliesTo(en, cond("", "any"), nameOf), "Applies to: nothing yet – please fill in the condition");
  assert.equal(conditionComplete(cond(WASH, "any")), true);
  assert.equal(conditionComplete(cond("", "prefix", "Raum")), true);
});

test("the condition in the list of kinds", () => {
  assert.equal(conditionLabel(de, "any", ""), "alle Meldungen dieser Automation");
  assert.equal(conditionLabel(de, "exact", "Fenster offen"), "genau „Fenster offen“");
  assert.equal(conditionLabel(en, "prefix", "Room"), "starts with “Room”");
  assert.equal(conditionLabel(en, "any", ""), "all messages of this automation");
  // a script is called a script
  assert.equal(conditionLabel(de, "any", "", "script.melden"), "alle Meldungen dieses Skripts");
  assert.equal(conditionLabel(en, "any", "", "script.melden"), "all messages of this script");
  assert.equal(conditionLabel(de, "any", "", WASH), "alle Meldungen dieser Automation");
});

// ----- how the dialog starts ---------------------------------------------------------

test("from New: an automation with one message gets all its messages, locked", () => {
  const s = startState({ from: "new", item: unknownItem() }, om());
  // the message's title is kept for a switch to another comparison; "any" does not use it
  assert.deepEqual(s.condition, cond(WASH, "any", "Wäsche fertig"));
  assert.equal(conditionLabel(de, s.condition.title_mode, s.condition.title_value), "alle Meldungen dieser Automation");
  assert.equal(appliesTo(de, s.condition, nameOf), "Gilt für: alle Meldungen der Automation „Waschmaschine“");
  assert.equal(s.locked, true);
  assert.equal(s.titleOpen, false);
  assert.equal(s.multiple, false);
  assert.equal(s.name, "Wäsche fertig");
});

test("from New: an automation with several messages opens the title with the message's title", () => {
  const s = startState({ from: "new", item: unknownItem({ origin: "automation.raumklima", title: "Raum Bad: lüften", multiple: true }) }, several);
  assert.deepEqual(s.condition, cond("automation.raumklima", "exact", "Raum Bad: lüften"));
  assert.equal(s.locked, true);
  assert.equal(s.titleOpen, true);
  assert.equal(s.multiple, true);
});

test("from New: the answer about the automation wins over the flag of the entry", () => {
  // the entry still says one message, the automation now sends several
  const s = startState({ from: "new", item: unknownItem({ multiple: false }) }, several);
  assert.equal(s.multiple, true);
  assert.equal(s.condition.title_mode, "exact");
  // until the answer is there the entry's flag decides
  const early = startState({ from: "new", item: unknownItem({ multiple: true }) });
  assert.equal(early.multiple, true);
  assert.equal(early.titleOpen, true);
});

test("from New: an unknown origin cannot have all its messages", () => {
  const s = startState({ from: "new", item: unknownItem({ origin: "unknown", origin_name: null, title: "Akku leer" }) },
    om({ source: "none", messages: [], any_allowed: false }));
  assert.deepEqual(s.condition, cond("", "exact", "Akku leer"));
  assert.equal(s.locked, true);
  assert.equal(s.titleOpen, false);
  assert.equal(s.multiple, false);
});

test("from the search: the suggestion of the found call", () => {
  const one = startState({ from: "scan", item: scanItem() }, om());
  assert.deepEqual(one.condition, cond(WASH, "any", "Wäsche fertig"));
  const computed = startState({ from: "scan", item: scanItem({ title: "{{ x }} fertig", title_template: true }) }, om());
  assert.deepEqual(computed.condition, cond(WASH, "any"));
  assert.equal(one.locked, true);
  assert.equal(one.titleOpen, false);
  assert.equal(one.name, "Wäsche fertig");

  const many = startState({ from: "scan", item: scanItem({ origin: "automation.raumklima", name: "Raumklima", title: "Raum {{ raum }}: lüften",
    title_template: true, suggestion: { mode: "prefix", value: "Raum" }, multiple: true }) }, several);
  assert.deepEqual(many.condition, cond("automation.raumklima", "prefix", "Raum"));
  assert.equal(many.titleOpen, true);
  assert.equal(many.multiple, true);
  assert.equal(many.name, "Raum");

  // a script has no origin of its own: its title decides, for any origin
  const script = startState({ from: "scan", item: scanItem({ source: "script", entity_id: "script.melden", name: "Melden", origin: null,
    title: "Akku leer", suggestion: { mode: "exact", value: "Akku leer" } }) });
  assert.deepEqual(script.condition, cond("", "exact", "Akku leer"));
  assert.equal(script.locked, true);
  assert.equal(script.titleOpen, false);

  // nothing to suggest: the title has to be filled in
  const free = startState({ from: "scan", item: scanItem({ origin: "automation.raumklima", name: "Raumklima", title: "{{ titel }}",
    title_template: true, suggestion: null, multiple: true }) }, several);
  assert.deepEqual(free.condition, cond("automation.raumklima", "exact", ""));
  assert.equal(free.titleOpen, true);
  assert.equal(free.name, "Raumklima");
});

test("editing a kind of an automation with one message puts it on all its messages, locked", () => {
  const sicherung = kind({ id: "k4", name: "Sicherung", origin: "automation.sicherung", title_mode: "prefix", title_value: "Sicherung" });
  const one = om({ messages: [{ title: "Sicherung abgeschlossen", template: false, display: "Sicherung abgeschlossen" }] });
  const s = startState({ from: "edit", kind: sicherung }, one, [sicherung]);
  // the old text waits in the condition for a switch back to another comparison; "any" does not use it
  assert.deepEqual(s.condition, cond("automation.sicherung", "any", "Sicherung"));
  assert.equal(appliesTo(de, s.condition, () => "Sicherung"), "Gilt für: alle Meldungen der Automation „Sicherung“");
  assert.equal(s.locked, true);
  assert.equal(s.titleOpen, false);
  assert.equal(s.multiple, false);
  assert.equal(s.switched, true);
  assert.equal(s.name, "Sicherung");
  assert.equal(kindPayload({ name: "Sicherung" }, s.condition, null).title_value, "");

  // until the answer about the automation is there, the kind keeps its condition
  const early = startState({ from: "edit", kind: sicherung });
  assert.deepEqual(early.condition, cond("automation.sicherung", "prefix", "Sicherung"));
  assert.equal(early.switched, false);
});

test("editing keeps the kind's condition when the automation sends several messages, or nothing is known", () => {
  const plain = startState({ from: "edit", kind: kind() }, several, [kind()]);
  assert.deepEqual(plain.condition, cond("automation.fenster", "exact", "Fenster offen"));
  assert.equal(plain.locked, true);
  assert.equal(plain.multiple, true);
  assert.equal(plain.titleOpen, true);
  assert.equal(plain.switched, false);
  assert.equal(plain.name, "Fenster offen");

  const all = startState({ from: "edit", kind: kind({ title_mode: "any", title_value: "" }) }, several);
  assert.deepEqual(all.condition, cond("automation.fenster", "any"));
  assert.equal(all.multiple, true);
  assert.equal(all.titleOpen, false);
  assert.equal(all.switched, false);

  // already all messages: nothing to switch
  const already = startState({ from: "edit", kind: kind({ title_mode: "any", title_value: "" }) }, om());
  assert.equal(already.switched, false);
  assert.equal(already.titleOpen, false);

  // nothing known about the automation: it may send one message or several
  const unknownCount = startState({ from: "edit", kind: kind() }, om({ source: "none", messages: [] }));
  assert.deepEqual(unknownCount.condition, cond("automation.fenster", "exact", "Fenster offen"));
  assert.equal(unknownCount.switched, false);

  // an orphaned kind is left as it is
  const orphan = startState({ from: "edit", kind: kind({ orphan: true }) }, om({ source: "seen", messages: [], seen_titles: ["Fenster offen"] }));
  assert.equal(orphan.condition.title_mode, "exact");
  assert.equal(orphan.switched, false);

  // any origin, or an unknown one, cannot have all its messages
  const anyOrigin = startState({ from: "edit", kind: kind({ origin: null }) });
  assert.equal(anyOrigin.condition.origin, "");
  const unknownOrigin = startState({ from: "edit", kind: kind({ origin: "unknown" }) }, om({ any_allowed: false, source: "none", messages: [] }));
  assert.equal(unknownOrigin.condition.title_mode, "exact");
  assert.equal(unknownOrigin.switched, false);
});

test("editing does not switch to a condition another kind already has", () => {
  const exact = kind({ id: "k1", name: "Fenster offen" });
  const allOfIt = kind({ id: "k2", name: "Fenster alles", title_mode: "any", title_value: "", active: false });
  const s = startState({ from: "edit", kind: exact }, om(), [exact, allOfIt]);
  assert.deepEqual(s.condition, cond("automation.fenster", "exact", "Fenster offen"));
  assert.equal(s.switched, false);
});

test("a new kind without a template starts with open fields", () => {
  const s = startState({ from: "blank" });
  assert.deepEqual(s.condition, cond("", "exact", ""));
  assert.equal(s.locked, false);
  assert.equal(s.name, "");
});

// ----- possible messages, comparisons -------------------------------------------------

test("the possible messages: fixed, computed with a placeholder, arrived", () => {
  const list = possibleMessages(several);
  assert.deepEqual(list.map((p) => [p.label, p.tag]), [
    ["Fenster offen", "fixed"],
    ["Raum …: lüften", "computed"],
    ["Raumklima", "fixed"],
    ["Raum Bad: lüften", "seen"],
  ]);
  // a fixed title as it is, a computed one by its fixed beginning, without a title the automation's name
  assert.deepEqual(list.map((p) => p.apply), [
    { title_mode: "exact", title_value: "Fenster offen" },
    { title_mode: "prefix", title_value: "Raum" },
    { title_mode: "exact", title_value: "Raumklima" },
    { title_mode: "exact", title_value: "Raum Bad: lüften" },
  ]);
});

test("a computed title without a fixed beginning offers its longest fixed part, or nothing", () => {
  const list = possibleMessages(om({ messages: [
    { title: "{{ wer }} ist angekommen", template: true, display: "… ist angekommen" },
    { title: "{{ x }}", template: true, display: "…" },
  ], multiple: true }));
  assert.deepEqual(list.map((p) => p.apply), [{ title_mode: "contains", title_value: "ist angekommen" }, null]);
});

test("all messages of this automation needs an automation or a script as origin", () => {
  assert.deepEqual(modeOptions(de, "").map((o) => o.value), ["exact", "prefix", "contains"]);
  assert.deepEqual(modeOptions(de, "unknown").map((o) => o.value), ["exact", "prefix", "contains"]);
  assert.deepEqual(modeOptions(de, WASH).map((o) => o.value), ["exact", "prefix", "contains", "any"]);
  assert.equal(modeOptions(de, WASH)[3].label, "alle Meldungen dieser Automation");
  assert.equal(modeOptions(de, "script.melden")[3].label, "alle Meldungen dieses Skripts");
  assert.equal(modeOptions(en, "script.melden")[3].label, "all messages of this script");
});

// ----- saving ----------------------------------------------------------------------------

test("the payload of a kind", () => {
  const data = { name: "Wäsche", priority: "2", no_hold: true, spacing: 5, expires_after: 0, light: "on", active: true };
  assert.deepEqual(kindPayload(data, cond(WASH, "any", "Wäsche fertig"), "g1"), {
    name: "Wäsche", origin: WASH, title_mode: "any", title_value: "", group_id: "g1", priority: 2, no_hold: true,
    spacing: 5, expires_after: 0, light: true, active: true,
  });
  const free = kindPayload({ ...data, light: "auto", active: false }, cond("", "prefix", " Raum "), null);
  assert.equal(free.origin, null);
  assert.equal(free.title_value, "Raum");
  assert.equal(free.light, null);
  assert.equal(free.active, false);
});

test("the double condition is found on the page before anything is saved", () => {
  const kinds = [
    kind({ id: "k1", name: "Fenster offen" }),
    kind({ id: "k2", name: "Wäsche", origin: WASH, title_mode: "any", title_value: "" }),
    // an inactive kind counts as well
    kind({ id: "k3", name: "Straße", origin: null, title_mode: "contains", title_value: "Straße", active: false }),
  ];
  // same origin, comparison and text, case and spaces aside
  assert.deepEqual(duplicateIn(kinds, cond("automation.fenster", "exact", "  FENSTER offen ")), { kind_id: "k1", name: "Fenster offen" });
  // "all messages" has no text: whatever waits in the field does not count
  assert.deepEqual(duplicateIn(kinds, cond(WASH, "any", "Wäsche fertig")), { kind_id: "k2", name: "Wäsche" });
  // any origin is its own origin; "ß" and "SS" alike, as the center compares
  assert.deepEqual(duplicateIn(kinds, cond("", "contains", "STRASSE")), { kind_id: "k3", name: "Straße" });
  // the kind being edited is no double of itself
  assert.equal(duplicateIn(kinds, cond("automation.fenster", "exact", "Fenster offen"), "k1"), null);
  // another comparison, text or origin is no double
  assert.equal(duplicateIn(kinds, cond("automation.fenster", "prefix", "Fenster offen")), null);
  assert.equal(duplicateIn(kinds, cond("automation.fenster", "exact", "Fenster zu")), null);
  assert.equal(duplicateIn(kinds, cond("", "exact", "Fenster offen")), null);
  assert.equal(duplicateIn([], cond(WASH, "any")), null);
  // two kinds that already share a condition (an older version): one of them can still be saved unchanged
  const shared = [kind(), kind({ id: "k4", name: "Fenster offen (alt)" })];
  assert.equal(duplicateIn(shared, cond("automation.fenster", "exact", "Fenster offen"), "k1"), null);
  // but not be changed onto the condition of another kind
  assert.deepEqual(duplicateIn([...shared, kinds[1]], cond(WASH, "any"), "k1"), { kind_id: "k2", name: "Wäsche" });
});

test("the double condition is read from the error", () => {
  assert.deepEqual(duplicateOf({ code: "duplicate", message: "x", kind_id: "k7", name: "Wäsche" }), { kind_id: "k7", name: "Wäsche" });
  assert.equal(duplicateOf({ code: "invalid_format", message: "x" }), null);
  assert.equal(duplicateOf(new Error("x")), null);
  assert.equal(duplicateOf(undefined), null);
});

test("the original message is asked about only for a kind made from New", () => {
  const item = unknownItem();
  assert.deepEqual(probeOf({ from: "new", item }), { origin: WASH, title: "Wäsche fertig" });
  assert.equal(probeOf({ from: "blank" }), null);
  assert.equal(probeOf({ from: "edit", kind: kind() }), null);
  assert.equal(probeOf({ from: "scan", item: scanItem() }), null);
});

test("saving asks only when the original message would land in New again", () => {
  const answer = (probe: KindMatches["probe"]): KindMatches => ({
    valid: true, new: [], new_count: 0, seen: [], seen_count: 0, taken_count: 0, overlaps: [], overlap_count: 0, probe,
  });
  assert.equal(landsInNew(answer({ matches: false, taken_by: null })), true);
  assert.equal(landsInNew(answer({ matches: true, taken_by: null })), false);
  // another kind takes it: it does not land in New
  assert.equal(landsInNew(answer({ matches: false, taken_by: { kind_id: "k2", name: "Andere" } })), false);
  assert.equal(landsInNew(answer(null)), false);
  assert.equal(landsInNew(undefined), false);
});

// ----- texts ---------------------------------------------------------------------------

test("the hints have the agreed wording", () => {
  assert.equal(de("hint_multiple"), "Diese Automation sendet mehrere verschiedene Meldungen – bitte prüfen, für welche diese Meldungsart gilt.");
  assert.equal(de("hint_advanced"), "Herkunft und Titel dienen nur der Zuordnung. Normalerweise musst du hier nichts ändern – nur für Fortgeschrittene.");
  assert.equal(de("condition_edit"), "Bedingung bearbeiten (erweitert)");
  assert.equal(de("duplicate").replace("{name}", "Wäsche"), "Diese Bedingung hat schon „Wäsche“.");
  assert.equal(de("duplicate_edit"), "Vorhandene bearbeiten");
  assert.equal(de("confirm_lands_in_new").replace("{title}", "Wäsche fertig"),
    "Die Meldung „Wäsche fertig“ würde dann wieder unter „Neu“ landen. Trotzdem speichern?");
  assert.equal(de("matches_title"), "Diese Bedingung passt auf");
  assert.equal(de("matches_none"), "Passt auf keine bisherige Meldung.");
  assert.equal(de("from_new"), "Aus „Neu“ übernehmen");
  assert.equal(de("orphan"), "verwaist");
  assert.equal(de("any"), "alle Meldungen dieser Automation");
  assert.equal(de("title_mode"), "Vergleichsart");
  assert.equal(de("matches_incomplete"), "Erscheint, sobald die Bedingung vollständig ist.");
  // an overlap names the other kind once and says who gets the shared messages
  assert.equal(de("overlap").replace("{name}", "Wasseralarm").replace("{winner}", de("overlap_other")),
    "Passt auch auf Meldungen von „Wasseralarm“: sie bleiben dort");
  assert.equal(en("overlap").replace("{name}", "Water alarm").replace("{winner}", en("overlap_this")),
    "Also matches messages of “Water alarm”: this kind gets them");
});

test("one and several are told apart", () => {
  assert.equal(counted(de, "matches_taken", 1), "1 davon geht an eine andere Meldungsart, die Vorrang hat.");
  assert.equal(counted(de, "matches_taken", 3), "3 davon gehen an andere Meldungsarten, die Vorrang haben.");
  assert.equal(counted(en, "matches_taken", 1), "1 of them goes to another kind that takes precedence.");
  assert.equal(counted(en, "matches_taken", 2), "2 of them go to other kinds that take precedence.");
  assert.equal(counted(de, "overlap_more", 1), "… und 1 weitere solche Meldungsart");
  assert.equal(counted(de, "overlap_more", 4), "… und 4 weitere solche Meldungsarten");
  assert.equal(counted(en, "overlap_more", 1), "… and 1 more such kind");
  assert.equal(counted(en, "overlap_more", 4), "… and 4 more such kinds");
});

test("a script is called a script", () => {
  assert.equal(forOrigin(de, "hint_multiple", "script.melden"),
    "Dieses Skript sendet mehrere verschiedene Meldungen – bitte prüfen, für welche diese Meldungsart gilt.");
  assert.equal(forOrigin(de, "hint_multiple", WASH), de("hint_multiple"));
  assert.equal(forOrigin(de, "any_helper", "script.melden"), "Wird hier nicht gebraucht: Die Meldungsart gilt für jeden Titel dieses Skripts.");
  assert.equal(forOrigin(de, "any_helper", WASH), "Wird hier nicht gebraucht: Die Meldungsart gilt für jeden Titel dieser Automation.");
  assert.equal(forOrigin(de, "orphan_hint", "script.melden"), "Das Skript gibt es nicht mehr. Diese Meldungsart wirkt auf nichts und kann gelöscht werden.");
  assert.equal(forOrigin(en, "orphan_hint", "script.melden"), "The script no longer exists. This kind affects nothing and can be deleted.");
  assert.equal(forOrigin(de, "hint_one", "script.melden").startsWith("Dieses Skript sendet nur eine Meldung."), true);
  assert.equal(forOrigin(en, "hint_one", WASH).startsWith("This automation sends only one message."), true);
  // without an origin: the automation's wording
  assert.equal(forOrigin(en, "any", null), "all messages of this automation");
  // every text with a script variant has it in both languages
  for (const key of ["any", "any_helper", "hint_multiple", "hint_one", "orphan_hint"]) {
    assert.ok(tables.de[`${key}_script`] && tables.en[`${key}_script`], key);
  }
});

test("every text exists in German and English", () => {
  const deKeys = Object.keys(tables.de).sort();
  const enKeys = Object.keys(tables.en).sort();
  assert.deepEqual(deKeys.filter((k) => !enKeys.includes(k)), []);
  assert.deepEqual(enKeys.filter((k) => !deKeys.includes(k)), []);
  for (const lang of [tables.de, tables.en]) {
    for (const [key, text] of Object.entries(lang)) assert.ok(text.trim(), key);
  }
});
