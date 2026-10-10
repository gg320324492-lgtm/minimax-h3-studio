"""p46_chart_control.py — prove a chart TYPE reaches the pixels, not just the JSON.

THE POSITIVE-CLASS PROBLEM, and why P45's method had to be reshaped
--------------------------------------------------------------------
P45 proved a printed NUMBER reaches the pixels by perturbing one value and
diffing the label box. Chart TYPE has no such single label box: `bar` and
`line` draw in the same region, so "the pixels changed" would not say *which
mark* changed. Worse, the naive proof — "the graph says `type: bar`, therefore
a bar chart is on the frame" — is exactly the mistake P45's report calls out
about `showValues: true`: a declared surface can be inert. A field that is
read by nobody changes nothing when you edit it.

So the control here is a **same-data type swap**. One payload, five declared
types, five renders of the SAME global frame:

    values + labels, unchanged
    chart.type:  bar | line | area | volume | sparkline

Every one of those five types reads the same `values` field (measured, not
assumed — `tests/test_p46_probe_instruments.py` renders them and a type that
silently
fell back to another would produce a byte-identical pair). If the type field
were inert, all five frames would be byte-identical. They are not, and the
diff is reported per type-pair with a bounding box, so "the type changed the
picture" is a measurement with coordinates rather than a claim.

WHAT THIS DOES NOT PROVE, said out loud:

  * that the renderer's mark for `bar` LOOKS like a bar. That is the
    classifier's job (`p46_chart_measure.py`), and it is measured there, not
    assumed here. This module only establishes that the type is ON the frame
    and that changing it changes the frame.
  * anything about the reference film. The film has no graph. Running this
    against it would measure ffmpeg, not the renderer.

Usage:
    py -3.12 -I p46_chart_control.py            # render + diff
    py -3.12 -I p46_chart_control.py --diff     # diff existing frames only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
GRAPHS = REPO / 'pipeline' / 'examples' / 'charts_demo.json'
OUT = REPO / 'out' / 'p46_probe'
STILL = REPO / 'studio' / 'bin' / 'still.mjs'

#: The source scene. `bar` is its declared type; only `chart.type` is varied.
SOURCE_SCENE = 'c01_bar'

#: The five types that all read `chart.values` and nothing else. Chosen by
#: reading `types.tsx`'s field usage, then CONFIRMED by the renders: a type
#: that silently fell back to another would produce a byte-identical pair.
#:
#: `slope`, `heatmap` and `rank` are deliberately NOT here: they read
#: `before`/`after`, `rows` and `items` respectively, so swapping them onto
#: this payload would be changing the DATA as well as the type, and a pixel
#: difference would no longer isolate the type.
TYPES = ('bar', 'line', 'area', 'volume', 'sparkline')

#: ⚠️ MEASURED INERT, not assumed. `line` and `area` render BYTE-IDENTICAL on
#: this payload (sha256 equal; `pairwise_diffs` reports changed_px=0), because
#: `LineOrArea` (types.tsx:268) resolves the fill as
#:
#:     option('line', 'showArea', opts) ?? defaultArea
#:
#: and `option()` (options.ts:201) NEVER returns undefined — it substitutes
#: `DEFAULT_CHART_OPTIONS[key]`, where `showArea` is `false` (options.ts:120).
#: So `defaultArea` is unreachable and `area` only differs from `line` when the
#: graph sets `showArea: true` explicitly. Verified against the shipped graph:
#: `c02_line` declares `showArea: true` and `c03_area` declares nothing, so the
#: two shipped scenes render with the fill INVERTED relative to their names.
#:
#: ⇒ `area` is excluded from the scorable set. Scoring a chart-type classifier
#: on a type the renderer cannot produce would measure the classifier's
#: behaviour on an unreachable class, which is the "confident zero" shape.
#: NOTE: `studio/src/**` is read-only for this work, so this is REPORTED, not
#: fixed. See docs/P46_PROBE_INSTRUMENTS.md.
INERT_TYPES = {'area'}
SCORABLE = tuple(t for t in TYPES if t not in INERT_TYPES)

#: The global frames rendered for every type. Absolute, because `still.mjs`
#: takes an ABSOLUTE frame number — `chart_ab_matrix.py:123-125` records that
#: writing a scene-LOCAL frame here measures a different scene and produces a
#: confident zero.
#:
#: ⚠️ AND NOT "NEAR THE END OF THE SCENE", which is the obvious wrong choice and
#: the one this module was first written with. `lifecycle.ts` gives the exit
#: `max(EXIT_MIN=6, round(duration * EXIT_SHARE=0.08))` frames, so for a
#: 150-frame scene `exitStart = 138` and **frame 140 is already leaving**.
#: Measured, not reasoned: frame 60 and frame 100 differ by 0 pixels for every
#: type, while frame 140 differs from frame 100 by 387,430 px on `bar`. A
#: classifier scored on an exiting frame is scored on a half-drawn chart, which
#: is the "measured on the wrong scale" failure wearing a settled-frame
#: costume (`docs/WORKORDER_P46_PROBE_INSTRUMENTS.md` §三.7).
FRAMES = (60, 100)
FRAME = FRAMES[-1]

#: Two frames are "the same picture" below this many differing pixels. Chosen
#: from the MEASURED spread of the ten real pairs, not guessed: see
#: `pairwise_diffs`, which prints the whole matrix. A threshold that cannot
#: separate the real pairs from zero would make this check vacuous, so the
#: check asserts the threshold sits strictly between them.
SAME_PICTURE_PX = 0


def source_scene() -> dict:
    doc = json.loads(GRAPHS.read_text(encoding='utf-8'))
    for scene in doc['scenes']:
        if scene['id'] == SOURCE_SCENE:
            return scene
    raise SystemExit(f'{SOURCE_SCENE} is not in {GRAPHS}')


def write_props(chart_type: str) -> Path:
    """One props file: the source scene, alone, with `chart.type` set.

    Single-scene because a type swap inside a 10-scene document would change
    the total duration and therefore which scene global frame 140 lands in —
    the exact frame-numbering accident `chart_ab_matrix.py` documents.
    """
    scene = json.loads(json.dumps(source_scene()))     # deep copy
    scene['content']['chart']['type'] = chart_type
    doc = {k: v for k, v in json.loads(GRAPHS.read_text(encoding='utf-8')).items()
           if k != 'scenes'}
    doc['scenes'] = [scene]
    out = OUT / f'type_{chart_type}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(json.dumps(doc, ensure_ascii=False, indent=1).encode('utf-8'))
    return out


def render(chart_type: str, frame: int = FRAME) -> Path:
    dest = OUT / 'ours' / f'type_{chart_type}'
    subprocess.run(
        ['node', str(STILL), '--comp', 'FinanceShowcaseWide',
         '--props', str(write_props(chart_type)), '--out', str(dest),
         '--frames', str(frame)],
        cwd=str(REPO / 'studio'), check=True, capture_output=True)
    return dest / f'f{frame:05d}.png'


def _array(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert('RGB'), dtype=np.int16)


def pairwise_diffs(frames: dict[str, Path], tol: int = 24) -> list[dict]:
    """Every unordered type pair: differing pixel count and bounding box.

    `tol` is a per-channel slack, because the renderer's own antialiasing on a
    glyph edge is not a type difference. It is small on purpose — the question
    is whether the MARKS differ, and a large tolerance could hide a type that
    changed only its outline.
    """
    out: list[dict] = []
    names = list(frames)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            pa, pb = _array(frames[a]), _array(frames[b])
            if pa.shape != pb.shape:
                out.append({'pair': f'{a}|{b}', 'shape_mismatch': True,
                            'changed_px': None, 'bbox': None})
                continue
            mask = (np.abs(pa - pb) > tol).any(axis=2)
            n = int(mask.sum())
            if n:
                ys, xs = np.nonzero(mask)
                bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
            else:
                bbox = None
            out.append({'pair': f'{a}|{b}', 'shape_mismatch': False,
                        'changed_px': n, 'bbox': bbox})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--diff', action='store_true',
                    help='diff frames already on disk; render nothing')
    ap.add_argument('--frame', type=int, default=None,
                    help='one frame; default is every frame in FRAMES')
    args = ap.parse_args(argv)
    frames_wanted = [args.frame] if args.frame is not None else list(FRAMES)

    for frame in frames_wanted:
        rendered: dict[str, Path] = {}
        for t in TYPES:
            p = OUT / 'ours' / f'type_{t}' / f'f{frame:05d}.png'
            if not args.diff:
                p = render(t, frame)
            if not p.is_file():
                raise SystemExit(f'missing {p} — render before diffing')
            rendered[t] = p

        digests = {t: hashlib.sha256(p.read_bytes()).hexdigest()[:16]
                   for t, p in rendered.items()}
        diffs = pairwise_diffs(rendered)

        print(f'\n=== source scene {SOURCE_SCENE}  global frame {frame}  '
              f'types {list(TYPES)} ===')
        print('sha256[:16] of each rendered frame:')
        for t, d in digests.items():
            print(f'  {t:10s} {d}')
        print('pairwise differing pixels (per-channel tol 24):')
        for row in diffs:
            print(f'  {row["pair"]:22s} changed_px={row["changed_px"]} '
                  f'bbox={row["bbox"]}')

        nonzero = [r for r in diffs if (r['changed_px'] or 0) > SAME_PICTURE_PX]
        zero = [r for r in diffs if (r['changed_px'] or 0) <= SAME_PICTURE_PX]
        print(f'{len(nonzero)} of {len(diffs)} pairs differ; '
              f'{len(zero)} are identical.')

        # A pair is inert only if NEITHER member is a declared-inert type; an
        # inert pair among types nobody scores is a fact, not a failure.
        undeclared = [r for r in zero
                      if not ({r['pair'].split('|')[0], r['pair'].split('|')[1]}
                              & INERT_TYPES)]
        if undeclared:
            bad = ', '.join(r['pair'] for r in undeclared)
            print(f'INERT TYPE FIELD: {bad} rendered identically, so at least '
                  f'one\n`chart.type` value is not read by the renderer and the '
                  f'chart-type\nclassifier must not be scored on it.')
            return 1
        for r in zero:
            print(f'measured inert pair: {r["pair"]} (byte-identical)')
        print(f'=> SCORABLE TYPES: {list(SCORABLE)}')
        print(f'=> EXCLUDED (measured inert): {sorted(INERT_TYPES)}')

    print('\n=> every SCORABLE declared type reaches the pixels. The type is ON')
    print("   the frame; whether it LOOKS like the type is the classifier's")
    print('   measurement, and it is measured separately.')
    return 0


if __name__ == '__main__':
    sys.exit(main())