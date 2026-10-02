import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";
import type { HomeAssistant } from "./types";
import type { Translate } from "./i18n";

export type FormData = Record<string, unknown>;

export interface Field {
  name: string;
  required?: boolean;
  selector: Record<string, unknown>;
}

// A dialog with an ha-form. Falls back to plain inputs when ha-form is not
// available (should not happen after ensureHaElements, but the page must
// never be unusable).
export class MessageCenterEditor extends LitElement {
  @property({ attribute: false }) public hass!: HomeAssistant;
  @property({ attribute: false }) public t!: Translate;
  @property() public heading = "";
  @property({ attribute: false }) public fields: Field[] = [];
  /** Initial values. The form keeps its own copy: the page re-renders on every
   *  state change in the house and would otherwise overwrite what was typed. */
  @property({ attribute: false }) public data: FormData = {};
  @property({ attribute: false }) public labels: Record<string, string> = {};
  @property({ attribute: false }) public helpers?: Record<string, string>;
  @property({ attribute: false }) public onSave!: (data: FormData) => Promise<void>;
  /** Optional hook to adjust the data after a change, e.g. to prefill defaults. */
  @property({ attribute: false }) public onChange?: (next: FormData, prev: FormData) => FormData;
  @state() private _error = "";
  @state() private _busy = false;
  @state() private _data: FormData = {};

  protected willUpdate(changed: Map<string, unknown>) {
    if (changed.has("data")) this._data = this.data;
  }

  static styles = css`
    .error { color: var(--error-color); margin-top: 8px; }
    .fallback label { display: block; margin: 8px 0 4px; font-weight: 500; }
    .fallback input, .fallback select { width: 100%; padding: 8px; box-sizing: border-box; }
  `;

  connectedCallback() {
    super.connectedCallback();
    // While the form is open, typed letters must never reach Home Assistant's
    // global shortcuts (e.g. "c" opens the command search when a dropdown has focus).
    this.addEventListener("keydown", this._swallowKeys);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.removeEventListener("keydown", this._swallowKeys);
  }

  private _swallowKeys = (e: KeyboardEvent) => { e.stopPropagation(); };

  render() {
    const hasForm = !!customElements.get("ha-form");
    const body = hasForm
      ? html`<ha-form
          .hass=${this.hass}
          .schema=${this.fields}
          .data=${this._data}
          .computeLabel=${(f: Field) => this.labels[f.name] ?? f.name}
          .computeHelper=${(f: Field) => this.helpers?.[f.name]}
          @value-changed=${(e: CustomEvent) => this._set(e.detail.value as FormData)}
        ></ha-form>`
      : this._fallbackForm();
    const content = html`
      ${body}
      ${this._error ? html`<div class="error">${this._error}</div>` : nothing}
    `;
    if (customElements.get("ha-dialog")) {
      // ha-dialog (Home Assistant 2026.x, built on wa-dialog): title via
      // header-title, body in the default slot, buttons in slot "footer".
      return html`<ha-dialog .open=${true} header-title=${this.heading} .preventScrimClose=${true} @closed=${this._close}>
        ${content}
        <ha-button slot="footer" appearance="plain" @click=${this._close}>${this.t("cancel")}</ha-button>
        <ha-button slot="footer" .disabled=${this._busy} @click=${this._save}>${this.t("save")}</ha-button>
      </ha-dialog>`;
    }
    return html`<ha-card .header=${this.heading}>
      <div class="card-content">${content}</div>
      <div class="card-actions">
        <ha-button appearance="plain" @click=${this._close}>${this.t("cancel")}</ha-button>
        <ha-button .disabled=${this._busy} @click=${this._save}>${this.t("save")}</ha-button>
      </div>
    </ha-card>`;
  }

  private _set(next: FormData) {
    const prev = this._data;
    this._data = this.onChange ? this.onChange(next, prev) : next;
  }

  private _fallbackForm() {
    return html`<div class="fallback">
      ${this.fields.map((f) => {
        const sel = f.selector as Record<string, { options?: { value: string; label: string }[]; min?: number; max?: number }>;
        const value = this._data[f.name];
        const set = (v: unknown) => this._set({ ...this._data, [f.name]: v });
        if (sel.select) {
          return html`<label>${this.labels[f.name] ?? f.name}</label>
            <select @change=${(e: Event) => set((e.target as HTMLSelectElement).value)}>
              ${sel.select.options?.map((o) => html`<option value=${o.value} ?selected=${o.value === value}>${o.label}</option>`)}
            </select>`;
        }
        if (sel.boolean) {
          return html`<label><input type="checkbox" ?checked=${!!value} @change=${(e: Event) => set((e.target as HTMLInputElement).checked)} /> ${this.labels[f.name] ?? f.name}</label>`;
        }
        if (sel.number) {
          return html`<label>${this.labels[f.name] ?? f.name}</label>
            <input type="number" .value=${String(value ?? "")} min=${sel.number.min ?? 0} max=${sel.number.max ?? 99999} @input=${(e: Event) => set(Number((e.target as HTMLInputElement).value))} />`;
        }
        return html`<label>${this.labels[f.name] ?? f.name}</label>
          <input type="text" .value=${String(value ?? "")} @input=${(e: Event) => set((e.target as HTMLInputElement).value)} />`;
      })}
    </div>`;
  }

  private _close = () => {
    this.dispatchEvent(new CustomEvent("editor-closed", { bubbles: true, composed: true }));
  };

  private _save = async () => {
    this._busy = true;
    this._error = "";
    try {
      await this.onSave(this._data);
      this._close();
    } catch (err) {
      this._error = (err as { message?: string }).message ?? String(err);
    } finally {
      this._busy = false;
    }
  };
}

// Registered only once: after an update Home Assistant imports the page module
// again under a new URL in the same tab, and a second define() would throw.
if (!customElements.get("message-center-editor")) customElements.define("message-center-editor", MessageCenterEditor);
