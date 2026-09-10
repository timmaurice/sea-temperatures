import { describe, it, expect } from 'vitest';
import { localize } from '../src/localize';
import { HomeAssistant } from '../src/types';
import de from '../src/translation/de.json';
import en from '../src/translation/en.json';
import es from '../src/translation/es.json';
import fr from '../src/translation/fr.json';
import italian from '../src/translation/it.json';

type Tree = { [key: string]: string | Tree };

function keysOf(tree: Tree, prefix = ''): string[] {
  return Object.entries(tree).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return typeof value === 'string' ? [path] : keysOf(value, path);
  });
}

const hass = (language: string) => ({ language }) as unknown as HomeAssistant;

describe('translations', () => {
  it('carries the same keys in every bundled language', () => {
    // A key added to en.json alone silently falls back for everyone else, and
    // rollup bundles all five, so the gap only shows up on a user's screen.
    const expected = keysOf(en as Tree).sort();
    for (const [language, tree] of Object.entries({ de, es, fr, it: italian })) {
      expect(keysOf(tree as Tree).sort(), language).toEqual(expected);
    }
  });

  it('fills the entity placeholder in a warning', () => {
    expect(localize(hass('en'), 'card.entity_problem.not_found', { entity: 'sensor.gone' })).toContain('sensor.gone');
    expect(localize(hass('de'), 'card.entity_problem.wrong_domain', { entity: 'light.x' })).toContain('light.x');
  });

  it('falls back to English for a language it does not bundle', () => {
    expect(localize(hass('nl'), 'card.yesterday')).toBe(en.card.yesterday);
  });
});
