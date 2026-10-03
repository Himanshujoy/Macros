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

function renderClock() {
  const now = Date.now();
  const meeting = lib.nextMeeting(data.fomc.meetings, now);
  if (!meeting) {
    $("countdown").textContent = "–";
    $("countdown-when").textContent = "No upcoming meeting is listed.";
  } else {
    const { days, hours, minutes } = lib.countdownParts(now, meeting.statement_at);
    $("countdown").textContent = `${days}d ${String(hours).padStart(2, "0")}h ${String(minutes).padStart(2, "0")}m`;
    // The same instant twice: in New York, and where the visitor is, which can be the next day.
    const at = new Date(meeting.statement_at);
    const parts = { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit", hour12: true };
    const newYork = new Intl.DateTimeFormat("en-GB", { ...parts, timeZone: "America/New_York" }).format(at);
    const local = new Intl.DateTimeFormat(undefined, { ...parts, timeZoneName: "short" }).format(at);
    $("countdown-when").textContent = `${newYork} in New York · ${local} your time`;
  }
  const outdated = $("odds-outdated");
  outdated.hidden = !lib.oddsAreOutdated(data.odds, data.fomc.meetings, now);
  outdated.textContent = `These odds were calculated before the ${lib.formatDate(data.odds.meeting)} decision.`;
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
  renderClock();
  setInterval(renderClock, 30000);

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
