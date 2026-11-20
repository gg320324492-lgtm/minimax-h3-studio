"""The beat grid must be derivable from the audio, and the graph's tempo must
match it (P9.1 guards).

`studio/public/audio/bgm_beats.json` holds 208 beats detected from the real track
(`source: mixtrack_Digital_Clouds.mp3`). It was committed, described itself as
"for the renderer", and had zero readers — while both example graphs declared
`bpm: 126` against a measured 129.00. That is not a rounding disagreement: 126
against 129 compounds to 11.8 ms at beat 1 and 2453 ms at beat 208, so anything
bound to the grid is bound to the wrong tempo and the error grows with how far in
you look — which is why it survives every short test.

So the guards are about the DECLARATION disagreeing with the MEASUREMENT, not
about a grid rendering correctly. A grid built from a wrong number renders
perfectly and is still wrong, and that is the whole failure.

Each check here is expected to be able to fail; the mutation record in the commit
that added this file shows the load-bearing one going red when the declared bpm is
reverted.

Where node is unavailable the behavioural test SKIPS rather than fails — the same
call `test_perspective_math.py` makes, for the same reason: a geometry check must
not be the reason the suite is red on a machine that cannot run it.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase'
BEAT = TEMPLATE / 'beat'
MODULE = BEAT / 'beatGrid.ts'
CHECK = BEAT / 'beatGrid.check.ts'
SNAP_MODULE = BEAT / 'beatSnap.ts'
SNAP_CHECK = BEAT / 'beatSnap.check.ts'
ANALYSIS = ROOT / 'studio' / 'public' / 'audio' / 'bgm_beats.json'
EXAMPLES = ROOT / 'pipeline' / 'examples'

_NPX = shutil.which('npx') or shutil.which('npx.cmd')


def _code_only(path: Path) -> str:
    """The file with block and line comments removed.

    Needed because the guards here are textual, and this repo explains itself in
    comments that quote the very constructs the guards forbid. A source guard that
    cannot distinguish a prohibition from a use of the thing is a guard that has
    to be weakened until it is useless.
    """
    import re

    text = path.read_text(encoding='utf-8')
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    text = re.sub(r'^\s*//.*$', '', text, flags=re.MULTILINE)
    return text


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
def test_beat_grid_check_passes():
    """The whole check, run for real.

    Red as of the commit that introduced it: both example graphs declare 126 bpm
    against a fitted 128.998, off by 3.00. Fixing the two numbers turns it green;
    that is the intended order of operations, guard first.
    """
    proc = subprocess.run(
        [_NPX, 'tsx', str(CHECK)],
        cwd=ROOT / 'studio',
        capture_output=True,
        text=True,
        timeout=300,
        # utf-8, not the gbk locale default: see test_chart_math's note —
        # locale-decoded capture eats the message exactly when it is needed
        encoding='utf-8',
        errors='replace',
    )
    assert proc.returncode == 0, f'beat grid check failed:\n{proc.stdout}\n{proc.stderr}'


def test_the_module_is_measurable_without_a_renderer():
    """beatGrid.ts must stay free of react and remotion, and of the filesystem.

    Not a style rule. The tempo disagreement is a property of arithmetic over
    numbers that came out of an audio file; if reaching `fitBpm` required a
    component tree or a bundled entry point, the fit could only be checked by
    rendering a frame and reading pixels, and nobody would do that on a change
    to one number. It is the reason the declared bpm survived this long.
    """
    src = MODULE.read_text(encoding='utf-8')
    for forbidden in ("from 'react'", 'from "react"', "from 'remotion'", 'from "remotion"'):
        assert forbidden not in src, f'beatGrid.ts imports {forbidden} — it cannot be measured'
    for forbidden in ("from 'node:fs'", "from 'node:fs'", 'require(', 'readFileSync'):
        assert forbidden not in src, (
            'beatGrid.ts must be pure — reading files belongs to the check, so the '
            'module stays importable by anything'
        )


def test_accent_cannot_be_derived_from_the_beat_index():
    """The `i % 4` shortcut must stay impossible to reintroduce silently.

    Measured on this track, accent is NOT on a 4-beat modulus: the 12 loudest
    beats sit at indices 2, 20, 22, 56, 58, 82, 84, 89, 96, 98, 114, 115, covering
    all four residues, with gaps from 1 to 34 beats. A permutation test over the
    detected bass values finds no index modulus that predicts loudness at all —
    observed spread 0.032 at mod 4 against a shuffled-null 95th percentile of
    0.070 — so an `i % 4` accent would look plausible and land on the wrong beats.

    Two guards, because one is not enough: the source may not mention a modulus at
    all, and the check must assert the accent set is not the index set.
    """
    src = _code_only(MODULE)
    for modulus in ('% 4', '% 2', '%4', '%2'):
        assert modulus not in src, (
            f'beatGrid.ts mentions `{modulus}` in executable code — accent must come '
            f'from the measured bass values, never from a beat index. (Prose is '
            f'excluded deliberately: the module documents why `i % 4` is wrong, and a '
            f'guard that cannot tell that from a shortcut protects nothing.)'
        )
    check_src = CHECK.read_text(encoding='utf-8')
    # The assertion is emitted from a loop over the moduli, so the source carries
    # the template, not the rendered strings. Matching on the rendered text would
    # pass against a check that no longer asserts anything.
    assert 'is NOT the i%${mod} set' in check_src, (
        'the check must keep asserting that accent is not the i%N set — that '
        'assertion is the one a later reader is most likely to delete as redundant'
    )
    assert 'for (const mod of [2, 4])' in check_src, (
        'the accent guard must cover both a 2-beat and a 4-beat modulus; checking '
        'only one leaves the other available as a shortcut'
    )
    assert 'ACCENT_SHARE' in check_src, 'the check should verify the accent is the top slice'


def test_the_check_cannot_lose_its_load_bearing_assertions():
    """The bpm agreement assertion is the guard; it must not be deletable quietly.

    It is red on purpose today. Anyone arriving later sees a red test whose fix is
    "edit one number", and the tempting resolution is to delete the assertion or
    widen the tolerance. These assertions make both of those show up as a diff.
    """
    src = CHECK.read_text(encoding='utf-8')
    required = [
        'RMS residual is within 25 ms',
        'max residual is within 40 ms',
        'advances by exactly one step',
        'is NOT the i%${mod} set',
        'declares a bpm within 0.5 of the fitted',
        'is renderable on an integer frame grid',
    ]
    missing = [r for r in required if r not in src]
    assert not missing, f'the check is missing assertion(s): {missing}'


def test_tolerance_is_not_widened_without_a_reason():
    """0.5 bpm is the tolerance. Widening it is a decision, not a cleanup.

    0.5 bpm over this track's 208 beats is 150 ms, so the tolerance is already
    generous relative to the 18 ms fit residual. It exists to absorb the
    difference between the fitted tempo and a hand-typed one, not to accommodate a
    disagreement.
    """
    src = CHECK.read_text(encoding='utf-8')
    assert 'bpmTolerance: 0.5' in src, 'the bpm tolerance must stay 0.5'
    assert 'bpmTolerance: 1' not in src and 'bpmTolerance: 2' not in src, (
        'the bpm tolerance has been widened — 150 ms per 208 beats is the cost of 0.5, '
        'and widening it to pass a wrong number re-creates the defect'
    )


def test_the_analysis_asset_is_still_the_one_being_measured():
    """The guard reads a committed file. If that file goes, the guard is theatre.

    `bgm_beats.json` is the only reason any of this is checkable, and it is also
    the asset that had zero readers. So its presence and its internal consistency
    are themselves under test: the beats it claims must fit the interval it
    claims, or the file is lying in a second way.
    """
    import json

    assert ANALYSIS.exists(), 'bgm_beats.json is missing — the beat guard has no input'
    doc = json.loads(ANALYSIS.read_text(encoding='utf-8'))
    assert len(doc['beats']) >= 64, f"only {len(doc['beats'])} beats — too few to fit"
    times = [b['t'] for b in doc['beats']]
    assert all(b > a for a, b in zip(times, times[1:])), 'beat times are not increasing'
    assert 'bass' in doc['beats'][0], (
        'no bass energy in the analysis — accent would have nothing to select on'
    )


def test_both_example_graphs_declare_a_bpm():
    """Both graphs must carry the field the guard reads.

    The check falls back to 126 when `bpm` is absent, which is exactly how a graph
    can be silently wrong: `report-demo`'s props has no `bpm` at all and inherits
    the schema default, and that default is the wrong tempo. So absence has to be
    visible here rather than resolved by a fallback somewhere downstream.
    """
    for name in ('showcase_demo.json', 'charts_demo.json'):
        import json

        doc = json.loads((EXAMPLES / name).read_text(encoding='utf-8'))
        assert isinstance(doc.get('bpm'), (int, float)), (
            f'{name} has no numeric bpm; the graph would silently inherit the '
            f'schema default, which is the tempo this guard exists to catch'
        )


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
def test_beat_snap_report_check_passes():
    """`beat_snap` stays off, and what turning it on would do stays pinned.

    The render path resolves with `false`, so this branch has never run in a
    delivered film and nobody can say what it does. `beatSnap.check.ts` measures
    it and pins the numbers — and pins the fact that it is LOSSY, because
    `resolveScenes` quantises each scene to a whole number of beats and discards
    the fraction. Run it here rather than leaving it as a file someone has to know
    to execute.
    """
    proc = subprocess.run(
        [_NPX, 'tsx', str(SNAP_CHECK)],
        cwd=ROOT / 'studio',
        capture_output=True,
        text=True,
        timeout=300,
        encoding='utf-8',
        errors='replace',
    )
    assert proc.returncode == 0, f'beat_snap check failed:\n{proc.stdout}\n{proc.stderr}'


def test_the_beat_snap_report_cannot_be_silently_repurposed():
    """The report must stay a report, and the render path must stay on `false`.

    The tempting future edit is to flip `resolveScenes(doc, false)` to `true`
    because the beat maths finally works. That would shorten `showcase_demo` by 20
    frames and `charts_demo` by 108, and shift the last chart scene 94 frames
    earlier — so the guard asserts the shipped call site as source text, which
    turns "someone flipped it" into a diff rather than a re-render nobody diffs.
    """
    src = (TEMPLATE / 'FinanceShowcaseWide.tsx').read_text(encoding='utf-8')
    call = [ln.strip() for ln in src.splitlines() if 'resolveScenes(' in ln]
    assert call, 'the render path no longer calls resolveScenes at all'
    assert any('doc, false' in c for c in call), (
        f'beat_snap is now enabled on the render path: {call}. That is a decision '
        f'about delivered frames, not a cleanup — see beatSnap.check.ts for the '
        f'cost (-20 frames on showcase_demo, -108 on charts_demo).'
    )
    check_src = SNAP_CHECK.read_text(encoding='utf-8')
    assert 'beat_snap is LOSSY' in check_src, (
        'the snap report must keep asserting that beat_snap loses frames — it is '
        'the reason the branch is off, and the first thing a reader will assume'
    )
