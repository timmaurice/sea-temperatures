from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from custom_components.seatemperatures.api import SeaTemperatureAPI


@pytest.fixture
def mock_hass():
    """Mock Home Assistant object."""
    return AsyncMock()


@pytest.mark.asyncio
async def test_get_places(mock_hass):
    """Test getting places from API."""
    api = SeaTemperatureAPI(mock_hass)

    mock_data = {"Europe": {"Spain": [{"id": 123, "name": "Ibiza", "slug": "ibiza"}]}}

    with patch(
        "custom_components.seatemperatures.api.async_get_clientsession"
    ) as mock_session:
        mock_response = AsyncMock()
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        # Async context manager mock setup
        mock_session.return_value.get.return_value.__aenter__.return_value = (
            mock_response
        )

        result = await api.get_places()
        assert result == mock_data


@pytest.mark.asyncio
async def test_get_temperatures(mock_hass):
    """Test getting temperatures from API including date attribute coverage."""
    api = SeaTemperatureAPI(mock_hass)

    mock_data = {
        "date": "2026-03-13",
        "sst": {
            "today": 17.25,
            "yesterday": 17.26,
            "last_week": 16.17,
            "last_year": 16.25,
            "average": {"min": 14.71, "max": 16.25, "avg": 15.422999999999998},
        },
        "charts": {
            "last_thirty": {
                "labels": ["03-12", "03-13"],
                "series": [17.26, 17.25],
            }
        },
    }

    with patch(
        "custom_components.seatemperatures.api.async_get_clientsession"
    ) as mock_session:
        mock_response = AsyncMock()
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        mock_session.return_value.get.return_value.__aenter__.return_value = (
            mock_response
        )

        result = await api.get_temperatures("123")

        # Verify result contains the mock data layout including date and nested average
        assert result == mock_data
        assert "date" in result
        assert result["date"] == "2026-03-13"
        assert result["sst"]["today"] == 17.25
        assert result["sst"]["average"]["avg"] == 15.422999999999998
        assert "charts" in result
        assert "last_thirty" in result["charts"]
        assert result["charts"]["last_thirty"]["labels"] == ["03-12", "03-13"]
