# Macros Page, Plan 2c: Four Changes to the Page

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Four changes the owner asked for after looking at the page: a marker line at the selected tenor on the curve, seconds in the countdown, a link to the code on GitHub at the end of the page, and a link from the odds note to CME's description of its method.

**Architecture:** No new files. The helpers gain seconds in the countdown and two functions that write the statement time the same way in every browser. The curve drawing gains the marker. The page gains two links to other sites. The static page test now tells a link to another site, which is allowed with safe attributes, from a file loaded from another site, which is still forbidden.

**Tech Stack:** As Plan 2b: browser JavaScript as ES modules with no build step and no npm packages, uPlot 1.6.32 vendored, Python 3.14 kept compatible with 3.12, pytest 9.1.1, and Node 20 or newer for the helpers' tests.

**Spec:** `docs/superpowers/specs/2026-10-04-macros-page-design.md`, sections 5.3, 5.4, 5.7, 5.9 and 13. The spec was updated alongside this plan.

**Supersedes:** for every file listed below, the content in Plan 2b.

---

## What changes

| Asked for | What this plan does |
|---|---|
| The vertical line of the left chart, on the right chart in even spacing | In even spacing, a vertical line runs through the selected tenor, in the same colour and weight as the date marker, directly above the slider's thumb. The selected point's value moves beside the line, on the side where the curve is lower, so the line does not run through the number. True scale has no line |
| Seconds in the countdown | The countdown reads `24d 17h 40m 55s` and is redrawn at each whole second. Its digits are all one width, so the line stays still as it ticks. Its size follows the card's width, so it stays on one line from a 320px phone up |
| A proper GitHub link at the end of the page | The footer ends with one link target: the GitHub mark, "Source code on GitHub", the repository's name and an arrow. It opens in a new tab |
| A link on "method CME Group" | "the method CME Group publishes" in the odds note links to CME's methodology article, in a new tab |

One more change comes with the countdown. The line under it showed the visitor's time in the browser's own format. On a US-English browser that read `Wed, Oct 28, 11:30 PM GMT+5:30`, beside a New York time written day first. Both times are now written the same way, `Wed 28 Oct, 11:30 pm IST`, with the zone's familiar short name where one exists.

Two things to know about the links:

- The GitHub mark is drawn in the page itself as SVG. Nothing is fetched from github.com or cmegroup.com unless the visitor follows a link.
- Both links carry `target="_blank"` and `rel="noopener noreferrer"`, so the other site learns nothing about this page.

## Rules for whoever executes this plan

- **Never run `git add`, `commit`, `push`, `stash`, `reset`, `checkout` or `restore`.** The owner makes every commit. Each task ends with a checkpoint. Stop there and report.
- **Tests never touch a real service.** Do not run `python -m macro refresh` or `python -m macro preview` unless a step says so.
- **Nothing in this plan touches the box or Cloudflare.** Do not run `ssh`.
- Run every command from the project root, `/Users/himanshusrivastava/Projects/Macros`, with `.venv/bin/python`.
- Each file below is shown in full. It **replaces** the existing file of the same path. Copy it exactly.
- The page must have no inline script or style, must not use `innerHTML`, and must load nothing from another site.

## File structure

| File | What changes in it |
|---|---|
| `site/lib.js` | `countdownParts` now returns seconds. New: `formatInstant` and `zoneLabel`, which write an instant for a time zone |
| `site/charts.js` | `drawCurve` draws the marker in even spacing and places the value label beside it |
| `site/app.js` | The clock is redrawn every second and uses the two new helpers. Text that has not changed is not rewritten, so it can still be selected |
| `site/index.html` | The link in the odds note, and the link to the code at the end of the footer |
| `site/style.css` | The marker, the countdown's size and digits, links inside sentences, and the link to the code |
| `tests/js/lib.test.js` | Tests for seconds and for the two new helpers |
| `tests/test_site_page.py` | Loads from another site are still refused. The two links to other sites are named and must carry the safe attributes |

---

### Task 1: The four changes

**Files:**
- Replace: `tests/js/lib.test.js`, `tests/test_site_page.py`
- Replace: `site/lib.js`, `site/charts.js`, `site/app.js`, `site/index.html`, `site/style.css`

These files were tested in Chrome before this plan was written: light and dark, from 320px to 1280px wide, on a US-English browser set to Indian time, with no console or security-policy errors. The marker, the selected point and the slider's thumb share one position to within a tenth of a pixel.

- [ ] **Step 1: Replace the two test files**

**File: `tests/js/lib.test.js`**

```javascript
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

test("countdownParts splits the time left down to the second and stops at zero", () => {
  const target = "2026-10-28T18:00:00Z";
  assert.deepEqual(lib.countdownParts(Date.parse("2026-10-04T01:55:00Z"), target), { days: 24, hours: 16, minutes: 5, seconds: 0, past: false });
  assert.deepEqual(lib.countdownParts(Date.parse("2026-10-27T16:58:53Z"), target), { days: 1, hours: 1, minutes: 1, seconds: 7, past: false });
  assert.deepEqual(lib.countdownParts(Date.parse("2026-10-28T17:59:30.400Z"), target), { days: 0, hours: 0, minutes: 0, seconds: 29, past: false });
  assert.deepEqual(lib.countdownParts(Date.parse("2026-10-29T00:00:00Z"), target), { days: 0, hours: 0, minutes: 0, seconds: 0, past: true });
});

test("formatInstant writes one instant as the clock reads in a given time zone, day first", () => {
  assert.equal(lib.formatInstant("2026-10-28T18:00:00Z", "America/New_York"), "Wed 28 Oct, 2:00 pm");
  assert.equal(lib.formatInstant("2026-10-28T18:00:00Z", "Asia/Kolkata"), "Wed 28 Oct, 11:30 pm");
  assert.equal(lib.formatInstant("2026-12-09T19:00:00Z", "Asia/Kolkata"), "Thu 10 Dec, 12:30 am");
  assert.equal(lib.formatInstant("2026-10-28T06:30:00Z", "Asia/Kolkata"), "Wed 28 Oct, 12:00 pm");
  assert.equal(lib.formatInstant("2026-09-08T03:05:00Z", "UTC"), "Tue 8 Sep, 3:05 am");
});

test("zoneLabel prefers a familiar short name and falls back to an offset", () => {
  assert.equal(lib.zoneLabel("2026-10-28T18:00:00Z", "Asia/Kolkata"), "IST");
  assert.equal(lib.zoneLabel("2026-10-28T18:00:00Z", "America/New_York"), "EDT");
  assert.equal(lib.zoneLabel("2026-12-09T19:00:00Z", "America/New_York"), "EST");
  assert.equal(lib.zoneLabel("2026-07-01T12:00:00Z", "Europe/London"), "BST");
  assert.equal(lib.zoneLabel("2026-12-09T19:00:00Z", "Europe/London"), "GMT");
  assert.equal(lib.zoneLabel("2026-10-28T18:00:00Z", "Asia/Tokyo"), "GMT+9");
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
```

**File: `tests/test_site_page.py`**

