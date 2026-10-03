// Preview of the real page outside Home Assistant, with example data.
// Not part of the shipped page: it provides plain stand-ins for the Home
// Assistant elements the page uses (ha-card, ha-button, ...) and a mock of the
// connection, so that the look can be judged without a running system.
// "npm run preview" bundles it into preview/preview.js; open preview/index.html
// through a local web server.
import { LitElement, css, html, nothing, render } from "lit";
import { property } from "lit/decorators.js";
import "./panel";
import type { Config, Kind, KindMatches, MatchedPair, MessageEntry, Messages, OriginMessages, Overview, ScanResult } from "./types";

// Address parameters, for screenshots:
//   ?lang=en             the page in English with English example data (without it: German)
//   ?only=wide|phone     just the wide or the narrow frame, without the preview's headings
//   ?tab=open&unfold=1   select a tab and unfold the first message row (?scan=1 runs the search on "kinds")
//   ?theme=light         light colours (without it: dark; preview.css holds both)
//   ?kind=one            the kind dialog: one (from "new", an automation with one message), many (one with
//                        several), advanced (one, condition opened), edit, switched (edit of a kind whose automation
//                        sends one message), blank, duplicate, overlap, scan
const params = new URLSearchParams(location.search);
document.documentElement.dataset.theme = params.get("theme") === "light" ? "light" : "dark";
const en = params.get("lang") === "en";
const only = params.get("only") === "wide" || params.get("only") === "phone" ? params.get("only") : null;

// ----- stand-ins for Home Assistant elements ---------------------------------

class Card extends LitElement {
  @property() public header?: string;
  static styles = css`
    :host { display: block; background: var(--card-background-color); border: 1px solid var(--divider-color);
      border-radius: 12px; overflow: hidden; color: var(--primary-text-color); }
    h1 { font-size: 22px; font-weight: 400; margin: 0; padding: 14px 16px 8px; }
  `;
  render() { return html`${this.header ? html`<h1>${this.header}</h1>` : nothing}<slot></slot>`; }
}

class Button extends LitElement {
  static styles = css`
    :host { display: inline-block; }
    button { font: inherit; font-size: 14px; font-weight: 500; height: 36px; padding: 0 16px; border-radius: 18px; cursor: pointer;
      border: 1px solid transparent; background: var(--primary-color); color: #fff; }
    :host([appearance="plain"]) button { background: transparent; color: var(--primary-color); padding: 0 10px; }
    :host([size="small"]) button { height: 28px; font-size: 13px; padding: 0 8px; }
    :host([appearance="outlined"]) button { background: transparent; color: var(--primary-color); border-color: var(--primary-color); }
    :host([appearance="filled"]) button { background: #fff; color: #000; }
  `;
  render() { return html`<button><slot></slot></button>`; }
}

class Icon extends LitElement {
  @property() public icon = "";
  static styles = css`:host { display: inline-flex; width: 24px; height: 24px; } svg { width: 24px; height: 24px; }`;
  render() {
    const d = this.icon.includes("thermometer") ? "M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0z"
      : this.icon.includes("server") ? "M4 5h16v6H4zM4 13h16v6H4zM7 8h.5M7 16h.5"
      : "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z";
    return html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"><path d=${d}></path></svg>`;
  }
}

class MenuButton extends LitElement {
  static styles = css`:host { display: inline-flex; width: 40px; height: 40px; align-items: center; justify-content: center; opacity: .9; }`;
  render() { return html`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M3 6h18v2H3zm0 5h18v2H3zm0 5h18v2H3z"></path></svg>`; }
}

/** Shows the fields of a form as plain rows. The real forms come from Home Assistant and look like its own dialogs. */
class Form extends LitElement {
  @property({ attribute: false }) public schema: { name: string; disabled?: boolean; selector: Record<string, unknown> }[] = [];
  @property({ attribute: false }) public data: Record<string, unknown> = {};
  @property({ attribute: false }) public computeLabel?: (f: { name: string }) => string;
  @property({ attribute: false }) public computeHelper?: (f: { name: string }) => string | undefined;
  static styles = css`
    .f { padding: 10px 0; border-top: 1px solid var(--divider-color); display: flex; gap: 12px; align-items: center; }
    .f:first-child { border-top: 0; }
    .f.dis { opacity: .45; }
    .l { flex: 1; min-width: 0; } .h { color: var(--secondary-text-color); font-size: 12px; margin-top: 2px; }
    .v { color: var(--secondary-text-color); font-size: 13px; padding: 6px 10px; border-radius: 6px; background: var(--secondary-background-color);
      max-width: 55%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .sw { width: 36px; height: 20px; border-radius: 10px; background: var(--divider-color); position: relative; flex: none; }
    .sw.on { background: color-mix(in srgb, var(--primary-color) 55%, transparent); }
    .sw::after { content: ""; position: absolute; top: 2px; left: 2px; width: 16px; height: 16px; border-radius: 50%; background: var(--secondary-text-color); }
    .sw.on::after { left: 18px; background: var(--primary-color); }
  `;
  render() {
    return html`${this.schema.map((f) => {
      const v = this.data?.[f.name];
      const helper = this.computeHelper?.(f);
      // a dropdown shows the label of its value, as the real one does
      const options = (f.selector.select as { options?: { value: string; label: string }[] } | undefined)?.options;
      const shown = Array.isArray(v) ? `${v.length} ${en ? "selected" : "gewählt"}`
        : options ? (options.find((o) => o.value === String(v ?? ""))?.label ?? (v ? String(v) : "–"))
        : v === "" || v == null ? "–" : String(v);
      return html`<div class="f ${f.disabled ? "dis" : ""}"><div class="l"><div>${this.computeLabel?.(f) ?? f.name}</div>${helper ? html`<div class="h">${helper}</div>` : nothing}</div>
        ${"boolean" in f.selector ? html`<span class="sw ${v ? "on" : ""}"></span>` : html`<span class="v">${shown}</span>`}</div>`;
    })}`;
  }
}

