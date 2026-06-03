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
API_URL_SEARCH = f"{BASE_URL}/api/search/"
DEFAULT_USER_AGENT = "HomeAssistant seatemperatures integration"

# Sensors
SENSOR_TODAY = "today"
SENSOR_YESTERDAY = "yesterday"
SENSOR_LAST_YEAR = "last_year"
SENSOR_LAST_WEEK = "last_week"
SENSOR_AVERAGE_MIN = "average_min"
SENSOR_AVERAGE_MAX = "average_max"
SENSOR_AVERAGE_AVG = "average_avg"

SENSOR_TYPES = (
    SENSOR_TODAY,
    SENSOR_YESTERDAY,
    SENSOR_LAST_YEAR,
    SENSOR_LAST_WEEK,
    SENSOR_AVERAGE_MIN,
    SENSOR_AVERAGE_MAX,
    SENSOR_AVERAGE_AVG,
)
