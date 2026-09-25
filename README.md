# Sea Temperatures Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://github.com/hacs/integration)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/timmaurice/sea-temperatures?style=flat-square)
[![GH-downloads](https://img.shields.io/github/downloads/timmaurice/sea-temperatures/total?style=flat-square)](https://github.com/timmaurice/sea-temperatures/releases)
[![GH-last-commit](https://img.shields.io/github/last-commit/timmaurice/sea-temperatures.svg?style=flat-square)](https://github.com/timmaurice/sea-temperatures/commits/master)
[![GH-code-size](https://img.shields.io/github/languages/code-size/timmaurice/sea-temperatures.svg?style=flat-square)](https://github.com/timmaurice/sea-temperatures)
![GitHub](https://img.shields.io/github/license/timmaurice/sea-temperatures?style=flat-square)

This custom integration for Home Assistant fetches sea temperatures directly from [seatemperatures.net](https://seatemperatures.net). **It comes fully bundled with a beautiful custom Lovelace card!**

<img src="https://raw.githubusercontent.com/timmaurice/sea-temperatures/main/frontend/image.png" alt="Card Screenshot" width="500px" />

> Today's sea temperature, the 10-year average, and a 30-day trend for 19,259 coastal locations, lakes, and rivers around the world.

## Features

- **Global Coverage**: Select coastal locations from around the world.
- **Detailed Attributes**: Provides today's temperature alongside current site data such as yesterday, 10-year averages, and a 30-day chart. A `last_week` value is exposed only when it can be derived from the published 30-day series.
- **Device per Place**: Creates a dedicated device in Home Assistant for each monitored location.
- **Bundled Custom Card**: Displays current temperatures, a trend indicator (↑/↓/→) against the site's own published `yesterday` value, and a 30-day D3 historical area chart.
- **Touch Friendly**: The chart is scrubbable by touch and pen as well as by mouse, without blocking page scrolling.
- **Accessible**: Place rows are focusable and keyboard-operable, and both the row and the chart expose screen-reader summaries.
- **Graceful When Offline**: An unavailable or unknown place shows a dash instead of a bogus reading and sorts last.
- **Localization**: Supports English, German, Spanish, French, and Italian out of the box.

## Installation

### HACS (Recommended)

This integration is available in the [Home Assistant Community Store (HACS)](https://hacs.xyz/). _Note: Because the frontend card is bundled, you do not need to install a separate frontend repository!_

**Requires Home Assistant 2026.6.0 or newer** (declared in `hacs.json`); HACS hides the repository on older cores.

<a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=timmaurice&repository=sea-temperatures&category=integration" target="_blank" rel="noreferrer noopener"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open a repository inside the Home Assistant Community Store." /></a>

<details>
<summary>Manual Installation</summary>

1.  Using the tool of your choice, copy the `seatemperatures` folder from `custom_components` in this repository into your Home Assistant's `custom_components` directory.
2.  Restart Home Assistant.

</details>

## Configuration

### 1. Adding the Integration

Configuration is done entirely through the Home Assistant UI.

1.  Go to **Settings** -> **Devices & Services**.
2.  Click **Add Integration** and search for "Sea Temperature".
    1. **Step 1: Select Continent**: Choose the continent of your desired location.
    2. **Step 2: Select Country**: Choose the country.
    3. **Step 3: Select Place**: Choose the specific location/beach.
3.  Click **Submit**.

### 2. Changing the Update Interval

The integration polls every **2 hours** by default - the site publishes one
reading a day, so there is little to gain from polling harder. To change it, go
to **Settings** -> **Devices & Services** -> **Sea Temperatures** -> **Configure**
and set the interval (1-24 hours). The entry reloads itself; nothing is deleted,
so the recorded history is kept.

Repointing an existing entry at a _different_ place is deliberately not offered:
one entity holding two locations' readings would corrupt its long-term
statistics. Add a second entry instead.

If something goes wrong, the integration's overflow menu offers
**Download diagnostics** - it reports the entry, the coordinator state and a
summary of the 30-day series.

### 3. Adding the Dashboard Card

Once your sensor is set up, you can add the custom card to your Lovelace dashboard:

1. Edit your dashboard and click **Add Card**.
2. Search for "Custom: Sea Temperatures Card" or use the Manual YAML editor.

<details>
<summary>Dashboards in YAML mode</summary>

The integration registers the card as a Lovelace resource by itself only while
Lovelace is in **storage** mode. With `lovelace: mode: yaml` it logs a warning
and registers nothing, because the resource list is your file to own. Add it
yourself:

```yaml
lovelace:
  mode: yaml
  resources:
    - url: /seatemperatures_frontend/sea-temperatures-card.js?v=3.3.1
      type: module
```

**Raise the `?v=` on every update.** Home Assistant serves the bundled card with
`Cache-Control: max-age=2678400` - 31 days - so a browser that has the file
keeps the old one for a month unless the URL changes. In storage mode the
integration does this for you by appending the integration's version; in YAML
mode the query string is yours to bump.

</details>

**YAML Configuration:**

| Name                | Type    | Default      | Description                                                                                                            |
| ------------------- | ------- | ------------ | ---------------------------------------------------------------------------------------------------------------------- |
| `type`              | string  | **Required** | `custom:sea-temperatures-card`                                                                                         |
| `title`             | string  | `(none)`     | The title of the card.                                                                                                 |
| `places`            | list    | **Required** | A list of places to display. Can be entity IDs, device IDs, or objects with `device` and `name` (`name` is YAML only). |
| `sort_by`           | string  | `default`    | Sort places by `default`, `name`, `temp_asc`, or `temp_desc`.                                                          |
| `show_last_updated` | boolean | `true`       | Show the last updated timestamp.                                                                                       |
| `show_trend`        | boolean | `true`       | Show the trend indicator (today vs. the sensor's `yesterday` attribute, not a 24h history query).                      |
| `show_stats`        | boolean | `true`       | Show statistics (Yesterday, Last Week, 10-Year Avg).                                                                   |
| `show_chart`        | boolean | `true`       | Show historical 30-day D3 chart.                                                                                       |
| `show_country`      | boolean | `false`      | Append the country to the place name (e.g., Bondi Beach (Australia)).                                                  |
| `chart_smoothing`   | string  | `smooth`     | Algorithm for D3 chart drawing. Valid options: `smooth`, `linear`, `step`                                              |

**YAML Example:**

```yaml
type: custom:sea-temperatures-card
title: My Favorite Beaches
places:
  - sensor.acharavi_sea_temperature
  - device: 5b1a09b17436b7a9e0f3e8f9d0c1b2a3
    name: My Local Beach
sort_by: name
show_country: true
```

## Created Sensors

For each configured place, the following sensor will be created:

| Sensor          | Description                        | Attributes                                                                                                                                                                      | Example Value |
| :-------------- | :--------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------------ |
| **Temperature** | The current sea temperature today. | `yesterday`, `last_week` (when derivable from the 30-day chart), `date`, `average_min`, `average_max`, `average_avg`, `charts`, `continent`, `country`, `area`, `place`, `path` | `21.5`        |

The sensor is named after its device class in your Home Assistant language, so it shows up as "Island of Sylt Temperature" in English and "Island of Sylt Temperatur" in German. Its icon is Home Assistant's default for temperature sensors. The entity ID (`sensor.seatemperatures_<place>_today`) is the same in every language, and a rename or custom icon you set in the UI still takes precedence.

`last_year` has been replaced by the `average_avg` (10-year average) attribute to align with the current SeaTemperatures.net layout.

The `charts` attribute holds the 30-day series as `charts.last_thirty` with `labels` and `series`. Labels are full ISO calendar dates (`YYYY-MM-DD`); earlier releases emitted `MM-DD`, which the card still accepts when reading a restored state.

## Development

<details>
<summary>Setting up the Dev Environment</summary>

This repository includes a standard Home Assistant Devcontainer.

1. Open the repository in VS Code and select "Reopen in Container".
2. The environment will automatically install Python dependencies and Pyrefly.
3. The frontend dependencies (`npm install`) will be automatically installed in the `/frontend` directory.
4. Building the card requires **Node 20 or newer**; the toolchain fails on Node 18.
5. To build the frontend card locally, run:

```bash
    npm run build
```

</details>

## Contributions

Contributions are welcome! If you find a bug or have a feature request, please open an issue on the GitHub repository.

<details>
<summary>Contributing Translations</summary>

If you would like to contribute a new frontend translation:

1.  In the `frontend/src/translation` directory, copy `en.json` and rename it to your language code (e.g., `nl.json` for Dutch).
2.  Translate all the values in the new file.
3.  Import new file in `frontend/src/localize.ts` and add it to `translations` array.
4.  Submit a pull request with your changes.

</details>

---

For further assistance or to [report issues](https://github.com/timmaurice/sea-temperatures/issues), please visit the [GitHub repository](https://github.com/timmaurice/sea-temperatures).

## ☕ Support My Work

[<img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" height="30" />](https://www.buymeacoffee.com/timmaurice)
