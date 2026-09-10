from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from custom_components.seatemperatures import (
    _async_migrate_unique_ids,
    async_migrate_entry,
    async_scan_interval,
    build_unique_id,
)
from custom_components.seatemperatures.config_flow import (
    SeaTemperatureConfigFlow,
    SeaTemperatureOptionsFlow,
)
from custom_components.seatemperatures.const import (
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
from custom_components.seatemperatures.diagnostics import (
    async_get_config_entry_diagnostics,
)

pytestmark = pytest.mark.asyncio

SYLT_PATH = "/europe/germany/island-of-sylt/"
LEGACY_UNIQUE_ID = f"{DOMAIN}_{SYLT_PATH}_today"
# Version 3's scheme, which folded "/" and "-" onto the same separator.
V3_UNIQUE_ID = f"{DOMAIN}_europe_germany_island_of_sylt_today"
SLUGIFIED_UNIQUE_ID = f"{DOMAIN}_europe_germany_island-of-sylt_today"


def _entry(**kwargs) -> SimpleNamespace:
    """A config entry stand-in with the fields the module under test reads."""
    defaults = {
        "entry_id": "entry-1",
        "version": 4,
        "minor_version": 1,
        "unique_id": SYLT_PATH,
        "title": "Island of Sylt Sea Temperature",
        "data": {
            CONF_PLACE: "Island of Sylt",
            CONF_PATH: SYLT_PATH,
            CONF_CONTINENT: "Europe",
            CONF_COUNTRY: "Germany",
            CONF_AREA: "Schleswig-Holstein",
        },
        "options": {},
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# --- options flow / poll interval ---------------------------------------


async def test_scan_interval_defaults_to_two_hours() -> None:
    """An entry that never saw the options flow keeps the shipped interval."""
    assert async_scan_interval(_entry()) == timedelta(
        hours=DEFAULT_SCAN_INTERVAL_HOURS
    )


async def test_scan_interval_follows_the_saved_option() -> None:
    """The whole point of the options flow: no delete-and-re-add to repoll."""
    entry = _entry(options={CONF_SCAN_INTERVAL_HOURS: 6})

    assert async_scan_interval(entry) == timedelta(hours=6)


@pytest.mark.parametrize("stored", ["nonsense", None, 0, -3])
async def test_scan_interval_falls_back_on_a_bad_option(stored) -> None:
    """A corrupted option must not produce a zero or negative interval."""
    entry = _entry(options={CONF_SCAN_INTERVAL_HOURS: stored})

    assert async_scan_interval(entry) == timedelta(
        hours=DEFAULT_SCAN_INTERVAL_HOURS
    )


async def test_the_config_flow_exposes_an_options_flow() -> None:
    """Home Assistant only shows the Configure button when this exists."""
    handler = SeaTemperatureConfigFlow.async_get_options_flow(_entry())

    assert isinstance(handler, SeaTemperatureOptionsFlow)


async def test_options_flow_form_is_prefilled_and_bounded() -> None:
    """The form has to open on the current value, inside sane bounds."""
    flow = SeaTemperatureOptionsFlow()
    flow.hass = MagicMock()
    flow.handler = "entry-1"
    flow.hass.config_entries.async_get_known_entry.return_value = _entry(
        options={CONF_SCAN_INTERVAL_HOURS: 6}
    )

    result = await flow.async_step_init()

    schema = result["data_schema"].schema
    key = next(k for k in schema if str(k) == CONF_SCAN_INTERVAL_HOURS)
    assert key.default() == 6

    config = schema[key].config
    assert config["min"] == MIN_SCAN_INTERVAL_HOURS
    assert config["max"] == MAX_SCAN_INTERVAL_HOURS


async def test_options_flow_stores_the_interval_as_an_int() -> None:
    """A NumberSelector hands back a float; timedelta(hours=8.0) is fine but
    the stored option should still read as hours, not as 8.0."""
    flow = SeaTemperatureOptionsFlow()
    flow.hass = MagicMock()
    flow.handler = "entry-1"
    flow.hass.config_entries.async_get_known_entry.return_value = _entry()

    result = await flow.async_step_init({CONF_SCAN_INTERVAL_HOURS: 8.0})

    assert result["data"] == {CONF_SCAN_INTERVAL_HOURS: 8}
    assert async_scan_interval(
        _entry(options=result["data"])
    ) == timedelta(hours=8)


# --- unique_id migration -------------------------------------------------


def _registry_entry(
    unique_id: str,
    entity_id: str = "sensor.seatemperatures_island_of_sylt_today",
) -> SimpleNamespace:
    return SimpleNamespace(
        entity_id=entity_id,
        unique_id=unique_id,
        domain="sensor",
        platform=DOMAIN,
        config_entry_id="entry-1",
    )


def _patched_registry(
    entries: list[SimpleNamespace],
    taken: str | None = None,
    taken_by: SimpleNamespace | None = None,
):
    """A registry stand-in.

    ``taken`` is a unique_id some other registry row already holds; ``taken_by``
    is that row, defaulting to a stale one belonging to the same config entry.
    """
    holder = taken_by or _registry_entry(taken or "", entity_id="sensor.stale")
    registry = MagicMock()
    registry.async_get_entity_id.side_effect = (
        lambda domain, platform, unique_id: holder.entity_id
        if taken is not None and unique_id == taken
        else None
    )
    registry.async_get.side_effect = (
        lambda entity_id: holder if entity_id == holder.entity_id else None
    )
    return registry, patch.multiple(
        "custom_components.seatemperatures.er",
        async_get=MagicMock(return_value=registry),
        async_entries_for_config_entry=MagicMock(return_value=entries),
    )


async def test_migration_slugifies_a_path_based_unique_id() -> None:
    """The registry entry is rewritten, so the entity_id - and the recorded
    history hanging off it - is untouched."""
    hass = MagicMock()
    registry, patched = _patched_registry([_registry_entry(LEGACY_UNIQUE_ID)])

    with patched:
        await _async_migrate_unique_ids(hass, _entry())

    registry.async_update_entity.assert_called_once_with(
        "sensor.seatemperatures_island_of_sylt_today",
        new_unique_id=SLUGIFIED_UNIQUE_ID,
    )


async def test_migration_reslugifies_a_version_3_unique_id() -> None:
    """An install that already ran version 3 carries the ambiguous id and has
    to be moved onto the collision-free one."""
    hass = MagicMock()
    registry, patched = _patched_registry([_registry_entry(V3_UNIQUE_ID)])

    with patched:
        await _async_migrate_unique_ids(hass, _entry())

    registry.async_update_entity.assert_called_once_with(
        "sensor.seatemperatures_island_of_sylt_today",
        new_unique_id=SLUGIFIED_UNIQUE_ID,
    )


async def test_migration_leaves_a_legacy_numeric_unique_id_alone() -> None:
    """seatemperatures_5484_today already slugifies to itself."""
    hass = MagicMock()
    entry = _entry(
        data={CONF_PLACE: "Island of Sylt", CONF_PLACE_ID: "5484", CONF_PATH: SYLT_PATH}
    )
    registry, patched = _patched_registry([_registry_entry(f"{DOMAIN}_5484_today")])

    with patched:
        await _async_migrate_unique_ids(hass, entry)

    registry.async_update_entity.assert_not_called()


async def test_two_paths_that_slugify_alike_keep_distinct_unique_ids() -> None:
    """The collision this scheme exists to prevent, pinned to the real pair of
    paths that produced it: "/" and "-" both slugify to "_"."""
    folded = build_unique_id("/europe/greece/nea-plagia/", "today")
    nested = build_unique_id("/europe/greece/nea/plagia/", "today")

    assert folded == f"{DOMAIN}_europe_greece_nea-plagia_today"
    assert nested == f"{DOMAIN}_europe_greece_nea_plagia_today"
    assert folded != nested
    assert "/" not in folded and "/" not in nested


async def test_a_collision_never_costs_the_user_the_entity() -> None:
    """The sensor claims the built id unconditionally at setup, so a migration
    that gave up here would orphan the row and delete the user's sensor."""
    hass = MagicMock()
    registry, patched = _patched_registry(
        [_registry_entry(LEGACY_UNIQUE_ID)], taken=SLUGIFIED_UNIQUE_ID
    )

    with patched:
        await _async_migrate_unique_ids(hass, _entry())

    # The stale row holding the id goes; the live entity keeps its entity_id,
    # its history, and the id the sensor is about to ask for.
    registry.async_remove.assert_called_once_with("sensor.stale")
    registry.async_update_entity.assert_called_once_with(
        "sensor.seatemperatures_island_of_sylt_today",
        new_unique_id=SLUGIFIED_UNIQUE_ID,
    )


async def test_a_collision_with_another_live_entry_touches_neither() -> None:
    """Ids are collision-free by construction now, so this cannot happen from
    two paths - and if it somehow does, no live entity gets removed."""
    hass = MagicMock()
    other = _registry_entry(SLUGIFIED_UNIQUE_ID, entity_id="sensor.other_entry")
    other.config_entry_id = "entry-2"
    registry, patched = _patched_registry(
        [_registry_entry(LEGACY_UNIQUE_ID)],
        taken=SLUGIFIED_UNIQUE_ID,
        taken_by=other,
    )

    with patched:
        await _async_migrate_unique_ids(hass, _entry())

    registry.async_remove.assert_not_called()
    registry.async_update_entity.assert_not_called()


async def test_migration_finishes_a_partially_migrated_entry() -> None:
    """A run interrupted halfway leaves both schemes side by side; the second
    pass must move the stragglers and leave the finished ones alone."""
    hass = MagicMock()
    done = _registry_entry(SLUGIFIED_UNIQUE_ID, entity_id="sensor.sylt_today")
    todo = _registry_entry(
        f"{DOMAIN}_{SYLT_PATH}_average", entity_id="sensor.sylt_average"
    )
    registry, patched = _patched_registry([done, todo])

    with patched:
        await _async_migrate_unique_ids(hass, _entry())

    registry.async_update_entity.assert_called_once_with(
        "sensor.sylt_average",
        new_unique_id=f"{DOMAIN}_europe_germany_island-of-sylt_average",
    )


async def test_async_migrate_entry_runs_the_unique_id_migration() -> None:
    """A version 2 entry has to reach version 4 without user action."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()
    entry = _entry(version=2)
    registry, patched = _patched_registry([_registry_entry(LEGACY_UNIQUE_ID)])

    with patched:
        assert await async_migrate_entry(hass, entry) is True

    registry.async_update_entity.assert_called_once()
    hass.config_entries.async_update_entry.assert_called_once_with(entry, version=4)


async def test_async_migrate_entry_reslugifies_a_version_3_entry() -> None:
    """The scheme changed after version 3 shipped, so a v3 install migrates."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()
    entry = _entry(version=3)
    registry, patched = _patched_registry([_registry_entry(V3_UNIQUE_ID)])

    with patched:
        assert await async_migrate_entry(hass, entry) is True

    registry.async_update_entity.assert_called_once_with(
        "sensor.seatemperatures_island_of_sylt_today",
        new_unique_id=SLUGIFIED_UNIQUE_ID,
    )
    hass.config_entries.async_update_entry.assert_called_once_with(entry, version=4)


async def test_async_migrate_entry_rejects_a_future_version() -> None:
    """Downgrading Home Assistant must fail loudly, not silently."""
    hass = MagicMock()

    assert await async_migrate_entry(hass, _entry(version=5)) is False


# --- diagnostics ---------------------------------------------------------


async def test_diagnostics_report_the_entry_and_summarise_the_chart() -> None:
    """A diagnostics download must be readable, not 30 numbers per place."""
    entry = _entry(options={CONF_SCAN_INTERVAL_HOURS: 6})
    coordinator = SimpleNamespace(
        last_update_success=True,
        update_interval=timedelta(hours=6),
        data={
            "date": "2026-05-21",
            "sst": {"today": 11.83, "yesterday": 11.7},
            "charts": {
                "last_thirty": {
                    "labels": [f"2026-04-{day:02d}" for day in range(1, 31)],
                    "series": list(range(30)),
                }
            },
        },
    )
    hass = MagicMock()
    hass.data = {DOMAIN: {entry.entry_id: coordinator}}

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["version"] == 4
    assert result["entry"]["data"][CONF_PATH] == SYLT_PATH
    assert result["entry"]["options"] == {CONF_SCAN_INTERVAL_HOURS: 6}
    assert result["coordinator"]["last_update_success"] is True
    assert result["coordinator"]["update_interval"] == "6:00:00"
    assert result["coordinator"]["data"]["sst"]["today"] == pytest.approx(11.83)

    series = result["coordinator"]["data"]["charts"]["last_thirty"]
    assert series == {
        "points": 30,
        "first_label": "2026-04-01",
        "last_label": "2026-04-30",
        "first_value": 0,
        "last_value": 29,
    }


async def test_diagnostics_survive_a_never_refreshed_entry() -> None:
    """Diagnostics are the tool you reach for when setup failed."""
    entry = _entry()
    hass = MagicMock()
    hass.data = {}

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["coordinator"]["data"] is None
    assert result["coordinator"]["last_update_success"] is None
    assert result["entry"]["unique_id"] == SYLT_PATH