```python
"""Static checks on the page's files: mistakes that would otherwise show only in a browser."""
import re
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1] / "site"
BUILD_ID = "v={{BUILD_ID}}"


def read(name):
    return (SITE / name).read_text(encoding="utf-8")


def test_every_element_the_script_looks_up_is_on_the_page():
    wanted = set(re.findall(r'\$\("([a-z0-9-]+)"\)', read("app.js")))
    present = re.findall(r'\bid="([a-z0-9-]+)"', read("index.html"))
    assert len(wanted) > 20
    assert wanted - set(present) == set()
    assert len(present) == len(set(present)), "an id is used twice"


def test_the_page_has_nothing_the_content_security_policy_would_block():
    page = read("index.html")
    assert not re.search(r"<style\b", page)
    assert not re.search(r"\sstyle\s*=", page)
    assert not re.search(r"\son[a-z]+\s*=", page)
    scripts = re.findall(r"<script\b([^>]*)>(.*?)</script>", page, flags=re.S)
    assert len(scripts) == 2
    for attributes, body in scripts:
        assert "src=" in attributes and body.strip() == ""
    for name in ("app.js", "charts.js"):
        assert "innerHTML" not in read(name) and "eval(" not in read(name)


def test_every_file_the_page_loads_is_local_and_carries_the_build_id():
    page = read("index.html")
    loaded = []
    for tag in re.findall(r"<(?:link|script|img|image|use|iframe|embed|object|source|video|audio)\b[^>]*>", page):
        loaded += re.findall(r'\b(?:href|src|data)="([^"]+)"', tag)
    files = [address for address in loaded if not address.startswith("data:")]
    assert len(files) == 4
    for address in files:
        path, _, query = address.partition("?")
        assert query == BUILD_ID, address
        assert ":" not in path and "//" not in path and (SITE / path).is_file(), address


def test_links_to_other_sites_open_in_a_new_tab_and_tell_them_nothing():
    page = read("index.html")
    outside = [tag for tag in re.findall(r"<a\b[^>]*>", page) if re.search(r'\bhref="[a-z]+:', tag)]
    assert sorted(re.search(r'\bhref="([^"]+)"', tag).group(1) for tag in outside) == [
        "https://github.com/Himanshujoy/Macros",
        "https://www.cmegroup.com/articles/2023/understanding-the-cme-group-fedwatch-tool-methodology.html",
    ]
    for tag in outside:
        assert 'target="_blank"' in tag and 'rel="noopener noreferrer"' in tag, tag
    assert len(re.findall(r"https?://", page)) == len(outside), "nothing else on the page may name another site"


@pytest.mark.parametrize("name", ["app.js", "charts.js"])
def test_the_scripts_import_each_other_with_the_build_id(name):
    imports = re.findall(r'^import\b.*\bfrom "([^"]+)";$', read(name), flags=re.M)
    assert imports
    for address in imports:
        path, _, query = address.partition("?")
        assert query == BUILD_ID, address
        assert path.startswith("./") and (SITE / path).is_file(), address


def test_every_colour_role_is_defined_for_light_and_for_dark():
    css = read("style.css")
    light = css[css.index(":root {"):css.index("@media (prefers-color-scheme: dark)")]
    dark = css[css.index("@media (prefers-color-scheme: dark)"):css.index("* {")]
    defined = set(re.findall(r"^\s*(--[a-z0-9-]+):", light, flags=re.M))
    used = set(re.findall(r"var\((--[a-z0-9-]+)\)", css)) | set(re.findall(r'value\("(--[a-z0-9-]+)"\)', read("charts.js")))
    assert used - defined == set()
    colours = {name for name in defined if name != "--thumb"}
    assert set(re.findall(r"^\s*(--[a-z0-9-]+):", dark, flags=re.M)) == colours
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
node --test tests/js/lib.test.js
.venv/bin/python -m pytest tests/test_site_helpers.py tests/test_site_page.py
```

Expected: Node reports `pass 22` and `fail 3`; pytest reports `2 failed, 7 passed`. The failures are the countdown's seconds, the two new helpers, and the links test.

- [ ] **Step 3: Replace the five page files**

**File: `site/lib.js`**

```javascript
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
```

**File: `site/charts.js`**

