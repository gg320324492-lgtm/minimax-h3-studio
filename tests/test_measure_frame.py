"""The measuring instrument has to be trustworthy in both themes (P6 review).

P6.5 made premium-light a real theme and the centring tool quietly stopped
working on it. Three versions of `measure_frame.py` have now been wrong in the
same way — each looked correct on premium-dark, each was found by a reviewer
measuring a light frame:

  v1  matched premium-dark surface colours. Light frames measured EMPTY.
  v2  sampled one modal backdrop colour and used a fixed delta of 8. premium-dark's
      backdrop spans 10..16 (range 6, under the delta) so it worked; premium-light's
      spans 244..255 (range 11, OVER the delta) so most of the frame registered as
      content. A correctly centred frame measured -57.5px. Reproduced digit for
      digit rather than suspected.
  v3  models the backdrop per row from the frame's own edges, and refuses to
      print an extent when the model does not explain the frame.

These tests pin v3 against both failures, using SYNTHETIC frames so they are
portable and do not depend on a render having been done.

Run:
  python -m pytest tests/test_measure_frame.py -q
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'studio' / 'scripts' / 'measure_frame.py'

W, H = 1920, 1080
MID = W / 2.0


def _run(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        capture_output=True, text=True, timeout=300,
        # utf-8, not the gbk locale default: see test_chart_math's note
        encoding='utf-8', errors='replace',
    )


def _paper_backdrop(img: np.ndarray) -> np.ndarray:
    """A premium-light style backdrop: a gradient whose range EXCEEDS a small
    fixed threshold. This is the property that broke v2."""
    for y in range(H):
        v = 255 - int(11 * y / (H - 1))
        img[y, :, :] = (v, v, int(v * 0.96))
    return img


def _offset(out: str, label: str) -> float:
    """Pull the offset out of a reported line, in px.

    A regex rather than a whitespace split. An earlier version of the tool
    printed `offset= +3.0px` — a width specifier had padded the number and
    injected a space — and the field came apart on it. The format is now
    unpadded, but a parser that cannot be broken by a space is worth having:
    this output is what gets read by people and by scripts.
    """
    for line in out.splitlines():
        if line.strip().startswith(label):
            m = re.search(r'offset=([-+]?[0-9.]+)px', line)
            if m:
                return float(m.group(1))
    raise AssertionError(f'no {label} offset in:\n{out}')


def _box(img: np.ndarray, y0: int, y1: int, x0: int, x1: int) -> None:
    img[y0:y1, x0:x1, :] = (250, 250, 247)


@pytest.fixture
def light_frame_with_window(tmp_path):
    """A paper frame with a near-white window — the case v2 got wrong.

    The window is only ~11 levels from the paper, which is the same order as
    the backdrop's own gradient, so no absolute threshold can separate them.
    """
    img = np.zeros((H, W, 3), dtype=np.uint8)
    _paper_backdrop(img)
    # window spanning x 395..1525, centred on the frame, with type inside it
    _box(img, 380, 740, 395, 1525)
    img[430:470, 430:900, :] = (20, 20, 15)
    p = tmp_path / 'light_window.png'
    Image.fromarray(img).save(p)
    return p


def test_light_theme_extent_finds_the_window_not_the_frame(light_frame_with_window):
    """The v2 failure: a correct frame measured -57.5px because the backdrop's
    own gradient range exceeded the fixed threshold."""
    proc = _run(light_frame_with_window)
    out = proc.stdout
    assert 'UNRELIABLE' not in out, f'model should explain this frame:\n{out}'
    offset = _offset(out, 'extent')
    # the window is 395..1525, centre 960.0 — so the true offset is 0.0px.
    # Anything near +/-100 means the backdrop leaked into the mask again.
    assert abs(offset) < 12, (
        f'light-theme extent is off by {offset}px; expected ~0 for a centred '
        f'window. The backdrop gradient is being counted as content:\n{out}'
    )


def test_light_and_dark_agree_on_the_same_geometry(tmp_path):
    """The cross-check that matters: one scene, two themes, same answer.

    `extent` includes whatever shadow is detectable, and a shadow's
    detectability depends on how bright the ground is, so extent is NOT
    comparable across themes. `marks` measures type and accents, which sit far
    from the ground either way, and IS.
    """
    results = {}
    # Ground and window separated by ~12 levels in BOTH directions-from-ground,
    # the way the two themes actually differ: on premium-dark the window is
    # lighter than the ground, on premium-light it is lighter too but both sit
    # far higher up the range. What must not change is the GEOMETRY.
    for name, ground, window, ink in (
        ('dark', 8, 24, (245, 242, 234)),
        ('light', 238, 254, (20, 20, 15)),
    ):
        img = np.zeros((H, W, 3), dtype=np.uint8)
        for y in range(H):
            v = ground + int(6 * y / (H - 1))
            img[y, :, :] = (v, v, min(255, int(v * 1.02)))
        img[380:740, 395:1525, :] = window
        img[430:470, 430:900, :] = ink
        p = tmp_path / f'{name}.png'
        Image.fromarray(img).save(p)
        proc = _run(p)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        results[name] = _offset(proc.stdout, 'marks')
    assert abs(results['dark'] - results['light']) < 4, (
        f'the same window measured at {results["dark"]}px on dark and '
        f'{results["light"]}px on light; marks must agree across themes'
    )


def test_refuses_rather_than_printing_a_wrong_number(tmp_path):
    """A full-bleed element makes the edge samples content, not backdrop.

    The honest answer is no answer: a confident wrong number gets recorded in a
    ledger and argued about, a refusal gets fixed.
    """
    img = _paper_backdrop(np.zeros((H, W, 3), dtype=np.uint8))
    img[:, 0:260, :] = (20, 20, 24)   # a panel running off the left edge
    p = tmp_path / 'fullbleed.png'
    Image.fromarray(img).save(p)

    proc = _run(p)
    out = proc.stdout
    assert 'UNRELIABLE' in out, f'a frame the model cannot explain must be refused:\n{out}'
    assert proc.returncode != 0, 'an unreliable measurement must fail the exit code'
    for line in out.splitlines():
        if line.strip().startswith('extent'):
            assert 'offset=' not in line, (
                f'extent printed a number AND called itself unreliable:\n{out}'
            )
    # marks is still measurable and must still be reported
    _offset(out, 'marks')
