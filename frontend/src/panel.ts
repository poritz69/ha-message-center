import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";
import { keyed } from "lit/directives/keyed.js";
import {
  deleteEntry, dismissUnknown, ensureHaElements, fetchConfig, fetchHistory, fetchMessages, fetchOverview,
  alarmOff, messageAction, saveEntry, saveOptions, scanHouse, sendTest, setRecipients, subscribe,
} from "./api";
import { makeT, type Translate } from "./i18n";
import type {
  Config, Group, HomeAssistant, Kind, MessageEntry, Messages, Options, Overview, Rule, ScanItem, ScanResult, Tab, UnknownItem,
} from "./types";
import { logoMark } from "./brand";
import "./editor";
import "./flow";
import "./kind-editor";
import "./mode-help";
import { conditionLabel, fill, forOrigin, type KindSource } from "./kind-logic";
import { readDeepLink, resolveDeepLink, rowKey, withoutDeepLink } from "./deep-link";
import { dateTime, endedAt, readOrder, sortByEnd, storeOrder, type HistoryOrder } from "./history";
import { icon } from "./icons";
import { ruleWithSwitch } from "./rule-logic";
import { scanNote } from "./scan-logic";
import { lightRows, optionsPayload, settingsChanged, withAlways, withDefaults, withLight, withoutLight, type LightRow } from "./settings-logic";
import type { Field, FormData } from "./editor";

const TABS: Tab[] = ["overview", "open", "history", "kinds", "rules", "recipients", "settings"];
const TAB_ICON: Record<Tab, string> = { overview: "grid", open: "inbox", history: "history", kinds: "tag", rules: "moon", recipients: "phone", settings: "sliders" };
const STATE_ICON: Record<string, string> = { waiting: "clock", sending: "send", retrying: "retry", unclear: "alert", delivered: "check", failed: "alert", discarded: "ban" };
const EFFECT_ICON: Record<string, string> = { hold: "pause", pass: "arrow", discard: "trash" };

interface Editor {
  heading: string;
  fields: Field[];
  labels: Record<string, string>;
  helpers?: Record<string, string>;
  data: FormData;
  onSave: (data: FormData) => Promise<void>;
  onChange?: (next: FormData, prev: FormData) => FormData;
  /** Content above the fields; `update` changes the dialog's data (see editor.ts). */
  extra?: (update: (change: (data: FormData) => FormData) => void) => unknown;
}

export class MessageCenterPanel extends LitElement {
  @property({ attribute: false }) public hass!: HomeAssistant;
  @property({ type: Boolean }) public narrow = false;
  @state() private _tab: Tab = "overview";
  @state() private _overview?: Overview;
  @state() private _messages?: Messages;
  @state() private _history?: MessageEntry[];
  @state() private _config?: Config;
  @state() private _error = "";
  @state() private _editor?: Editor;
  /** How the dialog for a message kind was opened; undefined while it is closed. */
  @state() private _kindSource?: KindSource;
  @state() private _filterGroup = "";
  @state() private _filterKind = "";
  @state() private _search = "";
  /** Order of the history's tables, remembered in this browser. */
  @state() private _order: HistoryOrder = readOrder();
  /** Working copy of the options on the settings tab; the page owns it, so refreshes never reset it. */
  @state() private _settings?: Options;
  @state() private _settingsNote = "";
  /** Counts the lamps added; a new count gives a new, empty picker (Home Assistant's keeps what was picked). */
  @state() private _lampAddRound = 0;
  @state() private _testNote = "";
  /** A short note above the tab, such as for a link to a message that is gone; cleared on the next tab. */
  @state() private _notice = "";
  /** Id of the kind being dragged and the card it hovers. */
  @state() private _dragKind = "";
  @state() private _dropTarget = "";
  /** Rows (`rowKey`: id and generation) that are unfolded; kept here so that refreshes do not fold them. */
  @state() private _openRows = new Set<string>();
  /** Result of the search over the house; shown on the kinds tab until closed. */
  @state() private _scan?: ScanResult;
  @state() private _scanBusy = false;
  @state() private _scanAll = false;
  private _unsub?: () => Promise<void>;
  private _t: Translate = makeT("en");
  private _lang = "";

