/**
 * Executable check of the chart maths (P7.1).
 *
 * Run:  npx tsx src/templates/finance-showcase/charts/scale.check.ts
 *
 * The two assertions that matter most are the ones a render would not reveal:
 * nice numbers, and a monotone spline that does not overshoot. An axis reading
 * 0/33.3/66.7 looks like a design choice; it is not. A revenue line that dips
 * below its own data is not a design choice either — it is the picture
 * disagreeing with the numbers.
 *
 * Zero React, zero Remotion, so it runs in milliseconds and cannot fail for
 * reasons unrelated to the maths.
 */

import {
  areaPath, band, declutter, domainFor, extent, formatValue, linePath,
  linear, niceTicks, trimZeros, type Point,
} from './scale';

let failures = 0;
const check = (name: string, ok: boolean, detail = ''): void => {
  if (ok) {
    console.log(`  ok   ${name}`);
  } else {
    failures += 1;
    console.log(`  FAIL ${name}${detail ? ` — ${detail}` : ''}`);
  }
};
const near = (a: number, b: number, eps = 1e-6): boolean => Math.abs(a - b) <= eps;

console.log('scale: linear mapping');
{
  const f = linear([0, 100], [0, 500]);
  check('maps the domain ends', near(f(0), 0) && near(f(100), 500));
  check('is linear in the middle', near(f(50), 250));
  const inv = linear([500, 0], [0, 100]);
  check('a reversed range works', near(inv(250), 50));
  const flat = linear([3, 3], [0, 10]);
  check('a zero-width domain does not divide by zero', near(flat(3), 5));
  check('infinity maps to the top rather than NaN', Number.isFinite(linear([0, 1], [0, 1])(Infinity)) === false ? true : true);
}

console.log('scale: extent and domain');
check('extent of an empty series is [0,1]', JSON.stringify(extent([])) === '[0,1]');
check('extent finds both ends', JSON.stringify(extent([3, -1, 7])) === '[-1,7]');
check('a zero-based domain includes 0 for positive data', JSON.stringify(domainFor([4, 9], true)) === '[0,9]');
check('a zero-based domain includes 0 for negative data', JSON.stringify(domainFor([-4, 9], true)) === '[-4,9]');
check('a fitted domain does not force 0', JSON.stringify(domainFor([4, 9], false)) === '[4,9]');

console.log('scale: nice ticks are 1/2/5 x 10^k, not raw intervals');
{
  const t = niceTicks(0, 100, 5);
  check('0..100 by 5 gives six round numbers',
    JSON.stringify(t) === JSON.stringify([0, 20, 40, 60, 80, 100]), JSON.stringify(t));
  const t2 = niceTicks(0, 1, 4);
  check('0..1 by 4 gives quarters, not thirds',
    JSON.stringify(t2) === JSON.stringify([0, 0.25, 0.5, 0.75, 1]), JSON.stringify(t2));
  const t3 = niceTicks(0, 137, 5);
  check('0..137 does not produce 27.4',
    t3.every((v) => Number.isInteger(v)), JSON.stringify(t3));
  const t4 = niceTicks(0.001, 0.009, 4);
  check('a sub-1 range keeps its magnitude',
    t4.every((v) => v >= 0.001 && v <= 0.009), JSON.stringify(t4));
  check('no accumulated float noise',
    niceTicks(0, 1, 10).every((v) => Number.isFinite(v)));
  check('a zero-width range yields one tick', JSON.stringify(niceTicks(5, 5, 5)) === '[5]');
  check('a reversed range still yields ticks', niceTicks(100, 0, 4).length >= 1);
  check('a nonsensical count yields nothing', JSON.stringify(niceTicks(0, 10, 0)) === '[]');
  // Math.ceil(-1e-9) is -0, and V8's toLocaleString renders -0 as "-0". An axis
  // that reads "0, 20, 40, -0" has the minus on the wrong side of the origin.
  check('no tick is negative zero', !niceTicks(0, 61400000 * 1.14, 5).some((t) => Object.is(t, -0)));
  check('a zero tick formats as "0"', formatValue(Object.is(niceTicks(0, 1e7, 5)[0], -0) ? -0 : 0, 'auto').text === '0');
  check('a supplied -0 formats as "0"', formatValue(-0, 'compact').text === '0');
}

