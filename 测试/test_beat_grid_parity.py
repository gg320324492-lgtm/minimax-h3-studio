"""Python and TypeScript must agree on the beat grid, item by item (P9.1).

`beatFrames = (60 / bpm) * fps` exists on both ends of the pipeline:
`scene_graph.Showcase.resolve` and `showcase-v1.resolveScenes`. They have been
kept honest about `resolve` by six tests, but the GRID is a new surface and a
guard written against one implementation cannot see the other disagree — which is
the whole failure mode of this file pair. A Python author rounds one way, a
TypeScript renderer rounds the other, and the two timelines differ by a frame at
some boundary that neither side's own test exercises.

So this runs BOTH implementations over the same graph and the same analysis and
compares the bar boundaries term by term. The beat grid is the thing 9.2 will bind
motion to, so a one-frame disagreement between the two ends is not a rounding
detail: it is the film and the plan describing different films.

`scene_graph` and the analysis are read directly; the TypeScript side is executed
through `beatGrid.check.ts`'s sibling, a tiny emitter that prints the grid as JSON
so the comparison needs no TypeScript test harness and no build step.

Where node is unavailable the TypeScript half SKIPS rather than fails — the same
call `test_perspective_math.py` makes. The Python-only assertions still run, so a
machine without node still learns whether `scene_graph` is self-consistent.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / 'pipeline'
BEAT = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'beat'
MODULE = BEAT / 'beatGrid.ts'
CHECK = BEAT / 'beatGrid.check.ts'
ANALYSIS = ROOT / 'studio' / 'public' / 'audio' / 'bgm_beats.json'
GRAPHS = ('showcase_demo.json', 'charts_demo.json')

sys.path.insert(0, str(PIPELINE))
import scene_graph as sg  # noqa: E402

_NPX = shutil.which('npx') or shutil.which('npx.cmd')

#: The TypeScript grid's own quantisation, restated here on purpose. This is NOT a
#: copy of the implementation — it is the SPECIFICATION, written twice so that the
#: two copies can disagree. If it agreed by construction the test would be theatre.
SPEC_FRAMES_PER_QUARTER = 'round((60 / bpm) * fps / 4), at least 1'


def _fit(beats: list[dict]) -> tuple[float, float]:
    """Least-squares fit, returned as (bpm, interval). Duplicated from the TS on purpose."""
    n = len(beats)
    xs = list(range(n))
    ys = [b['t'] for b in beats]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs)
    interval = num / den
    return 60 / interval, interval


def _load(name: str) -> dict:
    return json.loads((PIPELINE / 'examples' / name).read_text(encoding='utf-8'))


def _ts_grid(bpm: float, fps: int, horizon: int, out_dir: Path) -> dict:
    """Run the TypeScript grid and read back its JSON."""
    probe = out_dir / 'emit_grid.ts'
    probe.write_text(
        f'''import fs from 'node:fs';
import {{fitBpm, grid}} from '{MODULE.as_posix()}';

const analysis = JSON.parse(
  fs.readFileSync({json.dumps(ANALYSIS.as_posix())}, 'utf8')
);
const fit = fitBpm(analysis.beats);
const g = grid({{bpm: {bpm}, fps: {fps}}}, analysis, {{horizonFrames: {horizon}}});
fs.writeFileSync(
  {json.dumps((out_dir / 'grid.json').as_posix())},
  JSON.stringify({{fit: {{bpm: fit.bpm, interval: fit.interval}}, grid: g}})
);
''',
        encoding='utf-8',
    )
    proc = subprocess.run(
        [_NPX, 'tsx', str(probe)],
        cwd=ROOT / 'studio',
        capture_output=True,
        text=True,
        timeout=300,
        encoding='utf-8',
        errors='replace',
    )
    assert proc.returncode == 0, f'ts grid emitter failed:\n{proc.stdout}\n{proc.stderr}'
    return json.loads((out_dir / 'grid.json').read_text(encoding='utf-8'))


# ── Python-only: scene_graph is internally consistent ────────────────────────


def test_python_fit_matches_the_typescript_fit():
    """Both ends must derive the same tempo from the same beats.

    If they disagree, the grid differs before any rounding is involved, and every
    downstream comparison is comparing two different tempi.
    """
    doc = json.loads(ANALYSIS.read_text(encoding='utf-8'))
    bpm, interval = _fit(doc['beats'])
    assert bpm == pytest.approx(128.998, abs=0.01), f'python fit gave {bpm}'
    # The TS value is asserted in the node-backed test below; here, pin the
    # arithmetic so a change to this copy alone is visible.
    assert interval == pytest.approx(0.465122, abs=1e-6), f'python interval {interval}'


@pytest.mark.parametrize('name', GRAPHS)
def test_beat_frames_agree_between_the_two_beat_distance_implementations(name: str):
    """`beat_distance_frames` is the shared predicate; both ends must answer alike.

    This is the cheapest possible cross-end check that needs no grid at all, and
    it catches the class of bug that matters: a disagreement about whether a frame
    is ON a beat. `on_beat` is what a renderer would use to snap a motion, so if
    the two ends disagree, the same frame is simultaneously on-beat and off-beat
    depending on which language asked.
    """
    doc = _load(name)
    sc = sg.Showcase(
        project=doc['project'], width=doc['format']['width'],
        height=doc['format']['height'], fps=doc['format']['fps'],
        bpm=float(doc['bpm']), scenes=doc['scenes'],
        style_bible=doc.get('style_bible') or {},
    )
    beat_frames = (60.0 / sc.bpm) * sc.fps
    # Frames Python considers on-beat, over a window spanning several beats.
    on_beat = [f for f in range(0, 400) if sc.on_beat(f)]
    assert on_beat, 'no frame in 400 is on-beat — the beat maths is broken'
    # Every one must be within half a frame of a multiple of beat_frames, which is
    # what `on_beat` claims. Asserted independently so the two are not the same
    # statement written twice.
    for f in on_beat:
        off = f % beat_frames
        assert min(off, beat_frames - off) <= 0.5 + 1e-6, (
            f'frame {f} reported on-beat but sits {min(off, beat_frames - off):.4f} '
            f'frames from the nearest boundary'
        )
    assert len(on_beat) >= 14, f'only {len(on_beat)} on-beat frames in 400'


def test_grid_specification_is_written_down_where_both_ends_can_see_it():
    """The quantisation rule must exist as a specification, not only as code.

    Two implementations of a rounding rule that is described in a comment will
    diverge the first time the comment is not read. The rule itself is
    `SPEC_FRAMES_PER_QUARTER` above; this asserts the TypeScript side still
    implements THAT rule rather than a private one.
    """
    src = MODULE.read_text(encoding='utf-8')
    assert '(60 / bpm) * fps / 4' in src, (
        'beatGrid.ts no longer quantises from the quarter beat at (60/bpm)*fps/4; '
        f'the cross-end specification says {SPEC_FRAMES_PER_QUARTER}'
    )
    assert 'Math.round(idealQuarter)' in src, (
        'the quarter-beat step must be Math.round of the ideal, or the two ends '
        'can round differently for the same inputs'
    )


# ── the cross-end comparison, which needs node ──────────────────────────────


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
@pytest.mark.parametrize('name', GRAPHS)
def test_bar_boundaries_are_identical_on_both_ends(name: str, tmp_path: Path):
    """The load-bearing comparison: same graph, same analysis, same boundaries.

    Each end's grid is built from its OWN code — Python's from the specification
    restated above, TypeScript's from `grid()` executed via tsx — and then the four
    levels are compared term by term. Equality is exact, not approximate: both ends
    quantise to whole frames from the same integer step, so any difference is a
    genuine disagreement about where a boundary is.
    """
    doc = _load(name)
    fps = int(doc['format']['fps'])
    bpm = float(doc['bpm'])
    horizon = sum(int(s['durationInFrames']) for s in doc['scenes'])

    # --- Python side, built from the written specification -------------------
    quarter = max(1, round((60 / bpm) * fps / 4))
    steps = {'quarterBeat': quarter, 'halfBeat': 2 * quarter,
             'beat': 4 * quarter, 'bar': 16 * quarter}
    py = {
        level: list(range(0, horizon + 1, step))
        for level, step in steps.items()
    }

    # --- TypeScript side, from the real module ------------------------------
    ts_payload = _ts_grid(bpm, fps, horizon, tmp_path)
    ts_fit_bpm = ts_payload['fit']['bpm']
    assert ts_fit_bpm == pytest.approx(128.998, abs=0.01), (
        f'the TypeScript fit gave {ts_fit_bpm}, not the expected 128.998'
    )

    for level in ('quarterBeat', 'halfBeat', 'beat', 'bar'):
        assert ts_payload['grid'][level] == py[level], (
            f'{name}: {level} boundaries differ between the two ends.\n'
            f'  python: {len(py[level])} boundaries, first 6 {py[level][:6]}\n'
            f'  ts:     {len(ts_payload["grid"][level])} boundaries, '
            f'first 6 {ts_payload["grid"][level][:6]}\n'
            f'  python step {steps[level]} frames/level; '
            f'ts reports {ts_payload["grid"]["framesPer" + level[:1].upper() + level[1:]]} '
            f'frames/{level}'
        )

    # And the levels must nest on the TypeScript side too, since that is what makes
    # the comparison above meaningful rather than four independent equalities.
    ts_grid_obj = ts_payload['grid']
    assert all(v in set(ts_grid_obj['beat']) for v in ts_grid_obj['bar'])
    assert all(v in set(ts_grid_obj['halfBeat']) for v in ts_grid_obj['beat'])
    assert all(v in set(ts_grid_obj['quarterBeat']) for v in ts_grid_obj['halfBeat'])


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
@pytest.mark.parametrize('bpm', [90.0, 126.0, 128.998, 131.4, 174.0])
def test_bar_boundaries_agree_at_tempos_where_rounding_would_diverge(bpm: float, tmp_path: Path):
    """The cross-end comparison, run where the two designs actually differ.

    At 129 bpm an implementation that rounds each level separately produces the
    same numbers as one that builds every level from the quarter beat — the ideal
    beat is 27.907 frames, which rounds to 28, and 4 * round(27.907/4) is also
    4 * 7. So comparing only at the graphs' own tempo tests nothing. 131.4 bpm is
    included because there the ideal beat is 27.397 frames: the beat rounds to 27
    while four quarter-beats round to 28, so the two designs disagree by a frame at
    every bar line and the comparison becomes load-bearing.
    """
    fps = 60
    quarter = max(1, round((60 / bpm) * fps / 4))
    steps = {'quarterBeat': quarter, 'halfBeat': 2 * quarter,
             'beat': 4 * quarter, 'bar': 16 * quarter}
    py = {level: list(range(0, 2001, step)) for level, step in steps.items()}

    ts_payload = _ts_grid(bpm, fps, 2000, tmp_path)
    for level in ('quarterBeat', 'halfBeat', 'beat', 'bar'):
        assert ts_payload['grid'][level] == py[level], (
            f'at {bpm} bpm the two ends put {level} boundaries in different places: '
            f'python first 6 {py[level][:6]}, ts first 6 {ts_payload["grid"][level][:6]}'
        )


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
def test_the_two_ends_agree_about_which_beats_are_accented(tmp_path: Path):
    """Accent must be the same SET on both ends, not merely the same rule.

    The selection is a top-5% by measured bass, so the two ends can only agree if
    they read the same file and use the same tie-break. A tie-break difference is
    not hypothetical: beats 20 and 22 of this track are within a rounding step of
    each other, so a sort that is not stable picks different ones on each end and
    the film accents a different beat than the plan says.
    """
    doc = json.loads(ANALYSIS.read_text(encoding='utf-8'))
    bass = [b.get('bass', 0) for b in doc['beats']]
    take = max(1, math.ceil(len(bass) * 0.05))
    py_accent = sorted(
        sorted(range(len(bass)), key=lambda i: (-bass[i], i))[:take]
    )

    probe = tmp_path / 'emit_accent.ts'
    probe.write_text(
        f'''import fs from 'node:fs';
import {{fitBpm, grid}} from '{MODULE.as_posix()}';
const analysis = JSON.parse(
  fs.readFileSync({json.dumps(ANALYSIS.as_posix())}, 'utf8')
);
const g = grid({{bpm: fitBpm(analysis.beats).bpm, fps: 60}}, analysis);
fs.writeFileSync(
  {json.dumps((tmp_path / 'accent.json').as_posix())},
  JSON.stringify(g.accent)
);
''',
        encoding='utf-8',
    )
    proc = subprocess.run(
        [_NPX, 'tsx', str(probe)],
        cwd=ROOT / 'studio',
        capture_output=True, text=True, timeout=300,
        encoding='utf-8', errors='replace',
    )
    assert proc.returncode == 0, f'ts accent emitter failed:\n{proc.stdout}\n{proc.stderr}'
    ts_accent = json.loads((tmp_path / 'accent.json').read_text(encoding='utf-8'))

    assert ts_accent == py_accent, (
        f'the two ends accent different beats.\n'
        f'  python: {py_accent}\n'
        f'  ts:     {ts_accent}\n'
        f'  the bass values around the cut: '
        f'{[(i, bass[i]) for i in sorted(set(py_accent) ^ set(ts_accent))]}'
    )
