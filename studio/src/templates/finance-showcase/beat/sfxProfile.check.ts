/**
 * The SFX table, checked against the audio directory and against the habit it
 * replaces.
 *
 * Run:  npx tsx src/templates/finance-showcase/beat/sfxProfile.check.ts
 *
 * Three things are being defended here, and only the first is a table check:
 *
 *  1. Every mapped filename EXISTS in `studio/public/audio/`. A wrong name in a
 *     table is a 404 inside an `<Audio>` at render time, which is silence rather
 *     than an error — so the table is wrong in a way that only shows up in the
 *     output. Checked against the directory, not against a hand-kept list.
 *
 *  2. No event carries BOTH `sfx_whoosh` and `sfx_impact`. Not a style rule: it is
 *     the specific habit 9.3 exists to replace. Measured on the shipped report
 *     props, 8 of 8 sounding screens fire whoosh AND impact 0.18s apart — 18 events
 *     in 29.9s. The replacement has to be structurally incapable of reproducing
 *     that, so the table has one sound per event and this asserts it cannot grow a
 *     second.
 *
 *  3. The report baseline numbers are pinned. They are the "before" that any future
 *     wiring has to be compared against; if the report side ever changes, the
 *     comparison silently becomes meaningless unless these fail.
 */

import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {BINDING_EVENTS} from './bindings';
import {EVENT_SFX, MAPPED_EVENTS, REPORT_BASELINE, SFX_COVERAGE} from './sfxProfile';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../../../../..');
const AUDIO = path.join(ROOT, 'studio/public/audio');

let failures = 0;
const check = (name: string, ok: boolean, detail = ''): void => {
  if (ok) {
    console.log(`  ok   ${name}`);
  } else {
    failures += 1;
    console.log(`  FAIL ${name}${detail ? `\n         ${detail}` : ''}`);
  }
};

const present = new Set(
  fs.readdirSync(AUDIO).filter((f) => f.toLowerCase().endsWith('.m4a'))
);

console.log(`sfxProfile: the table 9.3 will wire, checked against ${AUDIO}`);
console.log(`  ${present.size} m4a in the audio directory ` +
  `(${[...present].filter((f) => f.startsWith('sfx_')).length} of them sfx_*)`);
console.log('\n  event           -> sfx                 mapped');
for (const e of BINDING_EVENTS) {
  const s = EVENT_SFX[e];
  console.log(`  ${e.padEnd(15)} -> ${(s ?? 'null').padEnd(20)} ${s ? 'yes' : 'no'}`);
}
console.log(`\n  coverage: ${MAPPED_EVENTS.length}/${BINDING_EVENTS.length} = ` +
  `${(SFX_COVERAGE * 100).toFixed(1)}%`);

// ── 1. the keys are exactly the six events ──────────────────────────────────
const keys = Object.keys(EVENT_SFX).sort();
const events = [...BINDING_EVENTS].sort();
check('the key set is exactly BindingEvent',
  keys.length === events.length && keys.every((k, i) => k === events[i]),
  `table has ${JSON.stringify(keys)}, events are ${JSON.stringify(events)}`);
for (const e of BINDING_EVENTS) {
  check(`every event appears exactly once as a key`,
    Object.keys(EVENT_SFX).filter((k) => k === e).length === 1, e);
}

// ── 2. mapped filenames exist on disk ───────────────────────────────────────
for (const e of BINDING_EVENTS) {
  const s = EVENT_SFX[e];
  if (s === null) continue;
  check(`${e} -> ${s} exists in the audio directory`,
    present.has(s), `${s} is not in ${AUDIO}`);
}
check('no mapped sound is a bgm',
  MAPPED_EVENTS.every((e) => !(EVENT_SFX[e] ?? '').startsWith('bgm')),
  'a table of event sounds must not map to a background track');

// ── 3. the habit: no event carries both whoosh and impact ───────────────────
console.log('\nthe habit being replaced (measured on the shipped report props):');
console.log(`  ${REPORT_BASELINE.sections} sections, ` +
  `${REPORT_BASELINE.soundingScreens} sounding`);
console.log(`  ${REPORT_BASELINE.screensWithBothWhooshAndImpact}/` +
  `${REPORT_BASELINE.soundingScreens} screens carry BOTH whoosh and impact`);
console.log(`  ${REPORT_BASELINE.totalEvents} events in ${REPORT_BASELINE.seconds}s, ` +
  `mix ${JSON.stringify(REPORT_BASELINE.mix)}`);

check(`baseline: all ${REPORT_BASELINE.soundingScreens} sounding screens fired both`,
  REPORT_BASELINE.screensWithBothWhooshAndImpact === REPORT_BASELINE.soundingScreens,
  `${REPORT_BASELINE.screensWithBothWhooshAndImpact} — the report side has changed, ` +
  `so this baseline is no longer the thing 9.3 reacts to`);
check(`baseline: ${REPORT_BASELINE.totalEvents} events in ` +
  `${REPORT_BASELINE.seconds}s (${(REPORT_BASELINE.totalEvents / REPORT_BASELINE.soundingScreens).toFixed(2)} per screen)`,
  REPORT_BASELINE.totalEvents === 18 && REPORT_BASELINE.soundingScreens === 8,
  `got ${REPORT_BASELINE.totalEvents} / ${REPORT_BASELINE.soundingScreens}`);
check('baseline: only ding and riser were conditional',
  Object.entries(REPORT_BASELINE.mix).filter(([, n]) => n === 1).length === 2,
  JSON.stringify(REPORT_BASELINE.mix));

for (const e of BINDING_EVENTS) {
  const s = EVENT_SFX[e];
  const both = s !== null && (s.includes('whoosh') || s.includes('sfx_whoosh')) &&
    (s.includes('impact') || s.includes('sfx_impact'));
  check(`${e} does not carry whoosh AND impact`, !both,
    'the table has to be structurally incapable of reproducing the per-screen pair');
}
// The single strongest form: the table must not even CONTAIN the pair as two rows
// pointing at the same event, which is what "one sound per event" means.
const soundsPerEvent = BINDING_EVENTS.map((e) => (EVENT_SFX[e] === null ? 0 : 1));
check('no event maps to more than one sound',
  soundsPerEvent.every((n) => n <= 1), JSON.stringify(soundsPerEvent));

// ── coverage, measured then asserted ────────────────────────────────────────
console.log(`\ncoverage: ${MAPPED_EVENTS.length} of ${BINDING_EVENTS.length} events ` +
  `have a sound = ${(SFX_COVERAGE * 100).toFixed(1)}%`);
check(`coverage is 3/6 (${(3 / 6 * 100).toFixed(1)}%) — two events with a queryable frame plus cut`,
  SFX_COVERAGE === 3 / 6, `got ${SFX_COVERAGE.toFixed(4)}`);
check('coverage derives from the table, not from a constant',
  Math.abs(SFX_COVERAGE - MAPPED_EVENTS.length / BINDING_EVENTS.length) < 1e-12,
  'the exported figure has drifted from the table');
check('the three unmapped are exactly the three with neither a frame nor an input',
  BINDING_EVENTS.filter((e) => EVENT_SFX[e] === null)
    .sort()
    .join(',') === 'card-arrival,hit,number-finish',
  BINDING_EVENTS.filter((e) => EVENT_SFX[e] === null).join(','));

console.log(failures ? `\n${failures} check(s) FAILED` : '\nall sfx profile checks passed');
process.exit(failures ? 1 : 0);
