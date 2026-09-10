// @vitest-environment node
// This file compiles the real stylesheet off disk, so it needs Node's fs and
// path rather than the jsdom environment the card tests run in.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import * as sass from 'sass';

/**
 * The narrow-column header, checked against the compiled stylesheet.
 *
 * At around 290px - a sections-grid card two columns wide on a phone - the
 * header used to break into three lines and drop the trend arrow underneath
 * the temperature. The cause was not a missing media query: `.place-info` and
 * `.place-name-container` were flex items at their default `min-width: auto`,
 * so the name would not shrink, and `.current-temp` was allowed to wrap
 * between the reading, its unit and the arrow.
 *
 * Which declarations may be global matters as much as their values. Letting a
 * column shrink and keeping one number on one line are right at every width,
 * but `overflow-wrap: anywhere` lowers a flex item's min-content size at any
 * width - a name and its country that fit on one line in a full-width card
 * would start wrapping - so the wrapping is asserted to be narrow-only.
 *
 * Compiling the real SCSS rather than asserting on the source text means a
 * value moved into a mixin, a variable or a nested block still counts.
 */

// Vitest runs from the repository root, and import.meta.url is not a file URL
// under its transform, so resolve against the project root instead.
const STYLES_DIR = resolve(process.cwd(), 'frontend/src/styles');

const css = sass.compileString(readFileSync(resolve(STYLES_DIR, 'card.styles.scss'), 'utf8'), {
  loadPaths: [STYLES_DIR],
  style: 'expanded',
}).css;

/** Return the declarations of a top-level rule, e.g. `.current-temp`. */
function declarationsOf(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = new RegExp(`(?:^|,|\\})\\s*${escaped}\\s*\\{([^{}]*)\\}`, 'm').exec(css);
  expect(match, `no rule found for ${selector}`).not.toBeNull();
  return match![1];
}

function declaration(selector: string, property: string): string | undefined {
  const body = declarationsOf(selector);
  const match = new RegExp(`(?:^|;)\\s*${property}\\s*:\\s*([^;]+)`).exec(body);
  return match?.[1].trim();
}

describe('the place header at narrow widths', () => {
  it('lets the name column shrink instead of pushing the temperature out', () => {
    expect(declaration('.place-info', 'min-width')).toBe('0');
    expect(declaration('.place-name-container', 'min-width')).toBe('0');
  });

  it('wraps a long place name once the card is narrow', () => {
    expect(declaration('ha-card.narrow .place-name-container', 'overflow-wrap')).toBe('anywhere');
    expect(declaration('ha-card.narrow .place-name-container', 'flex-wrap')).toBe('wrap');
  });

  it('keeps the reading, its unit and the trend arrow on one line', () => {
    expect(declaration('.current-temp', 'white-space')).toBe('nowrap');
    expect(declaration('.current-temp', 'flex')).toBe('0 0 auto');
  });
});

describe('the place header at full width', () => {
  it('does not let the name wrap, so a name and country stay on one line', () => {
    // The wide layout has room for both; wrapping here would be a regression,
    // not the fix. `overflow-wrap: anywhere` also changes the min-content size
    // used to lay the row out, so it must not leak out of the narrow block.
    expect(declaration('.place-name-container', 'overflow-wrap')).toBeUndefined();
    expect(declaration('.place-name-container', 'flex-wrap')).toBeUndefined();
  });

  it('leaves the header gap to the base rule at every width', () => {
    // A gap in the narrow block would take width away from the very name the
    // narrow fix is trying to fit.
    expect(declaration('.place-header', 'gap')).toBeUndefined();
    expect(css).not.toMatch(/ha-card\.narrow \.place-header\s*\{[^{}]*gap/);
  });

  it('does not repeat nowrap on a child of .current-temp', () => {
    // .current-trend sits inside .current-temp, which is already nowrap.
    expect(declaration('.current-trend', 'white-space')).toBeUndefined();
  });
});
