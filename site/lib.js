// Pure helpers for the page: no DOM and no network, so they run under `node --test`.

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
// Where to ask for a time zone's short name. Each of these knows the names used in its own region.
const ZONE_NAME_LOCALES = ["en-IN", "en-US", "en-GB", "en-AU"];
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
// Which tenors get an axis label first when there is not room for all of them.
const TENOR_LABEL_ORDER = ["10Y", "2Y", "30Y", "5Y", "3M", "1Y", "20Y", "7Y", "3Y", "6M", "1M"];

export const PRESET_YEARS = { "1Y": 1, "5Y": 5, "10Y": 10 };

/** "2026-10-02" as seconds since the epoch at midnight UTC. */
export function dateToSeconds(iso) {
  return Date.UTC(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1, Number(iso.slice(8, 10))) / 1000;
}

/** "2026-10-02" becomes "2 Oct 2026". */
export function formatDate(iso) {
  return `${Number(iso.slice(8, 10))} ${MONTHS[Number(iso.slice(5, 7)) - 1]} ${iso.slice(0, 4)}`;
}

/** "2026-10-02" becomes "2 Oct": the short form, for a tight table column. */
export function formatDayMonth(iso) {
  return `${Number(iso.slice(8, 10))} ${MONTHS[Number(iso.slice(5, 7)) - 1]}`;
}

/** Index of the last date not after `target` in a sorted list of ISO dates, or -1. */
export function indexOnOrBefore(dates, target) {
  let low = 0;
  let high = dates.length;
  while (low < high) {
    const middle = (low + high) >> 1;
    if (dates[middle] <= target) low = middle + 1;
    else high = middle;
  }
  return low - 1;
}

/** Index of the first date not before `target`, or `dates.length`. */
export function indexOnOrAfter(dates, target) {
  let low = 0;
  let high = dates.length;
  while (low < high) {
    const middle = (low + high) >> 1;
    if (dates[middle] < target) low = middle + 1;
    else high = middle;
  }
  return low;
}

/** The first and last indexes of the dates inside [from, to], or null when there are none. */
export function visibleSpan(dates, from, to) {
  const first = indexOnOrAfter(dates, from);
  const last = indexOnOrBefore(dates, to);
  return first <= last ? { first, last } : null;
}

/** An index kept inside a span, snapping to the nearer end. */
export function clampIndex(index, span) {
  return Math.min(span.last, Math.max(span.first, index));
}

