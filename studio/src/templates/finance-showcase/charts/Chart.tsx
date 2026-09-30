import React, {useMemo} from 'react';
import type {Scene} from '../../../schemas/showcase-v1';
import {CameraRig} from '../common/CameraRig';
import {ChartFrame, useFrame} from './ChartFrame';
import {
  Area, Bar, Bubble, Heatmap, Line, RankTable, Slope, Sparkline, VolumeBars,
} from './types';
import {
  CHART_TYPES, DEFAULT_CHART_OPTIONS, type ChartOptions, type ChartType,
} from './options';

/**
 * Chart scene adapter — turns a graph's `content.chart` into a frame and a mark.
 *
 * The graph never names a component. It names a chart TYPE and a bag of
 * options, and the option's surface is declared in charts/options.ts and
 * registered in FIELD_READERS. That is the whole point of the arrangement: a
 * field that no mark reads is a failing registry check, not a capability that
 * looks real.
 *
 * A graph may also set `chart.series` (or `values` at the top level) and the
 * adapter supplies the rest. Anything the graph does not supply falls back to
 * the declared default, so two renders of the same graph cannot differ.
 */

export type ChartSpec = {
  type: ChartType;
  series?: {name?: string; values: number[]; sizes?: number[]}[];
  values?: number[];
  labels?: string[];
  /** heatmap only */
  rows?: number[][];
  rowLabels?: string[];
  colLabels?: string[];
  /** rank only */
  items?: {label: string; value: number; previous?: number}[];
  /** slope only */
  before?: number[];
  after?: number[];
  /** every option in ChartOptions may appear here */
  [key: string]: unknown;
};

const asChartType = (v: unknown): ChartType =>
  typeof v === 'string' && (CHART_TYPES as readonly string[]).includes(v)
    ? (v as ChartType)
    : 'bar';

const numArray = (v: unknown): number[] =>
  Array.isArray(v) ? v.map((n) => (typeof n === 'number' ? n : Number(n))).filter(Number.isFinite) : [];

/**
 * Separate the OPTIONS from the DATA.
 *
 * `content.chart` is one bag, but a chart's data and a chart's options are
 * different things and conflating them is how a graph ends up with
 * `chart.values` meaning "the numbers" in one type and "the y domain" in
 * another. Data keys stay data.
 *
 * The key list is `Object.keys(DEFAULT_CHART_OPTIONS)`, NOT `ALL_OPTION_KEYS`.
 * That distinction is the whole point: ALL_OPTION_KEYS is derived from
 * TYPE_OPTIONS, which is documentation, and filtering by it made this a second
 * runtime gate — a graph could lose a value here, before `option()` ever saw it,
 * which is exactly what the `option()` de-gating was supposed to prevent and
 * which left its own docstring untrue.
 *
 * `DEFAULT_CHART_OPTIONS` is typed `ChartOptions`, so TypeScript fails to
 * compile if an option is declared and has no default. The list therefore
 * cannot fall behind the option surface the way a hand-maintained table can,
 * and adding an option makes it live immediately with nothing else to edit.
 */
const pickOptions = (raw: Record<string, unknown>): Partial<ChartOptions> => {
  const out: Record<string, unknown> = {};
  for (const key of Object.keys(DEFAULT_CHART_OPTIONS)) {
    if (raw[key] !== undefined) out[key] = raw[key];
  }
  return out as Partial<ChartOptions>;
};

export const normaliseChart = (raw: unknown): ChartSpec => {
  const c = (raw ?? {}) as Record<string, unknown>;
  const series = Array.isArray(c.series)
    ? (c.series as Record<string, unknown>[]).map((s) => ({
        name: typeof s.name === 'string' ? s.name : undefined,
        values: numArray(s.values),
        sizes: s.sizes ? numArray(s.sizes) : undefined,
      }))
    : undefined;
  return {...c, type: asChartType(c.type), series, values: numArray(c.values)} as ChartSpec;
};

/** Places a sparkline at the frame's left edge — it is a mark, not a scene. */
const SparklineSlot: React.FC<{values: number[]}> = ({values}) => {
  const f = useFrame();
  return (
    <div style={{position: 'absolute', left: f.plot.x, top: f.plot.y}}>
      <Sparkline values={values} width={420} height={140} />
    </div>
  );
};

