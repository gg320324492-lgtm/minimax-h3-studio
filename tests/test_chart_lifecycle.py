"""The chart lifecycle check, wired into pytest so it cannot rot (P7.3).

`lifecycle.check.ts` is 29 call sites / 54 assertions over the timeline every
mark animates from. Until P7.3 it was the one executable check with no pytest
wiring — scale.check.ts and projection.check.ts both had it — so P7.2's guards
ran only when someone remembered to run them. A guard nobody is forced to run
is a guard, eventually, that has not run.

Run:
  python -m pytest tests/test_chart_lifecycle.py -q
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / 'studio'
CHECK = STUDIO / 'src' / 'templates' / 'finance-showcase' / 'charts' / 'lifecycle.check.ts'

_NPX = shutil.which('npx') or shutil.which('npx.cmd')


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
def test_chart_lifecycle_holds():
    # utf-8 capture: see the note in test_chart_math — locale-decoded output
    # loses the failure message precisely when there is one to lose
    proc = subprocess.run(
        [_NPX, 'tsx', str(CHECK)],
        cwd=STUDIO, capture_output=True, text=True, timeout=300,
        encoding='utf-8', errors='replace',
    )
    assert proc.returncode == 0, f'lifecycle check failed:\n{proc.stdout}\n{proc.stderr}'


def test_the_check_actually_covers_the_properties_a_render_cannot_show():
    """A guard that checks nothing is the failure this project keeps meeting.

    The three properties a render would never reveal — phases tiling any
    duration, the entrance cap binding, and a stagger where the last mark
    finishes after the first — must be named in the check file, or the check
    is passing vacuously over the parts that matter.
    """
    assert CHECK.exists(), f'no executable check at {CHECK}'
    src = CHECK.read_text(encoding='utf-8')
    for load_bearing in (
        'entranceFrames',        # the cap exists and is exercised
        'enterFor',              # stagger delay, the only place it is applied
        'staggerFrames',         # and its knob
        'emphasis',              # emphasis held through highlight/focus
        'PHASES',                # phase tiling, in order
        'presence',              # exit never zero-length
        'WEIGHTS',               # the phase budget sums to 1
    ):
        assert load_bearing in src, f'the check never exercises {load_bearing}'


def test_lifecycle_module_stays_pure():
    """The timeline is arithmetic; React in it would make it untestable."""
    src = (STUDIO / 'src' / 'templates' / 'finance-showcase' / 'charts' / 'lifecycle.ts')
    body = src.read_text(encoding='utf-8')
    assert 'from \'react\'' not in body and 'from "react"' not in body
    assert 'remotion' not in body
