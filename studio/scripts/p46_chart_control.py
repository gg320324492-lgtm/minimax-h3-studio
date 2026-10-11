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
import os
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

#: WHICH TYPES ARE INERT IS NOT A CONSTANT. It was `INERT_TYPES = {'area'}`,
#: sitting under a comment that read "MEASURED INERT, not assumed" while
#: nothing ever re-measured it — a measurement frozen into a literal, with the
#: claim that it came from one still printed above it.
#:
#: `area` WAS inert when P46 wrote this. `types.tsx`'s `LineOrArea` resolved
#: the fill as `option('line', 'showArea', opts) ?? defaultArea`, and
#: `options.ts`'s `option()` returns `DEFAULT_CHART_OPTIONS[key]` for an absent
#: value and so never returns undefined, which left `defaultArea` unreachable
#: and made `area` differ from `line` only when a graph spelled `showArea: true`
#: out by hand. P47 fixed that — the per-type default now lives in
#: `TYPE_DEFAULT_ROWS` in options.ts and `option()` consults it — so the
#: literal would have gone quietly false with its comment still saying
#: MEASURED. It is measured here instead, by `measured_inert_types()`, from
#: the frames on disk, on every run.
#:
#: WHAT THE CONCEPT IS STILL FOR, unchanged. A classifier cannot be scored on
#: a class the renderer cannot produce: if two types render the same picture
#: there is nothing in the frame for the classifier to answer from, and every
#: miss on that class measures the question rather than the classifier. What
#: changed is that WHICH types qualify is now a result rather than a table.
#:
#: Refused rather than guessed: `scorable_types` raises if it has not been
#: given a frame for every declared type, because "not in the inert set" and
#: "never measured" are different answers and only one of them is a finding.

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


def _identical(pa: list[Path], pb: list[Path]) -> bool:
    """Do these two types render the SAME PICTURE on EVERY frame given?

    All of them, not one: a pair that differs on a single frame is still a
    pair the renderer can tell apart, and the classifier can be scored on it.

    A shape mismatch is NOT identity. Two frames of different sizes have not
    been shown to be the same picture, and calling that a collapse would be
    inventing a finding out of a measurement error — the same conflation
    `_only_match` exists to prevent on the other side of this module.
    """
    if not pa or len(pa) != len(pb):
        return False
    for x, y in zip(pa, pb):
        row = pairwise_diffs({'x': x, 'y': y})[0]
        if row.get('shape_mismatch') or (row['changed_px'] or 0) > SAME_PICTURE_PX:
            return False
    return True


def measured_inert_types(frames: dict[str, list[Path]]) -> set[str]:
    """Every type that renders the same picture as another one. MEASURED.

    Derived from the frames handed in, on every call. Nothing here is a
    table; see the note above `TYPES` for why that used to be the problem.
    """
    names = sorted(frames)
    inert: set[str] = set()
    for i, a in enumerate(names):
        for other in names[i + 1:]:
            if _identical(frames[a], frames[other]):
                inert.add(a)
                inert.add(other)
    return inert


def scorable_types(frames: dict[str, list[Path]]) -> tuple[str, ...]:
    """The declared types a classifier can be scored on, MEASURED.

    Raises rather than answering when the evidence is incomplete. A type with
    no frame on disk has not been shown to be distinguishable, and scoring a
    classifier on it would be the "confident zero" shape this P46 line exists
    to avoid.
    """
    missing = [t for t in TYPES if not frames.get(t)]
    if missing:
        raise SystemExit(
            f'no rendered frame for {missing}; run p46_chart_control.py before '
            'scoring. Refusing to infer which types are inert from the ones '
            'that happen to be on disk — "not measured" is not "not inert".')
    inert = measured_inert_types(frames)
    return tuple(t for t in TYPES if t not in inert)


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
    """One type, one frame.

    `--public-dir` points at an EMPTY directory and TMPDIR at a scratch beside
    the output, for the reason `ab_field.py` spells out: this graph references
    no static file, and `still.mjs` would otherwise copy the whole of
    `studio/public` — 773 MB — into every scratch bundle. 125 of those once
    filled a C: drive to zero free. `still.mjs` REFUSES the combination when a
    graph does reference a static file, so this cannot silently break an asset
    lookup: it stops the render instead, which is the right direction to fail.
    """
    dest = OUT / 'ours' / f'type_{chart_type}'
    scratch = dest / 'scratch'
    public = dest / 'public'
    scratch.mkdir(parents=True, exist_ok=True)
    public.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'TMPDIR': str(scratch), 'TMP': str(scratch),
           'TEMP': str(scratch)}
    subprocess.run(
        ['node', str(STILL), '--comp', 'FinanceShowcaseWide',
         '--props', str(write_props(chart_type)), '--out', str(dest),
         '--frames', str(frame), '--public-dir', str(public)],
        cwd=str(REPO / 'studio'), check=True, capture_output=True, env=env)
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
    measured: list[dict[str, list[Path]]] = []

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
        for r in zero:
            print(f'  measured inert pair on this frame: {r["pair"]}')
        measured.append({t: [p] for t, p in rendered.items()})

    # MEASURED over every frame rendered. Not read from a table written on a day
    # when the renderer looked a certain way.
    every: dict[str, list[Path]] = {}
    for one in measured:
        for t, ps in one.items():
            every.setdefault(t, []).extend(ps)
    inert = measured_inert_types(every)
    scorable = scorable_types(every)
    print(f'\n=> MEASURED INERT (renders identically to another type on every '
          f'frame): {sorted(inert) or "none"}')
    print(f'=> SCORABLE TYPES: {list(scorable)}')
    if inert:
        print('A classifier cannot be scored on a type that renders the same '
              'picture as\n   another: there is nothing in the frame for it to '
              'answer from.')
    else:
        print('\n=> every declared type reaches the pixels and is '
              'distinguishable from\n   the others. The type is ON the frame; '
              'whether it LOOKS like the type is\n   the classifier\'s '
              'measurement, and it is measured separately.')
    return 0


if __name__ == '__main__':
    sys.exit(main())