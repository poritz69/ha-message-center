// Tests of the delivery rule dialog's help on modes: a toggle created there
// is chosen for the rule at once, and the texts say that the page does not
// switch it. Run with "npm test".
import { test } from "node:test";
import assert from "node:assert/strict";
import { tables } from "../src/i18n";
import { ruleWithSwitch, switchEntityId } from "../src/rule-logic";

test("a created toggle has the entity id Home Assistant gives it", () => {
  assert.equal(switchEntityId({ id: "nachtruhe", name: "Nachtruhe" }), "input_boolean.nachtruhe");
  assert.equal(switchEntityId({ id: "night_mode_2", name: "Night mode" }), "input_boolean.night_mode_2");
});

test("the rule takes the created toggle, the state on, and its name when it has none", () => {
  assert.deepEqual(
    ruleWithSwitch({ name: "", entity_id: "", state: "off", effect_1: "hold", max_hours: 12 }, "input_boolean.nachtruhe", "Nachtruhe"),
    { name: "Nachtruhe", entity_id: "input_boolean.nachtruhe", state: "on", effect_1: "hold", max_hours: 12 });
  // a name typed before stays
  assert.deepEqual(
    ruleWithSwitch({ name: "Ruhe", entity_id: "sun.sun", state: "below_horizon" }, "input_boolean.urlaub", "Urlaub"),
    { name: "Ruhe", entity_id: "input_boolean.urlaub", state: "on" });
  assert.equal(ruleWithSwitch({ name: "  " }, "input_boolean.away", "Away").name, "Away");
});

test("the dialog says what a mode is and that the toggle is not switched here", () => {
  assert.equal(tables.de.mode_title, "Was ist ein Modus?");
  assert.equal(tables.en.mode_title, "What is a mode?");
  assert.equal(tables.de.switch_create, "Schalter anlegen");
  assert.equal(tables.de.switch_name_default, "Nachtmodus");
  assert.equal(tables.en.switch_name_default, "Night mode");
  assert.equal(tables.de.switch_hint,
    "Der Schalter wird hier nicht bedient. Ein- und ausschalten musst du ihn über eine Automation oder im Dashboard.");
  assert.equal(tables.en.switch_hint, "The toggle is not switched here. Turn it on and off with an automation or on a dashboard.");
  // the box names the usual examples, where a toggle is created, the dashboard and that something must switch it
  for (const word of ["Nachtmodus", "Urlaub", "Abwesend", "Helfer", "Dashboard", "Bettschalter", "Automation"]) {
    assert.ok(Object.keys(tables.de).filter((k) => k.startsWith("mode_")).some((k) => tables.de[k].includes(word)), word);
  }
  for (const word of ["Night mode", "Vacation", "Away", "Helpers", "dashboard", "bed switch", "automation"]) {
    assert.ok(Object.keys(tables.en).filter((k) => k.startsWith("mode_")).some((k) => tables.en[k].includes(word)), word);
  }
});

test("the way to a dashboard is the one of a dashboard of one's own", () => {
  // Home Assistant's own overview has "Edit overview" and no "Add card"; a dashboard of one's own has both
  assert.ok(tables.de.mode_dashboard.includes("eigenes Dashboard"));
  assert.ok(tables.de.mode_dashboard.includes("„Dashboard bearbeiten“ → „Karte hinzufügen“ → „Nach Entität“"));
  assert.ok(tables.en.mode_dashboard.includes("dashboard of your own"));
  assert.ok(tables.en.mode_dashboard.includes("“Edit dashboard” → “Add card” → “By entity”"));
});
