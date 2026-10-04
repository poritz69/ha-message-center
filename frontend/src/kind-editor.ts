import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";
import { fetchKindMatches, fetchOriginMessages, saveEntry } from "./api";
import { fallbackStyles, formFields, type Field, type FormData } from "./editor";
import type { Translate } from "./i18n";
import {
  appliesTo, conditionComplete, conditionOf, counted, duplicateIn, duplicateOf, fill, forOrigin, kindPayload, landsInNew, modeOptions,
  originAllowsAny, possibleMessages, probeOf, sourceOrigin, startState, type Apply, type Condition, type DialogStart, type KindSource,
} from "./kind-logic";
import type { Config, HomeAssistant, KindMatches, MatchedPair, OriginMessages, TitleMode, UnknownItem } from "./types";

/** Wait this long after a change before asking what the condition matches. */
const MATCH_DELAY = 400;

/** Key of an entry of "new" in the dropdown "take from New". */
const pairKey = (u: { origin: string; title: string }) => JSON.stringify([u.origin, u.title]);

/**
 * The dialog for a message kind. On top a sentence says what the kind applies
 * to. Origin, comparison and text are shown but locked when the dialog starts
 * from a message, a found call or an existing kind; "edit condition
 * (advanced)" opens them. For an automation that sends one message the
 * condition is "all messages of this automation" (an existing kind is put on
 * it with a note and the offer to keep its condition); for one that sends
 * several the text is open, with a hint and the messages it may send. At the
 * bottom the dialog shows what the condition matches. A new kind without a
 * template starts with open fields and can take an entry of "new".
 */
export class MessageCenterKindEditor extends LitElement {
  @property({ attribute: false }) public hass!: HomeAssistant;
  @property({ attribute: false }) public t!: Translate;
  @property({ attribute: false }) public config?: Config;
  /** The entries of "new", for "take from New". */
  @property({ attribute: false }) public unknown: UnknownItem[] = [];
  /** How the dialog was opened; a new value starts it anew. */
  @property({ attribute: false }) public source!: KindSource;
  /** What the dialog works from: the source, or the entry taken from "new". */
  @state() private _source: KindSource = { from: "blank" };
  @state() private _data: FormData = {};
  @state() private _cond: Condition = { origin: "", title_mode: "exact", title_value: "" };
  @state() private _locked = false;
  @state() private _titleOpen = true;
  @state() private _advanced = false;
  @state() private _multiple = false;
  /** The dialog put an existing kind on "all messages of this automation". */
  @state() private _switched = false;
  @state() private _om?: OriginMessages;
  @state() private _matches?: KindMatches;
  @state() private _matching = false;
  @state() private _picked = "";
  @state() private _error = "";
  @state() private _duplicate?: { kind_id: string; name: string };
  @state() private _busy = false;
  /** The condition was changed by hand: a late answer about the automation does not reset it. */
  private _touched = false;
  /** The values the dialog opened with; any input replaces them by a new copy. */
  private _openedWith: FormData = {};
  /** The name the dialog filled in itself; it follows a pick from "new" until it is typed over. */
  private _autoName = "";
  private _timer?: ReturnType<typeof setTimeout>;
  private _askedOrigin = 0;
  private _askedMatches = 0;

