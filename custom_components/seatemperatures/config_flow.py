from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .api import SeaTemperatureAPI
from .const import (
    CONF_AREA,
    DOMAIN,
    CONF_CONTINENT,
    CONF_COUNTRY,
    CONF_PLACE,
    CONF_PATH,
)

_LOGGER = logging.getLogger(__name__)
QUERY_FIELD = "query"


class SeaTemperatureConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sea Temperature."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._search_results: dict[str, dict[str, str]] = {}
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Search for a location to configure."""
        api = SeaTemperatureAPI(self.hass)
        errors: dict[str, str] = {}

        if user_input is not None:
            query = user_input[QUERY_FIELD].strip()
            if not query:
                errors["base"] = "invalid_query"
            else:
                results = await api.search_locations(query)
                if results is None:
                    return self.async_abort(reason="cannot_connect")

                self._search_results = self._build_result_map(results)
                self._data[QUERY_FIELD] = query
                if self._search_results:
                    return await self.async_step_select()

                errors["base"] = "no_results"

        data_schema = vol.Schema(
            {
                vol.Required(
                    QUERY_FIELD,
                    default=user_input[QUERY_FIELD] if user_input else "",
                ): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select one of the search results."""
        if not self._search_results:
            return await self.async_step_user()

        if user_input is not None:
            location = self._search_results[user_input[CONF_PLACE]]
            await self.async_set_unique_id(location[CONF_PATH])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"{location[CONF_PLACE]} Sea Temperature",
                data={
                    CONF_CONTINENT: location.get(CONF_CONTINENT, ""),
                    CONF_COUNTRY: location.get(CONF_COUNTRY, ""),
                    CONF_AREA: location.get(CONF_AREA, ""),
                    CONF_PLACE: location[CONF_PLACE],
                    CONF_PATH: location[CONF_PATH],
                },
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_PLACE): vol.In(list(self._search_results.keys())),
            }
        )

        return self.async_show_form(
            step_id="select",
            data_schema=data_schema,
            description_placeholders={QUERY_FIELD: self._data.get(QUERY_FIELD, "")},
            last_step=True,
        )

    def _build_result_map(
        self, results: list[dict[str, str]]
    ) -> dict[str, dict[str, str]]:
        """Build a stable label -> location mapping for flow selection."""
        mapped_results: dict[str, dict[str, str]] = {}
        for result in results:
            label = self._format_result_label(result)
            if label in mapped_results:
                label = f"{label} [{result[CONF_PATH]}]"

            mapped_results[label] = {
                CONF_CONTINENT: result.get("region", ""),
                CONF_COUNTRY: result.get("country", ""),
                CONF_AREA: result.get("area", ""),
                CONF_PLACE: result["name"],
                CONF_PATH: result["path"],
            }

        _LOGGER.debug("Search results mapped for selection: %s", mapped_results)
        return mapped_results

    @staticmethod
    def _format_result_label(result: dict[str, str]) -> str:
        """Format a search result for display in the config flow."""
        details = result.get("area") or ", ".join(
            part
            for part in (result.get("country"), result.get("region"))
            if part
        )
        if details:
            return f"{result['name']} ({details})"

        return result["name"]
