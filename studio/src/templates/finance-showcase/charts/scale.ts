/**
 * Scales, ticks and path geometry. Pure — no React, no Remotion, no DOM.
 *
 * Split out for the same reason projection.ts was: this is the arithmetic that
 * decides where every mark lands, and it has to be checkable by importing the
 * real functions rather than a re-implementation that can be just as wrong.
 *
 * Axis convention, fixed once here so all nine chart types agree:
 *   y increases UPWARD. Every renderer works in "plot space" where y=0 is the
 *   baseline and y=1 is the top, and the frame flips it. Chart code that has to
 *   remember which way is up is chart code that will get it wrong.
 */

import type {Curve} from './options';

export type Extent = [number, number];

export const extent = (values: readonly number[]): Extent => {
  if (!values.length) return [0, 1];
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values) {
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  return [lo, hi];
};

/** Linear map from a data domain to a pixel range. */
export const linear = (
  domain: Extent,
  range: Extent
): ((v: number) => number) => {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  const span = d1 - d0;
  if (Math.abs(span) < 1e-12) return () => (r0 + r1) / 2;
  return (v: number) => r0 + ((v - d0) / span) * (r1 - r0);
};

/**
 * A domain that starts at zero unless the data genuinely does not.
 *
 * A bar chart whose baseline is not zero lies about its magnitudes, because
 * length is the encoding. A line chart may use a fitted domain, so the caller
 * decides with `zeroBased`.
 */
export const domainFor = (values: readonly number[], zeroBased: boolean): Extent => {
  const [lo, hi] = extent(values);
  if (!zeroBased) return [lo, hi];
  return [Math.min(0, lo), Math.max(0, hi)];
};

/**
 * The nice-number ladder.
 *
 * 2.5 is in it and not only because quarters are nice: without it, a 0..1 axis
 * asked for four intervals jumps straight from 0.2 to 0.5 and gives three
 * ticks, because 2.5 rounds UP to 5. With it, 0..1 by 4 gives 0/0.25/0.5/0.75/1.
 */
const NICE_STEPS = [1, 2, 2.5, 5, 10];

/**
 * Tick values on a nice-number boundary.
 *
 * The "nice" numbers are not a nicety: a y axis labelled 0, 33.3, 66.7 makes
 * the reader do arithmetic to compare two bars. Nearest-round-step, not
 * count-intervals — that is the difference between 0/20/40/60/80/100 and
 * 0/27.4/54.8/82.2.
 *
 * Rounds UP to the next nice step, never down: too many gridlines is the worse
 * failure for this engine's look, and rounding down can also produce more ticks
 * than the caller asked for.
 *
 * A reversed range is normalised rather than refused — a caller with descending
 * data still gets an axis.
 */
export const niceTicks = (min: number, max: number, count = 5): number[] => {
  if (!Number.isFinite(min) || !Number.isFinite(max) || count < 1) return [];
  const lo = Math.min(min, max);
  const hi = Math.max(min, max);
  if (Math.abs(hi - lo) < 1e-12) return [lo];
  const rawStep = (hi - lo) / count;
  const mag = 10 ** Math.floor(Math.log10(Math.abs(rawStep)));
  const norm = Math.abs(rawStep) / mag;
  const step = (NICE_STEPS.find((n) => n >= norm - 1e-9) ?? 10) * mag;
  const first = Math.ceil(lo / step - 1e-9) * step;
  const out: number[] = [];
  for (let v = first; v <= hi + step * 1e-9; v += step) {
    // re-round to kill 0.30000000000000004 from accumulated float addition.
    // `+ 0` also kills NEGATIVE ZERO, which arrives here because
    // Math.ceil(-1e-9) is -0 — and -0 renders as "-0" through toLocaleString,
    // so an axis reads "0, 20, 40, -0" with the minus on the wrong side.
    out.push(Math.round(v / step) * step + 0);
  }
  return out;
};

/** Evenly spaced band centres plus a bandwidth, for categorical axes. */
export const band = (
  n: number,
  range: Extent,
  paddingRatio = 0.2
): {at: (i: number) => number; width: number; step: number} => {
  const [r0, r1] = range;
  const total = r1 - r0;
  const n_safe = Math.max(1, n);
  const step = total / n_safe;
  const width = step * (1 - Math.min(0.9, Math.max(0, paddingRatio)));
  const offset = (step - width) / 2;
  return {
    at: (i: number) => r0 + step * i + offset + width / 2,
    width,
    step,
  };
};

export type Point = {x: number; y: number};

const round = (v: number) => Math.round(v * 100) / 100;

/** SVG path data for a polyline through `pts`, y already flipped to pixels. */
export const linePath = (pts: readonly Point[], curve: Curve = 'linear'): string => {
  if (!pts.length) return '';
  if (curve === 'step' || pts.length < 3) {
    if (pts.length === 1) return `M ${round(pts[0].x)} ${round(pts[0].y)}`;
    let d = `M ${round(pts[0].x)} ${round(pts[0].y)}`;
    for (let i = 1; i < pts.length; i += 1) {
      d += ` L ${round(pts[i - 1].x)} ${round(pts[i - 1].y)} L ${round(pts[i].x)} ${round(pts[i - 1].y)}`;
    }
    d += ` L ${round(pts[pts.length - 1].x)} ${round(pts[pts.length - 1].y)}`;
    return d;
  }
  if (curve === 'linear') {
    return pts.map((p, i) => `${i ? 'L' : 'M'} ${round(p.x)} ${round(p.y)}`).join(' ');
  }
  return monotonePath(pts);
};

