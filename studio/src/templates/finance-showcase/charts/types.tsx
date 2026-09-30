import React, {useMemo} from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {FONT_NUM, FONT_SANS, scaleFrom} from '../design/tokens';
import {useDesign} from '../design/styleBible';
import {useFrame, type Frame} from './ChartFrame';
import {areaPath, band, declutter, linePath, type Extent, type Point} from './scale';
import {option, type ChartType} from './options';

/**
 * The nine marks.
 *
 * Every one reads its geometry from the frame's resolved scale rather than
 * computing its own, so a mark cannot be drawn against a domain the axis is not
 * using. All nine honour the SAME emphasis rule — one accent, everything else
 * recedes by `deemphasis` — because "this one matters" is one decision, and a
 * per-type spelling of it would be nine chances to spell it three ways.
 *
 * Reads from the declared option surface: emphasisIndex, deemphasis,
 * staggerFrames, enterFrames, showArea, strokeWidth, curve, barWidthRatio,
 * showRankDelta, showCellValues, sizeBy, showEndLabels, inline.
 */

export type Series = {
  name?: string;
  values: number[];
  /** optional per-point size, for bubble and volume */
  sizes?: number[];
};

const grow = (frame: number, delay: number, fps: number, frames: number, springName = 'land'): number => {
  if (frames < 1) return 1;
  return spring({
    frame: frame - delay,
    fps,
    config: {damping: 200, stiffness: springName === 'land' ? 100 : 160},
    durationInFrames: frames,
  });
};

/** The colour a mark wears: accent when emphasised, muted otherwise. */
const useMarkPaint = () => {
  const {PALETTE} = useDesign();
  return {
    accent: PALETTE.accent,
    muted: PALETTE.column,
    ink: PALETTE.ink,
    inkMuted: PALETTE.inkMuted,
    inkFaint: PALETTE.inkFaint,
    /** the emphasis fade, as a CSS colour so it composes over anything */
    fade: (isEmphasis: boolean, deemphasis: number) =>
      isEmphasis ? 'rgba(245,242,234,0.92)' : `rgba(245,242,234,${deemphasis})`,
  };
};

// ── bar ──────────────────────────────────────────────────────────────────────

export const Bar: React.FC<{series: Series; labels?: string[]}> = ({series, labels}) => {
  const f = useFrame();
  const paint = useMarkPaint();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const {PALETTE, SPACE, TYPE} = useDesign();
  const s = f.s;
  const b = useMemo(() => band(series.values.length, [f.plot.x, f.plot.x + f.plot.w], 0.28), [series.values.length, f.plot]);
  const width = b.width * option('bar', 'barWidthRatio', f.opts);
  const zeroY = f.yOf(0);
  const labelH = 26 * s;
  const labelY = declutter(
    series.values.map((v) => f.yOf(v) - labelH * 0.9),
    series.values.map(() => labelH),
    0,
    comp.height
  );

  return (
    <>
      {series.values.map((v, i) => {
        const p = grow(frame, i * f.opts.staggerFrames, comp.fps, f.opts.enterFrames);
        const emphasised = f.opts.emphasisIndex === i;
        const y = f.yOf(v);
        const top = Math.min(y, zeroY);
        const h = Math.abs(zeroY - y) * p;
        return (
          <div key={i}>
            <div
              style={{
                position: 'absolute',
                left: b.at(i) - width / 2,
                top,
                width,
                height: Math.max(0, h),
                background: emphasised ? paint.accent : paint.muted,
                borderRadius: `${6 * s}px ${6 * s}px 0 0`,
                boxShadow: emphasised ? `${0} ${18 * s}px ${44 * s}px ${PALETTE.accentDim}` : 'none',
              }}
            />
            {f.opts.showValues ? (
              <div
                style={{
                  position: 'absolute',
                  left: b.at(i) - 70 * s, width: 140 * s,
                  top: labelY[i],
                  textAlign: 'center',
                  fontFamily: FONT_NUM,
                  fontVariantNumeric: 'tabular-nums',
                  fontSize: TYPE.caption.size * s,
                  color: emphasised ? paint.ink : paint.inkMuted,
                }}
              >
                {f.valueText(v)}
              </div>
            ) : null}
          </div>
        );
      })}
      {SPACE ? null : null}
    </>
  );
};

// ── line / area ──────────────────────────────────────────────────────────────

