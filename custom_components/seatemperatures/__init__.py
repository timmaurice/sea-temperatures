from __future__ import annotations

import logging
from datetime import timedelta


from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SeaTemperatureAPI
from .const import CONF_PLACE, CONF_PLACE_ID, DOMAIN

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.SENSOR]
SCAN_INTERVAL = timedelta(hours=2)  # Sea temperatures don't change frequently
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Sea Temperatures component."""
    import json

    # Read version from manifest for cache busting
    version = "1.0.0"
    try:
        manifest_path = hass.config.path(
            "custom_components/seatemperatures/manifest.json"
        )
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            version = manifest.get("version", version)
    except Exception:
        pass

    # Register static path for the card
    from homeassistant.components.http import StaticPathConfig

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                url_path="/seatemperatures_frontend/sea-temperatures-card.js",
                path=hass.config.path(
                    "custom_components/seatemperatures/sea-temperatures-card.js"
                ),
                cache_headers=True,
            )
        ]
    )
    new_url = f"/seatemperatures_frontend/sea-temperatures-card.js?v={version}"

    async def _async_register_lovelace_resource(event=None):
        _LOGGER.debug("Attempting to register lovelace resource")
        if "lovelace" not in hass.data:
            _LOGGER.warning("Lovelace not found in hass.data")
            return

        lovelace_data = hass.data["lovelace"]
        mode = getattr(lovelace_data, "resource_mode", "storage")
        resources = getattr(lovelace_data, "resources", None)

        if not resources:
            _LOGGER.warning("Lovelace data does not have resources")
            return

        if mode != "storage":
            _LOGGER.warning(
                "Lovelace is not in storage mode (mode is '%s'), cannot auto-register",
                mode,
            )
            return

        # Check if resource is already registered
        for item in resources.async_items():
            if item.get("url", "").startswith("/seatemperatures_frontend/"):
                if item.get("url") != new_url:
                    _LOGGER.debug("Updating lovelace resource URL to %s", new_url)
                    await resources.async_update_item(item.get("id"), {"url": new_url})
                return

        # Not registered, add it
        try:
            _LOGGER.info("Registering lovelace resource: %s", new_url)
            await resources.async_create_item({"res_type": "module", "url": new_url})
        except Exception as e:
            _LOGGER.warning("Failed to register lovelace resource: %s", e)

    from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
    from homeassistant.core import CoreState

    if hass.state == CoreState.running:
        hass.async_create_task(_async_register_lovelace_resource())
    else:
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, _async_register_lovelace_resource
        )

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
