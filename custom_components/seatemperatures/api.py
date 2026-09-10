from __future__ import annotations

import logging
import time
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    API_URL_MAP_LOCATIONS,
    BASE_URL,
    DEFAULT_USER_AGENT,
    DOMAIN,
)
from .parser import parse_location_page, validate_location_path

_LOGGER = logging.getLogger(__name__)
_MAP_LOCATIONS_CACHE = "map_locations_cache"

# A host that accepts the connection but never answers would otherwise hold a
# refresh for the aiohttp default (no total timeout at all), and the coordinator
# would sit on that one request instead of failing and retrying two hours later.
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)

# The map-locations payload is ~19k rows and was previously cached for the whole
# process lifetime, so a beach the site added only showed up after a restart.
MAP_LOCATIONS_TTL = 3600.0


class SeaTemperatureError(Exception):
    """Raised when a location could not be fetched.

    The message is meant to be handed to UpdateFailed: the coordinator already
    logs a failed refresh, so logging it here as well printed every outage
    twice.
    """


def parse_map_locations(data: Any) -> dict[str, dict[str, str]]:
    """Parse map-locations payload into a place_id -> location mapping."""
    if isinstance(data, dict):
        raw_locations = data.get("locations", [])
    else:
        raw_locations = data

    if not isinstance(raw_locations, list):
        return {}

    mapping: dict[str, dict[str, str]] = {}
    for item in raw_locations:
        if not isinstance(item, list) or len(item) < 5:
            continue

        place_id, name, country, area, path = item[:5]
        if not isinstance(place_id, str) or not isinstance(name, str):
            continue
        if not isinstance(path, str):
            continue

        try:
            normalized_path = validate_location_path(path)
        except ValueError:
            _LOGGER.debug("Ignoring map location with invalid path: %s", path)
            continue

        mapping[place_id] = {
            "name": name,
            "country": country if isinstance(country, str) else "",
            "area": area if isinstance(area, str) else "",
            "path": normalized_path,
        }

    return mapping


class SeaTemperatureAPI:
    """API to fetch sea temperature data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the API."""
        self.hass = hass
        self._headers = {"User-Agent": DEFAULT_USER_AGENT}

    async def get_location_by_place_id(self, place_id: str) -> dict[str, str] | None:
        """Resolve a legacy place ID to a current path-based location."""
        if not place_id:
            return None

        cache = await self.get_map_locations()
        if cache is None:
            return None

        location = cache.get(place_id)
        if location is None and not place_id.startswith("sea-"):
            location = cache.get(f"sea-{place_id}")
        return location

    async def get_temperatures(self, location_path: str) -> dict[str, Any]:
        """Fetch temperature data for a specific location path.

        Raises SeaTemperatureError so the coordinator owns the one log line.
        """
        try:
            normalized_path = validate_location_path(location_path)
        except ValueError as err:
            raise SeaTemperatureError(
                f"Invalid SeaTemperatures path {location_path}: {err}"
            ) from err

        url = f"{BASE_URL}{normalized_path}"
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                url, headers=self._headers, timeout=REQUEST_TIMEOUT
            ) as response:
                response.raise_for_status()
                html = await response.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SeaTemperatureError(
                f"Error fetching temperature data for path {normalized_path}: {err}"
            ) from err

        return parse_location_page(html).as_legacy_payload()

    async def get_map_locations(self) -> dict[str, dict[str, str]] | None:
        """Fetch the map-locations payload, cached for MAP_LOCATIONS_TTL seconds.

        The config flow and the legacy place_id migration both read this list,
        and both run several times in a row - but a cache that never expires
        means a newly published location stays invisible until Home Assistant
        restarts, so the entry carries a monotonic timestamp.
        """
        domain_data = self.hass.data.setdefault(DOMAIN, {})
        cached = domain_data.get(_MAP_LOCATIONS_CACHE)
        if cached is not None:
            cached_at, mapping = cached
            if time.monotonic() - cached_at < MAP_LOCATIONS_TTL:
                return mapping

        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                API_URL_MAP_LOCATIONS, headers=self._headers, timeout=REQUEST_TIMEOUT
            ) as response:
                response.raise_for_status()
                mapping = parse_map_locations(await response.json())
        except (aiohttp.ClientError, TimeoutError) as err:
            # Debug only: the config flow and the migration both report this.
            _LOGGER.debug("Error fetching SeaTemperatures map locations: %s", err)
            return None

        domain_data[_MAP_LOCATIONS_CACHE] = (time.monotonic(), mapping)
        return mapping
