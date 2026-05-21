from __future__ import annotations

import logging
from datetime import timedelta


from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SeaTemperatureAPI
from .const import (
    CONF_AREA,
    CONF_CONTINENT,
    CONF_COUNTRY,
    CONF_PATH,
    CONF_PLACE,
    CONF_PLACE_ID,
    DOMAIN,
)

PLATFORMS = [Platform.SENSOR]
SCAN_INTERVAL = timedelta(hours=2)  # Sea temperatures don't change frequently
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Sea Temperatures component."""
    from homeassistant.loader import async_get_integration

    integration = await async_get_integration(hass, DOMAIN)
    version = integration.version or "1.0.0"

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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate legacy config entries from place IDs to path-based locations."""
    if entry.version > 2:
        _LOGGER.error("Unsupported SeaTemperatures config entry version: %s", entry.version)
        return False

    if entry.version < 2:
        _LOGGER.debug("Migrating SeaTemperatures entry %s from version %s", entry.entry_id, entry.version)

        data = dict(entry.data)
        location_path = data.get(CONF_PATH)
        if not location_path:
            place_id = data.get(CONF_PLACE_ID)
            if not place_id:
                _LOGGER.error(
                    "SeaTemperatures entry %s has no place_id to migrate. Remove and re-add the integration.",
                    entry.entry_id,
                )
                return False

            location = await SeaTemperatureAPI(hass).get_location_by_place_id(place_id)
            if location is None:
                _LOGGER.error(
                    "SeaTemperatures place_id %s could not be mapped to a current location path. Remove and re-add the integration.",
                    place_id,
                )
                return False

            data[CONF_PATH] = location[CONF_PATH]
            data[CONF_PLACE] = location.get("name", data.get(CONF_PLACE, "Unknown"))
            data[CONF_COUNTRY] = location.get(CONF_COUNTRY, data.get(CONF_COUNTRY, ""))
            data[CONF_AREA] = location.get(CONF_AREA, data.get(CONF_AREA, ""))
            data.setdefault(CONF_CONTINENT, data.get(CONF_CONTINENT, ""))

        hass.config_entries.async_update_entry(
            entry,
            data=data,
            unique_id=data[CONF_PATH],
            version=2,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sea Temperature from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    place_name = entry.data.get(CONF_PLACE, "Unknown")
    location_path = entry.data.get(CONF_PATH)
    location_key = entry.data.get(CONF_PLACE_ID) or location_path or entry.entry_id

    api = SeaTemperatureAPI(hass)

    async def async_update_data():
        """Fetch data from API."""
        if not location_path:
            raise UpdateFailed(
                "No location path configured. Remove and re-add the integration."
            )

        data = await api.get_temperatures(location_path)
        if not data:
            raise UpdateFailed(f"Failed to fetch data for place {place_name}")

        return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"seatemperatures_{location_key}",
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
