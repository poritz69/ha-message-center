// The links a tapped push opens. With the option "open Message Center" a push
// opens "/message-center?message=<id>": the page shows that message unfolded,
// on the tab Open or in the history. A message no kind takes opens
// "/message-center?classify=<id>": the dialog to classify its entry of "New";
// when that entry is gone (classified or dismissed) the message is shown.
import type { MessageEntry, UnknownItem } from "./types";

export interface DeepLink {
  mode: "message" | "classify";
  id: string;
}

export type DeepLinkTarget =
  | { action: "classify"; item: UnknownItem }
  | { action: "show"; tab: "open" | "history"; key: string }
  | { action: "missing" };

const KEYS = ["classify", "message"] as const;
// a message id: 16 hexadecimal characters (README, "message_id")
const ID = /^[0-9a-f]{16}$/;

/** The link in an address's query ("?message=…" or "?classify=…"); classify first, null when there is none. */
export function readDeepLink(search: string): DeepLink | null {
  const params = new URLSearchParams(search);
  for (const mode of KEYS) {
    const id = (params.get(mode) ?? "").toLowerCase();
    if (ID.test(id)) return { mode, id };
  }
  return null;
}

/** The query without the link, other parameters kept: "" or "?a=b". */
export function withoutDeepLink(search: string): string {
  const params = new URLSearchParams(search);
  for (const key of KEYS) params.delete(key);
  const rest = params.toString();
  return rest ? `?${rest}` : "";
}

/**
 * A row of the tables: one generation of a message. The id is the same for
 * all generations, and the history holds the earlier ones of a message that
 * came back; the row of each is unfolded on its own.
 */
export function rowKey(e: Pick<MessageEntry, "message_id" | "generation">): string {
  return `${e.message_id}:${e.generation}`;
}

/**
 * Where the link leads among what the page holds: `open` are the open
 * messages, `ended` those in the history (recent and older), `unknown`
 * the entries of "New". The id names all generations of the message; the
 * target is the newest: the open one, else the latest ended one.
 */
export function resolveDeepLink(link: DeepLink, open: readonly MessageEntry[], ended: readonly MessageEntry[],
  unknown: readonly UnknownItem[]): DeepLinkTarget {
  const isOpen = open.find((e) => e.message_id === link.id);
  const entry = isOpen ?? ended.filter((e) => e.message_id === link.id)
    .reduce<MessageEntry | undefined>((newest, e) => (!newest || e.generation > newest.generation ? e : newest), undefined);
  if (!entry) return { action: "missing" };
  if (link.mode === "classify") {
    const item = unknown.find((u) => u.origin === entry.origin && u.title === entry.title);
    if (item) return { action: "classify", item };
  }
  return { action: "show", tab: isOpen ? "open" : "history", key: rowKey(entry) };
}
