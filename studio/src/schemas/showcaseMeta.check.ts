/**
 * Executable check of showcase-v1 -> composition metadata (P8 regression guard).
 *
 * Run:  npx tsx src/schemas/showcaseMeta.check.ts
 *
 * The defect: `resolveShowcaseMeta` used to return `1920x1080@60 1 frames` for
 * ANY document that failed the schema. Four different authoring mistakes — a
 * string where a number belongs, a scene id that fails the id regex, a scene
 * type outside the enum, an fps over the cap — produced that one answer, and
 * the caller was told `Cannot use frame 515: Duration of composition is 1`,
 * which is a complaint about a frame number and not about any of the four.
 *
 * So the property to pin is not "the format comes back" — that was true even
 * while the defect was live, on the fallback. It is that an invalid graph is
 * REJECTED and its offending field is NAMED, while a graph that has not arrived
 * yet is not.
 *
 * Dependency-free (zod only) so it cannot fail for reasons unrelated to the
 * decision it is checking.
 */

import {ShowcaseSchema, describeIssues} from './showcase-v1';
import {resolveShowcaseMeta} from './showcaseMeta';

let failures = 0;

const check = (name: string, ok: boolean, detail = ''): void => {
  if (ok) {
    console.log(`  ok   ${name}`);
  } else {
    failures += 1;
    console.log(`  FAIL ${name}${detail ? ` — ${detail}` : ''}`);
  }
};

/** The demo graph's shape, with `format` overridable per case. */
const graph = (format: Record<string, unknown> = {}) => ({
  version: 1,
  project: 'showcase_demo',
  format: {width: 1920, height: 1080, fps: 60, ...format},
  bpm: 126,
  scenes: [
    {id: 's01_kpi', type: 'kpi-hero', durationInFrames: 229},
    {id: 's02_dash', type: 'browser-stack', durationInFrames: 229},
    {id: 's03_columns', type: 'dashboard', durationInFrames: 114},
    {id: 's04_calendar', type: 'calendar', durationInFrames: 229},
  ],
});

/** Runs `fn` and returns the error message it threw, or null if it did not. */
const thrownBy = (fn: () => unknown): string | null => {
  try {
    fn();
    return null;
  } catch (e) {
    return e instanceof Error ? e.message : String(e);
  }
};

console.log('the graph owns the format');
for (const [label, fmt] of [
  ['1920x1080@60', {width: 1920, height: 1080, fps: 60}],
  ['1080x1920@60', {width: 1080, height: 1920, fps: 60}],
  ['3840x2160@60', {width: 3840, height: 2160, fps: 60}],
  ['1920x1080@30', {width: 1920, height: 1080, fps: 30}],
] as [string, Record<string, unknown>][]) {
  const meta = resolveShowcaseMeta(graph(fmt));
  check(
    `${label} -> ${meta.width}x${meta.height}@${meta.fps}, ${meta.durationInFrames} frames`,
    meta.width === fmt.width && meta.height === fmt.height && meta.fps === fmt.fps
  );
}
check(
  'the frame total is the sum of the scenes (801) and is fps-independent',
  resolveShowcaseMeta(graph()).durationInFrames === 801 &&
    resolveShowcaseMeta(graph({fps: 30})).durationInFrames === 801
);

console.log('\na graph that is present and wrong is rejected, and the field is named');
const cases: [string, unknown, string][] = [
  ['format.width is a string', graph({width: '1920'}), 'format.width'],
  ['a scene id that fails the id regex', {...graph(), scenes: [{id: 'S01_Upper', type: 'kpi-hero', durationInFrames: 100}]}, 'scenes.0.id'],
  ['an unknown scene type', {...graph(), scenes: [{id: 's01', type: 'donut-chart', durationInFrames: 100}]}, 'scenes.0.type'],
  ['fps over the schema cap', graph({fps: 999}), 'format.fps'],
  // The hole the first version of the absent/present rule left: a document that
  // declares a format but no scenes is a graph missing a required field, not an
  // absent graph, and must not be answered with the registration default.
  ['format but no scenes', {version: 1, project: 'x', format: {width: 1920, height: 1080, fps: 60}}, 'scenes'],
  ['a missing scene duration', {...graph(), scenes: [{id: 's01', type: 'kpi-hero'}]}, 'durationInFrames'],
  ['a zero-height frame', graph({height: 0}), 'format.height'],
];
for (const [label, doc, expect] of cases) {
  const msg = thrownBy(() => resolveShowcaseMeta(doc));
  check(`${label} is rejected`, msg !== null, 'returned metadata instead of throwing');
  if (msg !== null) {
    check(
      `${label} names ${expect}`,
      msg.includes(expect),
      msg.split('\n').slice(0, 3).join(' / ')
    );
    check(
      `${label} does not fall back to 1920x1080`,
      !msg.includes('1920x1080'),
      'the fallback format is still being handed out'
    );
  }
}