```javascript
// Drawing: the two history charts with uPlot, and the curve and odds charts in SVG.
// Everything here touches the page; the arithmetic lives in lib.js.
/* global uPlot */
import { formatPercent, labelsThatFit, niceTicks, tenorLabelOrder, tenorPositions } from "./lib.js?v={{BUILD_ID}}";

const SVG_NS = "http://www.w3.org/2000/svg";
const FONT = '12px system-ui, -apple-system, "Segoe UI", sans-serif';
const TIME_CHART_HEIGHT = 280;
const CURVE = { height: 280, left: 48, right: 18, top: 24, bottom: 50 }; // the same baseline as the time chart beside it
const ODDS = { plot: 156, left: 44, right: 12, top: 28, column: 24, oneLine: 72 }; // oneLine: the room a range label needs
const LABEL_GAP = { even: 32, scale: 28 }; // the least distance between two tenor labels, in pixels

// Time axis: ticks never finer than a day, and dates written day first ("2 Oct", not "10/2").
const DAY = 86400;
const X_STEPS = [
  ...[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15].map((days) => days * DAY),
  ...[1, 2, 3, 4, 6].map((months) => months * 30 * DAY),
  ...[1, 2, 5, 10, 25, 50, 100].map((years) => years * 365 * DAY),
];
const X_LABELS = [
  [365 * DAY, "{YYYY}", null, null, null, null, null, null, 1],
  [28 * DAY, "{MMM}", "\n{YYYY}", null, null, null, null, null, 1],
  [DAY, "{D} {MMM}", "\n{YYYY}", null, null, null, null, null, 1],
];

/** The colours in force, read from the stylesheet so light and dark are defined in one place. */
function readTheme() {
  const style = getComputedStyle(document.documentElement);
  const value = (name) => style.getPropertyValue(name).trim();
  return {
    surface: value("--surface"),
    ink2: value("--ink-2"),
    muted: value("--muted"),
    grid: value("--grid"),
    axis: value("--axis"),
    series1: value("--series-1"),
    series2: value("--series-2"),
    wash2: value("--series-2-wash"),
  };
}

function svg(name, attributes = {}, text = null) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  if (text !== null) node.textContent = text;
  return node;
}

const tips = new WeakMap();

/**
 * One tooltip per chart host: a title, then rows with the value first and its label after.
 * It sits `gap` pixels to the right of x, or to the left when there is no room on the right.
 */
function tipFor(host) {
  if (tips.has(host)) return tips.get(host);
  const box = document.createElement("div");
  box.className = "tip";
  box.hidden = true;
  host.append(box);
  const tip = {
    show(title, rows, x, y, gap = 14) {
      box.replaceChildren();
      const heading = document.createElement("div");
      heading.className = "tip-title";
      heading.textContent = title;
      box.append(heading);
      for (const row of rows) {
        const line = document.createElement("div");
        line.className = "tip-row";
        if (row.key) {
          const key = document.createElement("span");
          key.className = `key ${row.key}`;
          line.append(key);
        }
        const value = document.createElement("strong");
        value.textContent = row.value;
        const label = document.createElement("span");
        label.textContent = row.label;
        line.append(value, label);
        box.append(line);
      }
      box.hidden = false;
      const width = box.offsetWidth;
      const left = x + gap + width > host.clientWidth ? x - gap - width : x + gap;
      box.style.left = `${Math.max(0, left)}px`;
      box.style.top = `${Math.max(0, y)}px`;
    },
    hide() {
      box.hidden = true;
    },
  };
  tips.set(host, tip);
  return tip;
}

/**
 * A uPlot time chart with a marker at one date and a tooltip that follows the pointer.
 *
 * `describe(theme)` returns `{ series, bands }` for the data columns after x.
 * `tooltip(index)` returns `{ title, rows }` for the data row under the pointer.
 * `onLayout()` is called once the plot area has its place, and again whenever that changes.
 */
export function timeChart(host, describe, tooltip, onLayout = null) {
  const tip = tipFor(host);
  let chart = null;
  let theme = null;
  let data = null;
  let range = null;
  let marker = null;

  function drawMarker(plot) {
    if (!marker) return;
    const box = plot.bbox;
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(1, Math.round(ratio));
    const centre = Math.round(plot.valToPos(marker.x, "x", true));
    if (centre < box.left || centre > box.left + box.width) return;
    const x = centre + (width % 2) / 2; // an odd-width line is sharp only when centred on a pixel
    const context = plot.ctx;
    context.save();
    context.strokeStyle = theme.ink2;
    context.lineWidth = width;
    context.beginPath();
    context.moveTo(x, box.top);
    context.lineTo(x, box.top + box.height);
    context.stroke();
    if (marker.y !== null && marker.y !== undefined) {
      const y = plot.valToPos(marker.y, "y", true);
      if (y >= box.top && y <= box.top + box.height) {
        context.fillStyle = theme.surface;
        context.beginPath();
        context.arc(x, y, 6 * ratio, 0, 2 * Math.PI);
        context.fill();
        context.fillStyle = theme.series1;
        context.beginPath();
        context.arc(x, y, 4 * ratio, 0, 2 * Math.PI);
        context.fill();
      }
    }
    context.restore();
  }

  function followPointer(plot) {
    const { idx, left } = plot.cursor;
    if (idx === null || idx === undefined || left === undefined || left < 0) {
      tip.hide();
      return;
    }
    const content = tooltip(idx);
    if (!content) {
      tip.hide();
      return;
    }
    tip.show(content.title, content.rows, plot.over.offsetLeft + left, plot.over.offsetTop + 8);
  }

  function build() {
    if (chart) chart.destroy();
    chart = null;
    if (!data || host.clientWidth === 0) return;
    theme = readTheme();
    const { series, bands } = describe(theme);
    const axis = {
      stroke: theme.muted,
      font: FONT,
      grid: { stroke: theme.grid, width: 1 },
      ticks: { stroke: theme.axis, width: 1, size: 4 },
    };
    chart = new uPlot(
      {
        width: host.clientWidth,
        height: TIME_CHART_HEIGHT,
        tzDate: (seconds) => uPlot.tzDate(new Date(seconds * 1000), "UTC"),
        legend: { show: false },
        cursor: {
          y: false,
          drag: { x: false, y: false },
          points: {
            size: 10,
            width: 2,
            stroke: () => theme.surface,
            fill: (plot, index) => series[index - 1].stroke,
          },
        },
        scales: { x: { time: true } },
        axes: [
          { ...axis, incrs: X_STEPS, values: X_LABELS },
          { ...axis, size: 52, values: (plot, splits) => splits.map((value) => `${Number(value.toFixed(2))}%`) },
        ],
        series: [{}, ...series.map((entry) => ({ spanGaps: false, points: { show: false }, ...entry }))],
        bands,
        hooks: { draw: [drawMarker], setCursor: [followPointer], setSize: [() => onLayout?.()] },
      },
      data,
      host,
    );
    if (range) chart.setScale("x", range);
  }

  return {
    setData(next) {
      data = next;
      if (!chart) {
        build();
        return;
      }
      chart.setData(data);
      if (range) chart.setScale("x", range);
    },
    setRange(min, max) {
      range = { min, max };
      if (chart) chart.setScale("x", range);
    },
    setMarker(next) {
      marker = next;
      if (chart) chart.redraw(false);
    },
    /** Rebuilds the chart for a new width or a new colour scheme. */
    rebuild: build,
    /** The plot area inside the host, in CSS pixels: used to line a slider up with the x-axis. */
    plotBox() {
      return chart ? { left: chart.over.offsetLeft, width: chart.over.offsetWidth } : null;
    },
  };
}

/** A fresh SVG for the host. Whatever its tooltip said belonged to the drawing this one replaces. */
function frame(host, label, height) {
  host.querySelector("svg")?.remove();
  tipFor(host).hide();
  const width = host.clientWidth;
  const root = svg("svg", { viewBox: `0 0 ${width} ${height}`, width, height, role: "img", "aria-label": label });
  host.prepend(root);
  return { root, width };
}

function watch(target, host, show) {
  const tip = tipFor(host);
  target.addEventListener("pointerenter", show);
  target.addEventListener("focus", show);
  target.addEventListener("pointerleave", () => tip.hide());
  target.addEventListener("blur", () => tip.hide());
}

/**
 * The yield curve on one date.
 *
 * `tenors` is every tenor in the data, so the axis stays put from date to date; `points` are
 * the tenors published that day; `selected` is a tenor index; `onPick(index)` is called when a
 * point is clicked or chosen with the keyboard. Returns the x of the first and last tenor in
 * CSS pixels, so the slider underneath can line up with them.
 */
export function drawCurve(host, { tenors, points, mode, selected, title, onPick }) {
  const { height, left, right, top, bottom } = CURVE;
  // A redraw replaces every node, so note which point has the focus and give it back afterwards.
  const focused = host.contains(document.activeElement) ? document.activeElement.dataset.tenor : undefined;
  const { root, width } = frame(host, title, height);
  const tip = tipFor(host);
  const plotWidth = width - left - right;
  const baseline = height - bottom;
  const xs = tenorPositions(tenors, mode).map((share) => left + share * plotWidth);
  const span = { first: xs[0], last: xs[xs.length - 1] };

  if (points.length === 0) {
    root.append(svg("text", { x: width / 2, y: height / 2, class: "tick", "text-anchor": "middle" }, "No yields were published on this date."));
    return span;
  }

  const ticks = niceTicks(Math.min(...points.map((p) => p.value)), Math.max(...points.map((p) => p.value)));
  const low = ticks[0];
  const high = ticks[ticks.length - 1];
  const y = (value) => top + (1 - (value - low) / (high - low)) * (baseline - top);

  for (const tick of ticks) {
    root.append(svg("line", { x1: left, x2: width - right, y1: y(tick), y2: y(tick), class: "grid" }));
    root.append(svg("text", { x: left - 8, y: y(tick) + 4, class: "tick", "text-anchor": "end" }, `${tick}%`));
  }
  root.append(svg("line", { x1: left, x2: width - right, y1: baseline, y2: baseline, class: "axis" }));
  xs.forEach((x) => root.append(svg("line", { x1: x, x2: x, y1: baseline, y2: baseline + 4, class: "axis" })));

  for (const index of labelsThatFit(xs, LABEL_GAP[mode], tenorLabelOrder(tenors))) {
    root.append(svg("text", { x: xs[index], y: baseline + 20, class: "tick", "text-anchor": "middle" }, tenors[index].label));
  }

  const path = points.map((point, order) => `${order === 0 ? "M" : "L"}${xs[point.index].toFixed(1)} ${y(point.value).toFixed(1)}`).join(" ");
  root.append(svg("path", { d: path, class: "line" }));

  // In even spacing the chosen tenor gets the same vertical marker as the chosen date on the
  // history chart. It sits above the slider's thumb. True scale has no marker: its slider is locked.
  const marked = mode === "even";
  if (marked) root.append(svg("line", { x1: xs[selected], x2: xs[selected], y1: top, y2: baseline, class: "marker" }));

  points.forEach((point, order) => {
    const chosen = point.index === selected;
    const x = xs[point.index];
    const cy = y(point.value);
    root.append(svg("circle", { cx: x, cy, r: chosen ? 6 : 4, class: chosen ? "dot is-selected" : "dot" }));
    if (!chosen) return;
    let shift = 0;
    let anchor = x > width - 60 ? "end" : x < left + 30 ? "start" : "middle";
    if (marked) {
      // Beside the marker, so the line does not run through the number: on the side the curve leaves lower.
      const before = points[order - 1];
      const after = points[order + 1];
      const onLeft = before !== undefined && (after === undefined || before.value <= after.value);
      shift = onLeft ? -10 : 10;
      anchor = onLeft ? "end" : "start";
    }
    root.append(svg("text", { x: x + shift, y: cy - 12, class: "point-label", "text-anchor": anchor }, formatPercent(point.value)));
  });
  // Hit targets go on top, and are much larger than the dots they stand for.
  for (const point of points) {
    const x = xs[point.index];
    const cy = y(point.value);
    const hit = svg("circle", {
      cx: x, cy, r: 12, class: "hit pick", tabindex: 0, role: "button", "data-tenor": point.index,
      "aria-pressed": point.index === selected, "aria-label": `${point.label}: ${formatPercent(point.value)}`,
    });
    watch(hit, host, () => tip.show(point.label, [{ key: "line series-1", value: formatPercent(point.value), label: "yield" }], x, Math.max(0, cy - 44)));
    hit.addEventListener("click", () => onPick(point.index));
    hit.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      onPick(point.index);
    });
    root.append(hit);
  }
  if (focused !== undefined) root.querySelector(`[data-tenor="${focused}"]`)?.focus();
  return span;
}

/**
 * Probability by target range as columns: one colour, the value on the cap, the current range
 * named in words. Where a range will not fit under its column on one line, it is written on two.
 */
export function drawOdds(host, { outcomes, current, title }) {
  const { plot, left, right, top, column, oneLine } = ODDS;
  const slot = (host.clientWidth - left - right) / outcomes.length;
  const stacked = slot < oneLine;
  const baseline = top + plot;
  const { root, width } = frame(host, title, baseline + (stacked ? 60 : 46));
  const tip = tipFor(host);
  const y = (percent) => top + (1 - percent / 100) * plot;
  const thick = Math.min(column, slot - 2);

  for (const tick of [0, 25, 50, 75, 100]) {
    root.append(svg("line", { x1: left, x2: width - right, y1: y(tick), y2: y(tick), class: tick === 0 ? "axis" : "grid" }));
    root.append(svg("text", { x: left - 8, y: y(tick) + 4, class: "tick", "text-anchor": "end" }, `${tick}%`));
  }

  outcomes.forEach((outcome, index) => {
    const centre = left + slot * (index + 0.5);
    const value = outcome.now ?? 0;
    const cap = y(value);
    const radius = Math.min(4, baseline - cap);
    const x0 = centre - thick / 2;
    const x1 = centre + thick / 2;
    if (value > 0) {
      const d = `M${x0} ${baseline} V${cap + radius} Q${x0} ${cap} ${x0 + radius} ${cap} H${x1 - radius} Q${x1} ${cap} ${x1} ${cap + radius} V${baseline} Z`;
      root.append(svg("path", { d, class: "column" }));
    }
    const low = outcome.range[0].toFixed(2);
    const high = outcome.range[1].toFixed(2);
    const range = `${low}–${high}`;
    const isCurrent = outcome.range[0] === current[0];
    const lines = stacked ? [`${low}–`, high] : [range];
    root.append(svg("text", { x: centre, y: cap - 8, class: "point-label", "text-anchor": "middle" }, formatPercent(outcome.now, 1)));
    lines.forEach((line, row) => {
      root.append(svg("text", { x: centre, y: baseline + 18 + 15 * row, class: "tick strong", "text-anchor": "middle" }, line));
    });
    if (isCurrent) root.append(svg("text", { x: centre, y: baseline + 19 + 15 * lines.length, class: "tick", "text-anchor": "middle" }, "current"));
    const label = `${range}%${isCurrent ? ", the current range" : ""}: ${formatPercent(outcome.now, 1)}`;
    const hit = svg("rect", { x: centre - slot / 2, y: top, width: slot, height: plot, class: "hit", tabindex: 0, role: "img", "aria-label": label });
    // Beside the column and clear of its value label, whatever the column's height.
    watch(hit, host, () => tip.show(`${range}%`, [{ key: "line series-1", value: formatPercent(outcome.now, 1), label: isCurrent ? "current range" : "probability" }], centre, top + 8, thick / 2 + 10));
    root.append(hit);
  });
}
```