/** A dialog over the page, like Home Assistant's: title, content, buttons below. */
class Dialog extends LitElement {
  @property({ attribute: false }) public open = false;
  @property({ attribute: "header-title" }) public headerTitle = "";
  @property({ attribute: false }) public preventScrimClose = false;
  static styles = css`
    :host { position: absolute; inset: 0; z-index: 10; display: block; background: rgba(0, 0, 0, .55); }
    .box { margin: 32px auto; width: min(560px, calc(100% - 24px)); box-sizing: border-box; border-radius: 24px;
      background: var(--card-background-color); color: var(--primary-text-color); box-shadow: 0 12px 40px rgba(0, 0, 0, .45); }
    h2 { margin: 0; padding: 22px 24px 10px; font-size: 22px; font-weight: 400; }
    .body { padding: 4px 24px; }
    .foot { display: flex; justify-content: flex-end; gap: 8px; padding: 14px 24px 20px; }
  `;
  render() {
    return html`<div class="box"><h2>${this.headerTitle}</h2><div class="body"><slot></slot></div><div class="foot"><slot name="footer"></slot></div></div>`;
  }
}

for (const [tag, cls] of [["ha-card", Card], ["ha-button", Button], ["ha-icon", Icon], ["ha-menu-button", MenuButton], ["ha-form", Form],
  ["ha-dialog", Dialog]] as const) {
  if (!customElements.get(tag)) customElements.define(tag, cls);
}

// ----- example data ---------------------------------------------------------------

const ago = (minutes: number) => new Date(Date.now() - minutes * 60000).toISOString();
const inMin = (minutes: number) => new Date(Date.now() + minutes * 60000).toISOString();
const two = (n: number) => String(n).padStart(2, "0");

/** A time as the center writes it into a German reason ("03.10. 07:14"). */
const deStamp = (iso: string) => {
  const d = new Date(iso);
  return `${two(d.getDate())}.${two(d.getMonth() + 1)}. ${two(d.getHours())}:${two(d.getMinutes())}`;
};

/** A time as the center writes it into an English reason ("Oct 03 07:14"). */
const enStamp = (iso: string) => {
  const d = new Date(iso);
  return `${d.toLocaleString("en-US", { month: "short" })} ${two(d.getDate())} ${two(d.getHours())}:${two(d.getMinutes())}`;
};

// ids as the center gives them: 16 hex characters, nothing of the title in them
const exampleId = (title: string) => {
  let a = 0x811c9dc5, b = 0x01000193;
  for (const ch of title) { a = Math.imul(a ^ ch.charCodeAt(0), 0x01000193) >>> 0; b = Math.imul(b + ch.charCodeAt(0), 0x27d4eb2f) >>> 0; }
  return a.toString(16).padStart(8, "0") + b.toString(16).padStart(8, "0");
};

const msg = (o: Partial<MessageEntry> & { title: string; message: string; state: string; priority: number }): MessageEntry => ({
  message_id: exampleId(o.title), origin: en ? "automation.example" : "automation.beispiel", origin_name: null, kind: null, group: null,
  data: {}, labels: [], count: 1, since: ago(30), reason: "", until: null, next_try: null, failed_recipients: [], last_error: null,
  generation: 1, revision: 1, accepted_at: ago(30), updated_at: ago(30), delivered_at: null, ended_at: null, forwarded_at: null,
  expires_at: null, spacing: 0, no_hold: false, kind_id: null, group_id: null, recipients: {}, events: [], ...o,
});

const scanItem = (o: Partial<ScanResult["found"][number]>): ScanResult["found"][number] => ({
  source: "automation", entity_id: "automation.feuchte", name: "Klima – Feuchte überwachen", origin: "automation.feuchte", blueprint: null, edit_url: null,
  service: "notify.send_message", target: "notify.send_message → notify.handy_alex", status: "direct", title: null, title_template: false,
  first_line: null, suggestion: null, file: "packages/bad_feuchte.yaml", line: 1, kind: null, ...o,
});

interface Example {
  messages: Messages;
  overview: Overview;
  config: Config;
  scan: ScanResult;
  /** What each automation sends, as message_center/origin_messages answers. */
  sends: Record<string, OriginMessages>;
  /** recipient names a test reaches */
  sent: string[];
  /** the helper the night rule watches */
  nightEntity: string;
}

/** What an automation sends: fixed titles as they are, computed ones with "…" for the computed parts. */
const sends = (o: Partial<OriginMessages> & { titles?: (string | [string, string])[] }): OriginMessages => ({
  source: "config", seen_titles: [], multiple: (o.titles?.length ?? 0) > 1, any_allowed: true,
  messages: (o.titles ?? []).map((t) => (typeof t === "string"
    ? { title: t, template: false, display: t }
    : { title: t[0], template: true, display: t[1] })),
  ...o,
});