  static styles = css`
    :host { display: block; height: 100%; container-type: inline-size;
      background: var(--primary-background-color); color: var(--primary-text-color);
      /* state colours as text: mixed with the text colour so that they stay readable on light and dark cards */
      --mc-warn: color-mix(in srgb, var(--warning-color) 62%, var(--primary-text-color));
      --mc-bad: color-mix(in srgb, var(--error-color) 70%, var(--primary-text-color));
      --mc-good: color-mix(in srgb, var(--success-color, #43a047) 70%, var(--primary-text-color)); }
    .ico { flex: none; display: block; }
    /* Head: the band is a speech bubble like the logo: round lower corners and a tail under the logo,
       with a thin lighter line along its lower edge. */
    header { position: relative; padding: 0 0 20px; background: var(--card-background-color);
      --mc-band: color-mix(in srgb, var(--primary-color) 64%, #000);
      --mc-line: color-mix(in srgb, var(--primary-color) 70%, #fff); }
    header .bubble { position: relative; display: flex; align-items: center; gap: 14px; min-height: 88px; box-sizing: border-box;
      padding: 10px 20px 10px 64px; border-radius: 0 0 24px 24px; color: #fff;
      background: linear-gradient(color-mix(in srgb, var(--primary-color) 84%, #000), var(--mc-band)); box-shadow: 0 4px 0 var(--mc-line); }
    header ha-menu-button { position: absolute; left: 8px; top: 50%; transform: translateY(-50%); color: #fff; }
    header .mc-logo { color: #fff; flex: none; }
    header .titles { min-width: 0; }
    header h1 { font-size: 28px; font-weight: 300; line-height: 1.15; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    header h1 b { font-weight: 600; }
    header .tag { margin-top: 2px; font-size: 13px; color: rgba(255, 255, 255, .88); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    header .ready { margin-left: auto; flex: none; display: inline-flex; align-items: center; gap: 7px;
      padding: 3px 11px 3px 4px; border-radius: 13px; background: rgba(255, 255, 255, .2); font-size: 13px; font-weight: 500; line-height: 1.3; }
    header .ready .led { display: grid; place-items: center; width: 18px; height: 18px; border-radius: 50%; background: var(--success-color, #43a047); }
    header .ready.off .led { background: var(--error-color); }
    /* the tail: same fill as the band's lower edge; its outline continues the lighter line */
    header .tail { position: absolute; left: 74px; top: 88px; width: 38px; height: 22px; display: block; overflow: hidden; }
    header .tail path { fill: var(--mc-band); stroke: var(--mc-line); stroke-width: 8; stroke-linejoin: round; paint-order: stroke; }
    /* Tabs: icon and name; on narrow screens the seven icons only, the active name in a line below. */
    nav { display: flex; align-items: stretch; gap: 4px; padding: 0 10px; overflow-x: auto; scrollbar-width: none;
      background: var(--card-background-color); border-bottom: 1px solid var(--divider-color); }
    nav::-webkit-scrollbar { display: none; }
    nav button { position: relative; display: inline-flex; align-items: center; gap: 8px; flex: none; padding: 11px 12px; border: 0;
      background: none; color: var(--secondary-text-color); font: inherit; line-height: 20px; white-space: nowrap; cursor: pointer; }
    nav button.active { color: var(--primary-text-color); font-weight: 500; }
    nav button.active .ico { color: color-mix(in srgb, var(--primary-color) 72%, var(--primary-text-color)); }
    nav button.active::after { content: ""; position: absolute; left: 10px; right: 10px; bottom: 0; height: 3px;
      border-radius: 3px 3px 0 0; background: var(--primary-color); }
    nav .ib { position: relative; display: inline-flex; }
    nav .cnt { box-sizing: border-box; min-width: 18px; height: 18px; padding: 0 5px; border-radius: 9px; font-size: 11.5px; font-weight: 500;
      line-height: 18px; text-align: center; background: color-mix(in srgb, var(--primary-color) 24%, transparent); color: var(--primary-text-color); }
    nav .ib .cnt { display: none; }
    .navcap { display: none; }
    main { padding: 16px; max-width: 1100px; margin: 0 auto; box-sizing: border-box; }
    /* Overview: two groups of numbers, "now" and "operation", each with a coloured top edge for its state. */
    .groups { display: grid; grid-template-columns: minmax(0, 4fr) minmax(0, 3fr); gap: 12px; margin-bottom: 16px; }
    .kgroup { min-width: 0; padding: 14px 4px 12px; background: var(--card-background-color); border: 1px solid var(--divider-color);
      border-radius: var(--ha-card-border-radius, 12px); overflow: hidden; box-shadow: inset 0 3px 0 var(--divider-color); }
    .kgroup.warn { box-shadow: inset 0 3px 0 var(--warning-color); }
    .kgroup.bad { box-shadow: inset 0 3px 0 var(--error-color); }
    .kgroup.good { box-shadow: inset 0 3px 0 var(--success-color, #43a047); }
    .kgroup h2 { margin: 0 0 10px; padding: 0 12px; font-size: 12px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; }
    .kgroup h2 span { margin-left: 6px; font-weight: 400; letter-spacing: 0; text-transform: none; color: var(--secondary-text-color); }
    .kpis { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); }
    .kpi { padding: 2px 12px; border-left: 1px solid var(--divider-color); min-width: 0; }
    .kpi:first-child { border-left: 0; }
    .kpi .value { font-size: 28px; font-weight: 500; line-height: 1.1; }
    .kpi .label { color: var(--secondary-text-color); font-size: 13px; margin-top: 4px; }
    .kpi.warn .value { color: var(--mc-warn); }
    .kpi.bad .value { color: var(--mc-bad); }
    .kpi.good .value { color: var(--mc-good); }
    .kpi.zero .value { color: var(--secondary-text-color); }
    .pair { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 0 12px; align-items: start; }
    /* Messages: a compact table, one line per message; a click unfolds text, reason, events and buttons. */
    .mtable { --mc-time: 92px; }
    /* the history shows date and time of the end, always */
    .mtable.ended { --mc-time: 118px; }
    .mtable .thead, .mtable summary { display: grid; grid-template-columns: 34px 128px minmax(0, 1fr) minmax(0, 240px) var(--mc-time) 18px;
      column-gap: 12px; align-items: center; padding: 0 12px 0 14px; }
    .mtable .thead { height: 32px; font-size: 12px; color: var(--secondary-text-color); border-bottom: 1px solid var(--divider-color); }
    .mtable details { border-top: 1px solid var(--divider-color); --st: var(--secondary-text-color); --lvl: var(--primary-color); --lvl-on: #fff; }
    .mtable .thead + details { border-top: 0; }
    .mtable summary { min-height: 44px; cursor: pointer; list-style: none; }
    .mtable summary::-webkit-details-marker { display: none; }
    .mtable summary:hover, .mtable details[open] { background: color-mix(in srgb, var(--primary-text-color) 5%, transparent); }
    .mtable details.s-wait { --st: var(--warning-color); }
    .mtable details.s-fail { --st: var(--error-color); }
    .mtable details.s-ok { --st: var(--success-color, #43a047); }
    .mtable details.l2, .fx-i.l2 { --lvl: var(--warning-color); --lvl-on: #000; }
    .mtable details.l3, .fx-i.l3 { --lvl: var(--error-color); --lvl-on: #fff; }
    .lvbox { display: grid; place-items: center; width: 22px; height: 22px; border-radius: 6px; background: var(--lvl, var(--primary-color));
      color: var(--lvl-on, #fff); font-size: 13px; font-weight: 600; line-height: 1; flex: none; }
    .stc { display: flex; align-items: center; gap: 6px; min-width: 0; font-size: 13px; font-weight: 500;
      color: color-mix(in srgb, var(--st) 55%, var(--primary-text-color)); }
    .stc span, .why b { text-transform: lowercase; }
    .line { display: flex; align-items: baseline; gap: 8px; min-width: 0; white-space: nowrap; }
    .line .title { flex: 0 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; font-weight: 500; }
    .line .cnt { flex: none; font-size: 12px; font-weight: 500; padding: 0 7px; border-radius: 9px; background: var(--secondary-background-color); }
    .snip { flex: 1 1 0; min-width: 0; overflow: hidden; text-overflow: ellipsis; color: var(--secondary-text-color); }
    .org { min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 13px; color: var(--secondary-text-color); }
    .time { text-align: right; font-size: 13px; font-variant-numeric: tabular-nums; color: var(--secondary-text-color); white-space: nowrap; }
    .chev { display: inline-flex; color: var(--secondary-text-color); transition: transform .15s; }
    details[open] > summary .chev { transform: rotate(90deg); }
    .more { display: flex; flex-wrap: wrap; gap: 12px 32px; padding: 4px 16px 14px 60px; }
    .more-l { flex: 1 1 280px; min-width: 0; }
    .more .text { white-space: pre-wrap; word-break: break-word; }
    .why { display: flex; align-items: flex-start; gap: 6px; margin-top: 6px; font-size: 13px; overflow-wrap: anywhere;
      color: color-mix(in srgb, var(--st) 55%, var(--primary-text-color)); }
    .why .ico { margin-top: 2px; }
    .why b { font-weight: 600; }
    .fail { color: var(--mc-bad); }
    .more .events { margin-top: 8px; font-size: 12px; color: var(--secondary-text-color); border-left: 2px solid var(--divider-color); padding-left: 8px; }
    .more .actions { justify-content: flex-start; margin: 8px 0 0 -8px; gap: 2px; }
    .dl { flex: 0 1 330px; display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 3px 14px; align-content: start; margin: 0; font-size: 13px; }
    .dl dt { color: var(--secondary-text-color); }
    .dl dd { margin: 0; overflow-wrap: anywhere; }
    /* Search over the house: places that notify, grouped by automation or script. */
    .scan-ico { display: inline-flex; flex: none; color: var(--primary-color); }
    .scan code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12.5px; overflow-wrap: anywhere; }
    .scan-head { margin: 0 16px 10px; padding: 10px 12px; border-radius: 8px; font-weight: 500; line-height: 1.4;
      background: color-mix(in srgb, var(--warning-color) 16%, transparent); border: 1px solid color-mix(in srgb, var(--warning-color) 45%, transparent); }
    .scan-head.done { background: color-mix(in srgb, var(--success-color, #43a047) 16%, transparent);
      border-color: color-mix(in srgb, var(--success-color, #43a047) 45%, transparent); }
    .scan-all { display: flex; gap: 8px; align-items: center; padding: 0 16px 12px; font-size: 13px; color: var(--secondary-text-color); cursor: pointer; }
    .scan-src { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; padding: 10px 16px; border-top: 1px solid var(--divider-color);
      background: color-mix(in srgb, var(--primary-text-color) 4%, transparent); }
    .scan-src b { font-weight: 500; font-size: 15px; }
    .scan-src .where { color: var(--secondary-text-color); font-size: 13px; }
    .scan-src a { font-size: 13px; margin-left: auto; }
    .scan-todo { color: var(--mc-warn); }
    .scan-note { padding: 8px 16px 12px; color: var(--secondary-text-color); font-size: 13px; }
    .chip.scan-direct { background: var(--warning-color); color: #000; }
    .chip.scan-center { background: var(--success-color, #43a047); color: #fff; }
    /* Kinds and rules: grip for dragging, effect per priority as three small fields. */
    .grip { display: inline-grid; place-items: center; flex: none; align-self: center; color: var(--secondary-text-color); cursor: grab; opacity: .75; }
    .fx { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 7px; }
    .fx-i { display: inline-flex; align-items: center; gap: 6px; padding: 3px 9px 3px 4px; border-radius: 8px; font-size: 13px;
      --lvl: var(--primary-color); --lvl-on: #fff;
      background: color-mix(in srgb, var(--lvl) 14%, transparent); border: 1px solid color-mix(in srgb, var(--lvl) 40%, transparent); }
    .fx-i .lvbox { width: 20px; height: 20px; font-size: 12px; font-weight: 700; }
    /* Seven tabs with names need about 900 px. Below that: icons only, the active name in a line below. */
    @container (max-width: 920px) {
      nav { gap: 0; padding: 0 4px; }
      nav button { flex: 1 1 0; justify-content: center; padding: 12px 0; }
      nav .lbl, nav button > .cnt { display: none; }
      nav .ib .cnt { display: block; position: absolute; top: -6px; right: -9px; min-width: 16px; height: 16px; padding: 0 4px; border-radius: 8px;
        font-size: 10.5px; font-weight: 600; line-height: 16px; background: var(--primary-color); color: #fff;
        box-shadow: 0 0 0 2px var(--card-background-color); }
      .navcap { display: block; padding: 7px 16px; border-bottom: 1px solid var(--divider-color); background: var(--card-background-color);
        font-size: 13px; color: var(--secondary-text-color); }
      .navcap b { font-weight: 500; color: var(--primary-text-color); }
    }
    @container (max-width: 600px) {
      header { padding-bottom: 17px; }
      header .bubble { gap: 10px; min-height: 64px; padding: 8px 12px 8px 50px; border-radius: 0 0 18px 18px; box-shadow: 0 3px 0 var(--mc-line); }
      header ha-menu-button { left: 4px; }
      header h1 { font-size: 20px; }
      header .mc-logo { width: 40px; height: 40px; }
      header .tag { display: none; }
      header .tail { left: 55px; top: 64px; width: 30px; height: 18px; }
      header .tail path { stroke-width: 6; }
      .groups, .pair { grid-template-columns: minmax(0, 1fr); }
      .kpi { padding: 2px 10px; }
      .kpi .value { font-size: 24px; }
      .kpi .label { font-size: 12px; }
      .mtable .thead { display: none; }
      .mtable details:first-of-type { border-top: 0; }
      .mtable summary { grid-template-columns: 22px 18px minmax(0, 1fr) auto 18px; column-gap: 8px; align-items: start; padding: 10px 10px 10px 12px; }
      .stc { padding-top: 2px; }
      .stc span, .org { display: none; }
      .line { flex-wrap: wrap; gap: 0 6px; }
      .line .title { max-width: 100%; }
      .snip { flex: 1 1 100%; }
      .time { padding-top: 2px; }
      .chev { margin-top: 2px; }
      .more { padding: 2px 12px 12px 12px; }
    }
    ha-card { margin-bottom: 16px; }
    /* Rows and group heads wrap on narrow screens: text keeps a readable width, buttons drop below. */
    .row { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: flex-start; padding: 12px 16px; border-top: 1px solid var(--divider-color); }
    .row:first-of-type { border-top: 0; }
    .row .body { flex: 1 1 16em; min-width: 0; }
    .row .title { font-weight: 500; }
    .row .meta { color: var(--secondary-text-color); font-size: 13px; margin-top: 2px; word-break: break-word; }
    .row .text { margin-top: 4px; white-space: pre-wrap; word-break: break-word; }
    .row .events { margin-top: 6px; font-size: 12px; color: var(--secondary-text-color); border-left: 2px solid var(--divider-color); padding-left: 8px; }
    .actions { display: flex; flex-wrap: wrap; gap: 4px; justify-content: flex-end; margin-left: auto; }
    .group-head { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; padding: 12px 16px; }
    .group-head ha-icon { color: var(--primary-color); flex: none; }
    .group-head .body { flex: 1 1 14em; min-width: 0; }
    .group-head .title { font-size: 16px; font-weight: 500; }
    .group-head .meta { color: var(--secondary-text-color); font-size: 13px; margin-top: 2px; word-break: break-word; }
    .chip { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 12px; margin-right: 4px;
      background: var(--secondary-background-color); color: var(--primary-text-color); }
    .chip.p1 { background: var(--primary-color); color: #fff; }
    .chip.p2 { background: var(--warning-color); color: #000; }
    .chip.p3 { background: var(--error-color); color: #fff; }
    .chip.state-waiting, .chip.state-retrying, .chip.state-unclear { background: var(--warning-color); color: #000; }
    .chip.state-failed { background: var(--error-color); color: #fff; }
    .chip.state-delivered { background: var(--success-color, #43a047); color: #fff; }
    .alarm-bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; padding: 10px 16px; margin-bottom: 12px;
      background: var(--error-color); color: #fff; border-radius: var(--ha-card-border-radius, 12px); font-weight: 500; }
    .alarm-bar span { flex: 1; }
    .empty { padding: 16px; color: var(--secondary-text-color); }
    .intro { color: var(--secondary-text-color); font-size: 14px; line-height: 1.4; margin: 0 0 12px; }
    .row[draggable="true"] { cursor: grab; }
    /* an orphaned kind: its automation is gone; greyed out, still deletable */
    .row.orphan .body, .row.orphan .grip { opacity: .55; }
    .chip.orphan { background: transparent; border: 1px dashed currentColor; color: var(--secondary-text-color); }
    .row.dragging { opacity: .5; }
    ha-card.drop-target { outline: 2px dashed var(--primary-color); outline-offset: -2px; }
    .level { display: flex; gap: 12px; align-items: flex-start; padding: 12px 16px; border-top: 1px solid var(--divider-color); }
    .level:first-of-type { border-top: 0; }
    .level .chip { flex: none; margin-top: 2px; }
    .level .name { font-weight: 500; }
    .level .effect { color: var(--secondary-text-color); font-size: 13px; margin-top: 2px; }
    /* the text takes what is left, so "Save" stands where "Test" stood, also on a phone */
    .level .body { flex: 1 1 0; min-width: 0; }
    .level .body ha-form { display: block; margin-top: 8px; }
    .level .actions { flex: none; }
    .form { padding: 0 16px 16px; }
    /* Lamps of the light pulse: one list, each lamp with its own "also when off" and a button to remove it. */
    .lamps { padding: 4px 0 6px; }
    .lamps-head { font-weight: 500; }
    .lamps-help { margin: 2px 0 8px; font-size: 13px; line-height: 1.4; color: var(--secondary-text-color); }
    .lamps ul { margin: 0 0 6px; padding: 0; list-style: none; border: 1px solid var(--divider-color); border-radius: 8px; }
    .lamp { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 14px; min-height: 48px; padding: 4px 4px 4px 12px;
      border-top: 1px solid var(--divider-color); }
    .lamp:first-child { border-top: 0; }
    .lamp-name { flex: 1 1 12em; min-width: 0; }
    .lamp-name .id { display: block; font-size: 12px; color: var(--secondary-text-color); overflow-wrap: anywhere; }
    .lamp-name .missing { color: var(--mc-warn); }
    .lamp-always { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; cursor: pointer; white-space: nowrap; }
    .lamp-remove { display: inline-grid; place-items: center; width: 36px; height: 36px; margin-left: auto; padding: 0; border: 0; border-radius: 50%;
      background: none; color: var(--secondary-text-color); cursor: pointer; }
    .lamp-remove:hover { background: color-mix(in srgb, var(--primary-text-color) 8%, transparent); color: var(--mc-bad); }
    .lamps-empty { margin: 0 0 6px; padding: 10px 12px; border: 1px dashed var(--divider-color); border-radius: 8px;
      font-size: 13px; color: var(--secondary-text-color); }
    .card-actions { display: flex; gap: 8px; align-items: center; justify-content: flex-end; padding: 8px 16px 12px; }
    .note { color: var(--success-color, #43a047); font-size: 13px; }
    .guide ol { margin: 0; padding: 0 16px 8px 36px; }
    .guide li { margin: 6px 0; line-height: 1.4; }
    .toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; }
    .toolbar input, .toolbar select { padding: 8px; font: inherit; border-radius: 6px; border: 1px solid var(--divider-color);
      background: var(--card-background-color); color: var(--primary-text-color); }
    .error { color: var(--error-color); padding: 8px 0; }
    .notice { display: flex; align-items: center; gap: 8px; margin: 0 0 12px; padding: 8px 12px; border-radius: 8px; font-size: 14px;
      background: color-mix(in srgb, var(--warning-color) 14%, transparent); color: var(--primary-text-color); }
    .notice .ico { color: var(--mc-warn); }
    .count { font-weight: 600; }
    a { color: var(--primary-color); }
  `;

