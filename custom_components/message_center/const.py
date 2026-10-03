"""Constants for the Message Center integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "message_center"

# Contract limits
PRIORITY_MIN: Final = 1
PRIORITY_MAX: Final = 3
SENDER_MAX_LENGTH: Final = 40
TITLE_MAX_LENGTH: Final = 100
MESSAGE_MAX_LENGTH: Final = 2000
KEY_MAX_LENGTH: Final = 80
NOTE_MAX_LENGTH: Final = 500
MINUTES_MAX: Final = 10080
DEFAULT_CATEGORY: Final = "default"
# title of a message without one whose origin is not known; with a known
# origin the message is called after its automation or script
DEFAULT_TITLE: Final = "Mitteilung"
# stands for the computed parts of a title read from a configuration
PLACEHOLDER: Final = "…"

# Store limits and timing
MAX_OPEN_MESSAGES: Final = 200
END_STATE_RETENTION: Final = timedelta(hours=24)
SPACING_RETENTION: Final = timedelta(days=7)
MAX_WAIT: Final = timedelta(days=7)
RESTART_GAP: Final = timedelta(minutes=60)
RETRY_DELAYS: Final = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
)
RETRY_INTERVAL: Final = timedelta(hours=1)
RECIPIENT_GIVE_UP: Final = timedelta(hours=24)
# end states waiting for the history store, kept with the working store
MAX_PENDING_HISTORY: Final = 1000

# Config entry data and options
CONF_RECIPIENTS: Final = "recipients"
CONF_LIMITS: Final = "limits"
CONF_HISTORY_DAYS: Final = "history_days"
CONF_HIDE_TITLES: Final = "hide_titles"
DEFAULT_HISTORY_DAYS: Final = 30
DEFAULT_PRIORITY_CAP: Final = 2
SUBENTRY_RULE: Final = "rule"

# Recipient record keys
RECIPIENT_ACTION: Final = "action"
RECIPIENT_NAME: Final = "name"
RECIPIENT_PLATFORM: Final = "platform"
RECIPIENT_TYPE: Final = "type"
RECIPIENT_TYPE_MOBILE_APP: Final = "mobile_app"
PLATFORM_IOS: Final = "ios"
PLATFORM_ANDROID: Final = "android"

# Events
EVENT_DELIVERED: Final = f"{DOMAIN}_delivered"
EVENT_FORWARDED: Final = f"{DOMAIN}_forwarded"
# Interventions, for the logbook only (no text): message discarded / snoozed
EVENT_DISCARDED: Final = f"{DOMAIN}_discarded"
EVENT_SNOOZED: Final = f"{DOMAIN}_snoozed"

# Push
PUSH_CHANNEL: Final = "message_center"
# Android alarm channel, chosen in the settings (option alarm_channel):
#   alarm_stream      the app plays the device's default alarm tone on the alarm stream
#   alarm_stream_max  same at full volume
#   own               own channel "message_center_alarm"; sound and DND set in Android
ALARM_CHANNEL_STREAM: Final = "alarm_stream"
ALARM_CHANNEL_MAX: Final = "alarm_stream_max"
ALARM_CHANNEL_OWN: Final = "message_center_alarm"
ALARM_CHANNELS: Final = (ALARM_CHANNEL_STREAM, ALARM_CHANNEL_MAX, ALARM_CHANNEL_OWN)
CONF_ALARM_CHANNEL: Final = "alarm_channel"
DEFAULT_ALARM_CHANNEL: Final = ALARM_CHANNEL_STREAM
CONF_ALARM_TTS: Final = "alarm_tts"  # extra push that reads the title aloud (Android)
PUSH_TIMEOUT: Final = 15
HOUSEKEEPING_INTERVAL: Final = timedelta(hours=1)
STORE_RETRY_INTERVAL: Final = timedelta(seconds=60)  # while not writable
RECIPIENT_REPAIR_AFTER: Final = timedelta(minutes=15)
CONF_ALLOW_ALARM: Final = "allow_alarm"
SUBENTRY_KIND: Final = "kind"
SUBENTRY_GROUP: Final = "group"
MAX_UNKNOWN: Final = 200
# titles of one origin the page is shown when a kind is set up
MAX_SEEN_TITLES: Final = 10
# entries per list when the page asks what a condition matches
MAX_MATCHES_LISTED: Final = 20
# contexts of the center's own effects kept to recognise what they send back
MAX_EFFECT_CONTEXTS: Final = 1000
UNKNOWN_KIND_NAME: Final = "unknown"
CONF_SIDEBAR: Final = "sidebar"
CONF_GUIDE_DISMISSED: Final = "guide_dismissed"
CONF_SILENT_REPEAT: Final = "silent_repeat"  # repeats replace the push without sound
CONF_LIGHTS: Final = "lights"
HISTORY_DAYS_MAX: Final = 365
CONF_BUTTON_SNOOZE: Final = "button_snooze"
CONF_BUTTON_FORWARD: Final = "button_forward"
CONF_SNOOZE_MINUTES: Final = "snooze_minutes"
CONF_SNOOZE_MINUTES_2: Final = "snooze_minutes_2"
CONF_SNOOZE_INPUT: Final = "snooze_input"
DEFAULT_SNOOZE_MINUTES: Final = 30
SNOOZE_MINUTES_MAX: Final = 10080
CONF_LIGHT_SPACING: Final = "light_spacing"  # seconds between pulses, 0 = none
DEFAULT_LIGHT_SPACING: Final = 0
LIGHT_SPACING_MAX: Final = 600
TEST_ORIGIN: Final = "test"
LIGHT_TIMEOUT: Final = 10
CONF_PULSE_MS: Final = "pulse_ms"  # off time of the light pulse
DEFAULT_PULSE_MS: Final = 500
PULSE_MS_MIN: Final = 100
PULSE_MS_MAX: Final = 10000
LIGHT_DOMAINS: Final = ("light", "switch")
# Push button action ids: "<prefix>|<message id>"
ACTION_SNOOZE: Final = "message_center_snooze"
ACTION_FORWARD: Final = "message_center_forward"
ACTION_ALARM_OFF: Final = "message_center_alarm_off"
# Alarm light (priority 3): chosen lamps and switches toggle in step until ended
CONF_ALARM_LIGHTS: Final = "alarm_lights"
CONF_ALARM_INTERVAL_MS: Final = "alarm_interval_ms"
CONF_ALARM_MAX_SECONDS: Final = "alarm_max_seconds"
CONF_ALARM_TEST_SECONDS: Final = "alarm_test_seconds"
DEFAULT_ALARM_INTERVAL_MS: Final = 1000  # Zigbee lamps need about a second
ALARM_SETTLE_SECONDS: Final = 1.0  # let queued commands finish before restoring
DEFAULT_ALARM_MAX_SECONDS: Final = 300
DEFAULT_ALARM_TEST_SECONDS: Final = 5
ALARM_INTERVAL_MS_MIN: Final = 100
ALARM_INTERVAL_MS_MAX: Final = 5000
ALARM_MAX_SECONDS_MAX: Final = 3600
ALARM_TEST_SECONDS_MAX: Final = 60
EVENT_NOTIFICATION_ACTION: Final = "mobile_app_notification_action"
# Script that runs when a message is forwarded "to the assistant"
CONF_FORWARD_SCRIPT: Final = "forward_script"
# Script per priority that runs on the first delivery of a cycle
CONF_EFFECT_SCRIPTS: Final = ("effect_script_1", "effect_script_2", "effect_script_3")
SCRIPT_TIMEOUT: Final = 30
# Lamps and switches that pulse even when off (short on, then off again)
CONF_LIGHTS_ALWAYS: Final = "lights_always"