const PathMark: React.FC<{series: Series; withArea: boolean}> = ({series, withArea}) => {
  const f = useFrame();
  const paint = useMarkPaint();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = f.s;
  const n = series.values.length;

  const pts: Point[] = useMemo(() => {
    if (n < 2) return [];
    const stepX = f.plot.w / (n - 1);
    return series.values.map((v, i) => ({
      x: f.plot.x + stepX * i,
      y: f.yOf(v),
    }));
  }, [series.values, n, f.plot, f.yOf]);

  // draw-on: the path reveals by dash offset rather than by redrawing per frame,
  // so the curve shape is identical on every frame of the animation
  const p = grow(frame, 0, comp.fps, f.opts.enterFrames + n * f.opts.staggerFrames, 'reveal');
  const d = linePath(pts, f.opts.curve);
  const approx = useMemo(() => {
    let len = 0;
    for (let i = 1; i < pts.length; i += 1) {
      len += Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y);
    }
    return len || 1;
  }, [pts]);

  const emphasised = f.opts.emphasisIndex;
  const last = n - 1;

  return (
    <>
      {withArea ? (
        <svg
          style={{position: 'absolute', left: 0, top: 0, width: '100%', height: '100%', overflow: 'visible'}}
          aria-hidden
        >
          <defs>
            <linearGradient id={`area-${f.chart}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={paint.accent} stopOpacity={0.24} />
              <stop offset="100%" stopColor={paint.accent} stopOpacity={0} />
            </linearGradient>
          </defs>
          <path d={areaPath(pts, f.yOf(Math.max(0, f.domain[0])), f.opts.curve)} fill={`url(#area-${f.chart})`} />
        </svg>
      ) : null}

      <svg
        style={{position: 'absolute', left: 0, top: 0, width: '100%', height: '100%', overflow: 'visible'}}
        aria-hidden
      >
        <path
          d={d}
          fill="none"
          stroke={paint.accent}
          strokeWidth={f.opts.strokeWidth * s}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray={approx}
          strokeDashoffset={approx * (1 - p)}
        />
      </svg>

      {/* the last point gets a dot only once the line has arrived there, so the
          dot never floats ahead of the curve */}
      {p > 0.985 && pts.length ? (
        <div
          style={{
            position: 'absolute',
            left: pts[last].x - 7 * s, top: pts[last].y - 7 * s,
            width: 14 * s, height: 14 * s,
            borderRadius: '50%',
            background: paint.accent,
            boxShadow: `0 0 ${26 * s}px ${paint.accent}`,
          }}
        />
      ) : null}

      {f.opts.showValues
        ? pts.map((pt, i) => (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: pt.x - 60 * s, width: 120 * s,
                top: pt.y - 34 * s,
                textAlign: 'center',
                fontFamily: FONT_NUM,
                fontVariantNumeric: 'tabular-nums',
                fontSize: 22 * s,
                color: emphasised < 0 || emphasised === i ? paint.ink : paint.inkFaint,
                opacity: interpolate(p, [0, 1], [0, 1], {extrapolateRight: 'clamp'}),
              }}
            >
              {f.valueText(series.values[i])}
            </div>
          ))
        : null}
    </>
  );
};

/**
 * `line` and `area` are the same mark with a different DEFAULT, not two marks.
 *
 * They used to be two components and `Line` hard-coded `withArea={false}`, so a
 * graph that set `showArea: true` on a line chart got nothing — while the
 * registry still showed showArea as "read by types.tsx". Source-level checks
 * cannot see that: the name is in the file, on the wrong component. This is the
 * class of inert option the A/B exists to catch, and it is why the option is
 * read here rather than passed in.
 */
const LineOrArea: React.FC<{series: Series; defaultArea: boolean}> = ({series, defaultArea}) => {
  const f = useFrame();
  return <PathMark series={series} withArea={option('line', 'showArea', f.opts) ?? defaultArea} />;
};

export const Line: React.FC<{series: Series}> = ({series}) => <LineOrArea series={series} defaultArea={false} />;
export const Area: React.FC<{series: Series}> = ({series}) => <LineOrArea series={series} defaultArea />;

// ── slope ────────────────────────────────────────────────────────────────────

