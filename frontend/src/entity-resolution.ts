import { TemplateResult, html } from 'lit';
import { localize } from './localize.js';
import { HassEntity, HomeAssistant } from './types.js';

/**
 * Turning a configured target into a usable entity, with a reason when it fails.
 *
 * A card that silently drops what it cannot resolve looks like a card that is
 * broken: the user sees an empty row and has nothing to act on. Every failure
 * here carries a typed reason so the caller can say what is wrong instead.
 */

/** Why a configured target could not be used. */
export type EntityProblem = 'not_found' | 'unavailable' | 'wrong_domain' | 'not_numeric';

export type EntityResolution = { ok: true; entity: HassEntity } | { ok: false; reason: EntityProblem; target: string };

export interface ResolveOptions {
  /** The domain the target has to live in. Omitted, any domain is accepted. */
  domain?: string;
  /** Require a state that parses as a number. */
  numeric?: boolean;
}

/** States Home Assistant uses to say it has no reading, not that it has a text one. */
const NON_STATES = new Set(['unavailable', 'unknown', '']);

export function resolveEntity(
  hass: HomeAssistant | undefined,
  target: string | undefined,
  options: ResolveOptions = {},
): EntityResolution {
  const id = (target ?? '').trim();
  if (!id) return { ok: false, reason: 'not_found', target: id };

  // Without a dot this is not an entity_id at all - a device_id, most likely -
  // so it is missing rather than in the wrong domain.
  const dot = id.indexOf('.');
  if (dot < 0) return { ok: false, reason: 'not_found', target: id };

  if (options.domain && id.slice(0, dot) !== options.domain) {
    return { ok: false, reason: 'wrong_domain', target: id };
  }

  const entity = hass?.states?.[id];
  if (!entity) return { ok: false, reason: 'not_found', target: id };

  if (NON_STATES.has(entity.state)) return { ok: false, reason: 'unavailable', target: id };

  if (options.numeric && isNaN(parseFloat(entity.state))) {
    return { ok: false, reason: 'not_numeric', target: id };
  }

  return { ok: true, entity };
}

/** A localised row explaining which target failed and why. */
export function renderEntityWarning(
  hass: HomeAssistant | undefined,
  reason: EntityProblem,
  target: string,
): TemplateResult {
  return html`
    <div class="entity-warning" role="status">
      <ha-icon icon="mdi:alert-outline"></ha-icon>
      <span>${localize(hass, `card.entity_problem.${reason}`, { entity: target })}</span>
    </div>
  `;
}