/**
 * Monotone cubic interpolation (Fritsch–Carlson).
 *
 * Chosen over a plain Catmull-Rom because a Catmull-Rom spline overshoots on a
 * sharp peak, and an overshoot in a revenue chart draws a dip that is not in
 * the data. Monotone guarantees the curve never exceeds its data range — which
 * for a chart is not a nicety, it is the difference between the picture and the
 * truth.
 */
const monotonePath = (pts: readonly Point[]): string => {
  const n = pts.length;
  if (n < 2) return '';
  const dx: number[] = [];
  const dy: number[] = [];
  const slope: number[] = [];
  for (let i = 0; i < n - 1; i += 1) {
    dx.push(pts[i + 1].x - pts[i].x);
    dy.push(pts[i + 1].y - pts[i].y);
    slope.push(dx[i] === 0 ? 0 : dy[i] / dx[i]);
  }
  const m: number[] = [slope[0]];
  for (let i = 1; i < n - 1; i += 1) {
    if (slope[i - 1] * slope[i] <= 0) {
      m.push(0); // a local extremum: flat tangent, so no overshoot
    } else {
      const w1 = 2 * dx[i] + dx[i - 1];
      const w2 = dx[i] + 2 * dx[i - 1];
      m.push((w1 + w2) / (w1 / slope[i - 1] + w2 / slope[i]));
    }
  }
  m.push(slope[n - 2]);

  let d = `M ${round(pts[0].x)} ${round(pts[0].y)}`;
  for (let i = 0; i < n - 1; i += 1) {
    const h = dx[i] / 3;
    d += ` C ${round(pts[i].x + h)} ${round(pts[i].y + h * m[i])},` +
         ` ${round(pts[i + 1].x - h)} ${round(pts[i + 1].y - h * m[i + 1])},` +
         ` ${round(pts[i + 1].x)} ${round(pts[i + 1].y)}`;
  }
  return d;
};

/** Close a line path down to a baseline to make an area fill. */
export const areaPath = (pts: readonly Point[], baselineY: number, curve: Curve = 'linear'): string => {
  if (!pts.length) return '';
  return `${linePath(pts, curve)} L ${round(pts[pts.length - 1].x)} ${round(baselineY)}` +
         ` L ${round(pts[0].x)} ${round(baselineY)} Z`;
};

// ── number formatting ───────────────────────────────────────────────────────

/**
 * Format a value for display.
 *
 * `auto` is the interesting one: it picks by magnitude, because a chart that
 * shows 1200000 as "1200000" in a 200px column has not formatted the number, it
 * has refused to. Returns the UNIT too when it compacted, so the caller can
 * label it once rather than repeating it on every mark.
 */
export const formatValue = (
  v: number,
  format: 'auto' | 'int' | 'one' | 'two' | 'percent' | 'compact' = 'auto'
): {text: string; unit: string} => {
  if (!Number.isFinite(v)) return {text: '—', unit: ''};
  // a graph can supply -0 directly, so the guard cannot live only in niceTicks
  if (Object.is(v, -0)) v = 0;
  if (format === 'percent') {
    return {text: `${trimZeros((v * 100).toFixed(1))}%`, unit: ''};
  }
  if (format === 'int') return {text: Math.round(v).toLocaleString('en-US'), unit: ''};
  if (format === 'one') return {text: trimZeros(v.toFixed(1)), unit: ''};
  if (format === 'two') return {text: trimZeros(v.toFixed(2)), unit: ''};

  const abs = Math.abs(v);
  if (format === 'compact' || (format === 'auto' && abs >= 10_000)) {
    const units: [number, string][] = [[1e12, 'T'], [1e9, 'B'], [1e6, 'M'], [1e3, 'K']];
    for (const [scale, suffix] of units) {
      if (abs >= scale) return {text: trimZeros((v / scale).toFixed(1)), unit: suffix};
    }
    return {text: Math.round(v).toLocaleString('en-US'), unit: ''};
  }
  if (format === 'auto' && abs < 1 && abs > 0) {
    return {text: trimZeros(v.toFixed(2)), unit: ''};
  }
  return {text: Math.round(v).toLocaleString('en-US'), unit: ''};
};

/** 3.0 -> 3, 3.50 -> 3.5. A chart showing "3.0" is showing padding. */
export const trimZeros = (s: string): string =>
  s.includes('.') ? s.replace(/\.?0+$/, '') : s;

/**
 * Snap label rectangles apart vertically.
 *
 * The cheapest correct answer to "labels collide": keep the order, push each
 * label away from the previous one by half the overlap, and stop at the band
 * edges. A full label-placement solver is not worth it here because value
 * labels in these charts are already ordered by value, so the only ambiguity
 * is a tie, and a tie is exactly the case a nudge fixes.
 *
 * Returns the same length as `positions`, in pixels.
 */
export const declutter = (positions: readonly number[], heights: readonly number[], min = 0, max = 1080): number[] => {
  const out = positions.slice();
  for (let i = 1; i < out.length; i += 1) {
    const need = out[i - 1] + (heights[i - 1] + heights[i]) / 2;
    if (out[i] < need) out[i] = need;
  }
  // if the last label ran past the bottom, push the stack back up
  const last = out.length - 1;
  if (last >= 0 && out[last] + heights[last] / 2 > max) {
    const overshoot = out[last] + heights[last] / 2 - max;
    for (let i = 0; i <= last; i += 1) {
      out[i] -= overshoot;
      if (out[i] - heights[i] / 2 < min) break;
    }
  }
  return out;
};
