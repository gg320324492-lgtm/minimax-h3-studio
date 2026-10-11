"""P48's re-acceptance, pinned so it can be re-run rather than re-read.

P48 was NOT "render it again". It was: take the instruments P27 did not have
and re-examine an artefact P27 signed off — an artefact PROVEN to slip past
P27's method (P47: `area`/`line` rendered with their appearances swapped, and
every numeric guard was green because a bare line IS content).

So this file does the two things that pass demands, and nothing else:

  1. IT PINS WHAT THE INSTRUMENTS ACTUALLY MEASURE. The recurring defect in
     this repository is a rule whose NAME says one thing and whose CODE does
     another (`font_size`, below). That is a property READ OFF the running code,
     not asserted about a source string.

     (P48 ALSO MEASURED a meta-guard that recognised one spelling of a
     tautology and walked past the other — `assert x or True`, below — and
     pinned the hole. P50 closed it: see §4, where the pin was removed as its
     own failure message ordered.)

  2. IT PINS THE TWO DEFECTS P48 FOUND, AS MEASUREMENTS. A guard that asserted
     "the renderer must not freeze" would be RED on the day it landed, and this
     project has met that shape before: P27 recorded B-2 / B-3 and queued them
     for adjudication rather than shipping a red gate. So these assert the state
     as MEASURED, with a message that tells the next reader to re-derive rather
     than to trust the number — the same contract `test_c10_is_150_frames` in
     `test_p42_fade_is_not_a_freeze.py` uses.

WHAT IS DELIBERATELY NOT HERE. No assertion that a NAME appears in a source
file. This repository has been fooled by that shape eleven times, and a guard
that grepped for `emphasisIndex` or `showArea` would have been perfectly green
on the very defects P47 and P48 were written for. Every claim below is reached
by RUNNING a function or reading a rendered pixel.

Run:
    python -m pytest tests/test_p48_reaccept.py -q

The render half needs node and the studio tree; it SKIPS (and says what it did
not check) when they are absent, and FAILS rather than skipping when a render it
did start comes back wrong — a guard that steps aside when its instrument breaks
is the vacuous pass this file argues against.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'studio' / 'scripts'
GRAPHS = ROOT / 'pipeline' / 'examples' / 'charts_demo.json'
STILL = ROOT / 'studio' / 'bin' / 'still.mjs'
STUDIO = ROOT / 'studio'

sys.path.insert(0, str(SCRIPTS))
import visual_qa as vqa  # noqa: E402

_NODE = shutil.which('node')


def _frame_equality(a: Path, b: Path) -> int:
    """Pixels that differ between two frames, by EXACT value (P48's instrument).

    `rule_freeze` measures a pair of frames it is HANDED; this is the same
    measurement, reached without the rule, so a change to the rule cannot make
    this agree with itself.
    """
    ia = np.asarray(Image.open(a).convert('RGB')).astype(np.int16)
    ib = np.asarray(Image.open(b).convert('RGB')).astype(np.int16)
    if ia.shape != ib.shape:
        return -1
    return int((np.abs(ia - ib) > 0).sum())


# ── 1. the freeze: a scene holds a byte-identical still for over half its run ─

pytestmark_render = pytest.mark.skipif(
    _NODE is None or not STILL.is_file(),
    reason='node/studio tree absent; the render-backed P48 checks did NOT run',
)


def _render_scene(scratch: Path, scene_id: str, frames: list[int],
                  chart_mutate=None) -> dict[int, Path]:
    """Render one scene of charts_demo standalone, at scene-local frames.

    Single-scene because `still.mjs` takes GLOBAL frame numbers: rendering
    scene 5 at "frame 70" of the full film renders a different scene (the
    confident-zero shape `p46_chart_control.py` documents). A one-scene props
    file makes the frame number the scene-local frame and nothing can drift.
    """
    doc = json.loads(GRAPHS.read_text(encoding='utf-8'))
    scene = next(s for s in doc['scenes'] if s['id'] == scene_id)
    if chart_mutate is not None:
        chart_mutate(scene['content']['chart'])
    out = {k: v for k, v in doc.items() if k != 'scenes'}
    out['scenes'] = [scene]
    scratch.mkdir(parents=True, exist_ok=True)
    props = scratch / f'{scene_id}.json'
    props.write_bytes(json.dumps(out, ensure_ascii=False).encode('utf-8'))
    dest = scratch / 'png'
    dest.mkdir(exist_ok=True)
    public = scratch / 'public'
    public.mkdir(exist_ok=True)
    env = {**__import__('os').environ, 'TMPDIR': str(scratch), 'TMP': str(scratch),
           'TEMP': str(scratch), 'REMOTION_SCRATCH_DIR': str(scratch)}
    proc = subprocess.run(
        [_NODE, str(STILL), '--comp', 'FinanceShowcaseWide', '--props', str(props),
         '--out', str(dest), '--frames', ','.join(str(f) for f in frames),
         '--public-dir', str(public)],
        cwd=str(STUDIO), capture_output=True, text=True, timeout=1800,
        encoding='utf-8', errors='replace', env=env)
    if proc.returncode != 0:
        raise AssertionError(
            f'still failed for {scene_id}:\n{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}')
    return {f: dest / f'f{f:05d}.png' for f in frames}


@pytestmark_render
def test_a_settled_scene_is_frozen_between_adjacent_frames(tmp_path):
    """P48's headline measurement, on a REAL lossless render.

    MEASURED (this test): frames 70 and 71 of `c01_bar`, rendered losslessly,
    are byte-identical -- 0 differing pixels. Nine of the ten scenes hold such
    a still; `c06_heatmap`'s entrance runs longer so it freezes a little later
    (frame 100 onward). About 1.35 s of each 2.5 s scene is one frozen picture.

    THE STATE THIS PINS, not a wish. `freeze` is a REAL rule (it is not in
    `visual_qa.UNIMPLEMENTED`), and its criterion `changed == 0` is exactly
    what distinguishes this still. What made the still invisible to P27 is the
    INPUT: P27 measured the 226 kbps film, where a "frozen" pair still differs
    by 281-2329 px of codec jitter, so `freeze` reported PASS on all 30 pairs
    (`docs/P27_VISUAL_ACCEPTANCE.md:186` says so). Measured here from the
    current h264 film, the same jitter is 266-3666 px -- never 0. So this can
    only be measured on a LOSSLESS render, which is what this test does.

    IF THIS TEST EVER FAILS because the frames now DIFFER, that is the freeze
    being fixed (a camera move, or a shorter hold). Re-derive the numbers in
    the message before changing them -- do not delete the check.
    """
    frames = _render_scene(tmp_path / 'c01', 'c01_bar', [70, 71])
    changed = _frame_equality(frames[70], frames[71])
    assert changed >= 0, 'the two frames are different sizes; not comparable'
    assert changed == 0, (
        f'c01_bar frames 70 and 71 now differ by {changed} px. As measured in '
        'P48 they were byte-identical (0 px): the scene holds a frozen still '
        'for ~1.35 s, because `lifecycleAt`\'s focus phase is static by design '
        'AND the graph gives the camera no movement channel (only a constant '
        '`perspective`), so `motion.preset: premium` multiplies nothing. If '
        'this is now fixed, update this guard AND the ledger -- the freeze was '
        'a real finding, not a rounding detail.')


@pytestmark_render
def test_the_freeze_is_invisible_to_rule_freeze_from_a_video(tmp_path):
    """Why P27 could not see it, reproduced as a measurement.

    `rule_freeze`'s criterion is `changed == 0`. P27 ran the rule on frames
    DECODED FROM THE 226 kbps FILM, where a frozen pair still carries codec
    jitter, so the criterion never fires. (A still-image re-encode does NOT
    reproduce this -- measured: two byte-identical frames saved to jpeg at
    quality 28 are still byte-identical, because jpeg is deterministic. The
    jitter is INTER-frame prediction in a real video stream.)

    So this test encodes the frozen pair into an actual h264 stream at a film-
    like bitrate, decodes two consecutive frames back, and shows the rule flips
    from FAIL to PASS purely because the input changed -- the artefact did not.

    "Measured on the wrong input" and "there is nothing there" look identical
    from the outside; that is the shape this whole file exists against.
    """
    if shutil.which('ffmpeg') is None:
        pytest.skip('ffmpeg absent; the compressed-input half did NOT run')

    frames = _render_scene(tmp_path / 'c01', 'c01_bar', [70, 71])
    lossless = vqa.rule_freeze(frames[70], frames[71])
    assert lossless.verdict == vqa.FAIL, (
        'rule_freeze did not call two byte-identical frames frozen. The rule '
        f'or its criterion changed: {lossless.detail!r}')

    # Encode an h264 stream that repeats the frozen image as an inter-coded
    # sequence, then pull two consecutive frames back out. The encoder sees a
    # still, exactly as it does in the film's frozen window.
    vid = tmp_path / 'frozen.mp4'
    seq = tmp_path / 'seq.txt'
    seq.write_text(''.join(f"file '{frames[70]}'\n" for _ in range(4)), encoding='utf-8')
    enc = subprocess.run(
        ['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(seq),
         '-r', '60', '-c:v', 'libx264', '-b:v', '226k', '-pix_fmt', 'yuv420p', str(vid)],
        capture_output=True, text=True)
    assert enc.returncode == 0, f'ffmpeg encode failed:\n{enc.stderr}'

    decoded = []
    for i in (1, 2):
        png = tmp_path / f'dec{i}.png'
        dec = subprocess.run(
            ['ffmpeg', '-y', '-v', 'error', '-i', str(vid), '-vf', f'select=eq(n\\,{i})',
             '-vsync', '0', '-frames:v', '1', str(png)],
            capture_output=True, text=True)
        assert dec.returncode == 0, f'ffmpeg decode failed:\n{dec.stderr}'
        decoded.append(png)

    compressed = vqa.rule_freeze(*decoded)
    assert compressed.value > 0, (
        'two consecutive frames decoded from the h264 stream measured 0 '
        'differing pixels, so this test proved nothing about a video codec\'s '
        'jitter floor -- check the encode settings.')
    assert compressed.verdict == vqa.PASS, (
        'rule_freeze still called the pair frozen when fed frames from a '
        'compressed stream. §四.1 of the P48 report rests on the opposite: on '
        f'the film the frozen pair carries codec jitter. Measured: '
        f'{compressed.detail!r}')


# ── 2. a declared chart field with no reader: c05_bubble's `sizes` ───────────

@pytestmark_render
def test_the_declared_bubble_sizes_are_inert(tmp_path):
    """`c05_bubble` declares `sizes`; the renderer reads `series[].sizes`.

    MEASURED (this test): changing `chart.sizes` from `[8,22,40,61,79,95]` to
    all 1 changes 0 pixels, while changing `chart.values[0]` from 12 to 11
    changes the frame. The declared `sizes` array is a sentence nothing reads
    -- `Chart.tsx` passes `spec.series?.[0]?.sizes` to `<Bubble>`, and this
    graph has no `series`, so the mark falls back to `values`.

    A POSITIVE CLASS is proved too, so a 0 here cannot mean "the render was
    empty": the `values` mutation must move pixels.
    """
    def mutate_sizes(chart):
        chart['sizes'] = [1, 1, 1, 1, 1, 1]

    def mutate_values(chart):
        chart['values'] = [11, 28, 45, 66, 88, 100]

    base = _render_scene(tmp_path / 'base', 'c05_bubble', [100])[100]
    moved = _render_scene(tmp_path / 'sizes', 'c05_bubble', [100],
                          chart_mutate=mutate_sizes)[100]
    valued = _render_scene(tmp_path / 'values', 'c05_bubble', [100],
                           chart_mutate=mutate_values)[100]

    # the instrument works: the values mutation MUST move the frame
    assert _frame_equality(base, valued) > 0, (
        'perturbing chart.values[0] changed 0 pixels, so this test is not '
        'measuring the mark at all -- fix the fixture before reading the next '
        'assertion as a finding about `sizes`.')
    assert _frame_equality(base, moved) == 0, (
        'changing c05_bubble\'s declared `sizes` moved pixels, so something now '
        'reads it. If a reader was added, remove the inertness finding from the '
        'P48 report -- and if the intent is that `chart.sizes` be honoured, '
        'wire it in `Chart.tsx` (which reads `series[].sizes` only).')


# ── 3. a rule that measures its argument, not the frame ──────────────────────

def test_rule_font_size_verdict_tracks_the_argument_not_the_frame():
    """`font_size`'s verdict is decided by `declared_px`, not by the pixels.

    MEASURED (this test): ONE synthetic frame is fed to `rule_font_size` twice,
    with `declared_px=20` and `declared_px=5`. The verdict is PASS then FAIL --
    while the frame, and every pixel-derived number in the reading, is
    identical. The measured `median` band enters only the ratio's numerator;
    the verdict is `declared_px < MIN_TYPE_PX`.

    This is the P22 shape one rule over: a constant reported as a per-frame
    measurement. P22 moved `contrast` off the frame path for exactly this
    reason; `font_size` kept the shape. It is pinned here so a reader sees it,
    not so it is endorsed -- the honest form is a rule that reads the rendered
    size and compares it to what the graph DECLARED, which needs the declared
    size from the graph rather than from argv.
    """
    # a plain frame with a text-like band. The band must be NARROW relative to
    # the frame (visual_qa.text_band_heights rejects a row band wider than 25%
    # of the width as a solid rectangle, not text) and must clear the backdrop
    # trust check, or the rule returns UNVERIFIABLE and there is no verdict to
    # compare. 180 px of a 640-wide frame is 28% of the frame but only ~9% of
    # the 1920 model -- sized here to sit under the 25% band cut.
    frame = np.full((360, 1920, 3), 12, dtype=int)
    frame[140:176, 880:1060] = 245  # one narrow bright band
    big = vqa.rule_font_size(frame, declared_px=20.0)
    small = vqa.rule_font_size(frame, declared_px=5.0)
    assert big.verdict == vqa.PASS and small.verdict == vqa.FAIL, (
        'rule_font_size no longer flips on `declared_px` alone. If it now '
        'measures the frame, delete this characterisation and replace it with '
        'one that asserts the frame decides the verdict.')
    # the frame-derived number is the SAME both times -- the frame did not change
    assert big.extra['measured_median_px'] == small.extra['measured_median_px'], (
        'the two calls measured different median bands, so they are not the '
        'same frame and this test does not show what it claims.')
    assert big.value != small.value, (
        'the reported ratio is identical across the two calls, which would mean '
        'the ratio uses a constant -- reconfirm what the ratio divides by.')


# ── 4. the tautology-hole test P48 commissioned deletion of ──────────────────
#
# P48 MEASURED a hole in `test_p42_fade_is_not_a_freeze.py`'s always-true
# meta-guard: it checked only `node.test.values[0]`, so it recognised
# `assert True or x` and walked past `assert x or True` -- and the same file
# carried a live instance at its line 328
# (`assert c10['durationInFrames'] in durations[:-1] or True`).
#
# The test that pinned that hole (`test_the_always_true_meta_guard_misses_the_
# constant_last_spelling`) said, in its own failure message, to DELETE it if the
# line was ever fixed: "do not leave a guard asserting a hole that no longer
# exists." P50 fixed the line (dropped the `or True`) and widened the guard's
# criterion to flag a literal-`True` operand on EITHER side of an `or`, so the
# hole is closed. The pin is therefore removed here, as its own message ordered,
# and not left behind asserting a hole that is gone. The replacement guard -- a
# positive test that the criterion catches both spellings -- lives in
# `test_p42_fade_is_not_a_freeze.py::test_the_meta_guard_flags_both_halves_of_an_or`.
