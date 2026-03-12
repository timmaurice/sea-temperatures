"""Constants for the Sea Temperature integration."""

DOMAIN = "seatemperatures"

CONF_CONTINENT = "continent"
CONF_COUNTRY = "country"
CONF_PLACE = "place"
CONF_PLACE_ID = "place_id"

BASE_URL = "https://seatemperatures.net"
API_URL_PLACES = f"{BASE_URL}/_data/places.json"
API_URL_TEMPS = f"{BASE_URL}/api/temps?placeId="

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
