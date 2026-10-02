// Preview of the real page outside Home Assistant, with example data.
// Not part of the shipped page: it provides plain stand-ins for the Home
// Assistant elements the page uses (ha-card, ha-button, ...) and a mock of the
// connection, so that the look can be judged without a running system.
// "npm run preview" bundles it into preview/preview.js; open preview/index.html
// through a local web server.
import { LitElement, css, html, nothing, render } from "lit";
import { property } from "lit/decorators.js";
import "./panel";
import type { Config, MessageEntry, Messages, Overview, ScanResult } from "./types";

// Address parameters, for screenshots:
//   ?lang=en             the page in English with English example data (without it: German)
//   ?only=wide|phone     just the wide or the narrow frame, without the preview's headings
//   ?tab=open&unfold=1   select a tab and unfold the first message row (?scan=1 runs the search on "kinds")
//   ?theme=light         light colours (without it: dark; preview.css holds both)
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
  @property({ attribute: false }) public schema: { name: string; selector: Record<string, unknown> }[] = [];
  @property({ attribute: false }) public data: Record<string, unknown> = {};
  @property({ attribute: false }) public computeLabel?: (f: { name: string }) => string;
  @property({ attribute: false }) public computeHelper?: (f: { name: string }) => string | undefined;
  static styles = css`
    .f { padding: 10px 0; border-top: 1px solid var(--divider-color); display: flex; gap: 12px; align-items: center; }
    .f:first-child { border-top: 0; }
    .l { flex: 1; min-width: 0; } .h { color: var(--secondary-text-color); font-size: 12px; margin-top: 2px; }
    .v { color: var(--secondary-text-color); font-size: 13px; padding: 6px 10px; border-radius: 6px; background: var(--secondary-background-color);
      max-width: 50%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .sw { width: 36px; height: 20px; border-radius: 10px; background: var(--divider-color); position: relative; flex: none; }
    .sw.on { background: color-mix(in srgb, var(--primary-color) 55%, transparent); }
    .sw::after { content: ""; position: absolute; top: 2px; left: 2px; width: 16px; height: 16px; border-radius: 50%; background: var(--secondary-text-color); }
    .sw.on::after { left: 18px; background: var(--primary-color); }
  `;
  render() {
    return html`${this.schema.map((f) => {
      const v = this.data?.[f.name];
      const helper = this.computeHelper?.(f);
      return html`<div class="f"><div class="l"><div>${this.computeLabel?.(f) ?? f.name}</div>${helper ? html`<div class="h">${helper}</div>` : nothing}</div>
        ${"boolean" in f.selector ? html`<span class="sw ${v ? "on" : ""}"></span>`
          : html`<span class="v">${Array.isArray(v) ? `${v.length} ${en ? "selected" : "gewählt"}` : v === "" || v == null ? "–" : String(v)}</span>`}</div>`;
    })}`;
  }
}

for (const [tag, cls] of [["ha-card", Card], ["ha-button", Button], ["ha-icon", Icon], ["ha-menu-button", MenuButton], ["ha-form", Form]] as const) {
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
  /** recipient names a test reaches */
  sent: string[];
  /** the helper the night rule watches */
  nightEntity: string;
}

