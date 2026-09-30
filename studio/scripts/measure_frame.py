"""Measure a rendered frame's actual geometry instead of trusting the numbers.

P6.2 was recorded as "the params took effect but the stack is not centred",
with the cause named: the near window is magnified by perspective, so optical
centre != geometric centre. The only thing that settles that is measuring the
pixels, so this does exactly that and prints the offset from frame centre.

Two independent measurements, because they can disagree and when they do the
disagreement is the finding:

  silhouette — every pixel that is a window SURFACE colour. This is the cluster
               the viewer perceives, so its bbox centre is the honest answer to
               "is it centred", and it is the only metric the exit code judges.
  content    — every pixel bright enough to be type or an accent. Reported for
               context, NOT as a centring verdict: in a stack of windows whose
               text is left-aligned and whose right side is occluded by the
               window in front, bright content is inherently left-heavy. A large
               content offset there is normal and says nothing about centring —
               reading it as a failure is the mistake this label exists to stop.

Usage:
  python studio/scripts/measure_frame.py out/stills_after/f00400.png
  python studio/scripts/measure_frame.py out/stills_after/*.png
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit('needs pillow + numpy')

# The backdrop is a radial gradient (design/tokens backgroundAlt -> background),
# so it is NOT a flat colour and a tolerance around a "surface" colour swallows
# it. Measured on a real frame the backdrop tops out at RGB(16,16,20) and is
# always neutral-to-cool by at most 3; the window surfaces sit at 20 and 28 on
# red with a blue lead of 4-6. R >= 19 separates them with margin.
SURFACE_MIN_RED = 19
SURFACE_MIN_BLUE_LEAD = 3
INK_LUMA = 90  # 0-255; type is 245, gold accent 196, dim ink 0.62*245=152


def _bbox(mask) -> tuple[int, int, int, int] | None:
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    if not rows.size or not cols.size:
        return None
    return int(cols[0]), int(rows[0]), int(cols[-1]), int(rows[-1])


def report(path: Path) -> int:
    img = np.asarray(Image.open(path).convert('RGB')).astype(np.int16)
    h, w, _ = img.shape
    mid = w / 2.0

    red = img[:, :, 0]
    lead = img[:, :, 2] - red
    surf = (red >= SURFACE_MIN_RED) & (lead >= SURFACE_MIN_BLUE_LEAD)

    luma = img.mean(axis=2)
    ink = luma >= INK_LUMA

    name = path.name
    print(f'\n{name}  {w}x{h}  frame centre x = {mid:.1f}')
    bad = 0
    for label, mask in (('silhouette', surf), ('content  ', ink)):
        box = _bbox(mask)
        if box is None:
            print(f'  {label:11s} EMPTY — nothing measured')
            bad += 1
            continue
        x0, y0, x1, y1 = box
        centre = (x0 + x1) / 2.0
        offset = centre - mid
        width = x1 - x0 + 1
        print(
            f'  {label:11s} x[{x0:4d}..{x1:4d}] y[{y0:4d}..{y1:4d}] '
            f'w={width:4d}  centre={centre:7.1f}  offset={offset:+7.1f}px '
            f'({offset / (w / 2) * 100:+5.2f}% of half-width)'
        )
    return bad


def main() -> int:
    paths = [Path(a) for a in sys.argv[1:]]
    if not paths:
        print(__doc__)
        return 2
    bad = sum(report(p) for p in paths)
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