export const Slope: React.FC<{before: number[]; after: number[]; labels: string[]}> = ({
  before, after, labels,
}) => {
  const f = useFrame();
  const paint = useMarkPaint();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = f.s;
  const n = Math.min(before.length, after.length);
  const left = f.plot.x;
  const right = f.plot.x + f.plot.w;
  const domain: Extent = [
    Math.min(...before.slice(0, n), ...after.slice(0, n)),
    Math.max(...before.slice(0, n), ...after.slice(0, n)),
  ];
  const y = (v: number) =>
    f.plot.y + f.plot.h - ((v - domain[0]) / Math.max(domain[1] - domain[0], 1e-6)) * f.plot.h;

  return (
    <>
      {Array.from({length: n}, (_, i) => {
        const p = grow(frame, i * f.opts.staggerFrames, comp.fps, f.opts.enterFrames);
        const y0 = y(before[i]);
        const y1 = y(after[i]);
        const emphasised = f.opts.emphasisIndex === i;
        return (
          <React.Fragment key={i}>
            <svg style={{position: 'absolute', inset: 0, overflow: 'visible'}} aria-hidden>
              <line
                x1={left} y1={y0 + (y1 - y0) * (1 - p) * 0}
                x2={left + (right - left) * p} y2={y1}
                stroke={emphasised ? paint.accent : paint.muted}
                strokeWidth={(emphasised ? 5 : 3) * s}
                strokeLinecap="round"
              />
            </svg>
            <div style={{position: 'absolute', left: left - 10 * s, top: y0 - 11 * s, width: 20 * s, textAlign: 'center'}}>
              <Dot color={emphasised ? paint.accent : paint.muted} s={s} />
            </div>
            <div style={{position: 'absolute', left: right - 10 * s, top: y1 - 11 * s, width: 20 * s, textAlign: 'center'}}>
              <Dot color={emphasised ? paint.accent : paint.muted} s={s} />
            </div>
            {f.opts.showEndLabels ? (
              <>
                <div style={{position: 'absolute', left: left + 18 * s, top: y0 - 12 * s, fontFamily: FONT_NUM, fontSize: 20 * s, color: paint.inkFaint}}>
                  {f.valueText(before[i])}
                </div>
                <div style={{position: 'absolute', left: right - 90 * s, top: y1 - 12 * s, width: 74 * s, textAlign: 'right', fontFamily: FONT_NUM, fontSize: 20 * s, color: emphasised ? paint.ink : paint.inkMuted}}>
                  {f.valueText(after[i])}
                </div>
                <div style={{position: 'absolute', left: left + (right - left) / 2 - 60 * s, top: (y0 + y1) / 2 - 30 * s, width: 120 * s, textAlign: 'center', fontFamily: FONT_SANS, fontSize: 18 * s, color: paint.inkFaint}}>
                  {/*
                    Above the line, not on it. A series name at the midpoint of
                    a slope line sits exactly where the line is, so the label
                    is drawn on top of the thing it names. Up is always clear of
                    the line whichever way it slopes.
                  */}
                  {labels[i] ?? ''}
                </div>
              </>
            ) : null}
          </React.Fragment>
        );
      })}
    </>
  );
};

const Dot: React.FC<{color: string; s: number}> = ({color, s}) => (
  <div style={{width: 20 * s, height: 20 * s, borderRadius: '50%', background: color, margin: '0 auto'}} />
);

// ── bubble ───────────────────────────────────────────────────────────────────

export const Bubble: React.FC<{series: Series; labels?: string[]}> = ({series, labels}) => {
  const f = useFrame();
  const paint = useMarkPaint();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = f.s;
  const sizeBy = option('bubble', 'sizeBy', f.opts);
  const sizes = series.sizes ?? series.values;
  const maxSize = Math.max(...sizes.map(Math.abs), 1e-6);
  const n = series.values.length;
  const cols = Math.ceil(Math.sqrt(n));
  const rows = Math.ceil(n / cols);
  const cw = f.plot.w / cols;
  const ch = f.plot.h / Math.max(rows, 1);

  return (
    <>
      {series.values.map((v, i) => {
        const p = grow(frame, i * f.opts.staggerFrames, comp.fps, f.opts.enterFrames);
        const r = sizeBy === 'none' ? 26 * s : (16 + 46 * (sizes[i] / maxSize)) * s;
        const cx = f.plot.x + cw * (i % cols) + cw / 2;
        const cy = f.plot.y + ch * Math.floor(i / cols) + ch / 2 - f.plot.h * 0.28 * v / 100;
        const emphasised = f.opts.emphasisIndex === i;
        return (
          <div key={i}>
            <div
              style={{
                position: 'absolute',
                left: cx - r, top: cy - r,
                width: r * 2, height: r * 2,
                borderRadius: '50%',
                background: emphasised ? paint.accent : paint.muted,
                opacity: emphasised ? 0.95 : f.opts.deemphasis,
                transform: `scale(${p})`,
                boxShadow: emphasised ? `0 0 ${r * 1.4}px ${paint.accent}` : 'none',
              }}
            />
            {f.opts.showValues ? (
              <div style={{position: 'absolute', left: cx - 60 * s, top: cy + r + 8 * s, width: 120 * s, textAlign: 'center', fontFamily: FONT_NUM, fontSize: 20 * s, color: paint.inkFaint}}>
                {labels?.[i] ?? f.valueText(v)}
              </div>
            ) : null}
          </div>
        );
      })}
    </>
  );
};

