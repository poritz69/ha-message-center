// The logic of the kind dialog, free of the page's elements: the sentence on
// top, how the dialog starts, the possible messages of an automation, the
// data of a kind as it is saved, the double condition and the question
// before saving. Tested by test/kind-logic.test.ts.
import type { Translate } from "./i18n";
import type { Kind, KindMatches, OriginMessages, ScanItem, TitleMode, UnknownItem } from "./types";

/** Stands for the computed parts of a title read from a configuration (as the center writes it). */
export const PLACEHOLDER = "…";

/** A fixed beginning or part shorter than this says too little to compare with. */
const MIN_FIXED = 3;

/** The condition of a kind as the dialog holds it; origin "" means any origin. */
export interface Condition {
  origin: string;
  title_mode: TitleMode;
  title_value: string;
}

/** How the dialog was opened. */
export type KindSource =
  | { from: "blank"; group?: string }
  | { from: "new"; item: UnknownItem; group?: string }
  | { from: "scan"; item: ScanItem }
  | { from: "edit"; kind: Kind };

/** How the dialog starts: the condition, which of its fields are open, and the name. */
export interface DialogStart {
  condition: Condition;
  /** Origin, comparison and text are locked; "edit condition (advanced)" opens them. */
  locked: boolean;
  /** The text is open although the rest is locked: the automation sends several messages. */
  titleOpen: boolean;
  /** The automation sends several different messages: show the hint and the possible messages. */
  multiple: boolean;
  /** An existing kind was put on "all messages of this automation": say so and offer to keep the old condition. */
  switched: boolean;
  name: string;
}

/** Comparison and text a possible message puts into the condition; null when it offers no fixed text. */
export type Apply = { title_mode: TitleMode; title_value: string } | null;

/** One message an automation may send, as the dialog lists it. */
export interface Possible {
  label: string;
  tag: "fixed" | "computed" | "seen";
  apply: Apply;
}

/** True when a kind for every title may be bound to this origin: an automation or script. */
export const originAllowsAny = (origin: string | null | undefined): boolean => !!origin && origin !== "unknown";

/** True when the condition can be saved: "any" needs an automation, the other comparisons a text. */
export const conditionComplete = (c: Condition): boolean =>
  c.title_mode === "any" ? originAllowsAny(c.origin) : c.title_value.trim().length > 0;

/** Put values into the {placeholders} of a text; the values themselves are not read again. */
export const fill = (text: string, values: Record<string, string | number>) =>
  text.replace(/\{(\w+)\}/g, (all, key: string) => (key in values ? String(values[key]) : all));

/** A text that names the sort of origin: its "…_script" variant for a script, else the one for an automation. */
export const forOrigin = (t: Translate, key: string, origin: string | null | undefined): string =>
  t(origin?.startsWith("script.") ? `${key}_script` : key);

/** A count in words: the "…_one" text for one, the "…_many" text with {n} otherwise. */
export const counted = (t: Translate, key: string, n: number): string => fill(t(`${key}_${n === 1 ? "one" : "many"}`), { n });

/** "der Automation „X“", "jeder Herkunft" and the like, for the sentence on top. */
function originPhrase(t: Translate, origin: string, name: string | null): string {
  if (!origin) return t("of_any");
  if (origin === "unknown") return t("of_unknown");
  const domain = origin.split(".")[0];
  const key = domain === "automation" ? "of_automation" : domain === "script" ? "of_script" : "of_origin";
  return fill(t(key), { name: name || origin });
}

/** The sentence on top: "Gilt für: alle Meldungen der Automation „Waschmaschine“". */
export function appliesTo(t: Translate, c: Condition, originName: (id: string) => string | null): string {
  if (!conditionComplete(c)) return fill(t("applies"), { what: t("applies_incomplete") });
  const origin = originPhrase(t, c.origin, c.origin ? originName(c.origin) : null);
  const what = fill(t(`applies_${c.title_mode}`), { origin, value: c.title_value.trim() });
  return fill(t("applies"), { what });
}

/** The condition in the list of kinds: "genau „Fenster offen“", "alle Meldungen dieser Automation" (or "dieses Skripts"). */
export const conditionLabel = (t: Translate, mode: TitleMode, value: string, origin?: string | null): string =>
  mode === "any" ? forOrigin(t, "any", origin) : `${t(mode)} ${t("q_open")}${value}${t("q_close")}`;

