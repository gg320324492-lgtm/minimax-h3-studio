/**
 * Which of the six binding events can be asked about, and what it answers.
 *
 * Run:  npx tsx src/templates/finance-showcase/beat/bindings.check.ts
 *
 * The availability table is the finding, and it is pinned rather than derived:
 *
 *   camera settle   AVAILABLE   cameraMoveFrames + cameraStateAt().t
 *   chart finish    AVAILABLE   lifecycleAt() focus-phase start
 *   cut             no surface  transitionIn is consumed inside SceneEnter
 *   card arrival    no surface  Reveal/Stagger compute the spring locally
 *   number finish   nothing     countUp's 1.6s is a default param, and the call
 *                               site passes the literal again
 *   hit             nothing     no such concept; and i%4 is measurably wrong
 *
 * A later change that makes one of the four available is an improvement and should
 * be recorded, not blocked — but it should not happen by accident, which is what
 * pinning the table prevents. Two of the six assertions are therefore written so
 * that flipping them to the opposite expectation FAILS with a message saying the
 * table needs updating deliberately.
 *
 * The fps-scaling assertions are kept separate on purpose, because the two
 * available events scale differently and a single "it scales" check would pass on
 * the wrong one:
 *
 *   camera settle  scales WITH fps (seconds * fps) — 120fps must be double 60fps
 *   chart finish   scales with SCENE DURATION, and not at all with fps — the
 *                  lifecycle is a fraction of the scene's frames, so at twice the
 *                  fps the same scene asks the same question in half the frames
 *
 * Dependency-free beyond the two real functions it queries.
 */

import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {BINDING_EVENTS, bindingFor, focusStartFrame, type BindingDoc} from './bindings';
import {ShowcaseSchema, resolveScenes, type Showcase} from '../../../schemas/showcase-v1';
import {lifecycleAt} from '../charts/lifecycle';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../../../../..');
const EXAMPLES = path.join(ROOT, 'pipeline/examples');

let failures = 0;
const check = (name: string, ok: boolean, detail = ''): void => {
  if (ok) {
    console.log(`  ok   ${name}`);
  } else {
    failures += 1;
    console.log(`  FAIL ${name}${detail ? `\n         ${detail}` : ''}`);
  }
};

const asDoc = (raw: unknown): BindingDoc => {
  const doc = ShowcaseSchema.parse(raw) as Showcase;
  const resolved = resolveScenes(doc, false);
  return {
    fps: doc.format.fps,
    scenes: doc.scenes.map((s, i) => ({
      id: s.id,
      type: s.type,
      durationInFrames: resolved[i].durationInFrames,
      startFrame: resolved[i].startFrame,
    })),
  };
};

const showcase = asDoc(
  JSON.parse(fs.readFileSync(path.join(EXAMPLES, 'showcase_demo.json'), 'utf8'))
);
const charts = asDoc(
  JSON.parse(fs.readFileSync(path.join(EXAMPLES, 'charts_demo.json'), 'utf8'))
);
const PROBE_FRAME = 515; // inside s03_columns on the showcase graph

console.log(`bindings: the six events of 9.2, at frame ${PROBE_FRAME} of ` +
  `${showcase.scenes.map((s) => s.id).join(', ')}`);
console.log(`  (the frame selects the scene, so the two per-scene answers are ` +
  `scoped to ${showcase.scenes.find((s) => PROBE_FRAME >= s.startFrame && PROBE_FRAME < s.startFrame + s.durationInFrames)?.id})\n`);

// ── the table ───────────────────────────────────────────────────────────────
const EXPECTED: Record<string, boolean> = {
  'camera-settle': true,
  'chart-finish': true,
  cut: false,
  'card-arrival': false,
  'number-finish': false,
  hit: false,
};

// Header as a plain string: a format specifier such as `${'event':15}` is not valid
// inside a template expression — the `:` is read as a conditional — so the columns
// below are built with padEnd/padStart to match these widths.
console.log('  event           available        frame  source length');
console.log('  --------------- ---------- -------  --------------------');
for (const event of BINDING_EVENTS) {
  const b = bindingFor(event, showcase, PROBE_FRAME);
  console.log(
    `  ${event.padEnd(15)} ${String(b.available).padEnd(10)} ` +
    `${String(b.frame ?? 'null').padStart(7)}  ${b.source.length} chars`
  );
}