**File: `site/app.js`**

```javascript
// The page: loads data.json once, keeps the few choices a visitor makes, and redraws.
import * as lib from "./lib.js?v={{BUILD_ID}}";
import { drawCurve, drawOdds, timeChart } from "./charts.js?v={{BUILD_ID}}";

const THUMB = 16; // the slider thumb's width in CSS pixels; style.css sets the same size
const COLUMN_NAMES = { now: "Now", d1: "1 day", w1: "1 week", m1: "1 month" };
const $ = (id) => document.getElementById(id);

const state = { preset: "10Y", range: null, dateIndex: 0, tenorIndex: 0, mode: "even" };
let data;
let yieldSeconds;
let historyChart;
let fedChart;
let lastWidth = 0;

function make(tag, text = null, className = null) {
  const node = document.createElement(tag);
  if (text !== null) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function press(group, attribute, value) {
  for (const button of group.querySelectorAll("button")) {
    button.setAttribute("aria-pressed", String(button.dataset[attribute] === value));
  }
}

/** Lines a slider's travel up with a stretch of the chart above it. */
function placeSlider(slider, left, width) {
  slider.style.marginLeft = `${left - THUMB / 2}px`;
  slider.style.width = `${width + THUMB}px`;
}

function renderHeader() {
  const when = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(data.generated_at));
  const age = lib.ageInDays(data.generated_at, Date.now());
  $("refreshed").textContent = age > 3 ? `Refreshed ${when}. The data is ${age} days old.` : `Refreshed ${when}`;
  if (data.analysis) {
    const link = $("explain");
    link.href = `${data.analysis.file}?v=${encodeURIComponent(data.snapshot_id)}`;
    link.hidden = false;
    $("explain-note").textContent = `AI-written analysis of this data · ${lib.formatDate(data.analysis.generated_at.slice(0, 10))}`;
    const notice = $("ai-notice");
    notice.textContent = `The analysis was written by an AI model (${data.analysis.model}) from the data on this page. It can be wrong. Not investment advice.`;
    notice.hidden = false;
  } else {
    $("explain-off").hidden = false;
    $("explain-note").textContent = "No analysis for this snapshot yet";
  }
}

function renderFed(iso) {
  const fed = data.fed_funds;
  const index = lib.indexOnOrBefore(fed.dates, iso);
  if (index < 0) {
    $("fed-readout").textContent = `No data before ${lib.formatDate(fed.dates[0])}`;
    fedChart.setMarker({ x: lib.dateToSeconds(iso), y: null });
    return;
  }
  const lower = fed.target_lower[index];
  const upper = fed.target_upper[index];
  const target = lower === upper ? lib.formatPercent(lower) : lib.formatRange([lower, upper]);
  $("fed-readout").textContent = `${lib.formatDate(fed.dates[index])} · EFFR ${lib.formatPercent(fed.effr[index])} · target ${target}`;
  fedChart.setMarker({ x: lib.dateToSeconds(iso), y: fed.dates[index] === iso ? fed.effr[index] : null });
}

function renderCurve() {
  const yields = data.yields;
  const day = lib.formatDate(yields.dates[state.dateIndex]);
  const points = lib.curveOn(yields, state.dateIndex);
  const title = `Yield curve on ${day}`;
  $("curve-title").textContent = title;
  const chosen = points.find((point) => point.index === state.tenorIndex);
  const label = yields.tenors[state.tenorIndex].label;
  $("curve-readout").textContent = chosen ? `${label} · ${lib.formatPercent(chosen.value)}` : `${label} was not published on this date`;
  const span = drawCurve($("curve-chart"), { tenors: yields.tenors, points, mode: state.mode, selected: state.tenorIndex, title, onPick: pickTenor });
  placeSlider($("tenor-slider"), span.first, span.last - span.first);
  const rows = points.map((point) => {
    const row = make("tr");
    row.append(make("th", point.label), make("td", lib.formatPercent(point.value)));
    row.firstChild.scope = "row";
    return row;
  });
  $("curve-table").tBodies[0].replaceChildren(...rows);
}

function renderDate() {
  const yields = data.yields;
  const iso = yields.dates[state.dateIndex];
  const value = yields.values[state.tenorIndex][state.dateIndex];
  const label = yields.tenors[state.tenorIndex].label;
  $("date-slider").setAttribute("aria-valuetext", lib.formatDate(iso));
  $("history-readout").textContent =
    value === null ? `${lib.formatDate(iso)} · ${label} was not published` : `${lib.formatDate(iso)} · ${lib.formatPercent(value)}`;
  historyChart.setMarker({ x: yieldSeconds[state.dateIndex], y: value });
  renderCurve();
  renderFed(iso);
}

function renderTenor() {
  const tenor = data.yields.tenors[state.tenorIndex];
  $("history-title").textContent = `${lib.tenorName(tenor.label)} Treasury yield`;
  const slider = $("tenor-slider");
  slider.value = String(state.tenorIndex);
  slider.setAttribute("aria-valuetext", tenor.label);
  historyChart.setData([yieldSeconds, data.yields.values[state.tenorIndex]]);
}

function pickTenor(index) {
  state.tenorIndex = index;
  renderTenor();
  renderDate();
}

function alignDateSlider() {
  const box = historyChart.plotBox();
  if (box) placeSlider($("date-slider"), box.left, box.width);
}

function applyRange(range) {
  const dates = data.yields.dates;
  state.range = range;
  $("from").value = range.from;
  $("to").value = range.to;
  press($("presets"), "preset", state.preset);
  const fallback = Math.max(0, lib.indexOnOrBefore(dates, range.to));
  const span = lib.visibleSpan(dates, range.from, range.to) ?? { first: fallback, last: fallback };
  state.dateIndex = lib.clampIndex(state.dateIndex, span);
  const slider = $("date-slider");
  slider.min = String(span.first);
  slider.max = String(span.last);
  slider.value = String(state.dateIndex);
  const min = lib.dateToSeconds(range.from);
  const max = lib.dateToSeconds(range.to);
  historyChart.setRange(min, max);
  fedChart.setRange(min, max);
  renderDate();
}

function setMode(mode) {
  state.mode = mode;
  press($("modes"), "mode", mode);
  const locked = mode === "scale";
  const wrap = $("tenor-slider-wrap");
  $("tenor-slider").disabled = locked;
  wrap.classList.toggle("is-locked", locked);
  if (locked) wrap.setAttribute("tabindex", "0");
  else wrap.removeAttribute("tabindex");
}

function drawOddsChart() {
  const odds = data.odds;
  const title = `Odds for the ${lib.formatDate(odds.meeting)} decision, by target range`;
  drawOdds($("odds-chart"), { outcomes: odds.outcomes, current: odds.current_range, title });
}

function renderOdds() {
  const odds = data.odds;
  $("odds-title").textContent = `Odds for the ${lib.formatDate(odds.meeting)} decision`;
  $("odds-readout").textContent = `Current range ${lib.formatRange(odds.current_range)} · priced on ${lib.formatDate(odds.priced_on)}`;

  const tiles = [["Cut", odds.summary.cut], ["Hold", odds.summary.hold], ["Hike", odds.summary.hike]].map(([name, value]) => {
    const tile = make("div", null, "tile");
    tile.append(make("span", name, "label"), make("span", lib.formatPercent(value, 1), "value"));
    return tile;
  });
  $("odds-tiles").replaceChildren(...tiles);

  drawOddsChart();

  const head = make("tr");
  head.append(make("th", "Target range"));
  head.firstChild.scope = "col";
  for (const column of odds.columns) {
    const cell = make("th", COLUMN_NAMES[column.key]);
    cell.scope = "col";
    cell.append(make("span", column.date ? lib.formatDayMonth(column.date) : "no data", "sub"));
    head.append(cell);
  }
  $("odds-table").tHead.replaceChildren(head);
  const rows = odds.outcomes.map((outcome) => {
    const row = make("tr");
    const name = make("th", lib.formatRange(outcome.range));
    name.scope = "row";
    if (outcome.range[0] === odds.current_range[0]) name.append(make("span", "current", "sub"));
    row.append(name);
    for (const column of odds.columns) row.append(make("td", lib.formatPercent(outcome[column.key], 1)));
    return row;
  });
  $("odds-table").tBodies[0].replaceChildren(...rows);
}

/** Writes text only when it has changed, so a line that is rewritten every second can still be selected and copied. */
function setText(id, text) {
  const node = $(id);
  if (node.textContent !== text) node.textContent = text;
}

function renderClock() {
  const now = Date.now();
  const meeting = lib.nextMeeting(data.fomc.meetings, now);
  if (!meeting) {
    setText("countdown", "–");
    setText("countdown-when", "No upcoming meeting is listed.");
  } else {
    const two = (value) => String(value).padStart(2, "0");
    const { days, hours, minutes, seconds } = lib.countdownParts(now, meeting.statement_at);
    setText("countdown", `${days}d ${two(hours)}h ${two(minutes)}m ${two(seconds)}s`);
    // The same instant twice: in New York, and where the visitor is, which can be the next day.
    const at = meeting.statement_at;
    setText("countdown-when", `${lib.formatInstant(at, "America/New_York")} in New York · ${lib.formatInstant(at)} ${lib.zoneLabel(at)} your time`);
  }
  $("odds-outdated").hidden = !lib.oddsAreOutdated(data.odds, data.fomc.meetings, now);
  setText("odds-outdated", `These odds were calculated before the ${lib.formatDate(data.odds.meeting)} decision.`);
}

/** Draws the clock now, and again at each whole second after. */
function tick() {
  renderClock();
  setTimeout(tick, 1000 - (Date.now() % 1000));
}

/** After a change of width or colour scheme. The history chart realigns its own slider. */
function redraw() {
  historyChart.rebuild();
  fedChart.rebuild();
  renderCurve();
  drawOddsChart();
}

function start(loaded) {
  data = loaded;
  const yields = data.yields;
  const fed = data.fed_funds;
  const first = yields.dates[0];
  const last = yields.dates[yields.dates.length - 1];
  yieldSeconds = yields.dates.map(lib.dateToSeconds);
  const tenYear = yields.tenors.findIndex((tenor) => tenor.label === "10Y");
  state.tenorIndex = tenYear >= 0 ? tenYear : yields.tenors.length - 1;
  state.dateIndex = yields.dates.length - 1;

  $("page").hidden = false;
  $("notices").hidden = false;
  lastWidth = $("page").clientWidth;

  const tenorSlider = $("tenor-slider");
  tenorSlider.min = "0";
  tenorSlider.max = String(yields.tenors.length - 1);
  for (const id of ["from", "to"]) {
    $(id).min = first;
    $(id).max = last;
  }

  historyChart = timeChart(
    $("history-chart"),
    (theme) => ({ series: [{ stroke: theme.series1, width: 2 }] }),
    (index) => ({
      title: lib.formatDate(yields.dates[index]),
      rows: [{ key: "line series-1", value: lib.formatPercent(yields.values[state.tenorIndex][index]), label: yields.tenors[state.tenorIndex].label }],
    }),
    alignDateSlider,
  );
  fedChart = timeChart(
    $("fed-chart"),
    (theme) => ({
      series: [{ stroke: theme.series1, width: 2 }, { stroke: theme.series2, width: 1 }, { stroke: theme.series2, width: 1 }],
      bands: [{ series: [2, 3], fill: theme.wash2 }],
    }),
    (index) => {
      const lower = fed.target_lower[index];
      const upper = fed.target_upper[index];
      return {
        title: lib.formatDate(fed.dates[index]),
        rows: [
          { key: "line series-1", value: lib.formatPercent(fed.effr[index]), label: "EFFR" },
          { key: "line series-2", value: lower === upper ? lib.formatPercent(lower) : lib.formatRange([lower, upper]), label: "target" },
        ],
      };
    },
  );
  fedChart.setData([fed.dates.map(lib.dateToSeconds), fed.effr, fed.target_upper, fed.target_lower]);

  renderHeader();
  setMode("even");
  renderTenor();
  applyRange(lib.presetRange(state.preset, first, last));
  renderOdds();
  tick();

  if (lib.publishedTargetLags(fed, data.odds)) {
    const note = $("fed-lag");
    note.textContent = `The Fed has moved the target range to ${lib.formatRange(data.odds.current_range)}. The published series shown here catches up within a day or two.`;
    note.hidden = false;
  }

  $("presets").addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    state.preset = button.dataset.preset;
    applyRange(lib.presetRange(state.preset, first, last));
  });
  for (const id of ["from", "to"]) {
    $(id).addEventListener("change", () => {
      const range = lib.customRange($("from").value, $("to").value, first, last);
      if (!range) {
        // Not a usable range: put back the one in force.
        $("from").value = state.range.from;
        $("to").value = state.range.to;
        return;
      }
      state.preset = null;
      applyRange(range);
    });
  }
  $("date-slider").addEventListener("input", (event) => {
    state.dateIndex = Number(event.target.value);
    renderDate();
  });
  tenorSlider.addEventListener("input", (event) => pickTenor(Number(event.target.value)));
  $("modes").addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    setMode(button.dataset.mode);
    renderCurve();
  });

  let pending = 0;
  new ResizeObserver(() => {
    const width = $("page").clientWidth;
    if (width === lastWidth) return;
    lastWidth = width;
    cancelAnimationFrame(pending);
    pending = requestAnimationFrame(redraw);
  }).observe($("page"));
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", redraw);
}

async function main() {
  const response = await fetch("data.json", { cache: "no-cache" });
  if (!response.ok) throw new Error(`data.json answered ${response.status}`);
  start(await response.json());
}

main().catch((error) => {
  const note = $("load-error");
  note.textContent = `The data could not be loaded (${error.message}). Try again in a minute.`;
  note.hidden = false;
});
```

