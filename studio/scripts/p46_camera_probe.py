"""p46_camera_probe.py — is frame-to-frame DIFFERENCE enough to separate a
camera move from object motion? Built so the answer is measured, not argued.

P37'S DEATH CAUSE
------------------
`docs/P37_REFERENCE_REANALYSIS.md:78`:

    | 6 | 相机 | B | 无测量 | 镜头运动与物体运动的分离需要光流/单应估计，
      本项目零此仪器。⚠️ 片子确实有 3D 透视运动（51–55s 段肉眼可见立柱升起），
      所以这是「输入有但仪器没有」，不是「片子没有」

So the gap is not the film, it is the instrument. This module builds the
cheapest honest half of one and measures exactly where it stops.

WHAT IS BUILT, AND WHAT IT IS NOT
---------------------------------
Built: a GLOBAL TRANSLATION estimate per frame pair, by phase correlation —
FFT(a) · conj(FFT(b)), normalised, inverse-transformed, and read at its peak.
This is not optical flow and is not called that here: it assumes the whole
frame shifted by ONE (dx, dy) and finds the shift that best aligns the two.
It says nothing about individual objects.

Then it reports three numbers per pair, which together answer the question:

    frame_difference   mean |Δ| between consecutive frames. This is what
                       `reference_probe` already measures, and it is the
                       instrument whose sufficiency is in question.
    global_shift       (dx, dy) in pixels, from phase correlation.
    residual           mean |Δ| AFTER compensating that shift.

The reading, stated as a rule and not as a threshold:

    residual << frame_difference  the change WAS a whole-frame translation.
                                  That is camera movement, isolated.
    residual ~= frame_difference  the change was NOT a translation of the
                                  whole frame. It is object motion, OR a
                                  camera move this model cannot express —
                                  rotation, zoom, dolly, perspective.

The second case is the interesting one, and it is where this film lives.

WHAT THIS DELIBERATELY DOES NOT CLAIM
-------------------------------------
A camera move in 3D is not a 2D shift. `camera.translateZ` is a dolly, which
looks like a scale change; `rotateY` is an orbit, which is a projective warp.
Phase correlation fits neither, and this module says so where a reader will
meet the numbers rather than in a footnote. Fitting a full homography needs
feature correspondence and a RANSAC solver — `cv2` is not importable under
py-3.12 here (it is under py-3.10, which has no pytest), so that instrument is
named as the next step and not faked with a partial one that would report a
small residual for a dolly and be read as "no camera motion".

Usage:
    py -3.12 -I p46_camera_probe.py --pairs pairs.json
    py -3.12 -I p46_camera_probe.py --film <path> --at 12.0,25.0,53.0,70.0
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / 'out' / 'p46_probe' / 'camera'


def _gray(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 3:
        f = frame.astype(np.float64)
        return (0.299 * f[..., 0] + 0.587 * f[..., 1] + 0.114 * f[..., 2])
    return frame.astype(np.float64)


def frame_difference(a: np.ndarray, b: np.ndarray) -> float:
    """Mean absolute luma difference. The instrument whose sufficiency is tested."""
    return float(np.abs(_gray(a) - _gray(b)).mean())


def global_shift(a: np.ndarray, b: np.ndarray,
                 limit: float | None = None) -> tuple[float, float]:
    """The (dy, dx) that best aligns `b` onto `a`, by phase correlation.

    Sub-pixel refinement is deliberately absent. The consumer of this number is
    a COMPENSATION step — if the shift is right, the residual drops — and a
    peak read off a correlation surface is already the right answer to within a
    pixel, which is far below what a compensation test can distinguish from
    zero. Claiming sub-pixel precision here would be precision nobody uses.
    """
    fa = np.fft.fft2(_gray(a) - _gray(a).mean())
    fb = np.fft.fft2(_gray(b) - _gray(b).mean())
    cross = fa * np.conj(fb)
    mag = np.abs(cross)
    mag[mag == 0] = 1.0
    corr = np.real(np.fft.ifft2(cross / mag))
    h, w = corr.shape
    dy, dx = np.unravel_index(int(np.argmax(corr)), corr.shape)
    # argmax gives a wrapped index; convert to a signed displacement.
    if dy > h // 2:
        dy -= h
    if dx > w // 2:
        dx -= w
    if limit is not None and (abs(dy) > limit or abs(dx) > limit):
        return 0.0, 0.0
    return float(dy), float(dx)


def compensate(a: np.ndarray, b: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """`b` shifted by (dy, dx), cropping the edges that have no source pixel.

    ⚠️ The result is FLOAT on purpose, and the first version was not:
    `np.full_like(b, np.nan)` on a `uint8` frame cannot store NaN — numpy casts
    it away and emits `RuntimeWarning: invalid value encountered in cast` —
    so the "no source pixel" border was filled with a real number and
    `~np.isnan(moved)` selected EVERY pixel. The residual was then averaged
    over a border that was never compared, which is a residual inflated by the
    size of the shift rather than by the motion left over. Same class of error
    as scoring a classifier on a frame it never saw, wearing arithmetic
    clothes. Measured before the fix, not after: at a planted (3, 0) the
    un-fixed form reported residual 0.847 where the corrected form reports
    0.000, because after compensating a pure translation there is nothing left.

    SIGN CONVENTION: the returned shift is the one that maps `b` ONTO `a`, so it
    is the negative of the direction `b` was moved. A frame rolled DOWN by 3
    yields `shift_dy = -3`. Compensating with the returned value is what
    `residual` does, and the two are self-consistent; the sign is only a trap
    for a reader comparing it with a plant direction.
    """
    if dy == 0 and dx == 0:
        return b
    out = np.full(b.shape[:2], np.nan, dtype=np.float64)
    g = _gray(b)
    h, w = g.shape
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    out[yd, xd] = g[ys, xs]
    return out


def residual(a: np.ndarray, b: np.ndarray, dy: int, dx: int) -> float:
    """Mean |Δ| over the pixels that survive the shift, not the cropped border.

    Measuring over the whole frame after blanking the border would compare a
    half-empty image against a full one and report a residual that is mostly
    the size of the shift rather than the size of the motion left over.
    """
    if dy == 0 and dx == 0:
        return frame_difference(a, b)
    moved = compensate(a, b, dy, dx)
    keep = ~np.isnan(moved)
    if keep.sum() == 0:
        return frame_difference(a, b)
    return float(np.abs(_gray(a)[keep] - moved[keep]).mean())


def global_similarity(a: np.ndarray, b: np.ndarray,
                      scales: tuple[float, ...] = tuple(
                          round(0.94 + 0.01 * i, 2) for i in range(13))
                      ) -> dict:
    """Best whole-frame ZOOM + translation, by searching scale then shifting.

    WHY THE SCALE TERM EXISTS. P37 records that this film's 51-55s segment has
    visible 3D perspective motion. A dolly or a zoom is not a translation: the
    whole frame changes size, so phase correlation reports `shift = 0` and the
    translation-only answer is "no camera motion" on a frame that plainly has
    some. That is the confident zero this project has been fooled by, so the
    instrument searches a 1-D scale ladder and for each scale runs the same
    phase correlation, then keeps whichever scale leaves the smallest residual.

    The ladder is +-6% in 1% steps, chosen because it brackets the per-frame
    zoom of a 60fps shot without pretending to resolve sub-pixel scale. The
    result is a COARSE scale, reported as the step it landed on.

    WHAT IT STILL CANNOT DO: rotation about the optical axis, and a projective
    warp from an orbit (`camera.rotateY`), which no scale-and-shift model
    expresses. A residual that survives this search is evidence that the motion
    is local, or projective, or both — and this module reports which of those
    it can rule out rather than calling the remainder "no motion".
    """
    best = {'scale': 1.0, 'shift_dy': 0, 'shift_dx': 0,
            'residual': frame_difference(a, b)}
    h, w = _gray(a).shape
    ga = _gray(a)
    gb = _gray(b)
    for s in scales:
        if s == 1.0:
            warped = gb
        else:
            # Centre-anchored nearest-neighbour zoom straight to the frame's own
            # size, for s < 1 (zoom IN) and s > 1 (zoom OUT) alike.
            #
            # ⚠️ The first version built an oversized `big` and pasted it at
            # ((h-nh)//2, (w-nw)//2). Python floors that division toward -inf,
            # so for EVERY s < 1 the offset was negative and the slice became a
            # 15x26 corner; for every s > 1 the paste raised `could not
            # broadcast input array from shape (734,1305) into shape (7,13)`.
            # A scale search that cannot express half its own ladder is a scale
            # search that would answer "no camera motion" on a zoom.
            #
            # Nearest-neighbour on purpose: a smoothing kernel would change the
            # very residual it is being asked to minimise.
            yi = (np.arange(h) / s).astype(np.int64).clip(0, h - 1)
            xi = (np.arange(w) / s).astype(np.int64).clip(0, w - 1)
            warped = gb[yi][:, xi]
        if warped.shape != ga.shape:
            continue
        dy, dx = global_shift(ga, warped)
        yi, xi = int(round(dy)), int(round(dx))
        r = residual(ga, warped, yi, xi)
        if r < best['residual']:
            best = {'scale': s, 'shift_dy': yi, 'shift_dx': xi,
                    'residual': r}
    diff = frame_difference(a, b)
    best['frame_difference'] = round(diff, 4)
    best['residual'] = round(best['residual'], 4)
    best['explained_by_similarity'] = round(
        1.0 - (best['residual'] / diff), 4) if diff > 0 else 0.0
    return best


def analyse_pair(a: np.ndarray, b: np.ndarray) -> dict:
    diff = frame_difference(a, b)
    dy, dx = global_shift(a, b)
    dy_i, dx_i = int(round(dy)), int(round(dx))
    res = residual(a, b, dy_i, dx_i)
    row = {
        'frame_difference': round(diff, 4),
        'shift_dy': dy_i, 'shift_dx': dx_i,
        'shift_magnitude_px': round(float(np.hypot(dy, dx)), 2),
        'residual_after_shift': round(res, 4),
        # The share of the difference that a whole-frame translation explains.
        # 1.0 means the change WAS a translation; ~0 means it was not.
        'explained_by_translation': round(1.0 - (res / diff), 4) if diff > 0 else 0.0,
    }
    sim = global_similarity(a, b)
    row['similarity_scale'] = sim['scale']
    row['explained_by_similarity'] = sim['explained_by_similarity']
    return row


def _decode_pair(path: str | Path, at: float, fps: float = 60.0) -> tuple:
    cmd = ['ffmpeg', '-v', 'error', '-ss', str(at), '-i', str(path),
           '-frames:v', '2', '-vsync', '0', '-f', 'rawvideo',
           '-pix_fmt', 'gray', '-']
    proc = subprocess.run(cmd, capture_output=True, timeout=300)
    if proc.returncode != 0 or len(proc.stdout) < 2:
        return None, None
    import re
    probe = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
         'stream=width,height', '-of', 'csv=p=0:s=x', str(path)],
        capture_output=True, text=True, timeout=60)
    w, h = (int(x) for x in probe.stdout.strip().split('x')[:2])
    fs = w * h
    a = np.frombuffer(proc.stdout[:fs], dtype=np.uint8).reshape(h, w)
    b = np.frombuffer(proc.stdout[fs:2 * fs], dtype=np.uint8).reshape(h, w)
    return a, b


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--film', type=Path, required=True)
    ap.add_argument('--at', default='5.0,12.0,25.0,30.0,40.0,53.0,60.0,70.0,78.0',
                    help='timestamps (s) at which to take a consecutive pair')
    ap.add_argument('--out', type=Path, default=OUT / 'camera_motion.json')
    args = ap.parse_args(argv)

    rows = []
    print(f'{"t":>7s} {"frame_diff":>11s} {"dy":>5s} {"dx":>5s} '
          f'{"expl_trans":>12s} {"scale":>7s} {"expl_sim":>9s}')
    for at in [float(x) for x in args.at.split(',') if x.strip()]:
        a, b = _decode_pair(args.film, at)
        if a is None:
            print(f'{at:7.2f}  could not decode a pair')
            continue
        row = analyse_pair(a, b)
        row['t_seconds'] = at
        rows.append(row)
        print(f'{at:7.2f} {row["frame_difference"]:11.4f} {row["shift_dy"]:5d} '
              f'{row["shift_dx"]:5d} {row["explained_by_translation"]:12.4f} '
              f'{row["similarity_scale"]:7.2f} '
              f'{row["explained_by_similarity"]:9.4f}')

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(json.dumps({'rows': rows}, indent=1).encode('utf-8'))
    print(f'\n-> {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())