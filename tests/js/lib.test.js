import assert from "node:assert/strict";
import { test } from "node:test";

import * as lib from "../../site/lib.js";

const DATES = ["2026-09-24", "2026-09-25", "2026-10-01", "2026-10-02"];

test("dateToSeconds is midnight UTC", () => {
  assert.equal(lib.dateToSeconds("1970-01-02"), 86400);
  assert.equal(lib.dateToSeconds("2026-10-02"), Date.UTC(2026, 9, 2) / 1000);
});

test("formatDate drops the leading zero and names the month", () => {
  assert.equal(lib.formatDate("2026-10-02"), "2 Oct 2026");
  assert.equal(lib.formatDate("1990-01-31"), "31 Jan 1990");
});

test("formatDayMonth is the short form for a tight column", () => {
  assert.equal(lib.formatDayMonth("2026-10-02"), "2 Oct");
  assert.equal(lib.formatDayMonth("2026-09-25"), "25 Sep");
});

test("indexOnOrBefore finds the last date not after the target", () => {
  assert.equal(lib.indexOnOrBefore(DATES, "2026-09-27"), 1);
  assert.equal(lib.indexOnOrBefore(DATES, "2026-09-25"), 1);
  assert.equal(lib.indexOnOrBefore(DATES, "2030-01-01"), 3);
  assert.equal(lib.indexOnOrBefore(DATES, "2026-01-01"), -1);
});

test("indexOnOrAfter finds the first date not before the target", () => {
  assert.equal(lib.indexOnOrAfter(DATES, "2026-09-27"), 2);
  assert.equal(lib.indexOnOrAfter(DATES, "2026-09-25"), 1);
  assert.equal(lib.indexOnOrAfter(DATES, "2026-01-01"), 0);
  assert.equal(lib.indexOnOrAfter(DATES, "2030-01-01"), 4);
});

test("visibleSpan covers the dates inside a range, or is null", () => {
  assert.deepEqual(lib.visibleSpan(DATES, "2026-09-25", "2026-10-01"), { first: 1, last: 2 });
  assert.deepEqual(lib.visibleSpan(DATES, "2020-01-01", "2030-01-01"), { first: 0, last: 3 });
  assert.equal(lib.visibleSpan(DATES, "2026-09-26", "2026-09-30"), null);
});

test("clampIndex snaps to the nearer end of the span", () => {
  const span = { first: 10, last: 20 };
  assert.equal(lib.clampIndex(5, span), 10);
  assert.equal(lib.clampIndex(15, span), 15);
  assert.equal(lib.clampIndex(99, span), 20);
});

test("yearsBefore keeps the day and handles 29 February", () => {
  assert.equal(lib.yearsBefore("2026-10-02", 10), "2016-10-02");
  assert.equal(lib.yearsBefore("2024-02-29", 1), "2023-02-28");
  assert.equal(lib.yearsBefore("2024-02-29", 4), "2020-02-29");
});

test("presetRange stays inside the data", () => {
  assert.deepEqual(lib.presetRange("10Y", "1990-01-02", "2026-10-02"), { from: "2016-10-02", to: "2026-10-02" });
  assert.deepEqual(lib.presetRange("5Y", "2024-01-02", "2026-10-02"), { from: "2024-01-02", to: "2026-10-02" });
  assert.deepEqual(lib.presetRange("MAX", "1990-01-02", "2026-10-02"), { from: "1990-01-02", to: "2026-10-02" });
});

test("customRange clamps, orders, and rejects half-typed dates", () => {
  const first = "1990-01-02";
  const last = "2026-10-02";
  assert.deepEqual(lib.customRange("2008-01-01", "2010-12-31", first, last), { from: "2008-01-01", to: "2010-12-31" });
  assert.deepEqual(lib.customRange("1980-01-01", "2030-01-01", first, last), { from: first, to: last });
  assert.deepEqual(lib.customRange("2020-01-01", "2010-01-01", first, last), { from: "2010-01-01", to: "2020-01-01" });
  assert.equal(lib.customRange("", "2010-01-01", first, last), null);
  assert.equal(lib.customRange("2010-1-1", "2010-01-01", first, last), null);
});

