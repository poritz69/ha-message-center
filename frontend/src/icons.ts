import { html, nothing, svg, type TemplateResult } from "lit";

// The page's own small line icons (24 px grid, drawn with the current text
// colour). Kept here instead of ha-icon so that tabs and states look the same
// everywhere and need nothing loaded from Home Assistant.
const SHAPES: Record<string, TemplateResult> = {
  grid: svg`<rect x="4" y="4" width="7" height="7" rx="1.5"></rect><rect x="13" y="4" width="7" height="7" rx="1.5"></rect><rect x="4" y="13" width="7" height="7" rx="1.5"></rect><rect x="13" y="13" width="7" height="7" rx="1.5"></rect>`,
  inbox: svg`<path d="M4 13l2.5-7.5h11L20 13v5a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18z"></path><path d="M4 13h4.5l1 2.5h5l1-2.5H20"></path>`,
  history: svg`<path d="M3.5 12a8.5 8.5 0 1 0 2.7-6.2L3.5 8.3"></path><path d="M3.5 3.8v4.5H8"></path><path d="M12 7.5V12l3.2 1.9"></path>`,
  tag: svg`<path d="M4 4.5h7.2l8.3 8.3a1.6 1.6 0 0 1 0 2.3l-4.9 4.9a1.6 1.6 0 0 1-2.3 0L4 11.7z"></path><circle cx="8" cy="8.5" r="1.2"></circle>`,
  moon: svg`<path d="M20 14.5A8 8 0 1 1 9.5 4a7.5 7.5 0 0 0 10.5 10.5z"></path>`,
  phone: svg`<rect x="7" y="3" width="10" height="18" rx="2.2"></rect><path d="M11 17.8h2"></path>`,
  sliders: svg`<path d="M4 6h8M16 6h4M4 12h2M10 12h10M4 18h10M18 18h2"></path><circle cx="14" cy="6" r="2"></circle><circle cx="8" cy="12" r="2"></circle><circle cx="16" cy="18" r="2"></circle>`,
  clock: svg`<circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path>`,
  retry: svg`<path d="M20 11a8 8 0 0 0-14.5-3.5"></path><path d="M4 4v4h4"></path><path d="M4 13a8 8 0 0 0 14.5 3.5"></path><path d="M20 20v-4h-4"></path>`,
  check: svg`<circle cx="12" cy="12" r="9"></circle><path d="M8 12.5l2.8 2.8L16 9.5"></path>`,
  tick: svg`<path d="M5.5 12.5l4.2 4.2 8.8-9.4"></path>`,
  ban: svg`<circle cx="12" cy="12" r="9"></circle><path d="M5.6 5.6l12.8 12.8"></path>`,
  alert: svg`<path d="M12 4l9 16H3z"></path><path d="M12 10v4.5M12 17.2v.3"></path>`,
  send: svg`<path d="M21 3L10 14"></path><path d="M21 3l-7 18-4-7-7-4z"></path>`,
  search: svg`<circle cx="11" cy="11" r="6.5"></circle><path d="M16 16l4.5 4.5"></path>`,
  file: svg`<path d="M6 3.5h8l4 4V20.5H6z"></path><path d="M14 3.5v4h4"></path>`,
  chev: svg`<path d="M9 6l6 6-6 6"></path>`,
  grip: svg`<circle cx="9" cy="6" r=".7"></circle><circle cx="15" cy="6" r=".7"></circle><circle cx="9" cy="12" r=".7"></circle><circle cx="15" cy="12" r=".7"></circle><circle cx="9" cy="18" r=".7"></circle><circle cx="15" cy="18" r=".7"></circle>`,
  pause: svg`<path d="M9 5v14M15 5v14"></path>`,
  arrow: svg`<path d="M4 12h15M13 6l6 6-6 6"></path>`,
  trash: svg`<path d="M4 7h16M9 7V4h6v3M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M10 11v6M14 11v6"></path>`,
};

export const icon = (name: string, size = 20, stroke = 1.8): TemplateResult =>
  html`<svg class="ico" width=${size} height=${size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width=${stroke} stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${SHAPES[name] ?? nothing}</svg>`;

