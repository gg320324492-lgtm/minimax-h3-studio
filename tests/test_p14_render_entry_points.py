"""P14 — guards on the render entry points, pinning what they do TODAY.

P14 measured what a long-lived render worker would cost before deciding whether
to build one (docs/P14_WORKER_PAYOFF.md). The verdict is that it is not worth
building, but that verdict is only as good as the facts under it, and a verdict
about what the system CANNOT do needs a pin: otherwise "the render paths were
changed" turns a documented decision into a mystery.

These guards therefore pin two things that are true right now and that any
render-worker work would have to change deliberately:

  1. There is no scene-level and no frame-range render entry point. The only
     addressable surface is `--comp` + `--props`. This is the fact P13 and P14
     both rest their verdicts on.
  2. `still.mjs` is a real, working single-frame entry point — and it REJECTS an
     out-of-range frame instead of silently writing a blank or clamped picture.

WHY THESE ARE NOT ASSERTED AS "A FILE DOES NOT EXIST". This project has paid for
that mistake: a guard written as `'mkdtemp' in source` matched the COMMENT that
explains why mkdtemp is required, and survived the mutation it was written to
kill. Every assertion here is on something observable:

  * the flags are exercised by RUNNING the entry point and reading its exit code
    and its output;
  * the absence of scene granularity is established by RUNNING the tool and
    observing that an unknown flag is rejected with a list of the flags that
    exist — the tool's own statement of its addressable surface, which is a
    stronger fact than a string search.

WHAT IS *NOT* PINNED HERE, ON PURPOSE.

Nothing here asserts that `render.mjs` calls `bundle()` once per process, nor
that its scratch directory is removed afterwards. That behaviour is real and is
covered by tests/test_render_bundle_cleanup.py. Repeating it would create a
second place to update for one fact.

Nothing here asserts anything about a render worker, because no render worker
exists. A guard written against a future artefact is a promise that the guard is
testing something when it is testing itself.

MEASURED on this machine, same commit (details in docs/P14_WORKER_PAYOFF.md):
node v24.16.0, remotion 4.0.529, scratch pinned to E: via
REMOTION_SCRATCH_DIR so no render in this file can add to the 118 leaked bundles
recorded at studio/bin/render.mjs:43-47.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / 'studio'
RENDER = STUDIO / 'bin' / 'render.mjs'
STILL = STUDIO / 'bin' / 'still.mjs'
PROPS = ROOT / 'pipeline' / 'examples' / 'showcase_demo.json'

#: E: is where the repo lives. The bundle is ~800 MB; render.mjs:43-47 records
#: that 118 leaked copies filled a C: TEMP to 46 GB. Every render this file runs
#: gets its scratch here, and the scratch root is a fresh temp dir under E:.
_SCRATCH = ROOT / 'out' / 'p14_guard_scratch'


@pytest.fixture(scope='module')
def scratch_env() -> dict[str, str]:
    """A per-module scratch root on the repo's drive, emptied afterwards.

    Scoped to the module so the renders below share one place, and removed on
    teardown even when an assertion fails, because a guard that leaks 800 MB on
    failure is a guard that can fill a disk.
    """
    if _SCRATCH.exists():
        shutil.rmtree(_SCRATCH, ignore_errors=True)
    _SCRATCH.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, REMOTION_SCRATCH_DIR=str(_SCRATCH))
    try:
        yield env
    finally:
        shutil.rmtree(_SCRATCH, ignore_errors=True)


def _node(entry: Path, args: list[str], env: dict[str, str],
          cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(['node', str(entry), *args], cwd=str(cwd), env=env,
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=900)


# ---------------------------------------------------------------------------
# FACT 1 — the addressable surface is `--comp` + `--props`, and nothing finer.
#
# Proved by making each tool state its own flags, not by grepping its source.
# still.mjs prints the complete list of known flags when it meets one it does
# not know, and rejects the unknown one. So a run asking for `--scene` returns
# exit 2 AND an error naming every flag that does exist. If either tool ever
# gains scene granularity, the surface changes and this test goes red — which is
# the signal to re-measure the P13/P14 verdicts, not to delete the assertion.
# ---------------------------------------------------------------------------

def _unknown_flag_error(result: subprocess.CompletedProcess) -> str:
    return result.stdout + result.stderr


#: Placeholder swapped for an absolute path before the command runs. render.mjs
#: does NOT reject unknown flags, so a relative --out would drop a ~700 KB mp4
#: into the repository root — which is exactly what this file did the first time
#: it ran, before the fixture was noticed and removed.
ABS_OUT = '<abs-out>'


@pytest.mark.parametrize('entry_name,required', [
    ('still.mjs', ['--comp', 'Phase0Probe', '--props', str(PROPS),
                   '--out', 'probe.png', '--frames', '1']),
    ('render.mjs', ['--comp', 'Phase0Probe', '--props', str(PROPS),
                    '--out', ABS_OUT]),
])
def test_a_scene_selector_does_not_exist_on_any_entry_point(
        entry_name: str, required: list[str], scratch_env: dict[str, str]) -> None:
    """Neither entry point can address a scene or a frame range. Measured.

    This is the precondition both verdicts stand on. docs/P13_CACHE_PAYOFF.md:
    "there is no scene-level entry point to address". docs/P14_WORKER_PAYOFF.md:
    a worker cannot make a per-scene render cheaper without one.

    The work order warns specifically against `assert 'frameRange' not in src`:
    a string search for a token that appears in a comment matches the comment.
    Here the tool itself enumerates its flags, so the assertion is on what the
    tool accepts, not on what its source happens to spell.

    THE TWO ENTRY POINTS DISAGREE ABOUT UNKNOWN FLAGS, and that difference is
    the finding rather than an inconvenience. still.mjs rejects one (exit 2) —
    it was fixed after `--frames` where `--frame` was meant fell through to a
    default and silently selected a different frame. render.mjs has no such
    check: it ignores `--scene`, renders the entire film, and exits 0. Both
    outcomes are recorded, because both mean the same thing for this work
    order — a `--scene` cannot be addressed anywhere — and only one of them
    tells the operator so.
    """
    args = [str(_SCRATCH / 'scene_probe.mp4') if a == ABS_OUT else a for a in required]
    entry = STUDIO / 'bin' / entry_name
    r = _node(entry, [*args, '--scene', 's01_kpi'], scratch_env, ROOT)
    combined = _unknown_flag_error(r)

    if entry_name == 'still.mjs':
        assert r.returncode == 2, (
            f'still.mjs accepted --scene and exited {r.returncode}, expected 2. '
            'Scene-level rendering may have landed; re-measure the P13/P14 '
            f'verdicts instead of deleting this assertion.\n{combined}'
        )
        assert '--scene' in combined and 'Unknown flag' in combined, (
            'still.mjs exited 2 but did not say which flag it rejected. The exit '
            'code alone would not tell a reader that scene granularity is '
            f'absent; the message is what carries the fact.\n{combined}'
        )
    else:
        # render.mjs ignores it and still renders. The point of the assertion is
        # that the result is NOT a scene render: the whole film is rendered,
        # because 150 frames of Phase0Probe come out the other end.
        assert r.returncode == 0, (
            'render.mjs no longer ignores --scene; it now does something with it '
            f'(exit {r.returncode}). Whatever it now does is scene granularity '
            f'and the P13/P14 verdicts need re-measuring.\n{combined}'
        )
        assert '150f' in combined, (
            'render.mjs ignored --scene but did not render the whole '
            f'composition (no "150f" in the output). Something is now narrowing '
            f'the render, which is exactly the granularity P13 wanted.\n{combined}'
        )


def test_render_mjs_silently_ignores_a_flag_it_does_not_understand(
        scratch_env: dict[str, str]) -> None:
    """Measured fact, recorded as a defect: the two entry points disagree.

    still.mjs rejects an unknown flag with exit 2 and a message naming the
    flags it does accept. render.mjs parses with a `get(key, fallback)` helper
    that never checks for leftovers, so ANY unknown flag is dropped: a typo,
    a flag meant for another tool, or a flag a caller believes is working all
    pass silently and the render proceeds.

    This is the same class of defect still.mjs's own comment describes —
    "`--frames` where `--frame` was meant fell through to a default" — and it
    was fixed in one tool and not the other. It is recorded here rather than
    fixed, because this work order authorises guards and not behaviour changes.

    It is also the exact failure mode a future render worker would have to
    inherit: a flag typo that silently renders the whole film instead of one
    scene looks like success, and nothing downstream compares frames.
    """
    out = _SCRATCH / 'unknown_flag.mp4'
    r = _node(RENDER, ['--comp', 'Phase0Probe', '--props', str(PROPS),
                       '--out', str(out), '--frames', '10'],
              scratch_env, ROOT)
    combined = _unknown_flag_error(r)

    assert r.returncode == 0, (
        'render.mjs now rejects an unknown flag. That is a fix, not a '
        'regression — but this test pins the ABSENCE of that fix, so it has to '
        f'be rewritten deliberately rather than deleted.\n{combined}'
    )
    assert out.exists(), (
        'render.mjs did not render at all with an unknown flag present, so this '
        'test is no longer measuring what it claims. Check the flags before '
        f'trusting it.\n{combined}'
    )
    assert '150f' in combined, (
        '--frames 10 was passed to render.mjs and it rendered something other '
        'than the full 150 frames, which would mean the flag is no longer '
        f'ignored.\n{combined}'
    )
    assert 'Unknown flag' not in combined, (
        'render.mjs printed an unknown-flag error; it has gained the check '
        f'still.mjs already had.\n{combined}'
    )


def test_the_rejected_flag_list_shows_scene_and_frame_range_are_absent(
        scratch_env: dict[str, str]) -> None:
    """The positive half, so the test above cannot be satisfied by always-fail.

    A guard that only asserts a failure passes against a tool broken in every
    other way. This project has shipped a guard satisfied by `assert True`, so
    the working direction is pinned too, against the same command line.

    still.mjs prints its known value flags when it rejects an unknown one. That
    list is a statement by the tool about what it can do, and neither
    frameRange nor imageRanges appears in it.
    """
    r = _node(STILL, ['--comp', 'Phase0Probe', '--props', str(PROPS),
                      '--out', 'probe.png', '--frames', '1', '--scene', 'x'],
              scratch_env, ROOT)
    combined = _unknown_flag_error(r)
    m = re.search(r'Known value flags: ([^;]+);', combined)

    assert m, f'still.mjs did not print its known value flags:\n{combined}'
    known = m.group(1)
    assert '--frames' in known, (
        f'--frames should be in the list still.mjs reports it accepts; got {known!r}. '
        'If this fails, the tool changed its flag surface and this file is stale.'
    )
    for token in ('frameRange', 'imageRanges', 'scene'):
        assert token not in known, (
            f'{token} now appears in the flags still.mjs accepts ({known!r}). '
            'Scene or frame-range rendering may have landed — re-measure before '
            'trusting the P13/P14 verdicts.'
        )


# ---------------------------------------------------------------------------
# FACT 2 — an illegal `--comp` fails loudly and writes nothing.
#
# render.mjs has no client-side validation of --comp: the failure comes from the
# bundler, and it is a real failure — exit 1, no output file. Pinning it matters
# because a worker would move this check into its own process, where "the
# composition id does not exist" has to keep being fatal. A worker that logged
# and continued would render nothing and report success, which is the same
# silent-pass shape the QA gate had.
# ---------------------------------------------------------------------------

def test_an_unknown_comp_exits_nonzero_and_writes_no_output_file(
        scratch_env: dict[str, str]) -> None:
    """Measured: exit 1, and the .mp4 is never created.

    The output file is the load-bearing half. A render that failed but left a
    plausible-looking file behind would satisfy any check that only looks for
    the artefact.
    """
    out = _SCRATCH / 'never_written.mp4'
    assert not out.exists(), f'the fixture path already exists: {out}'

    r = _node(RENDER, ['--comp', 'NoSuchComposition_9f31',
                       '--props', str(PROPS), '--out', str(out)],
              scratch_env, ROOT)
    combined = _unknown_flag_error(r)

    assert r.returncode != 0, (
        f'an unknown --comp exited 0 (exit {r.returncode}). A caller gating on '
        'the return code cannot tell "rendered" from "composition does not '
        f'exist":\n{combined}'
    )
    assert not out.exists(), (
        f'a failed render left an output file behind at {out}. Anything that '
        'checks for the artefact rather than the exit code would read this as '
        f'a successful render.\n{combined}'
    )
    assert 'NoSuchComposition_9f31' in combined, (
        'the error must name the composition that was asked for, so a caller '
        f'can tell a typo from a missing template:\n{combined}'
    )


# ---------------------------------------------------------------------------
# FACT 3 — still.mjs works, and it refuses an out-of-range frame.
#
# This is the entry point any incremental scheme would lean on, so both halves
# are pinned: that a valid frame renders, and that an invalid one is fatal
# rather than silently clamped. The second is the one that matters — a silent
# clamp writes a real PNG of the wrong picture, and P13 measured that nothing
# in this pipeline can notice a wrong picture (a changed scene value produces a
# byte-identical QA report).
# ---------------------------------------------------------------------------

def test_a_valid_single_frame_render_still_works(scratch_env: dict[str, str]) -> None:
    """The passing direction. Phase0Probe is 150 frames; frame 10 is real."""
    out = _SCRATCH / 'valid_frame.png'
    r = _node(STILL, ['--comp', 'Phase0Probe', '--props', str(PROPS),
                      '--out', str(out), '--frames', '10'],
              scratch_env, ROOT)
    combined = _unknown_flag_error(r)

    assert r.returncode == 0, (
        f'still.mjs failed on a valid frame (exit {r.returncode}). If the '
        'single-frame entry point is broken, the out-of-range guard below is '
        f'no longer testing anything real:\n{combined}'
    )
    assert out.exists() and out.stat().st_size > 0, (
        f'still.mjs exited 0 but wrote no PNG at {out}:\n{combined}'
    )


def test_an_out_of_range_frame_is_refused_not_clamped(
        scratch_env: dict[str, str]) -> None:
    """Measured: RangeError, exit 1, no PNG written.

    Phase0Probe declares durationInFrames=150, so frame 9999 is out of range
    by a margin no clamping argument could explain. The assertion is on the
    refusal, not on the wording — but it also requires that nothing was written,
    because the dangerous version of this failure is a successful exit that
    leaves a plausible picture on disk.
    """
    out = _SCRATCH / 'out_of_range.png'
    r = _node(STILL, ['--comp', 'Phase0Probe', '--props', str(PROPS),
                      '--out', str(out), '--frames', '9999'],
              scratch_env, ROOT)
    combined = _unknown_flag_error(r)

    assert r.returncode != 0, (
        f'an out-of-range frame exited 0 (exit {r.returncode}). A silent clamp '
        'writes a real image of the wrong frame, and this pipeline has no gate '
        'that could notice — see '
        'tests/test_p13_scene_cache_facts.py, where a changed scene value '
        f'produces a byte-identical QA report.\n{combined}'
    )
    assert not out.exists(), (
        f'an out-of-range frame still wrote {out}. A clamped frame is worse '
        'than a failure: it is a wrong picture that looks right.\n{combined}'
    )
    assert 'RangeError' in combined, (
        'the refusal should name the range it refused, so an operator can see '
        f'it was a bounds error and not a crash:\n{combined}'
    )


# ---------------------------------------------------------------------------
# FACT 4 — the scratch directory a render leaves behind is gone afterwards.
#
# This is the property that makes any future long-lived worker dangerous, and it
# is asserted here because it is the one that must not silently change: the
# per-render bundle directory is REMOVED. render.mjs:43-47 records why — 118
# leaked copies filled a C: TEMP to 46 GB. A worker holds exactly one of these
# permanently, which is the cost P14 measured; this test is what stops that
# change from arriving as a side effect.
# ---------------------------------------------------------------------------

def test_a_finished_render_leaves_no_bundle_directory_behind(
        scratch_env: dict[str, str]) -> None:
    """After a successful render the scratch root holds no bundle directory.

    Asserted on the filesystem, not on the source. `test_render_bundle_cleanup.py`
    already covers the source-level contract; this one is about what is true on
    disk after a real render on this machine, which is the claim the 46 GB
    incident is really about.
    """
    out = _SCRATCH / 'cleanup_probe.mp4'
    r = _node(RENDER, ['--comp', 'Phase0Probe', '--props', str(PROPS),
                       '--out', str(out), '--crf', '30', '--concurrency', '4'],
              scratch_env, ROOT)
    combined = _unknown_flag_error(r)
    assert r.returncode == 0, (
        f'the probe render failed (exit {r.returncode}); nothing was learned '
        f'about cleanup:\n{combined}'
    )

    leftover = [p.name for p in _SCRATCH.iterdir() if p.is_dir() and p.name.startswith('render-')]
    assert not leftover, (
        f'the render left bundle directories behind: {leftover}. Every render '
        'leaking one 800 MB copy is how 118 of them filled a C: TEMP to 46 GB '
        '(render.mjs:43-47). A long-lived worker would make this permanent, so '
        'it must be red before that change, not after.'
    )
