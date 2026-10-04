// Tests of the links a tapped push opens: "?message=<id>" shows the message,
// "?classify=<id>" opens the dialog for its entry of "New". Run with "npm test".
import { test } from "node:test";
import assert from "node:assert/strict";
import { readDeepLink, resolveDeepLink, rowKey, withoutDeepLink } from "../src/deep-link";
import type { MessageEntry, UnknownItem } from "../src/types";

const ID = "3c9f1e2d4b5a6978";
const OTHER = "0123456789abcdef";

const entry = (o: Partial<MessageEntry> = {}): MessageEntry => ({
  message_id: ID, origin: "automation.washing", origin_name: "Washing machine", kind: null, group: null, priority: 1,
  title: "Laundry done", message: "Please unload.", data: {}, labels: [], state: "delivered", count: 1,
  since: "2026-10-03T08:00:00+00:00", reason: "", until: null, next_try: null, failed_recipients: [], last_error: null,
  generation: 1, revision: 1, accepted_at: "2026-10-03T08:00:00+00:00", updated_at: "2026-10-03T08:00:00+00:00",
  delivered_at: "2026-10-03T08:00:00+00:00", ended_at: "2026-10-03T08:00:00+00:00", forwarded_at: null, expires_at: null,
  spacing: 0, no_hold: false, kind_id: null, group_id: null, recipients: {}, events: [], ...o,
});

const unknown = (o: Partial<UnknownItem> = {}): UnknownItem => ({
  origin: "automation.washing", origin_name: "Washing machine", labels: [], title: "Laundry done", count: 1,
  first_seen: "2026-10-03T08:00:00+00:00", last_seen: "2026-10-03T08:00:00+00:00", multiple: false, ...o,
});

test("the address names a message to show or to classify", () => {
  assert.deepEqual(readDeepLink(`?message=${ID}`), { mode: "message", id: ID });
  assert.deepEqual(readDeepLink(`?classify=${ID}`), { mode: "classify", id: ID });
  // other parameters stay out of it; classify wins when both are there
  assert.deepEqual(readDeepLink(`?lang=en&message=${ID}&theme=light`), { mode: "message", id: ID });
  assert.deepEqual(readDeepLink(`?message=${OTHER}&classify=${ID}`), { mode: "classify", id: ID });
  // an id is 16 hexadecimal characters; anything else is no link
  for (const search of ["", "?", "?message=", "?message=abc", `?message=${ID}x`, "?message=zzzzzzzzzzzzzzzz", `?msg=${ID}`]) {
    assert.equal(readDeepLink(search), null, search);
  }
  assert.deepEqual(readDeepLink(`?message=${ID.toUpperCase()}`), { mode: "message", id: ID });
});

test("the link leaves the address, other parameters stay", () => {
  assert.equal(withoutDeepLink(`?message=${ID}`), "");
  assert.equal(withoutDeepLink(`?classify=${ID}`), "");
  assert.equal(withoutDeepLink(`?lang=en&message=${ID}&theme=light`), "?lang=en&theme=light");
  assert.equal(withoutDeepLink("?lang=en"), "?lang=en");
  assert.equal(withoutDeepLink(""), "");
});

test("a row is one generation of a message", () => {
  assert.equal(rowKey(entry()), `${ID}:1`);
  assert.equal(rowKey(entry({ generation: 3 })), `${ID}:3`);
  assert.notEqual(rowKey(entry({ generation: 2 })), rowKey(entry({ generation: 1 })));
});

test("an open message is shown on the tab Open", () => {
  const open = [entry({ message_id: OTHER, title: "Other" }), entry({ state: "waiting", generation: 4 })];
  // its earlier generations in the history are not the target
  const ended = [entry({ generation: 3 }), entry({ generation: 2 })];
  assert.deepEqual(resolveDeepLink({ mode: "message", id: ID }, open, ended, []), { action: "show", tab: "open", key: `${ID}:4` });
});

test("an ended message is shown in the history", () => {
  assert.deepEqual(resolveDeepLink({ mode: "message", id: ID }, [], [entry()], [unknown()]), { action: "show", tab: "history", key: `${ID}:1` });
});

test("of a message that came back several times only the newest generation is the target", () => {
  // recent holds the newest, the history the earlier ones (a daily message, say)
  const ended = [entry({ message_id: OTHER, generation: 9 }), entry({ generation: 3 }), entry({ generation: 2 }), entry({ generation: 1 })];
  assert.deepEqual(resolveDeepLink({ mode: "message", id: ID }, [], ended, []), { action: "show", tab: "history", key: `${ID}:3` });
  // in whatever order the lists come
  const shuffled = [entry({ generation: 1 }), entry({ generation: 5 }), entry({ generation: 2 })];
  assert.deepEqual(resolveDeepLink({ mode: "message", id: ID }, [], shuffled, []), { action: "show", tab: "history", key: `${ID}:5` });
  // classify of a classified message shows the newest one too
  assert.deepEqual(resolveDeepLink({ mode: "classify", id: ID }, [], shuffled, []), { action: "show", tab: "history", key: `${ID}:5` });
});

test("a message that cannot be found is missing", () => {
  assert.deepEqual(resolveDeepLink({ mode: "message", id: ID }, [entry({ message_id: OTHER })], [], []), { action: "missing" });
  assert.deepEqual(resolveDeepLink({ mode: "classify", id: ID }, [], [], [unknown()]), { action: "missing" });
});

test("classify opens the dialog for the message's entry of New", () => {
  const item = unknown();
  const other = unknown({ title: "Dryer done" });
  assert.deepEqual(resolveDeepLink({ mode: "classify", id: ID }, [], [entry()], [other, item]), { action: "classify", item });
  // a held message too
  assert.deepEqual(resolveDeepLink({ mode: "classify", id: ID }, [entry({ state: "waiting" })], [], [item]), { action: "classify", item });
});

test("classify of a message classified meanwhile shows the message", () => {
  // its entry of New is gone (classified or dismissed): the message itself is shown
  assert.deepEqual(resolveDeepLink({ mode: "classify", id: ID }, [], [entry()], [unknown({ title: "Dryer done" })]),
    { action: "show", tab: "history", key: `${ID}:1` });
  assert.deepEqual(resolveDeepLink({ mode: "classify", id: ID }, [entry({ state: "waiting" })], [], []),
    { action: "show", tab: "open", key: `${ID}:1` });
  // same title from another origin is another entry
  assert.deepEqual(resolveDeepLink({ mode: "classify", id: ID }, [], [entry()], [unknown({ origin: "automation.dryer" })]),
    { action: "show", tab: "history", key: `${ID}:1` });
});
