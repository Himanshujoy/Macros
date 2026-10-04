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
