/**
 * The chart option surface — declared once, here, before any renderer exists.
 *
 * P7 discipline: a field that is declared and never read is the failure this
 * project has now hit three times (the demo graph's fifteen style_bible keys,
 * one effective; the A/B guard's stale-frame pairing; cameraLanguage wired but
 * inert for a graph whose scenes all override it). So the surface a graph may
 * set is written down first, registered in FIELD_READERS with the file that
 * reads each option, and only then implemented. An option with no reader is a
 * failing check, not a silent capability.
 *
 * Rules this table follows, and why:
 *
 *  - Options live on the SCENE's `content.chart`, never scattered through a
 *    component's props. A chart that takes thirty props and reads eight is the
 *    same defect wearing a different hat.
 *  - Every option has a DEFAULT here, and the renderer reads through
 *    `option(chart, 'name')` so a missing graph value is never a crash and
 *    never a silent difference between two renders of the same graph.
 *  - Nothing that changes the data belongs here. Series, categories and values
 *    are content, not options — an option that can contradict the data is an
 *    option nobody will trust.
 *
 * The premium grammar this engine is written to (reference film 24s+):
 *   - colour carries meaning only: one accent, used for the emphasised mark
 *   - direct labelling instead of axis furniture wherever a number fits
 *   - gridlines are hairlines or nothing
 *   - no legend when there are at most two series and both are labelled
 */

export type ChartType =
  | 'bar'
  | 'line'
  | 'area'
  | 'slope'
  | 'bubble'
  | 'heatmap'
  | 'rank'
  | 'sparkline'
  | 'volume';

export const CHART_TYPES: readonly ChartType[] = [
  'bar', 'line', 'area', 'slope', 'bubble', 'heatmap', 'rank', 'sparkline', 'volume',
];

export type Curve = 'linear' | 'monotone' | 'step';

export type ValueFormat =
  | 'auto'       // 0,0 / 0,000 / 0.0% chosen from the magnitude
  | 'int'
  | 'one'
  | 'two'
  | 'percent'
  | 'compact';   // 1.2M, 340K

/**
 * Options common to every chart type.
 *
 * `emphasisIndex` is the emphasis mechanism and is deliberately a single field
 * across all nine types: "this one matters" is the same decision in a bar chart
 * and a heatmap, and a per-type spelling of it would be nine chances to
 * implement it three different ways.
 */
export type ChartOptions = {
  // ── surface ──────────────────────────────────────────────────────────────
  /** hairline gridlines behind the marks. Off by default: premium charts
   *  usually get their structure from the marks themselves. */
  showGrid: boolean;
  /** axis lines and tick labels. Off by default for the same reason. */
  showAxis: boolean;
  /** print the value on or beside every mark. */
  showValues: boolean;
  /** y axis label, if the unit is not obvious from the values */
  axisLabel: string;

  // ── emphasis ─────────────────────────────────────────────────────────────
  /** index of the one mark that gets the accent; -1 for none */
  emphasisIndex: number;
  /** 0..1 — how far the non-emphasised marks recede (opacity) */
  deemphasis: number;

  // ── motion ───────────────────────────────────────────────────────────────
  /** frames between successive marks starting */
  staggerFrames: number;
  /** frames for one mark to complete its entrance */
  enterFrames: number;

  // ── numbers ──────────────────────────────────────────────────────────────
  valueFormat: ValueFormat;

  // ── per type ─────────────────────────────────────────────────────────────
  /** line: fill under the line */
  showArea: boolean;
  /** line/volume: stroke width in design px */
  strokeWidth: number;
  /** line: how the path interpolates */
  curve: Curve;
  /** bar/rank: bar width as a fraction of the band */
  barWidthRatio: number;
  /** rank: print the change against the previous period */
  showRankDelta: boolean;
  /** heatmap: draw the value inside each cell */
  showCellValues: boolean;
  /** bubble: radius is proportional to this field's value, not the y value */
  sizeBy: 'value' | 'none';
  /** slope: label each end of the line */
  showEndLabels: boolean;
};

