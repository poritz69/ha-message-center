// Tests of the settings tab's logic: the list of lamps for the light pulse
// (each with its own "also when off"), the options as they are saved, and
// whether something is not saved yet (then "Save" replaces "Test").
// Run with "npm test".
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  lightRows, lightsFromRows, optionsPayload, settingsChanged, withAlways, withDefaults, withLight, withoutLight,
} from "../src/settings-logic";
import type { Options } from "../src/types";

test("the list of lamps holds every lamp once, with its own 'also when off'", () => {
  assert.deepEqual(lightRows({ lights: ["light.hall", "switch.lamp"], lights_always: ["switch.lamp"] }), [
    { entity_id: "light.hall", always: false }, { entity_id: "switch.lamp", always: true }]);
  // a lamp marked "also when off" but missing from the lamps (saved by an older page) is in the list
  assert.deepEqual(lightRows({ lights: ["light.hall"], lights_always: ["light.porch"] }), [
    { entity_id: "light.hall", always: false }, { entity_id: "light.porch", always: true }]);
  assert.deepEqual(lightRows({ lights: ["light.hall", "light.hall"], lights_always: ["light.hall"] }), [
    { entity_id: "light.hall", always: true }]);
  assert.deepEqual(lightRows({}), []);
});

test("the list is saved as the lamps and the part of them that pulses when off", () => {
  assert.deepEqual(lightsFromRows([{ entity_id: "light.hall", always: false }, { entity_id: "switch.lamp", always: true }]),
    { lights: ["light.hall", "switch.lamp"], lights_always: ["switch.lamp"] });
  assert.deepEqual(lightsFromRows([]), { lights: [], lights_always: [] });
});

test("a lamp is added once, switched to 'also when off' and removed", () => {
  const start: Options = { lights: ["light.hall"], lights_always: [] };
  const added = withLight(start, "switch.lamp");
  assert.deepEqual([added.lights, added.lights_always], [["light.hall", "switch.lamp"], []]);
  // a lamp already in the list stays where it is
  assert.deepEqual(withLight(added, "light.hall").lights, ["light.hall", "switch.lamp"]);
  const always = withAlways(added, "switch.lamp", true);
  assert.deepEqual([always.lights, always.lights_always], [["light.hall", "switch.lamp"], ["switch.lamp"]]);
  assert.deepEqual(withAlways(always, "switch.lamp", false).lights_always, []);
  // removing a lamp takes its "also when off" with it
  const removed = withoutLight(always, "switch.lamp");
  assert.deepEqual([removed.lights, removed.lights_always], [["light.hall"], []]);
  // the other options stay, the original is not changed
  assert.equal(withLight({ ...start, pulse_ms: 700 }, "light.porch").pulse_ms, 700);
  assert.deepEqual(start, { lights: ["light.hall"], lights_always: [] });
});

test("the options as they are saved: all of them, the lamps as list and part, no empty script", () => {
  const p = optionsPayload({ ...withDefaults({}), lights: ["light.hall"], lights_always: ["light.porch"], forward_script: "",
    effect_script_2: "script.announce", tap_target: "center", pulse_ms: 700 }, true);
  assert.deepEqual(p.lights, ["light.hall", "light.porch"]);
  assert.deepEqual(p.lights_always, ["light.porch"]);
  assert.equal(p.forward_script, null);
  assert.equal(p.effect_script_2, "script.announce");
  assert.equal(p.tap_target, "center");
  assert.equal(p.pulse_ms, 700);
  assert.equal(p.guide_dismissed, true);
  // the defaults for what was never set
  const d = optionsPayload(withDefaults({}), false);
  assert.equal(d.history_days, 30);
  assert.equal(d.tap_target, "home");
  assert.equal(d.button_snooze, true);
  assert.equal(d.alarm_channel, "alarm_stream");
});

test("nothing is changed while the settings are as stored", () => {
  for (const stored of [{}, { lights: ["light.hall"], pulse_ms: 700, guide_dismissed: true }] as Options[]) {
    assert.equal(settingsChanged(withDefaults(stored), stored), false);
  }
});

test("each change counts until it is saved, and going back counts as no change", () => {
  const stored: Options = { lights: ["light.hall"] };
  const working = withDefaults(stored);
  assert.equal(settingsChanged({ ...working, pulse_ms: 800 }, stored), true);
  assert.equal(settingsChanged({ ...working, tap_target: "center" }, stored), true);
  assert.equal(settingsChanged({ ...working, forward_script: "script.ask" }, stored), true);
  assert.equal(settingsChanged({ ...working, alarm_lights: ["light.hall"] }, stored), true);
  assert.equal(settingsChanged(withLight(working, "light.porch"), stored), true);
  assert.equal(settingsChanged(withAlways(working, "light.hall", true), stored), true);
  assert.equal(settingsChanged(withoutLight(working, "light.hall"), stored), true);
  assert.equal(settingsChanged(withoutLight(withLight(working, "light.porch"), "light.porch"), stored), false);
});

test("what is saved the same way counts as the same", () => {
  // a lamp only in lights_always (older page), the order of lamps, an empty script and none
  const stored: Options = { lights: ["light.hall", "light.porch"], lights_always: ["switch.lamp"], forward_script: null };
  const working = withDefaults(stored);
  assert.equal(settingsChanged(working, stored), false);
  assert.equal(settingsChanged({ ...working, lights: ["light.porch", "light.hall"] }, stored), false);
  assert.equal(settingsChanged({ ...working, forward_script: "" }, stored), false);
  // the list shows the lamp of lights_always as a lamp: saving it so is no change either
  assert.equal(settingsChanged({ ...working, ...lightsFromRows(lightRows(working)) }, stored), false);
  // only showing the introduction again is no setting of this tab
  assert.equal(settingsChanged(working, { ...stored, guide_dismissed: true }), false);
});
