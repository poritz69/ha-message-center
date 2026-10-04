// Tests of the history's table: the column "Time" is when a message ended,
// always with date and time, and the order (newest or oldest first) is
// remembered in the browser. Run with "npm test".
import { test } from "node:test";
import assert from "node:assert/strict";
import { ORDER_KEY, dateTime, endedAt, readOrder, sortByEnd, storeOrder } from "../src/history";
import { tables } from "../src/i18n";
import type { MessageEntry } from "../src/types";

const at = (day: number, hour: number, minute = 0) => new Date(2026, 9, day, hour, minute).toISOString();

const entry = (o: Partial<MessageEntry> = {}): MessageEntry => ({
  message_id: "3c9f1e2d4b5a6978", origin: "automation.washing", origin_name: "Washing machine", kind: null, group: null, priority: 1,
  title: "Laundry done", message: "Please unload.", data: {}, labels: [], state: "delivered", count: 1,
  since: at(1, 8), reason: "", until: null, next_try: null, failed_recipients: [], last_error: null,
  generation: 1, revision: 1, accepted_at: at(1, 8), updated_at: at(1, 8), delivered_at: at(1, 8), ended_at: at(1, 8),
  forwarded_at: null, expires_at: null, spacing: 0, no_hold: false, kind_id: null, group_id: null, recipients: {}, events: [], ...o,
});

/** A storage like the browser's, in memory. */
const memory = () => {
  const items = new Map<string, string>();
  return { getItem: (k: string) => items.get(k) ?? null, setItem: (k: string, v: string) => { items.set(k, v); } };
};

test("the time of an ended message is its end, else its last change", () => {
  assert.equal(endedAt(entry({ ended_at: at(3, 9), updated_at: at(3, 10) })), at(3, 9));
  assert.equal(endedAt(entry({ ended_at: null, updated_at: at(3, 10) })), at(3, 10));
});

test("newest first or oldest first, by the end of each message", () => {
  const a = entry({ title: "a", since: at(1, 6), ended_at: at(2, 8) });
  // began first, ended last
  const b = entry({ title: "b", since: at(1, 5), ended_at: at(3, 8) });
  const c = entry({ title: "c", since: at(1, 7), ended_at: null, updated_at: at(1, 9) });
  const given = [a, b, c];
  assert.deepEqual(sortByEnd(given, "newest").map((e) => e.title), ["b", "a", "c"]);
  assert.deepEqual(sortByEnd(given, "oldest").map((e) => e.title), ["c", "a", "b"]);
  // the list given is not changed; the same end keeps the given order
  assert.deepEqual(given.map((e) => e.title), ["a", "b", "c"]);
  const d = entry({ title: "d", ended_at: at(2, 8) });
  assert.deepEqual(sortByEnd([a, d], "newest").map((e) => e.title), ["a", "d"]);
  assert.deepEqual(sortByEnd([a, d], "oldest").map((e) => e.title), ["a", "d"]);
});

test("the order is remembered in the browser", () => {
  const store = memory();
  assert.equal(readOrder(() => store), "newest");
  storeOrder("oldest", () => store);
  assert.equal(readOrder(() => store), "oldest");
  storeOrder("newest", () => store);
  assert.equal(readOrder(() => store), "newest");
  // anything else stored under the key is the default
  store.setItem(ORDER_KEY, "sideways");
  assert.equal(readOrder(() => store), "newest");
});

test("without a usable storage the page keeps the default and does not fail", () => {
  const blocked = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } };
  assert.equal(readOrder(() => blocked), "newest");
  assert.doesNotThrow(() => storeOrder("oldest", () => blocked));
  // the browser may refuse the storage itself
  const refused = () => { throw new Error("SecurityError"); };
  assert.equal(readOrder(refused), "newest");
  assert.doesNotThrow(() => storeOrder("oldest", refused));
  assert.equal(readOrder(() => null), "newest");
});

test("the column always shows date and time, the year only when it is another", () => {
  const now = new Date(2026, 9, 4, 12, 0);
  // today too, unlike "since" on the tab Open
  assert.match(dateTime(at(4, 7, 5), "de", now), /^04\.10\.,? 07:05$/);
  assert.match(dateTime(at(3, 23, 59), "de", now), /^03\.10\.,? 23:59$/);
  assert.match(dateTime(new Date(2025, 11, 30, 8, 0).toISOString(), "de", now), /^30\.12\.25,? 08:00$/);
  assert.match(dateTime(at(4, 19, 5), "en", now), /^10\/04,? 07:05\sPM$/);
  assert.equal(dateTime(null, "de", now), "?");
});

test("the history's texts", () => {
  assert.equal(tables.de.time_col, "Zeit");
  assert.equal(tables.en.time_col, "Time");
  assert.equal(tables.de.order_newest, "Neueste zuerst");
  assert.equal(tables.de.order_oldest, "Älteste zuerst");
  assert.equal(tables.en.order_newest, "Newest first");
  assert.equal(tables.en.order_oldest, "Oldest first");
  // the tab Open keeps "since"
  assert.equal(tables.de.since_col, "Seit");
});
