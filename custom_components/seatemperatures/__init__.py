from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SeaTemperatureAPI
from .const import CONF_PLACE, CONF_PLACE_ID, DOMAIN

# Patch cv for older HA versions (e.g. during testing)
if not hasattr(cv, "config_entry_only_config_schema"):
    import voluptuous as vol
    cv.config_entry_only_config_schema = lambda domain: vol.Schema({domain: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.SENSOR]
SCAN_INTERVAL = timedelta(hours=2)  # Sea temperatures don't change frequently
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Sea Temperatures component."""
    # Register static path for the card
    if hasattr(hass.http, "async_register_static_paths"):
        from homeassistant.components.http import StaticPathConfig
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                url_path="/seatemperatures_frontend/sea-temperatures-card.js",
                path=hass.config.path("custom_components/seatemperatures/sea-temperatures-card.js"),
                cache_headers=False,
            )
        ])
    else:
        hass.http.register_static_path(
            "/seatemperatures_frontend/sea-temperatures-card.js",
            hass.config.path("custom_components/seatemperatures/sea-temperatures-card.js"),
            cache_headers=False,
        )
    
    # Add extra JS url
    add_extra_js_url(hass, "/seatemperatures_frontend/sea-temperatures-card.js")
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sea Temperature from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    place_name = entry.data.get(CONF_PLACE, "Unknown")
    place_id = entry.data.get(CONF_PLACE_ID)

    api = SeaTemperatureAPI(hass)

    async def async_update_data():
        """Fetch data from API."""
        if not place_id:
            raise UpdateFailed("No place ID configured.")

        data = await api.get_temperatures(place_id)
        if not data:
            raise UpdateFailed(f"Failed to fetch data for place {place_name}")

        return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"seatemperatures_{place_id}",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