/** The example data in German. */
const germanExample = (): Example => {
  const nightUntil = inMin(600);
  const messages: Messages = {
    open: [
      msg({ title: "Feuchte hoch: Bad", message: "Luftfeuchte im Bad seit 30 min über 70 %. Bitte lüften.", state: "waiting", priority: 1,
        origin_name: "Klima – Feuchte überwachen", kind: "Feuchte", group: "Klima", since: ago(42), reason: `zurückgehalten: Nachtmodus bis ${deStamp(nightUntil)}` }),
      msg({ title: "Waschmaschine fertig", message: "Die Wäsche kann raus.", state: "retrying", priority: 2, count: 3,
        origin_name: "Haushalt – Waschmaschine", since: ago(76), reason: "Zustellfehler, nächster Versuch", next_try: inMin(9), failed_recipients: ["Tablet Küche"] }),
    ],
    recent: [
      msg({ title: "Wassermelder Keller", message: "Wasser am Boden erkannt. Bitte sofort prüfen.", state: "delivered", priority: 3,
        origin_name: "Sicherheit – Wasser", kind: "Wasseralarm", group: "Sicherheit", since: ago(114), delivered_at: ago(114), reason: "zugestellt",
        events: [{ at: ago(114), kind: "alarm_light", source: "center", detail: "3 Lampen" }, { at: ago(113), kind: "snoozed", source: "phone", detail: "30 min" },
          { at: ago(111), kind: "forwarded", source: "page", detail: "Was tun?" }] }),
      msg({ title: "Fenster offen: Büro", message: "Das Fenster im Büro ist seit 20 min offen, draußen sind es 4 °C.", state: "delivered", priority: 2,
        origin_name: "Klima – Fenster überwachen", kind: "Fenster offen", group: "Klima", since: ago(190), delivered_at: ago(190), reason: "zugestellt",
        events: [{ at: ago(190), kind: "light", source: "center", detail: "light.flur, light.kueche" }] }),
      msg({ title: "Sicherung abgeschlossen", message: "Die nächtliche Sicherung ist in 4 min durchgelaufen.", state: "discarded", priority: 1,
        origin_name: "Server – Sicherung", kind: "Sicherung", group: "Server", since: ago(1130), reason: "verworfen durch Regel" }),
    ],
  };

  const overview: Overview = {
    ready: true, ready_reason: "ready", open: 2, waiting: 1, disturbed: 1, new: 1, active_rules: 1, delivered_today: 5,
    last_delivery: { at: ago(114), origin: "Sicherheit – Wasser", title: "Wassermelder Keller" }, recipients: 2, missing_recipients: [],
    unknown: [{ origin: "automation.waschmaschine", origin_name: "Haushalt – Waschmaschine", labels: [], title: "Waschmaschine fertig", count: 3, first_seen: ago(300), last_seen: ago(76) }],
    language: "de", alarm_active: false, alarm_until: null,
  };

  const config: Config = {
    groups: [{ id: "g1", name: "Klima", icon: "mdi:thermometer", priority: 1, spacing: 60, expires_after: 0 },
      { id: "g2", name: "Server", icon: "mdi:server", priority: 1, spacing: 0, expires_after: 0 }],
    kinds: [
      { id: "k1", name: "Feuchte", origin: null, title_mode: "prefix", title_value: "Feuchte", group_id: "g1", priority: 1, no_hold: false, spacing: 60, expires_after: 0, light: null, active: true, ties: [] },
      { id: "k2", name: "Fenster offen", origin: "automation.fenster", title_mode: "exact", title_value: "Fenster offen", group_id: "g1", priority: 2, no_hold: false, spacing: 0, expires_after: 120, light: null, active: true, ties: ["Fenster lange offen"] },
      { id: "k3", name: "Frostschutz", origin: null, title_mode: "contains", title_value: "Frost", group_id: "g1", priority: 3, no_hold: true, spacing: 0, expires_after: 0, light: null, active: true, ties: [] },
      { id: "k4", name: "Sicherung", origin: "automation.sicherung", title_mode: "prefix", title_value: "Sicherung", group_id: "g2", priority: 1, no_hold: false, spacing: 0, expires_after: 0, light: null, active: false, ties: [] },
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
    origins: [{ entity_id: "automation.fenster", name: "Klima – Fenster überwachen" }, { entity_id: "automation.sicherung", name: "Server – Sicherung" }],
    options: { guide_dismissed: true },
  };

  const scan: ScanResult = {
    found: [
      scanItem({ first_line: "Feuchte im Bad hoch", suggestion: { mode: "exact", value: "Feuchte im Bad hoch" }, line: 118 }),
      scanItem({ first_line: "Feuchte im Bad wieder normal", suggestion: { mode: "exact", value: "Feuchte im Bad wieder normal" }, line: 164 }),
      scanItem({ entity_id: "automation.fenster", name: "Klima – Fenster überwachen", origin: "automation.fenster", file: "packages/fenster.yaml", line: 77,
        title: "Fenster offen", suggestion: { mode: "exact", value: "Fenster offen" }, kind: "Fenster offen" }),
      scanItem({ entity_id: "automation.fenster", name: "Klima – Fenster überwachen", origin: "automation.fenster", file: "packages/fenster.yaml", line: 131,
        title: "Raum {{ raum }}: Fenster lange offen", title_template: true, suggestion: { mode: "prefix", value: "Raum" } }),
      scanItem({ entity_id: "automation.muellabfuhr", name: "Haushalt – Müllabfuhr", origin: "automation.muellabfuhr", file: "automations.yaml", line: 42,
        edit_url: "/config/automation/edit/1759", service: "notify.message_center", target: "notify.message_center", status: "center",
        title: "Müllabfuhr morgen", suggestion: { mode: "exact", value: "Müllabfuhr morgen" }, kind: "Müllabfuhr" }),
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

  return { messages, overview, config, scan, sent: ["Handy Alex", "Tablet Küche"], nightEntity: "input_boolean.nachtruhe" };
};

/** The same cases in English: neutral names, nothing of a real home. */
const englishExample = (): Example => {
  const nightUntil = inMin(600);
  const messages: Messages = {
    open: [
      msg({ title: "Humidity high: Bathroom", message: "Humidity in the bathroom above 70 % for 30 min. Please ventilate.", state: "waiting", priority: 1,
        origin_name: "Climate – Watch humidity", kind: "Humidity", group: "Climate", since: ago(42), reason: `held back: Night mode until ${enStamp(nightUntil)}` }),
      msg({ title: "Washing machine done", message: "The laundry can be taken out.", state: "retrying", priority: 2, count: 3,
        origin_name: "Household – Washing machine", since: ago(76), reason: "delivery failed, next attempt", next_try: inMin(9), failed_recipients: ["Kitchen tablet"] }),
    ],
    recent: [
      msg({ title: "Water leak basement", message: "Water detected on the floor. Please check right away.", state: "delivered", priority: 3,
        origin_name: "Safety – Water", kind: "Water alarm", group: "Safety", since: ago(114), delivered_at: ago(114), reason: "delivered",
        events: [{ at: ago(114), kind: "alarm_light", source: "center", detail: "light.hallway, light.kitchen, light.basement" },
          { at: ago(113), kind: "snoozed", source: "phone", detail: "30 min" },
          { at: ago(111), kind: "forwarded", source: "page", detail: "What should I do?" }] }),
      msg({ title: "Window open: Office", message: "The office window has been open for 20 min, it is 4 °C outside.", state: "delivered", priority: 2,
        origin_name: "Climate – Watch windows", kind: "Window open", group: "Climate", since: ago(190), delivered_at: ago(190), reason: "delivered",
        events: [{ at: ago(190), kind: "light", source: "center", detail: "light.hallway, light.kitchen" }] }),
      msg({ title: "Backup finished", message: "The nightly backup completed in 4 min.", state: "discarded", priority: 1,
        origin_name: "Server – Backup", kind: "Backup", group: "Server", since: ago(1130), reason: "discarded by rule" }),
    ],
  };

  const overview: Overview = {
    ready: true, ready_reason: "ready", open: 2, waiting: 1, disturbed: 1, new: 1, active_rules: 1, delivered_today: 5,
    last_delivery: { at: ago(114), origin: "Safety – Water", title: "Water leak basement" }, recipients: 2, missing_recipients: [],
    unknown: [{ origin: "automation.washing_machine", origin_name: "Household – Washing machine", labels: [], title: "Washing machine done", count: 3, first_seen: ago(300), last_seen: ago(76) }],
    language: "en", alarm_active: false, alarm_until: null,
  };

  const config: Config = {
    groups: [{ id: "g1", name: "Climate", icon: "mdi:thermometer", priority: 1, spacing: 60, expires_after: 0 },
      { id: "g2", name: "Server", icon: "mdi:server", priority: 1, spacing: 0, expires_after: 0 }],
    kinds: [
      { id: "k1", name: "Humidity", origin: null, title_mode: "prefix", title_value: "Humidity", group_id: "g1", priority: 1, no_hold: false, spacing: 60, expires_after: 0, light: null, active: true, ties: [] },
      { id: "k2", name: "Window open", origin: "automation.window", title_mode: "exact", title_value: "Window open", group_id: "g1", priority: 2, no_hold: false, spacing: 0, expires_after: 120, light: null, active: true, ties: ["Window open long"] },
      { id: "k3", name: "Frost protection", origin: null, title_mode: "contains", title_value: "Frost", group_id: "g1", priority: 3, no_hold: true, spacing: 0, expires_after: 0, light: null, active: true, ties: [] },
      { id: "k4", name: "Backup", origin: "automation.backup", title_mode: "prefix", title_value: "Backup", group_id: "g2", priority: 1, no_hold: false, spacing: 0, expires_after: 0, light: null, active: false, ties: [] },
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
    origins: [{ entity_id: "automation.window", name: "Climate – Watch windows" }, { entity_id: "automation.backup", name: "Server – Backup" }],
    options: { guide_dismissed: true },
  };

  const found = (o: Partial<ScanResult["found"][number]>) => scanItem({ entity_id: "automation.humidity", name: "Climate – Watch humidity",
    origin: "automation.humidity", target: "notify.send_message → notify.alex_s_phone", file: "packages/bathroom_humidity.yaml", ...o });
  const scan: ScanResult = {
    found: [
      found({ first_line: "Humidity in the bathroom high", suggestion: { mode: "exact", value: "Humidity in the bathroom high" }, line: 118 }),
      found({ first_line: "Humidity in the bathroom back to normal", suggestion: { mode: "exact", value: "Humidity in the bathroom back to normal" }, line: 164 }),
      found({ entity_id: "automation.window", name: "Climate – Watch windows", origin: "automation.window", file: "packages/windows.yaml", line: 77,
        title: "Window open", suggestion: { mode: "exact", value: "Window open" }, kind: "Window open" }),
      found({ entity_id: "automation.window", name: "Climate – Watch windows", origin: "automation.window", file: "packages/windows.yaml", line: 131,
        title: "Room {{ room }}: window open long", title_template: true, suggestion: { mode: "prefix", value: "Room" } }),
      found({ entity_id: "automation.waste_collection", name: "Household – Waste collection", origin: "automation.waste_collection", file: "automations.yaml", line: 42,
        edit_url: "/config/automation/edit/1759", service: "notify.message_center", target: "notify.message_center", status: "center",
        title: "Waste collection tomorrow", suggestion: { mode: "exact", value: "Waste collection tomorrow" }, kind: "Waste collection" }),
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

  return { messages, overview, config, scan, sent: ["Alex's phone", "Kitchen tablet"], nightEntity: "input_boolean.night_mode" };
};

const { messages, overview, config, scan, sent, nightEntity } = en ? englishExample() : germanExample();

const listeners: (() => void)[] = [];
const changed = () => listeners.forEach((l) => l());

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
        // enough to try dragging a kind into another group
        const kind = config.kinds.find((k) => k.id === m.subentry_id);
        if (m.kind === "kind" && kind) Object.assign(kind, m.data);
        changed();
        return { subentry_id: String(m.subentry_id ?? "neu") };
      }
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

// For screenshots: ?tab=open selects a tab, ?unfold=1 unfolds the first message row.
const tab = params.get("tab");
if (tab) {
  document.querySelectorAll("message-center-panel").forEach((el) => {
    const panel = el as unknown as { updateComplete: Promise<unknown>; _select(t: string): Promise<void>; _openRows: Set<string> };
    void panel.updateComplete.then(async () => {
      await panel._select(tab);
      if (params.get("scan")) await (panel as unknown as { _runScan(): Promise<void> })._runScan();
      if (params.get("unfold")) panel._openRows = new Set([tab === "open" ? messages.open[0].message_id : messages.recent[0].message_id]);
    });
  });
}