test("customRange rejects a range with no width", () => {
  const first = "1990-01-02";
  const last = "2026-10-02";
  assert.equal(lib.customRange("2010-01-01", "2010-01-01", first, last), null);
  assert.equal(lib.customRange("1980-01-01", "1985-01-01", first, last), null);
  assert.deepEqual(lib.customRange("2010-01-01", "2010-01-02", first, last), { from: "2010-01-01", to: "2010-01-02" });
});

const TENORS = [
  { label: "3M", years: 0.25 },
  { label: "2Y", years: 2 },
  { label: "10Y", years: 10 },
  { label: "30Y", years: 30 },
];

test("tenorPositions are even in one mode and by years in the other", () => {
  assert.deepEqual(lib.tenorPositions(TENORS, "even"), [0, 1 / 3, 2 / 3, 1]);
  assert.deepEqual(lib.tenorPositions(TENORS, "scale"), [0.25 / 30, 2 / 30, 10 / 30, 1]);
  assert.deepEqual(lib.tenorPositions([TENORS[0]], "even"), [0.5]);
});

test("curveOn keeps only the tenors published that day", () => {
  const yields = { tenors: TENORS, values: [[null, 4.19], [3.5, 4.83], [4.1, 5.28], [4.8, 5.63]] };
  assert.deepEqual(lib.curveOn(yields, 0).map((point) => point.label), ["2Y", "10Y", "30Y"]);
  assert.deepEqual(lib.curveOn(yields, 1)[0], { index: 0, label: "3M", years: 0.25, value: 4.19 });
});

test("tenorName, formatPercent and formatRange", () => {
  assert.equal(lib.tenorName("10Y"), "10-year");
  assert.equal(lib.tenorName("1.5M"), "1.5-month");
  assert.equal(lib.formatPercent(5.28), "5.28%");
  assert.equal(lib.formatPercent(77.9, 1), "77.9%");
  assert.equal(lib.formatPercent(0, 1), "0.0%");
  assert.equal(lib.formatPercent(null), "n/a");
  assert.equal(lib.formatRange([3.75, 4]), "3.75–4.00%");
});

test("niceTicks are round and cover the values", () => {
  assert.deepEqual(lib.niceTicks(4.04, 5.67), [4, 4.5, 5, 5.5, 6]);
  assert.deepEqual(lib.niceTicks(0.05, 1.9), [0, 0.5, 1, 1.5, 2]);
  assert.deepEqual(lib.niceTicks(3, 3), [2.4, 2.6, 2.8, 3, 3.2, 3.4, 3.6]);
  const ticks = lib.niceTicks(6.63, 8.26);
  assert.ok(ticks[0] <= 6.63 && ticks.at(-1) >= 8.26);
});

const ALL_TENORS = ["1M", "1.5M", "2M", "3M", "4M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"].map((label) => ({
  label,
  years: label.endsWith("Y") ? Number(label.slice(0, -1)) : Number(label.slice(0, -1)) / 12,
}));

test("tenorLabelOrder puts the most watched tenors first and the rest in data order", () => {
  const order = lib.tenorLabelOrder(ALL_TENORS).map((index) => ALL_TENORS[index].label);
  assert.deepEqual(order, ["10Y", "2Y", "30Y", "5Y", "3M", "1Y", "20Y", "7Y", "3Y", "6M", "1M", "1.5M", "2M", "4M"]);
  assert.deepEqual(lib.tenorLabelOrder(TENORS), [2, 1, 3, 0]);
});

