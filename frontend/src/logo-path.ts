// The logo's outline: a house that is also a speech bubble, with "MC" cut out.
// Designed by poritz69, redrawn as one vector path. The house runs
// clockwise, the letters counter-clockwise, so they are holes under both fill
// rules. No imports here: the sidebar icon module must stay tiny.
export const LOGO_VIEWBOX = "318 61 900 900";
export const LOGO_PATH = [
  // house with chimney and the bubble's tail, clockwise from the roof top
  "M742.1 114.1A41 41 0 0 1 793.9 114.1L991 274.5V211Q991 196 1006 196H1081Q1096 196 1096 211V359.9",
  "L1188.6 435.2A41 41 0 0 1 1162.7 508H1135V740A75 75 0 0 1 1060 815H640L528 912",
  "A22 22 0 0 1 491.6 895.4V815H479A75 75 0 0 1 404 740V508H373.3A41 41 0 0 1 347.4 435.2Z",
  // M
  "M497 461V719H575V587L640 663L704 587V719H781V461H704L640 545L575 461Z",
  // C
  "M1048 517A134 134 0 1 0 1048 663L984.6 621.7A58 58 0 1 1 984.6 558.3Z",
].join("");