  connectedCallback() {
    super.connectedCallback();
    // a tapped push may lead here while the page is open: Home Assistant then changes the address only
    window.addEventListener("location-changed", this._onLocation);
    window.addEventListener("popstate", this._onLocation);
    void this._start();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener("location-changed", this._onLocation);
    window.removeEventListener("popstate", this._onLocation);
    void this._unsub?.();
    this._unsub = undefined;
  }

  private _onLocation = () => {
    if (readDeepLink(location.search)) void this._followLink(true);
  };

  protected updated(changed: Map<string, unknown>) {
    // Rebuild the translator only when the language changes, not on every state update.
    if (changed.has("hass") && this.hass && this.hass.language !== this._lang) {
      this._lang = this.hass.language;
      this._t = makeT(this._lang);
      this.requestUpdate();
    }
  }

  private async _start() {
    this._lang = this.hass?.language ?? "en";
    this._t = makeT(this._lang);
    await ensureHaElements();
    // the lamp list uses HA's switch, which comes with the forms: show it once it is there
    if (!customElements.get("ha-switch")) void customElements.whenDefined("ha-switch").then(() => this.requestUpdate());
    await this._refresh();
    await this._followLink();
    try {
      this._unsub = await subscribe(this.hass, () => void this._refresh());
    } catch (err) {
      this._error = (err as { message?: string }).message ?? String(err);
    }
  }

  /**
   * A tapped push opened the page as "?message=<id>" (show the message,
   * unfolded) or "?classify=<id>" (classify its entry of "New"; when that is
   * gone, show the message). The link leaves the address first, so that a
   * reload or a later visit does not follow it again. Of a message that came
   * back several times the newest generation is shown; the filters of the
   * history are cleared, so that it shows. A message the page cannot find
   * leaves the page as it is, with a note. An open dialog is closed, unless
   * it holds unsaved input: then it stays, and the message is only shown
   * behind it.
   */
  private async _followLink(refresh = false) {
    const link = readDeepLink(location.search);
    if (!link) return;
    try {
      history.replaceState(history.state, "", location.pathname + withoutDeepLink(location.search) + location.hash);
    } catch { /* the address keeps the link; it is followed all the same */ }
    if (refresh) await this._refresh();
    const keep = this._dialogEdited();
    const wanted = keep ? { ...link, mode: "message" as const } : link;
    const open = this._messages?.open ?? [];
    const recent = this._messages?.recent ?? [];
    const unknown = this._overview?.unknown ?? [];
    let target = resolveDeepLink(wanted, open, recent, unknown);
    if (target.action === "missing") {
      let older: MessageEntry[];
      try {
        older = (await fetchHistory(this.hass)).history;
      } catch {
        return; // the history could not be read: the message may be there, say nothing
      }
      this._history = older;
      target = resolveDeepLink(wanted, open, [...recent, ...older], unknown);
    }
    if (target.action === "missing") {
      this._notice = this._t("link_missing");
      return;
    }
    if (!keep) {
      this._editor = undefined;
      this._kindSource = undefined;
    }
    if (target.action === "classify") {
      await this._select("overview");
      this._openKindEditor({ from: "new", item: target.item });
      return;
    }
    await this._select(target.tab);
    if (target.tab === "history") {
      this._filterGroup = "";
      this._filterKind = "";
      this._search = "";
    }
    this._openRows = new Set([...this._openRows, target.key]);
    await this.updateComplete;
    this.shadowRoot?.querySelector(`details[data-key="${target.key}"]`)?.scrollIntoView({ block: "center" });
  }

  /** Whether an open dialog holds input that was not saved. */
  private _dialogEdited(): boolean {
    const dialog = this.shadowRoot?.querySelector<HTMLElement & { edited?: boolean }>(
      "message-center-editor, message-center-kind-editor");
    return !!dialog?.edited;
  }

  private async _refresh() {
    try {
      const [overview, messages, config] = await Promise.all([
        fetchOverview(this.hass), fetchMessages(this.hass), fetchConfig(this.hass),
      ]);
      this._overview = overview;
      this._messages = messages;
      this._config = config;
      if (this._tab === "history") this._history = (await fetchHistory(this.hass)).history;
      this._error = "";
    } catch (err) {
      const e = err as { code?: string; message?: string };
      this._error = e.code === "not_ready" ? this._t("not_set_up") : (e.message ?? String(err));
    }
  }

