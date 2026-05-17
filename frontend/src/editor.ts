import { LitElement, html, css, TemplateResult, unsafeCSS } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { HomeAssistant, LovelaceCardEditor, SeaTemperaturesCardConfig } from './types.js';
import { localize } from './localize.js';
import { fireEvent } from './utils.js';
import editorStyles from './styles/editor.styles.scss';

const SCHEMA = [
  { name: 'title', selector: { text: {} } },
  {
    name: 'places',
    selector: { device: { multiple: true, integration: 'seatemperatures' } },
  },
  {
    type: 'expandable',
    title: 'groups.display',
    schema: [
      { name: 'show_last_updated', selector: { boolean: {} } },
      { name: 'show_trend', selector: { boolean: {} } },
      { name: 'show_stats', selector: { boolean: {} } },
      { name: 'show_chart', selector: { boolean: {} } },
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
      show_trend: true,
      show_last_updated: true,
      show_stats: true,
      show_chart: true,
      chart_smoothing: 'smooth',
      ...config,
    };
  }

  private _valueChanged(ev: CustomEvent): void {
    if (!this.hass || !this._config) return;
    fireEvent(this, 'config-changed', { config: { ...this._config, ...ev.detail.value } });
  }

  protected render(): TemplateResult {
    if (!this.hass || !this._config) {
      return html``;
    }

    const computeSchema = (items: Record<string, unknown>[]): Record<string, unknown>[] => {
      return items.map((item) => {
        const newItem = { ...item };
        if (newItem.type === 'expandable' && Array.isArray(newItem.schema)) {
          newItem.title = localize(this.hass, `editor.${newItem.title}`);
          newItem.schema = newItem.schema.map((n: Record<string, unknown>) => ({ ...n }));
        }
        return newItem;
      });
    };

    const schema = computeSchema(SCHEMA);

    return html`
      <ha-card>
        <div class="card-content card-config">
          <ha-form
            .schema=${schema}
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
