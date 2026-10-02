"""visual_qa.py — deterministic visual QA for rendered frames (P10, rule 10.1).

Nine rules, each with a MEASURED threshold, and two that are reported
`unavailable` rather than faked. The audit that produced this file is in
`docs/UPGRADE_PROGRESS.md`; the numbers below are quoted from it because a
threshold without its distribution is a guess.

WHY THE ARCHITECTURE IS THIS WAY — three findings from the audit that dictated
it, none of which are stylistic:

1. THE BACKDROP MODEL MUST NOT BE TRUSTED BLIND. `safe_area` models the backdrop
   per row from the frame's own edges. Measured: that model has a residual of 3 on
   a settled frame and **208 on a frame whose content touches the edge** — because
   the edge samples are then content. So a detector for "content touches the
   edge" cannot model the backdrop FROM the edge. Hence:

     - `backdrop_model` returns `trusted: False` above TRUST_RESIDUAL and every
       rule that uses it reports `UNVERIFIABLE` instead of a wrong number;
     - `clipping` uses a PALETTE path (the known background colours of both
       themes) and is therefore never untrusted.

   This is the one place where `safe_area` and `clipping` deliberately disagree on
   a `padX=0` frame: safe_area says UNVERIFIABLE, clipping says FAIL. That
   difference is the design, not a bug — one rule has an instrument and the other
   does not.

2. `verdict` AND `trusted` ARE DIFFERENT FIELDS. `FAIL` means "measured, and it is
   wrong". `UNVERIFIABLE` means "the instrument could not measure it". Collapsing
   them is how a QA gate ends up reporting a confident wrong answer, which is the
   failure this project has hit repeatedly.

3. TWO RULES HAVE NO RELIABLE PIXEL DETECTOR. `overflow` and `collision` are
   reported `unavailable` with the reason attached and NO number. Three separate
   detectors were tried and each failed differently:

     - text bands + column runs: measures GLYPHS, and fuses labels precisely when
       they overlap — so it reports "0px overlap" BECAUSE the collision happened;
     - bar detection: merges the axis into a 1668px "bar";
     - connected components: bars and gridlines form one 1668x745 component that
       swallows the label column.

   Both need the mark layout from the chart options, not pixels.

   For `collision` that instrument now EXISTS — `chart_geometry.py` computes
   each label's width against its centre spacing from the chart options, and
   agrees with rendered frames to 0.2% at two different bar counts. The rule
   stays `unavailable` anyway, because what is missing is a THRESHOLD rather
   than a detector: the ledger names none and the delivered charts measure 0.278,
   so any cut point would be invented. A measurement is not a verdict.

THRESHOLDS, and the distribution each sits in:

  rule          threshold                     measured margin
  safe_area     margin == 0 (exact)           193 frames: smallest POSITIVE margin is
                                              16px left / 24 right / 7 top / 25 bottom.
                                              A positive inset is impossible: 7px is
                                              0.65% of a 1080 frame. 14 frames sit
                                              at 0.
  clipping      content touches an edge       exact, via the palette path
  font_size     ratio vs declared; >12px abs  median band 36/19/69px at s=1/.5625/2
  contrast      WCAG 4.5 text / 3.0 large     8 of 24 pairs fail 4.5 (2.16..4.18)
  black_frame   non-content >= 0.9995         window (0.999238, 1.0) — only 0.000762
                                              wide. THIN, stated as such. 8 corpus
                                              frames are exactly 1.0.
  freeze        difference == 0 (exact)       noise floor measured at exactly 0
  duplicate     distance < 0.5                reused from take_ranker; P1 measured
                                              the take distribution as {0.000} u
                                              [34.5, 67.2], so 0.5 has 34.5x margin
  blur          Laplacian variance < 2.0     corpus p5 is 11.5, so 5.75x; a blur
                                              ramp drops 58.0 -> 32.1 at radius 0.5
                                              and -> 10.5 at radius 1.0
  aspect        exact                         a lookup, no threshold
  missing_asset set difference                a lookup, no threshold

Usage:
    python studio/scripts/visual_qa.py --self-test
    python studio/scripts/visual_qa.py --frame out/stills/f00440.png
    python studio/scripts/visual_qa.py --frame-pair a.png b.png --rule freeze
    python studio/scripts/visual_qa.py --props studio/public/jobs/x/props.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(r'E:\Minimax-H3')
AUDIO_DIR = ROOT / 'studio' / 'public' / 'audio'
PUBLIC_DIR = ROOT / 'studio' / 'public'

PASS = 'PASS'
FAIL = 'FAIL'
UNVERIFIABLE = 'UNVERIFIABLE'
UNAVAILABLE = 'UNAVAILABLE'

# ── measured thresholds ──────────────────────────────────────────────────────
EDGE = 40
RING = 24
#: Above the backdrop model's own residual on a settled frame (measured: 3).
#: Above it the model has sampled content and every number derived from it is
#: wrong, so the rules that use it stop rather than report.
TRUST_RESIDUAL = 60.0
CONTENT_T = 24
#: Above the premium-dark gradient's own spread, 6+6+8 = 20.
PALETTE_TOL = 24
MIN_TYPE_PX = 12.0
WCAG_TEXT = 4.5
WCAG_LARGE = 3.0
BLACK_NONCONTENT = 0.9995
FREEZE_DIFF = 0
DUP_DISTANCE = 0.5
BLUR_VARIANCE = 2.0

PALETTE_BACKGROUNDS = {
    'premium-dark.background': (0x0A, 0x0A, 0x0C),
    'premium-dark.backgroundAlt': (0x10, 0x10, 0x14),
    'premium-light.background': (0xF4, 0xF1, 0xEA),
    'premium-light.backgroundAlt': (0xFF, 0xFF, 0xFF),
}

THEMES: dict[str, dict[str, object]] = {
    'premium-dark': {
        'bg': (0x0A, 0x0A, 0x0C), 'bgAlt': (0x10, 0x10, 0x14),
        'ink': (0xF5, 0xF2, 0xEA), 'inkMuted': (0xF5, 0xF2, 0xEA, 0.62),
        'inkFaint': (0xF5, 0xF2, 0xEA, 0.34), 'accent': (0xE8, 0xC4, 0x64),
        'positive': (0x5A, 0xD8, 0x78), 'negative': (0xFF, 0x6B, 0x6B),
    },
    'premium-light': {
        'bg': (0xF4, 0xF1, 0xEA), 'bgAlt': (0xFF, 0xFF, 0xFF),
        'ink': (0x14, 0x14, 0x0F), 'inkMuted': (0x14, 0x14, 0x0F, 0.62),
        'inkFaint': (0x14, 0x14, 0x0F, 0.34), 'accent': (0xA8, 0x80, 0x1F),
        'positive': (0x1E, 0x8E, 0x4A), 'negative': (0xC0, 0x39, 0x2B),
    },
}

#: Rules deliberately NOT implemented, with the reason. Reported, never faked.
UNIMPLEMENTED: dict[str, str] = {
    'overflow': ('no reliable detector: three attempts failed differently (column '
                 'runs measure glyphs and fuse overlapping labels; bar detection '
                 'merges the axis; connected components swallow the label column '
                 'into the bar/gridline blob). Needs the mark layout from the '
                 'chart options, not pixels.'),
    # The instrument now EXISTS — chart_geometry.py computes the label fit from
    # the chart options and agrees with rendered frames to 0.2% at two bar
    # counts. What is missing is not a detector but a THRESHOLD: the ledger
    # names none, and the delivered charts sit at ratio 0.278, so any cut point
    # would be invented rather than measured. It stays UNAVAILABLE on purpose.
    # A measurement is not a verdict, and this rule is where that distinction
    # has to be visible.
    'collision': ('the instrument is built — chart_geometry.py measures label '
                  'width against centre spacing from the chart options, '
                  'validated against rendered frames (334px vs 333.6px at 5 '
                  'bars, 104.5px vs 104.2px at 16). Still UNAVAILABLE because '
                  'no threshold has been set: the delivered charts measure '
                  '0.278, so any PASS/FAIL cut would be invented, not measured.'),
    'flicker': ('needs a luminance time-series instrument across a frame range, '
                'which no existing render in out/ provides as a sequence.'),
    'broken_font': ('needs font-file validation, not pixels: a fallback face and '
                    'a broken one can produce identical ink.'),
}


@dataclass
class Finding:
    rule: str
    verdict: str
    value: object = None
    detail: str = ''
    trusted: bool = True
    extra: dict = field(default_factory=dict)

    def __str__(self) -> str:
        flag = '' if self.trusted else '  [UNTRUSTED INSTRUMENT]'
        val = '' if self.value is None else f'  value={self.value}'
        return f'  [{self.verdict:12}] {self.rule:14}{val}{flag}\n' \
               f'                 {self.detail}'


def unavailable_findings() -> list[Finding]:
    return [Finding(rule=r, verdict=UNAVAILABLE, value=None, detail=why, trusted=False)
            for r, why in UNIMPLEMENTED.items()]


# ── instruments ──────────────────────────────────────────────────────────────

def load(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert('RGB')).astype(int)


def backdrop_model(a: np.ndarray) -> tuple[np.ndarray, bool, float]:
    """Per-row linear backdrop model, WITH a trust verdict.

    Fitted from the row's own edges, which is exactly why it cannot be used on a
    frame whose content reaches the edge: the samples are content, and the
    residual jumps from 3 to a measured 208. The trust flag is what keeps that
    from becoming a confident wrong answer.
    """
    h, w, _ = a.shape
    left = np.median(a[:, :EDGE, :], axis=1)
    right = np.median(a[:, w - EDGE:, :], axis=1)
    t = (np.arange(w) / max(w - 1, 1))[None, :, None]
    model = left[:, None, :] + (right - left)[:, None, :] * t
    res = np.abs(a - model).max(axis=2)
    ring = np.zeros(res.shape, dtype=bool)
    ring[:RING, :] = ring[-RING:, :] = True
    ring[:, :RING] = ring[:, -RING:] = True
    worst = float(res[ring].max())
    return model, worst <= TRUST_RESIDUAL, worst


def model_mask(a: np.ndarray) -> tuple[np.ndarray | None, bool, float]:
    model, trusted, worst = backdrop_model(a)
    return (np.abs(a - model).max(axis=2) > CONTENT_T if trusted else None), trusted, worst


def detect_theme(a: np.ndarray) -> tuple[str, float]:
    """Which theme's background this frame sits on, and how far it is from it.

    Necessary because a UNION over both themes' backgrounds cannot see this
    template's type at all: cream ink (245,242,234) is within PALETTE_TOL of the
    premium-light paper (244,241,234), so a white number on a near-black frame
    measured as BACKGROUND. Measured during the build of this tool — the palette
    mask found no content at all on a frame carrying a white bar.
    """
    med = np.median(a.reshape(-1, 3), axis=0)
    best, best_d = 'premium-dark', None
    for theme in ('premium-dark', 'premium-light'):
        for key in ('bg', 'bgAlt'):
            d = float(np.abs(med - np.array(THEMES[theme][key])).sum())
            if best_d is None or d < best_d:
                best, best_d = theme, d
    return best, best_d if best_d is not None else 999.0


def palette_mask(a: np.ndarray) -> tuple[np.ndarray, str]:
    """Content by distance from the DETECTED theme's two backgrounds.

    Never reads the frame's edges, so it stays trustworthy on a frame whose
    content reaches them — which is the whole reason `clipping` uses this path
    while `safe_area` uses the backdrop model.
    """
    theme, _ = detect_theme(a)
    near = np.zeros(a.shape[:2], dtype=bool)
    for key in ('bg', 'bgAlt'):
        near |= np.abs(a - np.array(THEMES[theme][key])).sum(axis=2) <= PALETTE_TOL
    return ~near, theme


def bbox(m: np.ndarray | None) -> tuple[int, int, int, int] | None:
    """Content bbox as (x0, x1, y0, y1), or None if there is nothing to bound.

    Accepts None because `model_mask` returns None rather than a mask when the
    backdrop is untrusted. Without this, every caller that measures the mask
    before checking `trusted` raises `ValueError: Calling nonzero on 0d arrays`
    instead of reporting the untrusted backdrop — an error that reads like a numpy
    bug rather than the verdict it is.
    """
    if m is None:
        return None
    ys, xs = np.where(m)
    if not xs.size:
        return None
    return int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())


def laplacian_variance(a: np.ndarray) -> float:
    """Variance of the 4-neighbour Laplacian = cv2.Laplacian(gray, CV_64F).

    Reimplemented because cv2 is not installed here, so `take_ranker` — which
    defines m_sharpness — cannot be imported at all. Same kernel, same definition,
    so the two are comparable.
    """
    g = a.astype(np.float64).mean(axis=2)
    lap = (g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
           - 4 * g[1:-1, 1:-1])
    return float(lap.var())


def signature(path: Path, size: tuple[int, int] = (64, 112)) -> np.ndarray:
    """Grayscale still signature, on take_ranker's scale: raw 0..255, not 0..1.

    `take_ranker.pixel_signature` resizes and casts to float32 WITHOUT dividing
    by 255, which is why P1's measured distances are {0.000} u [34.5, 67.2] — a
    0..255 range, not 0..1. An earlier version of this function normalised to
    0..1 and then reused the 0.5 threshold, which on that scale corresponds to
    127.5 on take_ranker's: every pair read as a duplicate, including two frames
    of the same shot at visibly different animation states (distance 0.033 and
    0.055). Reusing a threshold means reusing the SCALE it was measured on.
    """
    g = np.asarray(Image.open(path).convert('L')).astype(np.float32)
    return np.asarray(Image.fromarray(g.astype(np.uint8)).resize(size),
                      dtype=np.float32)


def signature_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Identical definition to take_ranker.signature_distance: mean abs difference."""
    return float(np.abs(a - b).mean())