  static styles = [fallbackStyles, css`
    .applies { padding: 10px 12px; margin: 0 0 12px; border-radius: 8px; font-weight: 500; line-height: 1.4; overflow-wrap: anywhere;
      background: color-mix(in srgb, var(--primary-color) 12%, transparent); border: 1px solid color-mix(in srgb, var(--primary-color) 38%, transparent); }
    .cond { margin: 12px 0; padding: 8px 12px 12px; border-radius: 8px; border: 1px solid var(--divider-color); }
    .cond-head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 4px 12px; margin-bottom: 6px; font-weight: 500; }
    .link { border: 0; padding: 0; background: none; font: inherit; font-size: 13px; font-weight: 400; color: var(--primary-color);
      text-decoration: underline; cursor: pointer; }
    .hint { margin: 10px 0 0; font-size: 13px; line-height: 1.4; color: var(--mc-bad, var(--error-color)); }
    .note { margin: 10px 0 0; font-size: 13px; line-height: 1.4; color: var(--secondary-text-color); }
    .note .link { white-space: nowrap; }
    .possible { margin: 10px 0 0; }
    .possible .p-head { font-size: 12px; font-weight: 500; color: var(--secondary-text-color); margin-bottom: 2px; }
    .possible ul { margin: 0; padding: 0; list-style: none; }
    .possible li { display: flex; align-items: center; gap: 8px; min-height: 34px; border-top: 1px solid var(--divider-color); font-size: 13px; }
    .possible li.current .p-label { font-weight: 600; }
    .p-label { flex: 1 1 auto; min-width: 0; overflow-wrap: anywhere; }
    .chip { flex: none; padding: 1px 8px; border-radius: 10px; font-size: 11.5px; background: var(--secondary-background-color); color: var(--secondary-text-color); }
    .matches { margin-top: 14px; padding: 10px 12px; border-radius: 8px; font-size: 13px; line-height: 1.4;
      background: color-mix(in srgb, var(--primary-text-color) 5%, transparent); }
    .m-head { font-weight: 600; margin-bottom: 4px; }
    .m-head .busy { font-weight: 400; color: var(--secondary-text-color); }
    .m-sub { margin-top: 6px; color: var(--secondary-text-color); font-weight: 500; }
    .matches ul { margin: 2px 0 0; padding-left: 18px; }
    .matches li { overflow-wrap: anywhere; }
    .m-origin, .m-note { color: var(--secondary-text-color); }
    .m-note { margin-top: 4px; }
    .m-warn, .m-taken { color: var(--mc-warn, var(--warning-color)); }
    .m-warn { font-weight: 500; }
    .m-overlap { margin-top: 6px; }
    .error { color: var(--error-color); margin-top: 10px; }
    .error .link { margin-left: 6px; }
  `];

  connectedCallback() {
    super.connectedCallback();
    // While the form is open, typed letters must never reach Home Assistant's
    // global shortcuts (e.g. "c" opens the command search when a dropdown has focus).
    this.addEventListener("keydown", this._swallowKeys);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.removeEventListener("keydown", this._swallowKeys);
    clearTimeout(this._timer);
  }

  private _swallowKeys = (e: KeyboardEvent) => { e.stopPropagation(); };

  protected willUpdate(changed: Map<string, unknown>) {
    if (changed.has("source") && this.source) this._start(this.source, true);
  }

  // ----- starting -----------------------------------------------------------------

  /** Start from a source: the opening one (`fresh`), or an entry taken from "new". */
  private _start(source: KindSource, fresh: boolean) {
    this._source = source;
    const s = startState(source, null, this._kinds);
    if (fresh) {
      this._data = this._initialData(source, s.name);
      this._openedWith = this._data;
      this._picked = "";
    } else if (!String(this._data.name ?? "").trim() || this._data.name === this._autoName) {
      this._data = { ...this._data, name: s.name };
    }
    this._autoName = s.name;
    this._use(s);
    this._touched = false;
    this._advanced = false;
    this._om = undefined;
    this._error = "";
    this._duplicate = undefined;
    this._matches = undefined;
    void this._askOrigin(sourceOrigin(source), true);
    this._askMatchesSoon(0);
  }

  /** Whether something was entered or chosen since the dialog opened: the condition, an entry of "new", a field. */
  get edited(): boolean {
    return this._touched || this._picked !== "" || this._data !== this._openedWith;
  }

  private _use(s: DialogStart) {
    this._cond = s.condition;
    this._locked = s.locked;
    this._titleOpen = s.titleOpen;
    this._multiple = s.multiple;
    this._switched = s.switched;
  }

  private _initialData(source: KindSource, name: string): FormData {
    if (source.from === "edit") {
      const k = source.kind;
      return { name: k.name, group_id: k.group_id ?? "", new_group: "", priority: String(k.priority), no_hold: k.no_hold,
        spacing: k.spacing, expires_after: k.expires_after, light: k.light === null ? "auto" : k.light ? "on" : "off", active: k.active };
    }
    const group = source.from === "scan" ? undefined : source.group;
    return this._withDefaults({ name, group_id: group ?? "", new_group: "", priority: "1", no_hold: false,
      spacing: 0, expires_after: 0, light: "auto", active: true }, group);
  }

