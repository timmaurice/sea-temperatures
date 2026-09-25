from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import slugify

from . import build_unique_id, entry_location_key
from .const import BASE_URL, CONF_AREA, CONF_PATH, CONF_PLACE, DOMAIN
from .parser import validate_location_path

_LOGGER = logging.getLogger(__name__)

# The coordinator does the one fetch per location; the sensor only reads its
# data and has no update method or action of its own, so nothing to serialise.
PARALLEL_UPDATES = 0


def _to_float(val: Any, round_to: int | None = None) -> float | str:
    """Safely convert a value to float if possible."""
    try:
        f_val = float(val)
        return round(f_val, round_to) if round_to is not None else f_val
    except (ValueError, TypeError):
        return val


@dataclass(frozen=True, kw_only=True)
class SeaTemperatureSensorEntityDescription(SensorEntityDescription):
    """Class describing Sea Temperature sensor entities."""

    data_key: str | None = None


# Single sensor per place, representing "Today's Temperature"
SENSORS: tuple[SeaTemperatureSensorEntityDescription, ...] = (
    SeaTemperatureSensorEntityDescription(
        key="today",
        name="Temperature",
        data_key="today",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sea Temperature sensor entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        SeaTemperatureSensor(coordinator, entry, description) for description in SENSORS
    ]

    async_add_entities(sensors)


class SeaTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sea Temperature Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        description: SeaTemperatureSensorEntityDescription,
    ):
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._place_name = entry.data.get(CONF_PLACE, "Unknown")
        # Shared with the unique_id migration, so both sides agree on the id.
        self._location_key = entry_location_key(entry)

        # Set friendly name
        self._attr_name = "Temperature"

        place_prefix = slugify(self._place_name)

        # Slugified: the raw location path produced ids like
        # "seatemperatures_/europe/germany/island-of-sylt/_today". Entry
        # version 4 rewrites the registry, so existing entities keep their
        # entity_id and their history.
        self._attr_unique_id = build_unique_id(self._location_key, description.key)
        self.entity_id = f"sensor.{DOMAIN}_{place_prefix}_{description.key}"

    @property
    def native_value(self) -> float | str | None:
        """Return the state of the sensor."""
        # native_value is read on every state write, so nothing here logs the
        # payload: it carries the 30-point chart series, and one place turned
        # debug logging for this integration into an unreadable wall of numbers.
        if not self.coordinator.data:
            return None

        # Try to get data from 'sst' nesting if it exists
        data = self.coordinator.data.get("sst", self.coordinator.data)

        if self.entity_description.data_key in data:
            return _to_float(data[self.entity_description.data_key])

        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if not self.coordinator.data:
            return None

        data = self.coordinator.data
        sst_data = data.get("sst", {})

        attrs = {}
        for attr_key in ["yesterday", "last_week", "last_year"]:
            if attr_key in sst_data:
                attrs[attr_key] = sst_data[attr_key]

        if "date" in data:
            attrs["date"] = data["date"]

        if "average" in sst_data:
            for avg_key in ["min", "max", "avg"]:
                if avg_key in sst_data["average"]:
                    attrs[f"average_{avg_key}"] = _to_float(
                        sst_data["average"][avg_key], round_to=2
                    )

        if "charts" in data:
            attrs["charts"] = data["charts"]

        attrs["continent"] = self._entry.data.get("continent", "")
        attrs["country"] = self._entry.data.get("country", "")
        attrs["area"] = self._entry.data.get(CONF_AREA, "")
        attrs["place"] = self._place_name
        attrs["path"] = self._entry.data.get(CONF_PATH, "")

        return attrs if attrs else None

    @property
    def device_info(self):
        """Return device information."""
        url = BASE_URL
        location_path = self._entry.data.get(CONF_PATH)
        if location_path:
            try:
                url = f"{BASE_URL}{validate_location_path(location_path)}"
            except ValueError:
                _LOGGER.debug("Invalid configuration URL path for %s", self._place_name)

        return {
            "identifiers": {(DOMAIN, self._location_key)},
            "name": self._place_name,
            "manufacturer": "Sea Temperatures",
            "model": "Sea Temperature Monitor",
            "configuration_url": url,
        }
