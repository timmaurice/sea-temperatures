"""Constants for the Sea Temperature integration."""

DOMAIN = "seatemperatures"

CONF_CONTINENT = "continent"
CONF_COUNTRY = "country"
CONF_AREA = "area"
CONF_PLACE = "place"
CONF_PLACE_ID = "place_id"
CONF_PATH = "path"
CONF_SCAN_INTERVAL_HOURS = "scan_interval_hours"

# Sea temperatures move by tenths of a degree a day, so two hours is generous
# already. The bounds exist to keep an options-flow typo from either hammering
# the site or letting a sensor go stale for days.
DEFAULT_SCAN_INTERVAL_HOURS = 2
MIN_SCAN_INTERVAL_HOURS = 1
MAX_SCAN_INTERVAL_HOURS = 24

BASE_URL = "https://seatemperatures.net"
API_URL_MAP_LOCATIONS = f"{BASE_URL}/api/map-locations.json"
DEFAULT_USER_AGENT = "HomeAssistant seatemperatures integration"
