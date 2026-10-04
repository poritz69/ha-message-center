// The notes the search over the house shows for a call, free of the page's
// elements. A call without a title is called after its automation (or, in a
// script, after the automation that starts the script, else after the
// script); it needs a title of its own only when the automation sends
// several messages. Tested by test/scan-logic.test.ts.
import type { ScanItem } from "./types";

/** The note on the title of a found call: a text key and the name it names, or null for none. */
export const scanNote = (i: ScanItem): { key: string; name?: string } | null => {
  if (i.status === "persistent") return null;
  if (!i.title) {
    if (!i.origin) return { key: "scan_untitled_script" };
    return { key: i.multiple ? "scan_untitled_many" : "scan_untitled_one", name: i.name };
  }
  return i.suggestion ? null : { key: "scan_title_computed" };
};