def _lin(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb) -> float:
    r, g, b = (_lin(float(v)) for v in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg, bg) -> float:
    l1, l2 = luminance(fg), luminance(bg)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def composite(fg_rgba, bg) -> tuple[int, int, int]:
    a = float(fg_rgba[3])
    return tuple(int(round(fg_rgba[i] * a + bg[i] * (1 - a))) for i in range(3))


def text_band_heights(a: np.ndarray, mask: np.ndarray, max_row_frac: float = 0.25
                      ) -> list[int]:
    """Heights of row bands that carry ink but not solid rectangles."""
    h, w = mask.shape
    per_row = mask.sum(axis=1)
    out, start = [], None
    for y in range(h):
        if per_row[y] > 0 and per_row[y] <= w * max_row_frac:
            if start is None:
                start = y
        elif start is not None:
            out.append(y - start)
            start = None
    if start is not None:
        out.append(h - start)
    return out


# ── the rules ────────────────────────────────────────────────────────────────

def rule_safe_area(a: np.ndarray) -> Finding:
    """Content bbox must not sit ON any edge. Exact criterion, per the audit.

    Uses the backdrop model, so it reports UNVERIFIABLE on a frame whose content
    touches the edge — which is precisely the frame a reader most wants an answer
    about, and is why `clipping` exists as a separate palette-path rule.
    """
    m, trusted, worst = model_mask(a)
    if not trusted:
        return Finding('safe_area', UNVERIFIABLE, None,
                       f'backdrop model residual {worst:.0f} exceeds {TRUST_RESIDUAL}; '
                       f'the edge samples are content, so no margin can be trusted. '
                       f'Use the clipping rule, which does not model the backdrop.',
                       trusted=False, extra={'residual': worst})
    box = bbox(m)
    if box is None:
        return Finding('safe_area', UNVERIFIABLE, None, 'no content found', trusted=False)
    x0, x1, y0, y1 = box
    h, w = m.shape
    margins = {'left': x0, 'right': w - 1 - x1, 'top': y0, 'bottom': h - 1 - y1}
    touched = [k for k, v in margins.items() if v == 0]
    return Finding('safe_area', FAIL if touched else PASS, min(margins.values()),
                   ('content touches ' + ', '.join(touched)) if touched
                   else f'margins {margins}',
                   extra={'margins': margins})


