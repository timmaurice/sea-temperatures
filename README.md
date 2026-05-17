# Sea Temperatures Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://github.com/hacs/integration)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/timmaurice/sea-temperatures?style=flat-square)
[![GH-downloads](https://img.shields.io/github/downloads/timmaurice/sea-temperatures/total?style=flat-square)](https://github.com/timmaurice/sea-temperatures/releases)
[![GH-last-commit](https://img.shields.io/github/last-commit/timmaurice/sea-temperatures.svg?style=flat-square)](https://github.com/timmaurice/sea-temperatures/commits/master)
[![GH-code-size](https://img.shields.io/github/languages/code-size/timmaurice/sea-temperatures.svg?style=flat-square)](https://github.com/timmaurice/sea-temperatures)
![GitHub](https://img.shields.io/github/license/timmaurice/sea-temperatures?style=flat-square)

This custom integration for Home Assistant fetches sea temperatures directly from [seatemperatures.net](https://seatemperatures.net). **It comes fully bundled with a beautiful custom Lovelace card!**

<img src="https://raw.githubusercontent.com/timmaurice/lovelace-sea-temperatures-card/main/image.png" alt="Card Screenshot" />

> We provide free daily current and average sea water temperatures for 12,165 locations in 227 countries.

## Features
- **Global Coverage**: Select coastal locations from around the world.
- **Detailed Attributes**: Provides today's temperature alongside historical data (yesterday, last week, last year) and averages as attributes.
- **Device per Place**: Creates a dedicated device in Home Assistant for each monitored location.
- **Bundled Custom Card**: Displays current temperatures, 24h trend indicators (🌊/📈/📉), and a 30-day D3 historical area chart.
- **Localization**: Supports English and German out of the box.

## Installation

### HACS (Recommended)

This integration is available in the [Home Assistant Community Store (HACS)](https://hacs.xyz/). *Note: Because the frontend card is bundled, you do not need to install a separate frontend repository!*

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
3.  **Step 1: Select Continent**: Choose the continent of your desired location.
4.  **Step 2: Select Country**: Choose the country.
5.  **Step 3: Select Place**: Choose the specific location/beach.
6.  Click **Submit**.

### 2. Adding the Dashboard Card

Once your sensor is set up, you can add the custom card to your Lovelace dashboard:

1. Edit your dashboard and click **Add Card**.
2. Search for "Custom: Sea Temperatures Card" or use the Manual YAML editor.

**YAML Configuration:**
| Name                | Type                    | Default      | Description                                                                                  |
| ------------------- | ----------------------- | ------------ | -------------------------------------------------------------------------------------------- |
| `type`              | string                  | **Required** | `custom:sea-temperatures-card`                                                               |
| `title`             | string                  | `(none)`     | The title of the card.                                                                       |
| `entity`            | string                  | **Required** | The entity ID of the sea temperature sensor (e.g. `sensor.acharavi_sea_temperature`).        |
| `show_last_updated` | boolean                 | `true`       | Show the last updated timestamp.                                                             |
| `show_trend`        | boolean                 | `true`       | Show 24h trend indicators.                                                                   |
| `show_stats`        | boolean                 | `true`       | Show statistics (Yesterday, Last Week, Last Year).                                           |
| `show_chart`        | boolean                 | `true`       | Show historical 30-day D3 chart.                                                             |
| `chart_smoothing`   | string                  | `smooth`     | Algorithm for D3 chart drawing. Valid options: `smooth`, `linear`, `step`                    |

## Created Sensors

For each configured place, the following sensor will be created:

| Sensor          | Description                        | Attributes                                                                                 | Example Value |
| :-------------- | :--------------------------------- | :----------------------------------------------------------------------------------------- | :------------ |
| **Temperature** | The current sea temperature today. | `yesterday`, `last_week`, `last_year`, `date`, `average_min`, `average_max`, `average_avg`, `charts` | `21.5`        |

## Development

<details>
<summary>Setting up the Dev Environment</summary>

This repository includes a standard Home Assistant Devcontainer. 
1. Open the repository in VS Code and select "Reopen in Container".
2. The environment will automatically install Python dependencies and Pyrefly.
3. The frontend dependencies (`npm install`) will be automatically installed in the `/frontend` directory.
4. To build the frontend card locally, run:
    ```bash
    cd frontend
    npm run build
    ```
</details>

## Contributions

Contributions are welcome! If you find a bug or have a feature request, please open an issue on the GitHub repository.

<details>
<summary>Contributing Translations</summary>

If you would like to contribute a new frontend translation:

1.  In the `frontend/src/translation` directory, copy `en.json` and rename it to your language code (e.g., `fr.json` for French).
2.  Translate all the values in the new file.
3.  Import new file in `frontend/src/localize.ts` and add it to `translations` array.
4.  Submit a pull request with your changes.

</details>

---

For further assistance or to [report issues](https://github.com/timmaurice/sea-temperatures/issues), please visit the [GitHub repository](https://github.com/timmaurice/sea-temperatures).

![Star History Chart](https://api.star-history.com/svg?repos=timmaurice/sea-temperatures&type=Date)

## ☕ Support My Work

[<img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" height="30" />](https://www.buymeacoffee.com/timmaurice)