const kindOf = (o: Partial<Kind> & { id: string; name: string }): Kind => ({
  origin: null, title_mode: "exact", title_value: "", group_id: null, priority: 1, no_hold: false, spacing: 0, expires_after: 0,
  light: null, active: true, ties: [], orphan: false, ...o,
});

/** The example data in German. */
const germanExample = (): Example => {
  const nightUntil = inMin(600);
  const messages: Messages = {
    open: [
      msg({ title: "Feuchte hoch: Bad", message: "Luftfeuchte im Bad seit 30 min über 70 %. Bitte lüften.", state: "waiting", priority: 1,
        origin: "automation.feuchte", origin_name: "Klima – Feuchte überwachen", kind: "Feuchte", group: "Klima", since: ago(42),
        reason: `zurückgehalten: Nachtmodus bis ${deStamp(nightUntil)}` }),
      msg({ title: "Waschmaschine fertig", message: "Die Wäsche kann raus.", state: "retrying", priority: 2, count: 3,
        origin: "automation.waschmaschine", origin_name: "Haushalt – Waschmaschine", since: ago(76), reason: "Zustellfehler, nächster Versuch",
        next_try: inMin(9), failed_recipients: ["Tablet Küche"] }),
    ],
    recent: [
      msg({ title: "Wassermelder Keller", message: "Wasser am Boden erkannt. Bitte sofort prüfen.", state: "delivered", priority: 3,
        origin: "automation.wasser", origin_name: "Sicherheit – Wasser", kind: "Wasseralarm", group: "Sicherheit", since: ago(114),
        delivered_at: ago(114), reason: "zugestellt",
        events: [{ at: ago(114), kind: "alarm_light", source: "center", detail: "3 Lampen" }, { at: ago(113), kind: "snoozed", source: "phone", detail: "30 min" },
          { at: ago(111), kind: "forwarded", source: "page", detail: "Was tun?" }] }),
      msg({ title: "Fenster offen", message: "Das Fenster im Büro ist seit 20 min offen, draußen sind es 4 °C.", state: "delivered", priority: 2,
        origin: "automation.fenster", origin_name: "Klima – Fenster überwachen", kind: "Fenster offen", group: "Klima", since: ago(190),
        delivered_at: ago(190), reason: "zugestellt",
        events: [{ at: ago(190), kind: "light", source: "center", detail: "light.flur, light.kueche" }] }),
      // what the appliance automation sent before; its entries in "new" were dismissed
      msg({ title: "Trockner fertig", message: "Die Wäsche im Trockner ist trocken.", state: "delivered", priority: 1,
        origin: "automation.geraete", origin_name: "Haushalt – Geräte melden", since: ago(260), delivered_at: ago(260), reason: "zugestellt" }),
      msg({ title: "Akku schwach: Fenstersensor Bad", message: "Der Akku des Fenstersensors im Bad steht bei 9 %.", state: "delivered", priority: 1,
        origin: "automation.geraete", origin_name: "Haushalt – Geräte melden", since: ago(610), delivered_at: ago(610), reason: "zugestellt" }),
      msg({ title: "Sicherung abgeschlossen", message: "Die nächtliche Sicherung ist in 4 min durchgelaufen.", state: "discarded", priority: 1,
        origin: "automation.sicherung", origin_name: "Server – Sicherung", kind: "Sicherung", group: "Server", since: ago(1130),
        reason: "verworfen durch Regel" }),
    ],
  };

  const overview: Overview = {
    ready: true, ready_reason: "ready", open: 2, waiting: 1, disturbed: 1, new: 2, active_rules: 1, delivered_today: 5,
    last_delivery: { at: ago(114), origin: "Sicherheit – Wasser", title: "Wassermelder Keller" }, recipients: 2, missing_recipients: [],
    unknown: [
      // an automation with one message ...
      { origin: "automation.waschmaschine", origin_name: "Haushalt – Waschmaschine", labels: [], title: "Waschmaschine fertig", count: 3,
        first_seen: ago(300), last_seen: ago(76), multiple: false },
      // ... and one with several
      { origin: "automation.geraete", origin_name: "Haushalt – Geräte melden", labels: [], title: "Akku schwach: Rauchmelder Flur", count: 1,
        first_seen: ago(95), last_seen: ago(95), multiple: true },
    ],
    language: "de", alarm_active: false, alarm_until: null,
  };

  const config: Config = {
    groups: [{ id: "g1", name: "Klima", icon: "mdi:thermometer", priority: 1, spacing: 60, expires_after: 0 },
      { id: "g2", name: "Server", icon: "mdi:server", priority: 1, spacing: 0, expires_after: 0 }],
    kinds: [
      kindOf({ id: "k1", name: "Feuchte", title_mode: "prefix", title_value: "Feuchte", group_id: "g1", spacing: 60 }),
      kindOf({ id: "k2", name: "Fenster offen", origin: "automation.fenster", title_value: "Fenster offen", group_id: "g1", priority: 2,
        expires_after: 120, ties: ["Fenster lange offen"] }),
      kindOf({ id: "k3", name: "Frostschutz", title_mode: "contains", title_value: "Frost", group_id: "g1", priority: 3, no_hold: true }),
      kindOf({ id: "k4", name: "Sicherung", origin: "automation.sicherung", title_mode: "prefix", title_value: "Sicherung", group_id: "g2", active: false }),
      kindOf({ id: "k5", name: "Wasseralarm", origin: "automation.wasser", title_mode: "any", priority: 3 }),
      // its automation was deleted
      kindOf({ id: "k6", name: "Garagentor offen", origin: "automation.garagentor_alt", title_mode: "any", priority: 2, orphan: true }),
    ],
    rules: [
      { id: "r1", name: "Nachtmodus", entity_id: "input_boolean.nachtruhe", state: "on", effect_1: "hold", effect_2: "hold", effect_3: "pass", max_hours: 12,
        current_state: "on", active: true, since: ago(120), until: nightUntil, expired: false, unknown: false },
      { id: "r2", name: "Urlaub", entity_id: "input_boolean.urlaub", state: "on", effect_1: "discard", effect_2: "hold", effect_3: "pass", max_hours: 168,
        current_state: "off", active: false, since: null, until: null, expired: false, unknown: false },
    ],
    recipients: [
      { action: "mobile_app_handy_alex", name: "Handy Alex", platform: "android", type: "mobile_app", configured: true, available: true, last_error: null },
      { action: "mobile_app_tablet_kueche", name: "Tablet Küche", platform: "ios", type: "mobile_app", configured: true, available: true,
        last_error: { error: "Timeout", at: ago(70), message_id: exampleId("Waschmaschine fertig") } },
    ],
    origins: [{ entity_id: "automation.feuchte", name: "Klima – Feuchte überwachen" }, { entity_id: "automation.fenster", name: "Klima – Fenster überwachen" },
      { entity_id: "automation.geraete", name: "Haushalt – Geräte melden" }, { entity_id: "automation.sicherung", name: "Server – Sicherung" },
      { entity_id: "automation.waschmaschine", name: "Haushalt – Waschmaschine" }, { entity_id: "automation.wasser", name: "Sicherheit – Wasser" }],
    options: { guide_dismissed: true },
  };

  const scan: ScanResult = {
    found: [
      // two calls without a title: one message, called after the automation
      scanItem({ first_line: "Feuchte im Bad hoch", suggestion: { mode: "any" }, line: 118 }),
      scanItem({ first_line: "Feuchte im Bad wieder normal", suggestion: { mode: "any" }, line: 164 }),
      scanItem({ entity_id: "automation.fenster", name: "Klima – Fenster überwachen", origin: "automation.fenster", file: "packages/fenster.yaml", line: 77,
        title: "Fenster offen", suggestion: { mode: "exact", value: "Fenster offen" }, multiple: true, kind: "Fenster offen" }),
      scanItem({ entity_id: "automation.fenster", name: "Klima – Fenster überwachen", origin: "automation.fenster", file: "packages/fenster.yaml", line: 131,
        title: "Raum {{ raum }}: Fenster lange offen", title_template: true, suggestion: { mode: "prefix", value: "Raum" }, multiple: true }),
      scanItem({ entity_id: "automation.muellabfuhr", name: "Haushalt – Müllabfuhr", origin: "automation.muellabfuhr", file: "automations.yaml", line: 42,
        edit_url: "/config/automation/edit/1759", service: "notify.message_center", target: "notify.message_center", status: "center",
        title: "Müllabfuhr morgen", suggestion: { mode: "any" }, kind: "Müllabfuhr" }),
      scanItem({ source: "script", entity_id: "script.sag_bescheid", name: "Sag Bescheid", origin: null, file: "scripts.yaml", line: 9,
        edit_url: "/config/script/edit/sag_bescheid", service: "notify.mobile_app_handy_alex", target: "notify.mobile_app_handy_alex",
        title: "{{ titel }}", title_template: true, suggestion: null }),
    ],
    files: [
      // a hit names the actions found in the line, never the line itself
      { file: "appdaemon/apps/muell.py", line: 31, text: "notify.mobile_app_handy_alex", status: "direct" },
      { file: "configuration.yaml", line: 58, text: "notify.message_center", status: "center" },
    ],
    counts: { automations: 23, scripts: 4, files: 18, direct: 5 },
  };

  const sent: Record<string, OriginMessages> = {
    "automation.waschmaschine": sends({ titles: ["Waschmaschine fertig"], seen_titles: ["Waschmaschine fertig"] }),
    "automation.geraete": sends({ titles: ["Trockner fertig", ["Akku schwach: {{ geraet }}", "Akku schwach: …"]],
      seen_titles: ["Akku schwach: Rauchmelder Flur", "Trockner fertig", "Akku schwach: Fenstersensor Bad"] }),
    "automation.fenster": sends({ titles: ["Fenster offen", ["Raum {{ raum }}: Fenster lange offen", "Raum …: Fenster lange offen"]],
      seen_titles: ["Fenster offen"] }),
    "automation.feuchte": sends({ source: "direct", messages: [{ title: null, template: false, display: "Klima – Feuchte überwachen" }],
      seen_titles: ["Feuchte hoch: Bad"] }),
    "automation.sicherung": sends({ titles: ["Sicherung abgeschlossen"], seen_titles: ["Sicherung abgeschlossen"] }),
    "automation.wasser": sends({ titles: ["Wassermelder Keller"], seen_titles: ["Wassermelder Keller"] }),
  };

  return { messages, overview, config, scan, sends: sent, sent: ["Handy Alex", "Tablet Küche"], nightEntity: "input_boolean.nachtruhe" };
};

