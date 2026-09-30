"""The chart maths, checked before any renderer exists (P7.1).

`charts/scale.ts` decides where every mark lands. A wrong `niceTicks` is
invisible in a render — the axis just looks like the wrong numbers — and a
`linePath` that overshoots draws a dip that is not in the data, which is a
chart that lies rather than a chart that looks odd.

So this runs against the real TypeScript via tsx, the same way
`projection.check.ts` does, and is wired into pytest so it cannot rot. The
monotone-interpolation test is the one that matters most: an overshoot in a
revenue chart is not a cosmetic bug, it is the picture disagreeing with the data.

Run:
  python -m pytest tests/test_chart_math.py -q
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / 'studio'
CHECK = STUDIO / 'src' / 'templates' / 'finance-showcase' / 'charts' / 'scale.check.ts'

_NPX = shutil.which('npx') or shutil.which('npx.cmd')


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
def test_chart_maths_holds():
    proc = subprocess.run(
        [_NPX, 'tsx', str(CHECK)],
        cwd=STUDIO, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, f'chart maths check failed:\n{proc.stdout}\n{proc.stderr}'


def test_the_check_actually_exists_and_covers_the_load_bearing_parts():
    """A guard that checks nothing is the failure this project keeps meeting.

    The monotone overshoot assertion and the nice-number assertion are the two
    that a render would not reveal, so their absence must be a failure.
    """
    assert CHECK.exists(), f'no executable check at {CHECK}'
    src = CHECK.read_text(encoding='utf-8')
    for load_bearing in ('niceTicks', 'monotone', 'overshoot', 'declutter', 'formatValue'):
        assert load_bearing in src, f'the check never exercises {load_bearing}'


def test_no_chart_renderer_may_import_react_in_the_maths_module():
    """scale.ts is pure on purpose: React in there means the maths cannot be
    checked by importing it, which is the whole reason it is a separate file."""
    src = (STUDIO / 'src' / 'templates' / 'finance-showcase' / 'charts' / 'scale.ts').read_text(encoding='utf-8')
    assert 'from \'react\'' not in src and 'from "react"' not in src
    assert 'remotion' not in src
