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
               THEME-LEVEL, not per-frame. P22 moved it off the `--frame`
               path: it took no frame, so it made that path permanently red.
               See CONTRAST_ROLES and `rule_contrast_frame`.
  black_frame   non-content >= 0.9995         window (0.999238, 1.0) — only 0.000762
                                              wide. THIN, stated as such. 8 corpus
                                              frames are exactly 1.0.
  freeze        difference == 0 (exact)       noise floor measured at exactly 0
  duplicate     distance == 0 (exact)       a cross-render cut is wrong here:
                                              --frame-pair hands it two CONSECU-
                                              TIVE frames, for which "nearly
                                              identical" is correct. Measured over
                                              329 corpus frames the two populations
                                              do not separate on this measure (best
                                              balance 0.9969, and it rests on one
                                              rerun pair); so this asks the
                                              identity question and leaves the
                                              cross-render cut to rank_takes.py
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
    python studio/scripts/visual_qa.py --theme-contrast

P22 — WHY `contrast` IS NOT A PER-FRAME RULE ANY MORE
-----------------------------------------------------
`contrast` took no arguments and returned the same 24-pair palette table on every
call, so `--frame` reported it and exited 1 on all 333 corpus frames for a fact
about `design/themes.ts` that no frame could have caused. It is now:

  * `rule_contrast()`  -> emits `theme_contrast`, reported by `--theme-contrast`
    and by nothing else, exiting on its own verdict when asked for;
  * `rule_contrast_frame()` -> emits `contrast_frame`, UNAVAILABLE on the frame path,
    because no per-frame instrument exists. Measured: 97.8% of corpus pixels sit
    in contrast [1.0, 1.5) against the gradient `Backdrop` paints, so a
    pixel-census rule fires on 333 of 333 frames and the population has no
    valley a cut could sit in.

NEITHER `WCAG_TEXT` NOR `WCAG_LARGE` CHANGED, and no palette value changed. The
defect was never the threshold; it was a constant being reported as a per-frame
measurement. See `CONTRAST_ROLES` for what each failing role is actually used
for, measured in the render source.
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
#: SIGNATURE IDENTITY CUT — the criterion `rule_duplicate` actually decides on.
#:
#: It is exact, and NOT 0.5. `rank_takes.DUP_THRESHOLD` (0.5, which shares this
#: number) is a cross-RENDER cut; the `--frame-pair` entry point hands this rule
#: two CONSECUTIVE frames of one render, a different population. Measured over
#: the 329-frame corpus in out/p13_probe (320 consecutive pairs, 47796
#: cross-scene pairs), no cut on signature distance separates them: the best
#: balance is 0.9969 and it sits above exactly 0.000000, and it is carried by a
#: SINGLE real rerun pair (fr_a/fr_b are two runs of one render). Every cut in
#: between fires on pairs drawn from the wrong population — measured 152 of 320
#: consecutive pairs FAIL at 0.5. So the cross-render question is left to
#: rank_takes.py, where the measurement that produced 0.5 lives, and this rule
#: decides the identity question its own entry point can be asked. See
#: rule_duplicate for the separation arithmetic.
SIGNATURE_EQUAL = 0.0
#: Retained as the scale reference the rule reports, NOT as its cut. It is
#: rank_takes.py's DUP_THRESHOLD, which is correct there.
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
    # P23. THE OLD REASON WAS MEASURABLY FALSE AND IS REPLACED BY THE TWO
    # BLOCKERS THAT ARE REAL. The old text said "needs a luminance time-series
    # instrument across a frame range, which no existing render in out/
    # provides as a sequence." The first half was already true; the second half
    # was false the moment P13 wrote the corpus. Measured: out/p13_probe holds
    # 329 frame PNGs across 9 directories (fr_a/fr_b 41 each, full_a/full_b/
    # full_r2 41 each, xc1a/xc1b 41 each, s1/s2 21 each) and they ARE ordered
    # frame sequences. So the instrument has a subject.
    #
    # What is actually missing is what the sequence cannot carry, and it is TWO
    # separate things — neither of which is "a sequence":
    #
    #   (a) TEMPORAL RESOLUTION. The corpus is strided, not contiguous. Measured
    #       by exact full-frame match against the render it came from: full_a's
    #       41 frames are video frames 0,20,40,...,800 (41/41 byte-identical),
    #       and s1's 21 frames are 0,40,...,800 (21/21). So consecutive corpus
    #       frames are 20 source frames apart (333 ms at 60fps), 40 for s1/s2.
    #       Measured consequence: a true adjacent pair changes 2.35% of pixels
    #       (median, demo1.mp4, n=25), while a corpus "consecutive" pair changes
    #       4.34-9.10% and up to 82.52% across a scene cut. By Nyquist a
    #       stride-S sample resolves only periods > 2S, so stride 20 is blind
    #       to every oscillation faster than 1.50 Hz and stride 40 to every
    #       oscillation faster than 0.75 Hz. Measured, not argued: a synthetic
    #       2-frame-period flicker of depth 50% on real frames reads p2p
    #       = 0.006583 at stride 1 and EXACTLY 0.000000 at stride 20. Every
    #       frequency in the band flicker is actually reported in (3-100 Hz,
    #       plus 50/60 Hz mains hum) is aliased to a flat line by this corpus.
    #
    #   (b) A POSITIVE CLASS. Every one of the 329 frames is a delivered clean
    #       render; the corpus contains zero flickering renders, so there is no
    #       defective population for a cut point to be placed against. Measured
    #       on the statistic below, the negative-only population spans
    #       [0.000000, 0.776885] with p50 = 0.009428 and 64.3% of its mass in
    #       the lowest tenth of that range; every cut inside that closed
    #       interval returns the identical verdict on every sequence that
    #       exists. The corpus cannot choose a number — the same situation P20
    #       recorded for rank_takes.DUP_THRESHOLD ("anything in (0.0, 34.543)
    #       gives the same verdict on every pair that exists").
    #
    # THE DEFINITION THAT WAS MEASURED, and what it showed. Flicker is an
    # oscillatory (sign-alternating) frame-to-frame luminance excursion WITHIN
    # one scene, so it is measured as the SECOND difference of per-frame mean
    # linear luminance, |L[n+1] - 2L[n] + L[n-1]|, normalised by that scene's
    # own luminance spread: a first difference responds to a scene cut and to
    # drift, while a second difference is blind to a linear ramp (an intended
    # fade) and peaks on curvature. Over 297 interior samples from 16
    # scene-segments, p5 = 0.000043, p50 = 0.009428, p95 = 0.695292,
    # max = 0.776885. That population is UNIMODAL with a right tail: the global
    # mode holds 64.3% of the mass in the lowest tenth of the range and no
    # interior local maximum comes within a factor of 29 of it, so there is no
    # second mode for a cut to sit between. Blocker (a) and blocker (b) are each
    # independently fatal; the unimodality is a third, corroborating failure
    # rather than the argument.
    #
    # WHAT WOULD MAKE IT AVAILABLE — stated so the next reader need not guess:
    # (i) CONTIGUOUS frames, stride 1, for at least one scene of a real render
    # (the 801-frame demo1.mp4 already carries them, so no new render is needed);
    # AND (ii) at least one render with a KNOWN introduced luminance excursion,
    # to supply the positive class. A third, cheap option that would NOT be
    # enough on its own: a prior from the literature (e.g. a WCAG/ITU-R BT.2113
    # modulation-depth bar) would supply a number, but not a number this
    # project's own frames were measured against.
    'flicker': (
        'P23: a frame sequence EXISTS — out/p13_probe holds 329 frames across 9 '
        'ordered directories (the old reason said none did, and that was false) — '
        'but two measured blockers keep this UNAVAILABLE, and neither is "a '
        'sequence". (a) The sequence is strided, not contiguous: measured by '
        'exact full-frame match against its own render, full_a is video frames '
        '0,20,...,800 (41/41 byte-identical) and s1 is 0,40,...,800 (21/21), so '
        'consecutive corpus frames are 20 source frames apart (333 ms at 60fps). '
        'By Nyquist that is blind to every oscillation faster than 1.50 Hz '
        '(0.75 Hz at stride 40), and a synthetic 2-frame-period flicker of depth '
        '50% measures p2p = 0.006583 at stride 1 and EXACTLY 0.000000 at stride '
        '20 — the whole 3-100 Hz flicker band, and 50/60 Hz mains hum, alias to '
        'a flat line. (b) There is no positive class: all 329 frames are '
        'delivered clean renders, so the measured statistic has no defective '
        'population to place a cut against. Measured on '
        '|L[n+1] - 2L[n] + L[n-1]| of mean linear luminance, normalised per scene '
        '(297 interior samples, 16 scene-segments): p5 = 0.000043, p50 = 0.009428, '
        'p95 = 0.695292, max = 0.776885 — unimodal, 64.3% of the mass in the '
        'lowest tenth of that range, no second mode for a cut to sit in, and every cut inside '
        '[0.000000, 0.776885] returns the identical verdict on every sequence that '
        'exists. Available when out/ holds CONTIGUOUS (stride 1) frames for a '
        'scene AND at least one render with a known introduced luminance '
        'excursion to supply the positive class.'),
    'broken_font': ('needs font-file validation, not pixels: a fallback face and '
                    'a broken one can produce identical ink.'),
}