  render() {
    const t = this._t;
    const o = this._overview;
    const count = (tab: Tab) => (!o ? 0 : tab === "open" ? o.open : tab === "overview" ? o.new : 0);
    const cap = this._tab === "overview" && o?.new ? t("cap_new").replace("{n}", String(o.new))
      : this._tab === "open" && o?.open ? t("cap_open").replace("{n}", String(o.open)) : "";
    return html`
      <header>
        <div class="bubble">
          <ha-menu-button .hass=${this.hass} .narrow=${this.narrow}></ha-menu-button>
          ${logoMark(56)}
          <div class="titles"><h1>Message <b>Center</b></h1><div class="tag">${t("tagline")}</div></div>
          ${o ? html`<span class="ready ${o.ready ? "" : "off"}"><span class="led">${icon(o.ready ? "tick" : "alert", 12, 3.2)}</span>${o.ready ? t("ready") : t("not_ready")}</span>` : nothing}
        </div>
        <svg class="tail" viewBox="-6 0 38 22" preserveAspectRatio="none" aria-hidden="true"><path d="M0 0H26L7 13.2Q3.5 15.6 3.2 11.6z"></path></svg>
      </header>
      <nav>
        ${TABS.map((tab) => {
          const n = count(tab);
          return html`<button class=${tab === this._tab ? "active" : ""} title=${t(tab)} @click=${() => this._select(tab)}>
            <span class="ib">${icon(TAB_ICON[tab])}${n ? html`<span class="cnt">${n}</span>` : nothing}</span>
            <span class="lbl">${t(tab)}</span>${n ? html`<span class="cnt">${n}</span>` : nothing}
          </button>`;
        })}
      </nav>
      <div class="navcap"><b>${t(this._tab)}</b>${cap ? html` · ${cap}` : nothing}</div>
      <main>
        ${this._overview?.alarm_active ? html`<div class="alarm-bar">
          <span>${t("alarm_active")}${this._overview.alarm_until ? html` · ${t("alarm_until")} ${this._time(this._overview.alarm_until)}` : nothing}</span>
          <ha-button appearance="filled" @click=${this._alarmOff}>${t("alarm_end")}</ha-button>
        </div>` : nothing}
        ${this._error ? html`<div class="error">${this._error}</div>` : nothing}
        ${this._notice ? html`<div class="notice">${icon("alert", 16)}<span>${this._notice}</span></div>` : nothing}
        ${this._renderTab()}
      </main>
      ${this._editor ? html`<message-center-editor .hass=${this.hass} .t=${t} .heading=${this._editor.heading}
        .fields=${this._editor.fields} .labels=${this._editor.labels} .helpers=${this._editor.helpers} .data=${this._editor.data}
        .onSave=${this._editor.onSave} .onChange=${this._editor.onChange} .extra=${this._editor.extra}
        @editor-closed=${() => { this._editor = undefined; if (this._scan && this._tab === "kinds") void this._runScan(); }}></message-center-editor>` : nothing}
      ${this._kindSource ? html`<message-center-kind-editor .hass=${this.hass} .t=${t} .config=${this._config}
        .unknown=${this._overview?.unknown ?? []} .source=${this._kindSource}
        @edit-kind=${(e: CustomEvent<{ kind_id: string }>) => this._editKindById(e.detail.kind_id)}
        @editor-closed=${() => { this._kindSource = undefined; if (this._scan && this._tab === "kinds") void this._runScan(); }}></message-center-kind-editor>` : nothing}
    `;
  }

  private async _select(tab: Tab) {
    this._tab = tab;
    this._notice = "";
    if (tab === "history" && !this._history) {
      try { this._history = (await fetchHistory(this.hass)).history; } catch { /* shown on refresh */ }
    }
    if (tab === "settings") {
      // a fresh working copy of the stored options; before they are loaded, the tab makes it once they are
      this._settings = this._config ? withDefaults(this._config.options) : undefined;
      this._settingsNote = "";
    }
  }

  /** "1 Meldung" / "3 Meldungen". */
  private _nKinds(n: number) {
    return n === 1 ? this._t("kinds_one") : this._t("kinds_many").replace("{n}", String(n));
  }

  private _intro(key: string) {
    return html`<p class="intro">${this._t(key)}</p>`;
  }

  private _renderTab() {
    switch (this._tab) {
      case "overview": return this._renderOverview();
      case "open": return this._renderOpen();
      case "history": return this._renderHistory();
      case "kinds": return this._renderKinds();
      case "rules": return this._renderRules();
      case "recipients": return this._renderRecipients();
      case "settings": return this._renderSettings();
    }
  }

  // ----- overview ------------------------------------------------------------

  private _renderOverview() {
    const t = this._t;
    const o = this._overview;
    if (!o) return html`<div class="empty">${t("loading")}</div>`;
    const kpi = (value: string | number, label: string, cls = "") =>
      html`<div class="kpi ${cls}"><div class="value">${value}</div><div class="label">${label}</div></div>`;
    const missing = o.missing_recipients.length;
    // the top edge of each group shows its worst state
    const now = o.disturbed ? "bad" : o.open || o.new ? "warn" : "good";
    const ops = !o.ready || missing || !o.recipients ? "bad" : "good";
    return html`
      <div class="groups">
        <section class="kgroup ${now}">
          <h2>${t("group_now")} <span>${t("group_now_sub")}</span></h2>
          <div class="kpis">
            ${kpi(o.open, t("open"), o.open ? "warn" : "zero")}
            ${kpi(o.waiting, t("waiting"), o.waiting ? "" : "zero")}
            ${kpi(o.disturbed, t("disturbed"), o.disturbed ? "bad" : "zero")}
            ${kpi(o.new, t("new"), o.new ? "warn" : "zero")}
          </div>
        </section>
        <section class="kgroup ${ops}">
          <h2>${t("group_ops")} <span>${t("group_ops_sub")}</span></h2>
          <div class="kpis">
            ${kpi(o.active_rules, t("active_rules"), o.active_rules ? "" : "zero")}
            ${kpi(o.delivered_today, t("delivered_today"), o.delivered_today ? "good" : "zero")}
            ${kpi(o.recipients - missing + "/" + o.recipients, t("recipients"), missing ? "bad" : "")}
          </div>
        </section>
      </div>
      ${this._config && !this._config.options.guide_dismissed ? html`<ha-card class="guide" .header=${t("guide_title")}>
        <ol>${[1, 2, 3, 4, 5].map((n) => html`<li>${t(`guide_${n}`)}</li>`)}</ol>
        <div class="card-actions"><ha-button @click=${() => this._setGuide(true)}>${t("guide_dismiss")}</ha-button></div>
      </ha-card>` : nothing}
      <div class="pair">
        <ha-card .header=${t("new_title")}>
          ${o.unknown.length === 0 ? html`<div class="empty">${t("new_empty")}</div>` : o.unknown.map((u) => this._renderUnknown(u))}
        </ha-card>
        <ha-card .header=${t("last_delivery")}>
          <div class="empty">${o.last_delivery
            ? html`${this._time(o.last_delivery.at)} · ${o.last_delivery.origin === "unknown" ? t("unknown_origin") : o.last_delivery.origin} · ${o.last_delivery.title}`
            : t("none_yet")}</div>
        </ha-card>
      </div>
      <ha-card><message-center-flow .t=${t}></message-center-flow></ha-card>
    `;
  }

  private _renderUnknown(u: UnknownItem) {
    const t = this._t;
    return html`<div class="row">
      <div class="body">
        <div class="title">${u.title}</div>
        <div class="meta">${u.origin_name ?? (u.origin === "unknown" ? t("unknown_origin") : u.origin)}
          ${u.labels.length ? html` · ${u.labels.join(", ")}` : nothing}
          · <span class="count">${u.count}×</span> · ${t("last_seen")} ${this._time(u.last_seen)}</div>
      </div>
      <div class="actions">
        <ha-button appearance="plain" @click=${() => this._dismiss(u)}>${t("dismiss")}</ha-button>
        <ha-button @click=${() => this._openKindEditor({ from: "new", item: u })}>${t("classify")}</ha-button>
      </div>
    </div>`;
  }

  private async _dismiss(u: UnknownItem) {
    try { await dismissUnknown(this.hass, u.origin, u.title); } catch (err) { this._error = String((err as { message?: string }).message ?? err); }
  }

  // ----- open and history ----------------------------------------------------

  private _renderOpen() {
    const t = this._t;
    const m = this._messages;
    if (!m) return html`<div class="empty">${t("loading")}</div>`;
    return html`${this._intro("intro_open")}<ha-card>
      ${m.open.length === 0 ? html`<div class="empty">${t("open_empty")}</div>` : this._renderTable(m.open, true)}
    </ha-card>`;
  }

  private _renderHistory() {
    const t = this._t;
    const groups = this._config?.groups ?? [];
    const kinds = this._config?.kinds ?? [];
    const recent = this._messages?.recent ?? [];
    const older = this._history ?? [];
    const filter = (e: MessageEntry) =>
      (!this._filterGroup || (this._filterGroup === "-" ? !e.group : e.group === this._filterGroup)) &&
      (!this._filterKind || (this._filterKind === "-" ? !e.kind : e.kind === this._filterKind)) &&
      (!this._search || (e.title + " " + e.message + " " + (e.origin_name ?? "")).toLowerCase().includes(this._search.toLowerCase()));
    const r = sortByEnd(recent.filter(filter), this._order);
    const o = sortByEnd(older.filter(filter), this._order);
    return html`
      ${this._intro("intro_history")}
      <div class="toolbar">
        <select @change=${(e: Event) => { this._filterGroup = (e.target as HTMLSelectElement).value; }}>
          <option value="" ?selected=${!this._filterGroup}>${t("all_groups")}</option>
          <option value="-" ?selected=${this._filterGroup === "-"}>${t("no_group")}</option>
          ${groups.map((g) => html`<option value=${g.name} ?selected=${this._filterGroup === g.name}>${g.name}</option>`)}
        </select>
        <select @change=${(e: Event) => { this._filterKind = (e.target as HTMLSelectElement).value; }}>
          <option value="" ?selected=${!this._filterKind}>${t("all_kinds")}</option>
          <option value="-" ?selected=${this._filterKind === "-"}>${t("no_kind")}</option>
          ${kinds.map((k) => html`<option value=${k.name} ?selected=${this._filterKind === k.name}>${k.name}</option>`)}
        </select>
        <input type="search" placeholder=${t("search")} .value=${this._search} @input=${(e: Event) => { this._search = (e.target as HTMLInputElement).value; }} />
        <select title=${t("order")} aria-label=${t("order")} @change=${(e: Event) => this._setOrder((e.target as HTMLSelectElement).value as HistoryOrder)}>
          <option value="newest" ?selected=${this._order === "newest"}>${t("order_newest")}</option>
          <option value="oldest" ?selected=${this._order === "oldest"}>${t("order_oldest")}</option>
        </select>
      </div>
      <ha-card .header=${t("recent")}>
        ${r.length === 0 ? html`<div class="empty">${t("history_empty")}</div>` : this._renderTable(r, false)}
      </ha-card>
      ${o.length ? html`<ha-card .header=${t("older")}>${this._renderTable(o, false)}</ha-card>` : nothing}
    `;
  }

  /** Newest or oldest first in both tables of the history; the browser keeps the choice. */
  private _setOrder(order: HistoryOrder) {
    this._order = order === "oldest" ? "oldest" : "newest";
    storeOrder(this._order);
  }

