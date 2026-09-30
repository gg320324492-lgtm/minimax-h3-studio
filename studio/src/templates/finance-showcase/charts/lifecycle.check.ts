/**
 * Executable check of the chart lifecycle (P7.2).
 *
 * Run:  npx tsx src/templates/finance-showcase/charts/lifecycle.check.ts
 *
 * The properties that matter are the ones a render would not show you:
 *
 *  - the phases tile the scene with no gap and no overlap, at ANY duration
 *  - the entrance is capped, so a 40-frame scene is not still arriving when it
 *    cuts (this is the bug the cap exists to prevent, and it is invisible: the
 *    chart just looks like it never finished)
 *  - a mark's staggered entrance is the shared one shifted, so the LAST mark
 *    finishes after the first — a stagger where every mark arrives together is
 *    not a stagger
 *  - the exit is never zero-length
 *  - nothing overshoots: the easing is monotonic and bounded by 1
 */

import {
  clamp01, easeOut, enterFor, lifecycleAt, PHASES, staggerPosition, WEIGHTS,
} from './lifecycle';

let failures = 0;
const check = (name: string, ok: boolean, detail = ''): void => {
  if (ok) {
    console.log(`  ok   ${name}`);
  } else {
    failures += 1;
    console.log(`  FAIL ${name}${detail ? ` — ${detail}` : ''}`);
  }
};
const near = (a: number, b: number, eps = 1e-9): boolean => Math.abs(a - b) <= eps;

console.log('lifecycle: the easing never overshoots and never leaves [0,1]');
check('easeOut is monotone', [-1, 0, 0.1, 0.5, 0.9, 1, 2].every((x, i, a) => i === 0 || easeOut(a[i - 1]) <= easeOut(x) + 1e-12));
check('easeOut is bounded', [-5, -1, 0, 0.5, 1, 5].every((x) => easeOut(x) >= 0 && easeOut(x) <= 1));
check('easeOut hits its ends', easeOut(0) === 0 && easeOut(1) === 1);
check('easeOut has no overshoot at the top', easeOut(0.9) <= 1 && near(easeOut(0.9), 0.999, 1e-3));
check('clamp01 clamps', clamp01(-3) === 0 && clamp01(4) === 1 && clamp01(0.5) === 0.5);

console.log('lifecycle: phases tile the scene at any duration');
for (const dur of [40, 90, 150, 229, 600, 1800]) {
  // sample every frame; the phase must be defined everywhere and change only
  // at boundaries, so the sequence must have exactly len(PHASES) runs
  const seq: string[] = [];
  for (let f = 0; f < dur; f += 1) seq.push(lifecycleAt({frame: f, durationInFrames: dur}).phase);
  const runs = seq.filter((p, i) => i === 0 || p !== seq[i - 1]);
  check(`dur=${dur} visits every phase in order`,
    JSON.stringify(runs) === JSON.stringify([...PHASES]), JSON.stringify(runs));
  check(`dur=${dur} has no undefined frame`,
    lifecycleAt({frame: dur, durationInFrames: dur}).phase === 'exit');
  check(`dur=${dur} clamps a negative frame`,
    lifecycleAt({frame: -5, durationInFrames: dur}).frameInScene === 0);
  check(`dur=${dur} clamps an overrunning frame`,
    lifecycleAt({frame: dur * 3, durationInFrames: dur}).frameInScene === dur);
}

console.log('lifecycle: the entrance is capped, so a short scene still finishes');
{
  // a chart of 40 frames cannot afford a 34-frame spring plus a stagger
  const life = lifecycleAt({
    frame: 40, durationInFrames: 40, count: 24,
    opts: {enterFrames: 34, staggerFrames: 2},
  });
  check('entrance is capped below the naive need', life.entranceFrames < 34 * 1.4 + 2 * 23,
    `${life.entranceFrames} vs naive ${34 * 1.4 + 2 * 23}`);
  check('everything has arrived by the end of a 40-frame scene',
    life.enter === 1, `enter=${life.enter}`);
}
{
  // and a long scene is not stretched to fill itself
  const life = lifecycleAt({
    frame: 100, durationInFrames: 1800, count: 5,
    opts: {enterFrames: 34, staggerFrames: 2},
  });
  check('a long scene does not stretch the entrance', life.entranceFrames <= 34 * 1.4 + 2 * 4 + 1,
    `${life.entranceFrames}`);
}

