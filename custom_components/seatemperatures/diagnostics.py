"""Diagnostics support for the Sea Temperatures integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    Nothing here is redacted, and that is deliberate: the entry stores a public
    location path plus its continent, country and area, and the coordinator
    holds published sea temperatures. There are no credentials, no coordinates
    and no account identifiers to hide.

    The 30-day chart is summarised rather than dumped - a diagnostics download
    is meant to be readable, and the series is 30 numbers per place that say
    nothing a first and last point does not.
    """
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    data = getattr(coordinator, "data", None)

    return {
        "entry": {
            "version": entry.version,
            "minor_version": getattr(entry, "minor_version", None),
            "unique_id": entry.unique_id,
            "title": entry.title,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": getattr(coordinator, "last_update_success", None),
            "update_interval": str(getattr(coordinator, "update_interval", None)),
            "data": _summarize_payload(data),
        },
    }


def _summarize_payload(data: Any) -> Any:
    """Return the coordinator payload with the chart series collapsed."""
    if not isinstance(data, dict):
        return data

    summary = {key: value for key, value in data.items() if key != "charts"}

    charts = data.get("charts")
    if isinstance(charts, dict):
        summary["charts"] = {
            name: _summarize_series(series) for name, series in charts.items()
        }

    return summary


def _summarize_series(series: Any) -> Any:
    """Describe one chart series by its length and its endpoints."""
    if not isinstance(series, dict):
        return series

    labels = series.get("labels")
    values = series.get("series")
    if not isinstance(labels, list) or not isinstance(values, list):
        return series

    return {
        "points": len(values),
        "first_label": labels[0] if labels else None,
        "last_label": labels[-1] if labels else None,
        "first_value": values[0] if values else None,
        "last_value": values[-1] if values else None,
    }
