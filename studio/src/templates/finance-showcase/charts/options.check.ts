/**
 * Executable check of the chart option surface (P47).
 *
 * Run:  npx tsx src/templates/finance-showcase/charts/options.check.ts
 *
 * `lifecycle.check.ts` proved the timeline cannot rot. This proves the DEFAULTS
 * cannot, and it exists because of a specific failure that every other check
 * was green through.
 *
 * WHAT WENT WRONG, in one line: `option()` returns
 * `DEFAULT_CHART_OPTIONS[key]` whenever the graph supplies nothing, so it NEVER
 * returned undefined — and `types.tsx` resolved the area fill as
 * `option('line', 'showArea', opts) ?? defaultArea`, which can therefore only
 * ever take its left side. `defaultArea` was unreachable, `area` and `line`
 * rendered byte-identical, and the delivered graph had the option on the LINE
 * scene and not on the AREA one, so they shipped swapped.
 *
 * The properties below are the ones a RENDER cannot show you, because they are
 * about the resolution order rather than about any one picture:
 *
 *  - `option()` resolves to a real value for every (type, option) pair, so a
 *    `?? something` written against it can never be a live fallback. The old
 *    code's dead branch is only dead because of this.
 *  - NO chart type can discard a value the graph supplied. This is the property
 *    `TYPE_OPTIONS` lost when it was a runtime filter (it silently threw away
 *    every volume chart's `emphasisIndex` while the registry check reported the
 *    option as read), and it is the reason the per-type default table is allowed
 *    to exist at all: it fills a gap, it cannot make anything inert.
 *  - "the graph said nothing" and "the graph said false" are DIFFERENT inputs
 *    with different answers, which is the whole distinction `Area` needed and
 *    could not get. That is what makes the area fill an overridable default
 *    rather than a hardcoded rule.
 *  - every row of `TYPE_DEFAULT_ROWS` is a real option on a real type, and
 *    differs from the shared default it overrides. A row that restates the
 *    shared default is saying nothing, and the pixel guard
 *    (`tests/test_chart_type_defaults_are_real.py`) is what proves the rest.
 */

import {
  CHART_TYPES, DEFAULT_CHART_OPTIONS, TYPE_DEFAULT_ROWS, option,
  type ChartOptions, type ChartType,
} from './options';

let failures = 0;
const check = (name: string, ok: boolean, detail = ''): void => {
  if (ok) {
    console.log(`  ok   ${name}`);
  } else {
    failures += 1;
    console.log(`  FAIL ${name}${detail ? ` — ${detail}` : ''}`);
  }
};

const KEYS = Object.keys(DEFAULT_CHART_OPTIONS) as (keyof ChartOptions)[];

console.log(`options: ${CHART_TYPES.length} types x ${KEYS.length} options resolve to a value`);

// ── 1. every pair resolves, and never to undefined or null ───────────────────
//
// This is the property the old dead branch assumed and could not have: if any
// pair could resolve to undefined, then `option(...) ?? defaultArea` would be
// a live fallback rather than a lie, and the area/line collapse would have been
// somebody's deliberate design instead of a bug nobody could see.
{
  const unresolved: string[] = [];
  for (const t of CHART_TYPES) {
    for (const k of KEYS) {
      const v = option(t, k);
      if (v === undefined || v === null) unresolved.push(`${t}.${k}`);
    }
  }
  check('no (type, option) pair resolves to undefined or null', unresolved.length === 0,
        unresolved.join(', '));
}

