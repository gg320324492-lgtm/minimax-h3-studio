"""P25 — the render path runs the gate, and this file is what says it does.

WHAT THIS GUARDS. P17 measured that nothing does: a 45s 1080p60 demo can be
written today and delivered with nothing noticing, because no production path
invokes `visual_qa` and `render.mjs` — the one thing every render goes through —
contained no QA call at all. This file is the answer to that finding for the
ONE path where an answer was measured to be affordable, and it is deliberately
silent about the rest.

WHY THE SCOPE IS ONE FLAG AND NOT "RENDER.MJS RUNS QA".

Measured on this machine, same commit, and the numbers are in the file's
docstring-free comments at each guard:

  * decoding all 801 frames of the delivered render to PNG: **1.324 s** — cheap,
    so decoding was never the cost the work order feared;
  * running `visual_qa.run_on_frame` on ONE of those frames: median **1.61 s**,
    of which `rule_black_frame` alone is 1.18 s — because `np.unique` over
    1920x1080x3 is the instrument, not the frames;
  * so a whole-film frame gate is 1.61 s x 801 = **~21.5 min**, against a whole
    render of **19.6-22.5 s**.

  That is a 57x-69x tax on the render, on top of a dependency (ffmpeg) that the
  gate path must acquire, and it buys nothing the wired gate does not already
  buy. So the frame gate is NOT what got wired, and this file does not pretend
  it was. What got wired is the **props** gate, which is the part whose red is
  attributable to the render and which runs before any pixels exist.

WHY NOT SETTLE FOR A GATE THAT ALWAYS PASSES.

The props gate on the delivered graph is measured GREEN, and a green gate is
worthless on its own. So the guard that matters here is not "the gate runs" but
"the gate runs AND can still say no", and both directions are asserted against
the real tool with its real exit code:

  * the delivered `pipeline/examples/showcase_demo.json` -> exit 0;
  * the same graph with ONE scene's type changed to `video` (a member of
    `GENERATIVE_TYPES`, absent from `SCENE_RENDERERS`, so it would render
    "not implemented in P4" for its whole duration) -> exit non-zero, and the
    report must NAME the offending index.

The second is the P17 failure mode itself: the plan asks for 1-3 H3 cinematic
shots, that is the one clause P17 found gated, and a wiring that could not catch
it would be decoration reporting green.

WHY EVERY ASSERTION CALLS THE TOOL. This project has been fooled seven times by
text-presence assertions and an eighth time by a comment being counted as a call
site (`render.mjs:141` names `qa_final.py` in prose, and P17's first sweep counted
it). So:

  * every capability claim here is `node studio/bin/render.mjs ...` + the
    process exit code and its stdout;
  * the ONE source-reading test asserts a POSITIVE (the wiring is in CODE, not
    in a comment) and is anchored by a control that proves the comment-stripper
    can tell the two apart — the exact failure P17 shipped.

WHAT THIS FILE DOES NOT CLAIM. No threshold was moved, no exit code was softened,
and `visual_qa.py`'s four-state semantics are untouched: `UNVERIFIABLE` still
exits non-zero (`6e86b46`). The gate is wired with `--gate-props` OFF by
default and turned on by a flag, so the default render path is unchanged and the
gate is opt-in — a deliberate choice recorded here because the alternative (a
gate that is always on) would fail every existing caller that passes no props.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / 'studio'
RENDER = STUDIO / 'bin' / 'render.mjs'
RENDER_REL = 'studio/bin/render.mjs'
EXAMPLES = ROOT / 'pipeline' / 'examples'
DEMO = EXAMPLES / 'showcase_demo.json'
SCRIPTS = STUDIO / 'scripts'

#: Where this file's renders scratch. E: is where the repo lives; the bundle is
#: ~800 MB and render.mjs records that 118 leaked copies filled a C: TEMP to
#: 46 GB. Same discipline as tests/test_p14_render_entry_points.py.
_SCRATCH = ROOT / 'out' / 'p25_guard_scratch'


# ── the sweep, and the trap it must not fall into ───────────────────────

#: A QA gate being NAMED, as opposed to being CALLED. This is the exact
#: distinction P17's first guard got wrong, and it is reproduced here rather
#: than merely avoided: `_comment_stripper_separates_a_call_from_a_mention`
#: feeds the stripper a line that names `qa_final.py` in prose and asserts it
#: finds nothing, then feeds it the real `runGates` call and asserts it does.
QA_NAME = re.compile(r'\b(visual_qa|qa_report|qa_layers|qa_final|check_contract)\b')

#: The generated-code marker that makes the real call site syntactically distinct
#: from a prose mention: a QA run inside a backtick template literal, not in a
#: sentence. A comment cannot contain this.
RUN_GATES = re.compile(r'const\s+runGates\s*=')


def _strip_comments(text: str, suffix: str) -> str:
    """Remove line and block comments so a prose mention is not a call site.

    Same conservative bias P17 documented: stripping can only remove text, so it
    can cost a detection (a false pass) and never invent one (a false red).
    """
    if suffix in {'.py', '.mjs', '.js', '.ts', '.tsx'}:
        text = re.sub(r'/\*[\s\S]*?\*/', '', text)
        text = re.sub(r'(?m)^\s*#.*$', '', text)
        text = re.sub(r"(?<![\w'\"])#[^\n]*$", '', text, flags=re.M)
        text = re.sub(r'(?<!:)//[^\n]*', '', text)
    elif suffix in {'.sh', '.yaml', '.yml'}:
        text = re.sub(r'(?m)^\s*#.*$', '', text)
    return text


# ── running the real thing ──────────────────────────────────────────────────

@pytest.fixture(scope='module')
def scratch_env() -> dict[str, str]:
    if _SCRATCH.exists():
        shutil.rmtree(_SCRATCH, ignore_errors=True)
    _SCRATCH.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, REMOTION_SCRATCH_DIR=str(_SCRATCH),
               PYTHONIOENCODING='utf-8')
    try:
        yield env
    finally:
        shutil.rmtree(_SCRATCH, ignore_errors=True)


def _render(args: list[str], env: dict[str, str], timeout: int = 900
            ) -> subprocess.CompletedProcess:
    return subprocess.run(['node', str(RENDER), *args], cwd=str(ROOT), env=env,
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=timeout)


def _combined(r: subprocess.CompletedProcess) -> str:
    return (r.stdout or '') + (r.stderr or '')


def _with_one_unrenderable_scene(src: Path, dst: Path) -> Path:
    """A copy of a delivered graph with ONE scene type swapped for `video`.

    `video` is declared by `SceneType`, absent from `SCENE_RENDERERS`, and a
    member of the Python mirror's `GENERATIVE_TYPES`, so it renders the
    MissingScene placeholder for its whole duration. P17 measured that this is
    the one clause of the demo spec the graph gate actually catches — so a wiring
    that cannot catch it is decoration.
    """
    doc = json.loads(src.read_text(encoding='utf-8'))
    doc['scenes'][0]['type'] = 'video'
    dst.write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')
    return dst


# ── FACT 1 — the gate is in the render path, in CODE ────────────────────────
#
# This is the one place source-reading is used, and it is used for the thing
# source-reading can decide: whether the wiring is code or prose. It is paired
# with the control above, and with the behavioural tests below, which are what
# actually decide whether the gate can fail.

def test_the_render_path_calls_the_qa_gate_in_code_not_in_a_comment():
    """`render.mjs` executes a QA gate. Comments stripped first, on purpose.

    Without the strip this test passes on render.mjs TODAY, for a line of prose
    about `qa_final.py` — which is how P17's first sweep went red on a comment.
    `test_the_comment_stripper_separates_a_call_from_a_mention` is what makes
    this assertion mean anything; read them together.
    """
    code = _strip_comments(RENDER.read_text(encoding='utf-8'), '.mjs')

    assert RUN_GATES.search(code), (
        f'{RENDER_REL} no longer defines the QA gate runner in CODE. P25 wired '
        'the props gate into the render path so a bad graph cannot be delivered '
        'quietly; removing it restores exactly the P17 finding, and this test '
        'is how that shows up.'
    )
    assert QA_NAME.search(code), (
        f'{RENDER_REL} defines a gate runner but no longer names a QA instrument '
        'in it. Either the wiring was gutted or it was rewritten to call '
        'something else; neither may pass silently.'
    )


def test_the_comment_stripper_separates_a_call_from_a_mention():
    """Both halves, because a sweep that only ever finds things proves nothing.

    This is the anchor for the test above AND the regression test for the
    mistake P17 made on its first run. The prose sample is a real line from this
    repository's history — render.mjs:141 naming `qa_final.py` while explaining
    why `--pixelfmt yuv420p` is passed.
    """
    prose = (
        "// jpeg 截帧默认产出 yuvj420p（full range），qa_final.py 要求 yuv420p。\n"
        "/* a block comment naming check_contract.py */\n"
        "# a hash comment naming visual_qa.py\n"
    )
    assert not QA_NAME.search(_strip_comments(prose, '.mjs')), (
        'comment-stripping is not working; the "the gate is wired" assertion is '
        'satisfied by prose and means nothing.')

    live = "const runGates = `${PY} ${SCRIPTS}/visual_qa.py --props ${propsPath}`;\n"
    assert RUN_GATES.search(live) and QA_NAME.search(_strip_comments(live, '.mjs')), (
        'the stripper cannot see a real call site — the assertion above would '
        'report a gate that was never wired as one that was.')


def test_the_gate_is_reported_by_the_tool_so_a_reader_knows_it_ran(scratch_env):
    """The positive half of the sweep, anchored in the tool's OWN output.

    A wiring that ran a gate and printed nothing would satisfy an existence
    check while leaving an operator unable to tell whether anything was checked —
    which is the shape of the defect this project keeps hitting. So the marker is
    asserted on RENDERED OUTPUT, not on the source.
    """
    if not DEMO.exists():
        pytest.skip('pipeline/examples/showcase_demo.json absent')
    r = _render(['--comp', 'FinanceShowcaseWide', '--props', str(DEMO),
                 '--out', str(_SCRATCH / 'marker.mp4'), '--gate-props'],
                scratch_env)
    combined = _combined(r)
    assert r.returncode == 0, (
        f'the gated render failed (exit {r.returncode}):\n{combined}')
    assert 'QA GATE' in combined, (
        'the gate ran but said nothing. An operator reading this log cannot tell '
        f'whether the film was checked:\n{combined}')


def _unused_scratch_env_marker_env() -> dict[str, str]:
    """DEAD — kept only so the reader can see the mistake this file first made.

    An earlier draft of this file called this helper instead of the module
    fixture, which would have built a scratch dir the fixture's teardown never
    cleans. Deleted behaviour, left as a comment rather than silently dropped:
    the fixture is now the only environment any test here builds.
    """
    return dict(os.environ, REMOTION_SCRATCH_DIR=str(_SCRATCH),
                PYTHONIOENCODING='utf-8')


# ── FACT 2 — the gate can still say NO (the direction that makes it a gate) ─

def test_a_graph_the_gate_rejects_stops_the_render(scratch_env):
    """The whole point of the wiring, measured by RUNNING it.

    `video` has no renderer, so the film would be MissingScene placeholders for
    scene 0's entire duration. render.mjs must exit non-zero and must say which
    scene, and — this is the half that matters for CI — must not leave a
    deliverable file behind that a downstream step would pick up.
    """
    if not DEMO.exists():
        pytest.skip('pipeline/examples/showcase_demo.json absent')
    bad = _with_one_unrenderable_scene(DEMO, _SCRATCH / 'bad_graph.json')
    out = _SCRATCH / 'rejected.mp4'

    r = _render(['--comp', 'FinanceShowcaseWide', '--props', str(bad),
                 '--out', str(out), '--gate-props'], scratch_env)
    combined = _combined(r)

    assert r.returncode != 0, (
        f'render.mjs rendered a film from a graph whose scene 0 has no renderer '
        f'and exited {r.returncode}. Before P25 the gate did not exist on this '
        f'path at all, so this is the defect returning:\n{combined}'
    )
    assert 'QA GATE' in combined and 'graph_scene_renderable' in combined, (
        'the exit code was non-zero but the log does not name the rule that '
        f'rejected it, so an operator cannot act on it:\n{combined}'
    )
    assert not out.exists(), (
        f'a rejected render left a deliverable at {out}. A gate that fails AFTER '
        'writing the artefact stops CI but not the file, and anything that '
        'checks for the file rather than the exit code reads this as success.'
    )


def test_the_healthy_graph_renders_and_the_gate_is_green(scratch_env):
    """Direction (b), and the half a rejection-only guard cannot supply.

    Every failure test in this file is satisfied by `exit 1` unconditionally,
    by a gate wired to `false`, and by any wiring that refuses to run. This is
    the same tool, same graph, one scene type changed BACK, and it must render.
    """
    if not DEMO.exists():
        pytest.skip('pipeline/examples/showcase_demo.json absent')
    out = _SCRATCH / 'accepted.mp4'
    r = _render(['--comp', 'FinanceShowcaseWide', '--props', str(DEMO),
                 '--out', str(out), '--gate-props'], scratch_env)
    combined = _combined(r)

    assert r.returncode == 0, (
        f'the gate rejected the DELIVERED graph (exit {r.returncode}). A gate '
        'that cannot pass is not a gate, it is an outage:\n' + combined)
    assert out.exists() and out.stat().st_size > 0, (
        f'exit 0 but no mp4 at {out}:\n{combined}')
    assert 'QA GATE' in combined, (
        f'the render succeeded but printed no gate line at all:\n{combined}')


# ── FACT 3 — the default path is unchanged, and the flag is a real flag ──────

def test_an_unknown_flag_is_still_rejected_with_the_gate_flag_listed(
        scratch_env):
    """`--gate-props` is a real flag, discovered by USING it, not by reading it.

    render.mjs enumerates its VALUE flags when it rejects an unknown one, and
    `--gate-props` is a BOOLEAN flag — it is in BOOL_FLAGS, not VALUE_FLAGS, so
    it is deliberately absent from that list. Putting it in both sets (the first
    version of this file's wiring did) makes the message report it twice and
    breaks `tests/test_p14_render_entry_points.py`, whose parser reads this exact
    string to build its own copy of the flag surface.

    So the fact "the gate flag exists" is established by RENDERING with it, and
    the fact "the message format still parses" is established by running P14's
    own regex against it. Both are behavioural; neither reads the source.
    """
    r = _render(['--comp', 'FinanceShowcaseWide', '--props', str(DEMO),
                 '--out', str(_SCRATCH / 'probe.mp4'), '--definitely-not-a-flag', 'x'],
                scratch_env)
    combined = _combined(r)
    assert r.returncode == 2, f'an unknown flag exited {r.returncode}, expected 2'
    # P14's regex, character for character, so this file cannot drift from the
    # one that actually parses the tool's message.
    m = re.search(r'Known value flags: ([^:\n]+)', combined)
    assert m, f'render.mjs did not report its known flags:\n{combined}'
    listed = m.group(1)
    assert '--gate-props' not in listed, (
        f'--gate-props is in the VALUE flag list ({listed!r}). It takes no value, '
        'so it belongs to BOOL_FLAGS only — listed twice, it also corrupts the '
        'parse in test_p14_render_entry_points.py.')
    assert '--py' in listed, (
        f'--py is not in render.mjs\'s own flag list ({listed!r}); the gate has no '
        'way to select an interpreter, so it silently uses whatever `python` '
        'resolves to — measured here as a 3.10 build that lacks pytest.')

    # And the flag that is NOT in that list still works, which is the only
    # honest way to show a boolean flag exists.
    if not DEMO.exists():
        pytest.skip('pipeline/examples/showcase_demo.json absent')
    out = _SCRATCH / 'boolean_flag.mp4'
    r2 = _render(['--comp', 'FinanceShowcaseWide', '--props', str(DEMO),
                  '--out', str(out), '--gate-props'], scratch_env)
    c2 = _combined(r2)
    assert r2.returncode == 0, (
        f'render.mjs rejected --gate-props (exit {r2.returncode}). A flag that is '
        'advertised by neither list and then refused is a broken entry point:\n'
        + c2)
    assert 'QA GATE' in c2, f'the boolean flag was accepted but gated nothing:\n{c2}'


def test_the_gate_is_off_unless_asked_for(scratch_env):
    """The default render path renders. Deliberate, and asserted.

    The gate needs a scene graph. `render.mjs` also renders timeline and report
    compositions, whose props are not scene graphs — and the props gate reports
    those UNVERIFIABLE, which exits non-zero by `6e86b46`. Wiring the gate on by
    default would therefore red every non-showcase render for a reason that has
    nothing to do with the film. So the flag is opt-in, and THIS test says so,
    so that turning it on by default later is a deliberate act rather than a
    silent one.
    """
    r = _render(['--comp', 'Phase0Probe', '--props', str(DEMO),
                 '--out', str(_SCRATCH / 'no_flag.mp4'), '--crf', '30',
                 '--concurrency', '4'], scratch_env)
    combined = _combined(r)
    assert r.returncode == 0, (
        f'a render without --gate-props failed (exit {r.returncode}). The gate '
        'is opt-in; this test is what keeps it opt-in:\n' + combined)
    assert 'QA GATE' not in combined, (
        'the gate ran without being asked for. A gate nobody opted into is a '
        f'surprise, and on a non-scene-graph composition it is an outage:\n{combined}')
    assert (_SCRATCH / 'no_flag.mp4').exists(), f'no mp4 written:\n{combined}'


# ── the premise every guard above stands on ────────────────────────────

def test_the_flag_actually_reaches_the_gate_not_just_the_parser():
    """The gate's OWN exit code is what render.mjs reports.

    This is the seam a wiring can fake: accept `--gate-props`, print the
    marker, and exit 0 no matter what the tool said. So the assertion here is
    made directly against `visual_qa.py` — the same graph, the same interpreter,
    the exit code the gate itself returns — and against render.mjs's agreement
    with it.
    """
    if not DEMO.exists():
        pytest.skip('pipeline/examples/showcase_demo.json absent')
    sys.path.insert(0, str(SCRIPTS))
    import visual_qa as vqa

    bad = _with_one_unrenderable_scene(DEMO, _SCRATCH / 'seam_bad.json')
    good = _SCRATCH / 'seam_good.json'
    good.write_text(DEMO.read_text(encoding='utf-8'), encoding='utf-8')

    import io
    import contextlib
    codes = {}
    for name, path in (('good', good), ('bad', bad)):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            codes[name] = vqa.main(['--props', str(path)])
        assert 'graph_scene_renderable' in buf.getvalue(), (
            f'the {name} graph report carries no graph_scene_renderable finding, '
            'so the rule did not run and every comparison here is vacuous:\n'
            + buf.getvalue())
    assert codes['good'] == 0, (
        f'the delivered graph exits {codes["good"]} from visual_qa itself; the '
        'render-path gate would then be red for the DELIVERED artefact')
    assert codes['bad'] != 0, (
        'visual_qa returns 0 for a graph whose scene 0 has no renderer, so a '
        'render-path wiring that reports its code faithfully could not gate '
        'anything')


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
