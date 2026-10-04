// The logic of the delivery rule dialog's help on modes, free of the page's
// elements: a toggle (input_boolean) created there is chosen for the rule at
// once. Message Center only creates it; it never switches it and creates no
// automation. Tested by test/rule-logic.test.ts.
import type { FormData } from "./editor";

/** What Home Assistant answers to input_boolean/create: the stored item. */
export interface CreatedSwitch {
  id: string;
  name: string;
}

/** The entity of a toggle created in the UI: Home Assistant names it after the item's id. */
export const switchEntityId = (item: CreatedSwitch): string => `input_boolean.${item.id}`;

/** The rule with the created toggle, the state "on", and the toggle's name when the rule has none yet. */
export const ruleWithSwitch = (data: FormData, entityId: string, name: string): FormData => ({
  ...data,
  name: String(data.name ?? "").trim() ? data.name : name,
  entity_id: entityId,
  state: "on",
});
