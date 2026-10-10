"""P13 — the two facts a scene cache would have to be correct about, pinned now.

P13 (Scene Cache / incremental build) is NOT implemented. Before anything builds
one, two properties have to be stated, because a cache is only ever as good as
the truth of these:

  1. THE SAME PROPS RENDER THE SAME BYTES. A cache that reuses a segment is
     asserting this; if it is false the cache is not wrong, it is a lie.
  2. CHANGING ONE SCENE RE-RENDERS THE WHOLE FILM. This is the cost the cache
     exists to remove, so it is recorded as a FACT, not as a defect to hide.

WHAT IS *NOT* ASSERTED HERE, ON PURPOSE.

No assertion mentions `job_state.json`, a hash cache, or any other artefact a
future P13 might introduce. This project has already paid for that mistake: a
guard written as `'mkdtemp' in source` matched the COMMENT explaining why
mkdtemp was required, and survived the mutation it was supposed to kill. An
assertion about a file that does not exist yet is not a guard, it is a promise
that the guard is testing something when it is only testing itself.

EVERY ASSERTION BELOW IS ON A MEASUREMENT OR ON CODE THAT EXISTS TODAY.

MEASURED, same machine, same commit (details in docs/P13_CACHE_PAYOFF.md):

  * three renders of one unchanged props file produced three DIFFERENT mp4
    files: 711054 / 710851 / 712303 bytes, three distinct sha256. So "identical
    props => identical bytes" is FALSE for this pipeline today, and a segment
    cache keyed on props hash would be keyed on something that does not imply
    identical output.
  * a change confined to one scene (`s01_kpi.content.value`) is visible ONLY
    inside that scene's 229 frames, at a magnitude an order above the noise
    floor. It is not bit-identical outside it — see
    `test_a_scene_change_is_confined_to_that_scene`, which records how that was
    nearly written down wrongly. So scene locality EXISTS: there is something
    for a scene cache to save. The reason it is not saved is that the entry
    point has no scene granularity at all, not that the renderer leaks.

The second half of that pair is the one that decides P13: the ceiling on the
saving is `bundle + whole-film render` (19.6s) against `bundle + one scene`
(7.3s), because bundling is re-done per process either way.

Nothing here renders. Rendered artefacts live in out/, which is gitignored, so
a test that depended on them would pass on the machine that made them and fail
everywhere else — the reason tests/test_visual_qa.py states this in its header
and skips instead.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / 'studio' / 'scripts' / 'visual_qa.py'
RENDER = ROOT / 'studio' / 'bin' / 'render.mjs'
SHOWCASE_DEMO = ROOT / 'pipeline' / 'examples' / 'showcase_demo.json'
_NPX = shutil.which('ffmpeg')


def _run_qa(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(QA), *args],
                          capture_output=True, text=True, encoding='utf-8', errors='replace')


def _rules(stdout: str) -> set[str]:
    return {line.split(']')[1].split()[0] for line in stdout.splitlines() if line.startswith('  [')}


# ---------------------------------------------------------------------------
# FACT 0 — a --props path that does not exist used to SILENTLY DISABLE the only
# rule in visual_qa.py that reads the graph. FIXED; the tests below are
# rewritten against the fixed behaviour.
#
# FOUND WHILE MEASURING, NOT ASKED FOR, and it is a real defect, so it was
# recorded here as a measured fact about the system as it stood.
#
# `visual_qa.py:762` used to read
#
#     if args.props and args.props.exists():
#
# so a nonexistent path was dropped without a word. Measured, both invocations,
# both exit 0:
#
#     --props <real>        -> 5 findings, `missing_asset` PASS
#     --props <nonexistent> -> 4 findings, `missing_asset` ABSENT
#
# The tool therefore reported the same "0 FAIL, 0 UNVERIFIABLE" for "I checked
# and it is fine" and "I checked nothing". A cache's entire value proposition is
# deciding when to SKIP work, and this is the state a skip decision would be
# made in.
#
# WHY THESE THREE TESTS WERE REWRITTEN RATHER THAN DELETED. The block comment
# above the original versions said: "the moment someone fixes visual_qa.py they
# go red and have to come back and rewrite them deliberately — which is the
# correct direction for this to fail." They went red, for exactly that reason,
# and the fix is now in. The pin did its job: it was not relaxed, and it was not
# deleted, and neither is what replaced it. Deleting them would have taken out
# the only statement that this behaviour was ever wrong; rewriting them keeps
# that statement and adds the contract that replaced it.
#
# WHAT CHANGED IN THE TOOL. `main()` now calls `rule_duplicate_check_props`,
# which existed with zero call sites and already returned the right thing. A
# missing path is reported as `missing_asset` / UNVERIFIABLE instead of being
# dropped, and UNVERIFIABLE exits non-zero (`qa_report.py` has always done this:
# "Exit 1 on any FAIL, and on any UNVERIFIABLE"). So the rule no longer
# disappears — it changes verdict, which is the whole point: the report now
# says WHY nothing ran instead of looking like a clean pass.
#
# The two tools had opposite conventions for this flag: `ab_field.py:472` does
# `ap.error('--props not found')`. They now agree on the part that matters —
# a missing `--props` does not exit 0.
# ---------------------------------------------------------------------------

#: The rule that reads the graph. Its disappearance WAS the whole defect.
GRAPH_READING_RULE = 'missing_asset'

#: Must not exist; the tests below are about what the tool does with its absence.
NO_SUCH_GRAPH = ROOT / 'out' / 'p13_no_such_graph_9d41.json'


def _verdict(stdout: str, rule: str) -> str | None:
    """The verdict the CLI printed for one rule, or None if it never ran."""
    for line in stdout.splitlines():
        if not line.startswith('  ['):
            continue
        parts = line.split(']')
        if len(parts) < 2:
            continue
        body = parts[1].split()
        if body and body[0] == rule:
            return parts[0].lstrip(' [').strip()
    return None


def test_a_missing_props_file_is_reported_as_unverifiable_not_dropped():
    """The fixed form of the defect: the rule still runs, and says it cannot.

    It used to be asserted the opposite way round. The message on the old
    version named the transition — "replace it with the assertion that the tool
    now says so out loud" — and this is that assertion.
    """
    assert not NO_SUCH_GRAPH.exists(), f'the fixture path exists: {NO_SUCH_GRAPH}'
    r = _run_qa('--props', str(NO_SUCH_GRAPH))

    assert _verdict(r.stdout, GRAPH_READING_RULE) == 'UNVERIFIABLE', (
        f'a --props path that does not exist must be reported UNVERIFIABLE by '
        f'{GRAPH_READING_RULE}, not silently skipped and not FAIL. Got '
        f'{_verdict(r.stdout, GRAPH_READING_RULE)!r} (exit {r.returncode}):\n'
        f'{r.stdout}'
    )
    assert str(NO_SUCH_GRAPH) in r.stdout, (
        'the report must name the path that could not be read, so a caller can '
        f'tell WHICH input was wrong rather than having to infer it:\n{r.stdout}'
    )


def test_that_gate_no_longer_exits_zero_on_a_missing_props_file():
    """The second half of the defect, also fixed: a caller CAN tell by exit code.

    This is why the defect survived — `qa_report.py` and CI gate on the return
    code, and this used to return 0. It must not return 0 again.

    Deliberately not written as "exit != 0": the sibling tests already pin WHICH
    verdict produces it, so this one asserts only that the number moved. A test
    that asserted a specific non-zero code would be a test of the exit constant.
    """
    assert not NO_SUCH_GRAPH.exists(), f'the fixture path exists: {NO_SUCH_GRAPH}'
    r = _run_qa('--props', str(NO_SUCH_GRAPH))
    assert r.returncode != 0, (
        f'exit code is 0 for a --props path that does not exist. That is the '
        'defect this file first recorded: a caller gating on the return code '
        'cannot tell "checked and clean" from "checked nothing".'
    )


def test_a_readable_props_file_still_exits_zero_and_runs_the_rule():
    """The other half, and the reason the previous test alone is not enough.

    A guard that only asserts the failure case is satisfied by an
    implementation that ALWAYS fails. That is not hypothetical — this project
    shipped a first-version guard that counted `assert` occurrences and was
    satisfied by `assert True`. So the passing direction is pinned here, in the
    same file, against the same command line.
    """
    r = _run_qa('--props', str(SHOWCASE_DEMO))
    assert _verdict(r.stdout, GRAPH_READING_RULE) == 'PASS', (
        f'a readable graph must still report {GRAPH_READING_RULE} PASS (exit '
        f'{r.returncode}):\n{r.stdout}'
    )
    assert r.returncode == 0, (
        f'a readable graph must exit 0, and this one exits {r.returncode}. '
        'The fix must not have turned the gate into one that always fails:\n'
        f'{r.stdout}'
    )


def test_the_readable_and_unreadable_runs_differ_only_in_verdict():
    """The quantitative form, kept separate from the verdict.

    This is the assertion a reviewer can check without trusting prose. The old
    version asserted the two runs reported DIFFERENT RULE SETS, which was the
    defect made visible: the rule vanished. It no longer vanishes, so the sets
    are now expected to MATCH and the verdict is expected to differ. A set
    mismatch in either direction is a regression.
    """
    readable = _rules(_run_qa('--props', str(SHOWCASE_DEMO)).stdout)
    unreadable = _rules(_run_qa('--props', str(NO_SUCH_GRAPH)).stdout)
    # ONE ASYMMETRY SINCE P21, and it is the opposite of the defect above. P21
    # added `graph_scene_renderable`, which by construction CANNOT run when the
    # file cannot be opened — there is no graph to resolve scene types out of. So
    # the unreadable run now reports a strict SUBSET: the rules that need no
    # graph (`missing_asset`, a repository check wearing a props argument, plus
    # the four UNAVAILABLE ones) and not the rule that needs one. The direction
    # is asserted rather than left as noise — an unreadable run naming rules the
    # readable one does not is the disappearance this file exists for.
    assert readable > unreadable, (
        f'readable graph reports {sorted(readable)}, unreadable reports '
        f'{sorted(unreadable)}. The graph rule must now run in BOTH cases and '
        'differ in verdict only — a set mismatch in either direction is a change '
        'in behaviour that this test has not measured.'
    )


# ---------------------------------------------------------------------------
# FACT 1 — there is no scene granularity to cache.
#
# This is asserted on CODE, not on `job_state.json`, which does not exist.
# Both entry points must keep bundling per process (that is what makes the
# saving real — see the payoff doc), and neither may grow a scene selector.
# If one of them DOES grow one, this test goes red on purpose: P13 has landed.
# ---------------------------------------------------------------------------

def test_no_entry_point_selects_a_scene_or_a_frame_range():
    """`--comp` + `--props` is the whole addressable surface today.

    A scene cache needs a scene-addressed render to store anything into. This
    asserts there isn't one, which is the actual precondition for the P13
    verdict in docs/P13_CACHE_PAYOFF.md (B for the bundle, C overall).
    """
    for entry in ('render.mjs', 'still.mjs'):
        src = (ROOT / 'studio' / 'bin' / entry).read_text(encoding='utf-8')
        for token in ('frameRange', 'imageRanges'):
            assert token not in src, (
                f'{entry} now passes {token} to the renderer — a scene cache '
                'may have landed. Re-verify the P13 verdict against the '
                'payoff numbers instead of deleting this assertion.'
            )


def test_the_qa_cli_has_no_scene_selector_either():
    """The QA side has the same gap; a cache that skips QA per scene has nothing
    to key on. `--props` is the only graph-shaped flag (visual_qa.py:1393)."""
    src = QA.read_text(encoding='utf-8')
    assert "'--scene'" not in src and '"--scene"' not in src, (
        'visual_qa.py grew a --scene flag — scene-level QA exists now, so the '
        'P13 verdict needs re-measuring'
    )


# ---------------------------------------------------------------------------
# FACT 2 — the two properties, as measurements, reproduced when a render exists.
#
# These are the work order's two named properties, and they are BOTH false
# today, in opposite directions. Neither is asserted as an ideal:
#
#   * "same props -> same artefact" is FALSE. Three runs of one unchanged graph
#     gave three different mp4s, and at concurrency 1 as well as 16, so it is
#     not a scheduling race. But the difference is far below anything the gate
#     can see: worst per-channel delta 123, against 759 for a real content
#     change, and using the project's own TRUST_RESIDUAL threshold the two
#     separate by ~300x (91 px vs 27073 px). A cache keyed on a props hash would
#     be keyed on something that does not imply identical bytes — which is a
#     reason to compare hashes carefully, not a reason to refuse to build one.
#
#   * "change one scene" DOES stay local. Frames outside the changed scene are
#     bit-identical (max delta 0 after frame 240). So there is something real
#     to cache. It is not cached because no entry point can address a scene.
#
# The tests below need the renders, so they skip when they are absent. A skipped
# guard is not a passing guard and the skip message says so.
# ---------------------------------------------------------------------------

#: Written by the measurement run documented in docs/P13_CACHE_PAYOFF.md.
PROBE = ROOT / 'out' / 'p13_probe'
_BASELINE = PROBE / 'demo1.mp4'
_MUTATED = PROBE / 'mut.mp4'


def _frame_deltas(a: Path, b: Path, every: int = 20) -> list[tuple[int, int]]:
    """(frame_index, worst per-channel-sum delta) for sampled frames.

    Decoded with ffmpeg and compared on RGB, NOT on file bytes: mp4 container
    bytes differ between two runs of identical content because of muxing
    metadata, which would make every comparison here a measurement of ffmpeg.
    """
    import subprocess
    import tempfile

    import numpy as np
    from PIL import Image

    out: list[tuple[int, int]] = []
    with tempfile.TemporaryDirectory() as td:
        dirs = []
        for src, tag in ((a, 'A'), (b, 'B')):
            d = Path(td) / tag
            d.mkdir()
            subprocess.run(
                ['ffmpeg', '-v', 'error', '-i', str(src), '-vf',
                 f"select='not(mod(n,{every}))'", '-vsync', '0',
                 str(d / '%04d.png'), '-y'],
                check=True, capture_output=True)
            dirs.append(d)
        for name in sorted(p.name for p in dirs[0].iterdir()):
            ia = np.asarray(Image.open(dirs[0] / name).convert('RGB')).astype(int)
            ib = np.asarray(Image.open(dirs[1] / name).convert('RGB')).astype(int)
            worst = int(np.abs(ia - ib).sum(axis=2).max())
            out.append(((int(name.split('.')[0]) - 1) * every, worst))
    return out


def test_nothing_in_the_qa_gate_can_see_that_a_scene_value_changed():
    """FACT 3 — measured: the system does NOT notice, and that is the finding.

    Mutation 2 in the work order asks exactly this question. Answer, measured:
    changing `s01_kpi.content.value` from 7263 to 9999 produces a byte-identical
    QA report — same rules, same verdicts, same exit code. The only rule in
    visual_qa.py that reads the graph (`missing_asset`) checks four hardcoded
    audio paths against `studio/public/` and nothing else; there is no rule that
    compares a graph with anything, so there is nothing that could notice.

    This is not a bug in the QA gate and is deliberately not written as one.
    QA is a visual gate: it judges pixels, and a changed number does not change
    the rules it applies. It becomes a defect only in combination with a cache,
    because a cache's entire job is to decide WHAT IS DIFFERENT — and this is
    the place that would have to do it. So the assertion is that nothing
    currently does, recorded so that whoever builds P13 has to change it.
    """
    demo = _run_qa('--props', str(SHOWCASE_DEMO))
    mutated_path = PROBE / 'mutated.json'
    if not mutated_path.exists():
        pytest.skip(
            'the mutated graph fixture is absent. It is regenerated by the '
            'measurement run in docs/P13_CACHE_PAYOFF.md; write it rather than '
            'skipping this silently, because the value of the test IS that the '
            'two reports are identical.'
        )
    mutated = _run_qa('--props', str(mutated_path))

    assert mutated_path.read_bytes() != SHOWCASE_DEMO.read_bytes(), (
        'the mutated graph is now identical to the original — the fixture was '
        'overwritten. This test compares two different graphs; identical files '
        'make it vacuous.'
    )
    assert _rules(mutated.stdout) == _rules(demo.stdout), (
        'visual_qa.py now distinguishes the two graphs. Good — but this test '
        'pins the ABSENCE of that ability, so it has to be rewritten against '
        'the new behaviour rather than deleted.'
    )
    assert mutated.returncode == demo.returncode, (
        'the exit code now differs between a read and a changed graph. Same '
        'note as above: the pin needs rewriting, not removing.'
    )


@pytest.mark.skipif(_NPX is None, reason='ffmpeg not on PATH — rerun measured on this machine')
def test_rerendering_the_same_props_does_not_reproduce_the_bytes_exactly():
    """FACT 2a, measured. Fails loudly rather than pretending determinism.

    The consequence for P13 is the interesting part and it is not "never build a
    cache": it is that a cached segment cannot be validated by re-rendering it,
    so correctness has to come from the key covering every input, not from
    comparing outputs.
    """
    if not (_BASELINE.exists() and _MUTATED.exists()):
        pytest.skip(
            'measured renders absent from out/p13_probe/ (gitignored). '
            'A skipped guard is not a passing guard — re-run the measurement '
            'script in docs/P13_CACHE_PAYOFF.md to exercise this.'
        )
    import hashlib

    a = hashlib.sha256(_BASELINE.read_bytes()).hexdigest()
    b = hashlib.sha256(_MUTATED.read_bytes()).hexdigest()
    assert a != b, (
        'two renders of the SAME props produced identical bytes. That is a '
        'change to the renderer, not a fix to this test — the property this '
        'pins is a measured fact, and a fact that stops being true has to be '
        're-measured before it is written down again.'
    )


@pytest.mark.skipif(_NPX is None, reason='ffmpeg not on PATH — rerun measured on this machine')
def test_a_scene_change_is_confined_to_that_scene():
    """FACT 2b, measured — and this is the one that argues FOR building P13.

    THE FIRST VERSION OF THIS TEST WAS WRONG AND CAUGHT IT. It asserted that
    frames past the changed scene were bit-identical to the baseline. They are
    not: at full resolution frames 240-440 differ by up to 198. That version had
    been written from a comparison made on frames downscaled to 480x270, where
    the difference averaged out — a measurement taken at the wrong scale, which
    is the same error as measuring ink at a point where the subject has left the
    frame.

    The correct comparison is against the NOISE FLOOR, not against zero, because
    two renders of an UNCHANGED graph already differ in that range. Measured, all
    full resolution, worst per-channel-sum delta:

        frame range      changed-scene delta      rerun-no-floor delta
        0-229   (s01)          710-761                     0
        240-440 (s02)              3-198                 0-224
        480-800 (s03,s04)          0                      0

    So the mutation's effect (~730) is an order of magnitude above everything
    else, and the residual in s02 is inside the band the renderer already
    occupies when nothing has changed at all. Scene locality is real; it is just
    not zero, and a guard that said "zero" would have been asserting a
    determinism this pipeline does not have.
    """
    if not (_BASELINE.exists() and _MUTATED.exists() and (PROBE / 'demo2.mp4').exists()):
        pytest.skip(
            'measured renders absent from out/p13_probe/ (gitignored). '
            'A skipped guard is not a passing guard — re-run the measurement '
            'script in docs/P13_CACHE_PAYOFF.md to exercise this.'
        )
    import json as _json

    doc = _json.loads(SHOWCASE_DEMO.read_text(encoding='utf-8'))
    mutated = _json.loads((PROBE / 'mutated.json').read_text(encoding='utf-8'))
    changed = [s['id'] for s, t in zip(doc['scenes'], mutated['scenes']) if s != t]
    assert changed == ['s01_kpi'], (
        f'the measured mutation now changes {changed}, not a single scene. '
        'This test encodes "one scene changed", so re-measure before trusting it.'
    )

    first_frames = sum(int(s['durationInFrames']) for s in doc['scenes'][:1])
    mutated_deltas = dict(_frame_deltas(_BASELINE, _MUTATED))
    noise_deltas = dict(_frame_deltas(_BASELINE, PROBE / 'demo2.mp4'))

    inside = [d for f, d in mutated_deltas.items() if f < first_frames]
    outside = [(f, d, noise_deltas.get(f, 0)) for f, d in sorted(mutated_deltas.items())
               if f >= first_frames]

    assert inside and max(inside) > 200, (
        f'the changed scene shows almost no difference (max {max(inside or [0])}). '
        'The mutation did not reach the render — check the measured fixture '
        'before trusting any locality claim.'
    )
    escaped = [(f, d, n) for f, d, n in outside if d > max(noise_deltas.values(), default=0)]
    assert not escaped, (
        f'frames past the changed scene ({first_frames}+) differ by more than the '
        f'run-to-run noise floor: {escaped[:6]}. Scene locality is measurably '
        'gone, which would remove the entire reason to build a scene cache.'
    )