  /**
   * The messages as a compact table; `open` adds the buttons of open messages.
   * The time column says since when an open message waits ("Since"), and when
   * an ended one ended ("Time", always with the date).
   */
  private _renderTable(entries: MessageEntry[], open: boolean) {
    const t = this._t;
    return html`<div class="mtable ${open ? "" : "ended"}">
      <div class="thead"><span>${t("level_word")}</span><span>${t("state")}</span><span>${t("message_col")}</span>
        <span>${t("origin")}</span><span class="time">${t(open ? "since_col" : "time_col")}</span><span></span></div>
      ${entries.map((e) => this._renderMessage(e, open))}
    </div>`;
  }

  private _rowToggled(row: string, isOpen: boolean) {
    if (this._openRows.has(row) === isOpen) return;
    const next = new Set(this._openRows);
    if (isOpen) next.add(row); else next.delete(row);
    this._openRows = next;
  }

  private _renderMessage(e: MessageEntry, open: boolean) {
    const t = this._t;
    const st = e.state;
    const cls = st === "delivered" ? "ok" : st === "failed" ? "fail" : st === "discarded" ? "drop" : "wait";
    const stIcon = STATE_ICON[st] ?? "clock";
    const origin = e.origin_name ?? (e.origin === "unknown" ? t("unknown_origin") : e.origin);
    const row = rowKey(e);
    const unfolded = this._openRows.has(row);
    // the reason repeats the state for plain end states ("delivered", "discarded"): say it once
    const reason = !open && e.delivered_at ? this._time(e.delivered_at) : e.reason.toLowerCase() === t(st).toLowerCase() ? "" : e.reason;
    return html`<details class="msg s-${cls} l${e.priority}" data-key=${row} ?open=${unfolded}
      @toggle=${(ev: Event) => this._rowToggled(row, (ev.currentTarget as HTMLDetailsElement).open)}>
      <summary>
        <span class="lvbox" title=${t(`p${e.priority}`)}>${e.priority}</span>
        <span class="stc" title=${t(st)}>${icon(stIcon, 18)}<span>${t(st)}</span></span>
        <span class="line"><span class="title">${e.title}</span>${e.count > 1 ? html`<span class="cnt">${e.count}×</span>` : nothing}<span class="snip">${e.message}</span></span>
        <span class="org">${origin}</span>
        <span class="time">${open ? this._time(e.since) : dateTime(endedAt(e), this.hass?.language ?? "en")}</span>
        <span class="chev">${icon("chev", 18)}</span>
      </summary>
      ${unfolded ? html`<div class="more">
        <div class="more-l">
          <div class="text">${e.message}</div>
          <div class="why">${icon(stIcon, 15)}<span><b>${t(st)}</b>${reason ? html` · ${reason}` : nothing}${e.next_try ? html` · ${t("next_try")} ${this._time(e.next_try)}` : nothing}${
            e.failed_recipients.length ? html` · <span class="fail">${t("recipients_failed")}: ${e.failed_recipients.join(", ")}</span>` : nothing}</span></div>
          ${e.events?.length ? html`<div class="events">${e.events.map((ev) => html`<div>
            ${this._time(ev.at)} · ${t(`ev_${ev.kind}`)} ${t(`src_${ev.source}`)}${ev.detail ? html` · ${ev.kind === "light_skipped" ? t(ev.detail === "spacing" ? "spacing_skip" : ev.detail === "effect" ? "effect_skip" : "nothing_on") : ev.detail}` : nothing}
          </div>`)}</div>` : nothing}
          ${open || st === "delivered" ? html`<div class="actions">
            ${open && (st === "waiting" || st === "unclear" || st === "retrying") ? html`<ha-button appearance="plain" @click=${() => this._act("send_now", e)}>${t("send_now")}</ha-button>` : nothing}
            ${open ? html`<ha-button appearance="plain" @click=${() => this._act("discard", e)}>${t("discard")}</ha-button>` : nothing}
            <ha-button appearance="plain" @click=${() => this._snooze(e)}>${t("snooze")}</ha-button>
            <ha-button appearance="plain" @click=${() => this._forward(e)}>${t("forward")}</ha-button>
          </div>` : nothing}
        </div>
        <dl class="dl">
          <dt>${t("origin")}</dt><dd>${origin}</dd>
          <dt>${t("kind")}</dt><dd>${e.kind ?? "–"}</dd>
          <dt>${t("group")}</dt><dd>${e.group ?? "–"}</dd>
          <dt>${t("level_word")}</dt><dd>${t(`p${e.priority}`)}</dd>
          <dt>${t("since_col")}</dt><dd>${this._time(e.since)}</dd>
          ${e.count > 1 ? html`<dt>${t("counter")}</dt><dd>${e.count}×</dd>` : nothing}
          ${e.delivered_at ? html`<dt>${t("delivered")}</dt><dd>${this._time(e.delivered_at)}</dd>` : nothing}
        </dl>
      </div>` : nothing}
    </details>`;
  }

  private async _act(action: "discard" | "send_now", e: MessageEntry) {
    try { await messageAction(this.hass, action, e.message_id); } catch (err) { this._error = String((err as { message?: string }).message ?? err); }
  }

  private _snooze(e: MessageEntry) {
    const t = this._t;
    this._editor = {
      heading: `${t("snooze")}: ${e.title}`,
      fields: [{ name: "minutes", required: true, selector: { number: { min: 1, max: 10080, mode: "box", unit_of_measurement: "min" } } }],
      labels: { minutes: t("minutes") },
      data: { minutes: 30 },
      onSave: async (d) => { await messageAction(this.hass, "snooze", e.message_id, { minutes: Number(d.minutes) }); },
    };
  }

  private _forward(e: MessageEntry) {
    const t = this._t;
    this._editor = {
      heading: `${t("forward")}: ${e.title}`,
      fields: [{ name: "note", selector: { text: { multiline: true } } }],
      labels: { note: t("note") },
      data: { note: "" },
      onSave: async (d) => { await messageAction(this.hass, "forward", e.message_id, { note: d.note || null }); },
    };
  }

  // ----- kinds, shown inside their groups --------------------------------------

  private _renderKinds() {
    const t = this._t;
    const c = this._config;
    if (!c) return html`<div class="empty">${t("loading")}</div>`;
    const groupIds = new Set(c.groups.map((g) => g.id));
    const unassigned = c.kinds.filter((k) => !k.group_id || !groupIds.has(k.group_id));
    return html`
      ${this._intro("intro_kinds")}
      <div class="toolbar">
        <ha-button @click=${() => this._openKindEditor({ from: "blank" })}>${t("add_kind")}</ha-button>
        <ha-button appearance="outlined" @click=${() => this._openGroupEditor()}>${t("add_group")}</ha-button>
        <ha-button appearance="outlined" .disabled=${this._scanBusy} @click=${this._runScan}>${t("scan_button")}</ha-button>
      </div>
      ${this._renderScan()}
      ${c.groups.map((g) => this._renderGroup(g, c.kinds.filter((k) => k.group_id === g.id)))}
      <ha-card class=${this._dropTarget === "-" ? "drop-target" : ""}
      @dragover=${(e: DragEvent) => { if (!this._dragKind) return; e.preventDefault(); if (e.dataTransfer) e.dataTransfer.dropEffect = "move"; this._dropTarget = "-"; }}
      @dragleave=${() => { if (this._dropTarget === "-") this._dropTarget = ""; }}
      @drop=${(e: DragEvent) => { e.preventDefault(); void this._moveKind(this._dragKind, "-"); }}>
        <div class="group-head">
          <ha-icon icon="mdi:folder-outline"></ha-icon>
          <div class="body">
            <div class="title">${t("unassigned")}</div>
            <div class="meta">${this._nKinds(unassigned.length)}</div>
          </div>
          <div class="actions">
            <ha-button appearance="plain" @click=${() => this._openKindEditor({ from: "blank" })}>${t("add_kind")}</ha-button>
          </div>
        </div>
        ${unassigned.length === 0
          ? html`<div class="empty">${c.kinds.length === 0 ? t("kinds_empty") : t("unassigned_empty")}</div>`
          : unassigned.map((k) => this._renderKind(k))}
      </ha-card>`;
  }

  // ----- search over the house -----------------------------------------------

  private _runScan = async () => {
    this._scanBusy = true;
    try {
      this._scan = await scanHouse(this.hass);
      this._error = "";
    } catch (err) {
      this._error = String((err as { message?: string }).message ?? err);
    } finally {
      this._scanBusy = false;
    }
  };

  /** The list of places that notify: what still sends directly, where it is, and a kind for each. */
  private _renderScan() {
    const t = this._t;
    const r = this._scan;
    if (!r) return this._scanBusy ? html`<ha-card><div class="empty">${t("scan_running")}</div></ha-card>` : nothing;
    const todo = r.counts.direct;
    const hidden = r.found.filter((i) => i.status !== "direct").length + r.files.filter((f) => f.status !== "direct").length;
    const items = this._scanAll ? r.found : r.found.filter((i) => i.status === "direct");
    const files = this._scanAll ? r.files : r.files.filter((f) => f.status === "direct");
    const groups = new Map<string, ScanItem[]>();
    for (const i of items) groups.set(i.entity_id, [...(groups.get(i.entity_id) ?? []), i]);
    const head = todo === 0 ? t("scan_head_done") : todo === 1 ? t("scan_head_one") : t("scan_head_todo").replace("{n}", String(todo));
    return html`<ha-card class="scan">
      <div class="group-head">
        <span class="scan-ico">${icon("search", 24)}</span>
        <div class="body">
          <div class="title">${t("scan_title")}</div>
          <div class="meta">${t("scan_searched").replace("{a}", String(r.counts.automations)).replace("{s}", String(r.counts.scripts)).replace("{f}", String(r.counts.files))}</div>
        </div>
        <div class="actions">
          <ha-button appearance="plain" .disabled=${this._scanBusy} @click=${this._runScan}>${t("scan_again")}</ha-button>
          <ha-button appearance="plain" @click=${() => { this._scan = undefined; }}>${t("scan_close")}</ha-button>
        </div>
      </div>
      <div class="scan-head ${todo ? "todo" : "done"}">${head}</div>
      ${hidden ? html`<label class="scan-all"><input type="checkbox" .checked=${this._scanAll}
        @change=${(e: Event) => { this._scanAll = (e.target as HTMLInputElement).checked; }} />${t("scan_show_all").replace("{n}", String(hidden))}</label>` : nothing}
      ${[...groups.values()].map((g) => this._renderScanGroup(g))}
      ${files.length ? html`
        <div class="scan-src"><span class="scan-ico">${icon("file", 18)}</span><b>${t("scan_files_title")}</b></div>
        <div class="scan-note">${t("scan_files_note")}</div>
        ${files.map((f) => html`<div class="row"><div class="body">
          <div class="title"><span class="chip scan-${f.status}">${t(`scan_${f.status}`)}</span><code>${f.file}</code> · ${t("scan_line")} ${f.line}</div>
          <div class="meta"><code>${f.text}</code></div>
        </div></div>`)}` : nothing}
      <div class="scan-note">${t("scan_limits")}</div>
    </ha-card>`;
  }

