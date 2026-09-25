"""The sensor's name and icon come from its device class, not from us.

These run against a real Home Assistant instance: the name is resolved from
the sensor component's translations in the configured language and the
registry row is rewritten at setup, and neither happens on a MagicMock.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.seatemperatures import build_unique_id
from custom_components.seatemperatures.const import (
    CONF_AREA,
    CONF_CONTINENT,
    CONF_COUNTRY,
    CONF_PATH,
    CONF_PLACE,
    DOMAIN,
)

SYLT_PATH = "/europe/germany/island-of-sylt/"
ENTITY_ID = "sensor.seatemperatures_island_of_sylt_today"
PAYLOAD = {
    "date": "2026-05-21",
    "sst": {
        "today": 11.83,
        "yesterday": 11.7,
        "average": {"min": 10.5, "max": 13.2, "avg": 12.126},
    },
}


@pytest.fixture(autouse=True)
def _custom_integrations(enable_custom_integrations: None) -> None:
    """Let the test instance load custom_components/seatemperatures."""


async def _setup_over_an_old_registry_entry(
    hass: HomeAssistant, language: str
) -> er.RegistryEntry:
    """Set the entry up on top of the registry row an older release left.

    Up to now the sensor was named "Temperature" in code and carried a fixed
    mdi:thermometer icon, and that is what the registry recorded for it.
    """
    hass.config.language = language
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=4,
        unique_id=SYLT_PATH,
        title="Island of Sylt",
        data={
            CONF_PLACE: "Island of Sylt",
            CONF_PATH: SYLT_PATH,
            CONF_CONTINENT: "Europe",
            CONF_COUNTRY: "Germany",
            CONF_AREA: "Schleswig-Holstein",
        },
    )
    entry.add_to_hass(hass)

    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        build_unique_id(SYLT_PATH, "today"),
        suggested_object_id="seatemperatures_island_of_sylt_today",
        config_entry=entry,
        has_entity_name=True,
        original_name="Temperature",
        original_icon="mdi:thermometer",
    )
    assert old.entity_id == ENTITY_ID

    with (
        # The card registration in async_setup is not what is under test.
        patch("custom_components.seatemperatures.async_setup", return_value=True),
        patch("custom_components.seatemperatures.coordinator.SeaTemperatureAPI") as api,
    ):
        api.return_value.get_temperatures = AsyncMock(return_value=PAYLOAD)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert [e.entity_id for e in entities] == [ENTITY_ID]
    return entities[0]


@pytest.mark.parametrize(
    ("language", "friendly_name"),
    [
        # English users see exactly the name they had before.
        ("en", "Island of Sylt Temperature"),
        # Everyone else now gets the device-class name in their language.
        ("de", "Island of Sylt Temperatur"),
    ],
)
async def test_an_existing_sensor_keeps_its_entity_id_and_gets_a_translated_name(
    hass: HomeAssistant, language: str, friendly_name: str
) -> None:
    """The unique_id is unchanged, so the registry hands back the old entity_id
    - and with it the recorded history - while the name follows the language."""
    registry_entry = await _setup_over_an_old_registry_entry(hass, language)

    assert registry_entry.entity_id == ENTITY_ID
    # The code no longer supplies a name or an icon of its own.
    assert registry_entry.name is None
    assert registry_entry.original_icon is None

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "11.83"
    assert state.attributes[ATTR_FRIENDLY_NAME] == friendly_name
    # The icon is left to the frontend's device-class default (mdi:thermometer
    # in the sensor component's icons.json), so no icon attribute is written.
    assert ATTR_ICON not in state.attributes