check('there are exactly six binding events', BINDING_EVENTS.length === 6,
  `got ${BINDING_EVENTS.length}`);
check('all six distinct literals are present',
  new Set(BINDING_EVENTS).size === 6, JSON.stringify(BINDING_EVENTS));

for (const event of BINDING_EVENTS) {
  const b = bindingFor(event, showcase, PROBE_FRAME);
  check(`${event}: available is ${EXPECTED[event]}`, b.available === EXPECTED[event],
    b.available === EXPECTED[event]
      ? ''
      : `the audit table says ${EXPECTED[event]}; if this genuinely changed, update ` +
        `the table here deliberately rather than letting it drift`);
}

// ── the two that answer ─────────────────────────────────────────────────────
console.log('\nthe two that answer:');
const probeScene = showcase.scenes[2];
const moveFrames = Math.ceil(2.6 * showcase.fps);
for (const event of ['camera-settle', 'chart-finish'] as const) {
  const b = bindingFor(event, showcase, PROBE_FRAME);
  check(`${event} returns an integer frame`, Number.isInteger(b.frame), `got ${b.frame}`);
  // The upper bound differs by event, and conflating them is the mistake: the chart
  // lifecycle is contained by the scene, while the camera move is deliberately NOT.
  // A 114-frame scene cannot hold a 2.6s move at 60fps, so camera settle lands at
  // frame 156 — past the end. That is the documented behaviour of cameraMoveFrames
  // ("the move is authored as if it continues past the scene"), not a bug, and a
  // guard that demanded frame <= scene would demand the camera not move.
  const upper = event === 'camera-settle'
    ? Math.max(probeScene.durationInFrames, moveFrames)
    : probeScene.durationInFrames;
  check(`${event} frame is within ${upper} frames (scene ${probeScene.durationInFrames})`,
    b.frame !== null && b.frame! >= 0 && b.frame! <= upper, `got ${b.frame}`);
  check(`${event} source names the function that answered`, b.source.length >= 40,
    `source is only ${b.source.length} chars: "${b.source}"`);
}
check('camera settle CAN exceed the scene (a 114-frame scene cannot hold 2.6s at 60fps)',
  bindingFor('camera-settle', showcase, PROBE_FRAME).frame! > probeScene.durationInFrames,
  'if this ever stops being true, cameraMoveFrames is no longer wall-clock anchored ' +
  'and this assertion is stale rather than the code');

// ── the four that do not ────────────────────────────────────────────────────
console.log('\nthe four that do not, and why:');
for (const event of BINDING_EVENTS) {
  const b = bindingFor(event, showcase, PROBE_FRAME);
  if (b.available) continue;
  check(`${event}: frame is null`, b.frame === null, `got ${b.frame}`);
  // 20 characters is the floor: `''`, `'n/a'`, `'none'` and `'unavailable'` all
  // pass a truthiness test and all tell a later reader nothing about WHY.
  check(`${event}: source explains the absence (>= 20 chars)`,
    b.source.trim().length >= 20, `got "${b.source}"`);
  check(`${event}: source is not a placeholder`,
    !/^(n\/?a|none|tbd|todo|unknown|unavailable|\-+)$/i.test(b.source.trim()),
    `"${b.source}" is a placeholder, not a reason`);
}

// ── scaling: fps for the camera, scene duration for the chart ───────────────
console.log('\nscaling, kept separate because the two events scale differently:');
const atFps = (fps: number): BindingDoc => ({
  fps,
  scenes: charts.scenes.map((s) => ({...s})),
});
for (const fps of [30, 60, 120]) {
  const doc = atFps(fps);
  const cam = bindingFor('camera-settle', doc, 0);
  const chart = bindingFor('chart-finish', doc, 0);
  console.log(`  ${String(fps).padStart(4)}fps: camera settle ${String(cam.frame).padStart(4)}  ` +
    `chart finish ${String(chart.frame).padStart(4)}  (scene ${doc.scenes[0].durationInFrames} frames)`);
}

const cam30 = bindingFor('camera-settle', atFps(30), 0).frame!;
const cam60 = bindingFor('camera-settle', atFps(60), 0).frame!;
const cam120 = bindingFor('camera-settle', atFps(120), 0).frame!;
// premium is 2.6s, wall-clock anchored: seconds * fps
check(`camera settle scales WITH fps (${cam30}, ${cam60}, ${cam120} frames)`,
  cam60 === Math.round(2.6 * 60) && cam30 === Math.round(2.6 * 30) && cam120 === Math.round(2.6 * 120),
  `expected ${Math.round(2.6 * 30)}/${Math.round(2.6 * 60)}/${Math.round(2.6 * 120)} for 2.6s`);
