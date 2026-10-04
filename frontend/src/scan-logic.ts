// The notes the search over the house shows for a call, free of the page's
// elements. A call without a title is called after its automation (or, in a
// script, after the automation that starts the script, else after the
// script); it needs a title of its own only when the automation sends
// several messages. Two or more calls without a title would replace each
// other on the phone: each of them should get a title. The center's example
// (`title_hint`, the first line of the text where it makes a title that tells
// the call apart) is named, never the raw line. Tested by
// test/scan-logic.test.ts.
import type { ScanItem } from "./types";

/** The note on the title of a found call: a text key with the name and the line it names, or null for none. */
export const scanNote = (i: ScanItem): { key: string; name?: string; line?: string } | null => {
  if (i.status === "persistent") return null;
  if (!i.title) {
    if (i.untitled_clash) {
      return i.title_hint ? { key: "scan_untitled_clash", name: i.name, line: i.title_hint } : { key: "scan_untitled_clash_noline", name: i.name };
    }
    if (!i.origin) return { key: "scan_untitled_script" };
    return { key: i.multiple ? "scan_untitled_many" : "scan_untitled_one", name: i.name };
  }
  return i.suggestion ? null : { key: "scan_title_computed" };
};
