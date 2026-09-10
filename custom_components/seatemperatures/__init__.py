from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .api import SeaTemperatureAPI, SeaTemperatureError
from .const import (
    CONF_AREA,
    CONF_CONTINENT,
    CONF_COUNTRY,
    CONF_PATH,
    CONF_PLACE,
    CONF_PLACE_ID,
    CONF_SCAN_INTERVAL_HOURS,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
    MAX_SCAN_INTERVAL_HOURS,
    MIN_SCAN_INTERVAL_HOURS,
)

PLATFORMS = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)

CARD_FILENAME = "sea-temperatures-card.js"
CARD_URL_PREFIX = "/seatemperatures_frontend/"


async def _async_reconcile_card_resource(resources, new_url: str) -> None:
    """Leave exactly one Lovelace resource pointing at the bundled card.

    The resource store is loaded lazily: until something awaits it, async_items()
    returns an empty list. Registering off that empty list appended a second
    resource on every restart, and the browser then loaded the bundle twice.
    """
    # Default to False, not True: assuming a collection we cannot recognise is
    # already loaded would let us register against an empty item list and save
    # a store that has lost every other card's resource. Missing async_load
    # raises instead, and the caller skips registration.
    if not getattr(resources, "loaded", False):
        await resources.async_load()
        resources.loaded = True

    own = [
        item
        for item in resources.async_items()
        if item.get("url", "").startswith(CARD_URL_PREFIX)
    ]

    if not own:
        _LOGGER.info("Registering lovelace resource: %s", new_url)
        await resources.async_create_item({"res_type": "module", "url": new_url})
        return

    for duplicate in own[1:]:
        _LOGGER.info("Removing duplicate lovelace resource %s", duplicate.get("url"))
        await resources.async_delete_item(duplicate.get("id"))

    if own[0].get("url") != new_url:
        _LOGGER.debug("Updating lovelace resource URL to %s", new_url)
        await resources.async_update_item(own[0].get("id"), {"url": new_url})


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
                url_path=f"{CARD_URL_PREFIX}{CARD_FILENAME}",
                path=hass.config.path(f"custom_components/{DOMAIN}/{CARD_FILENAME}"),
                cache_headers=True,
            )
        ]
    )
    new_url = f"{CARD_URL_PREFIX}{CARD_FILENAME}?v={version}"

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

        try:
            await _async_reconcile_card_resource(resources, new_url)
        except Exception as e:  # noqa: BLE001 - resource registration must never break setup
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


def entry_location_key(entry: ConfigEntry) -> str:
    """Return the key an entry's entity unique_ids are built from.

    The migration and the sensor both call this, so the id they arrive at is
    the same one by construction rather than by two matching expressions.
    """
    return str(
        entry.data.get(CONF_PLACE_ID)
        or entry.data.get(CONF_PATH)
        or entry.data.get(CONF_PLACE)
        or entry.entry_id
    )


def slug_location_key(location_key: object) -> str:
    """Slugify a location key without folding "/" and "-" together.

    ``slugify`` maps both to "_", so ``/europe/greece/nea-plagia/`` and
    ``/europe/greece/nea/plagia/`` - two real, distinct locations - used to
    produce the very same id. Each path segment is therefore slugified with "-"
    as its separator and the segments are joined with "_": a "-" can then only
    come from inside a segment and a "_" only from a segment boundary, which
    makes the encoding injective instead of merely unlikely to clash. A legacy
    numeric place_id has no separators at all and slugifies to itself.
    """
    segments = [segment for segment in str(location_key).split("/") if segment]
    return "_".join(slugify(segment, separator="-") for segment in segments)


def build_unique_id(location_key: object, sensor_key: str) -> str:
    """Return the slugified unique_id used from entry version 4 on."""
    return f"{DOMAIN}_{slug_location_key(location_key)}_{sensor_key}"