console.log('\nthe regression itself: an invalid graph must not get the default format');
const bad = thrownBy(() => resolveShowcaseMeta(graph({width: '1920'})));
check(
  'a string width does not yield 1920x1080@60 1 frames',
  bad !== null,
  'returned the fallback — this is the P8 defect'
);

console.log('\na graph that has not arrived yet is not an error');
// Remotion runs calculateMetadata once with defaultProps before real props
// arrive. That is a legitimate question, not an authoring mistake.
for (const [label, doc] of [
  ['undefined', undefined],
  ['null', null],
  ['{}', {}],
  ['a string', 'not a graph'],
  ['an array', [1, 2, 3]],
  ['an object with no graph fields', {foo: 1}],
] as [string, unknown][]) {
  let meta: ReturnType<typeof resolveShowcaseMeta> | null = null;
  let msg: string | null = null;
  try {
    meta = resolveShowcaseMeta(doc);
  } catch (e) {
    msg = e instanceof Error ? e.message : String(e);
  }
  check(
    `${label} falls back to 1920x1080@60`,
    msg === null && meta !== null && meta.width === 1920 && meta.height === 1080
      && meta.fps === 60 && meta.durationInFrames === 1,
    msg ?? 'no fallback'
  );
}

console.log('\nthe error message is one an author can act on');
const msg = thrownBy(() => resolveShowcaseMeta(graph({width: '1920'}))) ?? '';
check('names the field', /format\.width/.test(msg), msg);
check('says what it got', /received string/.test(msg), msg);
check('says what it wanted', /expected number/.test(msg), msg);
check(
  'does not leak a raw JSON blob',
  !msg.includes('"code"') && !msg.includes('[{'),
  msg
);

console.log('\ndescribeIssues renders every issue, with a path');
const parsed = ShowcaseSchema.safeParse({
  ...graph(),
  format: {width: '1920', height: 0, fps: 999},
});
if (parsed.success) {
  check('the multi-issue document is actually invalid', false);
} else {
  const text = describeIssues(parsed.error);
  check(`all ${parsed.error.issues.length} issues are listed`,
    parsed.error.issues.every((i) => text.includes(i.path.map(String).join('.'))),
    text
  );
  check('one line per issue',
    text.split('\n').length === parsed.error.issues.length,
    text
  );
}

console.log('\nfps is not a scene property: the frame count must not follow it');
{
  // Measured, not assumed: showcase_demo.json is 801 frames at 60, 30 AND 120
  // fps, so the same graph runs 13.35s / 26.70s / 6.67s. Scene lengths are
  // authored in frames, which is a deliberate choice and has a consequence
  // worth pinning: the same frame number is a DIFFERENT moment of the film at a
  // different rate. At frame 515 the 30fps and 60fps renders differ by 16.57%
  // of the frame, because the camera ramp is wall-clock anchored
  // (`cameraMoveFrames = seconds * fps`, checked in scale.check.ts) while the
  // scene lengths are not. Silent on this, someone changes fps to make a render
  // faster and the camera silently moves.
  const counts = [60, 30, 120].map((fps) =>
    resolveShowcaseMeta({...graph(), format: {width: 1920, height: 1080, fps}}).durationInFrames
  );
  check('the frame count is identical at 30, 60 and 120 fps',
    new Set(counts).size === 1, `${counts.join(' / ')}`);
  check('and it is the sum of the scenes, so it is authored not derived from fps',
    counts[0] === graph().scenes.reduce((n, s) => n + s.durationInFrames, 0),
    `${counts[0]}`);
}

if (failures) {
  console.log(`\n${failures} check(s) failed`);
  process.exit(1);
}
console.log('\nall showcaseMeta checks passed');