/** The comparisons to choose from; "all messages of this automation" only with an automation or script as origin. */
export function modeOptions(t: Translate, origin: string): { value: TitleMode; label: string }[] {
  const modes: TitleMode[] = ["exact", "prefix", "contains", ...(originAllowsAny(origin) ? ["any" as const] : [])];
  return modes.map((value) => ({ value, label: value === "any" ? forOrigin(t, "any", origin) : t(value) }));
}

/** The comparison for a computed title: its fixed beginning, else its longest fixed part, else nothing. */
function fixedPart(display: string): Apply {
  const parts = display.split(PLACEHOLDER).map((p) => p.trim());
  if (parts[0].length >= MIN_FIXED) return { title_mode: "prefix", title_value: parts[0] };
  const longest = parts.reduce((a, b) => (b.length > a.length ? b : a), "");
  return longest.length >= MIN_FIXED ? { title_mode: "contains", title_value: longest } : null;
}

/**
 * The messages an automation may send: its fixed titles, its computed ones
 * with the placeholder, and the titles that really arrived from it (each
 * once, case aside). Picking one puts its comparison into the condition.
 */
export function possibleMessages(om: OriginMessages): Possible[] {
  const list: Possible[] = [];
  const fixed = new Set<string>();
  for (const m of om.messages) {
    if (m.template) {
      list.push({ label: m.display, tag: "computed", apply: fixedPart(m.display) });
    } else {
      // a call without a title is called after its automation: display is that name
      const title = m.title ?? m.display;
      fixed.add(title.toLowerCase());
      list.push({ label: m.display, tag: "fixed", apply: { title_mode: "exact", title_value: title } });
    }
  }
  for (const title of om.seen_titles) {
    if (fixed.has(title.toLowerCase())) continue;
    fixed.add(title.toLowerCase());
    list.push({ label: title, tag: "seen", apply: { title_mode: "exact", title_value: title } });
  }
  return list;
}

/** The origin whose messages the dialog asks about; "" when there is none to ask. */
export function sourceOrigin(source: KindSource): string {
  switch (source.from) {
    case "new": return originAllowsAny(source.item.origin) ? source.item.origin : "";
    case "scan": return source.item.origin ?? "";
    case "edit": return originAllowsAny(source.kind.origin) ? source.kind.origin ?? "" : "";
    default: return "";
  }
}

/** The condition a kind has stored, as the dialog holds it. */
export const conditionOf = (k: Kind): Condition => ({ origin: k.origin ?? "", title_mode: k.title_mode, title_value: k.title_value });

/** True when the automation is known to send one message: its configuration or the titles that arrived say so. */
const sendsOne = (om: OriginMessages): boolean => om.any_allowed && om.source !== "none" && !om.multiple;

/**
 * How the dialog starts. From "New", from the search and to edit: an
 * automation that sends one message gets "all messages of this automation",
 * locked; one that sends several gets the title open, with the message's
 * title or the search's suggestion (an existing kind keeps its own
 * condition then). The answer about the automation (`om`) decides; until it
 * is there, the flag of the entry, and an existing kind keeps its
 * condition. An existing kind is not put on all messages when nothing is
 * known about the automation, when the automation is gone, or when another
 * kind (of `kinds`) has that condition already. A kind without a template
 * starts with open fields.
 */
