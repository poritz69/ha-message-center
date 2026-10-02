// Minimal view of the Home Assistant frontend objects the page uses.

export interface HassEntityState {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
}

export interface Connection {
  subscribeMessage<T>(
    callback: (message: T) => void,
    message: Record<string, unknown>
  ): Promise<() => Promise<void>>;
}

export interface HomeAssistant {
  language: string;
  states: Record<string, HassEntityState>;
  connection: Connection;
  callWS<T>(message: Record<string, unknown>): Promise<T>;
  callService(domain: string, service: string, data?: Record<string, unknown>): Promise<unknown>;
  user?: { is_admin: boolean; name: string };
}

export interface RecipientStatus {
  state: "pending" | "delivered" | "failed";
  last_error: string | null;
  attempts: number;
  next_try: string | null;
  delivered_at: string | null;
}

export interface MessageEntry {
  message_id: string;
  origin: string;
  origin_name: string | null;
  kind: string | null;
  group: string | null;
  priority: number;
  title: string;
  message: string;
  data: Record<string, unknown>;
  labels: string[];
  state: string;
  count: number;
  since: string;
  reason: string;
  until: string | null;
  next_try: string | null;
  failed_recipients: string[];
  last_error: Record<string, string> | null;
  generation: number;
  revision: number;
  accepted_at: string;
  updated_at: string;
  delivered_at: string | null;
  ended_at: string | null;
  forwarded_at: string | null;
  expires_at: string | null;
  spacing: number;
  no_hold: boolean;
  kind_id: string | null;
  group_id: string | null;
  recipients: Record<string, RecipientStatus>;
  /** Interventions and effects, oldest first: snoozed, forwarded, discarded, sent_now, light. */
  events: MessageEvent[];
}

export interface MessageEvent {
  at: string;
  kind: string;
  source: string;
  detail: string | null;
}

export interface UnknownItem {
  origin: string;
  origin_name: string | null;
  labels: string[];
  title: string;
  count: number;
  first_seen: string;
  last_seen: string;
}

export interface Overview {
  ready: boolean;
  ready_reason: string;
  open: number;
  waiting: number;
  disturbed: number;
  new: number;
  active_rules: number;
  delivered_today: number;
  last_delivery: { at: string; origin: string; title: string } | null;
  recipients: number;
  missing_recipients: string[];
  unknown: UnknownItem[];
  language: string;
  alarm_active: boolean;
  alarm_until: string | null;
}

export interface Messages {
  open: MessageEntry[];
  recent: MessageEntry[];
}

export interface Kind {
  id: string;
  name: string;
  origin: string | null;
  title_mode: "exact" | "prefix" | "contains";
  title_value: string;
  group_id: string | null;
  priority: number;
  no_hold: boolean;
  spacing: number;
  expires_after: number;
  light: boolean | null;
  active: boolean;
  /** Names of active kinds a title could match equally well: the older one wins. */
  ties: string[];
}

export interface Group {
  id: string;
  name: string;
  icon: string | null;
  priority: number;
  spacing: number;
  expires_after: number;
}

export interface Rule {
  id: string;
  name: string;
  entity_id: string;
  state: string;
  effect_1: string;
  effect_2: string;
  effect_3: string;
  max_hours: number;
  current_state: string | null;
  active: boolean;
  since: string | null;
  until: string | null;
  expired: boolean;
  unknown: boolean;
}

export interface Recipient {
  action: string;
  name: string;
  platform: string;
  type: string;
  configured: boolean;
  available: boolean;
  /** Latest failed push to this phone, from the stored messages; null when none. */
  last_error: { error: string; at: string; message_id: string } | null;
}

/** Options of the config entry, all optional (defaults apply when missing). */
export interface Options {
  history_days?: number;
  sidebar?: boolean;
  guide_dismissed?: boolean;
  silent_repeat?: boolean;
  hide_titles?: boolean;
  allow_alarm?: boolean;
  lights?: string[];
  pulse_ms?: number;
  light_spacing?: number;
  alarm_lights?: string[];
  alarm_interval_ms?: number;
  alarm_max_seconds?: number;
  alarm_test_seconds?: number;
  alarm_channel?: string;
  alarm_tts?: boolean;
  button_snooze?: boolean;
  button_forward?: boolean;
  snooze_minutes?: number;
  snooze_minutes_2?: number;
  snooze_input?: boolean;
  /** Targets from `lights` that pulse even when off (on, then off again). */
  lights_always?: string[];
  /** Script that runs on "to assistant" with the message as variables. */
  forward_script?: string | null;
  /** Script per priority that runs on the first delivery of a cycle. */
  effect_script_1?: string | null;
  effect_script_2?: string | null;
  effect_script_3?: string | null;
}

export interface Config {
  kinds: Kind[];
  groups: Group[];
  rules: Rule[];
  recipients: Recipient[];
  origins: { entity_id: string; name: string | null }[];
  options: Options;
}

export type Tab = "overview" | "open" | "history" | "kinds" | "rules" | "recipients" | "settings";

/** One notifying step found in an automation or script (the search over the house). */
export interface ScanItem {
  source: "automation" | "script";
  entity_id: string;
  name: string;
  /** Origin the center will see: the automation; null for scripts (depends on who starts them). */
  origin: string | null;
  blueprint: string | null;
  edit_url: string | null;
  service: string;
  target: string;
  status: "direct" | "center" | "persistent";
  title: string | null;
  title_template: boolean;
  first_line: string | null;
  suggestion: { mode: "exact" | "prefix"; value: string } | null;
  file: string | null;
  line: number | null;
  kind: string | null;
}

/** A line in a file of the configuration directory that mentions a notify action. */
export interface ScanFile {
  file: string;
  line: number;
  text: string;
  status: "direct" | "center" | "persistent";
}

export interface ScanResult {
  found: ScanItem[];
  files: ScanFile[];
  counts: { automations: number; scripts: number; files: number; direct: number };
}