/** The ISO date `years` years before `iso`. 29 February falls back to the 28th. */
export function yearsBefore(iso, years) {
  const year = Number(iso.slice(0, 4)) - years;
  const month = iso.slice(5, 7);
  const day = iso.slice(8, 10);
  const leap = (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
  const safeDay = month === "02" && day === "29" && !leap ? "28" : day;
  return `${String(year).padStart(4, "0")}-${month}-${safeDay}`;
}

/** The date range a preset stands for, kept inside the data's first and last dates. */
export function presetRange(preset, first, last) {
  if (!(preset in PRESET_YEARS)) return { from: first, to: last };
  const from = yearsBefore(last, PRESET_YEARS[preset]);
  return { from: from < first ? first : from, to: last };
}

/**
 * A typed range, kept inside the data and put in order.
 * Null unless both are full ISO dates and, once inside the data, they are different days.
 */
export function customRange(from, to, first, last) {
  if (!ISO_DATE.test(from) || !ISO_DATE.test(to)) return null;
  const inside = (value) => (value < first ? first : value > last ? last : value);
  const start = inside(from);
  const end = inside(to);
  if (start === end) return null;
  return start < end ? { from: start, to: end } : { from: end, to: start };
}

/** Where each tenor sits along the curve's axis, from 0 to 1. */
export function tenorPositions(tenors, mode) {
  if (tenors.length === 1) return [0.5];
  if (mode === "scale") {
    const longest = tenors[tenors.length - 1].years;
    return tenors.map((tenor) => tenor.years / longest);
  }
  return tenors.map((_, index) => index / (tenors.length - 1));
}

/** The curve on one date: a point for each tenor that has a value. */
export function curveOn(yields, dateIndex) {
  const points = [];
  yields.tenors.forEach((tenor, index) => {
    const value = yields.values[index][dateIndex];
    if (value !== null && value !== undefined) points.push({ index, label: tenor.label, years: tenor.years, value });
  });
  return points;
}

/** "10Y" becomes "10-year" and "3M" becomes "3-month". */
export function tenorName(label) {
  return `${label.slice(0, -1)}-${label.endsWith("Y") ? "year" : "month"}`;
}

export function formatPercent(value, digits = 2) {
  return value === null || value === undefined ? "n/a" : `${value.toFixed(digits)}%`;
}

/** [3.75, 4] becomes "3.75–4.00%". */
export function formatRange(range) {
  return `${range[0].toFixed(2)}–${range[1].toFixed(2)}%`;
}

/** Round axis values covering [min, max], roughly `count` of them. */
export function niceTicks(min, max, count = 5) {
  let low = min;
  let high = max;
  if (low === high) {
    low -= 0.5;
    high += 0.5;
  }
  const rough = (high - low) / count;
  const power = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((factor) => factor * power).find((candidate) => candidate >= rough - 1e-12);
  const start = Math.floor(low / step + 1e-9) * step;
  const end = Math.ceil(high / step - 1e-9) * step;
  const ticks = [];
  for (let value = start; value <= end + step / 2; value += step) ticks.push(Number(value.toFixed(6)));
  return ticks;
}

/** Tenor indexes in the order their axis labels matter: the most watched first, the rest in data order. */
export function tenorLabelOrder(tenors) {
  const rank = (index) => {
    const place = TENOR_LABEL_ORDER.indexOf(tenors[index].label);
    return place < 0 ? TENOR_LABEL_ORDER.length : place;
  };
  return tenors.map((_, index) => index).sort((a, b) => rank(a) - rank(b) || a - b);
}

/** The labels to draw: taken in `order`, skipping any that would sit within `gap` pixels of one already taken. */
export function labelsThatFit(positions, gap, order) {
  const taken = [];
  for (const index of order) {
    if (taken.every((other) => Math.abs(positions[index] - positions[other]) >= gap)) taken.push(index);
  }
  return taken.sort((a, b) => a - b);
}

/** The first meeting whose statement is still ahead of `nowMs`, or null. */
export function nextMeeting(meetings, nowMs) {
  return meetings.find((meeting) => Date.parse(meeting.statement_at) > nowMs) ?? null;
}

/** Whole days, hours, minutes and seconds from `nowMs` to an instant. All zero once it has passed. */
export function countdownParts(nowMs, target) {
  const left = Math.max(0, Date.parse(target) - nowMs);
  const seconds = Math.floor(left / 1000);
  return {
    days: Math.floor(seconds / 86400),
    hours: Math.floor((seconds % 86400) / 3600),
    minutes: Math.floor((seconds % 3600) / 60),
    seconds: seconds % 60,
    past: left === 0,
  };
}

/**
 * An instant as the clock reads in one time zone: "Wed 28 Oct, 2:00 pm".
 * With no zone it is the reader's own. Only the numbers come from the browser, so the wording
 * is the same everywhere and matches the dates on the rest of the page.
 */
export function formatInstant(iso, timeZone) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone, year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "numeric", hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const number = (type) => Number(parts.find((part) => part.type === type).value);
  const weekday = WEEKDAYS[new Date(Date.UTC(number("year"), number("month") - 1, number("day"))).getUTCDay()];
  const hour = number("hour") % 24;
  const minute = String(number("minute")).padStart(2, "0");
  return `${weekday} ${number("day")} ${MONTHS[number("month") - 1]}, ${hour % 12 || 12}:${minute} ${hour < 12 ? "am" : "pm"}`;
}

/** A short name for a time zone at an instant, such as "IST" or "EDT", or an offset such as "GMT+9". */
export function zoneLabel(iso, timeZone) {
  const at = new Date(iso);
  let offset = "";
  for (const locale of ZONE_NAME_LOCALES) {
    const parts = new Intl.DateTimeFormat(locale, { timeZone, timeZoneName: "short" }).formatToParts(at);
    const name = parts.find((part) => part.type === "timeZoneName").value;
    if (!/^(GMT|UTC)[+-]/.test(name)) return name;
    offset ||= name;
  }
  return offset;
}

/** Whole days since the data was generated. */
export function ageInDays(generatedAt, nowMs) {
  return Math.max(0, Math.floor((nowMs - Date.parse(generatedAt)) / 86400000));
}

/** True once the statement of the meeting the odds were calculated for has come out. */
export function oddsAreOutdated(odds, meetings, nowMs) {
  const meeting = meetings.find((candidate) => candidate.end === odds.meeting);
  return !meeting || Date.parse(meeting.statement_at) <= nowMs;
}

/** True when the published target range is not the one the odds treat as current. */
export function publishedTargetLags(fedFunds, odds) {
  const last = fedFunds.dates.length - 1;
  return fedFunds.target_lower[last] !== odds.current_range[0] || fedFunds.target_upper[last] !== odds.current_range[1];
}