  /** A new kind takes priority, spacing and expiry from its group's defaults. */
  private _withDefaults(d: FormData, groupId: unknown): FormData {
    const g = this.config?.groups.find((x) => x.id === groupId);
    return g ? { ...d, priority: String(g.priority), spacing: g.spacing, expires_after: g.expires_after } : d;
  }

  private get _kindId() {
    return this._source.from === "edit" ? this._source.kind.id : undefined;
  }

  /** All kinds, active or not: a double condition is looked for among them. */
  private get _kinds() {
    return this.config?.kinds ?? [];
  }

  // ----- asking the center ----------------------------------------------------------

  /**
   * Ask which messages an origin sends. For the source's origin the answer
   * decides how the dialog starts, unless the condition was changed by hand
   * meanwhile; for an origin chosen in the open fields it only shows the
   * hint and the possible messages.
   */
  private async _askOrigin(origin: string, fromSource: boolean) {
    const asked = ++this._askedOrigin;
    if (!origin) {
      this._om = undefined;
      if (!fromSource) this._multiple = false;
      return;
    }
    try {
      const om = await fetchOriginMessages(this.hass, origin);
      if (asked !== this._askedOrigin) return;
      this._om = om;
      if (fromSource && !this._touched) {
        this._use(startState(this._source, om, this._kinds));
        this._askMatchesSoon(0);
      } else {
        this._multiple = om.multiple;
      }
    } catch {
      if (asked === this._askedOrigin) this._om = undefined;
    }
  }

  /** Ask what the condition matches after a pause; an answer still on its way is for an old condition and is dropped. */
  private _askMatchesSoon(delay: number) {
    clearTimeout(this._timer);
    this._askedMatches++;
    if (!conditionComplete(this._cond)) {
      this._matches = undefined;
      this._matching = false;
      return;
    }
    this._matching = true;
    this._timer = setTimeout(() => void this._askMatches(), delay);
  }

  private _wire(c: Condition) {
    return { origin: c.origin || null, title_mode: c.title_mode, title_value: c.title_mode === "any" ? "" : c.title_value };
  }

  private async _askMatches() {
    const asked = ++this._askedMatches;
    this._matching = true;
    try {
      const m = await fetchKindMatches(this.hass, this._wire(this._cond), this._kindId);
      if (asked === this._askedMatches) this._matches = m;
    } catch {
      if (asked === this._askedMatches) this._matches = undefined;
    } finally {
      if (asked === this._askedMatches) this._matching = false;
    }
  }

  // ----- changes --------------------------------------------------------------------

  private _condChanged(next: FormData) {
    const prev = this._cond;
    const mode = (next.title_mode as TitleMode | undefined) ?? prev.title_mode;
    // the text field is empty while "any" is chosen; the text typed before comes back with another comparison
    const typed = String(next.title_value ?? "");
    const c: Condition = {
      origin: String(next.origin ?? ""),
      title_mode: mode,
      title_value: (mode === "any" || prev.title_mode === "any") && !typed ? prev.title_value : typed,
    };
    if (c.title_mode === "any" && !originAllowsAny(c.origin)) c.title_mode = "exact";
    if (c.origin === prev.origin && c.title_mode === prev.title_mode && c.title_value === prev.title_value) return;
    this._cond = c;
    this._touched = true;
    this._switched = false;
    this._duplicate = undefined;
    if (c.origin !== prev.origin) void this._askOrigin(c.origin, false);
    this._askMatchesSoon(MATCH_DELAY);
  }

  private _applyPossible(apply: Apply) {
    if (!apply) return;
    this._cond = { ...this._cond, ...apply };
    this._touched = true;
    this._switched = false;
    this._duplicate = undefined;
    this._askMatchesSoon(0);
  }

  /** Back to the condition the kind has stored; a late answer about the automation does not switch it again. */
  private _keepPrevious() {
    if (this._source.from !== "edit") return;
    const k = this._source.kind;
    this._cond = conditionOf(k);
    this._titleOpen = this._multiple && k.title_mode !== "any";
    this._touched = true;
    this._switched = false;
    this._duplicate = undefined;
    this._askMatchesSoon(0);
  }

  private _pick(key: string) {
    const item = this.unknown.find((u) => pairKey(u) === key);
    if (!item) return;
    const group = this.source.from === "blank" ? this.source.group : undefined;
    this._start({ from: "new", item, group }, false);
    this._picked = key;
  }

