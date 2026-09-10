import { test, expect } from './fixtures/hass';
import { removeState, setState, useDashboard } from './helpers/homeassistant';

/**
 * What the card asks a sections grid for, against what it then paints.
 *
 * getGridOptions used to count whole rows per switched-on option, so a place
 * whose sensor carries no `charts` attribute still paid for the chart - and the
 * card sat in a slot far taller than its content. Only a real dashboard can
 * show that: the grid, not the card, decides how tall the slot is.
 */

const BARE = 'sensor.e2e_layout_bare';
const FULL = 'sensor.e2e_layout_full';

function trailingThirtyDays(): { labels: string[]; series: number[] } {
  const labels: string[] = [];
  const series: number[] = [];
  const today = new Date();
  for (let offset = 29; offset >= 0; offset--) {
    const day = new Date(today.getFullYear(), today.getMonth(), today.getDate() - offset);
    labels.push(
      `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`,
    );
    series.push(Math.round((18 + (29 - offset) * 0.15) * 100) / 100);
  }
  return { labels, series };
}

/** Home Assistant stacks 56px grid rows with an 8px gap between them. */
function slotHeightFor(rows: number): number {
  return rows * 56 + (rows - 1) * 8;
}

let urlPath: string;

test.beforeAll(async () => {
  // A place with statistics but no chart: the shape the old row count missed.
  await setState(BARE, '21.4', {
    friendly_name: 'Bare Beach',
    unit_of_measurement: '°C',
    device_class: 'temperature',
    yesterday: 21.1,
    average_avg: 19.2,
  });
  await setState(FULL, '22.5', {
    friendly_name: 'Full Beach',
    unit_of_measurement: '°C',
    device_class: 'temperature',
    yesterday: 21.5,
    average_avg: 19.19,
    average_min: 17.36,
    average_max: 21.3,
    charts: { last_thirty: trailingThirtyDays() },
  });

  urlPath = await useDashboard('layout', {
    views: [
      {
        type: 'sections',
        title: 'Layout',
        sections: [
          {
            type: 'grid',
            cards: [
              { type: 'custom:sea-temperatures-card', places: [BARE] },
              { type: 'custom:sea-temperatures-card', places: [FULL] },
            ],
          },
        ],
      },
    ],
  });
});

test.afterAll(async () => {
  await removeState(BARE);
  await removeState(FULL);
});

/** The grid slot each card was given, and the height the card actually paints. */
async function measure(page: import('@playwright/test').Page) {
  return page.evaluate(() => {
    const found: HTMLElement[] = [];
    const walk = (root: Document | ShadowRoot) => {
      root.querySelectorAll('*').forEach((element) => {
        if (element.tagName.toLowerCase() === 'sea-temperatures-card') found.push(element as HTMLElement);
        const shadow = (element as HTMLElement).shadowRoot;
        if (shadow) walk(shadow);
      });
    };
    walk(document);
    return found.map((card) => {
      // hui-card sits in the grid slot, which carries the --row-size the card asked for.
      const slot = card.parentElement!.parentElement as HTMLElement;
      return {
        rows: Number(slot.style.getPropertyValue('--row-size')),
        slot: Math.round(slot.getBoundingClientRect().height),
        content: Math.round(card.getBoundingClientRect().height),
      };
    });
  });
}

test.describe('The card in a sections grid', () => {
  test('reserves rows that cover the content without a gap under it', async ({ page }) => {
    await page.goto(`/${urlPath}/0`);
    await expect(page.locator('sea-temperatures-card').first().locator('ha-card')).toBeVisible({ timeout: 60_000 });
    await expect(page.locator('sea-temperatures-card').nth(1).locator('.chart-container svg')).toBeVisible();

    const cards = await measure(page);
    expect(cards).toHaveLength(2);

    for (const card of cards) {
      expect(card.rows).toBeGreaterThan(0);
      expect(card.slot).toBe(slotHeightFor(card.rows));
      // The content must fit...
      expect(card.content).toBeLessThanOrEqual(card.slot);
      // ...without leaving most of a row empty under it. The old count left 161px.
      expect(card.slot - card.content).toBeLessThan(56);
    }
  });

  test('asks for fewer rows when a place has no chart to draw', async ({ page }) => {
    await page.goto(`/${urlPath}/0`);
    await expect(page.locator('sea-temperatures-card').first().locator('ha-card')).toBeVisible({ timeout: 60_000 });

    const [bare, full] = await measure(page);
    expect(bare.rows).toBeLessThan(full.rows);
  });
});
