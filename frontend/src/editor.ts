import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";
import type { HomeAssistant } from "./types";
import type { Translate } from "./i18n";

export type FormData = Record<string, unknown>;

export interface Field {
  name: string;
  required?: boolean;
  /** Shown but locked (ha-form greys it out). */
  disabled?: boolean;
  selector: Record<string, unknown>;
}

/** Styles of the plain inputs that stand in when ha-form is missing. */
export const fallbackStyles = css`
  .fallback label { display: block; margin: 8px 0 4px; font-weight: 500; }
  .fallback input, .fallback select { width: 100%; padding: 8px; box-sizing: border-box; }
  .fallback .helper { font-size: 12px; color: var(--secondary-text-color); margin-top: 2px; }
`;

/**
 * The fields of a form: an ha-form, or plain inputs when ha-form is not
 * available (should not happen after ensureHaElements, but the page must
 * never be unusable). `onValue` gets the whole data with the change.
 */
export function formFields(
  hass: HomeAssistant, fields: Field[], data: FormData, labels: Record<string, string>,
  helpers: Record<string, string> | undefined, onValue: (next: FormData) => void
) {
  if (customElements.get("ha-form")) {
    return html`<ha-form .hass=${hass} .schema=${fields} .data=${data}
      .computeLabel=${(f: Field) => labels[f.name] ?? f.name} .computeHelper=${(f: Field) => helpers?.[f.name]}
      @value-changed=${(e: CustomEvent) => onValue(e.detail.value as FormData)}></ha-form>`;
  }
  return html`<div class="fallback">
    ${fields.map((f) => {
      const sel = f.selector as Record<string, { options?: { value: string; label: string }[]; min?: number; max?: number }>;
      const value = data[f.name];
      const set = (v: unknown) => onValue({ ...data, [f.name]: v });
      const label = labels[f.name] ?? f.name;
      const helper = helpers?.[f.name] ? html`<div class="helper">${helpers[f.name]}</div>` : nothing;
      if (sel.select) {
        return html`<label>${label}</label>
          <select ?disabled=${!!f.disabled} @change=${(e: Event) => set((e.target as HTMLSelectElement).value)}>
            ${sel.select.options?.map((o) => html`<option value=${o.value} ?selected=${o.value === value}>${o.label}</option>`)}
          </select>${helper}`;
      }
      if (sel.boolean) {
        return html`<label><input type="checkbox" ?disabled=${!!f.disabled} ?checked=${!!value} @change=${(e: Event) => set((e.target as HTMLInputElement).checked)} /> ${label}</label>${helper}`;
      }
      if (sel.number) {
        return html`<label>${label}</label>
          <input type="number" ?disabled=${!!f.disabled} .value=${String(value ?? "")} min=${sel.number.min ?? 0} max=${sel.number.max ?? 99999} @input=${(e: Event) => set(Number((e.target as HTMLInputElement).value))} />${helper}`;
      }
      return html`<label>${label}</label>
        <input type="text" ?disabled=${!!f.disabled} .value=${String(value ?? "")} @input=${(e: Event) => set((e.target as HTMLInputElement).value)} />${helper}`;
    })}
  </div>`;
}

// A dialog with an ha-form (plain inputs without it, see formFields).
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

  /** Whether something was entered since the dialog opened (each change makes a new copy). */
  get edited(): boolean {
    return this._data !== this.data;
  }

  static styles = [fallbackStyles, css`
    .error { color: var(--error-color); margin-top: 8px; }
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
  }

  private _swallowKeys = (e: KeyboardEvent) => { e.stopPropagation(); };

  render() {
    const body = formFields(this.hass, this.fields, this._data, this.labels, this.helpers, (next) => this._set(next));
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
