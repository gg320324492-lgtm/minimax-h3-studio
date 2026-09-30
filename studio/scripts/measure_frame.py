"""Measure a rendered frame's actual geometry instead of trusting the numbers.

P6.2 was recorded as "the params took effect but the stack is not centred",
with the cause named: the near window is magnified by perspective, so optical
centre != geometric centre. The only thing that settles that is measuring the
pixels, so this does exactly that and prints the offset from frame centre.

BOTH metrics are measured RELATIVE TO THE BACKDROP, not against absolute
colours. That is not a stylistic choice — the first version of this script
matched the finance-showcase dark surface colours (RGB >= 19 on red, blue lead
>= 3) and reported EMPTY for every premium-light frame, because a white window
on a paper background is not a dark surface. An acceptance instrument that only
works on one of the two themes the project ships is an instrument that will
quietly certify the wrong thing.

  extent — every pixel that differs from the backdrop by more than a hair:
           surfaces, type, accents, and the shadows under them. This is the
           cluster the viewer perceives, so its bbox centre answers "is it
           centred".
  marks  — only pixels that differ a LOT from the backdrop: type and accents,
           not surfaces and not shadow. Type sits inside the composition, so a
           broken layout shows up here too.

On a dark theme the marks are light on near-black; on a light theme they are
dark on paper. Both are "far from the backdrop", which is why the threshold is
relative.

CAVEAT, measured: `extent` is trustworthy on LOSSLESS stills only. The same
Calendar frame reads -0.5px as a PNG and -34px out of an h264 mp4, because
compression noise crosses the threshold. For a delivered video use `marks`.

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

# A pixel counts as "not backdrop" once it moves this far from it. Small enough
# to catch antialiased type edges, large enough to ignore gradient banding in
# the radial backdrop.
SUBTLE = 8
# A pixel counts as a "mark" — type, an accent, a highlighted cell — once it
# moves this far. Chosen well clear of the backdrop gradient's own range
# (measured: premium-dark 10..16, premium-light 244..255) so no amount of
# gradient noise reaches it.
STRONG = 60


def _bbox(mask) -> tuple[int, int, int, int] | None:
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    if not rows.size or not cols.size:
        return None
    return int(cols[0]), int(rows[0]), int(cols[-1]), int(rows[-1])


def _backdrop(img: np.ndarray) -> np.ndarray:
    """The modal colour of the frame's border ring.

    The border is backdrop on every scene by construction — Backdrop is a
    full-frame AbsoluteFill inside each scene — so the ring is a clean sample of
    the background without touching the composition in the middle.
    """
    ring = np.concatenate(
        [img[:24].reshape(-1, 3), img[-24:].reshape(-1, 3),
         img[:, :24].reshape(-1, 3), img[:, -24:].reshape(-1, 3)]
    )
    colours, counts = np.unique(ring, axis=0, return_counts=True)
    return colours[int(np.argmax(counts))]


def report(path: Path) -> bool:
    img = np.asarray(Image.open(path).convert('RGB')).astype(np.int16)
    h, w, _ = img.shape
    mid = w / 2.0
    bg = _backdrop(img)
    delta = np.abs(img - bg).max(axis=2)

    print(f'\n{path.name}  {w}x{h}  frame centre x = {mid:.1f}  backdrop = {tuple(int(v) for v in bg)}')
    ok = True
    for label, mask in (('extent', delta > SUBTLE), ('marks ', delta > STRONG)):
        box = _bbox(mask)
        if box is None:
            print(f'  {label} EMPTY — nothing measured (is this frame blank?)')
            ok = False
            continue
        x0, y0, x1, y1 = box
        centre = (x0 + x1) / 2.0
        offset = centre - mid
        print(
            f'  {label} x[{x0:4d}..{x1:4d}] y[{y0:4d}..{y1:4d}] '
            f'w={x1 - x0 + 1:4d}  centre={centre:7.1f}  offset={offset:+7.1f}px '
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