/** The same cases in English: neutral names, nothing of a real home. */
const englishExample = (): Example => {
  const nightUntil = inMin(600);
  const messages: Messages = {
    open: [
      msg({ title: "Humidity high: Bathroom", message: "Humidity in the bathroom above 70 % for 30 min. Please ventilate.", state: "waiting", priority: 1,
        origin: "automation.humidity", origin_name: "Climate – Watch humidity", kind: "Humidity", group: "Climate", since: ago(42),
        reason: `held back: Night mode until ${enStamp(nightUntil)}` }),
      msg({ title: "Washing machine done", message: "The laundry can be taken out.", state: "retrying", priority: 2, count: 3,
        origin: "automation.washing_machine", origin_name: "Household – Washing machine", since: ago(76), reason: "delivery failed, next attempt",
        next_try: inMin(9), failed_recipients: ["Kitchen tablet"] }),
    ],
    recent: [
      msg({ title: "Water leak basement", message: "Water detected on the floor. Please check right away.", state: "delivered", priority: 3,
        origin: "automation.water", origin_name: "Safety – Water", kind: "Water alarm", group: "Safety", since: ago(114), delivered_at: ago(114),
        reason: "delivered",
        events: [{ at: ago(114), kind: "alarm_light", source: "center", detail: "light.hallway, light.kitchen, light.basement" },
          { at: ago(113), kind: "snoozed", source: "phone", detail: "30 min" },
          { at: ago(111), kind: "forwarded", source: "page", detail: "What should I do?" }] }),
      msg({ title: "Window open", message: "The office window has been open for 20 min, it is 4 °C outside.", state: "delivered", priority: 2,
        origin: "automation.window", origin_name: "Climate – Watch windows", kind: "Window open", group: "Climate", since: ago(190),
        delivered_at: ago(190), reason: "delivered",
        events: [{ at: ago(190), kind: "light", source: "center", detail: "light.hallway, light.kitchen" }] }),
      // what the appliance automation sent before; its entries in "new" were dismissed
      msg({ title: "Dryer done", message: "The laundry in the dryer is dry.", state: "delivered", priority: 1,
        origin: "automation.appliances", origin_name: "Household – Appliances", since: ago(260), delivered_at: ago(260), reason: "delivered" }),
      msg({ title: "Battery low: Bathroom window sensor", message: "The battery of the bathroom window sensor is at 9 %.", state: "delivered",
        priority: 1, origin: "automation.appliances", origin_name: "Household – Appliances", since: ago(610), delivered_at: ago(610), reason: "delivered" }),
      msg({ title: "Backup finished", message: "The nightly backup completed in 4 min.", state: "discarded", priority: 1,
        origin: "automation.backup", origin_name: "Server – Backup", kind: "Backup", group: "Server", since: ago(1130), reason: "discarded by rule" }),
    ],
  };

  const overview: Overview = {
    ready: true, ready_reason: "ready", open: 2, waiting: 1, disturbed: 1, new: 2, active_rules: 1, delivered_today: 5,
    last_delivery: { at: ago(114), origin: "Safety – Water", title: "Water leak basement" }, recipients: 2, missing_recipients: [],
    unknown: [
      { origin: "automation.washing_machine", origin_name: "Household – Washing machine", labels: [], title: "Washing machine done", count: 3,
        first_seen: ago(300), last_seen: ago(76), multiple: false },
      { origin: "automation.appliances", origin_name: "Household – Appliances", labels: [], title: "Battery low: Hallway smoke detector", count: 1,
        first_seen: ago(95), last_seen: ago(95), multiple: true },
    ],
    language: "en", alarm_active: false, alarm_until: null,
  };

  const config: Config = {
    groups: [{ id: "g1", name: "Climate", icon: "mdi:thermometer", priority: 1, spacing: 60, expires_after: 0 },
      { id: "g2", name: "Server", icon: "mdi:server", priority: 1, spacing: 0, expires_after: 0 }],
    kinds: [
      kindOf({ id: "k1", name: "Humidity", title_mode: "prefix", title_value: "Humidity", group_id: "g1", spacing: 60 }),
      kindOf({ id: "k2", name: "Window open", origin: "automation.window", title_value: "Window open", group_id: "g1", priority: 2,
        expires_after: 120, ties: ["Window open long"] }),
      kindOf({ id: "k3", name: "Frost protection", title_mode: "contains", title_value: "Frost", group_id: "g1", priority: 3, no_hold: true }),
      kindOf({ id: "k4", name: "Backup", origin: "automation.backup", title_mode: "prefix", title_value: "Backup", group_id: "g2", active: false }),
      kindOf({ id: "k5", name: "Water alarm", origin: "automation.water", title_mode: "any", priority: 3 }),
      kindOf({ id: "k6", name: "Garage door open", origin: "automation.old_garage_door", title_mode: "any", priority: 2, orphan: true }),
    ],
    rules: [
      { id: "r1", name: "Night mode", entity_id: "input_boolean.night_mode", state: "on", effect_1: "hold", effect_2: "hold", effect_3: "pass", max_hours: 12,
        current_state: "on", active: true, since: ago(120), until: nightUntil, expired: false, unknown: false },
      { id: "r2", name: "Vacation", entity_id: "input_boolean.vacation", state: "on", effect_1: "discard", effect_2: "hold", effect_3: "pass", max_hours: 168,
        current_state: "off", active: false, since: null, until: null, expired: false, unknown: false },
    ],
    recipients: [
      { action: "mobile_app_alex_s_phone", name: "Alex's phone", platform: "android", type: "mobile_app", configured: true, available: true, last_error: null },
      { action: "mobile_app_kitchen_tablet", name: "Kitchen tablet", platform: "ios", type: "mobile_app", configured: true, available: true,
        last_error: { error: "Timeout", at: ago(70), message_id: exampleId("Washing machine done") } },
    ],
    origins: [{ entity_id: "automation.appliances", name: "Household – Appliances" }, { entity_id: "automation.backup", name: "Server – Backup" },
      { entity_id: "automation.humidity", name: "Climate – Watch humidity" }, { entity_id: "automation.washing_machine", name: "Household – Washing machine" },
      { entity_id: "automation.water", name: "Safety – Water" }, { entity_id: "automation.window", name: "Climate – Watch windows" }],
    options: { guide_dismissed: true },
  };

  const found = (o: Partial<ScanResult["found"][number]>) => scanItem({ entity_id: "automation.humidity", name: "Climate – Watch humidity",
    origin: "automation.humidity", target: "notify.send_message → notify.alex_s_phone", file: "packages/bathroom_humidity.yaml", ...o });
  const scan: ScanResult = {
    found: [
      found({ first_line: "Humidity in the bathroom high", suggestion: { mode: "any" }, line: 118 }),
      found({ first_line: "Humidity in the bathroom back to normal", suggestion: { mode: "any" }, line: 164 }),
      found({ entity_id: "automation.window", name: "Climate – Watch windows", origin: "automation.window", file: "packages/windows.yaml", line: 77,
        title: "Window open", suggestion: { mode: "exact", value: "Window open" }, multiple: true, kind: "Window open" }),
      found({ entity_id: "automation.window", name: "Climate – Watch windows", origin: "automation.window", file: "packages/windows.yaml", line: 131,
        title: "Room {{ room }}: window open long", title_template: true, suggestion: { mode: "prefix", value: "Room" }, multiple: true }),
      found({ entity_id: "automation.waste_collection", name: "Household – Waste collection", origin: "automation.waste_collection", file: "automations.yaml", line: 42,
        edit_url: "/config/automation/edit/1759", service: "notify.message_center", target: "notify.message_center", status: "center",
        title: "Waste collection tomorrow", suggestion: { mode: "any" }, kind: "Waste collection" }),
      found({ source: "script", entity_id: "script.let_me_know", name: "Let me know", origin: null, file: "scripts.yaml", line: 9,
        edit_url: "/config/script/edit/let_me_know", service: "notify.mobile_app_alex_s_phone", target: "notify.mobile_app_alex_s_phone",
        title: "{{ title }}", title_template: true, suggestion: null }),
    ],
    files: [
      // a hit names the actions found in the line, never the line itself
      { file: "appdaemon/apps/waste.py", line: 31, text: "notify.mobile_app_alex_s_phone", status: "direct" },
      { file: "configuration.yaml", line: 58, text: "notify.message_center", status: "center" },
    ],
    counts: { automations: 23, scripts: 4, files: 18, direct: 5 },
  };

  const sent: Record<string, OriginMessages> = {
    "automation.washing_machine": sends({ titles: ["Washing machine done"], seen_titles: ["Washing machine done"] }),
    "automation.appliances": sends({ titles: ["Dryer done", ["Battery low: {{ device }}", "Battery low: …"]],
      seen_titles: ["Battery low: Hallway smoke detector", "Dryer done", "Battery low: Bathroom window sensor"] }),
    "automation.window": sends({ titles: ["Window open", ["Room {{ room }}: window open long", "Room …: window open long"]],
      seen_titles: ["Window open"] }),
    "automation.humidity": sends({ source: "direct", messages: [{ title: null, template: false, display: "Climate – Watch humidity" }],
      seen_titles: ["Humidity high: Bathroom"] }),
    "automation.backup": sends({ titles: ["Backup finished"], seen_titles: ["Backup finished"] }),
    "automation.water": sends({ titles: ["Water leak basement"], seen_titles: ["Water leak basement"] }),
  };

  return { messages, overview, config, scan, sends: sent, sent: ["Alex's phone", "Kitchen tablet"], nightEntity: "input_boolean.night_mode" };
};

