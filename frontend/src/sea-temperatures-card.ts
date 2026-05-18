import { LitElement, TemplateResult, html, svg, unsafeCSS } from 'lit';
import { property, state, query } from 'lit/decorators.js';
import { HomeAssistant, LovelaceCard, LovelaceCardEditor, PlaceConfig, SeaTemperaturesCardConfig } from './types.js';
import { localize } from './localize.js';
import { fireEvent } from './utils.js';
import { scaleTime, scaleLinear, line, area, curveMonotoneX, curveLinear, curveStepAfter, extent, bisector } from 'd3';
import styles from './styles/card.styles.scss';

const ELEMENT_NAME = 'sea-temperatures-card';
const EDITOR_ELEMENT_NAME = `${ELEMENT_NAME}-editor`;

interface SeaTemperatureData {
  name: string;
  country?: string;
  temperature: string;
  yesterday?: string;
  last_week?: string;
  last_year?: string;
  date?: string;
  average_min?: string;
  average_max?: string;
  average_avg?: string;
  unit?: string;
  entity_id: string;
}

interface HistoryPoint {
  date: Date;
  value: number;
}

declare global {
  interface Window {
    customCards?: {
      type: string;
      name: string;
      description: string;
      documentationURL: string;
      preview?: boolean;
    }[];
    loadCardHelpers(): Promise<void>;
  }

  interface CustomCard {
    type: string;
    name: string;
    description: string;
    documentationURL: string;
    preview?: boolean;
  }
}

export class SeaTemperaturesCard extends LitElement implements LovelaceCard {
  @property({ attribute: false }) public hass!: HomeAssistant;
  @query('ha-card') private _card!: LovelaceCard;
  @state() private _config!: SeaTemperaturesCardConfig;
  @state() private _chartData: Record<string, HistoryPoint[]> = {}; // entity_id -> history points
  @state() private _chartWidth = 400;
  private _resizeObserver?: ResizeObserver;
  private _dataFetched = false;

  public setConfig(config: SeaTemperaturesCardConfig): void {
    if (!config || !config.places || !Array.isArray(config.places) || config.places.length === 0) {
      throw new Error("Please define 'places'");
    }
    this._config = {
      show_last_updated: true,
      show_trend: true,
      show_stats: true,
      show_chart: true,
      show_country: false,
      compact: false,
      chart_smoothing: 'smooth',
      ...config,
    };
    // Fetching will happen in updated() when hass is available
  }