  private _originName(id: string): string | null {
    const known = this.config?.origins.find((o) => o.entity_id === id)?.name;
    if (known) return known;
    const state = this.hass?.states?.[id]?.attributes?.friendly_name;
    if (typeof state === "string" && state) return state;
    const s = this._source;
    if (s.from === "new" && s.item.origin === id) return s.item.origin_name;
    if (s.from === "scan" && s.item.origin === id) return s.item.name;
    return null;
  }

  private _originOptions() {
    const t = this.t;
    const options = [{ value: "", label: t("from_any") }];
    const add = (id: string, name: string | null) => {
      if (id && !options.some((o) => o.value === id)) {
        options.push({ value: id, label: id === "unknown" ? t("unknown_origin") : (name ?? id) });
      }
    };
    for (const o of this.config?.origins ?? []) add(o.entity_id, o.name);
    add(this._cond.origin, this._originName(this._cond.origin));
    const from = sourceOrigin(this._source);
    add(from, this._originName(from));
    return options;
  }

  // ----- saving -------------------------------------------------------------------

  private _close = () => {
    this.dispatchEvent(new CustomEvent("editor-closed", { bubbles: true, composed: true }));
  };

  private _save = async () => {
    const t = this.t;
    const d = this._data;
    const c = this._cond;
    this._error = "";
    this._duplicate = undefined;
    if (!String(d.name ?? "").trim()) { this._error = t("name_missing"); return; }
    if (!conditionComplete(c)) { this._error = t(c.title_mode === "any" ? "any_needs_origin" : "text_missing"); return; }
    // refused before anything is created (a new group, say); the center refuses a double as well
    const double = duplicateIn(this._kinds, c, this._kindId);
    if (double) { this._duplicate = double; return; }
    this._busy = true;
    try {
      // the message the kind is made from: would it land in "new" again?
      const probe = probeOf(this._source);
      if (probe) {
        const m = await fetchKindMatches(this.hass, this._wire(c), this._kindId, probe);
        if (landsInNew(m) && !window.confirm(fill(t("confirm_lands_in_new"), { title: probe.title }))) return;
      }
      await saveEntry(this.hass, "kind", kindPayload(d, c, await this._groupId()), this._kindId);
      this._close();
    } catch (err) {
      const double = duplicateOf(err);
      if (double) this._duplicate = double;
      else this._error = (err as { message?: string }).message ?? String(err);
    } finally {
      this._busy = false;
    }
  };

  /** The group: a name in "new group" wins over the dropdown; an existing name is reused. */
  private async _groupId(): Promise<string | null> {
    const d = this._data;
    const newName = String(d.new_group ?? "").trim();
    if (!newName) return (d.group_id as string) || null;
    const existing = (this.config?.groups ?? []).find((g) => g.name.toLowerCase() === newName.toLowerCase());
    const groupId = existing ? existing.id : (await saveEntry(this.hass, "group", {
      name: newName, icon: null, priority: Number(d.priority), spacing: Number(d.spacing ?? 0), expires_after: Number(d.expires_after ?? 0),
    })).subentry_id;
    // a retry after a failure of the kind must not create the group twice
    this._data = { ...this._data, group_id: groupId, new_group: "" };
    return groupId;
  }

  private _editExisting(e: Event, kindId: string) {
    e.preventDefault();
    this.dispatchEvent(new CustomEvent("edit-kind", { detail: { kind_id: kindId }, bubbles: true, composed: true }));
  }

  // ----- rendering ------------------------------------------------------------------

