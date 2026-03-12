from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from custom_components.seatemperature.api import SeaTemperatureAPI


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
        "custom_components.seatemperature.api.async_get_clientsession"
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
    """Test getting temperatures from API."""
    api = SeaTemperatureAPI(mock_hass)

    mock_data = {
        "today": 21.5,
        "yesterday": 21.0,
        "last_week": 20.5,
        "last_year": 22.1,
        "average": {"min": 15.0, "max": 26.0, "avg": 20.0},
    }

    with patch(
        "custom_components.seatemperature.api.async_get_clientsession"
    ) as mock_session:
        mock_response = AsyncMock()
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        mock_session.return_value.get.return_value.__aenter__.return_value = (
            mock_response
        )

        result = await api.get_temperatures("123")
        assert result == mock_data