const { messages, overview, config, scan, sends: sentBy, sent, nightEntity } = en ? englishExample() : germanExample();

const listeners: (() => void)[] = [];
const changed = () => listeners.forEach((l) => l());

// ----- stand-ins for the kind commands: what an automation sends, what a condition matches -----

type Cond = { origin: string | null; title_mode: Kind["title_mode"]; title_value: string };
const RANK = { exact: 3, prefix: 2, contains: 1, any: 0 } as const;

/** As the center compares: origin first, then the title, case aside; "any" needs an automation. */
const fits = (k: Cond, origin: string, title: string) => {
  if (k.origin && k.origin !== origin) return false;
  if (k.title_mode === "any") return !!k.origin && k.origin !== "unknown";
  const hay = title.toLowerCase();
  const needle = k.title_value.toLowerCase();
  return k.title_mode === "exact" ? hay === needle : k.title_mode === "prefix" ? hay.startsWith(needle) : hay.includes(needle);
};

/** Higher wins: a named origin, the stricter comparison, the longer text, the older kind. */
const beats = (a: Cond, aOrder: number, b: Cond, bOrder: number) => {
  const sa = [a.origin ? 1 : 0, RANK[a.title_mode], a.title_value.length, -aOrder];
  const sb = [b.origin ? 1 : 0, RANK[b.title_mode], b.title_value.length, -bOrder];
  for (let i = 0; i < sa.length; i++) if (sa[i] !== sb[i]) return sa[i] > sb[i];
  return false;
};

