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
  /** The automation sends several different messages (its configuration, else the titles that arrived). */
  multiple?: boolean;
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

/** How the title condition of a kind compares; "any" takes every title of its origin. */
export type TitleMode = "exact" | "prefix" | "contains" | "any";

export interface Kind {
  id: string;
  name: string;
  origin: string | null;
  title_mode: TitleMode;
  /** Empty for "any". */
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
  /** Its automation or script exists no more: it affects nothing and can be deleted. */
  orphan?: boolean;
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
  /** Condition for a kind: "any" for an automation that sends one message, else the title. */
  suggestion: Suggestion | null;
  /** The automation or script sends several different messages. */
  multiple?: boolean;
  file: string | null;
  line: number | null;
  kind: string | null;
}

export type Suggestion = { mode: "exact" | "prefix" | "contains"; value: string } | { mode: "any"; value?: undefined };

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

/** One message an automation or script sends, read from its configuration. */
export interface OriginMessage {
  /** The title as written; null for a call without one (it is called after the automation). */
  title: string | null;
  template: boolean;
  /** The title as shown: computed parts as "…", the automation's name for a call without a title. */
  display: string;
}

/** Which messages one origin sends (message_center/origin_messages). */
export interface OriginMessages {
  /** config: its calls to the center; seen: titles that arrived; direct: its calls past the center; none. */
  source: "config" | "seen" | "direct" | "none";
  messages: OriginMessage[];
  /** Different titles that arrived from it, newest first. */
  seen_titles: string[];
  multiple: boolean;
  /** False for an origin that is no automation or script: no "all messages of" for it. */
  any_allowed: boolean;
}

/** A pair of origin and title a condition matches, with the other kind that would take it. */
export interface MatchedPair {
  origin: string;
  origin_name: string | null;
  title: string;
  count?: number;
  last_seen: string;
  taken_by: { kind_id: string; name: string } | null;
}

/** What a condition matches in "new" and among the stored messages (message_center/kind_matches). */
export interface KindMatches {
  /** False while the condition is incomplete: it matches nothing. */
  valid: boolean;
  new: MatchedPair[];
  new_count: number;
  seen: MatchedPair[];
  seen_count: number;
  taken_count: number;
  overlaps: { kind_id: string; name: string; winner: "this" | "other"; shared: number }[];
  overlap_count: number;
  probe: { matches: boolean; taken_by: { kind_id: string; name: string } | null } | null;
}
