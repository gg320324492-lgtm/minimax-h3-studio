"""Behavioural test for take selection (P1 review follow-up R-03).

The source-text guard in test_p0_regressions.py is cheap but cannot prove that
selection actually works — renaming the variable would pass the text check
while shipping the wrong take again. These tests build real video fixtures and
assert on measured behaviour.

Run:
  python -m pytest tests/test_take_selection_behaviour.py -q
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'studio' / 'scripts'))

from take_ranker import analyze, pixel_signature, signature_distance  # noqa: E402


def _write_video(path: Path, frames: int, size=(320, 180), *, noise=0.0,
                 blur=False, seed=0) -> None:
    """A bright bar sweeps the frame; `noise`/`blur` degrade it."""
    import cv2

    w, h = size
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), 24, (w, h))
    rng = np.random.default_rng(seed)
    for i in range(frames):
        img = np.full((h, w, 3), 40, np.uint8)
        x = int((i / max(frames - 1, 1)) * (w - 40))
        cv2.rectangle(img, (x, 0), (x + 40, h), (220, 220, 220), -1)
        if noise:
            img = np.clip(img.astype(np.int16)
                          + rng.integers(-noise, noise, img.shape), 0, 255).astype(np.uint8)
        if blur:
            img = cv2.GaussianBlur(img, (9, 9), 0)
        vw.write(img)
    vw.release()


def test_blurred_take_loses_to_sharp_take():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        sharp, blurred = d / 'a.mp4', d / 'b.mp4'
        _write_video(sharp, frames=60)
        _write_video(blurred, frames=60, blur=True)

        m_sharp, m_blur = analyze(sharp), analyze(blurred)
        assert m_sharp.sharpness > m_blur.sharpness, (
            f'sharpness did not separate: {m_sharp.sharpness} vs {m_blur.sharpness}')
        assert m_sharp.score > m_blur.score, (
            f'blurred take outscored the sharp one: {m_sharp.score} vs {m_blur.score}')


def test_frozen_take_loses_to_moving_take():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        moving, frozen = d / 'mov.mp4', d / 'frz.mp4'
        _write_video(moving, frames=60)
        _write_video(frozen, frames=60)
        # freeze: same frame every time
        import cv2
        img = np.full((180, 320, 3), 40, np.uint8)
        cv2.rectangle(img, (140, 0), (180, 180), (220, 220, 220), -1)
        vw = cv2.VideoWriter(str(frozen), cv2.VideoWriter_fourcc(*'mp4v'), 24, (320, 180))
        for _ in range(60):
            vw.write(img)
        vw.release()

        m_mov, m_frz = analyze(moving), analyze(frozen)
        assert m_mov.motion > m_frz.motion, (
            f'motion did not separate: {m_mov.motion} vs {m_frz.motion}')
        assert m_mov.score > m_frz.score, (
            f'frozen take outscored the moving one: {m_mov.score} vs {m_frz.score}')


def test_same_seed_rerun_is_detected_as_duplicate():
    """The EP01 S06 case: identical pixels, different files. The signature must
    separate 'same generation' from 'genuinely different'."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        a, rerun, different = d / 'a.mp4', d / 'b.mp4', d / 'c.mp4'
        _write_video(a, frames=60)                      # seed 0
        _write_video(rerun, frames=60, seed=0)          # same synthesis
        _write_video(different, frames=60, noise=40, seed=7)  # real difference

        s_a = pixel_signature(a)
        same_d = signature_distance(s_a, pixel_signature(rerun))
        diff_d = signature_distance(s_a, pixel_signature(different))

        assert same_d < 0.5, f'same-seed rerun not detected (distance {same_d})'
        assert diff_d > 1.0, (
            f'a genuinely different take would be flagged as a duplicate '
            f'(distance {diff_d}) — threshold is too loose')


def test_rank_shot_picks_the_best_take():
    """Full shot-level ranking: good take must win over a frozen and a blurred one."""
    sys.path.insert(0, str(ROOT / 'studio' / 'scripts'))
    import cv2

    import rank_takes

    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / 'SX'
        raw.mkdir(parents=True)
        _write_video(raw / 'SX_T01.mp4', frames=60)                # frozen-ish default
        _write_video(raw / 'SX_T02.mp4', frames=60, noise=40, seed=7)  # real detail
        _write_video(raw / 'SX_T03.mp4', frames=60, blur=True)     # blurry

        import cv2 as _cv2
        vw = _cv2.VideoWriter(str(raw / 'SX_T01.mp4'),
                             _cv2.VideoWriter_fourcc(*'mp4v'), 24, (320, 180))
        still = np.full((180, 320, 3), 40, np.uint8)
        for _ in range(60):
            vw.write(still)
        vw.release()

        metrics, winner, err = rank_takes.rank_shot('SX', raw)
        assert err is None, err
        assert len(metrics) == 3
        assert winner == 'SX_T02', (
            f'expected the detailed take to win, got {winner} '
            f'({[(m.take_id, round(m.score, 3)) for m in metrics]})')


if __name__ == '__main__':
    raise SystemExit(__import__('pytest').main([__file__, '-q']))