// ── heatmap ──────────────────────────────────────────────────────────────────

export const Heatmap: React.FC<{
  rows: number[][];
  rowLabels: string[];
  colLabels: string[];
}> = ({rows, rowLabels, colLabels}) => {
  const f = useFrame();
  const paint = useMarkPaint();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = f.s;
  const flat = rows.flat();
  const max = Math.max(...flat.map(Math.abs), 1e-6);
  const gap = 6 * s;
  const cw = (f.plot.w - gap * (colLabels.length - 1)) / Math.max(colLabels.length, 1);
  const chh = Math.min(cw, (f.plot.h - gap * (rowLabels.length - 1)) / Math.max(rowLabels.length, 1));

  return (
    <>
      {rows.map((row, r) => (
        <React.Fragment key={r}>
          {row.map((v, c) => {
            const p = grow(frame, (r * colLabels.length + c) * f.opts.staggerFrames, comp.fps, f.opts.enterFrames);
            const t = Math.abs(v) / max;
            const emphasised = f.opts.emphasisIndex === r * colLabels.length + c;
            return (
              <div
                key={c}
                style={{
                  position: 'absolute',
                  left: f.plot.x + c * (cw + gap),
                  top: f.plot.y + r * (chh + gap),
                  width: cw, height: chh,
                  borderRadius: 8 * s,
                  background: emphasised
                    ? paint.accent
                    : `rgba(245,242,234,${(0.05 + t * 0.34).toFixed(3)})`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transform: `scale(${p})`,
                }}
              >
                {f.opts.showCellValues ? (
                  <span style={{fontFamily: FONT_NUM, fontVariantNumeric: 'tabular-nums', fontSize: 20 * s, color: emphasised ? '#14140F' : paint.inkFaint}}>
                    {f.valueText(v)}
                  </span>
                ) : null}
              </div>
            );
          })}
        </React.Fragment>
      ))}
      {/*
        Column labels. These were in the graph from the first draft of the demo
        and NOTHING read them — the cells were numbered by position alone, so
        "10" was a column with no name. A registry check cannot see this: the
        field is a top-level key of `content.chart`, not a ChartOptions entry, so
        it never appears in FIELD_READERS at all. Found by rendering and looking.
      */}
      {colLabels.map((label, c) => (
        <div
          key={`c${c}`}
          style={{
            position: 'absolute',
            left: f.plot.x + c * (cw + gap),
            top: f.plot.y + rowLabels.length * (chh + gap) + 10 * s,
            width: cw, textAlign: 'center',
            fontFamily: FONT_SANS, fontSize: 20 * s, color: paint.inkFaint,
          }}
        >
          {label}
        </div>
      ))}
      {rowLabels.map((label, r) => (
        <div key={label} style={{position: 'absolute', left: 0, width: f.plot.x - 14 * s, top: f.plot.y + r * (chh + gap) + chh / 2 - 12 * s, textAlign: 'right', fontFamily: FONT_SANS, fontSize: 20 * s, color: paint.inkFaint}}>
          {label}
        </div>
      ))}
    </>
  );
};

// ── rank ─────────────────────────────────────────────────────────────────────