  private _renderScanGroup(items: ScanItem[]) {
    const t = this._t;
    const src = items[0];
    return html`
      <div class="scan-src">
        <span class="chip">${t(`scan_${src.source}`)}</span><b>${src.name}</b>
        <span class="where">${src.file ? html`<code>${src.file}</code>` : t("scan_no_place")}${
          src.blueprint ? html` · ${t("scan_blueprint").replace("{name}", src.blueprint)}` : nothing}</span>
        ${src.edit_url ? html`<a href=${src.edit_url}>${t("scan_open_editor")}</a>` : nothing}
      </div>
      ${items.map((i) => {
        const note = scanNote(i);
        return html`<div class="row">
        <div class="body">
          <div class="title"><span class="chip scan-${i.status}">${t(`scan_${i.status}`)}</span>${i.title ?? i.first_line ?? "–"}${
            i.title ? nothing : html` <span class="chip">${t("scan_no_title")}${i.first_line ? html`, ${t("scan_first_line")}` : nothing}</span>`}</div>
          <div class="meta">${t("scan_target")}: <code>${i.target}</code>${i.line ? html` · ${t("scan_line")} ${i.line}` : nothing}</div>
          ${i.status === "direct" ? html`<div class="meta scan-todo">${t("scan_change_target")}.</div>` : nothing}
          ${note ? html`<div class="meta">${fill(t(note.key), { name: note.name ?? "", line: note.line ?? "" })}</div>` : nothing}
          ${i.source === "script" && i.status !== "persistent" && !i.kind ? html`<div class="meta">${t("scan_script_origin")}</div>` : nothing}
        </div>
        <div class="actions">${i.kind
          ? html`<span class="chip state-delivered">${t("scan_kind")}: ${i.kind}</span>`
          : i.status === "persistent" ? nothing
          : html`<ha-button appearance="plain" @click=${() => this._kindFromScan(i)}>${t("add_kind")}</ha-button>`}</div>
      </div>`;
      })}`;
  }

  /** Open the kind dialog for a found place: its origin and the suggested condition. */
  private _kindFromScan(i: ScanItem) {
    this._openKindEditor({ from: "scan", item: i });
  }

  private _renderGroup(g: Group, kinds: Kind[]) {
    const t = this._t;
    return html`<ha-card class=${this._dropTarget === g.id ? "drop-target" : ""}
      @dragover=${(e: DragEvent) => { if (!this._dragKind) return; e.preventDefault(); if (e.dataTransfer) e.dataTransfer.dropEffect = "move"; this._dropTarget = g.id; }}
      @dragleave=${() => { if (this._dropTarget === g.id) this._dropTarget = ""; }}
      @drop=${(e: DragEvent) => { e.preventDefault(); void this._moveKind(this._dragKind, g.id); }}>
      <div class="group-head">
        <ha-icon .icon=${g.icon || "mdi:folder"}></ha-icon>
        <div class="body">
          <div class="title">${g.name}</div>
          <div class="meta">${this._nKinds(kinds.length)} · ${t("defaults")}: ${t("priority")} ${g.priority}
            ${g.spacing ? html` · ${t("spacing").split(" ")[0]} ${g.spacing} min` : nothing}
            ${g.expires_after ? html` · ${t("expires_after").split(" ")[0]} ${g.expires_after} min` : nothing}</div>
        </div>
        <div class="actions">
          <ha-button appearance="plain" @click=${() => this._openKindEditor({ from: "blank", group: g.id })}>${t("add_kind")}</ha-button>
          <ha-button appearance="plain" @click=${() => this._openGroupEditor(g)}>${t("edit")}</ha-button>
          <ha-button appearance="plain" @click=${() => this._delete(g.id)}>${t("delete")}</ha-button>
        </div>
      </div>
      ${kinds.length === 0 ? html`<div class="empty">${t("group_empty")}</div>` : kinds.map((k) => this._renderKind(k))}
    </ha-card>`;
  }

  private _renderKind(k: Kind) {
    const t = this._t;
    const origin = k.origin ? this._originName(k.origin) : t("from_any");
    return html`<div class="row ${this._dragKind === k.id ? "dragging" : ""} ${k.orphan ? "orphan" : ""}" draggable="true"
      @dragstart=${(e: DragEvent) => { this._dragKind = k.id; e.dataTransfer?.setData("text/plain", k.id); if (e.dataTransfer) e.dataTransfer.effectAllowed = "move"; }}
      @dragend=${() => { this._dragKind = ""; this._dropTarget = ""; }}>
      <span class="grip" title=${t("drag_hint")}>${icon("grip")}</span>
      <div class="body">
        <div class="title"><span class="chip p${k.priority}">${k.priority}</span>${k.name}${k.active ? nothing : html` <span class="chip">${t("rule_inactive")}</span>`}
          ${k.orphan ? html` <span class="chip orphan" title=${forOrigin(t, "orphan_hint", k.origin)}>${t("orphan")}</span>` : nothing}
          ${k.ties?.length ? html` <span class="chip state-waiting" title=${t("tie").replace("{names}", k.ties.join(", "))}>${t("tie").replace("{names}", k.ties.join(", "))}</span>` : nothing}</div>
        <div class="meta">${origin} · ${conditionLabel(t, k.title_mode, k.title_value, k.origin)}
          ${k.no_hold ? html` · ${t("no_hold")}` : nothing}
          ${k.spacing ? html` · ${t("spacing").split(" ")[0]} ${k.spacing} min` : nothing}
          ${k.expires_after ? html` · ${t("expires_after").split(" ")[0]} ${k.expires_after} min` : nothing}</div>
        ${k.orphan ? html`<div class="meta">${forOrigin(t, "orphan_hint", k.origin)}</div>` : nothing}
      </div>
      <div class="actions">
        <ha-button appearance="plain" @click=${() => this._openKindEditor({ from: "edit", kind: k })}>${t("edit")}</ha-button>
        <ha-button appearance="plain" @click=${() => this._delete(k.id)}>${t("delete")}</ha-button>
      </div>
    </div>`;
  }

  /**
   * Open the dialog for a kind: new without a template ("blank", optionally
   * in a group), from an entry of "new", from a place the search found, or
   * to edit a kind (see kind-editor.ts).
   */
  private _openKindEditor(source: KindSource) {
    this._kindSource = source;
  }

  /** "Edit the existing one" after a refused double condition: the dialog switches to that kind. */
  private _editKindById(kindId: string) {
    const kind = this._config?.kinds.find((k) => k.id === kindId);
    if (kind) this._kindSource = { from: "edit", kind };
  }

  /** Name of an origin: as the center knows it, else as Home Assistant shows it, else its id. */
  private _originName(id: string): string {
    const known = this._config?.origins.find((o) => o.entity_id === id)?.name;
    const shown = this.hass?.states?.[id]?.attributes?.friendly_name;
    return known ?? (typeof shown === "string" && shown ? shown : id);
  }

  /** A kind dropped on a group card (or "-" for unassigned) gets that group; nothing else changes. */
  private async _moveKind(kindId: string, target: string) {
    this._dragKind = "";
    this._dropTarget = "";
    const k = this._config?.kinds.find((x) => x.id === kindId);
    if (!k) return;
    const groupId = target === "-" ? null : target;
    if ((k.group_id ?? null) === groupId) return;
    try {
      await saveEntry(this.hass, "kind", {
        name: k.name, origin: k.origin, title_mode: k.title_mode, title_value: k.title_value, group_id: groupId,
        priority: k.priority, no_hold: k.no_hold, spacing: k.spacing, expires_after: k.expires_after, light: k.light, active: k.active,
      }, k.id);
      this._error = "";
    } catch (err) {
      this._error = String((err as { message?: string }).message ?? err);
    }
  }

  private _openGroupEditor(group?: Group) {
    const t = this._t;
    const fields: Field[] = [
      { name: "name", required: true, selector: { text: {} } },
      { name: "icon", selector: { icon: {} } },
      { name: "priority", selector: { select: { options: [
        { value: "1", label: t("p1") }, { value: "2", label: t("p2") }, { value: "3", label: t("p3") }], mode: "dropdown" } } },
      { name: "spacing", selector: { number: { min: 0, max: 10080, mode: "box", unit_of_measurement: "min" } } },
      { name: "expires_after", selector: { number: { min: 0, max: 10080, mode: "box", unit_of_measurement: "min" } } },
    ];
    const labels = Object.fromEntries(fields.map((f) => [f.name, t(f.name)]));
    this._editor = {
      heading: group ? `${t("edit")}: ${group.name}` : t("add_group"),
      fields, labels,
      data: group ? { ...group, icon: group.icon ?? "", priority: String(group.priority) } : { name: "", icon: "", priority: "1", spacing: 0, expires_after: 0 },
      onSave: async (d) => {
        await saveEntry(this.hass, "group", {
          name: d.name, icon: d.icon || null, priority: Number(d.priority ?? 1),
          spacing: Number(d.spacing ?? 0), expires_after: Number(d.expires_after ?? 0),
        }, group?.id);
      },
    };
  }

