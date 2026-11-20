"""The frame must own a domain that covers what its marks actually draw.

THE DEFECT THIS EXISTS FOR (P28, acceptance item B-1).

`charts_demo.json`'s `c08_volume` sets `chart.baseline = 40` with values
18..96. `VolumeBars` hangs every bar from that baseline -- the top is
`yOf(baseline + value)`, the foot `yOf(baseline)` -- so the numbers it spans are
58..136. The frame, however, was fitted to `values` alone, giving the domain
[0, 99.84] and an axis reading 0/20/40/60/80. The tallest bars were therefore
drawn at 136 on a scale that stops at ~100, which put six of them outside the
picture: `clipping` and `safe_area` both FAIL, 356 px of content on row 0, for
roughly 1.7 s.

Measured on the delivered film, losslessly (`still.mjs`, frame 1125):
row 0 = 356 px, clipping FAIL, safe_area FAIL, top margin 0. After the repair the
same frame measures row 0 = 0 px, clipping PASS, safe_area PASS, top margin 93.

WHAT IS AND IS NOT PROVEN HERE.

    Proven: from the RENDERED markup, for both values of `showValues`, that no
             bar leaves the picture, that no bar is drawn outside the frame's own
             box, and that the bars are drawn on the axis's scale.
    NOT proven: that the resulting chart reads well. The axis label set changes
             (0/20/40/60/80 becomes 0/50/100) because the chart now describes the
             range it actually occupies; whether that is the axis an author
             wanted is an editorial question this file has no opinion about.

WHY THIS FILE RENDERS INSTEAD OF READING.

A guard that asserts a number appears in the source passes on the comment that
explains the defect, and this project has been fooled by exactly that seven times
(`render.mjs:141` names `qa_final.py` in a comment; P17's agent polluted 1101
lines). Every assertion below is made against markup produced by React. The
harness is the one `test_chart_baseline_is_read.py` already proves works here:
`<Player>` from `@remotion/player` supplies the frame and composition contexts
`useCurrentFrame`/`useVideoConfig` need, so the real `ChartScene` renders under
`renderToStaticMarkup` with no bundle and no Chrome.

BOTH VALUES OF `showValues`, AND WHY THAT IS NOT OPTIONAL.

`showValues` selects the headroom (`ChartFrame`: `showValues ? 0.14 : 0.04`) and
therefore selects the domain this file is about. It is not a cosmetic switch:
measured against the unfixed source, `showValues = true` put the domain at
[0, 109.44] against bars reaching 136 and STILL drew two bars out of the picture.
A guard that rendered only the `showValues = false` half would have gone green on
a source that fails the other half, and vice versa. Both are asserted.

`showValues` is not in `TYPE_OPTIONS.volume`, so a strict reading says a graph
cannot set it there -- but `option()` is deliberately not a runtime gate, the
field is honoured, and it is precisely the switch that moves the domain. Testing
the value a graph may not set is testing the switch, which is the point.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / 'studio'
DEMO = ROOT / 'pipeline' / 'examples' / 'charts_demo.json'

_NPX = shutil.which('npx') or shutil.which('npx.cmd')

#: the values the delivered scene ships, and the baseline it hangs them from
_VALUES = [18, 34, 26, 48, 39, 62, 55, 71, 64, 88, 79, 96]
_BASELINE = 40

#: scene-local frame used for every probe: past the entrance (which the lifecycle
#: caps well inside a 150-frame scene) so a bar is at its own value rather than a
#: progress term, and well before the exit.
_FRAME = 75
_SCENE_FRAMES = 150


# ── the probe ───────────────────────────────────────────────────────────────
# VolumeBars is the only mark drawn with a bottom-square-only border radius, so
# `0 0` selects the bars and not the axis furniture, which also carries a `top:`.
# Raw string: these are JavaScript regexes, and Python would warn about `\s`.
_PROBE = r"""
// tsx runs this through the CLASSIC JSX transform, so React is imported
// explicitly; without it the probe dies with "React is not defined" and every
// test here fails on the harness instead of on the frame.
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {Player} from '@remotion/player';
import {ChartScene} from './src/templates/finance-showcase/charts/Chart';

const scene = __SCENE__;

