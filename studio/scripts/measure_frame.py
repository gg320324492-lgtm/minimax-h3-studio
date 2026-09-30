"""Measure a rendered frame's actual geometry instead of trusting the numbers.

Both metrics are measured against a MODEL OF THE BACKDROP, never against an
absolute colour, and never against a single sampled background colour.

Both of those earlier versions were wrong, in the same way:

  v1 matched the premium-dark surface colours (RGB >= 19 on red). Every
     premium-light frame measured EMPTY, because a white window on a paper
     background is not a dark surface.
  v2 sampled one modal colour from the frame's border and thresholded against
     it with a fixed delta of 8. That works on premium-dark, whose backdrop
     gradient spans 10..16 (range 6, under the threshold) and fails on
     premium-light, whose backdrop spans 244..255 (range 11, OVER it) — so
     most of the light frame registered as "content" and extent reported
     -57.5px for a frame that is correctly centred to +3.0px. Measured and
     reproduced digit for digit, not suspected.

A fixed threshold cannot work here: the composition's contrast against its own
background is the same order as the background's gradient, and that ratio is a
design decision that differs per theme. So the backdrop is modelled per row
from the frame's own edges and the threshold is applied to the residual.

And when the model does not explain the frame, this prints UNRELIABLE and exits
non-zero instead of printing a number. An acceptance instrument that emits a
confident wrong number is worse than one that refuses: a wrong number gets
recorded in a ledger and argued about, a refusal gets fixed.

CAVEAT, measured: `extent` is trustworthy on LOSSLESS stills only. The same
Calendar frame reads -0.5px as a PNG and -34px out of an h264 mp4, because
compression noise crosses the threshold. For a delivered video use `marks`,
which measures type and accents and is far from any threshold either way.

Usage:
  python studio/scripts/measure_frame.py out/stills/f00440.png
  python studio/scripts/measure_frame.py out/stills/*.png
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit('needs pillow + numpy')

EDGE = 40          # px sampled at each end of a row to fit the backdrop
RING = 24          # px border band used to check the model and report its range
#: a pixel counts as "not backdrop" once the residual exceeds this. Small
#: enough to catch antialiased type edges, large enough to ignore the
#: backdrop model's own residual.
SUBTLE = 8
#: a pixel counts as a "mark" — type, an accent, a highlighted cell — once the
#: residual is this large. Type and accents sit far from the background in
#: BOTH themes (light-on-near-black, dark-on-paper), so this one is stable.
STRONG = 60
#: if this fraction of the border ring is still flagged, the backdrop model is
#: inadequate for this frame and no extent number will be printed.
RING_TOLERANCE = 0.02


def _fit_backdrop(img: np.ndarray) -> np.ndarray:
    """Model the backdrop as linear in x, per row, fitted from the row's edges.

    A radial-gradient backdrop is close to linear along any given row, and the
    composition is centred, so the leftmost and rightmost EDGE pixels of a row
    are backdrop in practice. Fitting per row also absorbs the vertical
    falloff, which a single global colour obviously cannot.
    """
    h, w, _ = img.shape
    left = np.median(img[:, :EDGE, :], axis=1)          # (h, 3)
    right = np.median(img[:, w - EDGE:, :], axis=1)     # (h, 3)
    t = (np.arange(w, dtype=np.float64) / max(w - 1, 1))[None, :, None]
    return left[:, None, :] + (right - left)[:, None, :] * t


def _bbox(mask) -> tuple[int, int, int, int] | None:
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    if not rows.size or not cols.size:
        return None
    return int(cols[0]), int(rows[0]), int(cols[-1]), int(rows[-1])


def report(path: Path) -> bool:
    img = np.asarray(Image.open(path).convert('RGB')).astype(np.float64)
    h, w, _ = img.shape
    mid = w / 2.0

    residual = np.abs(img - _fit_backdrop(img)).max(axis=2)
    subtle = residual > SUBTLE
    strong = residual > STRONG

    ring = np.zeros((h, w), dtype=bool)
    ring[:RING, :] = ring[-RING:, :] = True
    ring[:, :RING] = ring[:, -RING:] = True
    ring_flagged = float(subtle[ring].mean())
    ring_range = float(residual[ring].max())

    print(
        f'\n{path.name}  {w}x{h}  frame centre x = {mid:.1f}  '
        f'backdrop model residual: ring max {ring_range:.0f}, '
        f'ring flagged {ring_flagged * 100:.2f}%'
    )

    ok = True
    if ring_flagged > RING_TOLERANCE:
        print(
            f'  extent  UNRELIABLE — {ring_flagged * 100:.1f}% of the border ring '
            f'still reads as content, so the backdrop model does not explain this '
            f'frame. Refusing to print a centring number rather than printing a '
            f'wrong one. Two usual causes: a backdrop gradient spanning more than '
            f'the composition\'s own contrast (a per-theme design choice), or the '
            f'composition running off the frame edge, which makes the edge samples '
            f'content instead of backdrop.'
        )
        ok = False
    else:
        box = _bbox(subtle)
        if box is None:
            print('  extent  EMPTY — nothing measured (is this frame blank?)')
            ok = False
        else:
            x0, y0, x1, y1 = box
            centre = (x0 + x1) / 2.0
            offset = centre - mid
            print(
                f'  extent  x[{x0:4d}..{x1:4d}] y[{y0:4d}..{y1:4d}] '
                f'w={x1 - x0 + 1:4d}  centre={centre:7.1f}  offset={offset:+.1f}px '
                f'({offset / (w / 2) * 100:+6.2f}% of half-width)'
            )

    box = _bbox(strong)
    if box is None:
        print('  marks   EMPTY — no type or accent found (is this frame blank?)')
        ok = False
    else:
        x0, y0, x1, y1 = box
        centre = (x0 + x1) / 2.0
        offset = centre - mid
        print(
            f'  marks   x[{x0:4d}..{x1:4d}] y[{y0:4d}..{y1:4d}] '
            f'w={x1 - x0 + 1:4d}  centre={centre:7.1f}  offset={offset:+.1f}px '
            f'({offset / (w / 2) * 100:+6.2f}% of half-width)'
        )
    return ok


def main() -> int:
    paths = [Path(a) for a in sys.argv[1:]]
    if not paths:
        print(__doc__)
        return 2
    bad = sum(not report(p) for p in paths)
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
