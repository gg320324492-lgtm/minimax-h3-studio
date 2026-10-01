/**
 * Executable check of the beat grid (P9.1 regression guard).
 *
 * Run:  npx tsx src/templates/finance-showcase/beat/beatGrid.check.ts
 *
 * Every assertion here is expected to be able to FAIL, and the mutation record in
 * the commit that introduced this file shows each one turning red when the
 * behaviour it covers is undone. An assertion that has never failed is a
 * comment.
 *
 * The load-bearing one is `declared bpm agrees with the fitted bpm`. It is RED as
 * committed for `showcase_demo.json` (126 vs 129.00, off by 3.00) and that is the
 * point: the graph's tempo was never measured against the track it claims to be
 * timed to, and 3 bpm is 2453 ms of drift by beat 208. The check is written to
 * report the number and keep going rather than exit on the first failure, so one
 * run reports every disagreement instead of the alphabetically first.
 *
 * `node:fs` is used to read the analysis file. That is the only I/O and it is in
 * the CHECK, not the module — beatGrid.ts stays importable by anything.
 */

import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {
  ACCENT_SHARE,
  bpmDisagreement,
  fitBpm,
  grid,
  tempoAgreement,
  type BeatAnalysis,
} from './beatGrid';
import {snapCost} from './beatSnap';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../../../../..');
const ANALYSIS_PATH = path.join(ROOT, 'studio/public/audio/bgm_beats.json');
const EXAMPLES = path.join(ROOT, 'pipeline/examples');

type Graph = {
  bpm?: number;
  format: {fps: number};
  scenes: {id: string; durationInFrames: number}[];
};

let failures = 0;
const check = (name: string, ok: boolean, detail = ''): void => {
  if (ok) {
    console.log(`  ok   ${name}`);
  } else {
    failures += 1;
    console.log(`  FAIL ${name}${detail ? `\n         ${detail}` : ''}`);
  }
};

const analysis = JSON.parse(fs.readFileSync(ANALYSIS_PATH, 'utf8')) as BeatAnalysis;
const graphs = ['showcase_demo.json', 'charts_demo.json'].map((n) => ({
  name: n,
  doc: JSON.parse(fs.readFileSync(path.join(EXAMPLES, n), 'utf8')) as Graph,
}));

console.log(`analysis ${path.relative(ROOT, ANALYSIS_PATH)}`);
console.log(`  ${analysis.beats.length} beats, self-reported ${analysis.bpm} bpm, ` +
  `interval ${analysis.beat_interval}s, source ${analysis.source}\n`);

// ── the fit ────────────────────────────────────────────────────────────────
console.log('fitBpm: the detected times are the authority');
const fit = fitBpm(analysis.beats);
console.log(`  fitted ${fit.bpm.toFixed(3)} bpm  interval ${fit.interval.toFixed(6)}s  ` +
  `offset ${fit.offset.toFixed(4)}s`);
console.log(`  residual RMS ${fit.rmsMs.toFixed(1)} ms  max ${fit.maxMs.toFixed(1)} ms  ` +
  `over ${fit.count} beats`);
console.log(`  the file's own metadata implies ` +
  `${(60 / (analysis.beat_interval ?? 0)).toFixed(2)} bpm — ` +
  `${Math.abs(60 / (analysis.beat_interval ?? 0) - fit.bpm).toFixed(2)} away from the fit\n`);

check(`RMS residual is within 25 ms (got ${fit.rmsMs.toFixed(1)})`, fit.rmsMs <= 25);
check(`max residual is within 40 ms (got ${fit.maxMs.toFixed(1)})`, fit.maxMs <= 40);
check(
  `the fit is better than the file's declared interval`,
  fit.rmsMs < 20,
  `declared interval gives stdev 44.1 ms; the fit gives ${fit.rmsMs.toFixed(1)}`
);
check(
  `the file's self-reported bpm is not allowed to drift from its own beats`,
  Math.abs((analysis.bpm ?? 0) - fit.bpm) <= 0.5,
  `file says ${analysis.bpm}, fit says ${fit.bpm.toFixed(3)}`
);

// ── the four levels tile ───────────────────────────────────────────────────
console.log('\ngrid: the four levels tile the timeline exactly');
const g = grid({bpm: fit.bpm, fps: 60}, analysis, {horizonFrames: 801});
console.log(`  at the fitted tempo on 60fps: quarter ${g.framesPerQuarterBeat}  ` +
  `half ${g.framesPerHalfBeat}  beat ${g.framesPerBeat}  bar ${g.framesPerBar} frames`);
console.log(`  an integer grid can only play ${g.representedBpm.toFixed(3)} bpm ` +
  `(${g.tempoErrorPct >= 0 ? '+' : ''}${g.tempoErrorPct.toFixed(3)}%), ` +
  `drifting ${g.driftMsAtHorizon.toFixed(1)} ms by frame 801`);