  render() {
    const t = this.t;
    const heading = this._source.from === "edit" ? `${t("edit")}: ${this._source.kind.name}` : t("add_kind");
    const content = html`
      <div class="applies">${appliesTo(t, this._cond, (id) => this._originName(id))}</div>
      ${this._renderPick()}
      ${formFields(this.hass, [{ name: "name", required: true, selector: { text: {} } }], this._data, { name: t("name") }, undefined,
        (next) => { this._data = { ...this._data, name: next.name }; })}
      ${this._renderCondition()}
      ${this._renderRest()}
      ${this._renderMatches()}
      ${this._duplicate ? html`<div class="error">${fill(t("duplicate"), { name: this._duplicate.name })}<button class="link"
        @click=${(e: Event) => this._editExisting(e, this._duplicate!.kind_id)}>${t("duplicate_edit")}</button></div>` : nothing}
      ${this._error ? html`<div class="error">${this._error}</div>` : nothing}
    `;
    if (customElements.get("ha-dialog")) {
      return html`<ha-dialog .open=${true} header-title=${heading} .preventScrimClose=${true} @closed=${this._close}>
        ${content}
        <ha-button slot="footer" appearance="plain" @click=${this._close}>${t("cancel")}</ha-button>
        <ha-button slot="footer" .disabled=${this._busy} @click=${this._save}>${t("save")}</ha-button>
      </ha-dialog>`;
    }
    return html`<ha-card .header=${heading}>
      <div class="card-content">${content}</div>
      <div class="card-actions">
        <ha-button appearance="plain" @click=${this._close}>${t("cancel")}</ha-button>
        <ha-button .disabled=${this._busy} @click=${this._save}>${t("save")}</ha-button>
      </div>
    </ha-card>`;
  }

  /** "Take from New": only for a new kind without a template. */
  private _renderPick() {
    const t = this.t;
    if (this.source.from !== "blank" || !this.unknown.length) return nothing;
    const options = this.unknown.map((u) => ({
      value: pairKey(u),
      label: `${u.title} · ${u.origin_name ?? (u.origin === "unknown" ? t("unknown_origin") : u.origin)}`,
    }));
    const fields: Field[] = [{ name: "from_new", selector: { select: { options, mode: "dropdown" } } }];
    return formFields(this.hass, fields, { from_new: this._picked }, { from_new: t("from_new") }, undefined,
      (next) => this._pick(String(next.from_new ?? "")));
  }

  private _renderCondition() {
    const t = this.t;
    const c = this._cond;
    const open = !this._locked || this._advanced;
    const any = c.title_mode === "any";
    const fields: Field[] = [
      { name: "origin", disabled: !open, selector: { select: { options: this._originOptions(), mode: "dropdown" } } },
      { name: "title_mode", required: true, disabled: !open, selector: { select: { options: modeOptions(t, c.origin), mode: "dropdown" } } },
      { name: "title_value", disabled: any || !(open || this._titleOpen), selector: { text: {} } },
    ];
    const labels = { origin: t("origin"), title_mode: t("title_mode"), title_value: t("title_value") };
    const helpers = any ? { title_value: forOrigin(t, "any_helper", c.origin) } : undefined;
    const data = { origin: c.origin, title_mode: c.title_mode, title_value: any ? "" : c.title_value };
    return html`<div class="cond">
      <div class="cond-head"><span>${t("condition")}</span>${this._locked && !this._advanced
        ? html`<button class="link" @click=${() => { this._advanced = true; }}>${t("condition_edit")}</button>` : nothing}</div>
      ${formFields(this.hass, fields, data, labels, helpers, (next) => this._condChanged(next))}
      ${this._switched ? html`<div class="note">${forOrigin(t, "hint_one", c.origin)} <button class="link"
        @click=${() => this._keepPrevious()}>${t("keep_previous")}</button></div>` : nothing}
      ${this._advanced ? html`<div class="hint">${t("hint_advanced")}</div>` : nothing}
      ${this._multiple ? html`<div class="hint">${forOrigin(t, "hint_multiple", c.origin)}</div>${this._renderPossible()}` : nothing}
    </div>`;
  }

  /** The messages the automation may send; "use" puts one into the condition. */
  private _renderPossible() {
    const t = this.t;
    const list = this._om ? possibleMessages(this._om) : [];
    if (!list.length) return nothing;
    const c = this._cond;
    const isCurrent = (a: Apply) => !!a && a.title_mode === c.title_mode && a.title_value.toLowerCase() === c.title_value.trim().toLowerCase();
    return html`<div class="possible">
      <div class="p-head">${t("possible_title")}</div>
      <ul>${list.map((p) => html`<li class=${isCurrent(p.apply) ? "current" : ""}>
        <span class="p-label">${p.label}</span><span class="chip">${t(`possible_${p.tag}`)}</span>
        ${p.apply && !isCurrent(p.apply) ? html`<ha-button appearance="plain" size="small"
          @click=${() => this._applyPossible(p.apply)}>${t("possible_use")}</ha-button>` : nothing}
      </li>`)}</ul>
    </div>`;
  }

