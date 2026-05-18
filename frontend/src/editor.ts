import { LitElement, html, css, TemplateResult, unsafeCSS } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { HomeAssistant, LovelaceCardEditor, SeaTemperaturesCardConfig, PlaceConfig } from './types.js';
import { localize } from './localize.js';
import { fireEvent } from './utils.js';
import editorStyles from './styles/editor.styles.scss';

const SCHEMA_TOP = [{ name: 'title', selector: { text: {} } }];

const SCHEMA_BOTTOM = [
  {
    name: 'sort_by',
    selector: {
      select: {
        options: [
          { value: 'default', label: 'Default' },
          { value: 'name', label: 'Name' },
          { value: 'temp_asc', label: 'Temperature Asc' },
          { value: 'temp_desc', label: 'Temperature Desc' },
        ],
      },
    },
  },
  {
    type: 'expandable',
    title: 'groups.display',
    schema: [
      { name: 'show_last_updated', selector: { boolean: {} } },
      { name: 'show_trend', selector: { boolean: {} } },
      { name: 'show_stats', selector: { boolean: {} } },
      { name: 'show_chart', selector: { boolean: {} } },
      { name: 'show_country', selector: { boolean: {} } },
      { name: 'chart_smoothing', selector: { select: { options: ['smooth', 'linear', 'step'] } } },
    ],
  },
];

@customElement('sea-temperatures-card-editor')
export class SeaTemperaturesCardEditor extends LitElement implements LovelaceCardEditor {
  @property({ attribute: false }) public hass!: HomeAssistant;
  @state() private _config!: SeaTemperaturesCardConfig;

  public setConfig(config: SeaTemperaturesCardConfig): void {
    this._config = {
      sort_by: 'default',
      show_trend: true,
      show_last_updated: true,
      show_stats: true,
      show_chart: true,
      show_country: false,
      chart_smoothing: 'smooth',
      ...config,
    };
  }

  private _valueChanged(ev: CustomEvent): void {
    if (!this.hass || !this._config) return;
    fireEvent(this, 'config-changed', { config: { ...this._config, ...ev.detail.value } });
  }

  private _placeMoved(ev: CustomEvent): void {
    ev.stopPropagation();
    const { oldIndex, newIndex } = ev.detail;
    if (oldIndex === newIndex) return;

    const places = [...(this._config.places || [])];
    const moved = places.splice(oldIndex, 1)[0];
    places.splice(newIndex, 0, moved);

    this._config = { ...this._config, places };
    fireEvent(this, 'config-changed', { config: this._config });
  }

  private _placeChanged(index: number, value: PlaceConfig | undefined): void {
    if (!value) {
      this._removePlace(index);
      return;
    }

    const places = [...(this._config.places || [])];
    const target = typeof value === 'string' ? value : value.device;

    const isDuplicate = places.some((place, i) => {
      if (i === index || !place) return false;
      const placeTarget = typeof place === 'string' ? place : place.device;
      return placeTarget === target;
    });

    if (isDuplicate) {
      fireEvent(this, 'hass-notification', { message: localize(this.hass, 'common.errors.duplicate_place') });
      this.requestUpdate();
      return;
    }

    places[index] = value;
    this._config = { ...this._config, places };
    fireEvent(this, 'config-changed', { config: this._config });
  }

  private _removePlace(index: number): void {
    const places = [...(this._config.places || [])];
    places.splice(index, 1);
    this._config = { ...this._config, places };
    fireEvent(this, 'config-changed', { config: this._config });
  }

  private _addPlace(): void {
    const places = [...(this._config.places || []), ''];
    this._config = { ...this._config, places };
    fireEvent(this, 'config-changed', { config: this._config });
  }

  protected render(): TemplateResult {
    if (!this.hass || !this._config) {
      return html``;
    }

    const computeSchema = (items: Record<string, unknown>[]): Record<string, unknown>[] => {
      return items.map((item) => {
        const newItem = { ...item };
        if (newItem.name === 'sort_by') {
          newItem.selector = {
            select: {
              options: [
                { value: 'default', label: localize(this.hass, 'editor.sort_by_options.default') },
                { value: 'name', label: localize(this.hass, 'editor.sort_by_options.name') },
                { value: 'temp_asc', label: localize(this.hass, 'editor.sort_by_options.temp_asc') },
                { value: 'temp_desc', label: localize(this.hass, 'editor.sort_by_options.temp_desc') },
              ],
            },
          };
        }
        if (newItem.name === 'chart_smoothing') {
          newItem.selector = {
            select: {
              options: [
                { value: 'smooth', label: localize(this.hass, 'editor.chart_smoothing_options.smooth') },
                { value: 'linear', label: localize(this.hass, 'editor.chart_smoothing_options.linear') },
                { value: 'step', label: localize(this.hass, 'editor.chart_smoothing_options.step') },
              ],
            },
          };
        }
        if (newItem.type === 'expandable' && Array.isArray(newItem.schema)) {
          newItem.title = localize(this.hass, `editor.${newItem.title}`);
          newItem.schema = newItem.schema.map((n: Record<string, unknown>) => ({ ...n }));
        }
        return newItem;
      });
    };

    const schemaTop = computeSchema(SCHEMA_TOP);
    const schemaBottom = computeSchema(SCHEMA_BOTTOM);

    return html`
      <ha-card>
        <div class="card-content card-config">
          <ha-form
            .schema=${schemaTop}
            .hass=${this.hass}
            .data=${this._config}
            .computeLabel=${(s: { name: string }) => localize(this.hass, `editor.${s.name}`)}
            @value-changed=${this._valueChanged}
          ></ha-form>
          <div class="places-list">
            <div class="places-header">
              <h3>${localize(this.hass, 'editor.places')}</h3>
            </div>
            <ha-sortable handle-selector=".handle" @item-moved=${this._placeMoved}>
              <div class="places">
                ${this._config.places?.map(
                  (place, index) => html`
                    <div class="place-item">
                      <div class="handle">
                        <ha-icon icon="mdi:drag"></ha-icon>
                      </div>
                      <ha-selector
                        .hass=${this.hass}
                        .selector=${{ device: { integration: 'seatemperatures' } }}
                        .value=${typeof place === 'string' ? place : place.device}
                        @value-changed=${(e: CustomEvent) => this._placeChanged(index, e.detail.value)}
                      ></ha-selector>
                    </div>
                  `,
                )}
              </div>
            </ha-sortable>
            <div class="add-place-container">
              <ha-button @click=${this._addPlace} variant="brand" appearance="accent" size="medium">
                <ha-icon icon="mdi:plus"></ha-icon>
                ${localize(this.hass, 'editor.add_place')}
              </ha-button>
            </div>
          </div>
          <ha-form
            .schema=${schemaBottom}
            .hass=${this.hass}
            .data=${this._config}
            .computeLabel=${(s: { name: string }) => localize(this.hass, `editor.${s.name}`)}
            @value-changed=${this._valueChanged}
          ></ha-form>
        </div>
      </ha-card>
    `;
  }

  static styles = css`
    ${unsafeCSS(editorStyles)}
  `;
}
