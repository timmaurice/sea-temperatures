from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from homeassistant.helpers.selector import SelectSelector
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.seatemperatures import async_migrate_entry
from custom_components.seatemperatures.api import (
    MAP_LOCATIONS_TTL,
    REQUEST_TIMEOUT,
    SeaTemperatureAPI,
    SeaTemperatureError,
    parse_map_locations,
)
from custom_components.seatemperatures.config_flow import (
    CONTINENT_NAMES,
    SeaTemperatureConfigFlow,
)
from custom_components.seatemperatures.const import (
    CONF_AREA,
    CONF_CONTINENT,
    CONF_COUNTRY,
    CONF_PATH,
    CONF_PLACE,
    CONF_PLACE_ID,
)
from custom_components.seatemperatures.coordinator import SeaTemperatureCoordinator
from custom_components.seatemperatures.parser import (
    parse_location_page,
    validate_location_path,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_hass():
    """Mock Home Assistant object."""
    hass = AsyncMock()
    hass.data = {}
    hass.config_entries = SimpleNamespace(async_update_entry=MagicMock())
    return hass


def load_fixture(name: str) -> str:
    """Load an HTML fixture by name."""
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


async def test_parse_location_page_from_copenhagen_fixture() -> None:
    """Parse a standard location page fixture."""
    data = parse_location_page(load_fixture("copenhagen.html"))

    assert data.date == "2026-05-21"
    assert data.today == pytest.approx(11.83)
    assert data.yesterday == pytest.approx(11.7)
    assert data.average_avg == pytest.approx(12.126000000000001)
    assert data.average_min == pytest.approx(10.85)
    assert data.average_max == pytest.approx(13.67)
    assert data.last_week == pytest.approx(10.31)
    assert data.trend_labels is not None
    assert data.trend_labels[0] == "2026-04-22"
    assert data.trend_labels[-1] == "2026-05-21"
    assert data.trend_temps_c is not None
    assert data.trend_temps_c[-1] == pytest.approx(11.83)


async def test_parse_location_page_is_not_location_specific() -> None:
    """Parse a second fixture to prove the parser is generic."""
    data = parse_location_page(load_fixture("miami_beach.html"))

    assert data.today == pytest.approx(27.97)
    assert data.yesterday == pytest.approx(27.95)
    assert data.average_avg == pytest.approx(27.784999999999997)
    assert data.average_min == pytest.approx(26.47)
    assert data.average_max == pytest.approx(28.71)
    assert data.last_week == pytest.approx(28.5)


async def test_parse_location_page_tolerates_missing_values() -> None:
    """Missing values should produce None instead of crashing."""
    data = parse_location_page("<html><body><h1>No chart</h1></body></html>")

    assert data.today is None
    assert data.yesterday is None
    assert data.average_avg is None
    assert data.average_min is None
    assert data.average_max is None
    assert data.last_week is None
    assert data.trend_labels is None
    assert data.trend_temps_c is None


async def test_parse_location_page_tolerates_malformed_chart_json(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Malformed chart JSON should be ignored with a warning."""
    html = """
    <html><body>
      <p>Today</p><p><span data-c="15.5">15.5</span></p>
      <script type="application/json" data-sea-curve-payload>{broken json</script>
    </body></html>
    """

    data = parse_location_page(html)

    assert data.today == pytest.approx(15.5)
    assert data.trend_labels is None
    assert "Failed to parse SeaTemperatures chart payload" in caplog.text


async def test_validate_location_path() -> None:
    """Location paths should be normalized and validated."""
    assert (
        validate_location_path("/north-america/united-states/miami-beach")
        == "/north-america/united-states/miami-beach/"
    )

    with pytest.raises(ValueError):
        validate_location_path("https://seatemperatures.net/europe/denmark/copenhagen/")

    with pytest.raises(ValueError):
        validate_location_path("/../../etc/passwd")


async def test_parse_map_locations() -> None:
    """Legacy map-locations payload should support place_id migration."""
    data = {
        "locations": [
            [
                "sea-1",
                "Ain El Turk",
                "Algeria",
                "",
                "/africa/algeria/ain-el-turk/",
                35.7438,
                -0.7693,
                19.1,
            ],
            ["broken"],
        ]
    }

    results = parse_map_locations(data)

    assert results == {
        "sea-1": {
            "name": "Ain El Turk",
            "country": "Algeria",
            "area": "",
            "path": "/africa/algeria/ain-el-turk/",
        }
    }


async def test_get_temperatures_from_location_page(mock_hass) -> None:
    """The API should fetch HTML and return the legacy payload shape."""
    api = SeaTemperatureAPI(mock_hass)
    html = load_fixture("copenhagen.html")

    with patch(
        "custom_components.seatemperatures.api.async_get_clientsession"
    ) as mock_session:
        mock_response = AsyncMock()
        mock_response.text.return_value = html
        mock_response.raise_for_status = MagicMock()
        mock_session.return_value.get.return_value.__aenter__.return_value = (
            mock_response
        )

        result = await api.get_temperatures("/europe/denmark/copenhagen/")

    assert result is not None
    assert result["date"] == "2026-05-21"
    assert result["sst"]["today"] == pytest.approx(11.83)
    assert result["sst"]["yesterday"] == pytest.approx(11.7)
    assert result["sst"]["last_week"] == pytest.approx(10.31)
    assert result["sst"]["average"]["avg"] == pytest.approx(12.126000000000001)
    assert result["charts"]["last_thirty"]["labels"][-1] == "2026-05-21"


async def test_get_location_by_place_id_uses_map_locations(mock_hass) -> None:
    """Legacy IDs should resolve through map-locations data."""
    api = SeaTemperatureAPI(mock_hass)
    payload = {
        "locations": [
            [
                "canonical-36",
                "Boumerdas",
                "Algeria",
                "Boumerdes",
                "/africa/algeria/boumerdas/",
            ]
        ]
    }

    with patch(
        "custom_components.seatemperatures.api.async_get_clientsession"
    ) as mock_session:
        mock_response = AsyncMock()
        mock_response.json.return_value = payload
        mock_response.raise_for_status = MagicMock()
        mock_session.return_value.get.return_value.__aenter__.return_value = (
            mock_response
        )

        result = await api.get_location_by_place_id("canonical-36")

    assert result == {
        "name": "Boumerdas",
        "country": "Algeria",
        "area": "Boumerdes",
        "path": "/africa/algeria/boumerdas/",
    }


async def test_get_location_by_place_id_falls_back_to_sea_prefix(mock_hass) -> None:
    """Numeric legacy IDs should resolve by prefixing sea-."""
    api = SeaTemperatureAPI(mock_hass)
    payload = {
        "locations": [
            ["sea-5484", "Acharavi", "Greece", "Corfu", "/europe/greece/acharavi/"]
        ]
    }

    with patch(
        "custom_components.seatemperatures.api.async_get_clientsession"
    ) as mock_session:
        mock_response = AsyncMock()
        mock_response.json.return_value = payload
        mock_response.raise_for_status = MagicMock()
        mock_session.return_value.get.return_value.__aenter__.return_value = (
            mock_response
        )

        result = await api.get_location_by_place_id("5484")

    assert result == {
        "name": "Acharavi",
        "country": "Greece",
        "area": "Corfu",
        "path": "/europe/greece/acharavi/",
    }


async def test_config_flow_stores_path_based_location(mock_hass) -> None:
    """Config flow should store location metadata including the path."""
    flow = SeaTemperatureConfigFlow()
    flow.hass = mock_hass

    locations_cache = {
        "sea-1": {
            "name": "Miami Beach",
            "country": "United States",
            "area": "Florida, United States",
            "path": "/north-america/united-states/miami-beach/",
        }
    }

    with patch.object(
        SeaTemperatureAPI, "get_map_locations", AsyncMock(return_value=locations_cache)
    ):
        user_result = await flow.async_step_user(None)
        assert user_result["type"] == "form"
        assert user_result["step_id"] == "user"

        user_result = await flow.async_step_user({CONF_CONTINENT: "North America"})
        assert user_result["type"] == "form"
        assert user_result["step_id"] == "country"

        country_result = await flow.async_step_country({CONF_COUNTRY: "United States"})
        assert country_result["type"] == "form"
        assert country_result["step_id"] == "place"

        with patch.object(flow, "async_set_unique_id", AsyncMock()), patch.object(
            flow, "_abort_if_unique_id_configured", MagicMock()
        ):
            place_result = await flow.async_step_place(
                {CONF_PLACE: "Miami Beach (Florida, United States)"}
            )

    assert place_result["type"] == "create_entry"
    assert place_result["data"] == {
        CONF_CONTINENT: "North America",
        CONF_COUNTRY: "United States",
        CONF_AREA: "Florida, United States",
        CONF_PLACE: "Miami Beach",
        CONF_PATH: "/north-america/united-states/miami-beach/",
    }


async def test_async_migrate_entry_from_place_id(mock_hass) -> None:
    """Legacy config entries should migrate from place_id to path."""
    entry = SimpleNamespace(
        version=1,
        entry_id="entry-1",
        data={CONF_PLACE_ID: "sea-1", CONF_PLACE: "Legacy Name"},
    )

    with patch.object(
        SeaTemperatureAPI,
        "get_location_by_place_id",
        AsyncMock(
            return_value={
                "name": "Ain El Turk",
                "country": "Algeria",
                "area": "",
                "path": "/africa/algeria/ain-el-turk/",
            }
        ),
    ), patch(
        # The unique_id migration is exercised in test_entry.py; here it would
        # only drag a real entity registry into a mocked hass.
        "custom_components.seatemperatures._async_migrate_unique_ids",
        AsyncMock(),
    ) as migrate_unique_ids:
        migrated = await async_migrate_entry(mock_hass, entry)

    assert migrated is True
    migrate_unique_ids.assert_awaited_once()
    assert mock_hass.config_entries.async_update_entry.call_count == 2
    _, kwargs = mock_hass.config_entries.async_update_entry.call_args_list[0]
    assert kwargs["data"][CONF_PLACE] == "Ain El Turk"
    assert kwargs["data"][CONF_COUNTRY] == "Algeria"
    assert kwargs["data"][CONF_PATH] == "/africa/algeria/ain-el-turk/"
    assert kwargs["unique_id"] == "/africa/algeria/ain-el-turk/"
    assert kwargs["version"] == 2
    assert mock_hass.config_entries.async_update_entry.call_args_list[1].kwargs == {
        "version": 4
    }


async def test_async_migrate_entry_fails_when_place_id_cannot_be_mapped(
    mock_hass,
) -> None:
    """Migration should fail cleanly if a legacy ID no longer resolves."""
    entry = SimpleNamespace(
        version=1, entry_id="entry-2", data={CONF_PLACE_ID: "missing"}
    )

    with patch.object(
        SeaTemperatureAPI, "get_location_by_place_id", AsyncMock(return_value=None)
    ):
        migrated = await async_migrate_entry(mock_hass, entry)

    assert migrated is False
    mock_hass.config_entries.async_update_entry.assert_not_called()


async def test_config_flow_reshows_the_form_when_the_site_is_unreachable(
    mock_hass,
) -> None:
    """An unreachable site must show a translated error, not an abort."""
    flow = SeaTemperatureConfigFlow()
    flow.hass = mock_hass

    with patch.object(
        SeaTemperatureAPI, "get_map_locations", AsyncMock(return_value=None)
    ):
        result = await flow.async_step_user(None)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_retries_after_a_failed_fetch(mock_hass) -> None:
    """Submitting the error form should fetch again instead of raising."""
    flow = SeaTemperatureConfigFlow()
    flow.hass = mock_hass

    locations_cache = {
        "sea-1": {
            "name": "Copenhagen",
            "country": "Denmark",
            "area": "",
            "path": "/europe/denmark/copenhagen/",
        }
    }

    with patch.object(
        SeaTemperatureAPI,
        "get_map_locations",
        AsyncMock(side_effect=[None, locations_cache]),
    ):
        await flow.async_step_user(None)
        # The retry form has no continent field, so it submits an empty mapping.
        result = await flow.async_step_user({})

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result.get("errors")
    assert flow._continents == ["Europe"]


# The nine first path segments /api/map-locations.json actually publishes.
PUBLISHED_CONTINENT_SLUGS = {
    "africa",
    "antarctica",
    "asia",
    "australia-and-oceania",
    "central-america-and-the-caribbean",
    "europe",
    "middle-east",
    "north-america",
    "south-america",
}


async def test_continent_map_matches_the_published_slugs() -> None:
    """A stale slug adds a continent no location ever resolves to."""
    assert set(CONTINENT_NAMES) == PUBLISHED_CONTINENT_SLUGS


async def test_continent_names_read_as_names() -> None:
    """Every published slug should map to one readable spelling."""
    flow = SeaTemperatureConfigFlow()

    names = {flow._get_continent_name(slug) for slug in PUBLISHED_CONTINENT_SLUGS}

    assert names == {
        "Africa",
        "Antarctica",
        "Asia",
        "Australia and Oceania",
        "Central America and the Caribbean",
        "Europe",
        "Middle East",
        "North America",
        "South America",
    }


async def test_unknown_continent_slug_keeps_joining_words_small() -> None:
    """A slug the site adds later still has to read as a name."""
    flow = SeaTemperatureConfigFlow()

    assert (
        flow._get_continent_name("islands-of-the-atlantic") == "Islands of the Atlantic"
    )


def _selector_for(schema, key: str) -> SelectSelector:
    """Pull the selector a schema uses for one key."""
    for marker, validator in schema.schema.items():
        if str(marker) == key:
            return validator
    raise AssertionError(f"{key} is not in the schema")


async def test_every_step_offers_a_searchable_dropdown(mock_hass) -> None:
    """4,477 places in a plain list cannot be picked from without a search."""
    flow = SeaTemperatureConfigFlow()
    flow.hass = mock_hass

    locations_cache = {
        f"sea-{index}": {
            "name": f"Place {index}",
            "country": "United States",
            "area": "",
            "path": f"/north-america/united-states/place-{index}/",
        }
        for index in range(3)
    }

    with patch.object(
        SeaTemperatureAPI, "get_map_locations", AsyncMock(return_value=locations_cache)
    ):
        user_result = await flow.async_step_user(None)
        await flow.async_step_user({CONF_CONTINENT: "North America"})
        country_result = await flow.async_step_country(None)
        await flow.async_step_country({CONF_COUNTRY: "United States"})
        place_result = await flow.async_step_place(None)

    for result, key in (
        (user_result, CONF_CONTINENT),
        (country_result, CONF_COUNTRY),
        (place_result, CONF_PLACE),
    ):
        selector = _selector_for(result["data_schema"], key)
        assert isinstance(selector, SelectSelector), key
        assert selector.config["mode"] == "dropdown", key


async def test_get_temperatures_does_not_log_its_own_error(
    mock_hass, caplog: pytest.LogCaptureFixture
) -> None:
    """The coordinator logs a failed refresh, so the API layer must not."""
    api = SeaTemperatureAPI(mock_hass)

    with patch(
        "custom_components.seatemperatures.api.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value.get.side_effect = aiohttp.ClientError("boom")

        with caplog.at_level(logging.DEBUG), pytest.raises(
            SeaTemperatureError
        ) as excinfo:
            await api.get_temperatures("/europe/denmark/copenhagen/")

    assert "boom" in str(excinfo.value)
    assert [
        record for record in caplog.records if record.levelno >= logging.ERROR
    ] == []


async def test_get_temperatures_rejects_an_invalid_path(mock_hass) -> None:
    """An unusable path is a failed refresh, not a silent None."""
    api = SeaTemperatureAPI(mock_hass)

    with pytest.raises(SeaTemperatureError):
        await api.get_temperatures("https://example.com/evil/")


async def test_fetch_turns_an_api_error_into_update_failed() -> None:
    """The coordinator has to see one UpdateFailed carrying the reason."""
    entry = SimpleNamespace(
        data={CONF_PATH: "/europe/denmark/copenhagen/", CONF_PLACE: "Copenhagen"},
        options={},
        async_on_unload=MagicMock(),
    )

    with patch(
        "custom_components.seatemperatures.coordinator.SeaTemperatureAPI"
    ) as api:
        api.return_value.get_temperatures = AsyncMock(
            side_effect=SeaTemperatureError("upstream is down")
        )
        coordinator = SeaTemperatureCoordinator(
            MagicMock(), entry, "/europe/denmark/copenhagen/"
        )

    with pytest.raises(UpdateFailed, match="upstream is down"):
        await coordinator._async_update_data()


async def test_every_request_carries_an_explicit_timeout(mock_hass) -> None:
    """A host that accepts the connection but never answers must not hang a refresh."""
    api = SeaTemperatureAPI(mock_hass)

    with patch(
        "custom_components.seatemperatures.api.async_get_clientsession"
    ) as mock_session:
        get = mock_session.return_value.get
        mock_response = AsyncMock()
        mock_response.text.return_value = load_fixture("copenhagen.html")
        mock_response.json.return_value = {"locations": []}
        mock_response.raise_for_status = MagicMock()
        get.return_value.__aenter__.return_value = mock_response

        await api.get_temperatures("/europe/denmark/copenhagen/")
        await api.get_map_locations()

    assert get.call_count == 2
    for call in get.call_args_list:
        assert call.kwargs["timeout"] is REQUEST_TIMEOUT

    assert REQUEST_TIMEOUT.total is not None
    assert REQUEST_TIMEOUT.total > 0


async def test_map_locations_are_cached_within_the_ttl(mock_hass) -> None:
    """Repeated lookups inside the TTL must not refetch 19k rows."""
    api = SeaTemperatureAPI(mock_hass)
    payload = {
        "locations": [
            ["sea-1", "Acharavi", "Greece", "Corfu", "/europe/greece/acharavi/"]
        ]
    }

    with patch(
        "custom_components.seatemperatures.api.async_get_clientsession"
    ) as mock_session:
        mock_response = AsyncMock()
        mock_response.json.return_value = payload
        mock_response.raise_for_status = MagicMock()
        mock_session.return_value.get.return_value.__aenter__.return_value = (
            mock_response
        )

        first = await api.get_map_locations()
        second = await api.get_map_locations()

        assert mock_session.return_value.get.call_count == 1

    assert first == second
    assert "sea-1" in first


async def test_map_locations_are_refetched_once_the_ttl_expires(mock_hass) -> None:
    """A beach added upstream must appear without restarting Home Assistant."""
    api = SeaTemperatureAPI(mock_hass)
    first_payload = {
        "locations": [
            ["sea-1", "Acharavi", "Greece", "Corfu", "/europe/greece/acharavi/"]
        ]
    }
    second_payload = {
        "locations": [
            ["sea-1", "Acharavi", "Greece", "Corfu", "/europe/greece/acharavi/"],
            ["sea-2", "Sylt", "Germany", "", "/europe/germany/island-of-sylt/"],
        ]
    }

    with patch(
        "custom_components.seatemperatures.api.async_get_clientsession"
    ) as mock_session:
        mock_response = AsyncMock()
        mock_response.json.side_effect = [first_payload, second_payload]
        mock_response.raise_for_status = MagicMock()
        mock_session.return_value.get.return_value.__aenter__.return_value = (
            mock_response
        )

        with patch(
            "custom_components.seatemperatures.api.time.monotonic", return_value=0.0
        ):
            first = await api.get_map_locations()

        with patch(
            "custom_components.seatemperatures.api.time.monotonic",
            return_value=MAP_LOCATIONS_TTL + 1.0,
        ):
            second = await api.get_map_locations()

        assert mock_session.return_value.get.call_count == 2

    assert "sea-2" not in first
    assert "sea-2" in second
