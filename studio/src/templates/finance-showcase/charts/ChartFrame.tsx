import React, {createContext, useContext, useMemo} from 'react';
import {useVideoConfig} from 'remotion';
import {FONT_NUM, FONT_SANS, scaleFrom} from '../design/tokens';
import {useDesign} from '../design/styleBible';
import {formatValue, linear, niceTicks, type Extent} from './scale';
import {option, type ChartOptions, type ChartType} from './options';

/**
 * The chart frame — everything a chart draws that is not a mark.
 *
 * Axes, gridlines, tick labels, value formatting and the plot box live here so
 * that nine chart types cannot each invent their own. Before this, "where is
 * the baseline" and "how do we write 48200" were per-chart decisions, which is
 * how two charts in one film end up with different gutters and different
 * rounding.
 *
 * The frame also OWNS the y domain, and hands the resolved scale to the marks
 * through context. A mark therefore cannot accidentally use a different domain
 * from the axis it is drawn against — the failure that makes a chart readable
 * and wrong at the same time.
 *
 * Reads from the declared option surface: showGrid, showAxis, showValues,
 * axisLabel, valueFormat. The rest are the marks' business (charts/types.tsx).
 */

export type PlotBox = {x: number; y: number; w: number; h: number};

export type Frame = {
  chart: ChartType;
  opts: ChartOptions;
  /** design px; the frame is inside a CameraRig, so it is not perspective-scaled */
  plot: PlotBox;
  /** data value -> y in px from the TOP of the plot (y grows downward in px) */
  yOf: (v: number) => number;
  /** the y domain actually used, after the frame's headroom */
  domain: Extent;
  /** the tick values the axis is labelled with */
  ticks: number[];
  /** formatted text for a value, honouring valueFormat */
  valueText: (v: number) => string;
  /** the unit a compacted value carried, if any, so the caller can label it once */
  unit: string;
  /** design px per unit, for callers that need to convert (radius, offsets) */
  s: number;
};

const FrameContext = createContext<Frame | null>(null);

/** The frame a mark is drawn inside. Throws if used outside a ChartFrame,
 *  because a mark with no frame has no domain and would draw at the origin. */
export const useFrame = (): Frame => {
  const f = useContext(FrameContext);
  if (!f) throw new Error('chart marks must be rendered inside a <ChartFrame>');
  return f;
};

export type ChartFrameProps = {
  chart: ChartType;
  options?: Partial<ChartOptions> | null;
  /** the data the y domain is computed from */
  values: readonly number[];
  /** zeroBased: bar/rank/volume must be, or their lengths lie about magnitude */
  zeroBased?: boolean;
  /** labels along x; their presence reserves the bottom row */
  xLabels?: readonly string[];
  /** heatmap row labels; they size the gutter when the y axis is categorical */
  rowLabels?: readonly string[];
  /**
   * Where label i belongs, as a FRACTION of the plot width (0..1).
   *
   * A fraction, not pixels, because the mark computes this before the frame
   * exists and therefore before the plot box is known; the frame scales it.
   *
   * Supplied by the mark, because only the mark knows where it put its marks.
   * Without it the frame spaces labels evenly, which is right for a time series
   * and wrong for a category chart — and a label under the wrong bar is not a
   * cosmetic problem, it is a wrong chart.
   */
  xAt?: (i: number, count: number) => number;
  /** marks, drawn inside the plot box */
  children: React.ReactNode;
};

/** How many design px to leave for y tick labels, measured from the widest. */
const gutterFor = (labels: readonly string[], s: number): number => {
  const widest = labels.reduce((m, l) => Math.max(m, l.length), 1);
  return Math.min(190 * s, 34 * s + widest * 13 * s);
};