export const DEFAULT_CHART_OPTIONS: ChartOptions = {
  showGrid: false,
  showAxis: true,
  showValues: false,
  axisLabel: '',
  emphasisIndex: -1,
  deemphasis: 0.42,
  staggerFrames: 2,
  enterFrames: 34,
  valueFormat: 'auto',
  showArea: false,
  strokeWidth: 4,
  curve: 'monotone',
  barWidthRatio: 0.56,
  showRankDelta: true,
  showCellValues: true,
  sizeBy: 'value',
  showEndLabels: true,
};

/**
 * Which options each chart type is DOCUMENTED to accept.
 *
 * This table is documentation and a test target. It is deliberately NOT a
 * runtime gate, and it used to be one — which is a defect waiting to happen.
 * `TYPE_OPTIONS.volume` was missing `emphasisIndex`, an option VolumeBars reads
 * and the registry check passed on, because the name IS present in types.tsx.
 * Every emphasisIndex on a volume chart was therefore silently replaced by the
 * default. The A/B matrix caught it: 19 of 20 options live, and the one that
 * was not had a perfectly good frame.
 *
 * A declared surface that can make a working option inert is a surface that
 * eventually will, and the guard meant to prevent it cannot see that failure,
 * because the name is in the file. So the runtime honours whatever the graph
 * sets, and this table is kept honest by a test instead.
 */
export const TYPE_OPTIONS: Record<ChartType, readonly (keyof ChartOptions)[]> = {
  bar: ['showGrid', 'showAxis', 'showValues', 'axisLabel', 'emphasisIndex',
        'staggerFrames', 'enterFrames', 'valueFormat', 'barWidthRatio'],
  line: ['showGrid', 'showAxis', 'showValues', 'axisLabel', 'emphasisIndex',
         'staggerFrames', 'enterFrames', 'valueFormat', 'showArea',
         'strokeWidth', 'curve'],
  area: ['showGrid', 'showAxis', 'showValues', 'axisLabel', 'emphasisIndex',
         'staggerFrames', 'enterFrames', 'valueFormat', 'showArea',
         'strokeWidth', 'curve'],
  slope: ['staggerFrames', 'enterFrames', 'valueFormat',
          'showEndLabels', 'emphasisIndex'],
  bubble: ['showGrid', 'showAxis', 'showValues', 'emphasisIndex', 'deemphasis',
           'staggerFrames', 'enterFrames', 'valueFormat', 'sizeBy'],
  heatmap: ['showCellValues', 'emphasisIndex', 'staggerFrames', 'enterFrames',
            'valueFormat', 'axisLabel'],
  rank: ['showValues', 'staggerFrames', 'enterFrames', 'valueFormat',
         'showRankDelta', 'emphasisIndex'],
  // sparkline takes enterFrames because it now animates on the shared
  // lifecycle (P7.3) — before that it ignored the timeline entirely.
  // showEndLabels is slope's labelling knob; showValues was never read by the
  // slope mark (it only moved the frame's headroom), so the claim is dropped
  // rather than left as a documented option that does something else.
  sparkline: ['strokeWidth', 'curve', 'enterFrames'],
  volume: ['emphasisIndex', 'staggerFrames', 'enterFrames'],
};

/**
 * Every option key, across all chart types.
 *
 * Exported so the registry check can assert that FIELD_READERS names exactly
 * this set. Two lists that must agree, one of them in Python and one in
 * TypeScript, is a real chance to drift — and a chart option that is declared
 * in the registry but not in the table (or the reverse) is a field whose
 * existence nobody can vouch for.
 */
export const ALL_OPTION_KEYS: readonly (keyof ChartOptions)[] = [
  ...new Set(Object.values(TYPE_OPTIONS).flat()),
] as (keyof ChartOptions)[];

/**
 * Read one option, falling back to the default.
 *
 * Any value the graph supplied wins, and nothing here consults the documented
 * surface. Combined with `pickOptions` being keyed off
 * `Object.keys(DEFAULT_CHART_OPTIONS)` — which TypeScript guarantees complete,
 * since the object is typed `ChartOptions` — there is no path by which a graph's
 * value is discarded for want of a table entry. Adding an option makes it live.
 */
export const option = <K extends keyof ChartOptions>(
  chart: ChartType,
  key: K,
  overrides?: Partial<ChartOptions> | null
): ChartOptions[K] => {
  void chart; // the type is documentation now, not a gate
  const v = overrides?.[key];
  return v === undefined || v === null ? DEFAULT_CHART_OPTIONS[key] : v;
};