**File: `site/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<meta name="color-scheme" content="light dark">
<title>Macros</title>
<link rel="icon" href="data:,">
<link rel="stylesheet" href="vendor/uPlot.min.css?v={{BUILD_ID}}">
<link rel="stylesheet" href="style.css?v={{BUILD_ID}}">
</head>
<body>
<header class="top">
  <div class="top-main">
    <h1>Macros</h1>
    <a id="explain" class="button" target="_blank" rel="noopener" hidden>Explain Macros</a>
    <span id="explain-off" class="button is-off" aria-disabled="true" hidden>Explain Macros</span>
    <span id="explain-note" class="quiet"></span>
  </div>
  <p id="refreshed" class="quiet"></p>
</header>

<div class="alerts">
  <p id="load-error" class="notice" role="alert" hidden></p>
  <noscript><p class="notice">This page needs JavaScript to draw its charts.</p></noscript>
</div>

<main id="page" hidden>
  <div class="filters" role="group" aria-label="Date range for the two history charts">
    <span class="filters-label">Range</span>
    <div class="segmented" id="presets">
      <button type="button" data-preset="1Y" aria-pressed="false">1Y</button>
      <button type="button" data-preset="5Y" aria-pressed="false">5Y</button>
      <button type="button" data-preset="10Y" aria-pressed="true">10Y</button>
      <button type="button" data-preset="MAX" aria-pressed="false">Max</button>
    </div>
    <label>From <input type="date" id="from"></label>
    <label>To <input type="date" id="to"></label>
  </div>

  <section aria-labelledby="yields-heading">
    <h2 id="yields-heading">US Treasury yields</h2>
    <div class="pair">
      <figure class="card">
        <figcaption>
          <h3 id="history-title">Yield history</h3>
          <p id="history-readout" class="readout"></p>
        </figcaption>
        <div id="history-chart" class="plot" role="img" aria-labelledby="history-title"></div>
        <div class="slider">
          <input type="range" id="date-slider" step="1">
          <label for="date-slider">Date shown on the yield curve</label>
        </div>
      </figure>

      <figure class="card">
        <figcaption class="with-control">
          <div>
            <h3 id="curve-title">Yield curve</h3>
            <p id="curve-readout" class="readout"></p>
          </div>
          <div class="segmented" id="modes" role="group" aria-label="Horizontal axis">
            <button type="button" data-mode="even" aria-pressed="true">Even spacing</button>
            <button type="button" data-mode="scale" aria-pressed="false">True scale</button>
          </div>
        </figcaption>
        <div id="curve-chart" class="plot"></div>
        <div class="slider" id="tenor-slider-wrap" data-hint="Switch to even spacing to pick a tenor">
          <input type="range" id="tenor-slider" step="1">
          <label for="tenor-slider">Tenor shown on the yield history</label>
        </div>
        <details>
          <summary>Show table</summary>
          <table id="curve-table">
            <thead><tr><th scope="col">Tenor</th><th scope="col">Yield</th></tr></thead>
            <tbody></tbody>
          </table>
        </details>
      </figure>
    </div>
  </section>

  <section aria-labelledby="fomc-heading">
    <h2 id="fomc-heading">Next FOMC decision</h2>
    <p id="odds-outdated" class="notice" hidden></p>
    <div class="pair">
      <div class="card glance">
        <div>
          <p class="label">Time to the next statement</p>
          <p id="countdown" class="hero"></p>
          <p id="countdown-when" class="quiet"></p>
        </div>
        <div>
          <h3 id="odds-title">Odds for the decision</h3>
          <div class="tiles" id="odds-tiles"></div>
          <p id="odds-readout" class="readout"></p>
        </div>
      </div>

      <figure class="card">
        <figcaption>
          <h3>Odds by target range</h3>
          <p class="readout">Where the target range would be after the decision, in percent</p>
        </figcaption>
        <div id="odds-chart" class="plot"></div>
      </figure>
    </div>

    <div class="card below">
      <h3>How the odds have moved</h3>
      <div class="aside">
        <div class="scroll">
          <table id="odds-table">
            <thead></thead>
            <tbody></tbody>
          </table>
        </div>
        <p class="quiet">Own calculation from 30-Day Federal Funds futures prices, using <a href="https://www.cmegroup.com/articles/2023/understanding-the-cme-group-fedwatch-tool-methodology.html" target="_blank" rel="noopener noreferrer">the method CME Group publishes</a> for its FedWatch tool. These are not CME FedWatch figures.</p>
      </div>
    </div>
  </section>

  <section aria-labelledby="fed-heading">
    <h2 id="fed-heading">Fed funds rate and target range</h2>
    <figure class="card">
      <figcaption class="with-control">
        <p id="fed-readout" class="readout"></p>
        <ul class="legend">
          <li><span class="key line series-1"></span>Effective rate (EFFR)</li>
          <li><span class="key box series-2"></span>Target range</li>
        </ul>
      </figcaption>
      <div id="fed-chart" class="plot" role="img" aria-labelledby="fed-heading"></div>
      <p id="fed-lag" class="notice" hidden></p>
    </figure>
  </section>
</main>

<footer id="notices" hidden>
  <h2>Sources and notices</h2>
  <ul>
    <li>Yields: U.S. Department of the Treasury, Daily Treasury Par Yield Curve Rates.</li>
    <li>The EFFR is subject to the Terms of Use posted at newyorkfed.org. The New York Fed is not responsible for publication of the EFFR by theta-markets.com, does not sanction or endorse any particular republication, and has no liability for your use.</li>
    <li>Rate odds: own calculation from futures prices. Not investment advice.</li>
    <li id="ai-notice" hidden></li>
  </ul>
  <a class="repo" href="https://github.com/Himanshujoy/Macros" target="_blank" rel="noopener noreferrer" aria-label="Source code on GitHub: Himanshujoy/Macros (opens in a new tab)">
    <svg class="repo-mark" viewBox="0 0 16 16" width="22" height="22" aria-hidden="true" focusable="false"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
    <span class="repo-text">
      <span class="repo-label">Source code on GitHub</span>
      <span class="repo-name">Himanshujoy/Macros</span>
    </span>
    <svg class="repo-out" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false"><path fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" d="M6 3.5h6.5V10M12.5 3.5 4 12"/></svg>
  </a>
</footer>

<script src="vendor/uPlot.iife.min.js?v={{BUILD_ID}}" defer></script>
<script type="module" src="app.js?v={{BUILD_ID}}"></script>
</body>
</html>
```

