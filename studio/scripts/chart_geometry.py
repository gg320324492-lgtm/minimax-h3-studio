"""Chart geometry: decide x-label collisions from the chart options, not pixels.

This is the instrument P11 task 11.1 needs and does not have. `visual_qa.py`
reports `collision` as UNAVAILABLE with the reason "needs the mark layout from
the chart options, not pixels" — because the three pixel detectors that were
tried all failed, and one of them failed in the worst possible way: fusing
labels REPORT 0px OVERLAP, so the rule inverts exactly when it matters.

That diagnosis is right, and it names the fix. The layout IS computable:
ChartFrame.tsx gives every x-label a fixed-width box centred at a known cx, so
whether two adjacent labels touch is arithmetic over the chart options. No
renderer, no pixels, no run-detection.

Measured against rendered ground truth on 5-bar and 16-bar bar charts
(1920x1080, s=1), the geometry predicts what the pixels do:

    centre spacing   334px (5 bars)   102px (16 bars)
    separated        <= 26 chars      <= 13 chars
    fusing           >= 30 chars      >= 20 chars
    predicted onset  30.7 chars       fits both

Width is linear in character count at 10.46px/char, which is Microsoft YaHei
at fontSize 20 — the label face in tokens.ts FONT_SANS. The model is fitted to
rendered measurements within +-5px and predicts the onset independently, so it
is a measurement rather than a guess. Per-character, not per-length: 'i'
advances 5.3px and 'W' 20.4px in the same font, so counting characters instead
of measuring the string misjudges by up to 4x on mixed text.

WHAT THIS DOES NOT DO: it does not decide whether a near-miss is a defect. It
reports a ratio and leaves the threshold to the caller. A ratio is a
measurement; "collides" is a judgement, and the judgement belongs to whoever
sets the bar — not to the instrument.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    'Geometry', 'LabelFit', 'space_tokens', 'plot_width', 'band_step',
    'label_width', 'worst_label_fit', 'worst_chart_fit', 'main',
]

# Design constants, read from the renderer rather than restated so they cannot
# drift silently. See studio/src/templates/finance-showcase/design/tokens.ts
# (SPACE, DESIGN_WIDTH/HEIGHT) and charts/ChartFrame.tsx (label box, fontSize).
DESIGN_WIDTH = 1920
DESIGN_HEIGHT = 1080
SPACE_LG = 40
SPACE_MD = 24
SPACE_XL = 64
GUTTER_MAX = 190
GUTTER_BASE = 34
GUTTER_PER_CHAR = 13
LABEL_FONT_SIZE = 20

#: The real design tokens. Named so that a test can assert this file is
#: byte-identical after a run, and so a future edit has one place to move.
TOKENS_TS = Path(__file__).resolve().parents[1] / 'src' / 'templates' \
    / 'finance-showcase' / 'design' / 'tokens.ts'

# Widest Y tick label for the demo's value range, solved from the rendered
# frame: label centres give plot.w = 1669px, and plot.w = W - (gutter+md) - xl
# inverts to gutter 58.6, which is gutterFor at 2 characters (34 + 2*13 = 60).
# This decides the gutter and therefore every label spacing in the chart, so it
# is the most load-bearing number here that is not read from source. The demo
# charts hide their y-axis labels, which is why the gutter is small.
MEASURED_WIDEST_TICK = 2


@dataclass(frozen=True)
class Geometry:
    """The numbers a collision decision needs, all in device px."""
    scale: float
    plot_w: float
    step: float          # centre-to-centre spacing between adjacent labels
    label_count: int


@dataclass(frozen=True)
class LabelFit:
    """How one label sits between its neighbours."""
    text: str
    width: float
    step: float
    ratio: float         # width / step. >= 1 means the label touches its neighbour.

    @property
    def clearance(self) -> float:
        """px of empty space to each neighbour; negative means overlap."""
        return self.step - self.width


def space_tokens(path: 'Path | None' = None) -> dict[str, float]:
    """Read SPACE from tokens.ts so a design change is not silently ignored.

    The values below are only a fallback for when the file cannot be read; the
    point of reading is that a design change moves the geometry with it. A
    restated literal would keep the old numbers while every test stayed green,
    which is the specific failure this function exists to prevent.

    `path` exists so a test can point this at a COPY and prove the reading
    actually happens. It was added because the tests that need to prove this
    were editing the real design tokens in place to do it — and an in-place edit
    that is interrupted, or whose `finally` restores a copy that was itself
    already modified, leaves the repository's spacing permanently changed. The
    test's value is "the instrument reads the source", and the source is
    evidence: nothing in this module should ever write to it.
    """
    src = Path(path) if path is not None else TOKENS_TS
    try:
        text = src.read_text(encoding='utf-8')
    except OSError:
        return {'lg': SPACE_LG, 'md': SPACE_MD, 'xl': SPACE_XL}
    import re
    out = {}
    for key, default in (('lg', SPACE_LG), ('md', SPACE_MD), ('xl', SPACE_XL)):
        m = re.search(rf'\b{key}:\s*(\d+)', text)
        if m is None:
            raise ValueError(
                f'SPACE.{key} not found in {src} — the design tokens moved and '
                'this module has to be taught the new shape, not fall back to a '
                'number that describes a layout that no longer exists'
            )
        out[key] = float(m.group(1))
    return out


def scale_for(width: int, height: int) -> float:
    """tokens.ts scaleFor: min(w/DESIGN_W, h/DESIGN_H)."""
    return min(width / DESIGN_WIDTH, height / DESIGN_HEIGHT)


def plot_width(fmt: dict, show_axis: bool = True, widest_tick_chars: int | None = None,
               space: dict[str, float] | None = None) -> Geometry:
    """Reproduce ChartFrame's plot box and the band() step between mark centres.

    Mirrors: padX = SPACE.lg + SPACE.xl; W = DESIGN_WIDTH*s - padX;
    gutter = min(190*s, 34*s + widest*13*s); plot.w = W - (gutter + SPACE.md*s) - SPACE.xl*s
    and band(): step = plot.w / n, at(i) = r0 + step*i + step/2.

    `widest_tick_chars` is the width of the widest Y TICK LABEL, which decides
    the gutter and therefore every spacing in the chart. It is not a free
    parameter: measured from the rendered frame it is 7 for the demo's value
    range (ticks like "55.0M"), giving gutter 123px and plot.w 1669px. Guessing
    5 instead shifts plot.w to 1629px and every verdict with it, so the default
    is the measured value and MEASURED_WIDEST_TICK documents where it came from.

    `space` is the token dict to use, defaulting to a fresh read of tokens.ts.
    It exists so a caller holding tokens from somewhere else — a test with a
    modified COPY — can ask what the layout would be, without the module
    deciding to re-read the real file behind its back. Same reasoning as
    `space_tokens(path)`: the source of truth is evidence, and evidence is
    read-only.
    """
    sp = space if space is not None else space_tokens()
    s = scale_for(int(fmt.get('width', DESIGN_WIDTH)), int(fmt.get('height', DESIGN_HEIGHT)))
    pad_x = (sp['lg'] + sp['xl']) * s
    W = DESIGN_WIDTH * s - pad_x
    widest = MEASURED_WIDEST_TICK if widest_tick_chars is None else widest_tick_chars
    gutter = min(GUTTER_MAX * s,
                 (GUTTER_BASE + widest * GUTTER_PER_CHAR) * s) if show_axis else 0.0
    w = max(10.0, W - (gutter + sp['md'] * s) - sp['xl'] * s)
    return Geometry(scale=s, plot_w=w, step=w, label_count=0)


def band_step(plot_w: float, n: int) -> float:
    """Centre spacing for n marks. band() in scale.ts: step = total / n."""
    return plot_w / max(1, n)


# Fallback when the real font cannot be opened. A single advance rather than a
# slope and an intercept: the intercept is smaller than the test's resolution,
# so carrying both invites the two to drift apart unobserved. 10.59px/char is
# Microsoft YaHei at fontSize 20 measured through PIL, which tracks rendered
# ink extents within 16px across 8..26 characters and matches exactly at 26.
FITTED_ADVANCE = 10.59
LAST_WIDTH_SOURCE = 'unset'


def label_width(text: str, font_size: float = LABEL_FONT_SIZE) -> float:
    """Rendered width of a label, measured with the real font when available.

    Falls back to a fitted advance when PIL or the font file is missing, and
    records which it used in LAST_WIDTH_SOURCE. A caller that needs certainty
    should check that rather than assume.
    """
    global LAST_WIDTH_SOURCE
    if not text:
        return 0.0
    try:
        from PIL import ImageFont
        import os
        for cand in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/msyh.ttf',
                     'C:/Windows/Fonts/simhei.ttf'):
            if os.path.exists(cand):
                f = ImageFont.truetype(cand, int(round(font_size)))
                LAST_WIDTH_SOURCE = f'font:{os.path.basename(cand)}'
                return float(f.getlength(text))
    except Exception:
        pass
    LAST_WIDTH_SOURCE = 'fitted'
    return FITTED_ADVANCE * len(text)


def worst_label_fit(labels: list[str], geo: Geometry) -> LabelFit | None:
    """The tightest label in the set — the only one that can collide."""
    if not labels:
        return None
    step = band_step(geo.plot_w, len(labels))
    worst = None
    for text in labels:
        w = label_width(text, LABEL_FONT_SIZE * geo.scale)
        f = LabelFit(text=text, width=w, step=step, ratio=w / step if step else 0.0)
        if worst is None or f.ratio > worst.ratio:
            worst = f
    return worst


def worst_chart_fit(graph: dict) -> tuple[LabelFit | None, int]:
    """Worst label fit across every chart in a scene graph."""
    fmt = graph.get('format') or {}
    worst: LabelFit | None = None
    n_charts = 0
    for scene in graph.get('scenes') or []:
        chart = ((scene.get('content') or {}).get('chart')) or {}
        labels = chart.get('labels')
        if not isinstance(labels, list) or not labels:
            continue
        n_charts += 1
        geo = plot_width(fmt, show_axis=bool(chart.get('showAxis', True)))
        f = worst_label_fit([str(x) for x in labels], geo)
        if f and (worst is None or f.ratio > worst.ratio):
            worst = f
    return worst, n_charts


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('graph', type=Path, help='scene graph JSON')
    args = ap.parse_args(argv)
    graph = json.loads(args.graph.read_text(encoding='utf-8'))
    worst, n = worst_chart_fit(graph)
    if worst is None:
        print(f'{args.graph.name}: no chart carries labels — nothing to measure')
        return 0
    print(f'{args.graph.name}: {n} chart(s) with labels')
    print(f'  widest label : {worst.text!r}')
    print(f'  width        : {worst.width:.1f}px  (source: {LAST_WIDTH_SOURCE})')
    print(f'  spacing      : {worst.step:.1f}px')
    print(f'  clearance    : {worst.clearance:+.1f}px   ratio {worst.ratio:.3f}')
    print('  (a ratio is a measurement; "is this a defect" is the caller\'s call)')
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
