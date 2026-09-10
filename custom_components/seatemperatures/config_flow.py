from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .api import SeaTemperatureAPI
from .const import (
    CONF_AREA,
    CONF_CONTINENT,
    CONF_COUNTRY,
    CONF_PATH,
    CONF_PLACE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_CONTINENT_MINOR_WORDS = frozenset({"and", "of", "the"})

# The first path segment of every location, as published by
# /api/map-locations.json. Slugs missing here fall back to a title-cased name,
# so a stale entry is worse than none: it produces a second spelling of a
# continent that no location actually resolves to.
CONTINENT_NAMES = {
    "africa": "Africa",
    "antarctica": "Antarctica",
    "asia": "Asia",
    "australia-and-oceania": "Australia and Oceania",
    "central-america-and-the-caribbean": "Central America and the Caribbean",
    "europe": "Europe",
    "middle-east": "Middle East",
    "north-america": "North America",
    "south-america": "South America",
}


class SeaTemperatureConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sea Temperature."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._locations_data: dict[str, dict[str, str]] | None = None
        self._continents: list[str] = []
        self._countries: list[str] = []
        self._places: dict[str, dict[str, str]] = {}
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step (fetch map locations and select continent)."""
        errors: dict[str, str] = {}

        if self._locations_data is None:
            api = SeaTemperatureAPI(self.hass)
            locations = await api._get_map_locations()
            if not locations:
                # Re-show the form rather than aborting: "cannot_connect" only
                # exists under config.error in the translations, and an upstream
                # hiccup should be retryable without restarting the whole flow.
                errors["base"] = "cannot_connect"
            else:
                self._locations_data = locations

                # Extract unique continents from path segments
                continents_set = set()
                for loc in self._locations_data.values():
                    path = loc.get("path", "")
                    parts = [p for p in path.split("/") if p]
                    if parts:
                        continents_set.add(self._get_continent_name(parts[0]))
                self._continents = sorted(continents_set)

        # The retry form carries no continent field, so its submission has to fall
        # through to another fetch instead of being read as a selection.
        if user_input is not None and CONF_CONTINENT in user_input:
            self._data[CONF_CONTINENT] = user_input[CONF_CONTINENT]
            return await self.async_step_country()

        if errors:
            # An empty schema still renders a submit button, which is the retry.
            return self.async_show_form(
                step_id="user", data_schema=vol.Schema({}), errors=errors
            )

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
        selected_continent = self._data[CONF_CONTINENT]

        # Extract countries for the selected continent
        countries_set = set()
        for loc in self._locations_data.values():
            path = loc.get("path", "")
            parts = [p for p in path.split("/") if p]
            if (
                parts
                and self._get_continent_name(parts[0]) == selected_continent
                and loc.get("country")
            ):
                countries_set.add(loc["country"])
        self._countries = sorted(countries_set)

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
        selected_continent = self._data[CONF_CONTINENT]
        selected_country = self._data[CONF_COUNTRY]

        # Extract places for selected country and continent
        self._places = {}
        for loc in self._locations_data.values():
            path = loc.get("path", "")
            parts = [p for p in path.split("/") if p]
            if (
                parts
                and self._get_continent_name(parts[0]) == selected_continent
                and loc.get("country") == selected_country
            ):
                place_name = loc["name"]
                if loc.get("area"):
                    place_name = f"{place_name} ({loc['area']})"
                if place_name in self._places:
                    place_name = f"{place_name} [{loc['path']}]"
                self._places[place_name] = loc

        if user_input is not None:
            selected_label = user_input[CONF_PLACE]
            location = self._places[selected_label]
            await self.async_set_unique_id(location["path"])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"{location['name']} Sea Temperature",
                data={
                    CONF_CONTINENT: selected_continent,
                    CONF_COUNTRY: selected_country,
                    CONF_AREA: location.get("area", ""),
                    CONF_PLACE: location["name"],
                    CONF_PATH: location["path"],
                },
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_PLACE): vol.In(
                    sorted(self._places.keys()) if self._places else []
                ),
            }
        )

        return self.async_show_form(
            step_id="place",
            data_schema=data_schema,
            last_step=True,
        )

    def _get_continent_name(self, slug: str) -> str:
        """Map continent slug to friendly name."""
        if slug in CONTINENT_NAMES:
            return CONTINENT_NAMES[slug]

        # A slug the site adds later still has to read as a name rather than as
        # "Central America And The Caribbean", so keep the joining words small.
        words = slug.split("-")
        return " ".join(
            word if index and word in _CONTINENT_MINOR_WORDS else word.title()
            for index, word in enumerate(words)
        )