async def _async_migrate_unique_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Bring the registry unique_ids of an entry's entities up to date.

    Path-based entries produced ids like
    ``seatemperatures_/europe/germany/island-of-sylt/_today``, and entry
    version 3 slugified those with "_" for every separator - which folded two
    distinct paths onto one id. The target id is derived from the *entry*, not
    parsed back out of the old one, so it is the same id the sensor will claim.
    Rewriting the registry entry rather than just the sensor keeps the
    entity_id - and therefore the recorded history - exactly where it was. A
    legacy numeric key slugifies to itself, so those entries are left
    untouched.
    """
    registry = er.async_get(hass)
    location_key = entry_location_key(entry)

    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        old_unique_id = registry_entry.unique_id
        if not old_unique_id.startswith(f"{DOMAIN}_"):
            continue

        middle, _, sensor_key = old_unique_id[len(DOMAIN) + 1 :].rpartition("_")
        if not middle or not sensor_key:
            continue

        new_unique_id = build_unique_id(location_key, sensor_key)
        if new_unique_id == old_unique_id:
            continue

        holder = registry.async_get_entity_id(
            registry_entry.domain, registry_entry.platform, new_unique_id
        )
        if holder is not None and holder != registry_entry.entity_id:
            # The sensor claims the new id unconditionally at setup, so leaving
            # the old id in place would cost the user this entity: the platform
            # would reject the duplicate and the stale row would be orphaned.
            # Ids are collision-free by construction now, so a holder here is a
            # leftover row - drop it and let the live entity keep its history.
            conflicting = registry.async_get(holder)
            owner = getattr(conflicting, "config_entry_id", None)
            if owner not in (None, entry.entry_id):
                _LOGGER.error(
                    "Cannot migrate unique_id %s to %s: %s of another config entry "
                    "holds it. Both entities keep the id they have.",
                    old_unique_id,
                    new_unique_id,
                    holder,
                )
                continue

            _LOGGER.warning(
                "Removing the stale registry entry %s so %s can take the id %s",
                holder,
                registry_entry.entity_id,
                new_unique_id,
            )
            registry.async_remove(holder)

        _LOGGER.debug("Migrating unique_id %s to %s", old_unique_id, new_unique_id)
        registry.async_update_entity(
            registry_entry.entity_id, new_unique_id=new_unique_id
        )


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate legacy config entries from place IDs to path-based locations."""
    if entry.version > 4:
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

    if entry.version < 4:
        # Version 3 slugified these ids already, but with a scheme that could
        # fold two paths onto one id; re-deriving them from the entry fixes a
        # v3 install as well as a v2 one.
        await _async_migrate_unique_ids(hass, entry)
        hass.config_entries.async_update_entry(entry, version=4)

    return True


async def _async_fetch(
    api: SeaTemperatureAPI, location_path: str | None, place_name: str
) -> dict:
    """Fetch one refresh, turning an API failure into a single logged one.

    The coordinator logs an UpdateFailed once and stays quiet while the failure
    persists, so the API layer deliberately reports nothing of its own.
    """
    if not location_path:
        raise UpdateFailed(
            "No location path configured. Remove and re-add the integration."
        )

    try:
        data = await api.get_temperatures(location_path)
    except SeaTemperatureError as err:
        raise UpdateFailed(str(err)) from err

    if not data:
        raise UpdateFailed(f"Failed to fetch data for place {place_name}")

    return data


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry after the options flow saved a new poll interval.

    The coordinator is built with ``update_interval`` once, at setup, so a saved
    interval is inert until the entry is set up again. Core offers
    ``OptionsFlowWithReload`` for this, but only from 2025.8 on; an explicit
    listener works on every version the integration supports and keeps the
    minimum where hacs.json puts it.
    """
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sea Temperature from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Registered before the first refresh so an options save during a slow or
    # failing setup is not silently dropped; async_on_unload drops the
    # subscription with the entry rather than stacking one per reload.
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    place_name = entry.data.get(CONF_PLACE, "Unknown")
    location_path = entry.data.get(CONF_PATH)
    location_key = entry.data.get(CONF_PLACE_ID) or location_path or entry.entry_id

    api = SeaTemperatureAPI(hass)

    async def async_update_data():
        """Fetch data from API."""
        return await _async_fetch(api, location_path, place_name)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"seatemperatures_{location_key}",
        update_method=async_update_data,
        update_interval=async_scan_interval(entry),
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