console.log('lifecycle: a stagger is marks arriving at DIFFERENT times');
{
  const count = 5;
  const staggerFrames = 6;
  const dur = 200;
  const opts = {enterFrames: 30, staggerFrames};
  const at = (f: number) => lifecycleAt({frame: f, durationInFrames: dur, count, opts});
  const entrance = at(0).entranceFrames;
  const firstAt = (i: number) => {
    for (let f = 0; f < dur; f += 1) {
      if (enterFor(at(f), i, staggerFrames) >= 0.999) return f;
    }
    return -1;
  };
  const f0 = firstAt(0);
  const fLast = firstAt(count - 1);
  check('the last mark finishes after the first', fLast > f0, `first=${f0} last=${fLast}`);
  check('the gap matches the stagger', near(fLast - f0, staggerFrames * (count - 1), 2),
    `gap=${fLast - f0}, expected ~${staggerFrames * (count - 1)}`);
  check('every mark is monotonic', [0, 1, 2, 3, 4].every((i) => {
    let prev = -1;
    for (let f = 0; f < dur; f += 1) {
      const v = enterFor(at(f), i, staggerFrames);
      if (v < prev - 1e-9) return false;
      prev = v;
    }
    return true;
  }));
  check('a mark before its delay has not started', enterFor(at(0), count - 1, staggerFrames) === 0);
  check('staggerPosition spans 0..1',
    staggerPosition(0, 5) === 0 && near(staggerPosition(4, 5), 1) && staggerPosition(0, 1) === 0);
}

console.log('lifecycle: emphasis rises, then is HELD');
{
  const dur = 200;
  const life = (f: number) => lifecycleAt({frame: f, durationInFrames: dur, count: 5, emphasisIndex: 2});
  const intro = life(Math.round(dur * 0.05));
  const settle = life(Math.round(dur * 0.4));
  const held1 = life(Math.round(dur * 0.6));
  const held2 = life(Math.round(dur * 0.85));
  check('emphasis is not there at the start', intro.emphasis < 0.9, `${intro.emphasis}`);
  check('emphasis has arrived by the settle', settle.emphasis > 0.9, `${settle.emphasis}`);
  check('emphasis is HELD through highlight and focus',
    near(held1.emphasis, 1, 1e-6) && near(held2.emphasis, 1, 1e-6),
    `${held1.emphasis} / ${held2.emphasis}`);
  check('focus is the reading moment', life(Math.round(dur * 0.85)).reading === true);
  check('intro is not a reading moment', intro.reading === false);
  const noEmphasis = lifecycleAt({frame: 40, durationInFrames: dur, count: 5});
  check('with no emphasis, emphasis tracks the plain entrance',
    noEmphasis.emphasis === noEmphasis.enter);
}

console.log('lifecycle: the exit is never zero-length and always lands');
for (const dur of [40, 90, 229, 1800]) {
  const life = lifecycleAt({frame: dur, durationInFrames: dur, count: 3});
  check(`dur=${dur} exit completes`, life.exit === 1 && life.presence === 0, JSON.stringify(life));
  const mid = lifecycleAt({frame: dur - 2, durationInFrames: dur, count: 3});
  check(`dur=${dur} presence has started falling before the last frame`, mid.presence < 1,
    `${mid.presence}`);
}

console.log('lifecycle: the weights are a budget');
{
  const total = WEIGHTS.intro + WEIGHTS.settle + WEIGHTS.highlight + WEIGHTS.focus;
  check('weights sum to 1', near(total, 1, 1e-9), `${total}`);
  check('focus gets the largest share', WEIGHTS.focus === Math.max(...Object.values(WEIGHTS)));
  check('settle is the shortest', WEIGHTS.settle === Math.min(...Object.values(WEIGHTS)));
}

if (failures) {
  console.error(`\n${failures} check(s) FAILED`);
  process.exit(1);
}
console.log('\nall lifecycle checks passed');