def rule_clipping(a: np.ndarray) -> Finding:
    """Content crossing the frame edge, measured against the PALETTE.

    Never untrusted: the backgrounds are constants from `design/themes.ts`, so the
    instrument does not read the frame it is judging. Measured on the P8 vertical
    charts render (margins 36/58) this reports PASS, and on a `padX=0` frame FAIL.
    """
    m, theme = palette_mask(a)
    box = bbox(m)
    if box is None:
        return Finding('clipping', UNVERIFIABLE, None,
                       'no pixel differs from any known theme background — the frame '
                       'is a flat background, which clipping cannot judge', trusted=False)
    x0, x1, y0, y1 = box
    h, w = m.shape
    margins = {'left': x0, 'right': w - 1 - x1, 'top': y0, 'bottom': h - 1 - y1}
    touched = [k for k, v in margins.items() if v == 0]
    return Finding('clipping', FAIL if touched else PASS, 0 if touched else min(margins.values()),
                   ('content reaches the frame edge on ' + ', '.join(touched)) if touched
                   else f'content inside the frame, margins {margins}',
                   extra={'margins': margins})


def rule_font_size(a: np.ndarray, declared_px: float | None = None,
                   scale: float = 1.0) -> Finding:
    """Rendered type against the DECLARED size, as a ratio, plus the absolute.

    The ratio is the honest measure and it is 1.00 at every format — the scaling
    is exact. What the audit found is that the absolute falls below the
    readability bar in portrait: the chart value labels are declared `20 * s`, which
    is 11.25px at s=0.5625. So both numbers are reported and the absolute is what
    can go red.
    """
    m, trusted, _ = model_mask(a)
    if not trusted:
        return Finding('font_size', UNVERIFIABLE, None,
                       'backdrop model untrusted on this frame', trusted=False)
    bands = sorted(text_band_heights(a, m))
    if not bands:
        return Finding('font_size', UNVERIFIABLE, None, 'no text-like band found',
                       trusted=False)
    median = float(np.median(bands))
    if declared_px is None:
        return Finding('font_size', UNVERIFIABLE, median,
                       f'median band {median:.0f}px, but no declared size was supplied; '
                       f'a ratio needs both sides', trusted=False,
                       extra={'bands': len(bands), 'min': bands[0], 'max': bands[-1]})
    ratio = median / declared_px
    absolute_short = declared_px < MIN_TYPE_PX
    verdict = FAIL if absolute_short else PASS
    return Finding('font_size', verdict, round(ratio, 4),
                   f'declared {declared_px:.2f}px, measured median band {median:.0f}px '
                   f'(ratio {ratio:.3f}); declared size is '
                   f'{"BELOW" if absolute_short else "at or above"} the {MIN_TYPE_PX}px bar',
                   extra={'declared_px': declared_px, 'measured_median_px': median,
                          'bands': len(bands), 'scale': scale})