const conditionKey = (k: Cond) => [k.origin ?? "", k.title_mode, k.title_mode === "any" ? "" : k.title_value.trim().toLowerCase()].join("|");

const originMessages = (origin: string): OriginMessages => sentBy[origin]
  ?? { source: "none", messages: [], seen_titles: [], multiple: false, any_allowed: origin !== "unknown" };

/** A simple copy of message_center/kind_matches over the example data. */
const kindMatches = (m: Record<string, unknown>): KindMatches => {
  const cand: Cond = { origin: (m.origin as string | null) || null, title_mode: m.title_mode as Kind["title_mode"],
    title_value: m.title_mode === "any" ? "" : String(m.title_value ?? "").trim() };
  const empty = { new: [], new_count: 0, seen: [], seen_count: 0, taken_count: 0, overlaps: [], overlap_count: 0, probe: null };
  if (cand.title_mode === "any" ? !cand.origin || cand.origin === "unknown" : !cand.title_value) return { valid: false, ...empty };
  const editing = config.kinds.findIndex((k) => k.id === m.kind_id);
  const order = editing >= 0 ? editing : config.kinds.length;
  const others = config.kinds.map((k, i) => ({ k, i })).filter(({ k }) => k.active && k.id !== m.kind_id);
  const shared = new Map<string, number>();
  let taken = 0;
  const winner = (origin: string, title: string) => {
    let best: { k: Kind | null; c: Cond; i: number } | null = fits(cand, origin, title) ? { k: null, c: cand, i: order } : null;
    for (const { k, i } of others) if (fits(k, origin, title) && (!best || beats(k, i, best.c, best.i))) best = { k, c: k, i };
    return best;
  };
  const check = (pairs: Omit<MatchedPair, "taken_by">[]) => {
    const listed: MatchedPair[] = [];
    for (const p of pairs.filter((x) => fits(cand, x.origin, x.title))) {
      for (const { k } of others) if (fits(k, p.origin, p.title)) shared.set(k.id, (shared.get(k.id) ?? 0) + 1);
      const best = winner(p.origin, p.title);
      const takenBy = best?.k ? { kind_id: best.k.id, name: best.k.name } : null;
      if (takenBy) taken++;
      if (listed.length < 20) listed.push({ ...p, taken_by: takenBy });
    }
    return listed;
  };
  const newPairs = overview.unknown.map((u) => ({ origin: u.origin, origin_name: u.origin_name, title: u.title, count: u.count, last_seen: u.last_seen }));
  const inNew = new Set(newPairs.map((p) => `${p.origin}|${p.title.toLowerCase()}`));
  const seenPairs = [...messages.open, ...messages.recent]
    .filter((e, i, all) => all.findIndex((x) => x.origin === e.origin && x.title.toLowerCase() === e.title.toLowerCase()) === i)
    .filter((e) => !inNew.has(`${e.origin}|${e.title.toLowerCase()}`))
    .map((e) => ({ origin: e.origin, origin_name: e.origin_name, title: e.title, last_seen: e.since }));
  const newListed = check(newPairs);
  const seenListed = check(seenPairs);
  const overlaps = others.filter(({ k }) => shared.get(k.id)).map(({ k, i }) => ({
    kind_id: k.id, name: k.name, winner: beats(cand, order, k, i) ? "this" as const : "other" as const, shared: shared.get(k.id) ?? 0 }));
  const probe = m.probe as { origin: string; title: string } | undefined;
  const best = probe ? winner(probe.origin, probe.title) : null;
  return {
    valid: true, new: newListed, new_count: newPairs.filter((p) => fits(cand, p.origin, p.title)).length,
    seen: seenListed, seen_count: seenPairs.filter((p) => fits(cand, p.origin, p.title)).length, taken_count: taken,
    overlaps, overlap_count: overlaps.length,
    probe: probe ? { matches: fits(cand, probe.origin, probe.title), taken_by: best?.k ? { kind_id: best.k.id, name: best.k.name } : null } : null,
  };
};