test("labelsThatFit takes labels in order of importance and skips the ones that would collide", () => {
  assert.deepEqual(lib.labelsThatFit([0, 50, 100], 20, [0, 1, 2]), [0, 1, 2]);
  assert.deepEqual(lib.labelsThatFit([0, 10, 20, 30, 40], 20, [4, 3, 2, 1, 0]), [0, 2, 4]);
  assert.deepEqual(lib.labelsThatFit([0, 10, 20, 30, 40], 20, [1, 0, 2, 3, 4]), [1, 3]);
});

test("a narrow curve keeps the tenors people look for, at both ends of the axis", () => {
  const label = (positions, gap) =>
    lib.labelsThatFit(positions, gap, lib.tenorLabelOrder(ALL_TENORS)).map((index) => ALL_TENORS[index].label);
  const even = lib.tenorPositions(ALL_TENORS, "even").map((share) => share * 280);
  assert.deepEqual(label(even, 32), ["1M", "3M", "6M", "2Y", "5Y", "10Y", "30Y"]);
  const scale = lib.tenorPositions(ALL_TENORS, "scale").map((share) => share * 508);
  assert.deepEqual(label(scale, 28), ["3M", "2Y", "5Y", "7Y", "10Y", "20Y", "30Y"]);
  const wide = lib.tenorPositions(ALL_TENORS, "even").map((share) => share * 508);
  assert.equal(label(wide, 32).length, 14);
});

const MEETINGS = [
  { end: "2026-10-28", statement_at: "2026-10-28T18:00:00Z" },
  { end: "2026-12-09", statement_at: "2026-12-09T19:00:00Z" },
];

test("nextMeeting is the first whose statement is still ahead", () => {
  assert.equal(lib.nextMeeting(MEETINGS, Date.parse("2026-10-28T17:59:00Z")).end, "2026-10-28");
  assert.equal(lib.nextMeeting(MEETINGS, Date.parse("2026-10-28T18:00:00Z")).end, "2026-12-09");
  assert.equal(lib.nextMeeting(MEETINGS, Date.parse("2027-01-01T00:00:00Z")), null);
});

test("countdownParts splits the time left and stops at zero", () => {
  const target = "2026-10-28T18:00:00Z";
  assert.deepEqual(lib.countdownParts(Date.parse("2026-10-04T01:55:00Z"), target), { days: 24, hours: 16, minutes: 5, past: false });
  assert.deepEqual(lib.countdownParts(Date.parse("2026-10-28T17:59:30Z"), target), { days: 0, hours: 0, minutes: 0, past: false });
  assert.deepEqual(lib.countdownParts(Date.parse("2026-10-29T00:00:00Z"), target), { days: 0, hours: 0, minutes: 0, past: true });
});

test("ageInDays counts whole days and never goes negative", () => {
  assert.equal(lib.ageInDays("2026-10-03T18:15:00Z", Date.parse("2026-10-07T18:14:00Z")), 3);
  assert.equal(lib.ageInDays("2026-10-03T18:15:00Z", Date.parse("2026-10-07T18:15:00Z")), 4);
  assert.equal(lib.ageInDays("2026-10-03T18:15:00Z", Date.parse("2026-10-01T00:00:00Z")), 0);
});

test("oddsAreOutdated once the meeting's statement is out, or the meeting is off the list", () => {
  const odds = { meeting: "2026-10-28" };
  assert.equal(lib.oddsAreOutdated(odds, MEETINGS, Date.parse("2026-10-28T17:00:00Z")), false);
  assert.equal(lib.oddsAreOutdated(odds, MEETINGS, Date.parse("2026-10-28T18:00:00Z")), true);
  assert.equal(lib.oddsAreOutdated({ meeting: "2026-09-16" }, MEETINGS, Date.parse("2026-10-01T00:00:00Z")), true);
});

test("publishedTargetLags compares the last published range with the current one", () => {
  const fed = { dates: ["a", "b"], target_lower: [3.5, 3.75], target_upper: [3.75, 4.0] };
  assert.equal(lib.publishedTargetLags(fed, { current_range: [3.75, 4.0] }), false);
  assert.equal(lib.publishedTargetLags(fed, { current_range: [4.0, 4.25] }), true);
});