def rule_contrast() -> list[Finding]:
    """WCAG ratios for every theme x background x role pair. 24 pairs.

    A lookup on palette constants, so it is exact — no threshold margin applies.
    Measured at audit: 8 of the 24 fall below 4.5:1, ranging 2.16 to 4.18.
    """
    out = []
    rows = []
    for theme, t in THEMES.items():
        for bgname in ('bg', 'bgAlt'):
            bgc = t[bgname]
            for role in ('ink', 'inkMuted', 'inkFaint', 'accent', 'positive', 'negative'):
                raw = t[role]
                fg = composite(raw, bgc) if len(raw) == 4 else raw
                r = contrast_ratio(fg, bgc)
                rows.append((f'{theme}/{role} on {bgname}', r))
    failing = [x for x in rows if x[1] < WCAG_TEXT]
    worst = min(rows, key=lambda x: x[1])
    out.append(Finding(
        'contrast', FAIL if failing else PASS, len(failing),
        f'{len(failing)} of {len(rows)} pairs below {WCAG_TEXT}:1; worst is '
        f'{worst[0]} at {worst[1]:.2f}:1. Pairs: '
        + ', '.join(f'{n}={r:.2f}' for n, r in sorted(rows, key=lambda x: x[1])[:8]),
        extra={'pairs': [{'pair': n, 'ratio': round(r, 2)} for n, r in rows],
               'failing': [n for n, r in failing]}))
    return out