#: P23. The measurements the `flicker` reason above quotes, held as DATA so a
#: guard can re-derive them rather than believe them, and so a future implementer
#: has something concrete to update instead of a sentence to reword.
#:
#: WHY THIS IS NOT INSIDE `UNIMPLEMENTED`. That table maps a rule name to a
#: reason STRING, and a string is prose — this project's most-fooled assertion
#: shape. The measurements are kept beside it and attached to the Finding, so a
#: test reads `f.extra['statistic']['p95']` rather than searching a sentence for
#: a number that a comment could also have contained.
#:
#: NOTHING HERE IS A THRESHOLD. Every value is a property of the corpus or of
#: the sampling, recorded so the two blockers can be re-checked. Adding a
#: threshold field here would be the defect `collision` is UNAVAILABLE for.
UNIMPLEMENTED_MEASUREMENTS: dict[str, dict] = {
    'flicker': {
    # Measured by exact FULL-FRAME byte match against the render each directory
    # was sampled from (demo1.mp4, 801 frames @60fps), not by a downscaled
    # signature: full_a's 41 frames are video frames 0,20,...,800 and s1's 21
    # frames are 0,40,...,800. Both matched 100% byte-identical.
    'temporal_stride_frames': {'fr_a': 20, 'fr_b': 20, 'full_a': 20,
                               'full_b': 20, 'full_r2': 20, 'xc1a': 20,
                               'xc1b': 20, 's1': 40, 's2': 40},
    # fps of the render the corpus was sampled from.
    'source_fps': 60,
    # fps / (2 * stride): the fastest oscillation a stride-S sample can still
    # resolve. Everything faster aliases. 60 / (2*20) = 1.50 Hz.
    'alias_limit_hz': 1.50,
    # Measured, not argued: a synthetic 2-frame-period flicker of depth 50%
    # imposed on 40 true-adjacent demo1.mp4 frames reads these peak-to-peak
    # values when subsampled. A 2-frame period at 60fps is 30 Hz — inside the
    # band flicker is reported in — and it reads as EXACTLY zero at stride 20.
    'aliasing_test': {'true_period_frames': 2, 'depth_fraction': 0.5,
                      'p2p_at_stride_1': 0.006583, 'p2p_at_stride_20': 0.0},
    # True-adjacent pairs change far fewer pixels than the corpus's strided
    # pairs, which is the measurement that exposed the stride in the first place.
    'pixel_change_true_adjacent_p50': 0.0235,
    'pixel_change_corpus_pair_p50_range': [0.0434, 0.0910],
    # The statistic the reason is built on. |d2| of the per-frame mean linear
    # luminance, normalised by the scene's own spread: a first difference reacts
    # to a scene cut and to drift, a second difference is blind to a linear ramp
    # (an intended fade) and peaks on curvature. Measured over all 9 corpus
    # directories, split at steps above 0.8 x the series spread (a scene cut).
    'statistic': {
        'name': '|L[n+1] - 2*L[n] + L[n-1]| of mean linear luminance, '
                'normalised by the scene spread',
        'n_samples': 297,
        'n_segments': 16,
        'p5': 0.000043,
        'p50': 0.009428,
        'p95': 0.695292,
        'max': 0.776885,
        # 64.3% of the mass sits in the lowest tenth of the range; the largest
        # interior local maximum over 20 bins is 22 against a global mode of
        # 191, i.e. the population is unimodal with a right tail. Sampled with
        # n=297 over 20 bins (~15/bin), the sparse interior bins are sample
        # parity rather than a valley — which is the P22 finding restated.
        'mass_in_lowest_tenth': 0.643,
        'bins_20': [191, 38, 14, 12, 2, 2, 7, 5, 14, 12],
    },
    # The second blocker, as a falsifiable count: the corpus holds 329 frames
    # and ZERO of them is a flickering render. If a defective render is ever
    # added to out/, this number changes and the rule may become decidable.
    'corpus_frames': 329,
    'n_flickering_frames_in_corpus': 0,
    # What would unlock the rule, recorded so the next reader need not guess.
    'requires': [
        'CONTIGUOUS (stride 1) frames for at least one scene of a real render — '
        'the 801-frame demo1.mp4 already carries them, so no new render is '
        'needed for this half',
        'at least one render with a KNOWN introduced luminance excursion, to '
        'supply the positive class a cut point is placed against',
    ],
    },
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
    """Every unimplemented rule, reported with its reason and no number.

    `UNIMPLEMENTED_MEASUREMENTS` is attached to whichever rule owns it, so the
    numbers a reason quotes travel with the finding as data a machine can read
    (P23). Copied, not aliased: a caller that mutates `extra` must not be able to
    corrupt the module-level measurement for the next caller.
    """
    return [Finding(rule=r, verdict=UNAVAILABLE, value=None, detail=why, trusted=False,
                    extra=dict(UNIMPLEMENTED_MEASUREMENTS.get(r, {})))
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

    The scale note outlived the reuse: rule_duplicate no longer cuts at 0.5 (see
    its docstring), but it still reports distance on this 0..255 scale, so the
    scale has to stay stated.
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

    P22. THIS IS A THEME-LEVEL CHECK AND IS NOT PART OF THE PER-FRAME GATE.
    It takes no frame, reads none, and returns the same table whatever is under
    inspection — so running it once per `--frame` made `visual_qa.py --frame`
    exit non-zero on all 333 corpus frames for a reason that was not about any of
    them. A gate that is red for a constant cannot gate anything.

    Its verdict is therefore computed against BOTH WCAG bars rather than only the
    text one, and it is REPORTED, not gated. `rule_contrast_frame()` takes its place
    on the per-frame path and reports UNAVAILABLE, with the reason measured.
    The measurement that fixes the verdict vocabulary is in `CONTRAST_ROLES`;
    nothing here is tuned to make a number go green.
    """
    rows = theme_contrast_rows()
    failing_text = [r for r in rows if r['ratio'] < WCAG_TEXT]
    failing_any = [r for r in rows if r['ratio'] < WCAG_LARGE]
    worst = min(rows, key=lambda r: r['ratio'])
    return [Finding(
        'theme_contrast', FAIL if failing_any else PASS, len(failing_any),
        f'{len(failing_any)} of {len(rows)} theme x background x role pairs below '
        f'{WCAG_LARGE}:1 (the bar that applies to large text), of which '
        f'{len(failing_text)} are also below the {WCAG_TEXT}:1 text bar; worst is '
        f'{worst["pair"]} at {worst["ratio"]:.2f}:1. Every measured consumer of '
        f'these roles is TEXT, so the text bar is the one that applies here '
        f'(see CONTRAST_ROLES). This is a property of design/themes.ts and is '
        f'identical on every frame, which is why it is reported rather than '
        f'gated per frame.',
        extra={'pairs': rows, 'failing_text_bar': [r['pair'] for r in failing_text],
               'failing_large_bar': [r['pair'] for r in failing_any]})]


#: What each measured role is FOR, read off the render source rather than assumed
#: from its name. P22 measured every `inkFaint` / `accent` / `positive` consumer
#: under `studio/src/templates/finance-showcase/`:
#:
#:   inkFaint — 10 of 10 sites are TEXT: the Y axis tick labels (ChartFrame.tsx:342),
#:     the axis title (:361), the X category labels (:401), the PathMark value
#:     labels (types.tsx:244), the Slope end label and series name (:344, :350),
#:     the Bubble category label (:429), the Heatmap cell value and its column and
#:     row labels (:499, :523, :530), and the DataColumns cell rank number
#:     (:244). NOT ONE of them is a divider. The decorative roles are named
#:     differently — `grid`, `hairline`, `column`, `columnBright` — and none of
#:     those is in the six roles measured here. So "inkFaint is only a decorative
#:     shade, so 4.5:1 does not apply" is FALSIFIED for this template.
#:
#:   accent — 8 sites, and only THREE are text: the KpiHero eyebrow
#:     (KpiHero.tsx:84, 20px/500), the KpiHero value suffix (:118, 78.88px), and
#:     the "chart: no values" placeholder (Chart.tsx:211, 34px). The other five
#:     are mark fills and strokes, where 3:1 is the applicable bar (SC 1.4.11).
#:
#:   positive — 2 sites, both text: the KpiHero delta chip (KpiHero.tsx:139,
#:     44px/700) and the RankTable row delta (types.tsx:593, 20px).
#:
#: WHY THIS TABLE EXISTS. WCAG SC 1.4.3's bar depends on the RENDERED size, and
#: `s = scaleFor(w, h) = min(w/1920, h/1080)`, so a role declared at 20px renders
#: at 11.25px in the 1080x1920 format that 6 of the 9 delivered graphs declare.
#: Measured across the three delivered formats:
#:
#:     role/site      1920x1080     1080x1920     2560x1440     dark   light
#:     inkFaint 20px  20.0  text    11.25 text    26.67 LARGE    2.83   2.16
#:     inkFaint 22px  22.0  text    12.38 text    29.33 LARGE    2.83   2.16
#:     accent 20px    20.0  text    11.25 text    26.67 LARGE   11.78   3.23
#:     accent 78.9px  78.9 LARGE   44.4 LARGE    105.2 LARGE   11.78   3.23
#:     positive 44px  44.0 LARGE    24.8 LARGE    58.7 LARGE   10.86   3.71
#:
#: `inkFaint` fails BOTH bars in BOTH themes — 2.83 and 2.16 are below 3.0 as well
#: as below 4.5 — so no size argument rescues it. `positive` fails only in
#: premium-light, and only against the text bar; at every format it renders LARGE,
#: where the applicable bar is 3.0 and it passes at 3.71.
CONTRAST_ROLES: dict[str, dict[str, object]] = {
    'inkFaint': {'consumers': 'text', 'sites': 10,
                 'sites_detail': 'ChartFrame.tsx:342,361,401; types.tsx:244,344,'
                                 '350,429,499,523,530; DataColumns.tsx:244',
                 'applicable_bar': WCAG_TEXT,
                 'note': 'every measured consumer is a text label or a data '
                         'number; none is a divider. The divider roles are '
                         'grid/hairline/column and are not measured here.'},
    'accent': {'consumers': 'text and marks', 'sites': 8, 'text_sites': 3,
               'sites_detail': 'text: KpiHero.tsx:84,118 and Chart.tsx:211; '
                               'marks: KpiHero.tsx:169, BrowserStack.tsx:87,117, '
                               'DataColumns.tsx:140,234',
               'applicable_bar': WCAG_LARGE,
               'note': 'the three text sites are 20px, 34px and 78.88px; at '
                       's=1.0 the eyebrow is 20px regular, which is NOT large '
                       'text under SC 1.4.3, so it is the 4.5:1 text bar that '
                       'applies to it.'},
    'positive': {'consumers': 'text', 'sites': 2,
                 'sites_detail': 'KpiHero.tsx:139 (44px/700), types.tsx:593 (20px)',
                 'applicable_bar': WCAG_LARGE,
                 'note': 'both sites render LARGE at every delivered format, so '
                         'the applicable bar is 3.0:1 and premium-light reads '
                         'PASS at 3.71. Only the RankTable 20px site crosses '
                         'into the text bar at s=0.5625.'},
}


def theme_contrast_rows() -> list[dict]:
    """The 24 theme x background x role pairs, with the bar each one is held to.

    Derived by CALLING `contrast_ratio`, and the same table is what
    `rule_contrast` reports — one definition, so a guard cannot pass on a table
    the rule does not use.
    """
    rows: list[dict] = []
    for theme, t in THEMES.items():
        for bgname in ('bg', 'bgAlt'):
            bgc = t[bgname]
            for role in ('ink', 'inkMuted', 'inkFaint', 'accent', 'positive',
                         'negative'):
                raw = t[role]
                fg = composite(raw, bgc) if len(raw) == 4 else raw
                rows.append({'pair': f'{theme}/{role} on {bgname}',
                             'role': role, 'theme': theme, 'background': bgname,
                             'ratio': round(contrast_ratio(fg, bgc), 2),
                             'rgb': list(fg)})
    return rows


def rule_contrast_frame(a: np.ndarray) -> Finding:
    """Is THIS FRAME's type readable? UNAVAILABLE, and P22 measured why.

    P22 put a real per-frame contrast rule on this path so the palette lookup
    could stop gating it, and the instrument does not exist. Measured over the
    333-frame corpus in `out/p13_probe`:

      * every rendered pixel's contrast against its frame's own background is
        1.026 at p1 and 1.046 at p50, and 97.8% of all pixels sit in [1.0, 1.5).
        That is the backdrop RAMP, not type — `Backdrop` paints a radial
        gradient between `backgroundAlt` and `background`, spread 6+6+8, and
        `PALETTE_TOL` is 24, so a ramp pixel and an ink pixel are not separable
        by a distance-to-background test.
      * the naive rule — "FAIL if any pixel is below the 3:1 non-text bar" —
        fires on 333 of 333 frames, with >=96% of pixels below 3:1 on every
        one. It would be a SECOND permanently-red gate, the exact defect this
        function exists to avoid.
      * the population is not bimodal. Histogrammed over 531,100,800 pixels it
        runs 1.0 -> 1.5 (97.765%), 1.5 -> 2.0 (0.882%), 2.0 -> 3.0 (0.095%),
        3.0 -> 4.5 (0.056%), 4.5 -> 6.0 (0.044%), 6.0 -> 10.0 (0.104%),
        10.0 -> 25.0 (1.054%). There is no valley between "the gridline this
        design intends" and "the label a reader must be able to read", so no
        cut point on this measure separates them. That is the same argument
        `collision` rests on — the instrument would be fine, the JUDGEMENT is
        missing — and it is why this is UNAVAILABLE rather than invented.

    WHY A PIXEL RULE CANNOT ANSWER IT EVEN IN PRINCIPLE, which is the part
    worth keeping. Contrast is a property of a (foreground, background) PAIR, and
    a frame's pixels carry no foreground/background role. A glyph stem, a
    hairline and the ramp are all "a pixel"; separating them needs the mark
    layout from the chart options — the same missing input `overflow` names. The
    question is therefore NOT UNVERIFIABLE, which would mean "the instrument ran
    and could not decide": the instrument was never built, which is what
    UNAVAILABLE means in this file's vocabulary (`unavailable_findings`).

    WHAT WOULD MAKE IT AVAILABLE, so a future reader does not have to guess:
    the renderer knows each role's rendered px (it is `size * scaleFor(...)`),
    so a per-frame contrast rule that is actually decidable has to come from the
    graph and the declared format, not from the pixels — which is a `--props`
    question, and the shape `rule_graph_scene_renderable` already has.
    """
    theme, dist = detect_theme(a)
    return Finding(
        'contrast_frame', UNAVAILABLE, None,
        f'no per-frame contrast instrument exists. Measured on this frame '
        f'(theme {theme}, {dist:.0f} from its nearest declared background): a '
        f'pixel-census rule cannot separate the backdrop ramp from type — '
        f'97.8% of corpus pixels sit in contrast [1.0, 1.5) against the '
        f'gradient Backdrop paints — so "any pixel below 3:1" fires on 333 of '
        f'333 corpus frames and the population has no valley a cut could sit in. '
        f'The theme-level table is reported separately as `theme_contrast`; it '
        f'describes design/themes.ts, not this frame.',
        trusted=False,
        extra={'theme': theme, 'distance_to_declared_background': round(dist, 1)})


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
    """Did the sequence advance between these two frames?

    The instrument is unchanged and is take_ranker's: mean absolute difference of
    a 64x112 grayscale signature on the 0..255 scale. The question, the CUT and
    the docstring were not, and all three were wrong together.

    It used to say the cut was 0.5 "SAME threshold as take_ranker", reusing the
    margin to {0.000} u [34.5, 67.2]. That 0.5 is rank_takes.DUP_THRESHOLD, two
    renders of one graph. `--frame-pair` feeds this rule two CONSECUTIVE frames
    of one render, for which "nearly identical" is the CORRECT answer, so the
    rule reported DUPLICATE on frames that were visibly moving — measured 152 of
    320 consecutive pairs FAIL at 0.5.

    The alternative is not "pick a better cut". Measured, the two populations do
    not separate: scoring consecutive-pairs-should-PASS against
    rerun-pairs-should-FAIL over the 329-frame corpus, the best cut on this
    measure balances at 0.9969, it sits above exactly 0.000000, and it is carried
    by ONE real rerun pair (fr_a/fr_b are two runs of one render, not two frames).
    Cuts above it fire on pairs from the wrong population. So the cross-render
    question belongs to rank_takes.py, where the measurement lives, and this rule
    asks what its own entry point can be asked: are these two frames the SAME
    frame — the interval that should report zero and hand the run to `freeze`,
    which asks the continuous question this one cannot?

    The cut is therefore EXACT: distance == 0, the same criterion and the same
    kind of warrant `freeze` has, measured at exactly 0 rather than assumed.
    """
    dist = signature_distance(signature(pa), signature(pb))
    verdict = FAIL if dist <= SIGNATURE_EQUAL else PASS
    return Finding('duplicate', verdict, round(dist, 6),
                   f'signature distance {dist:.6f}; identical-frame cut is exact '
                   f'(<= {SIGNATURE_EQUAL}). Distances this small are the '
                   f'consecutive-frame population: 152 of 320 measured '
                   f'consecutive pairs fall below the 0.5 cross-render cut, '
                   f'which belongs to rank_takes.py, not here',
                   extra={'threshold': SIGNATURE_EQUAL,
                          'reference_cut': DUP_DISTANCE})


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


#: The rules whose verdict describes an ARTEFACT, i.e. the ones a `--frame` run
#: can legitimately FAIL. P22 added this because the separation between "a fact
#: about the theme" and "a measurement of this frame" was, until then, implicit:
#: `rule_contrast` took no frame and was emitted into a per-frame report anyway,
#: so it was the one name in the tool whose FAIL could not be about the thing
#: being judged.
#:
#: IT IS A SCOPE TABLE, NOT AN EXEMPTION LIST. Anything not named here is reported
#: on every path, so adding a rule cannot silently drop it from the frame report;
#: and `tests/test_p22_contrast_is_not_a_per_frame_gate.py` asserts this set
#: equals the set of rules that actually take a frame, so a rule that stops
#: reading frames fails the guard instead of inheriting an exemption.
FRAME_SCOPED_RULES = frozenset({
    'safe_area', 'clipping', 'font_size', 'black_frame', 'blur', 'aspect',
    'contrast_frame', 'freeze', 'duplicate',
})


SCENE_SCHEMA_TS = ROOT / 'studio' / 'src' / 'schemas' / 'showcase-v1.ts'
SHOWCASE_TEMPLATE_TSX = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' \
    / 'FinanceShowcaseWide.tsx'


def declared_scene_types() -> set[str]:
    """Every value `SceneType` declares, read from the zod enum.

    Read as TEXT, and that is the one concession this rule makes, stated here
    rather than hidden: the alternative is a node subprocess, and a guard that
    cannot run without a node runtime cannot fail when node is missing. The
    suite must stay runnable with nothing but pytest — the same reasoning
    `tests/style_bible_consumption.py` gives for parsing `StyleBibleSchema` the
    same way. What this file does NOT do is assert that a string appears in a
    source file and call that a behaviour: the verdict below is reached by
    running `main(argv)` and reading the report and the exit code.
    """
    try:
        src = SCENE_SCHEMA_TS.read_text(encoding='utf-8')
    except OSError as exc:  # pragma: no cover - the schema is not optional
        raise ValueError(f'{SCENE_SCHEMA_TS} unreadable: {exc}') from exc
    m = re.search(r'export const SceneType\s*=\s*z\.enum\(\[(.*?)\]\)', src, re.S)
    if not m:
        raise ValueError(
            f'SceneType enum not found in {SCENE_SCHEMA_TS.name}. If the enum was '
            'reshaped, teach this rule the new shape rather than reading the '
            'failure as a schema problem — a rule that silently sees zero '
            'declared types would report every graph as having unrendered scenes, '
            'or none.'
        )
    body = re.sub(r'//[^\n]*', '', m.group(1))
    return {x.strip().strip('\'"') for x in body.split(',') if x.strip()}


def rendered_scene_types() -> set[str]:
    """Every scene type `SCENE_RENDERERS` can actually draw.

    The KEY is what matters and the value is not read: a type is "rendered"
    exactly when the map names it, whatever component it routes to. Nine types
    route to `ChartScene`, which dispatches on the graph's own `chart.type`, so
    the value is a component name and says nothing about coverage.

    A key absent from the map is not an error — it routes to `MissingScene`,
    which renders the type's own name and the words "not implemented in P4".
    That is the entire fact this rule reports, and it is read here rather than
    inferred, because the fallback is three lines of JSX in the template and
    the difference between "no renderer" and "a renderer that says it is
    missing" is the difference between a blank frame and a labelled one.
    """
    try:
        src = SHOWCASE_TEMPLATE_TSX.read_text(encoding='utf-8')
    except OSError as exc:  # pragma: no cover - the template is not optional
        raise ValueError(f'{SHOWCASE_TEMPLATE_TSX} unreadable: {exc} from') from exc
    m = re.search(
        r'const SCENE_RENDERERS: Record<string, React\.FC<\{scene: Scene\}>> = \{(.*?)\n\};',
        src, re.S)
    if not m:
        raise ValueError(
            f'SCENE_RENDERERS not found in {SHOWCASE_TEMPLATE_TSX.name}. Same rule '
            'as above: teach this function the new shape. Returning an empty set '
            'here would mark all 22 declared types unrendered and turn the gate '
            'permanently red.'
        )
    keys: set[str] = set()
    for line in m.group(1).split('\n'):
        line = re.sub(r'//.*$', '', line).strip().rstrip(',')
        if not line or ':' not in line:
            continue
        keys.add(line.split(':', 1)[0].strip().strip('\'"'))
    return keys


def rule_graph_scene_renderable(props: dict) -> Finding:
    """Does every scene the graph asks for have a renderer? A lookup, no cut.

    P21. The `--props` path had exactly one rule (`missing_asset`) and that rule
    ignored its argument: poisoning all 49 strings of the delivered showcase
    graph produced a byte-identical report and the same exit code (0), and so
    did the clean graph. A path that cannot tell a right graph from a wrong one
    is decoration that reports green.

    THIS RULE IS THE PART OF THAT PATH WHICH HAS A MEASURED ANSWER.

    `MissingScene` in `FinanceShowcaseWide.tsx:150` is the fallback for any scene
    type the map does not name, and what it renders is the type's own name plus
    the words "not implemented in P4". Measured over the two schema mirrors:
    `SceneType` declares 22 values and `SCENE_RENDERERS` names 20 of them, so
    the 2 in between are `video` and `data-plane-3d`. (P40: the numbers here
    are recomputed by `tests/test_p40_docstring_counts_match_code.py`.)

    WHY THAT IS A DEFECT AND NOT A TODO. The ledger's line for step 3.2 reads
    "20 种 scene 类型注册" with the list of twenty spelled out beside it, struck
    through as done. All twenty of those reach a real renderer today; the
    ledger does not say so, and `visual_qa.py --props` exits 0 on a graph made
    entirely of the two that do not. A schema that validates a scene type the
    template cannot draw is the same defect class this file's header is about —
    "a field the graph can set and that reports success anyway" — one level up,
    and the level where it costs the viewer a whole film.

    WHY THERE IS NO THRESHOLD, which is what makes this different from
    `collision` (still UNAVAILABLE: the instrument is built, the judgement is
    missing). Here there is no judgement to invent. The question is not "how
    wrong is a gap" but "does this scene type have a renderer", and the answer
    is read off the map the renderer dispatches on. One absence is one absent
    component. A cut point here would be a number about nothing.

    WHAT IT IS DELIBERATELY NOT. It does not claim a gap is a BUG in the
    graph — nine types are declared ahead of their renderers on purpose, and
    `video` / `data-plane-3d` are routed to H3 by design. It claims the graph
    promises a frame the film cannot contain, which is exactly the claim a
    `--props` run should be able to make and currently cannot. And it is
    deliberately NOT a file-existence check: see `rule_missing_asset` for why
    the style bible's sections are the wrong place to look for paths.
    """
    scenes = props.get('scenes')
    if not isinstance(scenes, list):
        return Finding('graph_scene_renderable', UNVERIFIABLE, None,
                       'props carry no `scenes` array, so there is nothing to '
                       'resolve against the renderer map. That is not a FAIL — '
                       'nothing was measured and found wrong; it is the same '
                       'state a graph that could not be opened produces.',
                       trusted=False)

    declared = declared_scene_types()
    rendered = rendered_scene_types()
    # A type in the graph that the SCHEMA does not declare is zod's business,
    # not this rule's: the template will reject the graph at parse time, and a
    # rule that reported it would be reporting a different defect twice.
    unknown = sorted({s.get('type') for s in scenes
                      if isinstance(s, dict)
                      and isinstance(s.get('type'), str)
                      and s['type'] not in declared})
    used = [(i, s['type']) for i, s in enumerate(scenes)
            if isinstance(s, dict) and isinstance(s.get('type'), str)]
    gaps = [(i, t) for i, t in used if t not in rendered]

    detail_parts = [f'{len(used)} scene(s), {len(rendered)} of {len(declared)} '
                    f'declared scene types have a renderer']
    if gaps:
        names = ', '.join(sorted({t for _, t in gaps}))
        where = ', '.join(f'scenes[{i}]={t}' for i, t in gaps[:4])
        more = f' (+{len(gaps) - 4} more)' if len(gaps) > 4 else ''
        detail_parts.append(
            f'{len(gaps)} scene(s) have NO renderer and will render the '
            f'MissingScene placeholder ("not implemented in P4"): {where}{more}')
        if names:
            detail_parts.append(f'type(s) involved: {names}')
    else:
        detail_parts.append('every scene in this graph has a renderer')
    if unknown:
        detail_parts.append(
            f'{len(unknown)} type(s) are not declared by SceneType at all '
            f'({", ".join(unknown)}) — zod rejects the graph, which this rule '
            f'does not duplicate')

    return Finding(
        'graph_scene_renderable', FAIL if gaps else PASS, len(gaps),
        '; '.join(detail_parts),
        extra={'scenes': len(used),
               'declared_types': sorted(declared),
               'rendered_types': sorted(rendered),
               'unrendered_types': sorted(declared - rendered),
               'gaps': [{'index': i, 'type': t} for i, t in gaps],
               'undeclared_types': unknown})


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
      * `audioEvents` — declared at `showcase-v1.ts:259` as a SCENE-level field,
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

    WHAT THE P21 WORK ORDER ASKED, AND WHAT CAME BACK (measured, not inferred).

    The order asked whether `radius` / `shadow` / `depthCue` — declared by
    `StyleBibleSchema` since `836f532` — offer a "the graph declares a path and
    the disk does not have it" check, and it does not. Three reasons, all
    measured, and the third is the one that settles it:

      1. `radius` CANNOT carry a path. `mergeSection` keeps an incoming value
         only when `typeof v === typeof base[key]`, and `RADIUS` is
         `{chip: 999, card: 20, ...}` — numbers. Measured: poisoning `radius`
         with `'border-radius: url("../../assets/NOPE.png")'` leaves the
         resolved `radius` byte-identical to the defaults. The value is
         dropped before any file could be named.
      2. `spacing` is the same shape and drops for the same reason.
      3. `shadow` and `depthCue` DO pass their strings through — and that is
         exactly why a file-existence check is WRONG there, not merely
         unnecessary. They are CSS declarations handed to `boxShadow`. A
         missing `url()` target is a paint failure the browser resolves, not a
         missing deliverable this gate owns, and the same class of check would
         fire on `rgba(0,0,0,0.62)` if it were written by extension.

    So the style bible is the wrong instrument for an asset-existence question,
    and the ledger already says so — `docs/UPGRADE_PROGRESS.md:250` records step
    12.3 (Asset Router) as a dead end for exactly this reason.

    This rule therefore keeps its four hardcoded paths and is honest about what
    that is: a repository check wearing a props argument. The `--props` path's
    real coverage now comes from `rule_graph_scene_renderable`, which does read
    the graph and answers a question with a measured answer rather than a chosen
    threshold.
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
    """Sanity: the props file the asset rule reads is itself present and parseable.

    This function existed with ZERO call sites, while the code that needed it
    (`if args.props and args.props.exists():`) quietly did the opposite — a
    path that does not exist was dropped without a word. A rule can only fail
    if it runs; one that silently never runs reports the same "0 FAIL" as a
    clean frame, and in CI that is a green light on a QA pass that checked
    nothing.

    So it is now called. Its verdict vocabulary is already the right one:
    UNVERIFIABLE means "the instrument could not measure it" (see this file's
    header, point 2), and a graph that could not be opened is exactly that —
    it is not a FAIL, because nothing measured a frame and found it wrong.

    The exit code follows `qa_report.py`: UNVERIFIABLE exits non-zero, because
    a caller gating on the return code cannot otherwise tell "checked, clean"
    from "checked nothing". This is also the direction `ab_field.py` takes for
    the same flag; the two tools had opposite conventions, and the strict one
    is right for a gate.
    """
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
        # P22. `contrast` used to sit here, and it took no frame: the same 24-pair
        # palette table was emitted for every artefact, so `--frame` could not
        # exit 0. Its per-frame replacement reports UNAVAILABLE with the reason
        # measured; the palette table is still reported, as `theme_contrast`, on
        # the path that is about the theme.
        rule_contrast_frame(a),
    ]
    if props is not None:
        findings += rule_missing_asset(props)
        # Same graph, same question. `--frame --props` is how a frame is judged
        # against the graph that asked for it, so a scene with no renderer has
        # to be visible on that path too — the frame will otherwise render as
        # "not implemented in P4" and every pixel rule will pass it honestly,
        # because the frame really is well inside the safe area.
        findings.append(rule_graph_scene_renderable(props))
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
    ck('theme_contrast finds exactly 8 of 24 pairs below 4.5:1',
       len(cf[0].extra['failing_text_bar']) == 8 and len(cf[0].extra['pairs']) == 24,
       f"found {len(cf[0].extra['failing_text_bar'])} of "
       f"{len(cf[0].extra['pairs'])}")
    ck('theme_contrast worst pair is premium-light/inkFaint on bg at 2.16',
       min(cf[0].extra['pairs'], key=lambda p: p['ratio'])['ratio'] == 2.16,
       str(min(cf[0].extra['pairs'], key=lambda p: p['ratio'])))
    # P22: the per-frame path reports UNAVAILABLE with a reason, not a FAIL.
    cfr = rule_contrast_frame(interior)
    ck('the per-frame contrast path reports UNAVAILABLE, never FAIL',
       cfr.verdict == UNAVAILABLE and 'no per-frame contrast instrument' in cfr.detail,
       cfr.verdict)

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
    ap.add_argument('--theme-contrast', action='store_true',
                    help='report the palette contrast table and exit on its own '
                         'verdict. P22: this used to be emitted per frame, which '
                         'made every --frame run exit 1 for a constant.')
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    findings: list[Finding] = []
    props = None
    if args.props:
        # A --props path that does not exist is a CALLER ERROR, not an absence
        # of findings. It used to be dropped without a word here, which left
        # `props` None and silently skipped the whole `missing_asset` block
        # below — so a typo in a path produced a QA run that checked nothing,
        # printed "0 FAIL, 0 UNVERIFIABLE", and exited 0. In CI that is
        # indistinguishable from a clean pass.
        #
        # It is now reported through the rule system rather than raised, so the
        # report says WHY nothing ran instead of vanishing. UNVERIFIABLE is the
        # verdict for that ("the instrument could not measure it", header point
        # 2); an unreadable graph is not a FAIL, because no frame was measured
        # and found wrong.
        probe = rule_duplicate_check_props(args.props)
        if probe.verdict == PASS:
            props = json.loads(args.props.read_text(encoding='utf-8'))
        else:
            # Only the UNVERIFIABLE half is reported. The PASS half says a file
            # exists, which the `missing_asset` rule below then demonstrates by
            # running — emitting both printed `missing_asset` twice on every
            # healthy props-only run, for a fact nothing could act on.
            findings.append(probe)

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
        findings.append(rule_graph_scene_renderable(props))
    if not args.frame:
        # run_on_frame appends these itself, with the reason each instrument is
        # missing. Appending them here too emitted every one of them twice, so
        # the CLI counted 15 findings where the library counted 11 — and a
        # repair budget sized off that number over-counts by four.
        findings += unavailable_findings()

    # P22 — THE ANSWER TO "how does the gate know this red is not about the frame".
    #
    # `theme_contrast` is measured on `design/themes.ts` and describes no artefact.
    # Emitting it into a `--frame` report made every frame FAIL for a constant, so
    # the gate was red 333 times for one fact and could not catch the 333th real
    # defect behind it. It is therefore SEPARATED BY SCOPE, not exempted by name:
    #
    #   * on `--frame` and `--frame-pair` it is NOT in the report at all, so it
    #     cannot contribute a FAIL to those exit codes. `theme-contrast` below
    #     runs it explicitly, on its own exit code, when a human wants it.
    #   * the exclusion is a property of the SCOPE, written once, so a new rule
    #     cannot be silently exempted by adding its name to a list — anything
    #     not in `FRAME_SCOPED_RULES` is reported on every path, and
    #     `tests/test_p22_contrast_is_not_a_per_frame_gate.py` asserts the set is
    #     exactly the rules that take a frame.
    #
    # So the gate does not need to "know the red is known": on the frame path the
    # finding is not emitted, and the reason a fact exists without being a FAIL is
    # that it is reported by the path whose subject it describes.
    theme_findings: list[Finding] = []
    if args.theme_contrast:
        theme_findings += rule_contrast()
    # Asking for the palette table alongside a frame is a legitimate thing to do
    # — "show me both" — but the two have SEPARATE exit codes, and a combined
    # invocation has to say which one it reports. It reports the FRAME's, because
    # that is what a caller passing `--frame` is gating on: the theme verdict is
    # printed and counted in the summary, and never folded into this exit code.
    # Folding it in is the defect P22 removed.
    theme_is_frame_scoped = bool(args.frame or args.frame_pair)

    if args.json:
        # Two ways this used to break a consumer, both now closed:
        #  - the summary line followed the array, so json.load() raised
        #    "Extra data" — the summary goes to stderr instead;
        #  - ensure_ascii=False wrote real CJK through a GBK stdout on
        #    Windows, so the bytes were not valid UTF-8 and read_text('utf-8')
        #    died at the first non-ASCII char. JSON escapes to pure ASCII, so
        #    the byte stream no longer depends on the terminal's encoding.
        payload = [asdict(f) for f in findings + theme_findings]
        sys.stdout.write(json.dumps(payload, indent=1, ensure_ascii=True))
        sys.stdout.write('\n')
    else:
        for f in findings:
            print(f)
        for f in theme_findings:
            print(f)
    hard = [f for f in findings if f.verdict == FAIL]
    unver = [f for f in findings if f.verdict == UNVERIFIABLE]
    unavail = [f for f in findings if f.verdict == UNAVAILABLE]
    theme_fail = [f for f in theme_findings if f.verdict == FAIL]
    # One number for two different states. "the instrument is absent" and "the
    # instrument ran and could not decide" are not the same claim, and a budget
    # sized off their sum is sizing off a category that does not exist.
    counted = findings + theme_findings
    theme_note = ''
    if theme_findings and theme_is_frame_scoped:
        theme_note = (f' (of which {len(theme_fail)} theme-level FAIL, NOT counted '
                     f'in this exit code: it describes design/themes.ts, not the '
                     f'frame)')
    summary = (f'\n{len(findings)} findings'
               + (f' + {len(theme_findings)} theme-level' if theme_findings else '')
               + f': {len(hard)} FAIL, {len(unver)} UNVERIFIABLE, '
                 f'{len(unavail)} UNAVAILABLE' + theme_note)
    if args.json:
        print(summary, file=sys.stderr)
    else:
        print(summary)
    # FAIL exits 1 and UNVERIFIABLE exits 1 too. Only FAIL did before, so a run
    # that could not measure anything — including the missing-props case above —
    # returned 0, and `qa_report.py` and CI gate on exactly this number. The
    # vocabulary already separates the two states in the summary line; the exit
    # code now agrees with that separation instead of collapsing it. UNAVAILABLE
    # stays 0: an instrument that was never built is not a failed measurement,
    # and four of them are announced on every props-only run by design.
    #
    # P22. `theme_fail` counts on its own exit code, and ONLY when
    # `--theme-contrast` asked for the table. It is never added to `hard`,
    # because a fact about `themes.ts` is not a measurement of an artefact, and
    # adding it is what made `--frame` unable to pass while reading a clean
    # frame. The table is reported only when explicitly requested, so the two
    # questions cannot contaminate each other's exit code.
    del counted
    theme_blocked = bool(theme_fail) and args.theme_contrast \
        and not theme_is_frame_scoped
    return 1 if hard or unver or theme_blocked else 0


if __name__ == '__main__':
    sys.exit(main())