/** Save a kind as the center does: a double condition is refused; a new kind takes its pairs out of "new". */
const saveKind = (m: Record<string, unknown>) => {
  const data = m.data as Omit<Kind, "id" | "ties" | "orphan">;
  const double = config.kinds.find((k) => k.id !== m.subentry_id && conditionKey(k) === conditionKey(data));
  if (double) {
    throw { code: "duplicate", message: `the kind ${double.name} has this condition already`, kind_id: double.id, name: double.name };
  }
  const kind = config.kinds.find((k) => k.id === m.subentry_id);
  if (kind) {
    Object.assign(kind, data);
    return kind.id;
  }
  const id = `k${config.kinds.length + 1}`;
  config.kinds.push({ ...data, id, ties: [], orphan: false });
  overview.unknown = overview.unknown.filter((u) => !fits(data, u.origin, u.title));
  overview.new = overview.unknown.length;
  return id;
};

const hass = {
  language: en ? "en" : "de",
  states: { [nightEntity]: { entity_id: nightEntity, state: "on", attributes: {} } },
  user: { is_admin: true, name: "Alex" },
  connection: { subscribeMessage: async (cb: () => void) => { listeners.push(cb); return async () => undefined; } },
  callService: async () => undefined,
  callWS: async (m: Record<string, unknown>) => {
    switch (String(m.type).split("/")[1]) {
      case "overview": return overview;
      case "messages": return messages;
      case "history": return { history: [] };
      case "config": return config;
      case "save": {
        const id = m.kind === "kind" ? saveKind(m) : String(m.subentry_id ?? `g${config.groups.length + 1}`);
        changed();
        return { subentry_id: id };
      }
      case "origin_messages": return originMessages(String(m.origin));
      case "kind_matches": return kindMatches(m);
      case "options": Object.assign(config.options, m.options); changed(); return { options: config.options };
      case "scan": return scan;
      case "test": return { sent, failed: [], lights: [], script: null, script_error: null };
      default: changed(); return {};
    }
  },
};

