"""Data update coordinator for the Sea Temperatures integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SeaTemperatureAPI, SeaTemperatureError
from .const import (
    CONF_PATH,
    CONF_PLACE,
    CONF_SCAN_INTERVAL_HOURS,
    DEFAULT_SCAN_INTERVAL_HOURS,
    MAX_SCAN_INTERVAL_HOURS,
    MIN_SCAN_INTERVAL_HOURS,
)

# The package logger, not this module's: the coordinator logged through it while
# it lived in __init__.py, and a logger filter a user set up for
# custom_components.seatemperatures would not apply to a child logger's records.
_LOGGER = logging.getLogger(__package__)

# The coordinator is the only per-entry state, so it lives on the entry itself.
# hass.data[DOMAIN] keeps what is shared across entries: the map-locations
# cache in api.py, which the config flow reads before any entry exists.
type SeaTemperatureConfigEntry = ConfigEntry[SeaTemperatureCoordinator]


def async_scan_interval(entry: ConfigEntry) -> timedelta:
    """Return the poll interval for an entry, honouring the options flow."""
    hours = entry.options.get(CONF_SCAN_INTERVAL_HOURS, DEFAULT_SCAN_INTERVAL_HOURS)
    try:
        hours = int(hours)
    except (TypeError, ValueError):
        hours = DEFAULT_SCAN_INTERVAL_HOURS
    if not MIN_SCAN_INTERVAL_HOURS <= hours <= MAX_SCAN_INTERVAL_HOURS:
        # The options flow bounds the form, but a hand-edited or older stored
        # value reaches this reader directly - clamp both ends, not just the
        # one that would hammer the site.
        hours = DEFAULT_SCAN_INTERVAL_HOURS
    return timedelta(hours=hours)


class SeaTemperatureCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch the readings of one location, once per poll interval."""

    config_entry: SeaTemperatureConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SeaTemperatureConfigEntry,
        location_key: str,
    ) -> None:
        """Set up the coordinator for one config entry.

        ``location_key`` is passed in rather than derived here because
        ``entry_location_key`` lives in ``__init__.py``, which imports this
        module.
        """
        self._place_name = entry.data.get(CONF_PLACE, "Unknown")
        self._location_path = entry.data.get(CONF_PATH)
        self._api = SeaTemperatureAPI(hass)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"seatemperatures_{location_key}",
            update_interval=async_scan_interval(entry),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch one refresh, turning an API failure into a single logged one.

        The coordinator logs an UpdateFailed once and stays quiet while the failure
        persists, so the API layer deliberately reports nothing of its own.
        """
        if not self._location_path:
            raise UpdateFailed(
                "No location path configured. Remove and re-add the integration."
            )

        try:
            data = await self._api.get_temperatures(self._location_path)
        except SeaTemperatureError as err:
            raise UpdateFailed(str(err)) from err

        if not data:
            raise UpdateFailed(f"Failed to fetch data for place {self._place_name}")

        return data
