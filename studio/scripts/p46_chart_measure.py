"""p46_chart_measure.py — measure the chart-type classifier against ground truth.

WHAT IS MEASURED, AND WHY THE CORPUS IS BUILT THE WAY IT IS
-----------------------------------------------------------
Three buckets, because this project's own renders do not honour the naive
assumption that "the scene declares no `chart` field, therefore the frame has
no chart". They do not, and the counter-examples were found by LOOKING at the
renders before scoring anything — the P45 lesson, where a "negative" turned
out to carry the very thing the probe was asking about:

  * `s02_dash` (browser-stack) declares no `chart`, and its frame carries a
    miniature BAR chart in one window and a miniature LINE chart in another.
  * `s03_columns` (dashboard) declares no `chart`, and its frame is a row of
    vertical columns — a bar chart by any reading of option A.

Scoring either as "there is no chart here" would have recorded the classifier
as wrong when it was right, and manufactured a false-positive rate out of a
broken control. So:

  POSITIVE   frames rendered from a declared type; the control render proves
             the type reaches the pixels, so the expected letter is derived
             from the input rather than from a look at the picture.
  NEGATIVE   frames verified to carry no chart. Two are our own renders,
             checked one at a time; two are synthetic flats built from ffmpeg's
             own `color` source, which are chart-free by construction.
  CONTESTED  frames that declare no chart and visibly contain one. Expected is
             None on purpose: they are reported, never scored, and counting
             them either way would be inventing ground truth.

Every probe is asked TWICE and the two answers compared. The RAW answers go to
disk, because a number with no transcript under it is a number nobody can check.

Usage:
    py -3.12 -I p46_chart_measure.py
    py -3.12 -I p46_chart_measure.py --limit 6
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from p46_chart_control import FRAMES, TYPES, scorable_types          # noqa: E402
from p46_chart_probe import (NONE_LETTER, OPTION_LETTERS,             # noqa: E402
                             build_question, census, score)

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / 'out' / 'p46_probe'
RESULTS = OUT / 'chart_census.json'

#: declared chart type -> the letter `p46_chart_probe` describes it with.
#: Read off `OPTIONS`, not typed twice: a second copy of the mapping is a
#: second thing to drift.
TYPE_TO_LETTER = {'bar': 'A', 'line': 'B', 'volume': 'C', 'sparkline': 'D'}

#: Our own renders, one per non-chart scene type, each LOOKED AT first. The
#: scenes that declare no `chart` AND contain none are named individually
#: because two of the four do not qualify — see the module docstring.
NEGATIVE_RENDERS = {
    's01_kpi': 200,        # one KPI figure, a delta pill and a rule
    's04_calendar': 770,   # a month grid of unlabelled date cells
}
#: Declares no chart, visibly contains one. Reported, never scored.
CONTESTED_RENDERS = {
    's02_dash': 430,       # a miniature bar chart and a miniature line chart
    's03_columns': 545,    # a row of vertical columns
}

FLAT_SIZE = '1920x1080'


def synth_flats(n: int = 2) -> list[Path]:
    """Chart-free frames by construction: a flat fill from ffmpeg's `color`.

    Built rather than committed because `.gitignore` carries `*.mp4` and this
    project does not track media — the same reasoning P37's guard gives for
    building its fixtures with lavfi instead of committing one.
    """
    d = OUT / 'flat'
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for i, colour in enumerate(('0x141418', '0x1C1C22')):
        p = d / f'flat{i}.png'
        subprocess.run(
            ['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi',
             '-i', f'color=c={colour}:s={FLAT_SIZE}:d=1', '-frames:v', '1',
             str(p)], check=True, capture_output=True, timeout=120)
        out.append(p)
    return out[:n]


def corpus() -> tuple[list[tuple[Path, str | None]], list[tuple[Path, str | None]]]:
    """(scored items, unscored items). Scored = has ground truth."""
    scored: list[tuple[Path, str | None]] = []
    unscored: list[tuple[Path, str | None]] = []

    # The scorable set is MEASURED from these frames, not imported from a
    # table. It was `SCORABLE`, a tuple literal, which meant a type could
    # become indistinguishable in the renderer while the list of types you were
    # scoring it on stayed exactly as it was — the shape of the whole P46 line
    # is "does the declared field reach the frame", so a scorer built on a
    # frozen answer is the one place that question cannot be asked.
    by_type: dict[str, list[Path]] = {}
    for t in TYPES:
        for f in FRAMES:
            p = OUT / 'ours' / f'type_{t}' / f'f{f:05d}.png'
            if not p.is_file():
                raise SystemExit(f'missing {p} — run p46_chart_control.py first')
            by_type.setdefault(t, []).append(p)
    scorable = scorable_types(by_type)
    unscored_types = [t for t in TYPES if t not in scorable]
    if unscored_types:
        # Scored anyway: the frames exist and the type is a real declared type,
        # so a miss on it is a real miss. Reported, because a type that renders
        # identically to another has nothing in the frame for the classifier to
        # answer from, and a low score there measures the question.
        print(f'NOTE: {unscored_types} render identically to another type and '
              f'have no\n      distinguishing information in the frame; they are '
              f'scored but the\n      result cannot separate "the classifier '
              f'missed" from "the frame could\n      not say".')
    for t in scorable:
        for p in by_type[t]:
            scored.append((p, TYPE_TO_LETTER[t]))

    for _name, f in NEGATIVE_RENDERS.items():
        p = OUT / 'nochart' / f'f{f:05d}.png'
        if not p.is_file():
            raise SystemExit(f'missing {p} — render showcase_demo.json first')
        scored.append((p, NONE_LETTER))
    for p in synth_flats():
        scored.append((p, NONE_LETTER))

    for _name, f in CONTESTED_RENDERS.items():
        p = OUT / 'nochart' / f'f{f:05d}.png'
        if p.is_file():
            unscored.append((p, None))
    return scored, unscored


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--limit', type=int, default=0,
                    help='cap the scored corpus (smoke test); 0 = all')
    ap.add_argument('--times', type=int, default=2)
    ap.add_argument('--out', type=Path, default=RESULTS)
    args = ap.parse_args(argv)

    scored, unscored = corpus()
    if args.limit:
        scored = scored[:args.limit]
    if not scored:
        raise SystemExit('empty corpus: an empty probe set is not a measurement')

    print(build_question())
    print()
    t0 = time.time()
    verdicts = census(scored, times=args.times) + census(unscored, times=args.times)
    wall = time.time() - t0

    for v in verdicts:
        tag = f'expected={v.expected}' if v.expected else 'expected=<none>'
        print(f'{Path(v.path).parent.name}/{Path(v.path).name:12s} '
              f'{tag:16s} raw={v.raw} letter={v.letter} '
              f'{v.seconds[0]:.2f}s' + (f'  [{v.reason}]' if v.reason else ''))

    # Per-frame cost by SUMMING the calls actually made on that frame. Not
    # `median_call * n_frames` — P41 was pulled up for exactly that.
    per_frame = [{'frame': v.path, 'calls': len(v.seconds),
                  'seconds': round(sum(v.seconds), 3)} for v in verdicts]
    summary = score(verdicts)
    summary['wall_seconds'] = round(wall, 2)
    summary['calls'] = sum(pf['calls'] for pf in per_frame)
    summary['per_frame_seconds_max'] = max(pf['seconds'] for pf in per_frame)
    summary['per_frame_seconds_median'] = sorted(
        pf['seconds'] for pf in per_frame)[len(per_frame) // 2]

    print(f'\nsummary: {json.dumps(summary, ensure_ascii=False)}')
    contested = [v for v in verdicts if v.expected is None]
    if contested:
        print('\nCONTESTED (declares no chart, visibly contains one) — REPORTED, '
              'NOT SCORED:')
        for v in contested:
            print(f'  {Path(v.path).name}: answered {v.letter}')

    payload = {'question': build_question(),
               'option_letters': list(OPTION_LETTERS),
               'summary': summary,
               'per_frame': per_frame,
               'verdicts': [{'path': v.path, 'expected': v.expected,
                             'letter': v.letter, 'raw': v.raw,
                             'seconds': [round(s, 3) for s in v.seconds],
                             'reason': v.reason} for v in verdicts]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(json.dumps(payload, ensure_ascii=False, indent=1)
                         .encode('utf-8'))
    print(f'\n-> {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())