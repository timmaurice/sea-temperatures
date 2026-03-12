from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .api import SeaTemperatureAPI
from .const import (
    DOMAIN,
    CONF_CONTINENT,
    CONF_COUNTRY,
    CONF_PLACE,
    CONF_PLACE_ID,
)

_LOGGER = logging.getLogger(__name__)


class SeaTemperatureConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sea Temperature."""

    VERSION = 1
    _places_data: dict[str, Any] | None = None
    _continents: list[str] = []
    _countries: list[str] = []
    _places: dict[str, Any] = {}

    _data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step (fetch places and select continent)."""
        api = SeaTemperatureAPI(self.hass)

        if self._places_data is None:
            self._places_data = await api.get_places()
            if not self._places_data:
                return self.async_abort(reason="cannot_connect")

            # Extract continents from flat list
            self._continents = sorted(
                list(set(p["continent_name"] for p in self._places_data))
            )

        if user_input is not None:
            self._data[CONF_CONTINENT] = user_input[CONF_CONTINENT]
            return await self.async_step_country()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_CONTINENT): vol.In(self._continents),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
        )

    async def async_step_country(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the country selection step."""
        continent = self._data[CONF_CONTINENT]

        if not self._countries:
            # Extract countries for selected continent
            self._countries = sorted(
                list(
                    set(
                        p["country_name"]
                        for p in self._places_data
                        if p["continent_name"] == continent
                    )
                )
            )

        if user_input is not None:
            self._data[CONF_COUNTRY] = user_input[CONF_COUNTRY]
            return await self.async_step_place()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_COUNTRY): vol.In(self._countries),
            }
        )

        return self.async_show_form(
            step_id="country",
            data_schema=data_schema,
        )

    async def async_step_place(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the place selection step."""
        continent = self._data[CONF_CONTINENT]
        country = self._data[CONF_COUNTRY]

        if not self._places:
            # Extract places for selected country/continent
            places_list = [
                p
                for p in self._places_data
                if p["continent_name"] == continent and p["country_name"] == country
            ]
            self._places = {p["place_name"]: p["id"] for p in places_list}
            _LOGGER.debug(
                "Populated self._places for %s, %s: %s",
                continent,
                country,
                self._places,
            )

        if user_input is not None:
            place_name = user_input[CONF_PLACE]
            place_id = self._places[place_name]

            return self.async_create_entry(
                title=f"{place_name} Sea Temperature",
                data={
                    CONF_CONTINENT: continent,
                    CONF_COUNTRY: country,
                    CONF_PLACE: place_name,
                    CONF_PLACE_ID: str(place_id),
                },
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_PLACE): vol.In(
                    sorted(list(self._places.keys())) if self._places else []
                ),
            }
        )

        return self.async_show_form(
            step_id="place",
            data_schema=data_schema,
        )