const wide = html`<div class="frame"><message-center-panel .hass=${hass} .narrow=${false}></message-center-panel></div>`;
const phone = html`<div class="frame phone"><message-center-panel .hass=${hass} .narrow=${true}></message-center-panel></div>`;

if (only) {
  // only the frame, at the top left, without headings
  document.body.style.padding = "0";
  render(html`<style>.frame { margin: 0; }</style>${only === "wide" ? wide : phone}`, document.body);
} else if (en) {
  render(html`
    <h1 class="vtitle">Overview</h1>
    <p class="vintro">The real page with example data. The tabs can be clicked, rows unfolded, message kinds dragged. Forms (edit, settings)
      come from Home Assistant itself and are only hinted at here.</p>
    <section class="v"><div class="v-label"><b>wide</b> as on a computer</div>${wide}</section>
    <section class="v"><div class="v-label"><b>narrow</b> as on a phone</div>${phone}</section>
  `, document.body);
} else {
  render(html`
    <h1 class="vtitle">Gesamtbild</h1>
    <p class="vintro">Die echte Seite mit Beispieldaten. Die Reiter lassen sich anklicken, Zeilen aufklappen, Meldungsarten ziehen.
      Formulare (Bearbeiten, Einstellungen) kommen in Home Assistant von HA selbst und sind hier nur angedeutet.</p>
    <section class="v"><div class="v-label"><b>breit</b> wie am Rechner</div>${wide}</section>
    <section class="v"><div class="v-label"><b>schmal</b> wie am Handy</div>${phone}</section>
  `, document.body);
}
if (en) document.documentElement.lang = "en";

interface KindEditorInside {
  updateComplete: Promise<unknown>;
  _advanced: boolean;
  _data: Record<string, unknown>;
  _condChanged(next: Record<string, unknown>): void;
  _save(): Promise<void>;
}

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** For screenshots: open the kind dialog in one of its states (?kind=…). */
async function kindDemo(panel: HTMLElement & { updateComplete: Promise<unknown>; _openKindEditor(source: unknown): void }, demo: string) {
  const waterOrigin = en ? "automation.water" : "automation.wasser";
  const sources: Record<string, unknown> = {
    one: { from: "new", item: overview.unknown[0] }, advanced: { from: "new", item: overview.unknown[0] },
    many: { from: "new", item: overview.unknown[1] }, edit: { from: "edit", kind: config.kinds[1] },
    switched: { from: "edit", kind: config.kinds[3] },
    blank: { from: "blank" }, duplicate: { from: "blank" }, overlap: { from: "blank" }, scan: { from: "scan", item: scan.found[3] },
  };
  if (!sources[demo]) return;
  panel._openKindEditor(sources[demo]);
  await panel.updateComplete;
  const editor = panel.shadowRoot?.querySelector("message-center-kind-editor") as unknown as KindEditorInside | null;
  if (!editor) return;
  await editor.updateComplete;
  await pause(20);
  if (demo === "advanced") editor._advanced = true;
  if (demo === "duplicate" || demo === "overlap") {
    editor._data = { ...editor._data, name: demo === "duplicate" ? (en ? "Water" : "Wasser") : (en ? "Water anywhere" : "Wasser überall") };
    editor._condChanged(demo === "duplicate"
      ? { origin: waterOrigin, title_mode: "any", title_value: "" }
      : { origin: "", title_mode: "contains", title_value: en ? "water" : "wasser" });
  }
  if (demo === "duplicate") await editor._save();
}

// For screenshots: ?tab=open selects a tab, ?unfold=1 unfolds the first message row, ?kind=… opens the kind dialog.
const tab = params.get("tab") ?? (params.get("kind") ? "kinds" : null);
if (tab) {
  document.querySelectorAll("message-center-panel").forEach((el) => {
    const panel = el as unknown as HTMLElement & { updateComplete: Promise<unknown>; _select(t: string): Promise<void>; _openRows: Set<string>;
      _openKindEditor(source: unknown): void };
    void panel.updateComplete.then(async () => {
      await panel._select(tab);
      if (params.get("scan")) await (panel as unknown as { _runScan(): Promise<void> })._runScan();
      if (params.get("unfold")) panel._openRows = new Set([tab === "open" ? messages.open[0].message_id : messages.recent[0].message_id]);
      const demo = params.get("kind");
      if (demo) {
        // room for the dialog below the page
        panel.style.minHeight = "1500px";
        await kindDemo(panel, demo);
      }
    });
  });
}
