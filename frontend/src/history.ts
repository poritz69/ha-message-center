// The history's tables: the column "Time" is when a message ended (delivered,
// discarded, failed), always with date and time; the order, newest or oldest
// first, is remembered per browser. Tested by test/history.test.ts.
import type { MessageEntry } from "./types";

export type HistoryOrder = "newest" | "oldest";

/** The key under which the browser keeps the order. */
export const ORDER_KEY = "message_center_history_order";

type StorageLike = Pick<Storage, "getItem" | "setItem">;

/** The browser's storage; asking for it may throw (blocked site data), so it is asked inside try. */
const browserStorage = (): StorageLike | null => window.localStorage;

/** When a message ended; for one without an end its last change. */
export const endedAt = (e: Pick<MessageEntry, "ended_at" | "updated_at">): string => e.ended_at ?? e.updated_at;

/** The entries by their end, newest or oldest first; the same end keeps the given order. The list given stays as it is. */
export const sortByEnd = <T extends Pick<MessageEntry, "ended_at" | "updated_at">>(entries: readonly T[], order: HistoryOrder): T[] => {
  const sign = order === "newest" ? -1 : 1;
  return entries
    .map((e, i) => ({ e, i, at: Date.parse(endedAt(e)) || 0 }))
    .sort((a, b) => (a.at === b.at ? a.i - b.i : sign * (a.at - b.at)))
    .map((x) => x.e);
};

/** The order this browser chose; "newest" when none was chosen or the storage is not usable. */
export const readOrder = (storage: () => StorageLike | null = browserStorage): HistoryOrder => {
  try {
    return storage()?.getItem(ORDER_KEY) === "oldest" ? "oldest" : "newest";
  } catch {
    return "newest";
  }
};

/** Remember the order in this browser; without a usable storage it is not kept. */
export const storeOrder = (order: HistoryOrder, storage: () => StorageLike | null = browserStorage): void => {
  try {
    storage()?.setItem(ORDER_KEY, order);
  } catch {
    /* not kept */
  }
};

/** Date and time, also for today; the year (two digits) only when it is not the current one. */
export const dateTime = (value: string | null, lang: string, now: Date = new Date()): string => {
  if (!value) return "?";
  const d = new Date(value);
  return d.toLocaleString(lang, {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
    ...(d.getFullYear() !== now.getFullYear() ? { year: "2-digit" as const } : {}),
  });
};
