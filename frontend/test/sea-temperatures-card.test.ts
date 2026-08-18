import { describe, it, expect } from 'vitest';
import { SeaTemperaturesCard } from '../src/sea-temperatures-card';
import { HomeAssistant, SeaTemperaturesCardConfig } from '../src/types';

interface CardTestHarness {
  hass: HomeAssistant;
  _fetchChartData: () => void;
  _chartData: Record<string, { date: Date; value: number }[]>;
  _historyState: Record<string, string>;
}

describe('SeaTemperaturesCard', () => {
  describe('Initialization and Configuration', () => {
    it('is defined', () => {
      expect(customElements.get('sea-temperatures-card')).toBeDefined();
    });

    it('sets config correctly', () => {
      const card = new SeaTemperaturesCard();
      const config = {
        type: 'custom:sea-temperatures-card',
        places: [{ device: 'test-device', name: 'Test Place' }],
      };
      card.setConfig(config as unknown as SeaTemperaturesCardConfig);
      expect(
        ((card as unknown as { _config: SeaTemperaturesCardConfig })._config.places[0] as { name: string }).name,
      ).toBe('Test Place');
    });

    it('throws error if places are missing', () => {
      const card = new SeaTemperaturesCard();
      expect(() =>
        card.setConfig({ type: 'custom:sea-temperatures-card' } as unknown as SeaTemperaturesCardConfig),
      ).toThrow('You need to define at least one place.');
    });

    it('prioritizes entities with historical attributes', () => {
      const card = new SeaTemperaturesCard();
      const config: SeaTemperaturesCardConfig = {
        type: 'custom:sea-temperatures-card',
        places: [{ device: 'device-1' }],
      };
      const hass = {
        states: {
          'sensor.temp_sensor': {
            entity_id: 'sensor.temp_sensor',
            state: '20.0',
            attributes: { unit_of_measurement: '°C' },
          },
          'sensor.sea_temp_sensor': {
            entity_id: 'sensor.sea_temp_sensor',
            state: '21.0',
            attributes: { unit_of_measurement: '°C', yesterday: '20.5' },
          },
        },
        entities: {
          'sensor.temp_sensor': { device_id: 'device-1' },
          'sensor.sea_temp_sensor': { device_id: 'device-1' },
        },
        devices: {
          'device-1': { id: 'device-1', name: 'Test Device' },
        },
        localize: (key: string) => key,
      } as unknown as HomeAssistant;

      card.setConfig(config);
      const data = (
        card as unknown as { _getPlacesData: (h: HomeAssistant, c: SeaTemperaturesCardConfig) => unknown[] }
      )._getPlacesData(hass, config) as Record<string, unknown>[];
      expect(data[0].entity_id).toBe('sensor.sea_temp_sensor');
      expect(data[0].yesterday).toBe('20.5');
    });
  });

  describe('Chart Data Parsing', () => {
    it('parses chart data from charts attribute correctly', () => {
      const card = new SeaTemperaturesCard();
      const config: SeaTemperaturesCardConfig = {
        type: 'custom:sea-temperatures-card',
        places: [{ device: 'device-1' }],
      };
      const hass = {
        states: {
          'sensor.sea_temp_sensor': {
            entity_id: 'sensor.sea_temp_sensor',
            state: '21.0',
            attributes: {
              unit_of_measurement: '°C',
              charts: {
                last_thirty: {
                  labels: ['2026-03-12', '2026-03-13'],
                  series: [20.5, 21.0],
                },
              },
            },
          },
        },
        entities: {
          'sensor.sea_temp_sensor': { device_id: 'device-1' },
        },
        devices: {
          'device-1': { id: 'device-1', name: 'Test Device' },
        },
      } as unknown as HomeAssistant;

      card.setConfig(config);
      (card as unknown as CardTestHarness).hass = hass;

      (card as unknown as CardTestHarness)._fetchChartData();

      const chartData = (card as unknown as CardTestHarness)._chartData['sensor.sea_temp_sensor'];
      expect(chartData).toBeDefined();
      expect(chartData.length).toBe(2);
      expect(chartData[0].value).toBe(20.5);
      expect(chartData[1].value).toBe(21.0);
      expect(chartData[0].date).toBeInstanceOf(Date);
    });

    it('handles missing charts attribute without error', () => {
      const card = new SeaTemperaturesCard();
      const config: SeaTemperaturesCardConfig = {
        type: 'custom:sea-temperatures-card',
        places: [{ device: 'device-1' }],
      };
      const hass = {
        states: {
          'sensor.sea_temp_sensor': {
            entity_id: 'sensor.sea_temp_sensor',
            state: '21.0',
            attributes: {},
          },
        },
        entities: {
          'sensor.sea_temp_sensor': { device_id: 'device-1' },
        },
        devices: {
          'device-1': { id: 'device-1', name: 'Test Device' },
        },
      } as unknown as HomeAssistant;

      card.setConfig(config);
      (card as unknown as CardTestHarness).hass = hass;

      (card as unknown as CardTestHarness)._fetchChartData();

      const chartData = (card as unknown as CardTestHarness)._chartData;
      expect(chartData).toEqual({});
    });

    it('ignores invalid charts data length mismatch', () => {
      const card = new SeaTemperaturesCard();
      const config: SeaTemperaturesCardConfig = {
        type: 'custom:sea-temperatures-card',
        places: [{ device: 'device-1' }],
      };
      const hass = {
        states: {
          'sensor.sea_temp_sensor': {
            entity_id: 'sensor.sea_temp_sensor',
            state: '21.0',
            attributes: {
              charts: {
                last_thirty: {
                  labels: ['2026-03-12'],
                  series: [20.5, 21.0], // mismatch
                },
              },
            },
          },
        },
        entities: {
          'sensor.sea_temp_sensor': { device_id: 'device-1' },
        },
        devices: {
          'device-1': { id: 'device-1', name: 'Test Device' },
        },
      } as unknown as HomeAssistant;

      card.setConfig(config);
      (card as unknown as CardTestHarness).hass = hass;

      (card as unknown as CardTestHarness)._fetchChartData();

      const chartData = (card as unknown as CardTestHarness)._chartData;
      expect(chartData['sensor.sea_temp_sensor']).toBeUndefined();
    });
  });

  describe('Editor Configuration Rendering', () => {
    // Helper to setup card and render its shadow DOM
    const setupCard = async (configOptions: Partial<SeaTemperaturesCardConfig>) => {
      const card = new SeaTemperaturesCard();

      const config: SeaTemperaturesCardConfig = {
        type: 'custom:sea-temperatures-card',
        places: [{ device: 'device-1' }],
        ...configOptions,
      };

      const hass = {
        states: {
          'sensor.sea_temp_sensor': {
            entity_id: 'sensor.sea_temp_sensor',
            state: '21.0',
            last_updated: '2026-03-15T12:00:00.000Z',
            attributes: {
              unit_of_measurement: '°C',
              yesterday: '20.5',
              last_week: '19.0',
              average_avg: '18.0',
              charts: {
                last_thirty: {
                  labels: ['2026-03-12', '2026-03-13'],
                  series: [20.5, 21.0],
                },
              },
            },
          },
        },
        entities: {
          'sensor.sea_temp_sensor': { device_id: 'device-1' },
        },
        devices: {
          'device-1': { id: 'device-1', name: 'Test Device' },
        },
        localize: (key: string) => key,
      } as unknown as HomeAssistant;

      card.setConfig(config);
      card.hass = hass;

      // Mount the element to DOM to trigger Lit's render cycle
      document.body.appendChild(card);
      await card.updateComplete;

      return card;
    };

    it('renders the title if set', async () => {
      const card = await setupCard({ title: 'My Custom Ocean' });
      const header = card.shadowRoot?.querySelector('ha-card') as HTMLElement & { header?: string };
      expect(header?.header).toBe('My Custom Ocean');
      card.remove();
    });

    it('renders stats blocks strictly when show_stats is true or omitted', async () => {
      const cardEnabled = await setupCard({ show_stats: true });
      expect(cardEnabled.shadowRoot?.querySelector('.stats-grid')).not.toBeNull();
      cardEnabled.remove();

      const cardDisabled = await setupCard({ show_stats: false });
      expect(cardDisabled.shadowRoot?.querySelector('.stats-grid')).toBeNull();
      cardDisabled.remove();
    });

    it('renders SVG chart container strictly when show_chart is true or omitted', async () => {
      const cardEnabled = await setupCard({ show_chart: true });
      expect(cardEnabled.shadowRoot?.querySelector('.chart-container')).not.toBeNull();
      cardEnabled.remove();

      const cardDisabled = await setupCard({ show_chart: false });
      expect(cardDisabled.shadowRoot?.querySelector('.chart-container')).toBeNull();
      cardDisabled.remove();
    });

    it('renders last_updated strictly when show_last_updated is true or omitted', async () => {
      const cardEnabled = await setupCard({ show_last_updated: true });
      expect(cardEnabled.shadowRoot?.querySelector('.last-updated')).not.toBeNull();
      cardEnabled.remove();

      const cardDisabled = await setupCard({ show_last_updated: false });
      expect(cardDisabled.shadowRoot?.querySelector('.last-updated')).toBeNull();
      cardDisabled.remove();
    });

    it('renders trend icons strictly when show_trend is true or omitted', async () => {
      // For this to show we need history fetched (which sets _historyState)
      const cardEnabled = await setupCard({ show_trend: true });

      expect(cardEnabled.shadowRoot?.querySelector('.current-trend')).not.toBeNull();
      expect(cardEnabled.shadowRoot?.querySelector('.current-trend.pos')).not.toBeNull();
      cardEnabled.remove();

      const cardDisabled = await setupCard({ show_trend: false });
      expect(cardDisabled.shadowRoot?.querySelector('.current-trend')).toBeNull();
      cardDisabled.remove();
    });

    it('sets the correct default smoothing type', async () => {
      // should default to smooth
      const card = await setupCard({ show_chart: true });
      expect((card as unknown as { _config: SeaTemperaturesCardConfig })._config.chart_smoothing).toBe('smooth');
      card.remove();
    });

    it('honors explicitly defined chart smoothing properties', async () => {
      const cardStep = await setupCard({ show_chart: true, chart_smoothing: 'step' });
      expect((cardStep as unknown as { _config: SeaTemperaturesCardConfig })._config.chart_smoothing).toBe('step');
      cardStep.remove();

      const cardLinear = await setupCard({ show_chart: true, chart_smoothing: 'linear' });
      expect((cardLinear as unknown as { _config: SeaTemperaturesCardConfig })._config.chart_smoothing).toBe('linear');
      cardLinear.remove();
    });

    it('renders country name when show_country is true', async () => {
      const card = await setupCard({ show_country: true });
      // Add country to state attributes for testing - properly clone to trigger update
      const oldState = card.hass.states['sensor.sea_temp_sensor'];
      const hass = {
        ...card.hass,
        states: {
          ...card.hass.states,
          'sensor.sea_temp_sensor': {
            ...oldState,
            attributes: {
              ...oldState.attributes,
              country: 'Germany',
            },
          },
        },
      };
      card.hass = hass as unknown as HomeAssistant;
      await card.updateComplete;

      const country = card.shadowRoot?.querySelector('.place-country');
      expect(country).not.toBeNull();
      expect(country?.textContent).toBe('Germany');
      card.remove();
    });

    it('does not render country name when show_country is false', async () => {
      const card = await setupCard({ show_country: false });
      const oldState = card.hass.states['sensor.sea_temp_sensor'];
      const hass = {
        ...card.hass,
        states: {
          ...card.hass.states,
          'sensor.sea_temp_sensor': {
            ...oldState,
            attributes: {
              ...oldState.attributes,
              country: 'Germany',
            },
          },
        },
      };
      card.hass = hass as unknown as HomeAssistant;
      await card.updateComplete;

      const country = card.shadowRoot?.querySelector('.place-country');
      expect(country).toBeNull();
      card.remove();
    });
  });

  describe('Data Sorting', () => {
    const setupSortingTest = async (sortBy: string) => {
      const card = new SeaTemperaturesCard();
      const config: SeaTemperaturesCardConfig = {
        type: 'custom:sea-temperatures-card',
        places: [{ device: 'device-1' }, { device: 'device-2' }, { device: 'device-3' }],
        sort_by: sortBy as SeaTemperaturesCardConfig['sort_by'],
      };

      const hass = {
        states: {
          'sensor.a_temp': {
            entity_id: 'sensor.a_temp',
            state: '25.0',
            attributes: { friendly_name: 'Zebra Beach' },
          },
          'sensor.b_temp': {
            entity_id: 'sensor.b_temp',
            state: '15.0',
            attributes: { friendly_name: 'Apple Beach' },
          },
          'sensor.c_temp': {
            entity_id: 'sensor.c_temp',
            state: '20.0',
            attributes: { friendly_name: 'Middle Beach' },
          },
        },
        entities: {
          'sensor.a_temp': { device_id: 'device-1' },
          'sensor.b_temp': { device_id: 'device-2' },
          'sensor.c_temp': { device_id: 'device-3' },
        },
        devices: {
          'device-1': { id: 'device-1', name: 'Zebra Beach' },
          'device-2': { id: 'device-2', name: 'Apple Beach' },
          'device-3': { id: 'device-3', name: 'Middle Beach' },
        },
        localize: (key: string) => key,
      } as unknown as HomeAssistant;

      card.setConfig(config);
      const data = (
        card as unknown as {
          _getPlacesData: (h: HomeAssistant, c: SeaTemperaturesCardConfig) => { name: string; temperature: string }[];
        }
      )._getPlacesData(hass, config);
      return data;
    };

    it('sorts places by name', async () => {
      const data = await setupSortingTest('name');
      expect(data[0].name).toBe('Apple Beach');
      expect(data[1].name).toBe('Middle Beach');
      expect(data[2].name).toBe('Zebra Beach');
    });

    it('sorts places by temperature ascending', async () => {
      const data = await setupSortingTest('temp_asc');
      expect(data[0].temperature).toBe('15.0');
      expect(data[1].temperature).toBe('20.0');
      expect(data[2].temperature).toBe('25.0');
    });

    it('sorts places by temperature descending', async () => {
      const data = await setupSortingTest('temp_desc');
      expect(data[0].temperature).toBe('25.0');
      expect(data[1].temperature).toBe('20.0');
      expect(data[2].temperature).toBe('15.0');
    });
  });

  describe('Chart Label Parsing', () => {
    const parse = (label: string, now: Date) =>
      (
        new SeaTemperaturesCard() as unknown as {
          _parseChartLabel: (l: string, n: Date) => Date | undefined;
        }
      )._parseChartLabel(label, now);

    it('parses ISO labels with an explicit year', () => {
      const date = parse('2025-12-28', new Date(2026, 0, 5));
      expect(date?.getFullYear()).toBe(2025);
      expect(date?.getMonth()).toBe(11);
      expect(date?.getDate()).toBe(28);
    });

    it('rolls legacy MM-DD labels back across the new year', () => {
      // On 5 Jan 2026, a "12-28" label is December 2025, not December 2026.
      const date = parse('12-28', new Date(2026, 0, 5));
      expect(date?.getFullYear()).toBe(2025);
      expect(date?.getMonth()).toBe(11);
    });

    it('keeps legacy MM-DD labels in the current year when not in the future', () => {
      const date = parse('03-12', new Date(2026, 4, 1));
      expect(date?.getFullYear()).toBe(2026);
      expect(date?.getMonth()).toBe(2);
    });

    it('rejects unparseable labels', () => {
      expect(parse('not-a-date', new Date(2026, 4, 1))).toBeUndefined();
      expect(parse('2026', new Date(2026, 4, 1))).toBeUndefined();
    });
  });

  describe('Chart Refresh', () => {
    const stateWithLabels = (labels: string[], series: number[]) => ({
      entity_id: 'sensor.sea_temp_sensor',
      state: '21.0',
      last_updated: '2026-03-15T12:00:00.000Z',
      attributes: {
        unit_of_measurement: '°C',
        charts: { last_thirty: { labels, series } },
      },
    });

    const hassWith = (state: unknown) =>
      ({
        states: { 'sensor.sea_temp_sensor': state },
        entities: { 'sensor.sea_temp_sensor': { device_id: 'device-1' } },
        devices: { 'device-1': { id: 'device-1', name: 'Test Device' } },
        localize: (key: string) => key,
      }) as unknown as HomeAssistant;

    it('recomputes the series when the charts attribute changes', async () => {
      const card = new SeaTemperaturesCard();
      card.setConfig({
        type: 'custom:sea-temperatures-card',
        places: [{ device: 'device-1' }],
      } as unknown as SeaTemperaturesCardConfig);

      card.hass = hassWith(stateWithLabels(['2026-03-12', '2026-03-13'], [20.5, 21.0]));
      document.body.appendChild(card);
      await card.updateComplete;

      const harness = card as unknown as CardTestHarness;
      expect(harness._chartData['sensor.sea_temp_sensor'].length).toBe(2);

      // A coordinator refresh replaces the state (and the charts object).
      card.hass = hassWith(stateWithLabels(['2026-03-12', '2026-03-13', '2026-03-14'], [20.5, 21.0, 21.5]));
      await card.updateComplete;

      const points = harness._chartData['sensor.sea_temp_sensor'];
      expect(points.length).toBe(3);
      expect(points[2].value).toBe(21.5);

      card.remove();
    });

    it('builds the series for a place added after first render', async () => {
      const card = new SeaTemperaturesCard();
      card.setConfig({
        type: 'custom:sea-temperatures-card',
        places: [{ device: 'device-1' }],
      } as unknown as SeaTemperaturesCardConfig);

      const second = {
        entity_id: 'sensor.second_sensor',
        state: '18.0',
        last_updated: '2026-03-15T12:00:00.000Z',
        attributes: {
          unit_of_measurement: '°C',
          charts: { last_thirty: { labels: ['2026-03-12', '2026-03-13'], series: [17.5, 18.0] } },
        },
      };

      card.hass = {
        states: {
          'sensor.sea_temp_sensor': stateWithLabels(['2026-03-12', '2026-03-13'], [20.5, 21.0]),
          'sensor.second_sensor': second,
        },
        entities: {
          'sensor.sea_temp_sensor': { device_id: 'device-1' },
          'sensor.second_sensor': { device_id: 'device-2' },
        },
        devices: {
          'device-1': { id: 'device-1', name: 'Test Device' },
          'device-2': { id: 'device-2', name: 'Second Device' },
        },
        localize: (key: string) => key,
      } as unknown as HomeAssistant;

      document.body.appendChild(card);
      await card.updateComplete;

      const harness = card as unknown as CardTestHarness;
      expect(harness._chartData['sensor.sea_temp_sensor']?.length).toBe(2);
      expect(harness._chartData['sensor.second_sensor']).toBeUndefined();

      // Adding a place must not require a page reload to get its chart.
      (card as unknown as { _config: SeaTemperaturesCardConfig })._config = {
        type: 'custom:sea-temperatures-card',
        places: [{ device: 'device-1' }, { device: 'device-2' }],
      } as unknown as SeaTemperaturesCardConfig;
      card.requestUpdate('_config');
      await card.updateComplete;

      expect(harness._chartData['sensor.second_sensor']?.length).toBe(2);
      card.remove();
    });
  });

  describe('Unavailable Places', () => {
    const setupUnavailable = async (state: string) => {
      const card = new SeaTemperaturesCard();
      card.setConfig({
        type: 'custom:sea-temperatures-card',
        places: [{ device: 'device-1' }],
      } as unknown as SeaTemperaturesCardConfig);

      card.hass = {
        states: {
          'sensor.sea_temp_sensor': {
            entity_id: 'sensor.sea_temp_sensor',
            state,
            last_updated: '2026-03-15T12:00:00.000Z',
            attributes: { unit_of_measurement: '°C', yesterday: '20.5' },
          },
        },
        entities: { 'sensor.sea_temp_sensor': { device_id: 'device-1' } },
        devices: { 'device-1': { id: 'device-1', name: 'Test Device' } },
        localize: (key: string) => key,
      } as unknown as HomeAssistant;

      document.body.appendChild(card);
      await card.updateComplete;
      return card;
    };

    it('renders a placeholder instead of the raw state text', async () => {
      const card = await setupUnavailable('unavailable');
      const value = card.shadowRoot?.querySelector('.temp-value');
      expect(value?.classList.contains('unavailable')).toBe(true);
      expect(value?.textContent?.trim()).not.toContain('unavailable');
      // No misleading trend delta against a missing reading.
      expect(card.shadowRoot?.querySelector('.current-trend')).toBeNull();
      card.remove();
    });

    it('treats unknown the same way', async () => {
      const card = await setupUnavailable('unknown');
      expect(card.shadowRoot?.querySelector('.temp-value.unavailable')).not.toBeNull();
      card.remove();
    });

    it('sorts unavailable places last regardless of direction', async () => {
      const card = new SeaTemperaturesCard();
      const config = {
        type: 'custom:sea-temperatures-card',
        places: [{ device: 'device-1' }, { device: 'device-2' }],
        sort_by: 'temp_asc',
      } as unknown as SeaTemperaturesCardConfig;

      const hass = {
        states: {
          'sensor.dead': { entity_id: 'sensor.dead', state: 'unavailable', attributes: {} },
          'sensor.alive': { entity_id: 'sensor.alive', state: '15.0', attributes: {} },
        },
        entities: {
          'sensor.dead': { device_id: 'device-1' },
          'sensor.alive': { device_id: 'device-2' },
        },
        devices: {
          'device-1': { id: 'device-1', name: 'Dead' },
          'device-2': { id: 'device-2', name: 'Alive' },
        },
        localize: (key: string) => key,
      } as unknown as HomeAssistant;

      card.setConfig(config);
      const data = (
        card as unknown as {
          _getPlacesData: (h: HomeAssistant, c: SeaTemperaturesCardConfig) => { name: string }[];
        }
      )._getPlacesData(hass, config);
      expect(data[0].name).toBe('Alive');
      expect(data[1].name).toBe('Dead');
      card.remove();
    });
  });

  describe('Accessibility', () => {
    it('exposes the place row as a keyboard-operable button', async () => {
      const card = new SeaTemperaturesCard();
      card.setConfig({
        type: 'custom:sea-temperatures-card',
        places: [{ device: 'device-1' }],
      } as unknown as SeaTemperaturesCardConfig);

      card.hass = {
        states: {
          'sensor.sea_temp_sensor': {
            entity_id: 'sensor.sea_temp_sensor',
            state: '21.0',
            last_updated: '2026-03-15T12:00:00.000Z',
            attributes: { unit_of_measurement: '°C' },
          },
        },
        entities: { 'sensor.sea_temp_sensor': { device_id: 'device-1' } },
        devices: { 'device-1': { id: 'device-1', name: 'Test Device' } },
        localize: (key: string) => key,
      } as unknown as HomeAssistant;

      document.body.appendChild(card);
      await card.updateComplete;

      const header = card.shadowRoot?.querySelector('.place-header') as HTMLElement;
      expect(header.getAttribute('role')).toBe('button');
      expect(header.getAttribute('tabindex')).toBe('0');
      expect(header.getAttribute('aria-label')).toContain('Test Device');

      let fired = 0;
      card.addEventListener('hass-more-info', () => fired++);
      header.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      header.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
      header.dispatchEvent(new KeyboardEvent('keydown', { key: 'a', bubbles: true }));
      expect(fired).toBe(2);

      card.remove();
    });
  });
});
