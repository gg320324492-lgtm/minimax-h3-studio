/**
 * The shipped `formatValue` and the Python mirror in `studio/scripts/
 * vlm_critic.py` must agree, on a corpus, or the mirror is not a mirror.
 *
 * WHY THIS EXISTS. `vlm_critic.format_value` is a Python port, because calling
 * the real one per probe would mean a node subprocess per question. A port
 * nobody checks is a second opinion wearing a mirror's clothes: P24 measured
 * two renders of one graph disagreeing on `font_size` by 96.9% while agreeing
 * on the verdict 1356/1356 times. A silently divergent formatter would make
 * `frame_shows_expected_text` FAIL a correct frame — a false positive in the
 * one rule this module is allowed to have.
 *
 * So the corpus below is emitted by BOTH sides and compared as text. It is
 * not a list of values I typed with their expected outputs beside them; both
 * sides compute, and this file only checks that they computed the same thing.
 * That distinction is the whole reason the check is here rather than in the
 * pytest file: a table of "48200000 -> 48.2M" written by hand is only as
 * correct as the hand.
 *
 * The corpus covers every format the option type declares, plus the values
 * either side of each compaction boundary (999/1000, 999999/1e6, 1e9/1e12),
 * because a boundary is where a port goes wrong and nowhere else.
 *
 * Run: npx tsx src/templates/finance-showcase/charts/format_value_mirror.check.ts
 * Exit 1 on the first disagreement.
 */
import {formatValue} from './scale';

/** The corpus. Pairs of (value, format) — the answers are computed, not typed. */
const CORPUS: [number, string][] = [];
const FORMATS = ['auto', 'int', 'one', 'two', 'percent', 'compact'] as const;

const VALUES = [
  0, -0, 1, -1, 0.5, -0.5, 0.04, 0.638, 9.99, 10, 12, 22, 31, 42, 99, 100,
  999, 1000, 1001, 12_345, 99_999, 999_999, 1_000_000, 1_048_576,
  48_200_000, 61_400_000, 1_000_000_000, 1_234_567_890, 1e12, 2.5e12,
  -48_200_000, -0.638,
];
for (const v of VALUES) for (const f of FORMATS) CORPUS.push([v, f]);

/**
 * The string ON SCREEN, which is `valueText` in ChartFrame.tsx:
 *
 *     valueText: (v) => { const f = formatValue(v, opts.valueFormat);
 *                        return f.unit ? `${f.text}${f.unit}` : f.text; }
 *
 * Not `formatValue(v).text`. That distinction is the whole point: a compacted
 * value returns text '48.2' and unit 'M' SEPARATELY, and the viewer reads
 * '48.2M'. Comparing the Python mirror against `.text` alone would report a
 * disagreement over a space, and comparing against the wrong one would pass
 * while the expected string still lacked the unit that appears in every
 * screenshot of this film.
 */
const emit = (v: number, f: string): string => {
  const r = formatValue(v, f as never);
  return r.unit ? `${r.text}${r.unit}` : r.text;
};

const lines = CORPUS.map(([v, f]) => `${JSON.stringify(v)}\t${f}\t${emit(v, f)}`);
process.stdout.write(lines.join('\n') + '\n');