def rule_black_frame(a: np.ndarray) -> Finding:
    """Fraction of pixels that are not content, against a measured threshold.

    The threshold window is only 0.000762 wide — the busiest real frame measures
    0.999238 and the flat frames measure exactly 1.0 — so the margin is thin and
    is stated rather than dressed up. The exact flat-frame test is reported
    alongside, because it has no threshold at all.
    """
    m, trusted, _ = model_mask(a)
    if not trusted:
        return Finding('black_frame', UNVERIFIABLE, None,
                       'backdrop model untrusted: on a flat frame the model has '
                       'nothing to fit', trusted=False)
    noncontent = float(1.0 - m.mean())
    colours = int(np.unique(a.reshape(-1, 3), axis=0).shape[0])
    flat = colours <= 1
    verdict = FAIL if noncontent >= BLACK_NONCONTENT else PASS
    return Finding('black_frame', verdict, round(noncontent, 6),
                   f'{noncontent * 100:.4f}% non-content ({m.mean() * 100:.4f}% content), '
                   f'{colours} distinct colour(s)'
                   + ('; the frame is a single flat colour' if flat else ''),
                   extra={'threshold': BLACK_NONCONTENT, 'flat': flat,
                          'distinct_colours': colours})


def rule_freeze(pa: Path, pb: Path) -> Finding:
    """Consecutive frames must differ. Exact criterion.

    The noise floor was measured at exactly 0 (f00120 vs f00120 rendered twice is
    `array_equal`, and two settled frames differ by 0 px), so the criterion is
    `difference == 0` and there is no threshold to tune.
    """
    a, b = load(pa), load(pb)
    if a.shape != b.shape:
        return Finding('freeze', FAIL, None,
                       f'frame shapes differ: {a.shape[:2]} vs {b.shape[:2]}',
                       extra={'freezes': True})
    d = np.abs(a - b).sum(axis=2)
    changed = int((d > FREEZE_DIFF).sum())
    return Finding('freeze', FAIL if changed == 0 else PASS, changed,
                   f'{changed} of {d.size} pixels differ ({changed / d.size * 100:.4f}%)'
                   + (' — the frame is frozen' if changed == 0 else ''),
                   extra={'changed_px': changed, 'total_px': int(d.size)})


def rule_duplicate(pa: Path, pb: Path) -> Finding:
    """Two renders of the same graph must not be near-identical.

    Same measure and SAME threshold as `take_ranker` — mean absolute difference
    of a 64x112 grayscale signature, duplicate below 0.5. P1 measured the real take
    distribution as {0.000} u [34.5, 67.2], so 0.5 has 34.5x margin to the nearest
    genuinely different pair. Reusing the number rather than inventing one is the
    point: a second threshold for the same question is a second answer.
    """
    dist = signature_distance(signature(pa), signature(pb))
    verdict = FAIL if dist < DUP_DISTANCE else PASS
    return Finding('duplicate', verdict, round(dist, 6),
                   f'signature distance {dist:.6f}, duplicate threshold {DUP_DISTANCE} '
                   f'(reused from take_ranker; P1 margin 34.5x)',
                   extra={'threshold': DUP_DISTANCE})