  // ----- rules ----------------------------------------------------------------

  private _renderRules() {
    const t = this._t;
    const c = this._config;
    if (!c) return html`<div class="empty">${t("loading")}</div>`;
    const eff = (v: string) => (v === "discard" ? t("discard_effect") : t(v));
    return html`
      ${this._intro("intro_rules")}
      <div class="toolbar"><ha-button @click=${() => this._openRuleEditor()}>${t("add_rule")}</ha-button></div>
      <ha-card>
        ${c.rules.length === 0 ? html`<div class="empty">${t("rules_empty")}</div>` : c.rules.map((r) => html`<div class="row">
          <div class="body">
            <div class="title">
              <span class="chip ${r.active ? (r.expired ? "state-failed" : "state-waiting") : ""}">${r.active ? (r.expired ? t("expired") : t("active")) : t("rule_inactive")}</span>
              ${r.name}${r.unknown ? html` <span class="chip state-failed">${t("unknown_state")}</span>` : nothing}
            </div>
            <div class="meta">${r.entity_id} = ${t("q_open")}${r.state}${t("q_close")} (${t("current")}: ${r.current_state ?? "?"})
              ${r.since ? html` · ${t("since")} ${this._time(r.since)} · ${t("until")} ${this._time(r.until)}` : nothing}
              · ${t("max_hours").split(" ")[0]} ${r.max_hours} h</div>
            <div class="fx">${[r.effect_1, r.effect_2, r.effect_3].map((effect, i) => html`<span class="fx-i l${i + 1}"
              title="${t("level_word")} ${i + 1}: ${eff(effect)}"><span class="lvbox">${i + 1}</span>${icon(EFFECT_ICON[effect] ?? "pause", 17)}<span>${eff(effect)}</span></span>`)}</div>
          </div>
          <div class="actions">
            <ha-button appearance="plain" @click=${() => this._openRuleEditor(r)}>${t("edit")}</ha-button>
            <ha-button appearance="plain" @click=${() => this._delete(r.id)}>${t("delete")}</ha-button>
          </div>
        </div>`)}
      </ha-card>`;
  }

  private _openRuleEditor(rule?: Rule) {
    const t = this._t;
    const effects = { select: { options: [
      { value: "pass", label: t("pass") }, { value: "hold", label: t("hold") }, { value: "discard", label: t("discard_effect") }], mode: "dropdown" } };
    // The state is chosen from the entity's known states; any other value can be typed.
    const fieldsFor = (entityId: unknown, current: unknown): Field[] => {
      const known = this._knownStates(String(entityId ?? ""));
      if (current && !known.includes(String(current))) known.unshift(String(current));
      return [
        { name: "name", required: true, selector: { text: {} } },
        { name: "entity_id", required: true, selector: { entity: {} } },
        { name: "state", required: true, selector: { select: { options: known.map((s) => ({ value: s, label: s })), mode: "dropdown", custom_value: true } } },
        { name: "effect_1", selector: effects },
        { name: "effect_2", selector: effects },
        { name: "effect_3", selector: effects },
        { name: "max_hours", selector: { number: { min: 1, max: 168, mode: "box", unit_of_measurement: "h" } } },
      ];
    };
    const labels = { name: t("name"), entity_id: t("entity"), state: t("rule_state"), effect_1: t("effect_1"),
      effect_2: t("effect_2"), effect_3: t("effect_3"), max_hours: t("max_hours") };
    const data: FormData = rule ? { ...rule } : { name: "", entity_id: "", state: "on", effect_1: "hold", effect_2: "hold", effect_3: "pass", max_hours: 12 };
    this._editor = {
      heading: rule ? `${t("edit")}: ${rule.name}` : t("add_rule"),
      fields: fieldsFor(data.entity_id, data.state), labels, helpers: { state: t("rule_state_helper") },
      data,
      // what a mode is, and a toggle created here is chosen for the rule at once
      extra: (update) => html`<message-center-mode-help .hass=${this.hass} .t=${t}
        @switch-created=${(e: CustomEvent<{ entity_id: string; name: string }>) =>
          update((d) => ruleWithSwitch(d, e.detail.entity_id, e.detail.name))}></message-center-mode-help>`,
      onChange: (next, prev) => {
        if (next.entity_id !== prev.entity_id && this._editor) {
          // a new entity: offer its states and preselect the current one
          const known = this._knownStates(String(next.entity_id ?? ""));
          const state = known.includes(String(next.state)) ? next.state : (known[0] ?? next.state);
          next = { ...next, state };
          this._editor = { ...this._editor, fields: fieldsFor(next.entity_id, state) };
        }
        return next;
      },
      onSave: async (d) => {
        await saveEntry(this.hass, "rule", {
          name: d.name, entity_id: d.entity_id, state: d.state, effect_1: d.effect_1 ?? "hold",
          effect_2: d.effect_2 ?? "hold", effect_3: d.effect_3 ?? "pass", max_hours: Number(d.max_hours ?? 12),
        }, rule?.id);
      },
    };
  }

  /** Known states of an entity: the current one, its options, and the typical states of its domain. */
  private _knownStates(entityId: string): string[] {
    const st = this.hass?.states?.[entityId];
    const domain = entityId.split(".")[0];
    const typical: Record<string, string[]> = {
      input_boolean: ["on", "off"], switch: ["on", "off"], binary_sensor: ["on", "off"], light: ["on", "off"],
      person: ["home", "not_home"], device_tracker: ["home", "not_home"], sun: ["above_horizon", "below_horizon"],
      alarm_control_panel: ["disarmed", "armed_home", "armed_away", "armed_night", "armed_vacation", "triggered"],
      lock: ["locked", "unlocked"], cover: ["open", "closed"], calendar: ["on", "off"], schedule: ["on", "off"],
      media_player: ["playing", "paused", "idle", "off"], vacuum: ["cleaning", "docked", "returning", "idle"],
    };
    const options = (st?.attributes?.options as string[] | undefined) ?? [];
    const list = [...(st ? [st.state] : []), ...options, ...(typical[domain] ?? [])];
    return [...new Set(list.filter((s) => s && s !== "unknown" && s !== "unavailable"))];
  }

  // ----- recipients -----------------------------------------------------------

  private _renderRecipients() {
    const t = this._t;
    const c = this._config;
    if (!c) return html`<div class="empty">${t("loading")}</div>`;
    const fields: Field[] = c.recipients.map((r) => ({ name: r.action, selector: { boolean: {} } }));
    const labels = Object.fromEntries(c.recipients.map((r) => [r.action, r.name]));
    const helpers = Object.fromEntries(c.recipients.map((r) =>
      [r.action, `${r.platform} · notify.${r.action} · ${r.available ? t("available") : t("unavailable")} · ${
        r.last_error ? `${t("last_error")}: ${r.last_error.error} (${this._time(r.last_error.at)})` : t("no_error")}`]));
    const data = Object.fromEntries(c.recipients.map((r) => [r.action, r.configured]));
    return html`<ha-card>
      <div class="empty">${t("recipients_intro")}</div>
      <div class="form">
        <ha-form .hass=${this.hass} .schema=${fields} .data=${data}
          .computeLabel=${(f: Field) => labels[f.name] ?? f.name} .computeHelper=${(f: Field) => helpers[f.name]}
          @value-changed=${(e: CustomEvent) => this._recipientsChanged(e.detail.value as Record<string, boolean>)}></ha-form>
      </div>
      <div class="empty">${t("recipients_hint")} <a href="/config/integrations/integration/message_center">→</a></div>
    </ha-card>`;
  }

  private async _recipientsChanged(value: Record<string, boolean>) {
    const actions = Object.entries(value).filter(([, on]) => on).map(([action]) => action);
    try {
      await setRecipients(this.hass, actions);
      this._error = "";
    } catch (err) {
      const e = err as { code?: string; message?: string };
      this._error = e.code === "at_least_one" ? this._t("at_least_one") : String(e.message ?? err);
      await this._refresh(); // show the stored state again
    }
  }

  // ----- settings ---------------------------------------------------------------

