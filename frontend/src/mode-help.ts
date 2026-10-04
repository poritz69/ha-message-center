import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";
import { createSwitch } from "./api";
import { fallbackStyles, formFields, type Field } from "./editor";
import type { Translate } from "./i18n";
import { icon } from "./icons";
import { fill } from "./kind-logic";
import { switchEntityId } from "./rule-logic";
import type { HomeAssistant } from "./types";

const NAME_FIELD: Field[] = [{ name: "switch_name", required: true, selector: { text: {} } }];

/**
 * Help on modes in the delivery rule dialog: a box that unfolds "What is a
 * mode?", the button "Create toggle" with a name field, and, always in
 * sight, the note that the toggle is not switched here. A created toggle is
 * announced with the event "switch-created" ({ entity_id, name }); the dialog
 * then chooses it for the rule. Message Center only creates the toggle: it
 * never switches it and creates no automation.
 */
export class MessageCenterModeHelp extends LitElement {
  @property({ attribute: false }) public hass!: HomeAssistant;
  @property({ attribute: false }) public t!: Translate;
  @state() private _naming = false;
  @state() private _name = "";
  @state() private _busy = false;
  @state() private _error = "";
  /** Name of the toggle created last, for the note under the button. */
  @state() private _created = "";

  static styles = [fallbackStyles, css`
    :host { display: block; margin: 0 0 12px; }
    .ico { flex: none; display: block; }
    details { border: 1px solid var(--divider-color); border-radius: 8px; }
    summary { display: flex; align-items: center; gap: 8px; padding: 9px 12px; cursor: pointer; font-weight: 500; list-style: none; }
    summary::-webkit-details-marker { display: none; }
    summary .ico { color: var(--secondary-text-color); transition: transform .15s; }
    details[open] summary .ico { transform: rotate(90deg); }
    details p { margin: 0; padding: 0 12px 10px 38px; font-size: 13px; line-height: 1.45; color: var(--secondary-text-color); }
    .create { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 12px; }
    .naming { margin-top: 12px; padding: 4px 12px 10px; border: 1px solid var(--divider-color); border-radius: 8px; }
    .naming .buttons { display: flex; justify-content: flex-end; gap: 8px; margin-top: 6px; }
    .hint { display: flex; align-items: flex-start; gap: 8px; margin-top: 10px; padding: 8px 12px; border-radius: 8px; font-size: 13px; line-height: 1.4;
      background: color-mix(in srgb, var(--warning-color) 14%, transparent); color: var(--primary-text-color); }
    .hint .ico { margin-top: 1px; color: color-mix(in srgb, var(--warning-color) 62%, var(--primary-text-color)); }
    .done { margin-top: 8px; font-size: 13px; color: color-mix(in srgb, var(--success-color, #43a047) 70%, var(--primary-text-color)); }
    .error { margin-top: 8px; font-size: 13px; color: var(--error-color); }
  `];

  render() {
    const t = this.t;
    return html`
      <details>
        <summary>${icon("chev", 18)}${t("mode_title")}</summary>
        ${["mode_what", "mode_create", "mode_dashboard", "mode_switching"].map((key) => html`<p>${t(key)}</p>`)}
      </details>
      ${this._naming ? html`<div class="naming">
        ${formFields(this.hass, NAME_FIELD, { switch_name: this._name }, { switch_name: t("switch_name") }, undefined,
          (next) => { this._name = String(next.switch_name ?? ""); })}
        <div class="buttons">
          <ha-button appearance="plain" @click=${this._cancel}>${t("cancel")}</ha-button>
          <ha-button .disabled=${this._busy} @click=${this._create}>${t("switch_add")}</ha-button>
        </div>
      </div>` : html`<div class="create">
        <ha-button appearance="outlined" @click=${this._open}>${t("switch_create")}</ha-button>
      </div>`}
      ${this._created ? html`<div class="done">${fill(t("switch_created"), { name: this._created })}</div>` : nothing}
      ${this._error ? html`<div class="error">${this._error}</div>` : nothing}
      <div class="hint">${icon("alert", 16)}<span>${t("switch_hint")}</span></div>
    `;
  }

  private _open = () => {
    this._name = this.t("switch_name_default");
    this._naming = true;
    this._error = "";
    this._created = "";
  };

  private _cancel = () => {
    this._naming = false;
    this._error = "";
  };

  private _create = async () => {
    const name = this._name.trim();
    if (!name) {
      this._error = this.t("name_missing");
      return;
    }
    this._busy = true;
    this._error = "";
    try {
      const item = await createSwitch(this.hass, name);
      this._naming = false;
      this._created = item.name;
      this.dispatchEvent(new CustomEvent("switch-created", { detail: { entity_id: switchEntityId(item), name: item.name } }));
    } catch (err) {
      this._error = (err as { message?: string }).message ?? String(err);
    } finally {
      this._busy = false;
    }
  };
}

// Registered only once: after an update Home Assistant imports the page module
// again under a new URL in the same tab, and a second define() would throw.
if (!customElements.get("message-center-mode-help")) customElements.define("message-center-mode-help", MessageCenterModeHelp);
