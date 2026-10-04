// The logic of the settings tab, free of the page's elements: the options with
// their defaults, the list of lamps for the light pulse (each with its own
// "also when off"), the options as they are saved, and whether the tab holds
// something not saved yet. Tested by test/settings-logic.test.ts.
import type { Options } from "./types";

/** One lamp or switch of the light pulse; `always` pulses it even when off (on, then off again). */
export interface LightRow {
  entity_id: string;
  always: boolean;
}

/** The options with the defaults the center uses for what was never set. */
export const withDefaults = (o: Options): Options => ({
  history_days: o.history_days ?? 30, sidebar: o.sidebar ?? true, hide_titles: o.hide_titles ?? false,
  allow_alarm: o.allow_alarm ?? false, lights: o.lights ?? [], pulse_ms: o.pulse_ms ?? 500, light_spacing: o.light_spacing ?? 0,
  alarm_lights: o.alarm_lights ?? [], alarm_interval_ms: o.alarm_interval_ms ?? 1000, alarm_max_seconds: o.alarm_max_seconds ?? 300,
  alarm_test_seconds: o.alarm_test_seconds ?? 5, silent_repeat: o.silent_repeat ?? false,
  alarm_channel: o.alarm_channel ?? "alarm_stream", alarm_tts: o.alarm_tts ?? false,
  button_snooze: o.button_snooze ?? true, tap_target: o.tap_target ?? "home",
  button_forward: o.button_forward ?? true, snooze_minutes: o.snooze_minutes ?? 30,
  snooze_minutes_2: o.snooze_minutes_2 ?? 0, snooze_input: o.snooze_input ?? false,
  lights_always: o.lights_always ?? [], forward_script: o.forward_script ?? "",
  effect_script_1: o.effect_script_1 ?? "", effect_script_2: o.effect_script_2 ?? "", effect_script_3: o.effect_script_3 ?? "",
});

/**
 * The lamps as one list, each once. A lamp marked "also when off" that is
 * missing from the lamps (an older page could save that) belongs to them, as
 * the center reads it: it comes after the others.
 */
export const lightRows = (o: Options): LightRow[] => {
  const always = new Set(o.lights_always ?? []);
  return [...new Set([...(o.lights ?? []), ...(o.lights_always ?? [])])].map((entity_id) => ({ entity_id, always: always.has(entity_id) }));
};

/** The list as it is saved: all lamps, and the part of them that pulses when off. */
export const lightsFromRows = (rows: LightRow[]): { lights: string[]; lights_always: string[] } => ({
  lights: rows.map((r) => r.entity_id),
  lights_always: rows.filter((r) => r.always).map((r) => r.entity_id),
});

const withRows = (o: Options, rows: LightRow[]): Options => ({ ...o, ...lightsFromRows(rows) });

/** Add a lamp at the end of the list; one already in it stays where it is. */
export const withLight = (o: Options, entityId: string): Options => {
  const rows = lightRows(o);
  return rows.some((r) => r.entity_id === entityId) ? withRows(o, rows) : withRows(o, [...rows, { entity_id: entityId, always: false }]);
};

/** Take a lamp out of the list, with its "also when off". */
export const withoutLight = (o: Options, entityId: string): Options =>
  withRows(o, lightRows(o).filter((r) => r.entity_id !== entityId));

/** Turn "also when off" of one lamp on or off. */
export const withAlways = (o: Options, entityId: string, always: boolean): Options =>
  withRows(o, lightRows(o).map((r) => (r.entity_id === entityId ? { ...r, always } : r)));

/** The options as the settings tab saves them (all of them; an empty script is none). */
export const optionsPayload = (s: Options, guideDismissed: boolean): Options => ({
  guide_dismissed: guideDismissed,
  history_days: Number(s.history_days ?? 30), sidebar: s.sidebar !== false, hide_titles: !!s.hide_titles,
  allow_alarm: !!s.allow_alarm, ...lightsFromRows(lightRows(s)), pulse_ms: Number(s.pulse_ms ?? 500),
  light_spacing: Number(s.light_spacing ?? 0),
  alarm_lights: s.alarm_lights ?? [], alarm_interval_ms: Number(s.alarm_interval_ms ?? 1000),
  alarm_max_seconds: Number(s.alarm_max_seconds ?? 300), alarm_test_seconds: Number(s.alarm_test_seconds ?? 5),
  silent_repeat: !!s.silent_repeat, alarm_channel: String(s.alarm_channel ?? "alarm_stream"), alarm_tts: !!s.alarm_tts,
  button_snooze: s.button_snooze !== false, tap_target: s.tap_target === "center" ? "center" : "home",
  button_forward: s.button_forward !== false, snooze_minutes: Number(s.snooze_minutes ?? 30),
  snooze_minutes_2: Number(s.snooze_minutes_2 ?? 0), snooze_input: !!s.snooze_input,
  forward_script: s.forward_script || null,
  effect_script_1: s.effect_script_1 || null, effect_script_2: s.effect_script_2 || null, effect_script_3: s.effect_script_3 || null,
});

/** The options of this tab as they would be saved, lists in a fixed order: what to compare. */
const comparable = (o: Options): string => {
  const p: Record<string, unknown> = { ...optionsPayload(o, false) };
  delete p.guide_dismissed;
  for (const key of ["lights", "lights_always", "alarm_lights"]) p[key] = [...(p[key] as string[])].sort();
  return JSON.stringify(Object.keys(p).sort().map((key) => [key, p[key]]));
};

/**
 * Whether the working copy of the settings differs from the stored options:
 * then "Save" replaces each "Test" button, which would test the stored ones.
 * Lists count as sets, and values saved the same way count as the same.
 */
export const settingsChanged = (working: Options, stored: Options): boolean =>
  comparable(working) !== comparable(withDefaults(stored));
