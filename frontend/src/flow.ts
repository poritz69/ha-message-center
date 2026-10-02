import { LitElement, css, html, nothing, svg, type TemplateResult } from "lit";
import { property, state } from "lit/decorators.js";
import type { Translate } from "./i18n";

// A small looping picture of what happens to a message, for the overview:
// in -> assigned to a kind -> open -> delivery rules -> (held, back to open
// with a reason, waits) -> rules again -> recipient, with the effect of the
// priority. It runs once per priority with the night rule active, as the
// rule is usually set: 1 and 2 are held, 3 passes. Purely illustrative; it
// reads nothing from the center and changes nothing.

interface Step {
  at: number; // station index: 0 in, 1 kind, 2 open, 3 rules, 4 recipient
  text: string;
  ms: number;
  night: boolean;
  hidden?: boolean;
  wait?: boolean;
  effect?: boolean;
}

interface Layout {
  w: number; h: number; xs: number[]; y: number; bw: number; bh: number; ty: number;
  scale: number; sub: boolean; font: number;
}

const WIDE: Layout = { w: 720, h: 148, xs: [72, 216, 360, 504, 648], y: 44, bw: 120, bh: 80, ty: 120, scale: 1, sub: true, font: 13 };
const COMPACT: Layout = { w: 340, h: 112, xs: [42, 106, 170, 234, 298], y: 32, bw: 58, bh: 56, ty: 88, scale: 0.8, sub: false, font: 10 };
const RING = 2 * Math.PI * 19;
const STORE_KEY = "message_center_flow_paused";

/** The pause choice is remembered per browser; storage may be unavailable. */
const storedPause = (): boolean => { try { return localStorage.getItem(STORE_KEY) === "1"; } catch { return false; } };
const storePause = (paused: boolean) => { try { localStorage.setItem(STORE_KEY, paused ? "1" : "0"); } catch { /* not kept */ } };

export class MessageCenterFlow extends LitElement {
  @property({ attribute: false }) public t!: Translate;
  @state() private _level = 1;
  @state() private _i = 0;
  @state() private _paused = false;
  @state() private _compact = false;
  @state() private _count = 0;
  private _timer?: number;
  private _tick?: number;
  private _resize?: ResizeObserver;

  static styles = css`
    :host { display: block; padding: 12px 16px 14px; }
    .head { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; margin-bottom: 6px; }
    .head .title { font-size: 16px; font-weight: 500; flex: 1 1 auto; }
    .head.compact .title { flex-basis: 100%; }
    .head.compact button.ctl { margin-left: auto; }
    .lv { font-size: 12px; padding: 1px 9px; border-radius: 10px; border: 1px solid var(--divider-color);
      color: var(--secondary-text-color); transition: background .3s, color .3s; white-space: nowrap; }
    .lv.on.p1 { background: var(--primary-color); color: #fff; border-color: transparent; }
    .lv.on.p2 { background: var(--warning-color); color: #000; border-color: transparent; }
    .lv.on.p3 { background: var(--error-color); color: #fff; border-color: transparent; }
    button.ctl { border: 0; background: transparent; color: var(--secondary-text-color); cursor: pointer; padding: 4px;
      border-radius: 50%; display: inline-flex; }
    button.ctl:hover { background: var(--secondary-background-color); color: var(--primary-text-color); }
    svg.stage { display: block; width: 100%; height: auto; margin: 0 auto; }
    svg.stage.compact { max-width: 440px; }
    .caption { min-height: 2.8em; margin-top: 4px; font-size: 14px; line-height: 1.4; color: var(--primary-text-color); text-align: center; }
    .track { stroke: var(--divider-color); stroke-width: 2; stroke-dasharray: 2 6; stroke-linecap: round; fill: none; }
    .stop { fill: var(--divider-color); }
    .station rect { fill: var(--secondary-background-color, rgba(127,127,127,.08)); stroke: var(--divider-color); stroke-width: 1.5;
      transition: stroke .3s, stroke-width .3s; }
    .station.active rect { stroke: var(--primary-color); stroke-width: 2.5; }
    .station text { text-anchor: middle; fill: var(--primary-text-color); font-family: inherit; }
    .station text.label { font-weight: 500; }
    .station text.sub { fill: var(--secondary-text-color); font-size: 10.5px; }
    .ico { fill: none; stroke: var(--secondary-text-color); stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
    .station.active .ico { stroke: var(--primary-text-color); }
    .moon { transition: fill .5s, stroke .5s; }
    .moon.on { fill: #f5c542; stroke: #f5c542; }
    .glow { fill: #f5c542; stroke: #f5c542; transition: opacity .2s; }
    .dot { fill: var(--error-color); stroke: none; opacity: 0; }
    .token { transition: transform .9s cubic-bezier(.4, 0, .2, 1), opacity .35s; }
    .token.hidden { opacity: 0; transition: none; }
    .token .env { stroke: none; }
    .token.lvl1 .env { fill: var(--primary-color); }
    .token.lvl2 .env { fill: var(--warning-color); }
    .token.lvl3 .env { fill: var(--error-color); }
    .token .flap { fill: none; stroke: #fff; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
    .token.lvl2 .flap { stroke: #000; }
    .token .ring { fill: none; stroke: var(--primary-text-color); stroke-width: 2.5; stroke-linecap: round;
      stroke-dasharray: ${RING}; animation: drain linear forwards; }
    @keyframes drain { from { stroke-dashoffset: 0; } to { stroke-dashoffset: ${RING}; } }
    .fx { transform-box: fill-box; transform-origin: center; }
    .phone.ring1 .fx, .phone.ring2 .fx { animation: wiggle .45s ease-in-out .5s 3; }
    .phone.ring3 .fx { animation: wiggle .3s ease-in-out .5s 9; }
    .phone.ring1 .dot, .phone.ring2 .dot, .phone.ring3 .dot { animation: pop .3s ease-out .5s forwards; }
    @keyframes wiggle { 0%, 100% { transform: rotate(0); } 25% { transform: rotate(-14deg); } 75% { transform: rotate(14deg); } }
    @keyframes pop { to { opacity: 1; } }
    .lamp.ring2 .glow { animation: pulse 1.5s linear .9s 1; }
    .lamp.ring3 .glow { animation: alarm .6s steps(1) .9s 5; }
    @keyframes pulse { 0%, 15% { opacity: 1; } 22%, 62% { opacity: .08; } 70%, 100% { opacity: 1; } }
    @keyframes alarm { 0% { opacity: .08; } 50% { opacity: 1; } }
    @media (prefers-reduced-motion: reduce) { .token { transition: opacity .35s; } }
  `;

