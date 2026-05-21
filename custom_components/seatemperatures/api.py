from __future__ import annotations

import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    API_URL_MAP_LOCATIONS,
    API_URL_SEARCH,
    BASE_URL,
    DEFAULT_USER_AGENT,
    DOMAIN,
)
from .parser import parse_location_page, validate_location_path

_LOGGER = logging.getLogger(__name__)
_MAP_LOCATIONS_CACHE = "map_locations_cache"


def parse_search_results(data: Any) -> list[dict[str, str]]:
    """Parse search endpoint results into normalized location dictionaries."""
    if not isinstance(data, dict):
        return []

    results: list[dict[str, str]] = []
    for item in data.get("results", []):
        if not isinstance(item, dict):
            continue

        path = item.get("path")
        name = item.get("name")
        if not isinstance(path, str) or not isinstance(name, str):
            continue

        try:
            normalized_path = validate_location_path(path)
        except ValueError:
            _LOGGER.debug("Ignoring search result with invalid path: %s", path)
            continue

        results.append(
            {
                "name": name,
                "country": item.get("country", "")
                if isinstance(item.get("country"), str)
                else "",
                "region": item.get("region", "")
                if isinstance(item.get("region"), str)
                else "",
                "area": item.get("area", "")
                if isinstance(item.get("area"), str)
                else "",
                "path": normalized_path,
            }
        )

    return results


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

    async def search_locations(self, query: str) -> list[dict[str, str]] | None:
        """Search SeaTemperatures locations by query string."""
        if not query.strip():
            return []

        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                API_URL_SEARCH,
                params={"q": query.strip()},
                headers=self._headers,
            ) as response:
                response.raise_for_status()
                return parse_search_results(await response.json())
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("Error searching SeaTemperatures locations for %s: %s", query, err)
            return None

    async def get_location_by_place_id(self, place_id: str) -> dict[str, str] | None:
        """Resolve a legacy place ID to a current path-based location."""
        if not place_id:
            return None

        cache = await self._get_map_locations()
        if cache is None:
            return None

        return cache.get(place_id)

    async def get_temperatures(self, location_path: str) -> dict[str, Any] | None:
        """Fetch temperature data for a specific location path."""
        try:
            normalized_path = validate_location_path(location_path)
        except ValueError as err:
            _LOGGER.error("Invalid SeaTemperatures path %s: %s", location_path, err)
            return None

        url = f"{BASE_URL}{normalized_path}"
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(url, headers=self._headers) as response:
                response.raise_for_status()
                html = await response.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error(
                "Error fetching temperature data for path %s: %s",
                normalized_path,
                err,
            )
            return None

        return parse_location_page(html).as_legacy_payload()

    async def _get_map_locations(self) -> dict[str, dict[str, str]] | None:
        """Fetch and cache the map-locations payload for legacy migration."""
        domain_data = self.hass.data.setdefault(DOMAIN, {})
        if _MAP_LOCATIONS_CACHE in domain_data:
            return domain_data[_MAP_LOCATIONS_CACHE]

        session = async_get_clientsession(self.hass)
        try:
            async with session.get(API_URL_MAP_LOCATIONS, headers=self._headers) as response:
                response.raise_for_status()
                mapping = parse_map_locations(await response.json())
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("Error fetching SeaTemperatures map locations: %s", err)
            return None

        domain_data[_MAP_LOCATIONS_CACHE] = mapping
        return mapping