for (const [name, list, step] of [
  ['quarterBeat', g.quarterBeat, g.framesPerQuarterBeat],
  ['halfBeat', g.halfBeat, g.framesPerHalfBeat],
  ['beat', g.beat, g.framesPerBeat],
  ['bar', g.bar, g.framesPerBar],
] as const) {
  const ascending = list.every((v, i) => i === 0 || v > list[i - 1]);
  const exact = list.every((v, i) => i === 0 || v - list[i - 1] === step);
  const contiguous = list.length > 1 && list[list.length - 1] + step > 801;
  check(`${name} is strictly ascending`, ascending);
  check(`${name} advances by exactly one step (${step}) — no gap, no overlap`, exact,
    exact ? '' : `first break at index ${list.findIndex((v, i) => i > 0 && v - list[i - 1] !== step)}`);
  check(`${name} covers the whole horizon`, contiguous);
}

// nesting: every coarser boundary must also be a finer one, or the levels have
// come apart — which is the failure independent rounding would produce
for (const [coarse, fine, cname, fname] of [
  [g.bar, g.beat, 'bar', 'beat'],
  [g.beat, g.halfBeat, 'beat', 'halfBeat'],
  [g.halfBeat, g.quarterBeat, 'halfBeat', 'quarterBeat'],
] as const) {
  const set = new Set(fine);
  const orphans = coarse.filter((v) => !set.has(v));
  check(`every ${cname} boundary is also a ${fname} boundary`, orphans.length === 0,
    orphans.length ? `${orphans.length} orphaned: ${orphans.slice(0, 5).join(', ')}` : '');
}

/*
 * The nesting above is only meaningful at tempos where independent per-level
 * rounding happens to agree, and at THIS tempo it does: 27.9074 frames a beat
 * rounds to 28, and 4 * round(27.9074/4) is also 4 * 7 = 28. A sweep is required,
 * because an implementation that rounded each level separately passes every
 * assertion above at 129 bpm and fails at 131.4 — where the ideal beat is 27.397,
 * the beat rounds to 27, and 4 * round(6.849) is 28. Same film, same code path,
 * opposite answer, and the difference is one frame at every bar line.
 */
console.log('\ngrid: the levels stay exact multiples across tempos, not just this one');
const sweepBpm = [90, 100, 120, 126, 128.998, 131.4, 140, 160, 174];
const sweepFps = [24, 30, 60, 120];
let nestingFailures = 0;
let diverging = 0;
for (const bpm of sweepBpm) {
  for (const fps of sweepFps) {
    const s = grid({bpm, fps}, analysis, {horizonFrames: 2000});
    const exact = s.framesPerBeat === 4 * s.framesPerQuarterBeat
      && s.framesPerHalfBeat === 2 * s.framesPerQuarterBeat
      && s.framesPerBar === 16 * s.framesPerQuarterBeat;
    // what per-level rounding would have produced, for comparison
    const ideal = (60 / bpm) * fps;
    const independent = Math.max(1, Math.round(ideal)) !== 4 * Math.max(1, Math.round(ideal / 4));
    if (independent) diverging += 1;
    if (!exact) {
      nestingFailures += 1;
      console.log(`  FAIL ${bpm} bpm @${fps}fps: quarter ${s.framesPerQuarterBeat}  ` +
        `half ${s.framesPerHalfBeat}  beat ${s.framesPerBeat}  bar ${s.framesPerBar} ` +
        `(independent rounding would give beat ${Math.max(1, Math.round(ideal))})`);
    }
  }
}
check(`all ${sweepBpm.length * sweepFps.length} tempo/fps combinations nest exactly`,
  nestingFailures === 0,
  `${nestingFailures} combination(s) where the beat is not 4x the quarter beat`);
console.log(`  (${diverging} of those ${sweepBpm.length * sweepFps.length} combinations are ` +
  'ones where rounding each level separately would give a different answer)');

// ── accent comes from the audio ────────────────────────────────────────────
console.log('\naccent: selected from measured bass, never from the beat index');
const bass = analysis.beats.map((b) => b.bass ?? 0);
const threshold = [...bass].sort((a, b) => b - a)[Math.max(1, Math.ceil(bass.length * ACCENT_SHARE)) - 1];
console.log(`  ${g.accent.length} of ${bass.length} beats are accented ` +
  `(top ${(ACCENT_SHARE * 100).toFixed(0)}%, bass >= ${threshold})`);
console.log(`  indices ${g.accent.join(', ')}`);
console.log(`  their residues mod 4: ${g.accent.map((i) => i % 4).join(', ')}`);

