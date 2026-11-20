"""The perspective maths is checked where it lives, not in a Python copy (P6.2).

P6.2 shipped a bug in exactly this maths: `screenScaleFor` returned the
magnification `P/(P-z)` instead of its inverse `(P-z)/P`. Both are
plausible one-liners, a re-implementation in Python would have been just as
wrong as the TypeScript, and reading the source does not reveal a fraction that
is the right way round.

So this runs the real TypeScript through node. Where node is unavailable the
test SKIPS rather than fails — a geometry check must not be the reason the
suite is red on a machine that cannot run it, and a skip that nobody reads is
still better than a suite that is red for the wrong reason.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECK = (
    ROOT
    / 'studio'
    / 'src'
    / 'templates'
    / 'finance-showcase'
    / 'common'
    / 'projection.check.ts'
)
SOURCE = CHECK.with_name('projection.ts')


# Resolved once, at import. Resolving inside the test body instead made the
# skipif marker and the test disagree about whether node exists.
_NPX = shutil.which('npx') or shutil.which('npx.cmd')


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
def test_projection_maths_holds():
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
    assert proc.returncode == 0, f'projection check failed:\n{proc.stdout}\n{proc.stderr}'


def test_scale_compensation_is_not_the_magnitude():
    """Source-level guard, so the check has teeth even without node.

    `P / (P - z)` is the projection's magnification; the counter-scale has to be
    its inverse. They differ only in the order of the fraction, which is exactly
    why this reads as a bug rather than a style nit — and the mutation check in
    the commit record shows the behavioural test failing when it is inverted.
    """
    src = SOURCE.read_text(encoding='utf-8')
    body = src.split('export const screenScaleFor', 1)[1]
    assert 'perspective - planeZ) / perspective' in body, (
        'screenScaleFor must return (P - z) / P — the inverse of the projection'
    )
    assert 'perspective / (perspective - planeZ)' not in body, (
        'screenScaleFor is returning the magnification, not its inverse'
    )


def test_position_and_size_come_from_one_place():
    """Camera motion and projection must not be re-implemented in a scene."""
    stack = (
        ROOT
        / 'studio'
        / 'src'
        / 'templates'
        / 'finance-showcase'
        / 'scenes'
        / 'BrowserStack.tsx'
    ).read_text(encoding='utf-8')
    for helper in ('cssXForScreenX', 'screenScaleFor', 'useCameraState'):
        assert helper in stack, f'BrowserStack should use {helper} from the shared module'
    # a scene that recomputed the ramp/easing would silently disagree with the rig
    assert 'perspective ?' not in stack and 'perspective(' not in stack, (
        'BrowserStack must not build its own perspective transform — '
        'it solves against the camera state instead'
    )
