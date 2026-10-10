"""p46_font_measure.py — can anything tell SERIF from SANS, and where?

THREE INSTRUMENTS WERE TRIED. This one is the third, and it is the only one
whose accuracy can be SCORED, because the control corpus's font is known by
construction rather than by anybody's opinion of a picture.

  1. `p46_font_probe.statistics` — frame-level stroke contrast.
     MEASURED: serif 6.00-11.76, sans 5.25-22.00. The clouds overlap.
  2. `p46_font_probe.glyph_statistics` — per-glyph stroke contrast.
     MEASURED: serif median 1.600-2.160, sans 2.500-2.875. The clouds do NOT
     overlap — but the sans cloud sits entirely ABOVE the serif cloud, which is
     the OPPOSITE of what the statistic claims to measure. A serif detector
     that ranks Arial's strokes as more contrasty than Georgia's is not a weak
     detector, it is one pointing the wrong way, and shipping it because it
     separates would be the exact "a criterion that can be wrong about a
     correct artefact" P17 rules out. NOT SHIPPED.
  3. This module — a closed question to the model, scored on the corpus whose
     answer is known.

WHAT IS SCORED AND WHAT IS NOT, and why that line is the whole result
---------------------------------------------------------------------
SCORED: the 11 control cards. Their font is a `.ttf` path this module chose, so
"SERIF" is a fact about the input and the model is being scored, not trusted.

NOT SCORED: this project's own renders, and the reference film. For those the
true typeface is unknown to the measurement, so an answer can be recorded and
reported but can never be marked right. `expected=None` is carried all the way
into the summary so an unscored frame cannot silently inflate a rate — the same
discipline `p46_chart_measure.py` uses, and the reason P41's 0/12 was wrong.

Every probe is asked TWICE. RAW answers are written to disk.

Usage:
    py -3.12 -I p46_font_measure.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from p46_font_probe import (FONT_CLASS, OUT, ask_font_class,        # noqa: E402
                            control_cards)

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / 'out' / 'p46_probe'
RESULTS = PROBE / 'font_class_census.json'

#: The declared typography of our own renders, from design/tokens.ts. Carried
#: so the summary can say what the GRAPH declares next to what the model reads,
#: rather than leaving a reader to assume they agree.
DECLARED = {
    'FONT_NUM': '"Bahnschrift", "DIN Alternate", "Segoe UI", sans-serif',
    'FONT_SANS': '"Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif',
}


def scored_corpus() -> list[tuple[Path, str]]:
    """Control cards whose font this module chose, so the answer is a fact.

    `mono` is skipped: a SERIF/SANS question has no correct answer for a
    monospaced face, and scoring one against either class would invent a label.

    ⚠️ The first version of this function had its explanatory comment placed
    INSIDE the `if klass == 'mono':` block, which made the two statements below
    reachable only for mono — a class that is `continue`d. The corpus was
    therefore always empty and the summary printed `recall: 0/0`, which reads
    like a result and is not one. It is a vacuous 0/0, and the honest response
    is to notice it rather than quote it.
    """
    out = []
    for stem, klass in FONT_CLASS.items():
        if klass == 'mono':
            continue
        p = OUT / f'control_{stem}.png'
        if p.is_file():
            out.append((p, klass.upper()))
    return out


def unscored_corpus() -> list[tuple[Path, str | None]]:
    """Frames whose true typeface the measurement does not know."""
    items: list[tuple[Path, str | None]] = []
    for f in (200, 770):
        p = PROBE / 'nochart' / f'f{f:05d}.png'
        if p.is_file():
            items.append((p, None))
    for p in sorted((PROBE / 'ours').glob('type_*/f00100.png')):
        items.append((p, None))
    film = PROBE / 'film'
    if film.is_dir():
        for p in sorted(film.glob('film_*.png')):
            items.append((p, None))
    return items


def score_one(path: Path, expected: str | None, times: int = 2,
              **kw) -> dict:
    """Ask one frame `times` times and decide whether it was correct.

    EXTRACTED so the guard can drive the REAL scorer rather than a copy of it.
    ⚠️ MEASURED, and this is the reason it is not inline any more: the first
    version computed `ok` inline in `main`, and the test that claimed to cover
    mutation M5 ("ignore the expected class") re-implemented the comparison
    itself. The mutation rewrote `main`'s `ok` to `len(distinct) == 1` and the
    suite answered **20 passed, exit 0** — a green run on a neutered criterion.

    That is P16's own lesson, from its guard file: *"a calibration that tests a
    copy of the predicate is not a calibration"*. The fix is not a better
    assertion, it is making the predicate reachable.
    """
    raw, secs = [], []
    for _ in range(max(1, times)):
        t0 = time.perf_counter()
        got, why = ask_font_class(path, **kw)
        secs.append(time.perf_counter() - t0)
        raw.append(got if got else f'<{why}>')
    distinct = {r for r in raw if not r.startswith('<')}
    ok = (expected is not None and len(distinct) == 1
          and next(iter(distinct)) == expected)
    return {'path': str(path), 'expected': expected,
            'answers': sorted(distinct), 'raw': raw,
            'seconds': [round(s, 3) for s in secs],
            'correct': ok if expected is not None else None,
            'not_reproducible': len(distinct) > 1}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--times', type=int, default=2)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--out', type=Path, default=RESULTS)
    args = ap.parse_args(argv)

    control_cards()                      # make sure the cards exist on disk
    items = scored_corpus()
    if args.limit:
        items = items[:args.limit]
    if not items:
        # An empty SCORED set is the failure this module's own first run made:
        # every rate below would be computed over nothing and would print as a
        # tidy `0/0`. Refuse rather than report a vacuous measurement.
        raise SystemExit(
            'no scored control cards: every recall/false-positive rate below '
            'would be 0/0, which is indistinguishable from a perfect result. '
            'Render the control cards first (p46_font_probe.py) or fix why '
            'FONT_CLASS produced no non-mono entries.')
    unscored = unscored_corpus()

    rows: list[dict] = []

    def run(path: Path, expected: str | None) -> None:
        row = score_one(path, expected, times=args.times)
        rows.append(row)
        print(f'{path.parent.name}/{path.name:16s} '
              f'expected={str(expected):6s} raw={row["raw"]} '
              f'{row["seconds"][0]:.2f}s'
              + ('  NOT REPRODUCIBLE' if row['not_reproducible'] else ''))

    print('--- SCORED (font known by construction) ---')
    for p, e in items:
        run(p, e)
    print('\n--- REPORTED, NOT SCORED (true typeface unknown to the measurement) ---')
    for p, e in unscored:
        run(p, e)

    s = [r for r in rows if r['expected'] is not None]
    u = [r for r in rows if r['expected'] is None]
    correct = [r for r in s if r['correct']]
    # A false positive is a sans card answered SERIF.
    fp = [r for r in s if r['expected'] == 'SANS' and r['answers'] == ['SERIF']]
    fn = [r for r in s if r['expected'] == 'SERIF' and r['answers'] == ['SANS']]
    total_secs = [x for r in rows for x in r['seconds']]
    summary = {
        'scored': len(s),
        'unscored_no_ground_truth': len(u),
        'correct': len(correct),
        'recall': f'{len(correct)}/{len(s)}',
        'false_positive_serif_on_sans': f'{len(fp)}/{len([r for r in s if r["expected"] == "SANS"])}',
        'missed_serif_answered_sans': f'{len(fn)}/{len([r for r in s if r["expected"] == "SERIF"])}',
        'not_reproducible': [r['path'] for r in rows if r['not_reproducible']],
        'calls': len(total_secs),
        'per_call_seconds_max': round(max(total_secs), 3),
        'per_frame_seconds_median': round(
            sorted(sum(r['seconds']) for r in rows)[len(rows) // 2], 3),
        'declared_project_fonts': DECLARED,
    }
    print(f'\nsummary: {json.dumps(summary, ensure_ascii=False, indent=1)}')

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(json.dumps({'summary': summary, 'rows': rows},
                                    ensure_ascii=False, indent=1).encode('utf-8'))
    print(f'\n-> {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())