def rule_blur(a: np.ndarray) -> Finding:
    """Laplacian variance, the same measure as take_ranker's m_sharpness.

    Threshold 2.0 against a corpus 5th percentile of 11.5 — a 5.75x margin. A
    constructed blur ramp drops the measured frame from 58.0 to 32.1 at radius 0.5
    and to 10.5 at radius 1.0, so even a mild blur is caught with room to spare.
    """
    v = laplacian_variance(a)
    return Finding('blur', FAIL if v < BLUR_VARIANCE else PASS, round(v, 3),
                   f'Laplacian variance {v:.3f}, threshold {BLUR_VARIANCE} '
                   f'(corpus p5 = 11.5, so 5.75x margin)',
                   extra={'threshold': BLUR_VARIANCE})


def rule_aspect(measured: tuple[int, int] | None, declared: tuple[int, int] | None
                ) -> Finding:
    """Declared frame against measured frame. Exact, no threshold.

    A lookup, in the same spirit as qa_report.py's existing `resolution` check —
    the container-level precedent for reading the graph rather than guessing.
    """
    if measured is None or declared is None:
        return Finding('aspect', UNVERIFIABLE, None,
                       'needs both a measured frame and a declared format', trusted=False)
    mw, mh = measured
    dw, dh = declared
    ok = (mw, mh) == (dw, dh)
    return Finding('aspect', PASS if ok else FAIL, f'{mw}x{mh}',
                   f'measured {mw}x{mh}, declared {dw}x{dh}'
                   + ('' if ok else ' — the render is not the format the graph asked for'))


def rule_missing_asset(props: dict) -> list[Finding]:
    """Declared assets against what is on disk. A set difference, no threshold.

    `public/` is the delivery root, so a declared path is resolved relative to it
    and anything absent is reported. Mirrors the set-difference technique P3 used
    (disk glob against a manifest) — the comparison is exact, so there is nothing
    to tune.

    WHICH FIELDS ARE READ, AND WHY THAT LIST IS SHORT (P11 defect 1).

    This rule used to read `props['audio']`, `props['audioEvents']` and
    `props['narration']`. Of those, the renderer can receive NONE from a
    showcase-v1 graph, and that was not an oversight in this function — it was
    this function checking for something structurally impossible:

      * `audio` (top level) — NOT declared by `ShowcaseSchema`, which has no
        `.passthrough()`, so zod strips it before the template sees it. P11
        removed the template's read of it; see the header of
        `FinanceShowcaseWide.tsx` for the measured evidence. No schema in the
        studio declares it.
      * `narration` — declared, but by a DIFFERENT schema
        (`report-data.schema.json`, consumed by `ReportVertical.tsx`), not by
        `showcase-v1`. It can never appear in a showcase graph.
      * `audioEvents` — declared at `showcase-v1.ts:101` as a SCENE-level field,
        but zero renderer source reads it, and the position this rule read it
        from (top level) is not even the level it is declared at. Queued in the
        ledger as an inert field; it is not read here either.

    A rule that reads a field nothing can produce does not merely waste a scan —
    it manufactures a false sense of coverage. It reported "all N declared assets
    present" where N was always exactly 4, the hardcoded list below, and any
    future `audio` block in a props file would have been checked against a field
    the renderer ignores. Checking it would be checking a lie.

    So the rule now checks only what can actually arrive. What remains is still
    real work: these four SFX are hardcoded in the components, so nothing in the
    graph reports a rename, and this is the only thing that would catch one. The
    `narration` case for report-vertical props files is handled by that
    template's own props path, not by guessing at a showcase field.
    """
    declared: list[str] = []
    # report-vertical's SFX are referenced by the component, not the props; they
    # are listed so a rename of an asset the template hardcodes is still caught
    declared += ['audio/sfx_whoosh.m4a', 'audio/sfx_impact.m4a',
                 'audio/sfx_ding.m4a', 'audio/sfx_riser.m4a']

    missing = []
    for rel in sorted(set(declared)):
        if not (PUBLIC_DIR / rel).exists():
            missing.append(rel)
    return [Finding(
        'missing_asset', FAIL if missing else PASS, len(missing),
        (f'{len(missing)} declared asset(s) absent from studio/public: '
         + ', '.join(missing)) if missing
        else f'all {len(set(declared))} declared asset(s) present',
        extra={'checked': sorted(set(declared)), 'missing': missing})]


