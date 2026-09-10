import { HomeAssistant } from './types';

/**
 * Number and date formatting that follows the user's Home Assistant profile.
 *
 * `hass.locale` is set independently of `hass.language`: a user may read the UI
 * in English and still want 21,5 rather than 21.5, or a 24-hour clock in a
 * language whose default is 12-hour. Formatting off `hass.language` alone -
 * which the card used to do - ignores both of those settings.
 */

/** The locale whose separators match each Home Assistant number format. */
const NUMBER_FORMAT_LOCALES: Record<string, string | undefined> = {
  comma_decimal: 'en-US', // 1,234,567.89
  decimal_comma: 'de-DE', // 1.234.567,89
  space_comma: 'fr-FR', // 1 234 567,89
  system: undefined, // whatever the browser is set to
};

/** The locale to format numbers in, or undefined for the browser's own. */
export function numberFormatLocale(hass?: HomeAssistant): string | undefined {
  const format = hass?.locale?.number_format;
  if (format && format in NUMBER_FORMAT_LOCALES) return NUMBER_FORMAT_LOCALES[format];
  // 'language' and anything unknown follow the interface language.
  return hass?.locale?.language || hass?.language || undefined;
}

/**
 * Formats a number the way the rest of Home Assistant does.
 * @param value The number to format.
 * @param hass The Home Assistant object, read for locale settings.
 * @param options Intl options, e.g. a fixed number of fraction digits.
 */
export function formatNumber(value: number, hass?: HomeAssistant, options?: Intl.NumberFormatOptions): string {
  if (isNaN(value)) return String(value);
  // 'none' is the explicit opt-out: the raw value, ungrouped and unrounded.
  if (hass?.locale?.number_format === 'none') return String(value);

  try {
    return new Intl.NumberFormat(numberFormatLocale(hass), options).format(value);
  } catch {
    // An invalid locale must not take the whole card down with it.
    return String(value);
  }
}

/** True when the user asked for a 12-hour clock, false for 24, undefined for the locale default. */
function useHour12(hass?: HomeAssistant): boolean | undefined {
  switch (hass?.locale?.time_format) {
    case '12':
    case 'am_pm':
      return true;
    case '24':
      return false;
    default:
      return undefined;
  }
}

function formatWith(date: Date, hass: HomeAssistant | undefined, options: Intl.DateTimeFormatOptions): string {
  if (isNaN(date.getTime())) return '';
  try {
    return new Intl.DateTimeFormat(hass?.language || undefined, options).format(date);
  } catch {
    return date.toISOString();
  }
}

/** A day and month without a year, for chart axes and tooltips. */
export function formatMonthDay(date: Date, hass?: HomeAssistant): string {
  return formatWith(date, hass, { month: 'short', day: 'numeric' });
}

/** A day, month and clock time, for the "last updated" line. */
export function formatShortDateTime(date: Date, hass?: HomeAssistant): string {
  const hour12 = useHour12(hass);
  return formatWith(date, hass, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    ...(hour12 === undefined ? {} : { hour12 }),
  });
}

/** True when a state string carries a reading rather than a word. */
export function isNumeric(value: unknown): boolean {
  return !isNaN(parseFloat(String(value)));
}
