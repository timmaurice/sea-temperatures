# Sea Temperatures Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://github.com/hacs/integration)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/timmaurice/seatemperature?style=flat-square)
[![GH-downloads](https://img.shields.io/github/downloads/timmaurice/seatemperature/total?style=flat-square)](https://github.com/timmaurice/seatemperature/releases)
[![GH-last-commit](https://img.shields.io/github/last-commit/timmaurice/seatemperature.svg?style=flat-square)](https://github.com/timmaurice/seatemperature/commits/master)
[![GH-code-size](https://img.shields.io/github/languages/code-size/timmaurice/seatemperature.svg?style=flat-square)](https://github.com/timmaurice/seatemperature)
![GitHub](https://img.shields.io/github/license/timmaurice/seatemperature?style=flat-square)

This custom integration for Home Assistant fetches sea temperatures directly from [seatemperatures.net](https://seatemperatures.net).

- **Global Coverage**: Select coastal locations from around the world.
- **Detailed Attributes**: Provides today's temperature alongside historical data (yesterday, last week, last year) and averages as attributes.
- **Device per Place**: Creates a dedicated device in Home Assistant for each monitored location.

## Installation

### HACS (Recommended)

This card is available in the [Home Assistant Community Store (HACS)](https://hacs.xyz/).

<a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=timmaurice&repository=seatemperature&category=integration" target="_blank" rel="noreferrer noopener"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open a repository inside the Home Assistant Community Store." /></a>

<details>
<summary>Manual Installation</summary>

1.  Using the tool of your choice, copy the `seatemperature` folder from `custom_components` in this repository into your Home Assistant's `custom_components` directory.
2.  Restart Home Assistant.
</details>

## Configuration

Configuration is done entirely through the Home Assistant UI.

1.  Go to **Settings** -> **Devices & Services**.
2.  Click **Add Integration** and search for "Sea Temperature".
3.  **Step 1: Select Continent**: Choose the continent of your desired location.
4.  **Step 2: Select Country**: Choose the country.
5.  **Step 3: Select Place**: Choose the specific location/beach.
6.  Click **Submit**.

A new device will be created for the place, containing the temperature sensor. You can repeat this process to add multiple locations.

## Created Sensors

For each configured place, the following sensor will be created:

| Sensor          | Description                        | Attributes                                                                                 | Example Value |
| :-------------- | :--------------------------------- | :----------------------------------------------------------------------------------------- | :------------ |
| **Temperature** | The current sea temperature today. | `yesterday`, `last_week`, `last_year`, `date`, `average_min`, `average_max`, `average_avg` | `21.5`        |

## Contributions

Contributions are welcome! If you find a bug or have a feature request, please open an issue on the GitHub repository.

---

For further assistance or to [report issues](https://github.com/timmaurice/seatemperature/issues), please visit the [GitHub repository](https://github.com/timmaurice/seatemperature).

![Star History Chart](https://api.star-history.com/svg?repos=timmaurice/seatemperature&type=Date)

## ☕ Support My Work

[<img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" height="30" />](https://www.buymeacoffee.com/timmaurice)