check('camera settle doubles between 60 and 120fps',
  Math.abs(cam120 - cam60 * 2) <= 1, `${cam60} -> ${cam120}`);

const chart30 = bindingFor('chart-finish', atFps(30), 0).frame!;
const chart60 = bindingFor('chart-finish', atFps(60), 0).frame!;
const chart120 = bindingFor('chart-finish', atFps(120), 0).frame!;
check(`chart finish does NOT scale with fps (${chart30}, ${chart60}, ${chart120} frames)`,
  chart30 === chart60 && chart60 === chart120,
  'the lifecycle is a fraction of the SCENE, and the scene is authored in frames, ' +
  'so the answer is a frame count independent of fps — if this ever starts ' +
  'moving with fps, the lifecycle and the scene length have come apart');

// and with SCENE DURATION, which is what it does scale with — SUB-linearly, and the
// reason is worth pinning because "scales with the scene" is the wrong description.
//
// `lifecycleAt` caps the entrance at `min(round(dur * 0.34), needed, dur - exit)`,
// where `needed` is the time the marks actually take to arrive plus their 0.4 settle
// tail — 48 frames for a single mark. So the intro is proportional only while the 34%
// cap binds (dur < ~141 frames) and pinned at 48 after that, and only `settle` and
// `highlight` keep growing. Focus therefore starts at 58, 93, 138 and 228 for scenes
// of 90, 150, 300 and 600 frames: monotonic, and roughly 4x over a ~6.7x longer scene.
const finishAt = (dur: number): number => focusStartFrame(dur);
const table = [90, 150, 300, 600].map((dur) => ({dur, finish: finishAt(dur)}));
console.log(`  chart finish vs scene duration: ` +
  table.map((r) => `${r.dur}f->${r.finish}`).join('  '));
check('chart finish is monotonically non-decreasing in scene duration',
  table.every((r, i) => i === 0 || r.finish >= table[i - 1].finish),
  JSON.stringify(table));
const PINNED: Record<number, number> = {90: 58, 150: 93, 300: 138, 600: 228};
for (const {dur, finish} of table) {
  check(`a ${dur}-frame scene's focus starts at ${PINNED[dur]} frames`,
    finish === PINNED[dur],
    `got ${finish}. The lifecycle maths changed — if that is intended, update this ` +
    `pin; if not, the entrance cap or EXIT_SHARE moved.`);
}
check('chart finish does NOT double when the scene doubles (the entrance is capped)',
  Math.abs(table[2].finish - table[1].finish * 2) > 2,
  `${table[1].dur}f -> ${table[1].finish}, ${table[2].dur}f -> ${table[2].finish}; ` +
  `if these were proportional the entrance cap would have stopped binding, and ` +
  `the pinned values above would need re-deriving`);
check('chart finish is a fraction of the scene, not a fixed offset',
  finishAt(150) > 0 && finishAt(150) < 150, `got ${finishAt(150)}`);

// ── the focus search must agree with the lifecycle it queries ───────────────
console.log('\nthe focus search must agree with lifecycleAt itself:');
let focusMismatches = 0;
for (const dur of [40, 60, 90, 114, 150, 229, 300, 600, 900]) {
  const start = focusStartFrame(dur);
  const before = focusStartFrame(dur) - 1;
  const atStart = lifecycleAt({frame: start, durationInFrames: dur}).phase;
  const beforePhase = start > 0
    ? lifecycleAt({frame: before, durationInFrames: dur}).phase
    : 'intro';
  if (atStart !== 'focus' || beforePhase === 'focus') {
    focusMismatches += 1;
    console.log(`  FAIL ${dur}-frame scene: focusStart ${start} is phase "${atStart}", ` +
      `frame ${before} is "${beforePhase}"`);
  }
}
check('focusStartFrame is the exact first focus frame for 9 scene lengths',
  focusMismatches === 0, `${focusMismatches} disagreed with lifecycleAt`);

console.log(failures ? `\n${failures} check(s) FAILED` : '\nall binding checks passed');
process.exit(failures ? 1 : 0);