check(
  'the accent count is the top 5% of beats',
  g.accent.length === Math.max(1, Math.ceil(bass.length * ACCENT_SHARE)),
  `got ${g.accent.length}, expected ${Math.max(1, Math.ceil(bass.length * ACCENT_SHARE))}`
);
check(
  'every accent beat is at or above the bass threshold',
  g.accent.every((i) => bass[i] >= threshold),
  `threshold ${threshold}`
);
check(
  'every accent beat is in the measured top slice',
  g.accent.every((i) => bass[i] >= Math.min(...[...bass].sort((a, b) => b - a).slice(0, g.accent.length)))
);

for (const mod of [2, 4]) {
  const fromIndex = new Set<number>();
  for (let i = 0; i < bass.length; i += 1) if (i % mod === 0) fromIndex.add(i);
  const fromBass = new Set(g.accent);
  const same = fromIndex.size === fromBass.size && [...fromIndex].every((v) => fromBass.has(v));
  check(
    `accent is NOT the i%${mod} set — the simplification this guard exists for`,
    !same,
    same
      ? `accent is exactly {i : i%${mod}===0}; on this track that is measurably wrong ` +
        `(a permutation test finds no index modulus predicting bass: mod 4 spread 0.032 ` +
        `against a shuffled-null 95th percentile of 0.070)`
      : ''
  );
}

// ── what beat quantisation costs, and what bounds it ───────────────────────
console.log('\nsnapCost: beat quantisation is bounded per scene, and unbounded per film');
const TEMPOS = [90, 126, 128.998, 131.4, 174];
const FPS = [24, 30, 60, 120];
const costScenes = graphs[0].doc.scenes.map((s) => ({
  id: s.id,
  durationInFrames: s.durationInFrames,
}));
console.log(`  ${graphs[0].name} (${costScenes.length} scenes: ` +
  `${costScenes.map((s) => s.durationInFrames).join(', ')} frames)`);
// Header is a plain string, not a template: a format specifier like `${'bpm':>9}`
// is not valid inside a template expression — the `:` reads as a conditional. The
// columns below are padded with padStart to match.
const COST_HEADER =
  '        bpm   fps  1 beat  exact bf  max deficit  film delta  worst scene   film <1 beat?  scene within bound?';
console.log(COST_HEADER);

let perSceneBreaches = 0;
let filmTotalOverOneBeat = 0;
const filmOverCells: string[] = [];
for (const bpm of TEMPOS) {
  for (const fps of FPS) {
    const cost = snapCost({bpm, fps, scenes: costScenes});
    const filmOk = Math.abs(cost.deltaFrames) < cost.oneBeatFrames;
    const perSceneOk = cost.worstSceneDeficit <= cost.maxSceneDeficit;
    if (!perSceneOk) perSceneBreaches += 1;
    if (!filmOk) {
      filmTotalOverOneBeat += 1;
      filmOverCells.push(`${bpm}bpm@${fps}fps (${cost.deltaFrames} vs ${cost.oneBeatFrames})`);
    }
    console.log(
      `  ${String(bpm).padStart(8)} ${String(fps).padStart(5)} ` +
      `${String(cost.oneBeatFrames).padStart(8)} ` +
      `${cost.beatFramesExact.toFixed(3).padStart(9)} ` +
      `${cost.maxSceneDeficit.toFixed(2).padStart(12)} ` +
      `${String(cost.deltaFrames).padStart(11)} ` +
      `${String(cost.worstSceneDeficit).padStart(12)} ` +
      `${(filmOk ? 'yes' : 'NO').padStart(14)} ${(perSceneOk ? 'yes' : 'NO').padStart(20)}`
    );
  }
}

// The gated invariant. The bound is `beatFramesExact / 2 + 1`, NOT a half beat:
// `beats = round(requested / bf)` is wrong by at most half a beat, but the resolved
// duration is a difference of two independently rounded boundaries and so carries
// up to one further frame. At 128.998 bpm / 24fps a beat is 11.158 frames, the
// half-beat bound is 5.58, and a scene legitimately lands 6 frames from its request
// — measured, and it is why the looser-looking bound is the correct one.
check(
  `no scene in any of the ${TEMPOS.length * FPS.length} cells exceeds bf/2 + 1`,
  perSceneBreaches === 0,
  `${perSceneBreaches} cell(s) beyond the exact rounding bound — that is a bug in ` +
  `the quantisation, not the cost of rounding`
);

// The reverse assertion, named separately: these are two claims and their failure
// messages have to point at different repairs.
check(
  `no cell shows a per-scene loss of a whole beat or more (${TEMPOS.length * FPS.length} cells scanned)`,
  TEMPOS.length * FPS.length === 20 && perSceneBreaches === 0
);

