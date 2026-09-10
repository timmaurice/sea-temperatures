import { describe, it, expect } from 'vitest';
import { resolveEntity } from '../src/entity-resolution';
import { HomeAssistant } from '../src/types';

const hass = {
  states: {
    'sensor.beach': { entity_id: 'sensor.beach', state: '21.5', attributes: {} },
    'sensor.offline': { entity_id: 'sensor.offline', state: 'unavailable', attributes: {} },
    'sensor.text': { entity_id: 'sensor.text', state: 'warm', attributes: {} },
    'light.kitchen': { entity_id: 'light.kitchen', state: 'on', attributes: {} },
  },
} as unknown as HomeAssistant;

describe('resolveEntity', () => {
  it('returns the entity when everything fits', () => {
    const resolved = resolveEntity(hass, 'sensor.beach', { domain: 'sensor', numeric: true });
    expect(resolved).toEqual({ ok: true, entity: hass.states['sensor.beach'] });
  });

  it('reports a missing entity rather than saying nothing', () => {
    expect(resolveEntity(hass, 'sensor.gone')).toEqual({
      ok: false,
      reason: 'not_found',
      target: 'sensor.gone',
    });
  });

  it('reports an entity from the wrong domain', () => {
    expect(resolveEntity(hass, 'light.kitchen', { domain: 'sensor' })).toEqual({
      ok: false,
      reason: 'wrong_domain',
      target: 'light.kitchen',
    });
  });

  it('reports a text state as not numeric only when a number is asked for', () => {
    expect(resolveEntity(hass, 'sensor.text', { numeric: true })).toEqual({
      ok: false,
      reason: 'not_numeric',
      target: 'sensor.text',
    });
    expect(resolveEntity(hass, 'sensor.text').ok).toBe(true);
  });

  it('keeps unavailable apart from missing', () => {
    expect(resolveEntity(hass, 'sensor.offline', { numeric: true })).toEqual({
      ok: false,
      reason: 'unavailable',
      target: 'sensor.offline',
    });
  });

  it('treats an id without a domain as missing, not as a wrong domain', () => {
    // Device ids reach the card the same way place targets do.
    expect(resolveEntity(hass, 'a1b2c3', { domain: 'sensor' }).ok).toBe(false);
    expect(resolveEntity(hass, 'a1b2c3', { domain: 'sensor' })).toMatchObject({ reason: 'not_found' });
  });

  it('survives being called before hass exists', () => {
    expect(resolveEntity(undefined, 'sensor.beach')).toMatchObject({ reason: 'not_found' });
    expect(resolveEntity(hass, undefined)).toMatchObject({ reason: 'not_found' });
  });
});
