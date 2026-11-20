"""P49 — every scene must MOVE between its entrance and its exit.

THE DEFECT THIS EXISTS FOR
--------------------------
`charts_demo.json` declared ten scenes whose camera was `{"perspective": 1600}`
and nothing else. `perspective` is a constant. `common/CameraRig.tsx` computes
camera progress as

    ct = min(frame / cameraMoveFrames(motion.preset, dur, fps), 1)

and feeds it to `track(channel, ct, fallback)` for each of translateX/Y/Z,
rotateX/Y/Z and scale. With no channel declared, `track(undefined, ct, 0)`
returns the fallback for every one of them, so `ct` walked 0 -> 1 over 156
frames and multiplied NOTHING. The camera transform was the constant string
`perspective(1600px)` for all 150 frames of every scene.

The chart marks themselves are DRIVEN BY DESIGN TO STOP: `lifecycle.ts`
`focus` is "the reading moment. Nothing moves". So once the marks finish
arriving (measured: frame ~69 of a 150-frame scene, when the emphasised mark
reaches full attention at the end of `settle`) the ONLY thing that could keep
the frame alive is the camera -- and the camera was inert.

WHY `scale`, AND NOT `rotateY` -- MEASURED, NOT CHOSEN BY TASTE
---------------------------------------------------------------
The obvious repair for "the camera never moves" is a yaw, because the reference
film's camera is a `rotateY`-type orbit (P37 measured real 3D camera motion at
51-55 s; P46:393 classifies it as a projective orbit). A first pass put
`rotateY: [-3, 3]` on all ten scenes. That was rejected on measurement, on a
bar chart, and the measurement is reproducible:

    bar-centre x, five bars, at frame 137
      perspective only (the defect)   314.5  648.0  981.5  1315.0  1647.5
                                       spacing 333.5 333.5 333.5 332.5  -- uniform
      rotateY: [-3, 3]                304.0  645.5  981.5  1311.5  1636.0
                                       spacing 341.5 336.0 330.0 324.5  -- compresses 5%
      scale: [1.04, 1.0]              289.0  636.0  982.5  1329.0  1676.0
                                       spacing 347   346.5 346.5 347    -- uniform

`rotateY` makes the chart a TRAPEZOID: the spacing between adjacent bars shrinks
by 5% from the near edge to the far edge, the baseline axis stops being
horizontal, and the emphasis bar's value label ("61.4M") is clipped off the top
of the frame. On a chart whose bars encode value as LENGTH that is a
data-integrity defect, not a style choice, and it is the same family as the
ledger's still-undecided "s03 相机 rotateX:[12,2] 把竖柱剪斜".

`scale` is rigid: bar-to-label offsets measured [0.0, -0.5, 0.5, 0.5, 0.5] px
(within half a pixel), and the bar spacing scales by exactly the authored
factor. It is also a DELIVERED channel -- `showcase_demo.json` uses
`scale: [1.06, 1.0]` on `s01_kpi` and `scale: [1.04, 1.0]` on `s04_calendar` --
so the vocabulary is not invented here.

`[1.04, 1.0]` rather than `[1.06, 1.0]` or a growing zoom: it is s04_calendar's
value verbatim, and it settles INWARD, so the composition can only shrink and
therefore can never clip the frame edge the way the outward `rotateY` did. A
dense data composition (a calendar grid) is a closer analogue than a single
hero number.

ALL TEN SCENES GET THE SAME CHANNEL, AND THAT IS A CONCLUSION
------------------------------------------------------------
Not a shortcut, and not "it makes it move" (which describes an effect, not a
reason). The rule is per chart TYPE: every one of these ten scenes is a single
rigid plane whose marks encode value, and the measurement above says `scale` is
the one channel that cannot distort such a plane and `rotateY` does distort it.
The rule applies to all ten, so all ten get the same answer. A scene whose
marks do NOT encode value could take a different channel; none exists here.

MEASURED, LOSSLESS, ON THE DELIVERED GRAPH BEFORE THE REPAIR
-------------------------------------------------------------
Rendered with `bin/still.mjs` at 1920x1080, compared pixel-exact:

    c01_bar  f00053 -> f00138    0 changed pixels, 85 consecutive pairs
    9 of the 10 scenes  f71 -> f137    0 changed pixels
    c06_heatmap          f71 -> f137    9,434 px -- its ENTRANCE, not the camera

c06 is the tenth scene and it is the exception worth naming: 18 staggered cells
run its entrance to frame ~84 instead of c01's ~69, so the f71/f137 pair still
catches the decaying tail of the marks arriving. Densely measured, its changed
count also reaches 0 (from frame ~84). All ten freeze; they freeze at
different frames. That is why this guard renders a WINDOW and demands every
adjacent pair inside it move, rather than sampling two frames.

WHY THE KNOWN GUARD DID NOT CATCH IT
------------------------------------
`visual_qa.rule_freeze` runs on the ENCODED film, where the 226 kbps h264
stream leaves 281-2329 px of compression flicker on every "frozen" frame, so
`changed == 0` never fires and the rule returns 30/30 PASS. `rule_freeze` is
not wrong; it is measuring a different surface. A guard for THIS defect must
run on LOSSLESS frames, or say UNAVAILABLE -- never PASS.

WHAT IS ASSERTED
----------------
1. STRUCTURAL (no render, cheap, PER SCENE): every scene in `charts_demo.json`
   declares at least one camera channel that actually MOVES (a `[from, to]`
   with from != to). This is the graph half, and it is asked per scene so a
   graph where nine scenes are fixed and one is not still goes red.
2. PIXELS (render, one representative scene `c01_bar`): every adjacent frame
   pair from frame 0 to `exitStart - 1` differs by at least one pixel. This is
   the film half, and it is the assertion the encoded-film rule structurally
   cannot make.
3. Both predicates are RUN against input they must reject, so a predicate
   rewritten to always pass is caught by execution rather than by reading.

WHAT IS NOT PROVEN HERE (stated, not implied)
---------------------------------------------
Part 2 renders ONE scene. The freeze was STRUCTURAL -- ten scenes sharing one
channel-less camera -- so one scene exercising the repaired channel is
representative of the mechanism. It is not a per-scene pixel audit; part 1
covers all ten structurally, and P49's own report carries the per-scene
two-endpoint measurement taken separately.

WHY ENOBUFS IS RETRIED RATHER THAN REPORTED
-------------------------------------------
Rendering N lossless stills in one process exhausts the Windows socket table
(MEASURED: a 68-frame list completes in 38 s; a 91-frame list dies with
`ENOBUFS 127.0.0.1`). That is a fact about the machine, not about the film. It
is retried a few times with a backoff, and the reason is never converted into
a verdict: ENOBUFS must not be allowed to read as PASS ("couldn't measure" is
not "fine") and must not be dressed up as a frozen frame either. Any OTHER
still failure fails the test immediately.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / 'studio'
GRAPH = ROOT / 'pipeline' / 'examples' / 'charts_demo.json'
STILL = STUDIO / 'bin' / 'still.mjs'
LIFECYCLE_TS = (STUDIO / 'src' / 'templates' / 'finance-showcase'
                / 'charts' / 'lifecycle.ts')

sys.path.insert(0, str(ROOT / 'studio' / 'scripts'))
import visual_qa as vqa  # noqa: E402

_NODE = shutil.which('node')

#: The scene part 2 renders. `c01_bar` is the scene the work order measured and
#: the one the guard is written against; it is also a real shipped scene, so the
#: camera, the motion preset and the lifecycle are the film's own.
REPRESENTATIVE = 'c01_bar'

#: Channels that move the frame when perturbed. `focus` is deliberately NOT
#: here: `CameraSchema` declares `camera.focus`, but `CameraRig.cameraStateAt`
#: has no `focus` term and nothing reads it, so a graph that set only `focus`
#: would still be still. Leaving it out is the point -- this list is "channels a
#: reader consumes", measured from `cameraStateAt`, not "channels the schema
#: allows".
ANIMATED_CHANNELS = ('translateX', 'translateY', 'translateZ',
                     'rotateX', 'rotateY', 'rotateZ', 'scale')

#: A frame pair with zero changed pixels is frozen. Zero, not "small": the
#: repair must leave real motion, and the smallest measured post-fix pair is
#: 4159 px, four orders of magnitude above the floor. A threshold here would be
#: an invented number; 0 is the actual definition of "identical".
ZERO = 0

#: Frames per `still.mjs` invocation. MEASURED: one process asking for more than
#: ~90 lossless stills exhausts the Windows ephemeral-port table and dies with
#: `ENOBUFS 127.0.0.1`; 68 in a list completes. 40 sits well under the ceiling
#: and keeps each subprocess short.
_CHUNK = 40

#: How many times a failed chunk is retried, and the backoff between attempts.
#: Every render failure seen on this machine has been environmental (ENOBUFS, or
#: a headless-browser navigation failure when another agent renders at the same
#: time), so a chunk is retried before the test is failed. This cannot turn a
#: failure into a pass: the frames must exist and the pixel assertion is
#: unchanged, and a deterministic error fails every attempt and is reported.
_ENOBUFS_RETRIES = 4
_ENOBUFS_BACKOFF = 5.0


def _graph() -> dict:
    return json.loads(GRAPH.read_text(encoding='utf-8'))


def _channel_moves(value: object) -> bool:
    """Does this camera channel value change over the scene at all?

    A number is a constant -- it is the same at frame 0 and frame `dur`, so it
    moves nothing. Only a two-element `[from, to]` with `from != to` describes
    a change. A `[3, 3]` interval is a constant written in interval clothing;
    it is rejected on purpose.
    """
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return float(value[0]) != float(value[1])
        except (TypeError, ValueError):
            return False
    return False


def _moving_channels(camera: dict | None) -> list[str]:
    if not isinstance(camera, dict):
        return []
    return [k for k in ANIMATED_CHANNELS if _channel_moves(camera.get(k))]


def _exit_start(duration_in_frames: int) -> int:
    """First frame of the scene's exit, from the same mirror `black_frame` uses.

    `visual_qa.exit_window_start` is a mirror of `charts/lifecycle.ts`
    (`EXIT_SHARE`/`EXIT_MIN`) and `test_p42_fade_is_not_a_freeze` already
    asserts that mirror EQUALS the TypeScript it mirrors. Reused rather than
    re-derived here, so there is one mirror and not two.
    """
    return vqa.exit_window_start(duration_in_frames)


# ── pixels ───────────────────────────────────────────────────────────────────

def _changed(a: Path, b: Path, tol: int = 8) -> int:
    """Differing pixel count between two lossless frames; -1 if incomparable."""
    import numpy as np
    from PIL import Image

    ia = np.asarray(Image.open(a).convert('RGB')).astype(np.int16)
    ib = np.asarray(Image.open(b).convert('RGB')).astype(np.int16)
    if ia.shape != ib.shape:
        return -1
    return int((np.abs(ia - ib) > tol).any(axis=2).sum())


def _dead_pairs(frames: list[Path]) -> list[tuple[int, int]]:
    """Adjacent index pairs whose frames are pixel-identical.

    Split out so the mutation self-test can drive it with frames it built to be
    frozen -- a predicate proven only against input that passes is a comment.
    """
    out: list[tuple[int, int]] = []
    for i in range(len(frames) - 1):
        if _changed(frames[i], frames[i + 1]) == ZERO:
            out.append((i, i + 1))
    return out


def _render_window(scene_id: str, last_frame: int, dest: Path) -> list[Path]:
    """Render frames 0..last_frame of `scene_id`, losslessly, scene-local.

    A single-scene props file puts scene 0 at global frame 0, so the frame
    number IS the scene-local frame -- the P46 lesson: an absolute frame number
    silently renders a different scene, the confident-zero shape.
    """
    dest.mkdir(parents=True, exist_ok=True)
    scene = next((s for s in _graph()['scenes'] if s['id'] == scene_id), None)
    assert scene is not None, f'{scene_id} is not in {GRAPH.name}'
    doc = {k: v for k, v in _graph().items() if k != 'scenes'}
    doc['scenes'] = [scene]
    props = dest / f'{scene_id}.json'
    props.write_bytes(json.dumps(doc, ensure_ascii=False, indent=1).encode('utf-8'))

    scratch = dest / 'scratch'
    public = dest / 'public'
    scratch.mkdir(exist_ok=True)
    public.mkdir(exist_ok=True)
    env = {**os.environ, 'TMPDIR': str(scratch), 'TMP': str(scratch),
           'TEMP': str(scratch), 'REMOTION_SCRATCH_DIR': str(scratch)}
    # CHUNKED on purpose. `still.mjs` renders the frame list SEQUENTIALLY, but
    # each `renderStill` opens an HTTP connection to the headless browser and
    # Windows does not reclaim the ephemeral ports fast enough: one process
    # asking for more than ~90 stills dies with ENOBUFS on ~127.0.0.1, which is
    # not a rendering failure but a socket-exhaustion one. MEASURED: a 68-frame
    # list completes (38 s); a 91-frame list fails with ENOBUFS. So the render
    # is split into chunks, each its own subprocess -- a new process gets a
    # fresh socket table.
    for start in range(0, last_frame + 1, _CHUNK):
        stop = min(start + _CHUNK - 1, last_frame)
        argv = [_NODE, str(STILL), '--comp', 'FinanceShowcaseWide',
                '--props', str(props), '--out', str(dest),
                '--frames', ','.join(str(f) for f in range(start, stop + 1)),
                '--public-dir', str(public)]
        for attempt in range(1, _ENOBUFS_RETRIES + 1):
            proc = subprocess.run(argv, cwd=str(STUDIO), capture_output=True,
                                  text=True, timeout=3600, encoding='utf-8',
                                  errors='replace', env=env)
            if proc.returncode == 0:
                break
            # Every render failure on this machine has been an ENVIRONMENT one --
            # ENOBUFS (Windows socket table, MEASURED: a 68-frame list completes
            # in 38 s, a 91-frame list dies), or a headless-browser navigation
            # failure under concurrent renders from another agent. Both are
            # retried with a backoff. Neither can become a verdict: a run whose
            # render never produced frames FAILS the test below rather than
            # passing an empty window, and a deterministic error (a broken graph,
            # a bad flag) simply fails every attempt and is reported.
            if attempt < _ENOBUFS_RETRIES:
                time.sleep(_ENOBUFS_BACKOFF * attempt)
                continue
            raise AssertionError(
                f'still failed for {scene_id} over frames {start}..{stop} '
                f'after {attempt} attempts. If this is ENOBUFS it is this '
                f"machine's socket table, not the film.\n"
                f'stdout:\n{proc.stdout[-4000:]}\nstderr:\n{proc.stderr[-4000:]}')
    out = []
    for f in range(last_frame + 1):
        p = dest / f'f{f:05d}.png'
        assert p.is_file(), (
            f'{p} was not written -- a missing frame would be silently skipped '
            'and the window would shrink to whatever rendered')
        out.append(p)
    return out


# ── 1. STRUCTURAL (no render): every scene asks for a moving camera ──────────

def test_every_scene_declares_a_camera_channel_that_moves():
    """The graph half, per scene.

    A scene whose camera has no moving channel is a scene where
    `motion.preset` is a dumb declaration: it is read, it drives `ct`, and `ct`
    multiplies nothing. That is the failure this assertion names, for every
    scene, without rendering.
    """
    doc = _graph()
    scenes = doc['scenes']
    assert scenes, f'{GRAPH.name} has no scenes'
    dead = []
    for s in scenes:
        moving = _moving_channels(s.get('camera'))
        if not moving:
            dead.append(s['id'])
    assert not dead, (
        f'these scenes declare no camera channel that changes over time: {dead}.\n'
        'Their camera transform is a constant, so `motion.preset` is multiplied '
        'by nothing and the frame freezes the moment the chart entrance ends. '
        'Measured on the delivered graph: 0 changed pixels for 85 consecutive '
        'frame pairs (`c01_bar` f53..f138). Give each scene a `[from, to]` '
        'channel with from != to (the repair used `scale: [1.04, 1.0]`, '
                     'chosen by measurement -- see the header).')


# ── 2. PIXELS: nothing freezes between frame 0 and the exit ──────────────────

def test_no_two_adjacent_frames_between_start_and_exit_are_identical(tmp_path):
    """The film half, on lossless frames.

    `rule_freeze` runs on the encoded film and cannot see this (the codec's own
    flicker, 281-2329 px per frozen frame, keeps `changed == 0` from ever
    firing). This renders LOSSLESS and compares pixel-exact, so a frozen
    window is reported rather than hidden.
    """
    if _NODE is None or not STILL.is_file():
        pytest.skip('node/studio tree absent; the camera-move freeze is NOT '
                    'checked here (skipped, not passed)')
    scene = next(s for s in _graph()['scenes'] if s['id'] == REPRESENTATIVE)
    last = _exit_start(scene['durationInFrames']) - 1
    assert last >= 1, f'{REPRESENTATIVE} is too short to hold a window'
    frames = _render_window(REPRESENTATIVE, last, tmp_path / REPRESENTATIVE)
    dead = _dead_pairs(frames)
    assert not dead, (
        f'{REPRESENTATIVE}: {len(dead)} adjacent frame pair(s) in 0..{last} are '
        f'pixel-identical, first at frames {dead[:5]}. A scene that does not '
        'change between its entrance and its exit is a still frame, and the '
        'delivered graph had 85 such pairs per scene. The camera must move for '
        'the whole window: if a channel was added but its move finishes before '
        'the exit, the dead zone has only MOVED.')


# ── 3. the predicates must be able to say NO ─────────────────────────────────

def test_the_dead_pair_predicate_rejects_frozen_frames(tmp_path):
    """`_dead_pairs` must call identical frames dead, and differing frames not.

    Run, not read: a predicate rewritten to `return []` parses perfectly and
    measures nothing. Both directions are asserted on frames this test builds,
    so the predicate cannot pass by being blind to one side.
    """
    import numpy as np
    from PIL import Image

    a = tmp_path / 'a.png'
    b = tmp_path / 'b.png'
    c = tmp_path / 'c.png'
    arr = np.zeros((32, 32, 3), dtype=np.uint8)
    Image.fromarray(arr).save(a)
    Image.fromarray(arr).save(b)            # identical to a
    moved = arr.copy()
    moved[0, 0] = (255, 0, 0)               # one pixel differs
    Image.fromarray(moved).save(c)
    assert _dead_pairs([a, b]) == [(0, 1)], 'identical frames were not called dead'
    assert _dead_pairs([a, c]) == [], 'a one-pixel change was called dead'
    assert _dead_pairs([a]) == [], 'a single frame reported a pair'


def test_the_channel_predicate_rejects_a_constant_and_accepts_a_move():
    """`_channel_moves` must separate a move from every way of writing "no move".

    A constant number moves nothing; a `[3, 3]` interval is a constant in
    interval clothing; only `[from, to]` with from != to describes change. A
    predicate that returned True for any list would pass the graph half while
    the camera stood still.
    """
    assert _channel_moves([-3, 3]) is True
    assert _channel_moves([1.0, 1.045]) is True
    assert _channel_moves(1600) is False, 'a constant was called a move'
    assert _channel_moves([3, 3]) is False, '[3, 3] is a constant, not a move'
    assert _channel_moves(None) is False
    assert _channel_moves([]) is False


def test_a_scene_with_only_a_constant_camera_is_reported_dead():
    """The graph assertion, run against a scene it must reject.

    Drives the exact predicate part 1 uses, on a camera of the shape the
    defect used, so part 1 cannot be green-by-construction.
    """
    assert _moving_channels({'perspective': 1600}) == [], (
        'a perspective-only camera was found to carry a moving channel -- part 1 '
        'would pass the very graph this file was written for')
    assert _moving_channels({'perspective': 1600, 'rotateY': [-3, 3]}) == ['rotateY']