export const ChartFrame: React.FC<ChartFrameProps> = ({
  chart, options, values, zeroBased = true, xLabels, rowLabels, xAt, children,
}) => {
  const {PALETTE, SPACE, TYPE} = useDesign();
  const comp = useVideoConfig();
  const s = scaleFrom(comp.height);
  const opts = useMemo(
    () => ({
      showGrid: option(chart, 'showGrid', options),
      showAxis: option(chart, 'showAxis', options),
      showValues: option(chart, 'showValues', options),
      axisLabel: option(chart, 'axisLabel', options),
      valueFormat: option(chart, 'valueFormat', options),
    }),
    [chart, options]
  );

  // The plot lives inside a padded div, so its box is the FRAME minus that
  // padding. Measuring it from comp.width made every chart 2*SPACE.lg too wide
  // and the last point of a line ran off the right edge — which is why a
  // 'full width' chart is not a full width chart.
  const padX = (SPACE.lg + SPACE.xl) * s;
  const padY = SPACE.lg * s * 2;
  const W = comp.width - padX;
  const H = comp.height - padY;

  // A heatmap's y axis is rows (AMER/EMEA/APAC) and a rank table's is categories
  // (Enterprise/Mid-market/...). Neither has a numeric scale, and drawing one
  // put "60" on top of EMEA and "40" on top of SMB — the axis claimed a scale the
  // chart does not have AND collided with the labels that do mean something.
  const categoricalY = chart === 'heatmap' || chart === 'rank';
  const rowLabelW = categoricalY && rowLabels?.length
    ? Math.min(210 * s, 40 * s + Math.max(...rowLabels.map((l) => l.length)) * 13 * s)
    : 0;

  // domain first: the axis labels depend on the ticks, and the gutter depends
  // on the labels, and the plot box depends on the gutter. In that order.
  const rawLo = zeroBased ? Math.min(0, ...values) : Math.min(...values);
  const rawHi = Math.max(...values, zeroBased ? 0 : -Infinity);
  // Headroom. Without it the tallest mark's top edge IS the top of the plot and
  // its value label has nowhere to go but inside the mark — which is how a
  // value ends up printed on top of itself in a different colour.
  const headroom = options?.showValues ? 0.14 : 0.04;
  const lo = rawLo < 0 ? rawLo - Math.abs(rawHi - rawLo) * headroom : rawLo;
  const hi = rawHi + Math.abs(rawHi - rawLo) * headroom;
  const domain: Extent = Number.isFinite(lo) && Number.isFinite(hi) && hi > lo ? [lo, hi] : [0, 1];
  const ticks = niceTicks(domain[0], domain[1], 5);
  const tickLabels = ticks.map((t) => formatValue(t, opts.valueFormat).text);
  const unit = useMemo(
    () => (values.length
      ? formatValue(Math.max(...values.map(Math.abs)), opts.valueFormat).unit
      : ''),
    [values, opts.valueFormat]
  );

  const gutter = categoricalY ? rowLabelW : (opts.showAxis ? gutterFor(tickLabels, s) : 0);
  const drawYTicks = opts.showAxis && !categoricalY;
  const bottom = xLabels && xLabels.length ? 66 * s : 0;
  // headroom so a value label above the tallest mark has somewhere to sit
  const top = (opts.showValues ? 46 : 18) * s;

  const plot: PlotBox = {
    x: gutter + SPACE.md * s,
    y: top,
    w: Math.max(10, W - (gutter + SPACE.md * s) - SPACE.xl * s),
    h: Math.max(10, H - top - bottom - SPACE.xl * s),
  };

  const yOf = useMemo(
    () => linear(domain, [plot.y + plot.h, plot.y]),
    [domain, plot.y, plot.h]
  );

  const frame: Frame = useMemo(() => ({
    chart,
    opts: {
      ...opts,
      emphasisIndex: option(chart, 'emphasisIndex', options),
      deemphasis: option(chart, 'deemphasis', options),
      staggerFrames: option(chart, 'staggerFrames', options),
      enterFrames: option(chart, 'enterFrames', options),
      showArea: option(chart, 'showArea', options),
      strokeWidth: option(chart, 'strokeWidth', options),
      curve: option(chart, 'curve', options),
      barWidthRatio: option(chart, 'barWidthRatio', options),
      showRankDelta: option(chart, 'showRankDelta', options),
      showCellValues: option(chart, 'showCellValues', options),
      sizeBy: option(chart, 'sizeBy', options),
      showEndLabels: option(chart, 'showEndLabels', options),
    } as ChartOptions,
    plot, yOf, domain, ticks, s,
    valueText: (v: number) => {
      const f = formatValue(v, opts.valueFormat);
      return f.unit ? `${f.text}${f.unit}` : f.text;
    },
    unit,
  }), [chart, options, opts, plot, yOf, domain, ticks, s, values, unit]);

  return (
    <FrameContext.Provider value={frame}>
      <div style={{position: 'absolute', inset: 0, padding: `${SPACE.lg * s}px ${SPACE.xl * s}px`}}>
        <div style={{position: 'relative', width: '100%', height: '100%'}}>
          {/* gridlines: hairlines or nothing. never a box, never a frame. */}
          {opts.showGrid && !categoricalY
            ? ticks.map((t) => (
                <div
                  key={`g${t}`}
                  style={{
                    position: 'absolute',
                    left: plot.x, width: plot.w,
                    top: yOf(t), height: 1,
                    background: PALETTE.grid,
                  }}
                />
              ))
            : null}

          {/* the baseline: the one axis line that is always worth drawing, since
              without it a bar chart's lengths have nothing to be measured from */}
          <div
            style={{
              position: 'absolute',
              left: plot.x, width: plot.w,
              top: yOf(Math.max(0, domain[0]) === 0 ? 0 : domain[0]),
              height: 1,
              background: PALETTE.hairline,
            }}
          />

          {drawYTicks
            ? ticks.map((t) => {
                const label = formatValue(t, opts.valueFormat).text;
                return (
                  <div
                    key={`t${t}`}
                    style={{
                      // left/width, NOT right: `right` is measured from the
                      // container's right edge, so `right: W - plot.x` put the
                      // labels at the far LEFT of the frame, clipped. A tick
                      // label that is not next to its tick is worse than none.
                      position: 'absolute',
                      left: 0,
                      width: Math.max(0, plot.x - SPACE.sm * s),
                      top: yOf(t) - 11 * s,
                      textAlign: 'right',
                      fontFamily: FONT_NUM,
                      fontVariantNumeric: 'tabular-nums',
                      fontSize: 20 * s,
                      color: PALETTE.inkFaint,
                    }}
                  >
                    {label}
                  </div>
                );
              })
            : null}

          {opts.axisLabel ? (
            <div
              style={{
                position: 'absolute',
                left: 0, top: plot.y - 34 * s,
                fontFamily: FONT_SANS,
                fontSize: TYPE.annotation.size * s,
                letterSpacing: TYPE.annotation.tracking,
                textTransform: 'uppercase',
                color: PALETTE.inkFaint,
              }}
            >
              {opts.axisLabel}
            </div>
          ) : null}

          {/* the marks */}
          {children}

          {/*
            ONE row, and positioned by the mark's own geometry when the mark
            supplies it. The previous version mapped over the labels and
            rendered the whole set once per label, which stacked five copies on
            top of each other; and it spaced them evenly across the plot, which
            put "Revenue" under a bar that was not Revenue. A label that does
            not line up with its mark is worse than no label.
          */}
          {xLabels && xLabels.length
            ? (
                <div
                  style={{
                    position: 'absolute',
                    left: plot.x, width: plot.w, top: plot.y + plot.h + 16 * s,
                    height: 30 * s,
                  }}
                >
                  {xLabels.map((label, i) => {
                    const cx = (xAt ? xAt(i, xLabels.length) : (i + 0.5) / xLabels.length) * plot.w;
                    return (
                      <div
                        key={i}
                        style={{
                          position: 'absolute',
                          left: cx - 90 * s, width: 180 * s,
                          textAlign: 'center',
                          fontFamily: FONT_SANS,
                          fontSize: 20 * s,
                          color: PALETTE.inkFaint,
                        }}
                      >
                        {label}
                      </div>
                    );
                  })}
                </div>
              )
            : null}
        </div>
      </div>
    </FrameContext.Provider>
  );
};
