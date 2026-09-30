/**
 * Executable check of the perspective maths (P6.2 regression guard).
 *
 * Run:  npx tsx src/templates/finance-showcase/common/projection.check.ts
 *
 * This exists because a bug shipped in exactly this maths and no amount of
 * reading the source would have caught it: screenScaleFor returned the
 * magnification P/(P-z) instead of its inverse (P-z)/P. Both are plausible-
 * looking one-liners, they differ only in which way round the fraction is, and
 * the wrong one produced a stack that drifted 33px right on a 1920 frame. The
 * assertion that catches it is the round-trip, not a reading of the code.
 *
 * Deliberately dependency-free (no react, no remotion) so it runs in a
 * millisecond and cannot fail for reasons unrelated to the maths.
 */

import {cssXForScreenX, projectX, screenScaleFor} from './projection';

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

console.log('projection: cssXForScreenX must be the inverse of projectX');
for (const P of [1400, 800, 4000]) {
  for (const z of [-220, -90, 0, 90, 220]) {
    for (const screenX of [-300, -190, 0, 190, 300]) {
      const back = projectX(cssXForScreenX(screenX, z, P), z, P);
      if (!near(back, screenX)) {
        check(`round-trip P=${P} z=${z} x=${screenX}`, false, `got ${back}`);
      }
    }
  }
}
check('round-trip over 75 combinations', true);

console.log('projection: screenScaleFor must CANCEL the projection, not apply it');
// The invariant that was violated: scale * (P / (P - z)) === 1
for (const P of [1400, 800]) {
  for (const z of [-220, -150, -90, 0, 90, 150, 220]) {
    const k = screenScaleFor(z, P);
    const applied = k * (P / (P - z));
    if (!near(applied, 1, 1e-12)) {
      check(`scale cancels P=${P} z=${z}`, false, `k=${k} -> ${applied}x, expected 1x`);
    }
  }
}
check('scale cancels projection at 14 combinations', true);

// Direction, spelled out: a NEAR object (z > 0) is magnified by the
// projection, so its counter-scale must be SMALLER than 1. Getting this
// backwards is the bug — it would enlarge near objects further.
check('near plane counter-scales DOWN', screenScaleFor(90, 1400) < 1, `got ${screenScaleFor(90, 1400)}`);
check('far plane counter-scales UP', screenScaleFor(-90, 1400) > 1, `got ${screenScaleFor(-90, 1400)}`);
check('worked example 1310/1400', near(screenScaleFor(90, 1400), 1310 / 1400));
check('worked example 1490/1400', near(screenScaleFor(-90, 1400), 1490 / 1400));

console.log('projection: a stack authored symmetric stays symmetric on screen');
// This is the property the whole fix exists to deliver: even screen spacing
// about the axis, each window at its own depth, must land symmetrically.
{
  const P = 1400;
  const spreadX = 300;
  const spreadZ = 150;
  const n = 3;
  const c = (n - 1) / 2;
  const screen: number[] = [];
  for (let i = 0; i < n; i += 1) {
    const planeZ = (i - c) * spreadZ;
    // camera at rest: absolute depth is the plane's own
    const cssX = cssXForScreenX((i - c) * spreadX, planeZ, P);
    screen.push(projectX(cssX, planeZ, P));
  }
  check('outer windows mirror', near(screen[0], -screen[n - 1], 1e-9), `got ${screen.join(', ')}`);
  check('middle window on the axis', near(screen[1], 0, 1e-9), `got ${screen.join(', ')}`);
  check('spacing is the authored spacing', near(screen[2] - screen[1], spreadX, 1e-9));
}

console.log('projection: degenerate inputs pass through instead of exploding');
check('no perspective -> x unchanged', projectX(123, 90, 0) === 123);
check('no perspective -> scale is 1', screenScaleFor(90, 0) === 1);
check('behind the eye -> x unchanged', projectX(123, 2000, 1400) === 123);
check('behind the eye -> scale is 1', screenScaleFor(2000, 1400) === 1);

if (failures) {
  console.error(`\n${failures} check(s) FAILED`);
  process.exit(1);
}
console.log('\nall projection checks passed');