  connectedCallback() {
    super.connectedCallback();
    this._resize = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width ?? 0;
      if (width) this._compact = width < 560;
    });
    this._resize.observe(this);
    if (storedPause() || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      // paused last time, or no motion wanted: show the waiting message and stop
      this._paused = true;
      this._level = 2;
      this._i = this._steps(2).findIndex((s) => s.wait);
    } else {
      this._enter(0);
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._resize?.disconnect();
    this._clear();
  }

  private _clear() {
    window.clearTimeout(this._timer);
    window.clearInterval(this._tick);
    this._timer = undefined;
    this._tick = undefined;
  }

  private _steps(level: number): Step[] {
    const t = this.t;
    const fill = (key: string) => t(key).replace("{n}", String(level)).replace("{name}", t(`level_${level}_name`));
    const start: Step[] = [
      { at: 0, text: "", ms: 500, night: true, hidden: true },
      { at: 0, text: fill("flow_c_in"), ms: 2400, night: true },
      { at: 1, text: fill("flow_c_kind"), ms: 3200, night: true },
      { at: 2, text: fill("flow_c_open"), ms: 2000, night: true },
    ];
    const end: Step[] = [
      { at: 4, text: fill(`flow_c_out_${level}`), ms: level === 3 ? 4800 : 4000, night: level === 3, effect: true },
      { at: 4, text: "", ms: 500, night: level === 3, hidden: true },
    ];
    if (level === 3) return [...start, { at: 3, text: fill("flow_c_rules_pass"), ms: 3000, night: true }, ...end];
    return [
      ...start,
      { at: 3, text: fill("flow_c_rules_hold"), ms: 3000, night: true },
      { at: 2, text: fill("flow_c_wait"), ms: 4000, night: true, wait: true },
      { at: 2, text: fill("flow_c_night_off"), ms: 2600, night: false },
      { at: 3, text: fill("flow_c_rules_free"), ms: 2200, night: false },
      ...end,
    ];
  }

  private _enter(i: number) {
    this._clear();
    this._i = i;
    const step = this._steps(this._level)[i];
    if (step.wait) {
      this._count = Math.ceil(step.ms / 1000);
      this._tick = window.setInterval(() => { if (this._count > 1) this._count -= 1; }, 1000);
    }
    this._timer = window.setTimeout(() => { if (!this._paused) this._advance(); else this._timer = undefined; }, step.ms);
  }

  private _advance() {
    const steps = this._steps(this._level);
    if (this._i + 1 < steps.length) {
      this._enter(this._i + 1);
    } else {
      this._level = (this._level % 3) + 1;
      this._enter(0);
    }
  }

  private _toggle = () => {
    this._paused = !this._paused;
    storePause(this._paused);
    // a running step ends on its own; when it already ended while paused, go on now
    if (!this._paused && this._timer === undefined) this._advance();
  };

  render() {
    const t = this.t;
    const L = this._compact ? COMPACT : WIDE;
    const step = this._steps(this._level)[this._i];
    const fx = step.effect ? `ring${this._level}` : "";
    const icons: TemplateResult[] = [
      svg`<rect class="ico" x="-11" y="-8" width="22" height="16" rx="2"></rect><polyline class="ico" points="-11,-7 0,2 11,-7"></polyline>`,
      svg`<path class="ico" d="M-10 -8 H2 L11 0 L2 8 H-10 Z"></path><circle class="ico" cx="-5" cy="0" r="1.6"></circle>`,
      svg`<path class="ico" d="M-11 -1 L-7 -9 H7 L11 -1 V8 H-11 Z"></path><path class="ico" d="M-11 -1 H-4 Q-4 3 0 3 Q4 3 4 -1 H11"></path>`,
      svg`<path class="ico moon ${step.night ? "on" : ""}" d="M3 -10 A10 10 0 1 0 10 4 A8.5 8.5 0 0 1 3 -10 Z"></path>`,
      svg`<g transform="translate(-13 0)" class="phone ${fx}"><g class="fx">
            <rect class="ico" x="-6" y="-11" width="12" height="22" rx="2.5"></rect><path class="ico" d="M-2 7.5 H2"></path>
            <circle class="dot" cx="6" cy="-10" r="3.6"></circle></g></g>
          <g transform="translate(13 0)" class="lamp ${fx}">
            <circle class="ico glow" cx="0" cy="-3" r="6.5"></circle><path class="ico" d="M-3 5.5 H3 M-2 8.5 H2"></path></g>`,
    ];
    const labels = ["flow_s_in", "flow_s_kind", "flow_s_open", this._compact ? "flow_s_rules_short" : "flow_s_rules", "flow_s_out"].map((k) => t(k));
    const subs = [
      t("flow_s_in_sub"), t("flow_s_kind_sub"),
      step.wait ? t("flow_waiting").replace("{s}", String(this._count)) : "",
      step.night ? t("flow_night_on") : t("flow_night_off"), t("flow_s_out_sub"),
    ];
    const station = (i: number) => svg`<g class="station ${!step.hidden && step.at === i ? "active" : ""}">
      <rect x=${L.xs[i] - L.bw / 2} y=${L.y - L.bh / 2} width=${L.bw} height=${L.bh} rx="12"></rect>
      <g transform="translate(${L.xs[i]} ${L.y - (L.sub ? 16 : 9)}) scale(${L.scale})">${icons[i]}</g>
      <text class="label" x=${L.xs[i]} y=${L.y + (L.sub ? 12 : 20)} font-size=${L.font}>${labels[i]}</text>
      ${L.sub ? svg`<text class="sub" x=${L.xs[i]} y=${L.y + 28}>${subs[i]}</text>` : nothing}
    </g>`;
    return html`
      <div class="head ${this._compact ? "compact" : ""}">
        <span class="title">${t("flow_title")}</span>
        ${[1, 2, 3].map((n) => html`<span class="lv p${n} ${n === this._level ? "on" : ""}">${n} · ${t(`level_${n}_name`)}</span>`)}
        <button class="ctl" @click=${this._toggle} title=${this._paused ? t("flow_play") : t("flow_pause")} aria-label=${this._paused ? t("flow_play") : t("flow_pause")}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">${this._paused
            ? svg`<path d="M8 5v14l11-7z"></path>` : svg`<path d="M6 5h4v14H6zM14 5h4v14h-4z"></path>`}</svg>
        </button>
      </div>
      <svg class="stage ${this._compact ? "compact" : ""}" viewBox="0 0 ${L.w} ${L.h}" role="img" aria-label=${t("flow_title")}>
        <path class="track" d="M${L.xs[0]} ${L.ty} H${L.xs[4]}"></path>
        ${L.xs.map((x) => svg`<circle class="stop" cx=${x} cy=${L.ty} r="3"></circle>`)}
        ${[0, 1, 2, 3, 4].map(station)}
        <g class="token lvl${this._level} ${step.hidden ? "hidden" : ""}" style="transform: translate(${L.xs[step.at]}px, ${L.ty}px)">
          <g transform="scale(${L.scale})">
            ${step.wait ? svg`<circle class="ring" r="19" transform="rotate(-90)" style="animation-duration: ${step.ms}ms"></circle>` : nothing}
            <rect class="env" x="-14" y="-10" width="28" height="20" rx="3"></rect>
            <polyline class="flap" points="-13,-9 0,1.5 13,-9"></polyline>
          </g>
        </g>
      </svg>
      <div class="caption">${step.text || html`&nbsp;`}</div>
    `;
  }
}

if (!customElements.get("message-center-flow")) customElements.define("message-center-flow", MessageCenterFlow);
