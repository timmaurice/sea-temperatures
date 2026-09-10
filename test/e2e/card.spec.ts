import { test, expect } from './fixtures/hass';
import { removeState, setState, useDashboard } from './helpers/homeassistant';

const ENTITY = 'sensor.e2e_card_sea_temperature';

/** Thirty ISO-dated points, the way parser.py's `_parse_trend_chart` emits them. */
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

/**
 * Mirrors what sensor.py's `extra_state_attributes` puts on the entity. Writing
 * the real shape here is the point of an end-to-end test: an invented one would
 * have passed while the card showed nothing.
 */
const ATTRIBUTES = {
  friendly_name: 'E2E Beach',
  unit_of_measurement: '°C',
  device_class: 'temperature',
  state_class: 'measurement',
  yesterday: 21.5,
  last_week: 20.1,
  last_year: 19.4,
  date: '2026-09-10',
  average_min: 17.36,
  average_max: 21.3,
  average_avg: 19.19,
  charts: { last_thirty: trailingThirtyDays() },
  continent: 'Europe',
  country: 'Greece',
  area: 'Corfu',
  place: 'E2E Beach',
  path: '/europe/greece/corfu/e2e-beach',
};

const STATE = '22.5';

const DASHBOARD = {
  views: [
    {
      title: 'Sea',
      cards: [
        {
          type: 'custom:sea-temperatures-card',
          title: 'E2E sea temperatures',
          places: [ENTITY],
          show_country: true,
          show_trend: true,
        },
      ],
    },
    { title: 'Elsewhere', cards: [{ type: 'markdown', content: 'nothing here' }] },
  ],
};

let urlPath: string;

test.beforeAll(async () => {
  await setState(ENTITY, STATE, ATTRIBUTES);
  urlPath = await useDashboard('card', DASHBOARD);
});

test.afterAll(async () => {
  await removeState(ENTITY);
});

test.describe('The card on a real dashboard', () => {
  test('renders the temperature the sensor reports', async ({ page, consoleErrors }) => {
    await page.goto(`/${urlPath}/0`);

    // Assert on what the card paints, not on the custom element itself: the host
    // has no box of its own, so Playwright rightly calls it hidden.
    const card = page.locator('sea-temperatures-card');
    await expect(card.locator('ha-card')).toBeVisible({ timeout: 60_000 });
    await expect(card.locator('.place-name')).toHaveText('E2E Beach');
    await expect(card.locator('.place-country')).toHaveText('Greece');
    await expect(card.locator('.temp-value')).toHaveText('22.5');
    await expect(card.locator('.temp-unit')).toHaveText('°C');
    // yesterday 21.5 -> today 22.5 is a rise of one degree.
    await expect(card.locator('.current-trend')).toContainText('+1.0');
    expect(consoleErrors).toEqual([]);
  });

  test('draws the thirty-day chart from the charts attribute', async ({ page }) => {
    await page.goto(`/${urlPath}/0`);
    const card = page.locator('sea-temperatures-card');
    await expect(card.locator('.chart-container svg')).toBeVisible({ timeout: 60_000 });
    // An empty `d` is what a mis-shaped charts attribute produces, and it is
    // invisible on screen - so check the path actually has geometry.
    const path = await card.locator('.chart-line').getAttribute('d');
    expect(path?.length ?? 0).toBeGreaterThan(20);
  });

  test('comes back after leaving the view and returning', async ({ page }) => {
    // Views are torn out of the DOM on a switch. A card that does not notice it
    // is visible again comes back empty, and no unit test sees that.
    await page.goto(`/${urlPath}/0`);
    const temperature = page.locator('sea-temperatures-card').locator('.temp-value');
    await expect(temperature).toHaveText('22.5', { timeout: 60_000 });

    await page.getByRole('tab', { name: 'Elsewhere' }).click();
    await expect(page.locator('sea-temperatures-card')).toHaveCount(0);

    await page.getByRole('tab', { name: 'Sea' }).click();
    await expect(temperature).toHaveText('22.5', { timeout: 30_000 });
  });
});
