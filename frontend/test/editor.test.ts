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
    it('adds a new place when add button is clicked', async () => {
      const editor = await setupEditor();

      const addButton = editor.shadowRoot?.querySelector('ha-button') as HTMLElement | null;
      expect(addButton).not.toBeNull();

      // Spy on the private config
      const editorAny = editor as unknown as { _config: SeaTemperaturesCardConfig };
      expect(editorAny._config.places.length).toBe(1);

      // Click add place
      addButton?.click();
      await editor.updateComplete;

      expect(editorAny._config.places.length).toBe(2);
      expect(editorAny._config.places[1]).toBe('');

      editor.remove();
    });
  });
});
