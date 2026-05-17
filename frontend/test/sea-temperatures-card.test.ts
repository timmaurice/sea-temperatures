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
      ).toThrow("Please define 'places'");
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
                  labels: ['03-12', '03-13'],
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
                  labels: ['03-12'],
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
              last_year: '18.0',
              charts: {
                last_thirty: {
                  labels: ['03-12', '03-13'],
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

      // Manually inject history state since fetchHistory is async and potentially mocked
      (cardEnabled as unknown as CardTestHarness)._historyState = { 'sensor.sea_temp_sensor': '20.0' }; // current is 21.0, so trending up
      await cardEnabled.updateComplete;

      expect(cardEnabled.shadowRoot?.querySelector('.trend-icon')).not.toBeNull();
      expect(cardEnabled.shadowRoot?.querySelector('.trend-icon.up')).not.toBeNull();
      cardEnabled.remove();

      const cardDisabled = await setupCard({ show_trend: false });
      (cardDisabled as unknown as CardTestHarness)._historyState = { 'sensor.sea_temp_sensor': '20.0' };
      await cardDisabled.updateComplete;

      expect(cardDisabled.shadowRoot?.querySelector('.trend-icon')).toBeNull();
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
  });
});