  public connectedCallback(): void {
    super.connectedCallback();
    this._resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) {
          const newWidth = Math.max(200, entry.contentRect.width - 32); // 32px is the card padding
          if (this._chartWidth !== newWidth) {
            this._chartWidth = newWidth;
          }
        }
      }
    });
    this._resizeObserver.observe(this);
  }

  public disconnectedCallback(): void {
    super.disconnectedCallback();
    this._resizeObserver?.disconnect();
  }

  public static async getConfigElement(): Promise<LovelaceCardEditor> {
    await import('./editor.js');
    return document.createElement(EDITOR_ELEMENT_NAME) as LovelaceCardEditor;
  }

  public static getStubConfig(): Record<string, unknown> {
    return {
      title: 'Sea Temperatures',
      places: [],
    };
  }

  public getCardSize(): number {
    return this._config?.places?.length || 1;
  }

  private _getPlacesData(hass: HomeAssistant, config: SeaTemperaturesCardConfig): SeaTemperatureData[] {
    const places: SeaTemperatureData[] = [];
    const allEntities = Object.values(hass.states);

    config.places.forEach((place: PlaceConfig) => {
      const target = typeof place === 'string' ? place : place.device;
      const customName = typeof place === 'object' ? place.name : undefined;

      let tempEntity = hass.states[target];
      let deviceId: string | undefined;

      if (tempEntity) {
        // Target is an entity_id
        deviceId = hass.entities[target]?.device_id;
      } else {
        // Target is likely a device_id
        deviceId = target;
        const deviceEntities = allEntities.filter(
          (entity) => hass.entities[entity.entity_id]?.device_id === deviceId && entity.entity_id.startsWith('sensor.'),
        );

        if (deviceEntities.length === 0) return;

        // Find the main temperature sensor:
        // 1. Prioritize entity with 'yesterday' attribute (main sensor)
        // 2. Then by unit of measurement
        // 3. Fallback to first sensor
        tempEntity =
          deviceEntities.find((e) => e.attributes.yesterday !== undefined) ||
          deviceEntities.find(
            (e) => e.attributes.unit_of_measurement === '°C' || e.attributes.unit_of_measurement === '°F',
          ) ||
          deviceEntities[0];
      }

      if (tempEntity) {
        const attr = tempEntity.attributes;
        const device = deviceId ? hass.devices[deviceId] : undefined;
        const baseName = device?.name_by_user || device?.name || attr.friendly_name || 'Unknown';

        places.push({
          name: customName || baseName,
          country: config.show_country && attr.country ? String(attr.country) : undefined,
          temperature: tempEntity.state,
          yesterday: attr.yesterday ? String(attr.yesterday) : undefined,
          last_week: attr.last_week ? String(attr.last_week) : undefined,
          last_year: attr.last_year ? String(attr.last_year) : undefined,
          date: attr.date ? String(attr.date) : undefined,
          average_min: attr.average_min ? String(attr.average_min) : undefined,
          average_max: attr.average_max ? String(attr.average_max) : undefined,
          average_avg: attr.average_avg ? String(attr.average_avg) : undefined,
          unit: attr.unit_of_measurement || '°C',
          entity_id: tempEntity.entity_id,
        });
      }
    });

    if (config.sort_by) {
      places.sort((a, b) => {
        if (config.sort_by === 'name') {
          return a.name.localeCompare(b.name);
        }
        if (config.sort_by === 'temp_asc' || config.sort_by === 'temp_desc') {
          const tempA = parseFloat(a.temperature);
          const tempB = parseFloat(b.temperature);
          const valA = isNaN(tempA) ? -Infinity : tempA;
          const valB = isNaN(tempB) ? -Infinity : tempB;

          if (config.sort_by === 'temp_asc') {
            return valA - valB;
          } else {
            return valB - valA;
          }
        }
        return 0; // 'default'
      });
    }

    return places;
  }

  protected updated(changedProperties: Map<string | number | symbol, unknown>): void {
    super.updated(changedProperties);

    // We can only fetch history once we have both _config and hass
    if (this.hass && this._config && !this._dataFetched) {
      this._dataFetched = true;
      this._fetchChartData();
    }
  }

  protected shouldUpdate(changedProperties: Map<string | number | symbol, unknown>): boolean {
    if (changedProperties.has('_config')) return true;
    const oldHass = changedProperties.get('hass') as HomeAssistant | undefined;
    if (oldHass) {
      const places = this._getPlacesData(this.hass, this._config);
      const hasChanged = places.some((p) => oldHass.states[p.entity_id] !== this.hass.states[p.entity_id]);
      return (
        hasChanged ||
        oldHass.language !== this.hass.language ||
        changedProperties.has('_chartData') ||
        changedProperties.has('_chartWidth')
      );
    }
    return true;
  }

  private _fetchChartData(): void {
    if (!this.hass || !this._config.places) return;
    const places = this._getPlacesData(this.hass, this._config);
    const entities = places.map((p) => p.entity_id);
    if (entities.length === 0) return;

    const chartData: Record<string, HistoryPoint[]> = {};

    entities.forEach((entityId) => {
      const entity = this.hass?.states[entityId];
      const charts = entity?.attributes?.charts as
        | { last_thirty?: { labels?: string[]; series?: (number | string)[] } }
        | undefined;

      if (charts?.last_thirty?.labels && charts?.last_thirty?.series) {
        const labels = charts.last_thirty.labels as string[];
        const series = charts.last_thirty.series as (number | string)[];

        if (Array.isArray(labels) && Array.isArray(series) && labels.length === series.length) {
          const currentYear = new Date().getFullYear();
          const currentMonth = new Date().getMonth() + 1; // 1-12

          chartData[entityId] = labels
            .map((label, index) => {
              const parts = String(label).split('-');
              if (parts.length !== 2) return { date: new Date(), value: NaN };
              const month = parseInt(parts[0], 10);
              const day = parseInt(parts[1], 10);

              let year = currentYear;
              // If data month is ahead of current month (e.g. data is Dec, current is Jan), assume last year
              if (month > currentMonth + 1) {
                year -= 1;
              }
              // If we are late in the year (e.g., Dec) and we get data for early next year (e.g., Jan), this shouldn't happen for past 30 days, but just in case
              if (currentMonth > 10 && month < 3) {
                year += 1;
              }

              return {
                date: new Date(year, month - 1, day),
                value: parseFloat(String(series[index])),
              };
            })
            .filter((p) => !isNaN(p.value))
            .sort((a, b) => a.date.getTime() - b.date.getTime());
        }
      }
    });

    this._chartData = { ...chartData };
    this.requestUpdate();
  }

  private _handleMoreInfo(entityId: string): void {
    fireEvent(this, 'hass-more-info', { entityId });
  }

  private _renderTrend(yesterday: string | undefined, currentState: string, unit: string = ''): TemplateResult {
    if (!this._config.show_trend) return html``;
    const oldState = yesterday;
    if (oldState === undefined || isNaN(parseFloat(currentState)) || isNaN(parseFloat(oldState))) return html``;

    const currentVal = parseFloat(currentState);
    const oldVal = parseFloat(oldState);

    const delta = currentVal - oldVal;
    const roundedDelta = Math.round(delta * 10) / 10;

    if (Math.abs(roundedDelta) > 0) {
      const isPos = roundedDelta > 0;
      const deltaFormatted = new Intl.NumberFormat(this.hass?.language, {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      }).format(Math.abs(roundedDelta));
      const deltaClass = isPos ? 'pos' : 'neg';
      const deltaIcon = isPos ? '↑' : '↓';
      const deltaSign = isPos ? '+' : '-';
      return html`<div class="stat-delta ${deltaClass} current-trend">
        ${deltaIcon} ${deltaSign}${deltaFormatted}${unit}
      </div>`;
    }
    return html`<div class="stat-delta neu current-trend">→ 0.0${unit}</div>`;
  }

  protected render(): TemplateResult {
    if (!this._config || !this.hass) return html``;

    const places = this._getPlacesData(this.hass, this._config);

    return html`
      <ha-card .header=${this._config.title} tabindex="0">
        <div class="card-content">
          ${places.map(
            (place) => html`
              <div class="place-row">
                <div class="place-header" @click=${() => this._handleMoreInfo(place.entity_id)}>
                  <div class="place-info">
                    <div class="place-name-container">
                      <span class="place-name">${place.name}</span>
                      ${place.country ? html`<span class="place-country">${place.country}</span>` : ''}
                    </div>
                    ${this._config.show_last_updated
                      ? html`<div class="last-updated">
                          ${this.hass.states[place.entity_id]
                            ? new Date(this.hass.states[place.entity_id].last_updated).toLocaleString(
                                this.hass.language || undefined,
                                { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' },
                              )
                            : ''}
                        </div>`
                      : ''}
                  </div>
                  <div class="current-temp">
                    <span class="temp-value"
                      >${!isNaN(Number(place.temperature))
                        ? new Intl.NumberFormat(this.hass?.language).format(Number(place.temperature))
                        : place.temperature}</span
                    >
                    <span class="temp-unit">${place.unit}</span>
                    ${this._renderTrend(place.yesterday, place.temperature, place.unit)}
                  </div>
                </div>

                ${this._config.show_stats !== false
                  ? html`
                      <div class="stats-grid">
                        ${this._renderStat(localize(this.hass, 'card.yesterday'), place.yesterday, place.unit)}
                        ${this._renderStat(localize(this.hass, 'card.last_week'), place.last_week, place.unit)}
                        ${this._renderStat(localize(this.hass, 'card.last_year'), place.last_year, place.unit)}
                      </div>
                    `
                  : ''}
                ${this._config.show_chart !== false ? this._renderChart(place) : ''}
              </div>
            `,
          )}
        </div>
      </ha-card>
    `;
  }

  private _renderStat(label: string, value?: string, unit?: string): TemplateResult {
    if (!value || value === 'unknown' || value === 'unavailable') return html``;
    const numVal = Number(value);
    const formattedVal = !isNaN(numVal) ? new Intl.NumberFormat(this.hass?.language).format(numVal) : value;

    return html`
      <div class="stat-item">
        <span class="stat-label">${label}</span>
        <span class="stat-value">${formattedVal}${unit}</span>
      </div>
    `;
  }

  private _renderChart(place: SeaTemperatureData): TemplateResult {
    const data = this._chartData[place.entity_id];

    if (!data || data.length < 2) {
      return html``;
    }

    return html`
      <div class="chart-container">
        <svg
          viewBox="0 0 ${this._chartWidth} 120"
          preserveAspectRatio="xMidYMid meet"
          id="chart-${place.entity_id.replace(/\./g, '-')}"
        >
          ${this._drawChart(place.entity_id, data, place)}
        </svg>
      </div>
    `;
  }

  private _handleMouseMove(
    e: MouseEvent,
    entityId: string,
    data: HistoryPoint[],
    x: d3.ScaleTime<number, number>,
    y: d3.ScaleLinear<number, number>,
    unit: string,
  ) {
    const svgNode = (e.currentTarget as SVGRectElement).ownerSVGElement;
    if (!svgNode) return;

    const pt = svgNode.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const ctm = svgNode.getScreenCTM();
    if (!ctm) return;

    const svgP = pt.matrixTransform(ctm.inverse());
    const date = x.invert(svgP.x);

    const bisectDate = bisector<HistoryPoint, Date>((d) => d.date).left;
    const index = bisectDate(data, date, 1);
    const d0 = data[index - 1];
    const d1 = data[index];

    let closestPoint = d0;
    if (d0 && d1) {
      closestPoint = date.getTime() - d0.date.getTime() > d1.date.getTime() - date.getTime() ? d1 : d0;
    } else if (d1) {
      closestPoint = d1;
    }

    if (!closestPoint) return;

    const hoverGroup = svgNode.querySelector(`.hover-group`) as SVGGElement | null;
    if (!hoverGroup) return;

    hoverGroup.style.opacity = '1';

    const hx = x(closestPoint.date);
    const hy = y(closestPoint.value);

    const hoverLine = hoverGroup.querySelector('.hover-line') as SVGLineElement;
    hoverLine.setAttribute('x1', String(hx));
    hoverLine.setAttribute('x2', String(hx));

    const hoverPoint = hoverGroup.querySelector('.hover-point') as SVGCircleElement;
    hoverPoint.setAttribute('cx', String(hx));
    hoverPoint.setAttribute('cy', String(hy));

    const bg = hoverGroup.querySelector('.hover-tooltip-bg') as SVGRectElement;
    const textVal = hoverGroup.querySelector('.hover-tooltip-text') as SVGTextElement;
    const textDate = hoverGroup.querySelector('.hover-tooltip-date') as SVGTextElement;

    const width = this._chartWidth;
    const tooltipBgWidth = 70;

    // Bound the background rect within the SVG width
    const tooltipRectX = Math.max(0, Math.min(hx - tooltipBgWidth / 2, width - tooltipBgWidth));

    // The text should always be exactly in the center of the background rect
    const tooltipX = tooltipRectX + tooltipBgWidth / 2;
    const textAnchor = 'middle';

    const tooltipY = Math.max(0, hy - 34);
    const textLine1Y = tooltipY + 11;
    const textLine2Y = tooltipY + 23;

    bg.setAttribute('x', String(tooltipRectX));
    bg.setAttribute('y', String(tooltipY));

    textVal.setAttribute('x', String(tooltipX));
    textVal.setAttribute('y', String(textLine1Y));
    textVal.setAttribute('text-anchor', textAnchor);
    const formattedVal = new Intl.NumberFormat(this.hass?.language).format(closestPoint.value);
    textVal.textContent = `${formattedVal}${unit}`;

    textDate.setAttribute('x', String(tooltipX));
    textDate.setAttribute('y', String(textLine2Y));
    textDate.setAttribute('text-anchor', textAnchor);
    textDate.textContent = closestPoint.date.toLocaleDateString(this.hass?.language || undefined, {
      month: 'short',
      day: 'numeric',
    });
  }

  private _handleMouseLeave(e: MouseEvent) {
    const svgNode = (e.currentTarget as SVGRectElement).ownerSVGElement;
    if (!svgNode) return;
    const hoverGroup = svgNode.querySelector(`.hover-group`) as SVGGElement | null;
    if (hoverGroup) {
      hoverGroup.style.opacity = '0';
    }
  }

  private _drawChart(entityId: string, data: HistoryPoint[], place: SeaTemperatureData): TemplateResult {
    const width = this._chartWidth;
    const height = 120;
    const margin = { top: 15, right: 65, bottom: 25, left: 10 };

    const x = scaleTime()
      .domain(extent(data, (d) => d.date) as [Date, Date])
      .range([margin.left, width - margin.right]);

    const allValues = [...data.map((d) => d.value)];
    if (place.average_min) allValues.push(parseFloat(place.average_min));
    if (place.average_max) allValues.push(parseFloat(place.average_max));
    const finalYExtent = extent(allValues) as [number, number];
    const padding = (finalYExtent[1] - finalYExtent[0]) * 0.1 || 1;

    const y = scaleLinear()
      .domain([finalYExtent[0] - padding, finalYExtent[1] + padding])
      .range([height - margin.bottom, margin.top]);

    let curveType = curveMonotoneX;
    if (this._config.chart_smoothing === 'linear') curveType = curveLinear;
    if (this._config.chart_smoothing === 'step') curveType = curveStepAfter;

    const lineGen = line<HistoryPoint>()
      .x((d) => x(d.date))
      .y((d) => y(d.value))
      .curve(curveType);

    const areaGen = area<HistoryPoint>()
      .x((d) => x(d.date))
      .y0(height - margin.bottom)
      .y1((d) => y(d.value))
      .curve(curveType);

    const renderRefLine = (val?: string, className?: string, label?: string) => {
      if (!val) return null;
      const v = parseFloat(val);
      if (isNaN(v)) return null;
      const yPos = y(v);
      const unitStr = place.unit || '°C';
      const displayText = label ? `${label} ${v.toFixed(1)}${unitStr}` : '';
      return svg`
        <line
          class="ref-line ${className}"
          x1="${margin.left}"
          x2="${width - margin.right}"
          y1="${yPos}"
          y2="${yPos}"
        ></line>
        ${displayText ? svg`<text class="ref-label ${className}" x="${width - margin.right + 4}" y="${yPos}" text-anchor="start">${displayText}</text>` : ''}
      `;
    };

    const formatDate = (d: Date) =>
      d.toLocaleDateString(this.hass?.language || undefined, { month: 'short', day: 'numeric' });
    const startDate = x.domain()[0];
    const endDate = x.domain()[1];

    // Now Dot
    const lastPoint = data[data.length - 1];
    const nowDot = lastPoint
      ? svg`
      <circle
        class="now-dot"
        cx="${x(lastPoint.date)}"
        cy="${y(lastPoint.value)}"
        r="3"
        fill="var(--primary-color, #0077be)"
      ></circle>
    `
      : '';

    // Extrema points
    const minPoint = data.reduce((min, p) => (p.value < min.value ? p : min), data[0]);
    const maxPoint = data.reduce((max, p) => (p.value > max.value ? p : max), data[0]);

    const unitStr = place.unit || '°C';

    const hoverElements = svg`
      <g class="hover-group" style="opacity: 0;">
        <line class="hover-line" x1="0" x2="0" y1="${margin.top}" y2="${height - margin.bottom}"></line>
        <circle class="hover-point" cx="0" cy="0" r="4"></circle>
        <rect class="hover-tooltip-bg" x="0" y="0" width="70" height="28" rx="4"></rect>
        <text class="hover-tooltip-text" x="0" y="0" text-anchor="middle"></text>
        <text class="hover-tooltip-date" x="0" y="0" text-anchor="middle"></text>
      </g>
    `;

    return svg`
      <defs>
        <linearGradient id="gradient-${entityId.replace(/\./g, '-')}" x1="0%" y1="100%" x2="0%" y2="0%">
          <stop offset="0%" style="stop-color: var(--primary-color, #0077be); stop-opacity: 0.1"></stop>
          <stop offset="100%" style="stop-color: var(--error-color, #db4437); stop-opacity: 0.4"></stop>
        </linearGradient>
      </defs>
      <text class="axis-label start" x="${margin.left}" y="${height - 5}">${formatDate(startDate)}</text>
      <text class="axis-label end" x="${width - margin.right}" y="${height - 5}" text-anchor="end">${formatDate(endDate)}</text>
      
      <path class="chart-area" d="${areaGen(data) || ''}" fill="url(#gradient-${entityId.replace(/\./g, '-')})"></path>
      <path
        class="chart-line"
        d="${lineGen(data) || ''}"
        fill="none"
        stroke="var(--primary-color, #0077be)"
        stroke-width="2"
      ></path>
      
      ${renderRefLine(place.average_min, 'min', localize(this.hass, 'card.min'))}
      ${renderRefLine(place.average_max, 'max', localize(this.hass, 'card.max'))}
      ${renderRefLine(place.average_avg, 'avg', localize(this.hass, 'card.avg'))}
      
      ${minPoint ? svg`<circle class="extrema-dot min" cx="${x(minPoint.date)}" cy="${y(minPoint.value)}" r="3"></circle>` : ''}
      ${maxPoint ? svg`<circle class="extrema-dot max" cx="${x(maxPoint.date)}" cy="${y(maxPoint.value)}" r="3"></circle>` : ''}

      ${nowDot}
      ${hoverElements}
      
      <rect
        class="hover-overlay"
        x="${margin.left}"
        y="${margin.top}"
        width="${width - margin.left - margin.right}"
        height="${height - margin.top - margin.bottom}"
        fill="transparent"
        @mousemove="${(e: MouseEvent) => this._handleMouseMove(e, entityId, data, x, y, unitStr)}"
        @mouseleave="${(e: MouseEvent) => this._handleMouseLeave(e)}"
      ></rect>
    `;
  }

  static get styles() {
    return [unsafeCSS(styles)];
  }
}

if (!customElements.get(ELEMENT_NAME)) {
  customElements.define(ELEMENT_NAME, SeaTemperaturesCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: ELEMENT_NAME,
  name: 'Sea Temperatures Card',
  description: 'Display current and historical sea temperatures.',
  preview: true,
  documentationURL: 'https://github.com/timmaurice/sea-temperatures',
});