**File: `site/style.css`**

```css
/* Colours are roles, defined once for light and once for dark. The charts read them from here. */
:root {
  color-scheme: light dark;
  --page: #f9f9f7;
  --surface: #fcfcfb;
  --ink: #0b0b0b;
  --ink-2: #52514e;
  --muted: #898781;
  --grid: #e1e0d9;
  --axis: #c3c2b7;
  --border: rgba(11, 11, 11, 0.1);
  --series-1: #2a78d6;
  --series-2: #eb6834;
  --series-2-wash: rgba(235, 104, 52, 0.14);
  --thumb: 16px;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
}

@media (prefers-color-scheme: dark) {
  :root {
    --page: #0d0d0d;
    --surface: #1a1a19;
    --ink: #ffffff;
    --ink-2: #c3c2b7;
    --muted: #898781;
    --grid: #2c2c2a;
    --axis: #383835;
    --border: rgba(255, 255, 255, 0.1);
    --series-1: #3987e5;
    --series-2: #d95926;
    --series-2-wash: rgba(217, 89, 38, 0.22);
  }
}

* {
  box-sizing: border-box;
}

/* `hidden` must win over any class that sets `display`. */
[hidden] {
  display: none !important;
}

body {
  margin: 0;
  background: var(--page);
  color: var(--ink);
  font-size: 15px;
  line-height: 1.45;
}

.top,
.alerts,
main,
footer {
  max-width: 1240px;
  margin: 0 auto;
  padding: 0 20px;
}

.top {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 24px;
  padding-top: 20px;
  padding-bottom: 12px;
}

.top-main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 16px;
}

h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 650;
}

h2 {
  margin: 28px 0 10px;
  font-size: 17px;
  font-weight: 650;
}

h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

p {
  margin: 0;
}

.quiet {
  color: var(--ink-2);
  font-size: 13px;
}

.readout {
  color: var(--ink-2);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  min-height: 19px;
}

/* A link inside a sentence keeps the sentence's colour and is marked by its underline. */
p a {
  color: inherit;
  text-underline-offset: 2px;
}

p a:hover {
  color: var(--ink);
}

.notice {
  margin-top: 10px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--ink-2);
  font-size: 13px;
}

/* Buttons and the two-or-more-way switches */
.button {
  display: inline-block;
  padding: 8px 16px;
  border: 1px solid var(--ink);
  border-radius: 8px;
  background: var(--ink);
  color: var(--surface);
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
}

.button:hover {
  opacity: 0.88;
}

.button.is-off {
  border-color: var(--border);
  background: transparent;
  color: var(--muted);
  cursor: not-allowed;
}

.segmented {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.segmented button {
  padding: 5px 12px;
  border: 0;
  background: var(--surface);
  color: var(--ink-2);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

.segmented button + button {
  border-left: 1px solid var(--border);
}

.segmented button[aria-pressed="true"] {
  background: var(--ink);
  color: var(--surface);
  font-weight: 600;
}

:focus-visible {
  outline: 2px solid var(--series-1);
  outline-offset: 2px;
}

/* The one filter row, above everything it scopes */
.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
  margin-top: 4px;
  color: var(--ink-2);
  font-size: 13px;
}

.filters-label {
  font-weight: 600;
}

.filters input[type="date"] {
  margin-left: 4px;
  padding: 4px 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: var(--ink);
  font: inherit;
}

/* Cards and layout */
.pair {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
}

.card {
  min-width: 0;
  margin: 0;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
}

.card.below {
  margin-top: 16px;
}

/* The numbers to take in at a glance: two groups, spread over the card's height.
   The card is a size container, so the countdown can scale with the card's width. */
.glance {
  display: flex;
  flex-direction: column;
  justify-content: space-around;
  gap: 20px;
  container-type: inline-size;
}

section > .notice {
  margin: 0 0 12px;
}

figcaption {
  margin-bottom: 8px;
}

figcaption.with-control {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px 16px;
}

.plot {
  position: relative;
  overflow: hidden;
}

.plot svg {
  display: block;
}

/* Sliders: a fixed 16px thumb, so their travel can be lined up with the chart above */
.slider {
  position: relative;
  margin-top: 6px;
}

.slider label {
  display: block;
  color: var(--ink-2);
  font-size: 12px;
}

input[type="range"] {
  display: block;
  height: 28px;
  margin: 0;
  background: transparent;
  cursor: pointer;
  -webkit-appearance: none;
  appearance: none;
}

input[type="range"]::-webkit-slider-runnable-track {
  height: 4px;
  border-radius: 2px;
  background: var(--axis);
}

input[type="range"]::-moz-range-track {
  height: 4px;
  border-radius: 2px;
  background: var(--axis);
}

input[type="range"]::-webkit-slider-thumb {
  box-sizing: border-box;
  width: var(--thumb);
  height: var(--thumb);
  margin-top: -6px;
  border: 2px solid var(--surface);
  border-radius: 50%;
  background: var(--series-1);
  -webkit-appearance: none;
  appearance: none;
}

input[type="range"]::-moz-range-thumb {
  box-sizing: border-box;
  width: var(--thumb);
  height: var(--thumb);
  border: 2px solid var(--surface);
  border-radius: 50%;
  background: var(--series-1);
}

input[type="range"]:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.slider.is-locked {
  cursor: not-allowed;
}

.slider.is-locked::after {
  content: attr(data-hint);
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  padding: 5px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--ink);
  color: var(--surface);
  font-size: 12px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
}

.slider.is-locked:hover::after,
.slider.is-locked:focus::after {
  opacity: 1;
}

/* SVG charts take their colours from the same roles */
.grid {
  stroke: var(--grid);
  stroke-width: 1;
}

.axis {
  stroke: var(--axis);
  stroke-width: 1;
}

.tick {
  fill: var(--muted);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.tick.strong {
  fill: var(--ink-2);
}

.line {
  fill: none;
  stroke: var(--series-1);
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.dot {
  fill: var(--series-1);
  stroke: var(--surface);
  stroke-width: 2;
}

/* The line at the chosen tenor: the same weight and colour as the one at the chosen date. */
.marker {
  stroke: var(--ink-2);
  stroke-width: 1;
  shape-rendering: crispEdges;
}

.column {
  fill: var(--series-1);
}

/* A value label keeps a rim of the surface colour, so it stays readable where a line runs behind it. */
.point-label {
  fill: var(--ink);
  stroke: var(--surface);
  stroke-width: 4px;
  stroke-linejoin: round;
  paint-order: stroke;
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

/* Hit targets are invisible until the pointer or the keyboard is on them. */
.hit {
  fill: var(--ink);
  fill-opacity: 0;
  outline: none;
}

.hit:hover {
  fill-opacity: 0.06;
}

.hit.pick {
  cursor: pointer;
}

.hit:focus-visible {
  stroke: var(--series-1);
  stroke-width: 2;
}

/* uPlot's cursor line: a solid hairline, not its default dashes */
.u-hz .u-cursor-x {
  border-right: 1px solid var(--axis);
}

/* Tooltip, legend and their colour keys */
.tip {
  position: absolute;
  z-index: 2;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
  font-size: 12px;
  white-space: nowrap;
  pointer-events: none;
}

.tip-title {
  color: var(--ink-2);
}

.tip-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-variant-numeric: tabular-nums;
}

.tip-row span:last-child {
  color: var(--ink-2);
}

.key {
  display: inline-block;
  flex: none;
}

.key.line {
  width: 14px;
  height: 2px;
  border-radius: 1px;
}

.key.box {
  width: 12px;
  height: 10px;
  border-radius: 2px;
}

.key.series-1 {
  background: var(--series-1);
}

.key.series-2 {
  background: var(--series-2);
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  margin: 0;
  padding: 0;
  list-style: none;
  color: var(--ink-2);
  font-size: 13px;
}

.legend li {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* Numbers that stand alone */
.label {
  color: var(--ink-2);
  font-size: 13px;
}

/* The countdown. It ticks every second, so its digits are all one width and the line stays still.
   Its size follows the card's width, so days to seconds always fit on one line. The first size
   is for a browser that does not know container units. */
.hero {
  margin: 2px 0 6px;
  font-size: 40px;
  font-size: clamp(28px, 10.5cqw, 56px);
  font-weight: 650;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
  white-space: nowrap;
}

.tiles {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 28px;
  margin: 8px 0;
}

.tile {
  display: flex;
  flex-direction: column;
}

.tile .value {
  font-size: 24px;
  font-weight: 650;
}

/* Tables: the same numbers without the chart */
table {
  width: 100%;
  margin-top: 8px;
  border-collapse: collapse;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

th,
td {
  padding: 5px 8px;
  border-bottom: 1px solid var(--grid);
  text-align: right;
  white-space: nowrap;
}

/* A table too wide for a narrow screen scrolls inside its card, not the page. */
.scroll {
  overflow-x: auto;
}

th:first-child {
  text-align: left;
}

thead th {
  color: var(--ink-2);
  font-weight: 600;
  vertical-align: bottom;
}

tbody th {
  font-weight: 600;
}

.sub {
  display: block;
  color: var(--ink-2);
  font-size: 12px;
  font-weight: 400;
}

details {
  margin-top: 8px;
}

summary {
  width: max-content;
  color: var(--ink-2);
  font-size: 13px;
  cursor: pointer;
}

#curve-table {
  max-width: 260px;
}

/* A table with a note beside it, or under it when there is no room. */
.aside {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 40px;
}

.aside .scroll {
  flex: 1 1 420px;
  max-width: 620px;
}

.aside .quiet {
  flex: 1 1 260px;
}

footer {
  margin-top: 32px;
  padding-bottom: 40px;
  color: var(--ink-2);
  font-size: 13px;
}

footer h2 {
  margin-top: 0;
  font-size: 14px;
}

footer ul {
  margin: 0;
  padding-left: 18px;
}

footer li + li {
  margin-top: 4px;
}

/* The link to the code: the mark, two lines of text and an arrow, as one target. */
.repo {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  padding: 8px 14px 8px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  color: var(--ink);
  text-decoration: none;
}

.repo:hover {
  border-color: var(--muted);
}

.repo-mark,
.repo-out {
  flex: none;
}

.repo-text {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.repo-label {
  color: var(--ink-2);
  font-size: 12px;
}

.repo-name {
  font-size: 14px;
  font-weight: 600;
}

.repo-out {
  color: var(--muted);
}

@media (max-width: 900px) {
  .pair {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 480px) {
  .top,
  .alerts,
  main,
  footer {
    padding-left: 12px;
    padding-right: 12px;
  }

  .card {
    padding: 12px;
  }

  th,
  td {
    padding: 5px 4px;
  }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
node --test tests/js/lib.test.js
.venv/bin/python -m pytest tests/test_site_helpers.py tests/test_site_page.py
```

