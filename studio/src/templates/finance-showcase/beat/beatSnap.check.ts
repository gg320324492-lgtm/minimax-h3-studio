/**
 * Report what `beat_snap: true` would do, and pin it (P9, step 10).
 *
 * Run:  npx tsx src/templates/finance-showcase/beat/beatSnap.check.ts
 *
 * The render path stays as it is. `FinanceShowcaseWide` calls
 * `resolveScenes(doc, false)`, and flipping that would move delivered frames, so
 * this file does not suggest it in a way anyone could mistake for a plan — it
 * answers the question "what is in that branch, then" so the branch is not
 * folklore.
 *
 * The numbers are ASSERTED as well as printed. A report nobody checks is a log
 * line; pinning them means a change to `resolveScenes`, to the rounding, or to a
 * graph's scene durations shows up as a failure here, in a file whose entire
 * subject is that branch's effect. If someone later turns `beat_snap` on
 * deliberately, these assertions will fail and say by how much the film moved —
 * which is the information that decision should be made with.
 *
 * Dependency-free: pure arithmetic plus `node:fs` and the real `resolveScenes`.
 */

import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {ShowcaseSchema, resolveScenes, type Showcase} from '../../../schemas/showcase-v1';
import {compareBeatSnap, type SceneTiming} from './beatSnap';

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

console.log('beat_snap: what the undelivered branch would do');
console.log('(FinanceShowcaseWide calls resolveScenes(doc, false); this reports, it does not change)\n');

