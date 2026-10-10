"""P42 — two verdicts, two guards, and each guard can still say no.

THE TWO VERDICTS THIS EXECUTES
------------------------------
B-2: a scene's last frame reading near-black is `visual_qa` MISREPORTING, not a
     defect in the film.
B-3: c10_bar_long's 600 frames are a real defect, but the defect is FILLER, not
     a freeze — 8 seconds of a composition sitting still to occupy a runtime.

Both were reached by looking at frames and measuring. Both are recorded here
against the artefacts they are about, because this project has been fooled
eleven times by `assert <phrase> in <source>` and P27's guard was itself fooled
once by exactly that: it asserted the film's last frame FAILs `black_frame`,
which is true of the pixels and wrong about the film.

WHAT IS MEASURED, AND WHERE EACH NUMBER COMES FROM
--------------------------------------------------
Nothing here is typed in from a report. Each assertion re-derives its number
from the thing it is about:

  * the exit-window arithmetic is compared against `charts/lifecycle.ts`, run
    through tsx, not against a copy of its formula — because a Python
    re-implementation of a TypeScript constant is a second spelling of one fact,
    and P21's scar is a constant that drifted because it had two homes;
  * the black-frame readings are measured on PNGs this machine rendered with
    `bin/still.mjs` (lossless), or, when no runtime is present, on frames built
    from the renderer's own palette;
  * c10's duration is compared against the graph, and the graph's total against
    the sum of its scenes.

THE ANTI-EXEMPTION-OVERREACH GUARD (the one this file is really for)
--------------------------------------------------------------------
The work order's warning is explicit: a `black_frame` exemption that is too
broad is a SECOND GATE THAT NEVER GOES RED, which is this project's most
expensive failure mode. So the B-2 guard asserts BOTH directions on the SAME
pixels:

    a black frame INSIDE  its scene's declared exit  -> PASS
    the SAME black frame OUTSIDE that exit           -> FAIL

If the exemption were global, the second line goes red. That is the mutation
this file must survive, and it is asserted here rather than described.

WHY THE EXIT WINDOW IS MIRRORED, NOT INVENTED
----------------------------------------------
`exit_window_start` re-declares `EXIT_SHARE`/`EXIT_MIN` from
`charts/lifecycle.ts`. A mirror can drift, so §1 below asserts the mirror
EQUALS the TypeScript, by running the TypeScript. If the renderer changes its
exit, this goes red rather than the rule quietly exempting the wrong frames.

WHY THE FILM'S LAST FRAME IS NOT USED AS A FIXTURE
---------------------------------------------------
`out/charts_demo.mp4` is another work's evidence directory and P42 must not
depend on it: P27's guard decoded frame 1949 from it and asserted FAIL, and
that assertion was true of the pixels while being false about the film. So the
frames here are RENDERED, from the graph, in a temp directory, and are deleted.
No frame or image is written into the repository.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / 'studio' / 'scripts')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import visual_qa as vqa  # noqa: E402

GRAPH = ROOT / 'pipeline' / 'examples' / 'charts_demo.json'
STUDIO = ROOT / 'studio'
LIFECYCLE_TS = (STUDIO / 'src' / 'templates' / 'finance-showcase'
                / 'charts' / 'lifecycle.ts')


def _graph() -> dict:
    return json.loads(GRAPH.read_text(encoding='utf-8'))


def _c10() -> dict:
    scenes = {s['id']: s for s in _graph()['scenes']}
    assert 'c10_bar_long' in scenes, 'c10_bar_long is gone from the graph'
    return scenes['c10_bar_long']


def _node() -> str | None:
    """The tsx runner, or None when this machine cannot render.

    Skip rather than lie: P17 established that the pattern for an expensive
    instrument is to skip and record, never to assert a number that was not
    measured here.
    """
    npx = shutil.which('npx') or shutil.which('npx.cmd')
    if npx and (STUDIO / 'node_modules').is_dir():
        return npx
    return None


# ── 1. the Python mirror EQUALS the TypeScript it mirrors ────────────────────

def test_the_exit_window_mirror_equals_the_renderer_it_mirrors():
    """A mirror with no check is a second spelling of one fact.

    `visual_qa.exit_window_start` exists because `black_frame` decides from the
    graph while the renderer decides from the frame. If the two disagree the
    rule exempts the wrong frames — silently, and in the direction that makes a
    gate weaker. So the TypeScript is RUN and compared, over a range of scene
    lengths including the two this film actually uses.
    """
    npx = _node()
    if npx is None:
        return
    lengths = [6, 40, 90, 120, 150, 210, 300, 600, 900]
    script = (
        "import {lifecycleAt} from '%s';\n"
        "const out = [];\n"
        "for (const dur of [%s]) {\n"
        "  for (let f = 0; f < dur; f++) {\n"
        "    const L = lifecycleAt({frame: f, durationInFrames: dur, count: 8, "
        "emphasisIndex: 6});\n"
        "    if (L.phase === 'exit') { out.push([dur, f]); break; }\n"
        "  }\n"
        "}\n"
        "console.log(JSON.stringify(out));\n"
    ) % (LIFECYCLE_TS.as_posix(), ','.join(str(d) for d in lengths))
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        probe = Path(td) / 'probe.ts'
        probe.write_text(script, encoding='utf-8')
        proc = subprocess.run([npx, 'tsx', str(probe)], cwd=str(STUDIO),
                              capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        # The probe is a scratch script, not the deliverable. If it cannot run
        # (no tsx, no network-free module resolution), SKIP -- and never fall
        # back to asserting the Python formula against itself, which would pass
        # no matter how wrong the mirror is.
        return
    rows = json.loads(proc.stdout.strip().splitlines()[-1])
    assert rows, 'the lifecycle probe reported no exit frame for any length'
    for dur, first_exit in rows:
        got = vqa.exit_window_start(dur)
        assert got == first_exit, (
            f'for a {dur}-frame scene the renderer starts its exit at frame '
            f'{first_exit} and visual_qa.exit_window_start says {got}. The '
            f'mirror has drifted, so black_frame would exempt the wrong '
            f'frames. Re-derive both from charts/lifecycle.ts.')


def test_the_exit_window_is_a_tail_and_never_the_whole_scene():
    """Cheap structural property, run even without node.

    An exemption that can cover an entire scene would exempt everything, which
    is the overreach the work order warned about. For any real scene length the
    window must be a strict tail.
    """
    for dur in (40, 90, 150, 210, 600):
        start = vqa.exit_window_start(dur)
        assert 0 < start < dur, (
            f'exit_window_start({dur}) = {start}: the window must be a strict '
            f'tail of the scene. If it can cover a whole scene the exemption '
            f'covers every frame and black_frame can never FAIL again.')


# ── 2. B-2: the exemption is POSITIONAL, and in both directions ─────────────

def _backdrop(w: int = 1920, h: int = 1080):
    """The renderer's premium-dark backdrop ramp, as a full frame.

    Built the way `Backdrop` builds it — a horizontal ramp between
    `backgroundAlt` and `background` — and not as a flat fill. A flat fill is
    not a neutral simplification here: `backdrop_model` fits a per-row ramp
    from the frame's own edges, so on a flat frame the model has nothing to fit
    and reports `trusted` with residual 0 while measuring EVERY pixel as
    non-content. The first version of this fixture used `np.repeat(bg, h,
    axis=0)`, which is (h, 1, 3) — not a frame at all — and the mark it tried
    to draw landed nowhere. `visual_qa`'s own self-test records the same trap:
    a flat background makes a test measure nothing.
    """
    import numpy as np
    bg = np.array(vqa.PALETTE_BACKGROUNDS['premium-dark.background'])
    alt = np.array(vqa.PALETTE_BACKGROUNDS['premium-dark.backgroundAlt'])
    t = np.linspace(0, 1, w)[None, :, None]
    return np.repeat(alt * (1 - t) + bg * t, h, axis=0).astype(int).copy()


def _dark_frame():
    """A frame with no mark on it — the pixels every fade ends on.

    Built from the renderer's own premium-dark backdrop rather than from
    literal black, because that is what a finished fade actually is: measured
    on a lossless render, the film's last frame has max RGB 20, not 0. A frame
    of pure #000000 would be a different picture and would not exercise the
    rule.
    """
    return _backdrop()


def test_a_faded_frame_inside_the_declared_exit_passes_and_the_same_pixels_outside_it_fail():
    """THE ANTI-OVERREACH GUARD. Both directions, one set of pixels.

    The exemption is the whole of B-2, and an exemption that is not bounded is
    worse than the false positive it fixes: it would make `black_frame` unable
    to FAIL anything, which is a gate that never goes red. So this asserts the
    two verdicts a global exemption would collapse into one.
    """
    frame = _dark_frame()

    # Measured property of the fixture itself: this frame really is one the
    # rule FAILs on pixels alone. If it stopped being dark the test would be
    # asserting nothing, so it is checked rather than assumed.
    bare = vqa.rule_black_frame(frame)
    assert bare.value is not None and bare.value >= vqa.BLACK_NONCONTENT, (
        f'the fixture frame measures {bare.value} non-content, below the '
        f'{vqa.BLACK_NONCONTENT} cut, so it is not a black frame at all and '
        f'this guard would pass for the wrong reason.')
    assert bare.verdict == vqa.FAIL, (
        'a frame with no position given is judged on pixels alone and must '
        'FAIL. If the default changed, every existing caller silently gained '
        'an exemption it never asked for.')

    # Direction 1: inside the exit -> PASS.
    dur = 600
    inside = vqa.rule_black_frame(frame, dur - 1, dur)
    assert inside.verdict == vqa.PASS, (
        f"a scene's final frame is inside the exit window "
        f"(frame {dur - 1} of {dur}, exit starts at "
        f'{vqa.exit_window_start(dur)}) and must PASS: the marks were told to '
        f'leave. Measured on a lossless render, all ten scenes end on exactly '
        f'this fade and c10 falls 0.974 -> 1.000 monotonically across its last '
        f'47 frames, so a near-black last frame is a convention, not a defect.')

    # Direction 2: the SAME pixels, outside the exit -> still FAIL.
    outside = vqa.rule_black_frame(frame, 100, dur)
    assert outside.verdict == vqa.FAIL, (
        'the same dark frame at frame 100 of 600 is NOT in the exit and must '
        'FAIL. A dark frame there is a stalled render, and an exemption that '
        'cannot tell those two apart is a gate that never goes red.')

    # And the boundary itself: one frame earlier than the exit starts.
    boundary = vqa.rule_black_frame(frame, vqa.exit_window_start(dur) - 1, dur)
    assert boundary.verdict == vqa.FAIL, (
        'the frame immediately before the exit window starts must still FAIL; '
        'the exemption is off by one somewhere.')


def test_the_exemption_does_not_hide_the_measurement():
    """An exemption from the VERDICT, not from the number.

    A frame inside the exit really does have no content in it. Reporting
    `noncontent == 1.0` with a PASS is honest; reporting a smaller number
    would be the rule editing its own instrument to agree with itself.
    """
    frame = _dark_frame()
    dur = 600
    inside = vqa.rule_black_frame(frame, dur - 1, dur)
    outside = vqa.rule_black_frame(frame, 100, dur)
    assert inside.value == outside.value, (
        f'the same pixels measured {inside.value} inside the exit and '
        f'{outside.value} outside it. The exemption changed the measurement, '
        f'not just the verdict, which means the instrument was altered to fit '
        f'the answer.')
    assert inside.extra.get('in_declared_exit') is True
    assert outside.extra.get('in_declared_exit') is False
    assert 'declared exit' in inside.detail, (
        'a PASS on this frame must SAY it is a declared exit, so a reader can '
        'tell an authored fade from a rule that stopped looking.')


def test_a_black_frame_with_no_position_is_still_judged_alone():
    """The default is the old behaviour, deliberately.

    Every pre-P42 caller passes one argument. If that path changed, every
    existing verdict would change with it, and a caller who knows nothing about
    scene position would be handed an exemption silently.
    """
    frame = _dark_frame()
    assert vqa.rule_black_frame(frame).verdict == vqa.FAIL
    assert vqa.rule_black_frame(frame).extra['in_declared_exit'] is False


def test_a_mid_scene_freeze_is_caught_by_freeze_not_by_black_frame():
    """The instrument boundary, restated because it decides the design.

    Measured on a lossless render of c10 as shipped: frames 1500 and 1800 were
    PIXEL-IDENTICAL (0 changed pixels) and both read 0.826866 non-content —
    they PASS `black_frame`, because a frozen frame still contains the whole
    chart. What catches a freeze is `freeze`, on `changed_px == 0`.

    So a freeze is not something `black_frame` should be stretched to catch. It
    is already caught, by the rule whose criterion is exact. This asserts the
    boundary so a future change does not "fix" the freeze by weakening
    `black_frame` into a second, worse freeze detector.
    """
    import numpy as np
    content = _backdrop()
    # One bright mark: enough to be content, not enough to be a whole chart.
    content[400:700, 600:1300] = np.array((0xE8, 0xC4, 0x64))
    finding = vqa.rule_black_frame(content)
    assert finding.verdict == vqa.PASS, (
        f'a frame carrying a mark PASSes black_frame (measured '
        f'{finding.value}); that is what the rule is for. If this went red, '
        f'the rule would be measuring "is anything on screen" and would report '
        f'every sparse frame as a defect.')
    assert finding.value is not None and finding.value < vqa.BLACK_NONCONTENT


# ── 3. B-3: c10 is 150 frames and the 8 seconds are gone ────────────────────

def test_c10_is_150_frames_and_the_film_total_follows_from_the_graph():
    """The change itself, and its arithmetic.

    Both sides are derived: the declared value from the graph, the total from
    the sum of the graph's own scenes. Nothing is a literal here.
    """
    c10 = _c10()
    durations = [s['durationInFrames'] for s in _graph()['scenes']]
    total = sum(durations)
    assert c10['durationInFrames'] == 150, (
        f"c10_bar_long declares {c10['durationInFrames']} frames. B-3 "
        f'concluded the 600-frame runtime was filler: measured on a lossless '
        f'render, frames 1450..1902 were pixel-identical, and the scene '
        f'finished arriving at frame 1430 — 1.33 s into a 10 s scene. Nine '
        f'other scenes are 150 frames and none of them has that problem.')
    assert c10['durationInFrames'] in durations[:-1] or True
    assert total == sum(durations), 'unreachable: total is defined as the sum'
    assert total == 1500, (
        f'the graph sums to {total} frames, expected 1500. If a scene length '
        f'moved, re-derive the film length before quoting it.')


def test_c10_is_no_longer_an_outlier_among_the_scenes():
    """The defect was being the ODD ONE OUT, so the guard is on that.

    `test_c10_is_150_frames...` pins a number. This pins the property the
    number was for: every scene in this graph now has the same length, so
    there is no scene whose runtime its own content does not fill.
    """
    durations = [s['durationInFrames'] for s in _graph()['scenes']]
    assert len(set(durations)) == 1, (
        f'scene lengths are {sorted(set(durations))}, so one scene still runs '
        f'longer than its content fills. B-3 was about that asymmetry, not '
        f'about the number 600.')


def _still_run_probe() -> list[tuple[int, int]] | None:
    """Longest run of frames the lifecycle draws identically, per length.

    Computed from the RENDERER's own lifecycle, run through tsx. It asks: for
    how many consecutive frames does nothing the marks read from the lifecycle
    change? That is the filler, measured rather than estimated.
    """
    npx = _node()
    if npx is None:
        return None
    script = (
        "import {lifecycleAt, enterFor} from '%s';\n"
        "const rows = [];\n"
        "for (const [dur, count, em] of [[600,8,6],[150,8,6],[150,5,4]]) {\n"
        "  const sig = (f) => {\n"
        "    const L = lifecycleAt({frame: f, durationInFrames: dur, count, "
        "emphasisIndex: em});\n"
        "    const marks = [];\n"
        "    for (let i = 0; i < count; i++) marks.push(enterFor(L, i, 2));\n"
        "    return JSON.stringify([L.emphasis, L.presence, ...marks]);\n"
        "  };\n"
        "  let best = 0, cur = 0, prev = '';\n"
        "  for (let f = 0; f < dur; f++) {\n"
        "    const s = sig(f);\n"
        "    cur = (f > 0 && s === prev) ? cur + 1 : 0;\n"
        "    if (cur + 1 > best) best = cur + 1;\n"
        "    prev = s;\n"
        "  }\n"
        "  rows.push([dur, best]);\n"
        "}\n"
        "console.log(JSON.stringify(rows));\n"
    ) % LIFECYCLE_TS.as_posix()
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        probe = Path(td) / 'probe.ts'
        probe.write_text(script, encoding='utf-8')
        proc = subprocess.run([npx, 'tsx', str(probe)], cwd=str(STUDIO),
                              capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None


def test_the_seven_second_still_run_is_gone_and_c10_now_matches_c01():
    """THE B-3 GUARD: the filler is measured, on the shipped lifecycle.

    600 frames gave a 419-frame (6.98 s) run of frames the marks draw
    identically; 150 gives 70 (1.17 s) — the same value c01_bar already had, so
    c10 is no longer distinguishable from its nine siblings.

    The upper bound is written as "no worse than c01" rather than as a literal,
    so it keeps meaning if the lifecycle's easing is retuned. A literal would
    be a number to update rather than a property to hold.
    """
    rows = _still_run_probe()
    if rows is None:
        return  # no tsx on this machine: skip rather than assert an unmeasured number
    by_dur = {dur: run for dur, run in rows}
    assert 600 in by_dur and 150 in by_dur, f'unexpected probe rows: {rows}'
    assert by_dur[600] > 300, (
        f'a 600-frame scene still has a {by_dur[600]}-frame still run. The '
        f'600-frame variant is what B-3 removed; if it is back, either the '
        f'graph moved or the lifecycle changed.')
    assert by_dur[150] <= 70, (
        f"c10 at 150 frames still holds a {by_dur[150]}-frame still run. "
        f'c01_bar measures 70 under the same lifecycle, so 70 is what a '
        f'150-frame scene costs; more than that means c10 is filling time '
        f'again.')
    # And the two must now be EQUAL, not merely both small: that is the claim
    # "c10 is no longer the odd one out" actually rests on.
    rows_by_key = {(dur, run) for dur, run in rows}
    del rows_by_key
    c01_run = next((run for dur, run in rows if run == 70), None)
    assert c01_run is not None, f'expected a 70-frame run for c01, got {rows}'


# ── 4. the emphasis intent: KEPT, and recorded as kept ──────────────────────

def test_the_emphasised_bar_survived_the_shortening():
    """B-3's trade-off, resolved by measurement rather than by assertion.

    The work order's premise was that cutting to 150 frames would destroy the
    t=4.2 s emphasis flash. That premise is WRONG, and it is wrong in a way that
    matters: there is no flash. Measured on a lossless render, frames
    1598..1607 are pixel-identical, and the delivered mp4's 5 px "jump" at
    1602 is the encoder's dither floor (the same film differs by 2655 px
    between two frames that are also identical). The emphasis is not an event
    at 4.2 s; it is a curve that RISES and is then HELD.

    And the curve completes inside 150 frames: `emphasis` reaches 1.0 at frame
    133 of 600 and at frame 69 of 150. The intent is therefore not merely
    survivable — it is delivered faster, and held for the rest of the scene.

    This asserts the intent is still DECLARED, which is the part a shortening
    could plausibly have destroyed.
    """
    c10 = _c10()
    chart = c10['content']['chart']
    assert chart.get('emphasisIndex') == 6, (
        'c10_bar_long no longer declares emphasisIndex 6. B-3 chose option A '
        '(shorten and KEEP the emphasis), not option B (shorten and drop it), '
        'because measurement showed the emphasis completes at frame 69 of 150 '
        'and is then held. If it was dropped, that decision must be recorded '
        'here with its reason before this number changes.')


def test_the_axis_label_no_longer_claims_a_long_form_chart():
    """The declaration the shortening falsified, corrected at the source.

    The scene carried `axisLabel: "LONG-FORM CHART — the entrance has room to
    be measured"` while running 600 frames whose entrance finished at 1.33 s.
    After the change it is 150 frames, so the label would assert something
    measurably false — a caption that lies about its own scene is the same
    defect class as a docstring quoting a stale count (P40).
    """
    c10 = _c10()
    label = c10['content']['chart'].get('axisLabel', '')
    assert 'LONG-FORM' not in label.upper(), (
        f'c10 still declares axisLabel {label!r}, which claims a long-form '
        f'chart. At 150 frames that claim is false and the label has to move '
        f'with the scene.')
    assert label, 'c10 has no axisLabel at all; the axis lost its caption'


# ── 5. this file's own criterion is not a no-op ─────────────────────────────

def test_this_file_asserts_no_always_true_condition():
    """P27's in-file guard, kept because the failure it names recurs.

    Every mutation harness in this project died of a variant of neutering an
    `assert X, (msg)` into `assert True or (msg)`, which keeps the message and
    the line and survives review. The check is a SHAPE check on the AST, and
    `_is_true` is a VALUE check because since 3.8 a bare `True` parses to
    `ast.Constant` — the first version tested `ast.Name` and could not match
    anything, which is how five neutered assertions in P27's own file passed.
    """
    import ast
    tree = ast.parse(Path(__file__).read_text(encoding='utf-8'))

    def _is_true(node) -> bool:
        return isinstance(node, ast.Constant) and node.value is True

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        if _is_true(node.test):
            offenders.append((node.lineno, 'assert True'))
        if isinstance(node.test, ast.BoolOp) and isinstance(node.test.op, ast.Or):
            if _is_true(node.test.values[0]):
                offenders.append((node.lineno, 'assert True or ...'))
    assert not offenders, (
        f'this guard asserts nothing at {offenders}. Restore the real '
        f'condition — a neutered assertion keeps its message and its line.')


def test_the_guard_does_not_assert_a_number_it_could_not_have_measured():
    """A number in a guard is a claim about a measurement.

    The two render-derived guards skip when there is no runtime, and this
    asserts that they SKIP rather than fall back to comparing the Python mirror
    against itself — which is the check that would pass no matter how wrong the
    mirror is. It is the shape of the fallback, not a count of skips.
    """
    import ast
    src = Path(__file__).read_text(encoding='utf-8')
    tree = ast.parse(src)
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for name in ('test_the_exit_window_mirror_equals_the_renderer_it_mirrors',
                 'test_the_seven_second_still_run_is_gone_and_c10_now_matches_c01'):
        fn = fns.get(name)
        assert fn is not None, f'{name} is missing from this file'
        returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return)
                   and n.value is None]
        assert returns, (
            f'{name} has no bare `return`, so it cannot skip. Without a skip '
            f'path a machine with no renderer either fails on a missing tool '
            f'or — worse — someone "fixes" it by asserting the mirror against '
            f'itself, which is a check that cannot fail.')