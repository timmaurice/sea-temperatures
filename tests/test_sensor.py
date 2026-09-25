from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.seatemperatures import build_unique_id, entry_location_key
from custom_components.seatemperatures.const import (
    CONF_AREA,
    CONF_CONTINENT,
    CONF_COUNTRY,
    CONF_PATH,
    CONF_PLACE,
)
from custom_components.seatemperatures.sensor import (
    SENSORS,
    SeaTemperatureSensor,
    async_setup_entry,
)

pytestmark = pytest.mark.asyncio

SYLT_PATH = "/europe/germany/island-of-sylt/"


def _payload() -> dict:
    """A coordinator payload the size a real one has."""
    return {
        "date": "2026-05-21",
        "sst": {
            "today": 11.83,
            "yesterday": 11.7,
            "last_week": 10.31,
            "average": {"min": 10.5, "max": 13.2, "avg": 12.126},
        },
        "charts": {
            "last_thirty": {
                "labels": [f"2026-04-{day:02d}" for day in range(1, 31)],
                "series": [round(9.0 + index * 0.09, 2) for index in range(30)],
            }
        },
    }


def _entry(path: str = SYLT_PATH, place: str = "Island of Sylt") -> SimpleNamespace:
    return SimpleNamespace(
        data={
            CONF_PLACE: place,
            CONF_PATH: path,
            CONF_CONTINENT: "Europe",
            CONF_COUNTRY: "Germany",
            CONF_AREA: "Schleswig-Holstein",
        },
        options={},
        entry_id="entry-1",
    )


def _sensor(entry: SimpleNamespace, data: dict | None = None) -> SeaTemperatureSensor:
    coordinator = MagicMock()
    coordinator.data = data
    return SeaTemperatureSensor(coordinator, entry, SENSORS[0])


async def test_platform_setup_reads_the_coordinator_from_the_entry() -> None:
    """The coordinator is handed over on entry.runtime_data, not hass.data."""
    entry = _entry()
    entry.runtime_data = MagicMock()
    hass = MagicMock()
    hass.data = {}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, entry, async_add_entities)

    (sensors,) = async_add_entities.call_args.args
    assert len(sensors) == len(SENSORS)
    assert all(sensor.coordinator is entry.runtime_data for sensor in sensors)


async def test_unique_id_is_slugified() -> None:
    """A path-based key must not leak slashes into the registry id."""
    sensor = _sensor(_entry())

    assert sensor.unique_id == "seatemperatures_europe_germany_island-of-sylt_today"
    assert "/" not in sensor.unique_id


async def test_the_sensor_and_the_migration_agree_on_the_id() -> None:
    """The migration derives the target id from the entry; if the sensor built
    its own differently, setup would be rejected as a duplicate."""
    entry = _entry()
    sensor = _sensor(entry)

    assert sensor.unique_id == build_unique_id(entry_location_key(entry), "today")


async def test_two_paths_that_slugify_alike_get_different_sensors() -> None:
    """ "/" and "-" both slugify to "_", so these two real Greek beaches used to
    claim one id - and the second sensor was rejected at setup."""
    folded = _sensor(_entry(path="/europe/greece/nea-plagia/", place="Nea Plagia"))
    nested = _sensor(_entry(path="/europe/greece/nea/plagia/", place="Plagia"))

    assert folded.unique_id != nested.unique_id


async def test_a_legacy_numeric_key_slugifies_to_itself() -> None:
    """Older place_id entries must keep the id they already have."""
    assert build_unique_id("5484", "today") == "seatemperatures_5484_today"


async def test_a_non_string_location_key_degrades_instead_of_raising() -> None:
    """slugify() rejects an int, and a hand-edited entry storing place_id as a
    number must not take sensor setup down with a TypeError."""
    assert build_unique_id(5484, "today") == "seatemperatures_5484_today"


async def test_native_value_does_not_log_the_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """native_value runs on every state write - it must not print the chart."""
    sensor = _sensor(_entry(), _payload())

    with caplog.at_level(
        logging.DEBUG, logger="custom_components.seatemperatures.sensor"
    ):
        assert sensor.native_value == pytest.approx(11.83)
        assert sensor.native_value == pytest.approx(11.83)

    assert caplog.text == ""


async def test_native_value_is_none_without_data_and_stays_quiet(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A missing payload is the coordinator's business to report, not ours."""
    sensor = _sensor(_entry(), None)

    with caplog.at_level(
        logging.DEBUG, logger="custom_components.seatemperatures.sensor"
    ):
        assert sensor.native_value is None

    assert caplog.text == ""


async def test_extra_state_attributes_still_carry_the_chart() -> None:
    """Dropping the log line must not drop the card's data contract."""
    sensor = _sensor(_entry(), _payload())
    attrs = sensor.extra_state_attributes

    assert attrs["yesterday"] == pytest.approx(11.7)
    assert attrs["average_avg"] == pytest.approx(12.13)
    assert len(attrs["charts"]["last_thirty"]["series"]) == 30
    assert attrs["path"] == SYLT_PATH