for (const name of ['showcase_demo.json', 'charts_demo.json']) {
  const doc = ShowcaseSchema.parse(
    JSON.parse(fs.readFileSync(path.join(EXAMPLES, name), 'utf8'))
  ) as Showcase;

  // requested durations come from the graph, not from the resolved scenes
  const requested = new Map(doc.scenes.map((s) => [s.id, s.durationInFrames]));
  const shippedRaw = resolveScenes(doc, false);
  const snappedRaw = resolveScenes(doc, true);
  const withRequested = (rs: typeof shippedRaw): SceneTiming[] =>
    rs.map((r) => ({
      id: r.id,
      startFrame: r.startFrame,
      durationInFrames: r.durationInFrames,
      requestedFrames: requested.get(r.id),
    }));

  const cmp = compareBeatSnap(withRequested(shippedRaw), withRequested(snappedRaw));

  console.log(`=== ${name}  (bpm ${doc.bpm}, ${doc.format.fps}fps, ` +
    `${cmp.shippedTotal} frames)`);
  console.log('  scene                req               shipped             snapped   dStart  dLen');
  for (const r of cmp.rows) {
    // padStart rather than `${x:16}` — a format specifier is not valid inside a
    // template expression, and `:` there reads as a conditional to the parser.
    const shippedRange = `${r.shippedStart}..${r.shippedStart + r.shippedDuration}`;
    const snappedRange = `${r.snappedStart}..${r.snappedStart + r.snappedDuration}`;
    const sign = (n: number): string => `${n >= 0 ? '+' : ''}${n}`;
    console.log(
      `  ${r.id.padEnd(16)}${String(r.requested).padStart(5)} ` +
      `${shippedRange.padStart(16)} ${snappedRange.padStart(16)} ` +
      `${sign(r.startDelta).padStart(7)} ${sign(r.durationDelta).padStart(5)}` +
      `${r.lengthAdjusted ? '  length quantised' : ''}`
    );
  }
  console.log(`  total: shipped ${cmp.shippedTotal}, snapped ${cmp.snappedTotal} ` +
    `(${cmp.snappedTotal - cmp.shippedTotal >= 0 ? '+' : ''}${cmp.snappedTotal - cmp.shippedTotal})`);
  console.log(`  ${cmp.movedCount}/${cmp.rows.length} scenes would move; ` +
    `largest start shift ${cmp.maxStartDelta} frames, ` +
    `largest length change ${cmp.maxDurationDelta} frames\n`);

  /*
   * WHAT THIS MEASURED, because it is the reason beat_snap is off and the reason
   * it cannot simply be switched on:
   *
   * `resolveScenes(beat_snap=True)` computes `beats = round(requested / beat_frames)`
   * per scene and then places boundaries at `round(k * beat_frames)`. The fraction
   * of a beat in every requested duration is DISCARDED, so the snapped timeline is
   * shorter than the authored one whenever the durations are not whole beats — and
   * the loss accumulates, so later scenes start progressively earlier.
   *
   * The tempo decides how much is lost, and it is not a monotone function of it.
   * At the graph's old 126 bpm a 229-frame scene is 8.015 beats, which rounds to 8
   * for the loss of 0.015 of a beat: the snapping was effectively free, and the
   * whole film lost 1 frame. At the fitted 128.998 the same scene is 8.206 beats,
   * still rounding to 8, and now every scene carries a 0.206-beat deficit — 20
   * frames on showcase_demo, and on charts_demo it cost 10 or 11 frames per scene
   * (108 across the film as it stood with a 600-frame c10; 105 after P42
   * shortened that scene to 150). So correcting the tempo made this
   * branch lossier. Nothing delivered changes, because the render path resolves
   * with `false` and no delivered film has ever gone through this code; but it is
   * the honest consequence of the tempo fix, and it is why the numbers below are
   * pinned rather than assumed.
   *
   * Note also that 126 was free by luck, not by design. A tempo that divides the
   * graph evenly — 130.435 bpm, exactly 27.6 frames a beat at 60fps — loses 8.2
   * frames on the same scene. There is no tempo at which beat_snap is lossless for
   * an arbitrary graph; the rounding is structural.
   */

  const PINS: Record<string, {
    shippedTotal: number;
    snappedTotal: number;
    moved: number;
    maxStart: number;
  }> = {
    'showcase_demo.json': {shippedTotal: 801, snappedTotal: 781, moved: 4, maxStart: 14},
    // P42: charts_demo's c10_bar_long went 600 -> 150 frames, so these two
    // totals moved with it and were re-measured, not estimated. What the pins
    // are FOR is unchanged and is stated by the checks below them: beat_snap
    // stays lossy, and the loss is per-scene rounding. At 600 frames c10
    // absorbed 20 beats and the film lost 108 frames to the fractional-beat
    // deficit; at 150 it absorbs 5 and the film loses 105 across ten scenes of
    // 10 or 11 frames each. `maxStart` did not move (94) -- it is c10's START
    // that shifts, and shortening c10 did not change where the scenes before
    // it end.
    'charts_demo.json': {shippedTotal: 1500, snappedTotal: 1395, moved: 10, maxStart: 94},
  };
  const p = PINS[name];

  check(`${name}: shipped timeline is still ${p.shippedTotal} frames`,
    cmp.shippedTotal === p.shippedTotal, `now ${cmp.shippedTotal}`);
  check(`${name}: beat_snap would give ${p.snappedTotal} frames (pinned)`,
    cmp.snappedTotal === p.snappedTotal,
    `now ${cmp.snappedTotal} — the fractional-beat loss changed, so resolveScenes, ` +
    `the rounding, or the graph's scene durations have moved`);
  check(`${name}: beat_snap is LOSSY, by a pinned amount`,
    cmp.snappedTotal < cmp.shippedTotal,
    `snapped ${cmp.snappedTotal} >= shipped ${cmp.shippedTotal}; if this ever goes ` +
    `non-negative the quantisation changed and the report above is stale`);
  check(`${name}: ${p.moved} scene(s) would move (pinned)`,
    cmp.movedCount === p.moved, `now ${cmp.movedCount}`);
  check(`${name}: largest start shift ${p.maxStart} frames (pinned)`,
    cmp.maxStartDelta === p.maxStart, `now ${cmp.maxStartDelta}`);
  check(`${name}: every snapped length is quantised to whole beats`,
    cmp.rows.every((r) => r.lengthAdjusted),
    'a scene whose length was not quantised means beat_snap was not applied to it');
}

console.log('\nfor the record: the shipped path');
const demo = ShowcaseSchema.parse(
  JSON.parse(fs.readFileSync(path.join(EXAMPLES, 'showcase_demo.json'), 'utf8'))
) as Showcase;
const src = fs.readFileSync(
  path.join(ROOT, 'studio/src/templates/finance-showcase/FinanceShowcaseWide.tsx'), 'utf8');
const callLine = src.split('\n').find((l) => l.includes('resolveScenes('))?.trim() ?? '(not found)';
console.log(`  FinanceShowcaseWide: ${callLine}`);
check('the render path still resolves without beat_snap', callLine.includes('doc, false'),
  `found: ${callLine}`);

console.log(failures ? `\n${failures} check(s) FAILED` : '\nall beat_snap report checks passed');
process.exit(failures ? 1 : 0);