Expected: Node reports `pass 25` and `fail 0`; pytest reports `9 passed`.

- [ ] **Step 5: Check the scripts parse, and run the whole suite**

Run:

```bash
node --check site/lib.js && node --check site/charts.js && node --check site/app.js && echo "scripts parse"
.venv/bin/python -m pytest
```

Expected: `scripts parse`, then `243 passed`.

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: the seven above. Suggested message: `feat: tenor marker on the curve, seconds in the countdown, links to GitHub and to CME's method`.

---

### Task 2: Try it

This task runs the real commands. It adds no code. The refresh makes six read-only requests.

- [ ] **Step 1: Build**

Run: `.venv/bin/python -m macro refresh`

Expected: the five summary lines, ending `Built dist/ (no analysis yet) and work/facts.json`.

- [ ] **Step 2: Start the preview in one terminal**

Run: `.venv/bin/python -m macro preview`

Expected: `serving .../dist on http://127.0.0.1:8081/`, and it keeps running.

- [ ] **Step 3: Look at it**

Open `http://127.0.0.1:8081/` in a browser, with the developer console open. Check each of these:

| Try | Expect |
|---|---|
| Load the page | No errors in the console |
| The curve, in even spacing | A vertical line through the selected tenor, above the slider's thumb, with the value beside it |
| Drag the tenor slider, or click a point | The line moves with the selection |
| Press "True scale" | The line is gone. Press "Even spacing" and it is back |
| The countdown | Days, hours, minutes and seconds on one line, ticking once a second without the line shifting |
| The line under the countdown | Both times in the same form, such as `Wed 28 Oct, 2:00 pm in New York · Wed 28 Oct, 11:30 pm IST your time` |
| The odds note | "the method CME Group publishes" is underlined and opens CME's article in a new tab |
| The end of the page | The GitHub mark with "Source code on GitHub" and `Himanshujoy/Macros`, opening the repository in a new tab |
| Narrow the window to phone width | The countdown still fits on one line, and nothing scrolls sideways |

- [ ] **Step 4: Stop the preview**

Press Ctrl-C in the first terminal.

- [ ] **Step 5: Checkpoint**

Stop and report what the owner saw. Nothing new to commit.
