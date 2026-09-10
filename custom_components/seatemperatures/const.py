"""Constants for the Sea Temperature integration."""

DOMAIN = "seatemperatures"

CONF_CONTINENT = "continent"
CONF_COUNTRY = "country"
CONF_AREA = "area"
CONF_PLACE = "place"
CONF_PLACE_ID = "place_id"
CONF_PATH = "path"

BASE_URL = "https://seatemperatures.net"
API_URL_MAP_LOCATIONS = f"{BASE_URL}/api/map-locations.json"
DEFAULT_USER_AGENT = "HomeAssistant seatemperatures integration"