  private _renderRest() {
    const t = this.t;
    const groups = [{ value: "", label: t("no_group") }, ...(this.config?.groups ?? []).map((g) => ({ value: g.id, label: g.name }))];
    const fields: Field[] = [
      { name: "group_id", selector: { select: { options: groups, mode: "dropdown" } } },
      { name: "new_group", selector: { text: {} } },
      { name: "priority", required: true, selector: { select: { options: [
        { value: "1", label: t("p1") }, { value: "2", label: t("p2") }, { value: "3", label: t("p3") }], mode: "dropdown" } } },
      { name: "no_hold", selector: { boolean: {} } },
      { name: "spacing", selector: { number: { min: 0, max: 10080, mode: "box", unit_of_measurement: "min" } } },
      { name: "expires_after", selector: { number: { min: 0, max: 10080, mode: "box", unit_of_measurement: "min" } } },
      { name: "light", selector: { select: { options: [
        { value: "auto", label: t("light_auto") }, { value: "on", label: t("light_on") }, { value: "off", label: t("light_off") }], mode: "dropdown" } } },
      { name: "active", selector: { boolean: {} } },
    ];
    const labels = Object.fromEntries(fields.map((f) => [f.name, t(f.name)]));
    return formFields(this.hass, fields, this._data, labels, { new_group: t("new_group_helper") }, (next) => {
      // a new kind takes the defaults of the group chosen
      const changedGroup = next.group_id !== this._data.group_id && this._source.from !== "edit";
      this._data = changedGroup ? this._withDefaults({ ...this._data, ...next }, next.group_id) : { ...this._data, ...next };
    });
  }

  /** What the condition matches in "new" and among the stored messages, and where it overlaps. */
  private _renderMatches() {
    const t = this.t;
    const m = this._matches;
    const complete = conditionComplete(this._cond);
    if (complete && !m && !this._matching) return nothing;
    const busy = this._matching ? html` <span class="busy">${t("matches_loading")}</span>` : nothing;
    let body: unknown = nothing;
    if (!complete) body = html`<div class="m-note">${t("matches_incomplete")}</div>`;
    else if (m && !m.new_count && !m.seen_count) body = html`<div class="m-warn">${t("matches_none")}</div>`;
    else if (m) {
      body = html`${this._renderPairs(t("matches_new"), m.new, m.new_count, true)}
        ${this._renderPairs(t("matches_seen"), m.seen, m.seen_count, false)}
        ${m.taken_count ? html`<div class="m-note">${counted(t, "matches_taken", m.taken_count)}</div>` : nothing}`;
    }
    const overlaps = complete && m ? m.overlaps : [];
    return html`<div class="matches">
      <div class="m-head">${t("matches_title")}${busy}</div>
      ${body}
      ${overlaps.map((o) => html`<div class="m-overlap m-warn">${fill(t("overlap"), {
        name: o.name, winner: t(o.winner === "this" ? "overlap_this" : "overlap_other") })}</div>`)}
      ${m && complete && m.overlap_count > m.overlaps.length
        ? html`<div class="m-note">${counted(t, "overlap_more", m.overlap_count - m.overlaps.length)}</div>` : nothing}
    </div>`;
  }

  private _renderPairs(label: string, pairs: MatchedPair[], count: number, fromNew: boolean) {
    const t = this.t;
    if (!count) return nothing;
    return html`<div class="m-sub">${fill(label, { n: count })}</div>
      <ul>${pairs.map((p) => html`<li>${p.title} <span class="m-origin">· ${p.origin_name ?? (p.origin === "unknown" ? t("unknown_origin") : p.origin)}${
        fromNew && p.count ? ` · ${p.count}×` : ""}</span>${p.taken_by ? html` <span class="m-taken">→ ${fill(t("matches_taken"), { name: p.taken_by.name })}</span>` : nothing}</li>`)}</ul>
      ${count > pairs.length ? html`<div class="m-note">${fill(t("matches_more"), { n: count - pairs.length })}</div>` : nothing}`;
  }
}

// Registered only once: after an update Home Assistant imports the page module
// again under a new URL in the same tab, and a second define() would throw.
if (!customElements.get("message-center-kind-editor")) customElements.define("message-center-kind-editor", MessageCenterKindEditor);

declare global {
  interface HTMLElementTagNameMap {
    "message-center-kind-editor": MessageCenterKindEditor;
  }
}