// ── 2. no chart type may discard a value the graph supplied ──────────────────
//
// The `TYPE_OPTIONS` incident, asserted as behaviour rather than as the absence
// of a particular token. `tsx` strips types without checking them, so this is
// also the only thing standing between a renamed option and a row that quietly
// stopped matching.
{
  const probes: Partial<ChartOptions>[] = [
    {showArea: false}, {showArea: true}, {showGrid: true}, {showGrid: false},
    {showAxis: false}, {showValues: true}, {emphasisIndex: 3}, {deemphasis: 0.9},
    {strokeWidth: 11}, {curve: 'linear'}, {curve: 'step'}, {barWidthRatio: 0.8},
    {showRankDelta: false}, {showCellValues: false}, {sizeBy: 'none'},
    {showEndLabels: false}, {valueFormat: 'percent'}, {staggerFrames: 7},
    {enterFrames: 90}, {axisLabel: 'X'},
  ];
  const discarded: string[] = [];
  for (const t of CHART_TYPES) {
    for (const k of KEYS) {
      for (const probe of probes) {
        const supplied = probe[k];
        if (supplied === undefined) continue;
        const got = option(t, k, probe);
        if (got !== supplied) discarded.push(`${t}.${k}: set ${String(supplied)}, got ${String(got)}`);
      }
    }
  }
  check('no chart type discards a value the graph set', discarded.length === 0,
        discarded.slice(0, 6).join('; '));
}

// ── 3. silence and `false` are different inputs ─────────────────────────────
//
// The distinction `Area` needed and could not get, pinned at the resolver. If
// these two lines ever come to agree, the area fill has stopped being an
// overridable default and become a hardcoded rule — which is the other way for
// a graph author's `showArea: false` to become a silent no-op.
{
  check('`area` fills when the graph says nothing',
        option('area', 'showArea') === true);
  check('`area` fills when the graph says nothing but `null`',
        option('area', 'showArea', null) === true);
  check('`area` fills when the graph sets an unrelated option',
        option('area', 'showArea', {showGrid: true}) === true);
  check('`area` obeys an explicit false', option('area', 'showArea', {showArea: false}) === false);
  check('`area` obeys an explicit true', option('area', 'showArea', {showArea: true}) === true);
  check('`line` is bare when the graph says nothing', option('line', 'showArea') === false);
  check('`line` obeys an explicit true', option('line', 'showArea', {showArea: true}) === true);
  check('`line` obeys an explicit false', option('line', 'showArea', {showArea: false}) === false);
}

// ── 4. every per-type row names a real type and a real option ──────────────
//
// `tsx` does not type-check, so the `Partial<Record<ChartType, …>>` annotation
// is documentation to this process. A typo in either half would otherwise be a
// row that resolves nothing and looks correct.
{
  const badTypes = Object.keys(TYPE_DEFAULT_ROWS).filter(
    (t) => !(CHART_TYPES as readonly string[]).includes(t));
  check('every TYPE_DEFAULT_ROWS key is a declared chart type', badTypes.length === 0,
        badTypes.join(', '));

  const badKeys: string[] = [];
  for (const [t, row] of Object.entries(TYPE_DEFAULT_ROWS)) {
    for (const k of Object.keys(row)) {
      if (!KEYS.includes(k as keyof ChartOptions)) badKeys.push(`${t}.${k}`);
    }
  }
  check('every TYPE_DEFAULT_ROWS option is a declared option', badKeys.length === 0,
        badKeys.join(', '));

  const redundant: string[] = [];
  for (const [t, row] of Object.entries(TYPE_DEFAULT_ROWS)) {
    for (const [k, v] of Object.entries(row)) {
      if ((DEFAULT_CHART_OPTIONS as Record<string, unknown>)[k] === v) {
        redundant.push(`${t}.${k}=${JSON.stringify(v)}`);
      }
    }
  }
  // A row that restates the shared default is not wrong, it is redundant — and
  // it is the shape a dumb declaration takes when nobody checks it, so it is
  // failed here rather than left in the table.
  check('no TYPE_DEFAULT_ROWS row restates the shared default', redundant.length === 0,
        redundant.join(', '));
}

if (failures) {
  console.error(`\n${failures} check(s) FAILED`);
  process.exit(1);
}
console.log('\nall option checks passed');