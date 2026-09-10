import { describe, it, expect } from 'vitest';
import { formatMonthDay, formatNumber, formatShortDateTime, isNumeric } from '../src/format';
import { HomeAssistant } from '../src/types';

const hassWith = (locale: Partial<HomeAssistant['locale']>, language = 'en'): HomeAssistant =>
  ({ language, locale: { language, ...locale } }) as unknown as HomeAssistant;

describe('formatNumber', () => {
  it('follows the number format, not the interface language', () => {
    // A German reading Home Assistant in English still wants 21,5.
    const hass = hassWith({ number_format: 'decimal_comma' }, 'en');
    expect(formatNumber(21.5, hass)).toBe('21,5');
  });

  it('honours comma_decimal and space_comma', () => {
    expect(formatNumber(1234.5, hassWith({ number_format: 'comma_decimal' }, 'de'))).toBe('1,234.5');
    expect(formatNumber(1234.5, hassWith({ number_format: 'space_comma' }, 'en'))).toContain(',5');
  });

  it('leaves the value alone when formatting is turned off', () => {
    expect(formatNumber(1234.5, hassWith({ number_format: 'none' }))).toBe('1234.5');
  });

  it('falls back to the language when no number format is set', () => {
    expect(formatNumber(21.5, hassWith({}, 'de'))).toBe('21,5');
  });

  it('passes fraction digits through', () => {
    const hass = hassWith({ number_format: 'comma_decimal' });
    expect(formatNumber(1, hass, { minimumFractionDigits: 1, maximumFractionDigits: 1 })).toBe('1.0');
  });

  it('never throws on a broken locale', () => {
    expect(formatNumber(1.5, hassWith({}, 'not a locale'))).toBe('1.5');
  });
});

describe('formatShortDateTime', () => {
  const date = new Date(2026, 4, 21, 15, 30);

  it('uses a 24-hour clock when the profile asks for one', () => {
    expect(formatShortDateTime(date, hassWith({ time_format: '24' }, 'en'))).toContain('15:30');
  });

  it('uses a 12-hour clock when the profile asks for one', () => {
    const formatted = formatShortDateTime(date, hassWith({ time_format: '12' }, 'en'));
    expect(formatted.toLowerCase()).toContain('pm');
  });
});

describe('formatMonthDay', () => {
  it('formats in the interface language', () => {
    expect(formatMonthDay(new Date(2026, 4, 21), hassWith({}, 'en'))).toBe('May 21');
  });
});

describe('isNumeric', () => {
  it('separates readings from words', () => {
    expect(isNumeric('21.5')).toBe(true);
    expect(isNumeric('warm')).toBe(false);
    expect(isNumeric('')).toBe(false);
    expect(isNumeric(undefined)).toBe(false);
  });
});
