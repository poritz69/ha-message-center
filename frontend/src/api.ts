import type {
  Config, HomeAssistant, KindMatches, MessageEntry, Messages, OriginMessages, Options, Overview, ScanResult, TitleMode,
} from "./types";

const D = "message_center";

export const fetchOverview = (hass: HomeAssistant) =>
  hass.callWS<Overview>({ type: `${D}/overview` });

export const fetchMessages = (hass: HomeAssistant) =>
  hass.callWS<Messages>({ type: `${D}/messages` });

export const fetchHistory = (hass: HomeAssistant) =>
  hass.callWS<{ history: MessageEntry[] }>({ type: `${D}/history` });

export const fetchConfig = (hass: HomeAssistant) =>
  hass.callWS<Config>({ type: `${D}/config` });

export const saveEntry = (
  hass: HomeAssistant,
  kind: "kind" | "group" | "rule",
  data: Record<string, unknown>,
  subentryId?: string
) => hass.callWS<{ subentry_id: string }>({
  type: `${D}/save`, kind, data, ...(subentryId ? { subentry_id: subentryId } : {}),
});

export const deleteEntry = (hass: HomeAssistant, subentryId: string) =>
  hass.callWS<Record<string, never>>({ type: `${D}/delete`, subentry_id: subentryId });

export const messageAction = (
  hass: HomeAssistant,
  action: "discard" | "snooze" | "send_now" | "forward",
  message_id: string,
  extra: Record<string, unknown> = {}
) => hass.callWS<Record<string, never>>({ type: `${D}/action`, action, message_id, ...extra });

export const dismissUnknown = (hass: HomeAssistant, origin: string, title: string) =>
  hass.callWS<Record<string, never>>({ type: `${D}/dismiss_unknown`, origin, title });

export const saveOptions = (hass: HomeAssistant, options: Options) =>
  hass.callWS<{ options: Options }>({ type: `${D}/options`, options });

export const setRecipients = (hass: HomeAssistant, actions: string[]) =>
  hass.callWS<{ recipients: unknown[] }>({ type: `${D}/recipients`, actions });

export const sendTest = (hass: HomeAssistant, priority: number) =>
  hass.callWS<{ sent: string[]; failed: string[]; lights: string[]; script: string | null; script_error: string | null }>({ type: `${D}/test`, priority });

export const alarmOff = (hass: HomeAssistant) =>
  hass.callWS<{ ended: boolean }>({ type: `${D}/alarm_off` });

export const scanHouse = (hass: HomeAssistant) =>
  hass.callWS<ScanResult>({ type: `${D}/scan` });

/** Which messages an automation or script sends: one, or several to tell apart. */
export const fetchOriginMessages = (hass: HomeAssistant, origin: string) =>
  hass.callWS<OriginMessages>({ type: `${D}/origin_messages`, origin });

/** What a condition matches; `kind_id` leaves the kind being edited out, `probe` asks about one pair. */
export const fetchKindMatches = (
  hass: HomeAssistant,
  condition: { origin: string | null; title_mode: TitleMode; title_value: string },
  kindId?: string,
  probe?: { origin: string; title: string } | null
) => hass.callWS<KindMatches>({
  type: `${D}/kind_matches`, ...condition, ...(kindId ? { kind_id: kindId } : {}), ...(probe ? { probe } : {}),
});

export const subscribe = (hass: HomeAssistant, callback: () => void) =>
  hass.connection.subscribeMessage(() => callback(), { type: `${D}/subscribe` });

// ha-form, ha-dialog and friends are loaded lazily by the frontend. Loading a
// card editor pulls them in (the same trick HACS uses).
export async function ensureHaElements(): Promise<void> {
  if (customElements.get("ha-form") && customElements.get("ha-dialog")) return;
  const loader = (window as unknown as { loadCardHelpers?: () => Promise<{
    createCardElement: (config: Record<string, unknown>) => Promise<{ constructor: { getConfigElement?: () => Promise<unknown> } }>;
  }> }).loadCardHelpers;
  if (!loader) return;
  try {
    const helpers = await loader();
    const card = await helpers.createCardElement({ type: "entities", entities: [] });
    await card.constructor.getConfigElement?.();
  } catch {
    // the page still works without the dialogs; forms fall back to plain inputs
  }
}
