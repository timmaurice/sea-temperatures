from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
import json
import logging
import posixpath
import re
from typing import Any
from urllib.parse import unquote, urlsplit

_LOGGER = logging.getLogger(__name__)

_CHART_PAYLOAD_RE = re.compile(
    r'<script[^>]*data-sea-curve-payload[^>]*>(.*?)</script>',
    flags=re.IGNORECASE | re.DOTALL,
)
_DATE_RE = re.compile(r">\s*([A-Za-z]+ \d{1,2}(?:st|nd|rd|th) [A-Za-z]+, \d{4})\s*<")


@dataclass(slots=True)
class SeaTemperatureData:
    """Structured data parsed from a location page."""

    date: str | None = None
    today: float | None = None
    yesterday: float | None = None
    last_week: float | None = None
    last_year: float | None = None
    average_min: float | None = None
    average_max: float | None = None
    average_avg: float | None = None
    trend_labels: list[str] | None = None
    trend_temps_c: list[float] | None = None

    def as_legacy_payload(self) -> dict[str, Any]:
        """Return the legacy payload shape expected by the integration."""
        payload: dict[str, Any] = {"sst": {}}
        sst: dict[str, Any] = payload["sst"]

        if self.date is not None:
            payload["date"] = self.date

        for key in ("today", "yesterday", "last_week", "last_year"):
            value = getattr(self, key)
            if value is not None:
                sst[key] = value

        average = {
            key: value
            for key, value in {
                "min": self.average_min,
                "max": self.average_max,
                "avg": self.average_avg,
            }.items()
            if value is not None
        }
        if average:
            sst["average"] = average

        if self.trend_labels and self.trend_temps_c:
            payload["charts"] = {
                "last_thirty": {
                    "labels": self.trend_labels,
                    "series": self.trend_temps_c,
                }
            }

        return payload


def validate_location_path(path: str) -> str:
    """Validate and normalize a SeaTemperatures location path."""
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Location path is empty")

    parts = urlsplit(path.strip())
    if parts.scheme or parts.netloc or parts.query or parts.fragment:
        raise ValueError("Location path must be a relative path")

    decoded_path = unquote(parts.path)
    if not decoded_path.startswith("/"):
        raise ValueError("Location path must start with '/'")

    if "\\" in decoded_path:
        raise ValueError("Location path must not contain backslashes")

    segments = [segment for segment in decoded_path.split("/") if segment]
    if not segments:
        raise ValueError("Location path must contain at least one segment")

    if any(segment in {".", ".."} for segment in segments):
        raise ValueError("Location path must not contain path traversal")

    normalized = posixpath.normpath("/" + "/".join(segments))
    return f"{normalized}/"


def parse_location_page(html: str) -> SeaTemperatureData:
    """Parse a SeaTemperatures location page into structured data."""
    data = SeaTemperatureData(
        date=_parse_page_date(html),
        today=_extract_summary_value(html, "Today"),
        yesterday=_extract_summary_value(html, "Yesterday"),
        average_avg=_extract_summary_value(html, "10-year average"),
        average_min=_extract_float(
            html, r'low temperature of\s*<span[^>]+data-c="([^"]+)"'
        ),
        average_max=_extract_float(html, r'high of\s*<span[^>]+data-c="([^"]+)"'),
    )

    trend_labels, trend_temps_c, last_week = _parse_trend_chart(html)
    data.trend_labels = trend_labels
    data.trend_temps_c = trend_temps_c
    data.last_week = last_week

    if not any(
        value is not None
        for value in (
            data.today,
            data.yesterday,
            data.average_avg,
            data.average_min,
            data.average_max,
            data.last_week,
        )
    ):
        _LOGGER.warning("Parsed SeaTemperatures page without any temperature values")

    return data


def _extract_summary_value(html: str, label: str) -> float | None:
    pattern = (
        rf">\s*{re.escape(label)}\s*</p>\s*<p[^>]*>\s*"
        r'<span[^>]+data-c="([^"]+)"'
    )
    return _extract_float(html, pattern)


def _extract_float(html: str, pattern: str) -> float | None:
    match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
    if match is None:
        return None

    try:
        return float(match.group(1))
    except (TypeError, ValueError):
        _LOGGER.debug("Failed to parse float from %s", match.group(1))
        return None


def _parse_page_date(html: str) -> str | None:
    match = _DATE_RE.search(html)
    if match is None:
        return None

    page_date = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", match.group(1))
    try:
        return datetime.strptime(page_date, "%A %d %B, %Y").date().isoformat()
    except ValueError:
        _LOGGER.debug("Failed to parse page date from %s", page_date)
        return None


def _parse_trend_chart(html: str) -> tuple[list[str] | None, list[float] | None, float | None]:
    match = _CHART_PAYLOAD_RE.search(html)
    if match is None:
        return None, None, None

    try:
        chart_payload = json.loads(unescape(match.group(1)))
    except json.JSONDecodeError as err:
        _LOGGER.warning("Failed to parse SeaTemperatures chart payload: %s", err)
        return None, None, None

    if not isinstance(chart_payload, dict):
        return None, None, None

    raw_times = chart_payload.get("times")
    raw_temps = chart_payload.get("tempsC")
    if not isinstance(raw_times, list) or not isinstance(raw_temps, list):
        return None, None, None

    points: list[tuple[int, float]] = []
    for raw_time, raw_temp in zip(raw_times, raw_temps, strict=False):
        try:
            points.append((int(raw_time), float(raw_temp)))
        except (TypeError, ValueError):
            continue

    if not points:
        return None, None, None

    points.sort(key=lambda point: point[0])
    labels = [datetime.fromtimestamp(ts, UTC).strftime("%m-%d") for ts, _ in points]
    temps = [temp for _, temp in points]

    latest_timestamp = points[-1][0]
    # The current site no longer exposes dedicated last-week/last-year values.
    # We only derive last_week when the daily chart includes the exact day.
    last_week_timestamp = latest_timestamp - 7 * 24 * 60 * 60
    last_week = next(
        (temp for timestamp, temp in points if timestamp == last_week_timestamp),
        None,
    )

    return labels, temps, last_week
