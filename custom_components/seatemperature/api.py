from __future__ import annotations

import logging
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_URL_PLACES, API_URL_TEMPS

_LOGGER = logging.getLogger(__name__)


class SeaTemperatureAPI:
    """API to fetch sea temperature data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the API."""
        self.hass = hass

    async def get_places(self) -> dict[str, Any] | None:
        """Fetch the places hierarchy (continents -> countries -> places)."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(API_URL_PLACES, ssl=False) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as err:
            _LOGGER.error("Error fetching places data: %s", err)
            return None

    async def get_temperatures(self, place_id: str) -> dict[str, Any] | None:
        """Fetch temperature data for a specific place_id."""
        url = f"{API_URL_TEMPS}{place_id}"
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(url, ssl=False) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as err:
            _LOGGER.error(
                "Error fetching temperature data for place %s: %s", place_id, err
            )
            return None