  private _renderSettings() {
    const t = this._t;
    if (!this._config) return html`<div class="empty">${t("loading")}</div>`;
    const data = this._settings ?? (this._settings = withDefaults(this._config.options));
    const onChange = (e: CustomEvent) => { this._settings = { ...data, ...(e.detail.value as Options) }; this._settingsNote = ""; };
    // something not saved yet: each "Test" would test the stored settings, so "Save" stands in its place
    const unsaved = settingsChanged(data, this._config.options);
    const pulseFields: Field[] = [
      { name: "pulse_ms", required: true, selector: { number: { min: 100, max: 10000, step: 50, mode: "box", unit_of_measurement: "ms" } } },
      { name: "light_spacing", required: true, selector: { number: { min: 0, max: 600, mode: "box", unit_of_measurement: "s" } } },
    ];
    const alarmFields: Field[] = [
      { name: "alarm_lights", selector: { entity: { domain: ["light", "switch"], multiple: true } } },
      { name: "alarm_interval_ms", required: true, selector: { number: { min: 100, max: 5000, step: 50, mode: "box", unit_of_measurement: "ms" } } },
      { name: "alarm_max_seconds", required: true, selector: { number: { min: 5, max: 3600, mode: "box", unit_of_measurement: "s" } } },
      { name: "alarm_test_seconds", required: true, selector: { number: { min: 1, max: 60, mode: "box", unit_of_measurement: "s" } } },
      { name: "alarm_channel", required: true, selector: { select: { mode: "dropdown", options: [
        { value: "alarm_stream", label: t("alarm_channel_stream") }, { value: "alarm_stream_max", label: t("alarm_channel_max") },
        { value: "message_center_alarm", label: t("alarm_channel_own") }] } } },
      { name: "alarm_tts", selector: { boolean: {} } },
    ];
    const alarmHelpers: Record<string, string> = { alarm_lights: t("alarm_lights_helper"), alarm_channel: t("alarm_channel_helper") };
    const buttonFields: Field[] = [
      { name: "tap_target", required: true, selector: { select: { mode: "dropdown", options: [
        { value: "home", label: t("tap_target_home") }, { value: "center", label: t("tap_target_center") }] } } },
      { name: "button_snooze", selector: { boolean: {} } },
      { name: "snooze_minutes", required: true, selector: { number: { min: 1, max: 10080, mode: "box", unit_of_measurement: "min" } } },
      { name: "snooze_minutes_2", selector: { number: { min: 0, max: 10080, mode: "box", unit_of_measurement: "min" } } },
      { name: "snooze_input", selector: { boolean: {} } },
      { name: "button_forward", selector: { boolean: {} } },
      { name: "forward_script", selector: { entity: { domain: "script" } } },
    ];
    const buttonHelpers: Record<string, string> = {
      tap_target: t("tap_target_helper"), snooze_input: t("snooze_input_helper"), forward_script: t("forward_script_helper") };
    const optionFields: Field[] = [
      { name: "history_days", required: true, selector: { number: { min: 1, max: 365, mode: "box", unit_of_measurement: "d" } } },
      { name: "sidebar", selector: { boolean: {} } },
      { name: "hide_titles", selector: { boolean: {} } },
      { name: "allow_alarm", selector: { boolean: {} } },
      { name: "silent_repeat", selector: { boolean: {} } },
    ];
    const scriptField = (n: number): Field[] => [{ name: `effect_script_${n}`, selector: { entity: { domain: "script" } } }];
    const level = (n: number) => html`<div class="level">
      <span class="chip p${n}">${n}</span>
      <div class="body"><div class="name">${t(`level_${n}_name`)}</div><div class="effect">${t(`level_${n}_effect`)}</div>
        <ha-form .hass=${this.hass} .schema=${scriptField(n)} .data=${data}
          .computeLabel=${(f: Field) => t(f.name)} .computeHelper=${() => t("effect_script_helper")} @value-changed=${onChange}></ha-form>
      </div>
      <div class="actions">${unsaved
        ? html`<ha-button @click=${this._saveSettings}>${t("save")}</ha-button>`
        : html`<ha-button appearance="outlined" @click=${() => this._sendTest(n)}>${t("test")}</ha-button>`}</div>
    </div>`;
    const helpers: Record<string, string> = { light_spacing: t("light_spacing_helper") };
    return html`
      ${this._intro("intro_settings")}
      <ha-card .header=${t("levels_title")}>
        <div class="empty">${t("test_hint")}${this._testNote ? html` <span class="note">${this._testNote}</span>` : nothing}</div>
        ${level(1)}${level(2)}
        <div class="form">
          ${this._renderLights(data)}
          <ha-form .hass=${this.hass} .schema=${pulseFields} .data=${data}
            .computeLabel=${(f: Field) => t(f.name)} .computeHelper=${(f: Field) => helpers[f.name]}
            @value-changed=${onChange}></ha-form>
        </div>
        ${level(3)}
        <div class="form">
          <ha-form .hass=${this.hass} .schema=${alarmFields} .data=${data}
            .computeLabel=${(f: Field) => t(f.name)} .computeHelper=${(f: Field) => alarmHelpers[f.name]} @value-changed=${onChange}></ha-form>
        </div>
      </ha-card>
      <ha-card .header=${t("buttons_title")}>
        <div class="empty">${t("buttons_intro")}</div>
        <div class="form">
          <ha-form .hass=${this.hass} .schema=${buttonFields} .data=${data}
            .computeLabel=${(f: Field) => t(f.name)} .computeHelper=${(f: Field) => buttonHelpers[f.name]}
            @value-changed=${onChange}></ha-form>
        </div>
      </ha-card>
      <ha-card .header=${t("options_title")}>
        <div class="form">
          <ha-form .hass=${this.hass} .schema=${optionFields} .data=${data}
            .computeLabel=${(f: Field) => t(f.name)} @value-changed=${onChange}></ha-form>
        </div>
        <div class="card-actions">
          ${this._settingsNote ? html`<span class="note">${this._settingsNote}</span>` : nothing}
          <ha-button appearance="plain" @click=${() => this._setGuide(false)}>${t("guide_show")}</ha-button>
          <ha-button @click=${this._saveSettings}>${t("save")}</ha-button>
        </div>
      </ha-card>`;
  }

  /**
   * The lamps and switches of the light pulse as one list: each with its own
   * switch "also when off" and a button to remove it, and a picker below to
   * add one. Saved as `lights` and the part of them in `lights_always`.
   */
  private _renderLights(data: Options) {
    const t = this._t;
    const rows = lightRows(data);
    const change = (edit: (o: Options) => Options) => {
      this._settings = edit(this._settings ?? data);
      this._settingsNote = "";
    };
    const add: Field[] = [{ name: "light_add", selector: { entity: { domain: ["light", "switch"], exclude_entities: rows.map((r) => r.entity_id) } } }];
    return html`<div class="lamps">
      <div class="lamps-head">${t("lights")}</div>
      <div class="lamps-help">${t("lights_helper")}</div>
      ${rows.length ? html`<ul>${rows.map((r) => this._renderLight(r, change))}</ul>` : html`<div class="lamps-empty">${t("lights_empty")}</div>`}
      ${keyed(this._lampAddRound, html`<ha-form .hass=${this.hass} .schema=${add} .data=${{ light_add: "" }} .computeLabel=${() => t("light_add")}
        @value-changed=${(e: CustomEvent) => {
          const id = (e.detail.value as { light_add?: string } | undefined)?.light_add;
          if (!id) return;
          change((o) => withLight(o, id));
          // the entity picker keeps the lamp it shows; a new one is empty again
          this._lampAddRound++;
        }}></ha-form>`)}
    </div>`;
  }

  private _renderLight(r: LightRow, change: (edit: (o: Options) => Options) => void) {
    const t = this._t;
    const st = this.hass?.states?.[r.entity_id];
    const name = typeof st?.attributes?.friendly_name === "string" && st.attributes.friendly_name ? st.attributes.friendly_name : r.entity_id;
    const setAlways = (on: boolean) => change((o) => withAlways(o, r.entity_id, on));
    // HA's switch once the page has it (it comes with the forms), a plain checkbox until then
    const toggle = customElements.get("ha-switch")
      ? html`<ha-switch .checked=${r.always} @change=${(e: Event) => setAlways((e.target as HTMLInputElement).checked)}></ha-switch>`
      : html`<input type="checkbox" .checked=${r.always} @change=${(e: Event) => setAlways((e.target as HTMLInputElement).checked)} />`;
    return html`<li class="lamp">
      <div class="lamp-name">${name}<span class="id">${r.entity_id}${st ? nothing : html` · <span class="missing">${t("light_missing")}</span>`}</span></div>
      <label class="lamp-always" title=${t("light_always_helper")}>${toggle}<span>${t("light_always")}</span></label>
      <button class="lamp-remove" title=${t("light_remove")} aria-label=${t("light_remove")}
        @click=${() => change((o) => withoutLight(o, r.entity_id))}>${icon("trash", 18)}</button>
    </li>`;
  }

  private _alarmOff = async () => {
    try { await alarmOff(this.hass); } catch (err) { this._error = String((err as { message?: string }).message ?? err); }
  };

  private async _setGuide(dismissed: boolean) {
    try {
      // only this one option: the server merges it into the stored ones
      await saveOptions(this.hass, { guide_dismissed: dismissed });
      if (!dismissed) this._tab = "overview";
    } catch (err) {
      this._error = String((err as { message?: string }).message ?? err);
    }
  }

  private async _sendTest(priority: number) {
    const t = this._t;
    if (priority === 3 && !window.confirm(t("confirm_alarm_test"))) return;
    this._testNote = "";
    try {
      const r = await sendTest(this.hass, priority);
      const parts = [t("test_sent").replace("{n}", String(priority)).replace("{names}", r.sent.join(", ") || "–")];
      if (priority === 2) parts.push(r.lights.length ? t("test_lights").replace("{lights}", r.lights.join(", ")) : t("test_no_lights"));
      if (priority === 3 && r.lights.length) parts.push(t("test_alarm").replace("{lights}", r.lights.join(", ")));
      if (r.script) parts.push(r.script_error
        ? t("test_script_failed").replace("{script}", r.script).replace("{error}", r.script_error)
        : t("test_script").replace("{script}", r.script));
      if (r.failed.length) parts.push(t("test_failed").replace("{names}", r.failed.join(", ")));
      this._testNote = parts.join(" · ");
      this._error = "";
    } catch (err) {
      this._error = String((err as { message?: string }).message ?? err);
    }
  }

  private _saveSettings = async () => {
    const s = this._settings;
    if (!s) return;
    try {
      const res = await saveOptions(this.hass, optionsPayload(s, this._config?.options.guide_dismissed ?? false));
      // the stored state is known now: the test buttons come back without waiting for the refresh
      if (this._config) this._config = { ...this._config, options: res.options };
      this._settings = withDefaults(res.options);
      this._settingsNote = this._t("saved");
      this._error = "";
    } catch (err) {
      this._error = String((err as { message?: string }).message ?? err);
    }
  };

  // ----- helpers --------------------------------------------------------------

  private async _delete(id: string) {
    if (!window.confirm(this._t("confirm_delete"))) return;
    try { await deleteEntry(this.hass, id); } catch (err) { this._error = String((err as { message?: string }).message ?? err); }
  }

  private _time(value: string | null) {
    if (!value) return "?";
    const d = new Date(value);
    const lang = this.hass?.language ?? "en";
    const today = new Date();
    const sameDay = d.toDateString() === today.toDateString();
    return sameDay
      ? d.toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit" })
      : d.toLocaleString(lang, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  }
}

// Registered only once: after an update Home Assistant imports the page module
// again under a new URL in the same tab, and a second define() would throw.
if (!customElements.get("message-center-panel")) customElements.define("message-center-panel", MessageCenterPanel);

declare global {
  interface HTMLElementTagNameMap {
    "message-center-panel": MessageCenterPanel;
    "message-center-editor": import("./editor").MessageCenterEditor;
  }
}