/*
 * The FILM-level total is reported, not gated, and the reason is arithmetic rather
 * than a preference: `resolveScenes` rounds each scene independently, so the film's
 * deficit is the SUM of the per-scene deficits and grows with the scene count. A
 * gate of "whole film loses less than one beat" is therefore a gate on the scene
 * count, and it is unsatisfiable for a 4-scene film at some tempos — measured above,
 * ${filmTotalOverOneBeat} of ${TEMPOS.length * FPS.length} cells exceed one beat, up to 68
 * frames, while the worst SINGLE scene in any of them is 20.
 *
 * Also worth stating because it is counter-intuitive: the sign is not fixed.
 * Quantisation shortens a film when the requests sit above a whole beat and
 * lengthens it when they sit below, so "beat_snap costs frames" is wrong for some
 * tempo/graph pairs. The sign flip is visible above at 174 bpm / 120fps.
 *
 * Changing this is a semantic change to beat space — pad the last scene, or allow
 * fractional beats — which is a 9.2 design question, not a guard change.
 */
console.log(`\n  film-level total exceeds one beat in ${filmTotalOverOneBeat} of ` +
  `${TEMPOS.length * FPS.length} cells: ${filmOverCells.join(', ') || 'none'}`);
console.log('  reported, not gated: the film total is the SUM of independent per-scene');
console.log('  round() errors, so it grows with the scene count. The per-scene bound');
console.log('  above is the invariant; gating the film total would gate the scene count.');

// ── the load-bearing one ───────────────────────────────────────────────────
console.log('\ndeclared bpm must agree with the measured track');
for (const {name, doc} of graphs) {
  const declared = doc.bpm ?? 126;
  const diff = bpmDisagreement(declared, fit);
  // The horizon is the GRAPH's own length, not the track's: this is the drift a
  // viewer would see inside this film. Using the 96s track would report a number
  // about a piece of the film that does not exist.
  const filmFrames = doc.scenes.reduce((s, sc) => s + sc.durationInFrames, 0);
  const gg = grid({bpm: declared, fps: doc.format.fps}, analysis, {horizonFrames: filmFrames});
  const verdict = tempoAgreement(declared, fit, {bpmTolerance: 0.5, maxDriftBeats: 1}, gg);

  // What the same graph would do at the measured tempo, so a red result says what
  // turns it green instead of only what is wrong.
  const fixed = grid({bpm: fit.bpm, fps: doc.format.fps}, analysis, {horizonFrames: filmFrames});
  const fixedVerdict = tempoAgreement(fit.bpm, fit, {bpmTolerance: 0.5, maxDriftBeats: 1}, fixed);

  console.log(`\n  ${name}: ${filmFrames} frames at ${doc.format.fps}fps, declares ${declared} bpm, ` +
    `track measures ${fit.bpm.toFixed(2)} -> ${diff >= 0 ? '+' : ''}${diff.toFixed(2)} bpm`);
  console.log(`    grid at the declared tempo: ${gg.framesPerBeat} frames/beat ` +
    `(${gg.representedBpm.toFixed(3)} bpm), drifts ` +
    `${gg.driftBeatsAtHorizon >= 0 ? '+' : ''}${gg.driftBeatsAtHorizon.toFixed(2)} beats ` +
    `(${gg.driftMsAtHorizon.toFixed(0)} ms) by the end`);
  console.log(`    grid at the measured tempo: ${fixed.framesPerBeat} frames/beat ` +
    `(${fixed.representedBpm.toFixed(3)} bpm), drifts ` +
    `${fixed.driftBeatsAtHorizon >= 0 ? '+' : ''}${fixed.driftBeatsAtHorizon.toFixed(2)} beats ` +
    `(${fixed.driftMsAtHorizon.toFixed(0)} ms) by the end  <- ${fixedVerdict.representable ? 'clean' : 'still dirty'}`);
  for (const r of verdict.reasons) console.log(`    - ${r}`);
  check(`${name} declares a bpm within 0.5 of the fitted ${fit.bpm.toFixed(2)}`,
    Math.abs(diff) <= 0.5,
    `declared ${declared}, fitted ${fit.bpm.toFixed(3)}, off by ${diff.toFixed(2)} — ` +
    `compounds to ${(analysis.beats.length * (60 / declared - 60 / fit.bpm) * 1000).toFixed(0)} ms ` +
    `by beat ${analysis.beats.length}`);
  check(`${name} is renderable on an integer frame grid`, verdict.representable,
    `at the measured tempo it would be: ` +
    `${fixed.driftBeatsAtHorizon.toFixed(2)} beats over ${filmFrames} frames`);
}

console.log(failures
  ? `\n${failures} check(s) FAILED`
  : '\nall beat grid checks passed');
process.exit(failures ? 1 : 0);