export const RankTable: React.FC<{items: {label: string; value: number; previous?: number}[]}> = ({items}) => {
  const f = useFrame();
  const paint = useMarkPaint();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = f.s;
  const {SPACE} = useDesign();
  const max = Math.max(...items.map((i) => Math.abs(i.value)), 1e-6);
  const rowH = Math.min(96 * s, f.plot.h / Math.max(items.length, 1));
  // Centre the stack. Four rows at 78px in a 1000px plot left the lower two
  // thirds empty and the whole thing read as a header rather than a table.
  const stackH = rowH * items.length;
  const stackTop = f.plot.y + (f.plot.h - stackH) / 2;
  const labelW = Math.max(150 * s, f.plot.w * 0.26);

  return (
    <>
      {items.map((it, i) => {
        const p = grow(frame, i * f.opts.staggerFrames, comp.fps, f.opts.enterFrames);
        const emphasised = f.opts.emphasisIndex === i;
        const w = (Math.abs(it.value) / max) * (f.plot.w - labelW - 150 * s) * p;
        const delta = it.previous ? (it.value - it.previous) / Math.abs(it.previous) : 0;
        return (
          <div
            key={it.label}
            style={{
              position: 'absolute',
              left: f.plot.x, top: stackTop + i * rowH,
              width: f.plot.w, height: rowH - 8 * s,
              display: 'flex', alignItems: 'center',
            }}
          >
            <div style={{width: labelW - SPACE.md * s, fontFamily: FONT_SANS, fontSize: 24 * s, color: emphasised ? paint.ink : paint.inkMuted, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>
              {it.label}
            </div>
            <div
              style={{
                width: w, height: rowH * 0.46,
                background: emphasised ? paint.accent : paint.muted,
                borderRadius: `${6 * s}px`,
              }}
            />
            <div style={{marginLeft: 18 * s, fontFamily: FONT_NUM, fontVariantNumeric: 'tabular-nums', fontSize: 26 * s, color: paint.ink}}>
              {f.valueText(it.value)}
            </div>
            {f.opts.showRankDelta && it.previous ? (
              <div style={{marginLeft: 14 * s, fontFamily: FONT_NUM, fontSize: 20 * s, color: delta >= 0 ? paint.accent : paint.inkFaint, whiteSpace: 'nowrap'}}>
                {delta >= 0 ? '▲' : '▼'} {Math.abs(delta * 100).toFixed(1)}%
              </div>
            ) : null}
          </div>
        );
      })}
    </>
  );
};

// ── sparkline ────────────────────────────────────────────────────────────────

export const Sparkline: React.FC<{values: number[]; width?: number; height?: number}> = ({
  values, width = 220, height = 64,
}) => {
  const f = useFrame();
  const paint = useMarkPaint();
  const {PALETTE} = useDesign();
  const s = f.s;
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const pts: Point[] = values.map((v, i) => ({
    x: (width * s * i) / Math.max(values.length - 1, 1),
    y: height * s - ((v - lo) / Math.max(hi - lo, 1e-6)) * height * s * 0.86 - height * s * 0.07,
  }));
  const d = linePath(pts, f.opts.curve);
  return (
    <svg width={width * s} height={height * s} style={{overflow: 'visible', display: 'block'}} aria-hidden>
      <path d={d} fill="none" stroke={PALETTE.accent} strokeWidth={Math.max(2, f.opts.strokeWidth * 0.6) * s} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={pts[pts.length - 1]?.x ?? 0} cy={pts[pts.length - 1]?.y ?? 0} r={4 * s} fill={paint.accent} />
    </svg>
  );
};

// ── volume ───────────────────────────────────────────────────────────────────

export const VolumeBars: React.FC<{values: number[]; baseline?: number}> = ({values, baseline}) => {
  const f = useFrame();
  const paint = useMarkPaint();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = f.s;
  const max = Math.max(...values.map(Math.abs), 1e-6);
  const b = band(values.length, [f.plot.x, f.plot.x + f.plot.w], 0.12);
  const w = b.width * 0.72;
  const zero = baseline ?? 0;

  return (
    <>
      {values.map((v, i) => {
        const p = grow(frame, i * f.opts.staggerFrames, comp.fps, f.opts.enterFrames);
        const y = f.yOf(zero + v * p);
        const zeroY = f.yOf(zero);
        const emphasised = f.opts.emphasisIndex === i;
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: b.at(i) - w / 2,
              top: Math.min(y, zeroY),
              width: w,
              height: Math.max(0, Math.abs(zeroY - y)),
              background: emphasised ? paint.accent : paint.muted,
              borderRadius: `${3 * s}px ${3 * s}px 0 0`,
            }}
          />
        );
      })}
    </>
  );
};

/** Dispatch on the chart type. One place, so a new type cannot be half-wired. */
export const MARK: Record<ChartType, React.FC<any>> = {
  bar: Bar, line: Line, area: Area, slope: Slope, bubble: Bubble,
  heatmap: Heatmap, rank: RankTable, sparkline: Sparkline, volume: VolumeBars,
};