export function startState(source: KindSource, om?: OriginMessages | null, kinds: readonly Kind[] = []): DialogStart {
  if (source.from === "blank") {
    return { condition: { origin: "", title_mode: "exact", title_value: "" }, locked: false, titleOpen: true, multiple: false, switched: false, name: "" };
  }
  if (source.from === "edit") {
    const k = source.kind;
    const kept = conditionOf(k);
    if (om && sendsOne(om) && !k.orphan && k.title_mode !== "any" && originAllowsAny(k.origin)) {
      // the old text waits in the condition for a switch back to another comparison; "any" does not use it
      const all: Condition = { ...kept, title_mode: "any" };
      if (!duplicateIn(kinds, all, k.id)) {
        return { condition: all, locked: true, titleOpen: false, multiple: false, switched: true, name: k.name };
      }
    }
    const multiple = !!om?.multiple;
    return { condition: kept, locked: true, titleOpen: multiple && k.title_mode !== "any", multiple, switched: false, name: k.name };
  }
  const origin = source.from === "new"
    ? (source.item.origin === "unknown" ? "" : source.item.origin)
    : (source.item.origin ?? "");
  const anyAllowed = om ? om.any_allowed && originAllowsAny(origin) : originAllowsAny(origin);
  const multiple = anyAllowed && (om ? om.multiple : !!source.item.multiple);
  if (anyAllowed && !multiple) {
    const name = source.from === "new" ? source.item.title : scanName(source.item);
    // "any" does not use the text; the message's fixed title waits there for a switch to another comparison
    const title = source.from === "new" ? source.item.title
      : source.item.title && !source.item.title_template ? source.item.title : "";
    return { condition: { origin, title_mode: "any", title_value: title }, locked: true, titleOpen: false, multiple, switched: false, name };
  }
  if (source.from === "new") {
    return {
      condition: { origin, title_mode: "exact", title_value: source.item.title },
      locked: true, titleOpen: multiple, multiple, switched: false, name: source.item.title,
    };
  }
  const s = source.item.suggestion;
  if (s && s.mode !== "any") {
    return {
      condition: { origin, title_mode: s.mode, title_value: s.value }, locked: true, titleOpen: multiple, multiple, switched: false,
      name: scanName(source.item),
    };
  }
  // nothing fixed to suggest: the title has to be filled in
  return { condition: { origin, title_mode: "exact", title_value: "" }, locked: true, titleOpen: true, multiple, switched: false, name: scanName(source.item) };
}

/** Name for a kind made from a found call: its fixed title, else the suggested text, else the automation's name. */
function scanName(i: ScanItem): string {
  if (i.title && !i.title_template) return i.title;
  return i.suggestion?.value || i.name;
}

/** The pair a kind is made from, to ask before saving whether the new condition still takes it. */
export const probeOf = (source: KindSource): { origin: string; title: string } | null =>
  source.from === "new" ? { origin: source.item.origin, title: source.item.title } : null;

/** True when the original message would land in "new" again: the condition misses it and no other kind takes it. */
export const landsInNew = (m: KindMatches | null | undefined): boolean => !!m?.probe && !m.probe.matches && !m.probe.taken_by;

/** Case aside, as the center compares (like Python's casefold: "ß" and "SS" alike). */
const fold = (s: string) => s.toUpperCase().toLowerCase();

/** The condition as the center compares it: origin or none, comparison, text without case and spaces; "any" has no text. */
const conditionKey = (origin: string | null | undefined, mode: TitleMode, value: string) =>
  JSON.stringify([origin || null, mode, mode === "any" ? "" : fold(value.trim())]);

/**
 * The kind that already has this condition, active or not, leaving out the
 * kind being edited (`kindId`). As the center does, a kind being edited is
 * checked only when its condition changes: two kinds that already share a
 * condition (saved by an older version) can still be renamed, moved or
 * switched off. Asked before saving, so that nothing (such as a new group)
 * is created for a kind the center would refuse; the center's own refusal
 * stays the second safeguard.
 */
export function duplicateIn(kinds: readonly Kind[], c: Condition, kindId?: string): { kind_id: string; name: string } | null {
  const key = conditionKey(c.origin, c.title_mode, c.title_value);
  const keyOf = (k: Kind) => conditionKey(k.origin, k.title_mode, k.title_value);
  const own = kindId ? kinds.find((k) => k.id === kindId) : undefined;
  if (own && keyOf(own) === key) return null;
  const found = kinds.find((k) => k.id !== kindId && keyOf(k) === key);
  return found ? { kind_id: found.id, name: found.name } : null;
}

/** The kind that already has this condition, from the error of a refused save. */
export function duplicateOf(err: unknown): { kind_id: string; name: string } | null {
  const e = err as { code?: unknown; kind_id?: unknown; name?: unknown } | null | undefined;
  if (!e || e.code !== "duplicate" || typeof e.kind_id !== "string") return null;
  return { kind_id: e.kind_id, name: typeof e.name === "string" ? e.name : "" };
}

/** The data of a kind as message_center/save takes it. */
export function kindPayload(d: Record<string, unknown>, c: Condition, groupId: string | null): Record<string, unknown> {
  return {
    name: String(d.name ?? "").trim(), origin: c.origin || null, title_mode: c.title_mode,
    title_value: c.title_mode === "any" ? "" : c.title_value.trim(), group_id: groupId, priority: Number(d.priority ?? 1),
    no_hold: !!d.no_hold, spacing: Number(d.spacing ?? 0), expires_after: Number(d.expires_after ?? 0),
    light: d.light === "auto" || d.light == null ? null : d.light === "on", active: d.active !== false,
  };
}
