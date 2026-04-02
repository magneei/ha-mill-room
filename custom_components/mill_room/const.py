"""Constants for the Mill Room integration."""

DOMAIN = "mill_room"
PLATFORMS = ["climate", "sensor"]

CONF_USERNAME = "username"
CONF_PASSWORD = "password"

DEFAULT_SCAN_INTERVAL = 120  # seconds
MAX_BACKOFF_INTERVAL = 1800  # 30 minutes

PRESET_COMFORT = "Comfort"
PRESET_SLEEP = "Sleep"
PRESET_AWAY = "Away"
PRESET_PROGRAM = "Program"
PRESET_OFF = "Off"