const html = renderToStaticMarkup(
  <Player
    component={ChartScene}
    inputProps={{scene}}
    durationInFrames={__DUR__}
    fps={60}
    compositionWidth={1920}
    compositionHeight={1080}
    controls={false}
    loop={false}
    initialFrame={__FRAME__}
    acknowledgeRemotionLicense={{companyName: 'p28-guard'}}
    style={{width: 1920, height: 1080}}
  />,
);

const bars = [];
const ticks = [];
// the frame's own top padding, read out of the markup rather than assumed: it is
// what converts a mark's `top` in the chart's coordinate space into a position in
// the 1920x1080 picture, and hardcoding it would let a change to SPACE.lg
// silently move the criterion.
let padTop = null;
for (const m of html.matchAll(/<div style="([^"]*)"[^>]*>([^<]*)</g)) {
  const style = m[1];
  const text = m[2].trim();
  const pad = /padding:\s*([\d.]+)px/.exec(style);
  if (pad) padTop = Number(pad[1]);
  const top = /top:\s*(-?[\d.]+)px/.exec(style);
  if (!top) continue;
  const height = /height:\s*(-?[\d.]+)px/.exec(style);
  const rec = {top: Number(top[1]), height: height ? Number(height[1]) : null, text: text.slice(0, 24)};
  if (/border-radius:[^"]*0 0/.test(style)) bars.push(rec);
  else if (text) ticks.push(rec);
}
console.log(JSON.stringify({padTop, bars, ticks}));
"""


def _volume_scene(show_values: bool, baseline: int | None = _BASELINE) -> dict:
    chart: dict = {'type': 'volume', 'values': list(_VALUES)}
    if baseline is not None:
        chart['baseline'] = baseline
    chart['showValues'] = show_values
    return {
        'id': 'probe',
        'type': 'volume-chart',
        'durationInFrames': _SCENE_FRAMES,
        'camera': {'perspective': 1600},
        'motion': {'preset': 'premium'},
        'content': {'chart': chart},
    }


def _render(scene: dict, frame: int = _FRAME) -> dict:
    """Render one volume scene and return what the markup actually says."""
    if _NPX is None:
        pytest.skip('node/npx not on PATH')
    probe = STUDIO / '__probe_p28_guard.tsx'
    src = (_PROBE.replace('__SCENE__', json.dumps(scene))
                .replace('__DUR__', str(scene['durationInFrames']))
                .replace('__FRAME__', str(frame)))
    try:
        probe.write_text(src, encoding='utf-8')
        proc = subprocess.run(
            [_NPX, 'tsx', str(probe)],
            cwd=STUDIO, capture_output=True, text=True, timeout=300,
            # utf-8, not the locale default: see test_chart_baseline_is_read.py.
            # The failure message is precisely what is lost when it is decoded wrong.
            encoding='utf-8', errors='replace',
        )
        assert proc.returncode == 0, proc.stderr[-3000:]
        line = [l for l in proc.stdout.splitlines() if l.startswith('{')]
        assert line, f'no probe output:\n{proc.stdout}\n{proc.stderr}'
        return json.loads(line[-1])
    finally:
        probe.unlink(missing_ok=True)


# ── the criteria, in one place, so every test judges the same way ───────────

def _picture_edge(got: dict) -> float:
    """Where the picture's top edge sits, in the chart's own coordinates.

    `ChartFrame` draws inside a padded box, so the chart's y = 0 is already
    `padding` px below the top of the 1920x1080 frame. A mark above that line is
    off the picture -- which is the defect, whatever its cause.
    """
    assert got['padTop'] is not None, 'the frame rendered no padding; the probe is broken'
    return -float(got['padTop'])


def _outside_picture(got: dict) -> list[dict]:
    """Every mark the frame drew above the picture's top edge."""
    edge = _picture_edge(got)
    offenders = [b for b in got['bars'] if b['top'] < edge]
    for t in got['ticks']:
        if t['top'] < edge:
            offenders.append({**t, 'kind': 'tick'})
    return offenders


def _outside_frame_box(got: dict) -> list[dict]:
    """Every bar drawn above the frame's own padded box (chart y = 0).

    Stricter than `_outside_picture` and about a different thing: a bar here may
    still be inside the picture, but it is already outside the box the frame laid
    out for the chart, which means the domain did not describe it.
    """
    return [b for b in got['bars'] if b['top'] < 0]


def _axis_scale(got: dict) -> float:
    """Pixels per data unit, recovered from two labelled ticks.

    Deliberately recovered from the RENDERING rather than recomputed from
    `scale.ts`: recomputing would make this file a second implementation of the
    layout, and the two would drift while both stayed green.
    """
    labelled: dict[float, float] = {}
    for t in got['ticks']:
        try:
            value = float(t['text'].replace(',', ''))
        except ValueError:
            continue
        # the label's box top is yOf(value) - 11; the offset cancels in a difference
        labelled[value] = t['top']
    assert len(labelled) >= 2, f'need two numeric ticks to recover a scale, got {labelled}'
    values = sorted(labelled)
    v0, v1 = values[0], values[-1]
    assert v1 != v0, labelled
    return (labelled[v0] - labelled[v1]) / (v1 - v0)


# ── 1. the measurements, for BOTH showValues values ─────────────────────────

@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
@pytest.mark.parametrize('show_values', [False, True],
                         ids=['showValues=false', 'showValues=true'])
def test_no_volume_bar_is_drawn_outside_the_picture(show_values: bool) -> None:
    """THE MEASUREMENT, and the acceptance criterion itself.

    Parametrised over `showValues` because that switch picks the headroom and so
    picks the domain. Against the unfixed source BOTH halves fail -- six bars out
    of the picture at `false`, two at `true` -- so a guard that rendered one half
    would have been green on a source the other half rejects.
    """
    got = _render(_volume_scene(show_values))
    assert len(got['bars']) == len(_VALUES), got

    offenders = _outside_picture(got)
    assert not offenders, (
        f'showValues={show_values}: {len(offenders)} mark(s) drawn above the '
        f"picture's top edge (edge at chart y={_picture_edge(got)}, padding "
        f'{got["padTop"]}px): {offenders}. The bars hang from baseline={_BASELINE} '
        f'and span {min(_VALUES) + _BASELINE}..{max(_VALUES) + _BASELINE}, so the '
        'domain has to reach that far.')


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
@pytest.mark.parametrize('show_values', [False, True],
                         ids=['showValues=false', 'showValues=true'])
def test_no_volume_bar_is_drawn_above_the_frame_box(show_values: bool) -> None:
    """The same failure one step earlier, where it is still unambiguous.

    Chart y = 0 is the top of the box the frame laid out. A bar above it is
    outside the chart even when the padding happens to keep it on screen, so this
    does not depend on `SPACE.lg` at all.
    """
    got = _render(_volume_scene(show_values))
    offenders = _outside_frame_box(got)
    assert not offenders, (
        f'showValues={show_values}: {len(offenders)} bar(s) drawn above the '
        f'frame box: {[b["top"] for b in offenders]}')


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
@pytest.mark.parametrize('show_values', [False, True],
                         ids=['showValues=false', 'showValues=true'])
def test_the_bars_are_drawn_on_the_scale_the_axis_describes(show_values: bool) -> None:
    """The invariant ChartFrame states in its own note.

    "A mark cannot accidentally use a different domain from the axis it is drawn
    against." Every bar shares the baseline foot, so the tallest bar's height is
    its value times the axis scale. This is NOT the check that catches B-1 --
    before the repair the bars and the axis agreed with each other and were both
    wrong about the range -- it guards the neighbouring failure, a mark that
    computes its own scale.
    """
    got = _render(_volume_scene(show_values))
    scale = _axis_scale(got)
    tallest = max(_VALUES)

    foot = max(b['top'] + (b['height'] or 0) for b in got['bars'])
    drawn_height = foot - min(b['top'] for b in got['bars'])

    assert abs(drawn_height - tallest * scale) < 1.0, (
        f'showValues={show_values}: the tallest bar is {drawn_height:.2f}px tall but '
        f'the axis scale ({scale:.4f} px/unit) puts {tallest} at {tallest * scale:.2f}px. '
        'The marks and the axis are on different scales -- one of them is lying.')


# ── 2. the guard can say no ─────────────────────────────────────────────────

#: The geometry the delivered scene produced BEFORE the repair, captured by THIS
#: probe, through THIS harness, against the same scene at HEAD -- not written by
#: hand. Recorded here so the criteria above are known to be able to reject
#: something, which is the only way to tell a guard from a comment.
PRE_FIX = {
    False: {
        'padTop': 40,
        # ticks 0/20/40/60/80 -> domain [0, 99.84], scale 9.1948 px/unit
        'ticks': [{'top': 925.0, 'height': None, 'text': '0'},
                  {'top': 741.11, 'height': None, 'text': '20'},
                  {'top': 557.21, 'height': None, 'text': '40'},
                  {'top': 373.32, 'height': None, 'text': '60'},
                  {'top': 189.42, 'height': None, 'text': '80'}],
        'bars': [{'top': 402.71, 'height': 165.50, 'text': ''},
                 {'top': 255.59, 'height': 312.62, 'text': ''},
                 {'top': 329.15, 'height': 239.06, 'text': ''},
                 {'top': 126.87, 'height': 441.35, 'text': ''},
                 {'top': 209.62, 'height': 358.59, 'text': ''},
                 {'top': -1.86, 'height': 570.07, 'text': ''},
                 {'top': 62.50, 'height': 505.71, 'text': ''},
                 {'top': -84.61, 'height': 652.82, 'text': ''},
                 {'top': -20.25, 'height': 588.46, 'text': ''},
                 {'top': -240.92, 'height': 809.13, 'text': ''},
                 {'top': -158.17, 'height': 726.38, 'text': ''},
                 {'top': -314.48, 'height': 882.69, 'text': ''}],
    },
    True: {
        'padTop': 40,
        # ticks 0/25/50/75/100 -> domain [0, 109.44], scale 8.1323 px/unit
        'ticks': [{'top': 925.0, 'height': None, 'text': '0'},
                  {'top': 721.69, 'height': None, 'text': '25'},
                  {'top': 518.38, 'height': None, 'text': '50'},
                  {'top': 315.08, 'height': None, 'text': '75'},
                  {'top': 111.77, 'height': None, 'text': '100'}],
        'bars': [{'top': 464.33, 'height': 146.38, 'text': ''},
                 {'top': 334.21, 'height': 276.50, 'text': ''},
                 {'top': 399.27, 'height': 211.44, 'text': ''},
                 {'top': 220.36, 'height': 390.35, 'text': ''},
                 {'top': 293.55, 'height': 317.16, 'text': ''},
                 {'top': 106.50, 'height': 504.20, 'text': ''},
                 {'top': 163.43, 'height': 447.28, 'text': ''},
                 {'top': 33.31, 'height': 577.39, 'text': ''},
                 {'top': 90.24, 'height': 520.47, 'text': ''},
                 {'top': -104.94, 'height': 715.64, 'text': ''},
                 {'top': -31.74, 'height': 642.45, 'text': ''},
                 {'top': -169.99, 'height': 780.70, 'text': ''}],
    },
}


@pytest.mark.parametrize('show_values', [False, True],
                         ids=['showValues=false', 'showValues=true'])
def test_the_criteria_reject_the_geometry_the_defect_actually_produced(show_values: bool) -> None:
    """A guard that cannot demonstrate its own failure is a comment.

    The input is not invented: it is what this same probe measured against the
    unfixed source, on this same scene, with these same values. If the criteria
    above ever stop rejecting it, they have gone vacuous and this is what says so.
    """
    pre = PRE_FIX[show_values]
    outside_picture = _outside_picture(pre)
    outside_box = _outside_frame_box(pre)
    assert outside_picture, (
        f'showValues={show_values}: the picture-edge criterion accepted the pre-fix '
        'geometry; it cannot fail')
    assert outside_box, (
        f'showValues={show_values}: the frame-box criterion accepted the pre-fix '
        'geometry; it cannot fail')
    assert min(b['top'] for b in outside_picture) < _picture_edge(pre)


def test_the_scale_criterion_reads_the_axis_the_way_the_render_writes_it() -> None:
    """Same job for the third criterion: prove the recovery is not nonsense.

    The recovered scale has to agree with the captured domain, or the criterion is
    reading the tick labels wrong rather than judging the chart.
    """
    pre = PRE_FIX[False]
    scale = _axis_scale(pre)
    assert abs(scale - 9.1948) < 0.005, scale
    # 918 px of plot height / 99.84 of domain = the same number, computed the
    # other way round, from the numbers the capture recorded.
    assert abs(918 / 99.84 - scale) < 0.005, (918 / 99.84, scale)


# ── 3. the repair is confined to charts that set a baseline ─────────────────

@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
def test_a_volume_chart_without_a_baseline_is_untouched() -> None:
    """`baseline = 0` and no baseline at all must render identically.

    The repair widens the domain from `values` to `baseline + values`. If that
    widening happened for a graph that set no baseline, every volume chart in
    every other film would move by a hair and nobody would be able to say why.
    This is the assertion that keeps the repair inside its blast radius.
    """
    without = _render(_volume_scene(False, baseline=None))
    zero = _render(_volume_scene(False, baseline=0))
    assert [b['top'] for b in without['bars']] == [b['top'] for b in zero['bars']], (
        'setting baseline=0 changed the rendering; the domain is being widened '
        'for charts that did not ask for it')


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
def test_a_large_baseline_that_would_have_pushed_the_bars_off_is_covered() -> None:
    """The delivered baseline is 40; the defect scales with it.

    A baseline near the top of the values is the same defect at a size that is
    impossible to miss, so this pins the guard against being accidentally tuned
    to one number.
    """
    got = _render(_volume_scene(False, baseline=90))
    assert not _outside_picture(got), (
        f'baseline=90 spans {90 + min(_VALUES)}..{90 + max(_VALUES)} and still leaves '
        f'the picture: {_outside_picture(got)}')
    assert not _outside_frame_box(got), _outside_frame_box(got)


# ── 4. the delivered graph is the one under test ────────────────────────────

def test_the_delivered_graph_ships_the_scene_this_file_measures() -> None:
    """Pin the fixture against the film, so this cannot drift into a synthetic case.

    `charts_demo.json` is what P27 measured and what `out/charts_demo.mp4` was
    made from. If the graph changes its baseline or its values, the numbers in
    this file's docstring stop describing the film and this says so.
    """
    doc = json.loads(DEMO.read_text(encoding='utf-8-sig'))
    volumes = [s for s in doc['scenes'] if s['type'] == 'volume-chart']
    assert len(volumes) == 1, [s['id'] for s in volumes]
    chart = volumes[0]['content']['chart']
    assert chart['values'] == _VALUES, chart['values']
    assert chart.get('baseline') == _BASELINE, chart.get('baseline')
    # the probe renders a scene this long because the lifecycle divides the scene
    # into phases; a shorter scene animates differently at the same frame number
    assert volumes[0]['durationInFrames'] == _SCENE_FRAMES, volumes[0]


# ── 5. this file is not a comment ────────────────────────────────────────────

def test_no_assertion_in_this_file_is_neutered() -> None:
    """`assert True or (...)` is a passing assertion and nothing else.

    Written after a mutation survived it. The first version here looked only for
    an assert whose WHOLE test was a boolean constant -- so `assert True or
    offenders` walked straight past it, because `True or X` parses as a `BoolOp`
    and not as a `Constant`. That is the same hole P27's third mutation found in
    its own meta-guard, and it was found the same way: by a mutation, not by
    reading the code.

    So the rule is structural rather than positional: within an assert, a bare
    boolean constant has no meaning. Either the test IS one (always passes or
    always fails) or one of its `or` operands is one (the other operand is dead
    code). `assert x is True` is unaffected -- that constant is compared, not
    evaluated on its own.
    """
    src = Path(__file__).resolve().read_text(encoding='utf-8')

    def is_bare_bool(node: ast.AST) -> bool:
        return (isinstance(node, ast.Constant) and isinstance(node.value, bool))

    neutered = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Assert):
            continue
        if is_bare_bool(node.test):
            neutered.append(node.lineno)
            continue
        for sub in ast.walk(node.test):
            if isinstance(sub, ast.BoolOp) and isinstance(sub.op, ast.Or):
                if any(is_bare_bool(v) for v in sub.values):
                    neutered.append(node.lineno)
                    break
            elif isinstance(sub, ast.UnaryOp) and isinstance(sub.op, ast.Not) \
                    and is_bare_bool(sub.operand):
                neutered.append(node.lineno)
                break
    assert not neutered, (
        f'assert whose test can never fail, at line(s) {sorted(set(neutered))} -- '
        "that is a comment wearing an assertion's syntax")