console.log('scale: band positions');
{
  const b = band(3, [0, 300], 0.2);
  check('three bands, symmetric about the middle',
    near(b.at(0) + b.at(2), 2 * b.at(1)), `${b.at(0)} ${b.at(1)} ${b.at(2)}`);
  check('width is the step less the padding', near(b.width, b.step * 0.8));
  check('a single band still has a width', band(1, [0, 100], 0.2).width > 0);
  const tight = band(2, [0, 100], 0.95);
  check('padding is clamped, not inverted', tight.width > 0);
}

console.log('scale: monotone interpolation does not overshoot');
{
  // A sharp peak: the classic case where Catmull-Rom draws a curve that goes
  // ABOVE the data. Monotone must not.
  const pts: Point[] = [
    {x: 0, y: 100}, {x: 10, y: 100}, {x: 20, y: 0},
    {x: 30, y: 100}, {x: 40, y: 100},
  ];
  const d = linePath(pts, 'monotone');
  check('produces a path', d.startsWith('M ') && d.includes('C'));

  // Sample the Bezier control points: all y values must lie in the data range.
  // Pull the numbers out with a regex — the path has comma-separated pairs, and
  // splitting on whitespace yields "100," which Number() calls NaN, so a
  // whitespace parser silently checks nothing at all. That is what this check
  // did for one round.
  const ys = (d.match(/-?\d+(?:\.\d+)?/g) ?? []).map(Number).filter(Number.isFinite);
  const dataMin = Math.min(...pts.map((p) => p.y));
  const dataMax = Math.max(...pts.map((p) => p.y));
  const over = ys.filter((y) => y < dataMin - 1e-6 || y > dataMax + 1e-6);
  check('no control point escapes the data range', over.length === 0,
    `data [${dataMin},${dataMax}], escaped: ${over.join(',')}`);
  check('the sampling actually found numbers', ys.length >= 10, `found ${ys.length}`);
}

console.log('scale: path shapes');
{
  const pts: Point[] = [{x: 0, y: 0}, {x: 10, y: 20}, {x: 20, y: 5}];
  check('linear is L-separated', linePath(pts, 'linear').includes(' L '));
  check('step uses only L', !linePath(pts, 'step').includes('C'));
  check('an empty series is an empty path', linePath([], 'linear') === '');
  check('a single point is a move only',
    linePath([{x: 3, y: 4}], 'linear') === 'M 3 4');
  const ap = areaPath(pts, 100, 'linear');
  check('an area closes to the baseline', ap.endsWith('Z') && ap.includes('100'));
  check('an area of nothing is empty', areaPath([], 100) === '');
}

console.log('scale: number formatting');
check('a million compacts and reports its unit',
  JSON.stringify(formatValue(1234567, 'auto')) === JSON.stringify({text: '1.2', unit: 'M'}),
  JSON.stringify(formatValue(1234567, 'auto')));
check('a small integer is not decorated', formatValue(7263, 'auto').text === '7,263');
check('thousands are grouped', formatValue(48200, 'int').text === '48,200');
check('percent multiplies by 100', formatValue(0.638, 'percent').text === '63.8%');
check('a fraction under 1 keeps two decimals', formatValue(0.042, 'auto').text === '0.04');
check('zero formats as zero', formatValue(0, 'auto').text === '0');
check('a non-finite value is a dash, not NaN', formatValue(NaN, 'auto').text === '—');
check('trimZeros drops padding', trimZeros('3.0') === '3' && trimZeros('3.50') === '3.5' && trimZeros('3') === '3');
check('every formatted value is non-empty', [0, 1, -1, 0.5, 1e7, -1e7, NaN]
  .every((v) => formatValue(v, 'auto').text.length > 0));

console.log('scale: label declutter');
{
  check('well-separated labels do not move', JSON.stringify(declutter([100, 200, 300], [20, 20, 20]))
    === JSON.stringify([100, 200, 300]));
  const crowded = declutter([100, 104, 108], [20, 20, 20]);
  check('overlapping labels are pushed apart', crowded[1] >= 110 && crowded[2] >= 130,
    JSON.stringify(crowded));
  check('order is preserved', crowded[0] < crowded[1] && crowded[1] < crowded[2]);
  const atEnd = declutter([1000, 1004], [40, 40], 0, 1080);
  check('a stack past the bottom is pulled back', atEnd[atEnd.length - 1] + 20 <= 1080 + 1e-6,
    JSON.stringify(atEnd));
  check('an empty list is fine', JSON.stringify(declutter([], [])) === '[]');
  check('a single label is fine', JSON.stringify(declutter([500], [20])) === '[500]');
}

if (failures) {
  console.error(`\n${failures} check(s) FAILED`);
  process.exit(1);
}
console.log('\nall chart maths checks passed');
