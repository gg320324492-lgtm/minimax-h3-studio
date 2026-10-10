"""p46_font_probe.py — SERIF or SANS, from the SHAPE of the strokes.

THE DEATH CAUSE THIS ATTACKS
----------------------------
P37 adjudicated 字体 (`docs/P37_REFERENCE_REANALYSIS.md:80`):

    | 8 | 字体 | B | 无测量 | 需要字形识别（OCR/字体分类），零仪器。
      目视见衬线大标题（KZG OPTION HOUSE）与等宽数字，不构成字体判定 |

The stated cause is "zero instruments for glyph recognition / font
classification". Two instruments could answer it and this module builds the
one that does not need a model:

  * A VLM closed question ("are these letters serif?") is a judgement about
    style. It is exactly the "looks like" criterion the work order rules out,
    and it cannot be scored without knowing the answer — which is the thing
    being asked.
  * A GEOMETRIC statistic on the ink is a checkable shape. Serif faces put a
    thin stroke next to a thick one and hang a horizontal terminal off the end
    of a stem; sans faces do neither. That is visible in the pixel data as
    modulation, and it is measurable without naming the typeface.

THE TWO STATISTICS, both scale-free ratios so no absolute size is baked in
-------------------------------------------------------------------------
  stroke_contrast   p90 / p10 over the horizontal ink-run lengths.
                    Georgia's thick stem and its hairline are both horizontal
                    runs in the rows that cross them, so the ratio is large.
                    In a sans face every stroke is the same width and the
                    ratio collapses toward 1.

  row_mass_contrast p90 / p10 of the per-row ink pixel count, over rows that
                    carry ink. Serifs put a wide bar on the first and last row
                    of the x-height band and almost nothing between; a sans
                    face's rows are near-uniform.

Neither has a threshold. A threshold is only needed to TURN the number into a
verdict, and this module deliberately does not: it reports the numbers for a
corpus whose font is known by construction, and the separation between the
known-serif and known-sans clouds is the measurement. If the clouds overlap,
the instrument is dead and the numbers say so.

THE POSITIVE CLASS IS A CONTROL RENDER, NOT A CLAIM ABOUT A PICTURE
--------------------------------------------------------------------
P45's rule, applied to glyphs: the font is chosen by the code that writes the
frame, so "this frame is serif" is a fact about the input rather than an
opinion about the output. `control_cards()` renders the SAME layout — same
strings, same sizes, same colours, same positions — once per font file. Every
pair differs in exactly one byte-level input, which is the font path.

⚠️ AND THE LIMIT, stated where a reader will meet it: these are SYNTHETIC
frames drawn by Pillow, not this project's renderer. They establish that the
statistic separates known typefaces. They do not establish that it separates
typefaces inside a rendered video frame, which is a further claim and is
measured separately in `p46_font_measure.py`, against frames whose font is
NOT known by construction.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vlm_critic import ask_vlm                                       # noqa: E402

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / 'out' / 'p46_probe' / 'font'
FONTS_DIR = Path('C:/Windows/Fonts')

#: The premium-dark tokens the control frames borrow, so the statistic is not
#: being handed an easier binarisation than the real frames get.
BG = (0x0A, 0x0A, 0x0C)        # premium-dark `background`
INK = (0xF5, 0xF2, 0xEA)       # premium-dark `ink`
MUTED = (0x8C, 0x8A, 0x84)
ACCENT = (0xE8, 0xC4, 0x64)    # premium-dark `accent`

SIZE = (1920, 1080)

#: One line of each role, so the statistic sees a display face AND a text face
#: rather than a single word that might happen to flatter the metric.
LINES = (
    ('KZG OPTION HOUSE', 168, 'display'),
    ('美股期权日报 · MINUTE AGGREGATE OPTION REPORT', 46, 'sub'),
    ('成交量 7,263  留存 63.8%  错误率 0.04%', 40, 'body'),
    ('2026-09-25  OPEN INTEREST 1,438.2  DELTA 28.5', 36, 'caption'),
)

#: font file stem -> the class it belongs to. Chosen as the obvious members of
#: each class on a stock Windows install; the point is not the list but that
#: the two clouds do not overlap.
FONT_CLASS: dict[str, str] = {
    'georgia': 'serif', 'georgiab': 'serif', 'times': 'serif',
    'constan': 'serif', 'cambria': 'serif', 'pala': 'serif',
    'arial': 'sans', 'segoeui': 'sans', 'seguisb': 'sans',
    'trebuc': 'sans', 'verdana': 'sans',
    'consola': 'mono', 'cour': 'mono',
}


def _runs(row: np.ndarray) -> list[int]:
    """Lengths of the maximal True runs in one row."""
    out, n = [], 0
    for v in row:
        if v:
            n += 1
        elif n:
            out.append(n)
            n = 0
    if n:
        out.append(n)
    return out


def ink_mask(img: Image.Image) -> np.ndarray:
    """Pixels that are not the background, at the frames' own ink contrast.

    Threshold is relative to the frame's own background rather than absolute,
    so a frame that is near-white (the reference film's 23-51s segment measures
    `[252,252,252]`) inverts no better than a near-black one and is not handed
    a kinder binarisation than `premium-dark` gets.
    """
    a = np.asarray(img.convert('RGB'), dtype=np.int16)
    flat = a.reshape(-1, 3)
    vals, counts = np.unique(flat, axis=0, return_counts=True)
    bg = vals[int(counts.argmax())]
    return (np.abs(a - bg) > 40).any(axis=2)


def statistics(mask: np.ndarray) -> dict[str, float]:
    """The two ratios. No threshold, no verdict, no name for the typeface."""
    lengths: list[int] = []
    row_mass: list[int] = []
    for row in mask:
        r = _runs(row)
        if r:
            lengths.extend(r)
            row_mass.append(int(row.sum()))
    if len(lengths) < 20:
        return {'stroke_contrast': 0.0, 'row_mass_contrast': 0.0,
                'runs': float(len(lengths)), 'rows': float(len(row_mass))}
    l = np.asarray(lengths, dtype=np.float64)
    m = np.asarray(row_mass, dtype=np.float64)
    return {
        'stroke_contrast': round(float(np.percentile(l, 90)
                                       / max(np.percentile(l, 10), 1e-9)), 4),
        'row_mass_contrast': round(float(np.percentile(m, 90)
                                         / max(np.percentile(m, 10), 1e-9)), 4),
        'runs': float(len(lengths)),
        'rows': float(len(row_mass)),
    }


def measure(img: Image.Image) -> dict[str, float]:
    return statistics(ink_mask(img))


def _font(stem: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONTS_DIR / f'{stem}.ttf'
    if not path.is_file():
        raise SystemExit(f'control font missing: {path}')
    return ImageFont.truetype(str(path), size)


def control_card(stem: str) -> Image.Image:
    """A product-shaped frame in ONE font. Nothing else varies between cards."""
    img = Image.new('RGB', SIZE, BG)
    d = ImageDraw.Draw(img)
    y = 150
    for text, size, role in LINES:
        d.text((120, y), text, font=_font(stem, size),
               fill=INK if role == 'display' else MUTED)
        y += int(size * 1.35)
    d.rectangle([120, y + 40, 320, y + 46], fill=ACCENT)
    return img


def control_cards() -> list[dict]:
    """Render one card per font and measure it. Ground truth is the font file."""
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for stem, klass in FONT_CLASS.items():
        path = OUT / f'control_{stem}.png'
        img = control_card(stem)
        img.save(path)
        row = {'font': stem, 'class': klass, 'path': str(path)}
        row.update(measure(img))
        row.update(glyph_statistics(ink_mask(img)))
        rows.append(row)
    return rows


def separation(rows: list[dict], key: str) -> dict:
    """Do the two clouds overlap? Reported, not thresholded into a verdict."""
    by: dict[str, list[float]] = {}
    for r in rows:
        by.setdefault(r['class'], []).append(float(r[key]))
    out: dict[str, object] = {}
    for klass, vals in sorted(by.items()):
        out[klass] = {'n': len(vals), 'min': round(min(vals), 4),
                      'max': round(max(vals), 4),
                      'mean': round(sum(vals) / len(vals), 4)}
    if 'serif' in by and 'sans' in by:
        out['gap_sans_min_over_serif_max'] = round(
            min(by['sans']) / max(max(by['serif']), 1e-9), 4)
        out['gap_serif_min_over_sans_max'] = round(
            min(by['serif']) / max(max(by['sans']), 1e-9), 4)
        out['overlapping'] = not (min(by['sans']) > max(by['serif'])
                                  or min(by['serif']) > max(by['sans']))
    return out


# ── the geometric attempt, kept because it FAILED and the failure is the point

def glyph_statistics(mask: np.ndarray, min_px: int = 60) -> dict[str, float]:
    """Stroke contrast measured per glyph rather than per frame.

    THE BETTER-MOTIVATED VERSION, and it failed too. Isolating a glyph removes
    the mixing of sizes that made `statistics()` noisy, and an isolated capital
    I is the textbook case: serif fonts hang a wide bar off both ends of a thin
    stem, sans fonts draw a stem of uniform width.

    MEASURED, on the corpus above where every font is known by construction:

        serif  median 1.600 - 2.160
        sans   median 2.500 - 2.875

    The classes do not merely overlap, they ORDER BACKWARDS — the sans cloud
    sits entirely above the serif cloud. A statistic that ranks Arial's strokes
    as more contrasty than Georgia's is not a weak serif detector, it is a
    detector pointing the wrong way, and no threshold on it would be honest.
    Both statistics are retained so the negative result is reproducible rather
    than a story about something that was tried once.
    """
    ys, xs = np.nonzero(mask)
    if ys.size == 0:
        return {'glyph_contrast_median': 0.0, 'glyphs': 0.0}
    lab, n = _components(mask)
    vals: list[float] = []
    for g in range(1, n + 1):
        sub = lab == g
        if int(sub.sum()) < min_px:
            continue
        runs: list[int] = []
        for row in sub:
            runs.extend([x for x in _runs(row) if x >= 2])
        if len(runs) < 4:
            continue
        a = np.asarray(runs, dtype=np.float64)
        p50 = float(np.percentile(a, 50))
        if p50 > 0:
            vals.append(float(np.percentile(a, 90)) / p50)
    vals = [v for v in vals if v > 1.05]
    if not vals:
        return {'glyph_contrast_median': 0.0, 'glyphs': 0.0}
    return {'glyph_contrast_median': round(float(np.median(vals)), 4),
            'glyphs': float(len(vals))}


def _components(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """4-connected components, iterative flood fill. No scipy, no cv2."""
    h, w = mask.shape
    lab = np.zeros((h, w), dtype=np.int32)
    cur = 0
    for sy in range(h):
        for sx in range(w):
            if mask[sy, sx] and lab[sy, sx] == 0:
                cur += 1
                stack = [(sy, sx)]
                lab[sy, sx] = cur
                while stack:
                    y, x = stack.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if (0 <= ny < h and 0 <= nx < w
                                and mask[ny, nx] and lab[ny, nx] == 0):
                            lab[ny, nx] = cur
                            stack.append((ny, nx))
    return lab, cur


# ── the instrument that remains: ask the model, score it where the font is KNOWN

#: Closed question. Serif and sans are defined by a property of the letter's
#: terminals, so the model is told what to look for rather than asked to judge
#: taste. Two words back, as P41's question does, so a rambling answer is
#: detectable instead of parsed hopefully.
FONT_QUESTION = (
    'Look at the LETTERS in this image. Do their strokes end in small '
    'horizontal finishing strokes (SERIF, as in a Times or Georgia face), or '
    'are the strokes plain and unadorned with no finishing strokes (SANS '
    'SERIF, as in an Arial or Helvetica face)? Answer with exactly one word: '
    'SERIF or SANS.'
)

FONT_CLASSES = ('SERIF', 'SANS')


def parse_font_class(text: str) -> str | None:
    """`SERIF` / `SANS`, or None when the answer is neither. None is not a vote.

    Order matters: the word SERIF is a substring of neither SANS, but a model
    that answers "NOT SERIF" is answering about SANS and must not be recorded as
    unreadable, so the negation is handled explicitly rather than by substring.
    """
    if not text:
        return None
    head = ' '.join(text.strip().upper().split()[:6])
    if 'NOT SERIF' in head or 'NO SERIF' in head:
        return 'SANS'
    if head.startswith('SERIF'):
        return 'SERIF'
    if head.startswith('SANS'):
        return 'SANS'
    return None


def ask_font_class(path: Path, **kw: Any) -> tuple[str | None, str]:
    """`(class, reason)` — reason is non-empty exactly when class is None."""
    answer, why = ask_vlm(path, FONT_QUESTION, **kw)
    if why:
        return None, why
    got = parse_font_class(answer or '')
    if got is None:
        return None, (f'the model answered {answer!r}, which is neither SERIF '
                      f'nor SANS — an unreadable answer is not a measurement')
    return got, ''


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--out', type=Path, default=OUT / 'control_stats.json')
    args = ap.parse_args(argv)

    rows = control_cards()
    print(f'{"font":10s} {"class":6s} {"stroke_contrast":>16s} '
          f'{"row_mass_contrast":>18s} {"glyph_med":>10s} {"glyphs":>7s}')
    for r in rows:
        print(f'{r["font"]:10s} {r["class"]:6s} {r["stroke_contrast"]:16.4f} '
              f'{r["row_mass_contrast"]:18.4f} '
              f'{r["glyph_contrast_median"]:10.4f} {int(r["glyphs"]):7d}')
    for key in ('stroke_contrast', 'row_mass_contrast', 'glyph_contrast_median'):
        sep = separation(rows, key)
        print(f'\nseparation by {key}: '
              f'{json.dumps(sep, ensure_ascii=False)}')

    payload = {'rows': rows,
               'separation': {k: separation(rows, k)
                              for k in ('stroke_contrast', 'row_mass_contrast',
                                        'glyph_contrast_median')}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(json.dumps(payload, ensure_ascii=False, indent=1)
                         .encode('utf-8'))
    print(f'\n-> {args.out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())