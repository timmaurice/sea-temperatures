from __future__ import annotations

import logging
from dataclasses import dataclass

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

from .const import CONF_PLACE, CONF_PLACE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class SeaTemperatureSensorEntityDescription(SensorEntityDescription):
    """Class describing Sea Temperature sensor entities."""

    data_key: str | None = None


# Single sensor per place, representing "Today's Temperature"
SENSORS: tuple[SeaTemperatureSensorEntityDescription, ...] = (
    SeaTemperatureSensorEntityDescription(
        key="temperature",
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
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._place_name = entry.data.get(CONF_PLACE, "Unknown")
        self._place_id = entry.data[CONF_PLACE_ID]

        place_prefix = slugify(self._place_name)

        self._attr_unique_id = f"seatemperature_{self._place_id}_{description.key}"
        self.entity_id = f"sensor.seatemperature_{place_prefix}_{description.key}"

    @property
    def native_value(self) -> float | str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            _LOGGER.debug("No coordinator data available for %s", self.entity_id)
            return None

        _LOGGER.debug(
            "Coordinator data for %s: %s", self.entity_id, self.coordinator.data
        )

        # Try to get data from 'sst' nesting if it exists
        data = self.coordinator.data.get("sst", self.coordinator.data)

        if self.entity_description.data_key in data:
            val = data[self.entity_description.data_key]
            try:
                return float(val)
            except (ValueError, TypeError):
                return val

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
                    try:
                        val = float(sst_data["average"][avg_key])
                        attrs[f"average_{avg_key}"] = round(val, 2)
                    except (ValueError, TypeError):
                        attrs[f"average_{avg_key}"] = sst_data["average"][avg_key]

        return attrs if attrs else None

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._place_id)},
            "name": self._place_name,
            "manufacturer": "Sea Temperatures",
            "model": "Sea Temperature Monitor",
            "configuration_url": "https://seatemperatures.net",
        }