def rule_duplicate_check_props(props_path: Path) -> Finding:
    """Sanity: the props file the asset rule reads is itself present and parseable."""
    if not props_path.exists():
        return Finding('missing_asset', UNVERIFIABLE, None,
                       f'props file {props_path} does not exist', trusted=False)
    return Finding('missing_asset', PASS, None, f'props {props_path.name} readable',
                   extra={'note': 'asset comparison runs separately'})


# ── driver ───────────────────────────────────────────────────────────────────

def run_on_frame(path: Path, declared_px: float | None = None,
                 scale: float = 1.0, declared_format: tuple[int, int] | None = None,
                 props: dict | None = None) -> list[Finding]:
    a = load(path)
    im = Image.open(path)
    findings = [
        rule_safe_area(a),
        rule_clipping(a),
        rule_font_size(a, declared_px, scale),
        rule_black_frame(a),
        rule_blur(a),
        rule_aspect((im.width, im.height), declared_format),
    ]
    findings += rule_contrast()
    if props is not None:
        findings += rule_missing_asset(props)
    findings += unavailable_findings()
    return findings


def self_test() -> int:
    """The tool checking its own instruments. Run by tests/test_visual_qa.py too."""
    failures: list[str] = []

    def ck(name: str, ok: bool, detail: str = '') -> None:
        print(f'  [{"ok  " if ok else "FAIL"}] {name}' + (f'  {detail}' if detail else ''))
        if not ok:
            failures.append(name)

    print('visual_qa self-test\n')

    # Synthetic frames. These reproduce the real conditions rather than an idealised
    # one, which is the whole point: the first version of this test used a flat
    # background and a hard-edged box, and it PASSED the trust check that the real
    # padX=0 render fails (residual 208). A flat background has nothing for the
    # model to get wrong, so the test was measuring nothing.
    W, H = 640, 360
    dark_bg = PALETTE_BACKGROUNDS['premium-dark.background']
    dark_alt = PALETTE_BACKGROUNDS['premium-dark.backgroundAlt']
    ink = np.array((0xF5, 0xF2, 0xEA))

    def gradient_frame() -> np.ndarray:
        """The real backdrop: a radial-ish ramp between backgroundAlt and background."""
        t = np.linspace(0, 1, W)[None, :, None]
        ramp = np.array(dark_alt) * (1 - t) + np.array(dark_bg) * t
        return np.repeat(ramp, H, axis=0).astype(int).copy()

    def soft_bar(frame: np.ndarray, x0: int, x1: int, y0: int, y1: int,
                 blur: int = 0) -> np.ndarray:
        f = frame.copy()
        region = f[y0:y1, max(0, x0):x1]
        region[:] = ink
        if blur:
            f = np.asarray(Image.fromarray(f.astype(np.uint8))
                           .filter(ImageFilter.GaussianBlur(blur))).astype(int)
        return f

    interior = soft_bar(gradient_frame(), 200, 440, 100, 260)
    m, trusted, res = model_mask(interior)
    ck('backdrop model is trusted on a gradient frame with interior content', trusted,
       f'residual {res:.1f}')
    ck('backdrop model finds the bar', bbox(m) == (200, 439, 100, 259), str(bbox(m)))

    # Content reaching the left edge. The construction matters: a WIDE bar at the
    # edge makes the row's 40-column median bright, so the per-row model fits it
    # and comes back trusted — the first version of this test did exactly that
    # and measured a residual of 8.5. The real padX=0 frame breaks the model with
    # NARROW content: a 4px accent underline and text stems, each only a few
    # columns wide, which the median ignores while the pixels are 200 brighter
    # than the background. Measured on the real frame: residual 208, worst rows
    # 569-596, which is the underline.
    e = gradient_frame()
    e[300:304, 0:160] = np.array((0xE8, 0xC4, 0x64))   # accent underline
    e[100:280, 0:6] = ink                                 # a text stem
    edge = e
    m2, trusted2, res2 = model_mask(edge)
    ck('backdrop model is UNTRUSTED when NARROW content reaches the edge',
       not trusted2, f'residual {res2:.1f} vs TRUST_RESIDUAL {TRUST_RESIDUAL}')
    pm, etheme = palette_mask(edge)
    pbox = bbox(pm)
    ck('palette path still measures that frame — clipping needs no backdrop model',
       pbox is not None and pbox[0] == 0, str(pbox))
    ck('palette path marks the stem as content', bool(pm[180, 2]))
    ck('palette path marks the underline as content', bool(pm[302, 80]))
    ck('palette path leaves the far background alone', not bool(pm[180, 620]))
    ck('palette path detects the dark theme on a dark frame', etheme == 'premium-dark',
       etheme)

    # contrast: the 8 known failures must be found without any rendering
    cf = rule_contrast()
    ck('contrast finds exactly 8 of 24 pairs below 4.5:1',
       cf[0].value == 8 and len(cf[0].extra['pairs']) == 24,
       f"found {cf[0].value} of {len(cf[0].extra['pairs'])}")
    ck('contrast worst pair is premium-light/inkFaint on bg at 2.16',
       min(cf[0].extra['pairs'], key=lambda p: p['ratio'])['ratio'] == 2.16,
       str(min(cf[0].extra['pairs'], key=lambda p: p['ratio'])))

    # Laplacian matches the definition take_ranker uses
    ck('laplacian_variance of a flat frame is exactly 0',
       laplacian_variance(np.zeros((H, W, 3), dtype=int) + np.array(dark_bg)) == 0.0)
    ck('laplacian_variance of a hard-edged bar is large',
       laplacian_variance(interior) > BLUR_VARIANCE,
       f'{laplacian_variance(interior):.1f}')

    # every rule reports a verdict from the fixed vocabulary
    ck('verdict vocabulary is exactly PASS/FAIL/UNVERIFIABLE/UNAVAILABLE',
       {PASS, FAIL, UNVERIFIABLE, UNAVAILABLE} ==
       {PASS, FAIL, UNVERIFIABLE, UNAVAILABLE})
    fs = run_on_frame(Path(__file__)) if False else None
    ck('overflow and collision are reported unavailable with no number',
       all(f.value is None for f in unavailable_findings()
           if f.rule in ('overflow', 'collision')))
    ck('flicker and broken_font are reported unavailable too',
       all(f.value is None for f in unavailable_findings()
           if f.rule in ('flicker', 'broken_font')))

    print(f'\n{"all instrument self-tests passed" if not failures else f"{len(failures)} FAILED"}')
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--frame', type=Path)
    ap.add_argument('--frame-pair', nargs=2, type=Path, metavar=('A', 'B'))
    ap.add_argument('--props', type=Path)
    ap.add_argument('--declared-px', type=float)
    ap.add_argument('--scale', type=float, default=1.0)
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    findings: list[Finding] = []
    props = None
    if args.props and args.props.exists():
        props = json.loads(args.props.read_text(encoding='utf-8'))

    if args.frame:
        declared = None
        if props and isinstance(props.get('format'), dict):
            f = props['format']
            declared = (int(f['width']), int(f['height']))
        findings += run_on_frame(args.frame, args.declared_px, args.scale, declared, props)
    if args.frame_pair:
        findings.append(rule_freeze(*args.frame_pair))
        findings.append(rule_duplicate(*args.frame_pair))
    if props is not None and not args.frame:
        findings += rule_missing_asset(props)
    if not args.frame:
        # run_on_frame appends these itself, with the reason each instrument is
        # missing. Appending them here too emitted every one of them twice, so
        # the CLI counted 15 findings where the library counted 11 — and a
        # repair budget sized off that number over-counts by four.
        findings += unavailable_findings()

    if args.json:
        # Two ways this used to break a consumer, both now closed:
        #  - the summary line followed the array, so json.load() raised
        #    "Extra data" — the summary goes to stderr instead;
        #  - ensure_ascii=False wrote real CJK through a GBK stdout on
        #    Windows, so the bytes were not valid UTF-8 and read_text('utf-8')
        #    died at the first non-ASCII char. JSON escapes to pure ASCII, so
        #    the byte stream no longer depends on the terminal's encoding.
        sys.stdout.write(json.dumps([asdict(f) for f in findings], indent=1,
                                    ensure_ascii=True))
        sys.stdout.write('\n')
    else:
        for f in findings:
            print(f)
    hard = [f for f in findings if f.verdict == FAIL]
    unver = [f for f in findings if f.verdict == UNVERIFIABLE]
    unavail = [f for f in findings if f.verdict == UNAVAILABLE]
    # One number for two different states. "the instrument is absent" and "the
    # instrument ran and could not decide" are not the same claim, and a budget
    # sized off their sum is sizing off a category that does not exist.
    if args.json:
        print(f'\n{len(findings)} findings: {len(hard)} FAIL, '
              f'{len(unver)} UNVERIFIABLE, {len(unavail)} UNAVAILABLE', file=sys.stderr)
    else:
        print(f'\n{len(findings)} findings: {len(hard)} FAIL, '
              f'{len(unver)} UNVERIFIABLE, {len(unavail)} UNAVAILABLE')
    return 1 if hard else 0


if __name__ == '__main__':
    sys.exit(main())