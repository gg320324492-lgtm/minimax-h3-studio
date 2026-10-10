"""p45_vlm_measure.py — measure how often qwen2.5vl finds a string that IS there.

THE MEASUREMENT, and what makes it a measurement rather than an opinion:

  * the DENOMINATOR is frames whose pixels provably carry the value, not every
    frame rendered. `p45_control_render` proves that per frame by perturbing one
    input value and watching the label pixels change; frames with no label
    difference have no positive class and are excluded, because scoring "the VLM
    missed a number" on a frame that never printed one measures the renderer,
    not the reader. That mistake is exactly what P41 recorded as 0/12.
  * EVERY probe is asked TWICE. The two answers are compared byte for byte, so
    reproducibility is a measured column and not an assumption about a seed.
  * the RAW answer is written to disk for every probe. A verdict with no
    transcript under it is a number nobody can check.
  * ABSENT strings are probed on the same frames. A reader that answers YES to
    everything scores 100% recall and is worthless, so the false-positive rate
    is measured, not assumed away.

Nothing here decides whether the criterion is any good; it produces the numbers
that decide that.

Usage:
    py -3.12 -I p45_vlm_measure.py [--frames 0,20,40,60,96,120] [--limit-scenes ...]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vlm_critic import (DEFAULT_MODEL, ask_vlm, expected_strings,   # noqa: E402
                         parse_verdict, PROBE_QUESTION)

REPO = Path(__file__).resolve().parents[2]
GRAPHS = REPO / 'pipeline' / 'examples' / 'charts_demo.json'
FRAMES = REPO / 'out' / 'p45_vlm' / 'frames'
RESULTS = REPO / 'out' / 'p45_vlm' / 'results.json'

#: The three scenes whose graphs declare `showValues: true`. The other seven
#: declare `false` or omit the field, and `options.ts` defaults it to false, so
#: they print no values and have no positive class to measure against.
SCENES = ['c01_bar', 'c05_bubble', 'c10_bar_long']


def scenes() -> dict[str, dict]:
    doc = json.loads(GRAPHS.read_text(encoding='utf-8'))
    return {s['id']: s for s in doc['scenes'] if s['id'] in SCENES}


#: The y-axis TICK LABELS each frame also carries, read from pixels rather than
#: computed from a mirror of `niceTicks`. This matters because a chart frame does
#: NOT carry only its declared values: `showAxis` defaults to true, so the
#: renderer draws its own tick numbers. First cut of this control set ignored
#: that and used 45x1.01 -> `50` as an "absent" string for c05_bubble; the
#: VLM answered YES, reproducibly, on all three frames — and the pixel bitmap
#: says the frame really does say `50`, in the gutter at x127-144. The reader
#: was right and the control was wrong. Excluding the tick labels is the fix.
#:
#: `50` and `100` are established by reading the bitmap directly (two glyph
#: components at the tick row: a `5` and a `0`). The others follow from the
#: ticks being evenly spaced at 195 / 417 / 640 / 860 px.
TICK_LABELS: dict[str, set[str]] = {
    'c01_bar': {'0', '20', '40', '60'},
    'c05_bubble': {'0', '25', '50', '75', '100'},
    'c10_bar_long': {'0', '20', '40', '60', '80'},
}


def absent_for(scene: dict, k: int = 3) -> list[str]:
    """Strings the frame provably does NOT carry.

    The perturbation has to survive the FORMATTER, not just change a number.
    A first attempt used `v + 1`, which is a no-op for `valueFormat: compact`:
    48200000 + 1 still formats as `48.2M`, so c01_bar produced NO absent
    controls at all and its false-positive rate would have been measured on an
    empty set. So the step is applied in the FORMATTED string's own units.

    Results are checked against the declared values AND against the axis tick
    labels — see `TICK_LABELS` for why the second check is not optional.
    """
    import vlm_critic
    chart = scene['content']['chart']
    fmt = chart.get('valueFormat', 'auto')
    declared = set(expected_strings(scene)) | TICK_LABELS.get(scene['id'], set())
    out: list[str] = []
    for v in chart['values']:
        for factor in (1.1, 0.9, 1.01, 0.99, 1.001, 2.0):
            s = vlm_critic.format_value(v * factor, fmt)
            if s not in declared and s not in out:
                out.append(s)
                break
        if len(out) >= k:
            break
    return out


def ask_with_retry(path: Path, text: str, tries: int = 3
                   ) -> tuple[str | None, str, float, int]:
    """`ask_vlm`, retried on TRANSPORT failure only.

    Measured: 2 of 46 probes failed with `WinError 10055` (WSAENOBUFS, "no
    buffer space available") when requests were fired back to back at a local
    ollama. That is the socket, not the reader: the same probe answered `YES` on
    the retry. Retrying is therefore correct — but the retry COUNT is returned so
    the report can say how often it happened instead of quietly absorbing it.
    A genuine answer, YES or NO, is never retried.
    """
    question = PROBE_QUESTION.format(text=text)
    last = ''
    for attempt in range(tries):
        t0 = time.perf_counter()
        answer, why = ask_vlm(path, question, model=DEFAULT_MODEL)
        dt = time.perf_counter() - t0
        if not why:
            return answer, '', dt, attempt
        last = why
        time.sleep(0.4 * (attempt + 1))
    return None, last, dt, tries - 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--frames', default='0,20,40,60,96,120')
    ap.add_argument('--absent-k', type=int, default=3)
    ap.add_argument('--absent-frames', default='60,96,120')
    ap.add_argument('--out', type=Path, default=RESULTS)
    ap.add_argument('--only-kind', choices=['present', 'absent'],
                    help='measure one half only; the absent controls were '
                         're-run after the first set was found to contain an '
                         'axis tick label')
    args = ap.parse_args(argv)

    frames = [int(x) for x in args.frames.split(',') if x.strip()]
    absent_frames = {int(x) for x in args.absent_frames.split(',') if x.strip()}
    all_scenes = scenes()

    rows: list[dict] = []
    t_start = time.time()
    calls = 0
    retries_total = 0

    for scene_id in SCENES:
        scene = all_scenes[scene_id]
        want = expected_strings(scene)
        negatives = absent_for(scene, args.absent_k)
        for frame in frames:
            path = FRAMES / scene_id / f'f{frame:05d}.png'
            if not path.exists():
                raise SystemExit(f'missing frame {path} — render before measuring')
            targets = [(t, True) for t in want]
            if args.only_kind == 'absent':
                targets = []
            elif args.only_kind == 'present':
                pass
            if frame in absent_frames and args.only_kind != 'present':
                targets += [(t, False) for t in negatives]
            for text, should_be_there in targets:
                rec = {'scene': scene_id, 'frame': frame, 'text': text,
                       'kind': 'present' if should_be_there else 'absent',
                       'raw': [], 'verdicts': [], 'seconds': []}
                # Asked twice with the identical request. Both raw answers are
                # kept: the first is what the verdict is parsed from, the second
                # is the reproducibility check, and `raw` is the transcript a
                # reader can check the parse against.
                for _ in range(2):
                    answer, why, dt, retries = ask_with_retry(path, text)
                    rec['seconds'].append(dt)
                    calls += 1
                    rec['raw'].append(answer)
                    retries_total += retries
                    if why:
                        rec.setdefault('errors', []).append(why)
                    rec['verdicts'].append(
                        None if why else parse_verdict(answer or ''))
                rows.append(rec)
                print(f'{scene_id:12s} f{frame:03d} {rec["kind"]:7s} '
                      f'{text:8s} raw={rec["raw"]} '
                      f'verdicts={rec["verdicts"]} {rec["seconds"][0]:.2f}s',
                      flush=True)

    payload = {
        'model': DEFAULT_MODEL,
        'scenes': SCENES,
        'frames': frames,
        'absent_frames': sorted(absent_frames),
        'calls': calls,
        'transport_retries': retries_total,
        'wall_seconds': time.time() - t_start,
        'rows': rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(json.dumps(payload, indent=1).encode('utf-8'))
    print(f'\n{calls} calls in {payload["wall_seconds"]:.1f}s -> {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())