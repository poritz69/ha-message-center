import { html, svg, type TemplateResult } from "lit";

import { LOGO_PATH, LOGO_VIEWBOX } from "./logo-path";

/**
 * The logo as inline SVG in the current text colour. With `dots`, three points
 * in the priority colours (1 notice, 2 important, 3 alarm) sit under the gable.
 */
export const logoMark = (size = 40, dots = true): TemplateResult =>
  html`<svg class="mc-logo" width=${size} height=${size} viewBox=${LOGO_VIEWBOX} aria-hidden="true">
    <path fill="currentColor" fill-rule="evenodd" d=${LOGO_PATH}></path>
    ${dots ? svg`<circle cx="658" cy="368" r="40" fill="var(--primary-color)"></circle>
      <circle cx="768" cy="368" r="40" fill="var(--warning-color)"></circle>
      <circle cx="878" cy="368" r="40" fill="var(--error-color)"></circle>` : ""}
  </svg>`;