export const ChartScene: React.FC<{scene: Scene}> = ({scene}) => {
  const c = (scene.content ?? {}) as Record<string, unknown>;
  const spec = useMemo(() => normaliseChart(c.chart), [c.chart]);
  const type = spec.type;

  // every value the frame's domain must cover, per type
  const values = useMemo<number[]>(() => {
    if (spec.series?.length) return spec.series.flatMap((s) => s.values);
    if (type === 'slope') return [...(spec.before ?? []), ...(spec.after ?? [])];
    if (type === 'heatmap') return (spec.rows ?? []).flat();
    if (type === 'rank') return (spec.items ?? []).map((i) => i.value);
    return spec.values ?? [];
  }, [spec, type]);

  if (!values.length) {
    return (
      <CameraRig camera={scene.camera} motion={scene.motion} durationInFrames={scene.durationInFrames}>
        <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
          <div style={{fontFamily: 'monospace', fontSize: 34, color: '#E8C464'}}>
            chart: no values
          </div>
        </div>
      </CameraRig>
    );
  }

  // bar, rank and volume encode magnitude as LENGTH, so their baseline must be
  // zero. A fitted domain on a bar chart is a chart that lies about size.
  const zeroBased = type === 'bar' || type === 'rank' || type === 'volume';

  // Category charts label by the mark's own band positions, so "Revenue" sits
  // under the Revenue bar. Evenly spaced labels are right for a time series and
  // wrong here, and a label under the wrong bar is not a cosmetic problem.
  // A band's CENTRE is at (i + 0.5) / n whatever the padding, because the
  // padding is symmetric — which is why the label lands under its own mark and
  // not under the gap beside it.
  const xAt = useMemo(() => {
    if (!spec.labels || !(type === 'bar' || type === 'bubble' || type === 'volume')) return undefined;
    return (i: number, n: number) => (n > 0 ? (i + 0.5) / n : 0.5);
  }, [spec.labels, type]);

  return (
    <CameraRig camera={scene.camera} motion={scene.motion} durationInFrames={scene.durationInFrames}>
      <ChartFrame
        chart={type}
        options={pickOptions(spec as unknown as Record<string, unknown>)}
        values={values}
        zeroBased={zeroBased}
        xLabels={type === 'bar' || type === 'bubble' || type === 'volume' ? spec.labels : undefined}
        rowLabels={type === 'heatmap' ? spec.rowLabels : undefined}
        xAt={xAt}
      >
        {type === 'bar' ? <Bar series={{values}} labels={spec.labels} /> : null}
        {type === 'line' ? <Line series={{values}} /> : null}
        {type === 'area' ? <Area series={{values}} /> : null}
        {type === 'bubble' ? <Bubble series={{values: spec.series?.[0]?.values ?? values, sizes: spec.series?.[0]?.sizes}} labels={spec.labels} /> : null}
        {type === 'slope' ? (
          <Slope before={spec.before ?? []} after={spec.after ?? []} labels={spec.labels ?? []} />
        ) : null}
        {type === 'heatmap' ? (
          <Heatmap
            rows={spec.rows ?? [values]}
            rowLabels={spec.rowLabels ?? []}
            colLabels={spec.colLabels ?? []}
          />
        ) : null}
        {type === 'rank' ? (
          <RankTable
            items={spec.items ?? values.map((v, i) => ({label: spec.labels?.[i] ?? String(i + 1), value: v}))}
          />
        ) : null}
        {type === 'volume' ? <VolumeBars values={values} baseline={typeof c.baseline === 'number' ? c.baseline : undefined} /> : null}
        {/*
          sparkline is normally an INLINE mark — the metric inside a browser
          window, a stat card — not a full-frame scene, and no declared scene
          type routes to it. It is still renderable here, at its natural size
          and centred, so a graph that asks for one gets a chart rather than a
          blank frame. `inline: true` is the option that says "this is a mark,
          not a scene" and it is honoured by the component, not by this branch.
        */}
        {type === 'sparkline' ? <SparklineSlot values={values} /> : null}
      </ChartFrame>
    </CameraRig>
  );
};
