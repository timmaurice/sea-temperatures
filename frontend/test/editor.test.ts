import { describe, it, expect } from 'vitest';
import { SeaTemperaturesCardEditor } from '../src/editor';
import { SeaTemperaturesCardConfig, HomeAssistant } from '../src/types';

describe('SeaTemperaturesCardEditor', () => {
  const setupEditor = async (configOptions: Partial<SeaTemperaturesCardConfig> = {}) => {
    const editor = new SeaTemperaturesCardEditor();

    const config: SeaTemperaturesCardConfig = {
      type: 'custom:sea-temperatures-card',
      places: [{ device: 'device-1' }],
      ...configOptions,
    };

    const hass = {
      localize: (key: string) => key,
    } as unknown as HomeAssistant;

    editor.setConfig(config);
    editor.hass = hass;

    document.body.appendChild(editor);
    await editor.updateComplete;

    return editor;
  };

  describe('Initialization', () => {
    it('is defined', () => {
      expect(customElements.get('sea-temperatures-card-editor')).toBeDefined();
    });

    it('sizes the add button with the current token', async () => {
      const editor = await setupEditor();

      // "medium" is a legacy alias the design system only maps to a font size:
      // it leaves the button at its default height. The token is "m".
      expect(editor.shadowRoot?.querySelector('ha-button')?.getAttribute('size')).toBe('m');

      editor.remove();
    });

    it('renders the places list and title correctly', async () => {
      const editor = await setupEditor();

      const haForms = editor.shadowRoot?.querySelectorAll('ha-form');
      expect(haForms?.length).toBe(2); // Top schema (title) and bottom schema

      const placesList = editor.shadowRoot?.querySelector('.places-list');
      expect(placesList).not.toBeNull();

      const placeItems = editor.shadowRoot?.querySelectorAll('.place-item');
      expect(placeItems?.length).toBe(1);

      editor.remove();
    });
  });

  describe('Place Management', () => {
    it('opens an empty place row without writing it to the config', async () => {
      const editor = await setupEditor();

      const addButton = editor.shadowRoot?.querySelector('ha-button') as HTMLElement | null;
      expect(addButton).not.toBeNull();

      const editorAny = editor as unknown as { _config: SeaTemperaturesCardConfig };
      expect(editorAny._config.places.length).toBe(1);

      const emitted: SeaTemperaturesCardConfig[] = [];
      editor.addEventListener('config-changed', (e) =>
        emitted.push((e as CustomEvent<{ config: SeaTemperaturesCardConfig }>).detail.config),
      );

      addButton?.click();
      await editor.updateComplete;

      // The row is on screen so the user can pick a place...
      expect(editor.shadowRoot?.querySelectorAll('.place-item').length).toBe(2);
      // ...but a place with no target is not configuration.
      expect(editorAny._config.places.length).toBe(1);
      expect(emitted.some((config) => config.places.some((place) => place === ''))).toBe(false);

      editor.remove();
    });

    it('drops the draft row once it has a target', async () => {
      const editor = await setupEditor();
      const editorAny = editor as unknown as {
        _config: SeaTemperaturesCardConfig;
        _addPlace: () => void;
        _placeChanged: (i: number, v: unknown) => void;
      };

      editorAny._addPlace();
      editorAny._placeChanged(1, 'sensor.second_beach');
      await editor.updateComplete;

      expect(editorAny._config.places).toEqual([{ device: 'device-1' }, 'sensor.second_beach']);
      expect(editor.shadowRoot?.querySelectorAll('.place-item').length).toBe(2);

      editor.remove();
    });

    it('never saves a key that is already the default', async () => {
      const editor = await setupEditor({ show_chart: false, title: '' });
      const editorAny = editor as unknown as { _valueChanged: (e: CustomEvent) => void };

      let saved: SeaTemperaturesCardConfig | undefined;
      editor.addEventListener('config-changed', (e) => {
        saved = (e as CustomEvent<{ config: SeaTemperaturesCardConfig }>).detail.config;
      });

      editorAny._valueChanged(new CustomEvent('value-changed', { detail: { value: { sort_by: 'name' } } }));

      // Only what the user actually chose, plus the keys the card needs.
      expect(saved).toEqual({
        type: 'custom:sea-temperatures-card',
        places: [{ device: 'device-1' }],
        show_chart: false,
        sort_by: 'name',
      });

      editor.remove();
    });

    it('keeps a custom name when the target selector reports a change', async () => {
      const editor = await setupEditor({ places: [{ device: 'device-1', name: 'My Local Beach' }] });
      const editorAny = editor as unknown as {
        _config: SeaTemperaturesCardConfig;
        _placeChanged: (i: number, v: unknown) => void;
      };

      // ha-selector only ever emits a bare target; the name must survive it.
      editorAny._placeChanged(0, 'device-2');

      expect(editorAny._config.places[0]).toEqual({ device: 'device-2', name: 'My Local Beach' });
      editor.remove();
    });

    it('rejects a duplicate target without touching the config', async () => {
      const editor = await setupEditor({ places: ['device-1', 'device-2'] });
      const editorAny = editor as unknown as {
        _config: SeaTemperaturesCardConfig;
        _placeChanged: (i: number, v: unknown) => void;
      };

      editorAny._placeChanged(1, 'device-1');

      expect(editorAny._config.places).toEqual(['device-1', 'device-2']);
      editor.remove();
    });

    it('renders an entity selector for an entity-based place', async () => {
      const editor = await setupEditor({ places: ['sensor.acharavi_sea_temperature'] });

      const selector = editor.shadowRoot?.querySelector('ha-selector') as HTMLElement & {
        selector?: Record<string, unknown>;
        value?: string;
      };
      expect(selector?.selector?.entity).toBeDefined();
      expect(selector?.selector?.device).toBeUndefined();
      expect(selector?.value).toBe('sensor.acharavi_sea_temperature');

      editor.remove();
    });

    it('renders a device selector for a device-based place', async () => {
      const editor = await setupEditor({ places: [{ device: 'device-1' }] });

      const selector = editor.shadowRoot?.querySelector('ha-selector') as HTMLElement & {
        selector?: Record<string, unknown>;
      };
      expect(selector?.selector?.device).toBeDefined();
      expect(selector?.selector?.entity).toBeUndefined();

      editor.remove();
    });

    it('removes a place when the target is cleared', async () => {
      const editor = await setupEditor({ places: ['device-1', 'device-2'] });
      const editorAny = editor as unknown as {
        _config: SeaTemperaturesCardConfig;
        _placeChanged: (i: number, v: unknown) => void;
      };

      editorAny._placeChanged(0, undefined);

      expect(editorAny._config.places).toEqual(['device-2']);
      editor.remove();
    });
  });
});
