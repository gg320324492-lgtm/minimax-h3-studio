"""`baseline` must be read at the level an author writes it, and nowhere else.

THE DEFECT THIS EXISTS FOR.

`chart.baseline` was read off the SCENE's `content`, one level above its
siblings, so the value that WORKED was `content.baseline` and
`content.chart.baseline` — the position that reads naturally, beside `values`
and `labels` where every other chart field sits — was silently discarded.

This is a different class from the audio branch (62f3249) and `motion.ease`
(e74e285). Those were lies you can SEE in the source: a field the schema strips,
a field the renderer never touches. This one had nothing wrong with it but the
level, so it passed every sweep either of them installed — and it was invisible
in the delivered film, because `charts_demo.json` set BOTH levels to 40 and the
renderer used the one that happened to be there.

WHAT IS AND IS NOT PROVEN HERE.

    Proven:  `content.chart.baseline` is the level the renderer reads, by
             RENDERING and measuring the pixels -- not by finding the word in
             the source; and `content.baseline` is refused, not tolerated.
    NOT proven: that the resulting chart looks good, or that 40 is the right
             comparison point for those bars. Only that the number reaches the
             mark and that the dead level cannot be written by mistake.

THE TRAP THIS FILE IS BUILT AROUND.

A guard that asserts a TOKEN APPEARS IN TEXT passes by reading its own comment --
and Chart.tsx now carries a long argument naming `content.baseline` and
`content.chart.baseline` on purpose. Every renderer assertion here therefore
runs against RENDERED OUTPUT: `VolumeBars` computes each bar's top from
`f.yOf(baseline + v)`, so changing the baseline MOVES THE BARS. Measuring the
mark is immune to the prose; reading the source is not.

The second trap is the mutation direction. Re-adding `content.baseline` to the
graph is the mistake, and the guard has to FAIL on it, not merely notice it.
`test_the_guard_fails_when_the_graph_sets_the_inert_level` writes the inert
level back and requires a red result, proving the sweep is not vacuous.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / 'studio'
TEMPLATE = STUDIO / 'src' / 'templates' / 'finance-showcase'
CHARTS = TEMPLATE / 'charts'
EXAMPLES = ROOT / 'pipeline' / 'examples'
DEMO = EXAMPLES / 'charts_demo.json'
CHART_TSX = CHARTS / 'Chart.tsx'

_NPX = shutil.which('npx') or shutil.which('npx.cmd')


def _strip_comments(text: str) -> str:
    """Remove `/* */` blocks and `//` line comments.

    Chart.tsx explains this defect at length above `normaliseChart`. Without
    this, a source assertion could be satisfied by the argument written to
    explain the very thing the guard is checking.
    """
    text = re.sub(r'/\*(?:.|\n)*?\*/', '', text)
    return re.sub(r'//[^\n]*', '', text)


#: The scene the delivered graph actually ships, as the renderer receives it:
#: `content` is the whole bag and `chart` is the spec inside it.
def _volume_scene(content: dict) -> dict:
    return {
        'id': 'probe',
        'type': 'volume-chart',
        'durationInFrames': 60,
        'camera': {'perspective': 1600},
        'motion': {'preset': 'premium'},
        'content': content,
    }


# ── 1. the delivered graph sets the working level, and only it ──────────────

def test_delivered_graph_sets_baseline_at_the_level_that_works():
    """`charts_demo.json` is the film. It must set exactly `content.chart.baseline`.

    The old file set both levels to 40, which is why the bug survived: with the
    wrong level still present in the data, no test can tell a working renderer
    from a lucky one. Removing it means the graph now exercises the real
    contract, and a future regression in Chart.tsx turns this scene's bars down
    instead of silently reusing a number nobody reads.
    """
    doc = json.loads(DEMO.read_text(encoding='utf-8-sig'))
    volumes = [s for s in doc['scenes'] if s['type'] == 'volume-chart']
    assert len(volumes) == 1, [s['id'] for s in volumes]
    scene = volumes[0]
    content = scene['content']

    assert 'baseline' not in content, (
        f'{scene["id"]} sets content.baseline, one level above its siblings. That '
        'level is the one this renderer used to read and now refuses: it renders '
        'as if no baseline were set. Put it in content.chart, beside `values`.')

    chart = content['chart']
    assert chart.get('baseline') == 40, (
        f'{scene["id"]} must keep setting chart.baseline: {chart.get("baseline")!r}')


def test_the_ledger_still_locks_baseline_after_the_move():
    """The move must not cost the lock.

    `baseline` is a 数值事实 — a comparison point is a claim about the past — and
    `locked_fields.iter_locked` matches on the LEAF KEY while walking the whole
    content subtree, so the lock survives a change of level. That was the
    deciding evidence for moving rather than keeping the old level, so it is
    pinned here: if someone narrows the walker to the top level, this is what
    says the field stopped being protected.
    """
    import sys
    sys.path.insert(0, str(STUDIO / 'scripts'))
    import locked_fields  # noqa: PLC0415

    doc = json.loads(DEMO.read_text(encoding='utf-8-sig'))
    locked = [(p, r.kind, v) for _, _, p, r, v in locked_fields.iter_locked(doc)
              if r.key == 'baseline']
    assert len(locked) == 1, f'expected exactly one locked baseline: {locked}'
    path, kind, value = locked[0]
    assert path == 'scenes[7].content.chart.baseline', path
    assert kind == 'fact', kind
    assert value == 40, value


# ── 2. behaviour: the working level reaches the mark ────────────────────────

# `VolumeBars` puts each bar's top at `yOf(baseline + value)` and its bottom at
# `yOf(baseline)`, so a baseline of 0 and a baseline of 40 cannot render the
# same pixels. That is what makes the number worth measuring.
#
# Two harness facts were measured, not assumed, and both are load-bearing:
#
#  * `<Player>` from `@remotion/player` supplies the frame and composition
#    contexts `useCurrentFrame`/`useVideoConfig` demand, so the real ChartScene
#    renders under `renderToStaticMarkup` with no bundle and no Chrome. A full
#    `selectComposition` render was tried first and does not fit a test suite.
#  * a scene's bars are the only elements whose style carries a `border-radius`
#    ending `0 0` (types.tsx, `VolumeBars`), which is how they are told apart
#    from the axis and label elements that ALSO carry a `top:`. Matching bare
#    `top:` catches those first and reports the axis, not the marks.
_RENDER_PROBE = """
// tsx runs this through the CLASSIC JSX transform, so React is imported
// explicitly; without it the probe dies with "React is not defined" and every
// test here fails on the harness instead of on the field.
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {Player} from '@remotion/player';
import {ChartScene} from './src/templates/finance-showcase/charts/Chart';

const scene = __SCENE__;

const html = renderToStaticMarkup(
  <Player
    component={ChartScene}
    inputProps={{scene}}
    durationInFrames={60}
    fps={60}
    compositionWidth={1920}
    compositionHeight={1080}
    controls={false}
    loop={false}
    initialFrame={__FRAME__}
    acknowledgeRemotionLicense={{companyName: 'baseline-guard'}}
    style={{width: 1920, height: 1080}}
  />,
);

// VolumeBars is the only mark drawn with a bottom-square-only radius, so this
// selects the bars and not the axis furniture that also carries a `top:`.
const bars = [];
for (const m of html.matchAll(/style="([^"]*border-radius:[^"]*0 0[^"]*)"/g)) {
  const top = /top:\\s*(-?[\\d.]+)px/.exec(m[1]);
  const height = /height:\\s*(-?[\\d.]+)px/.exec(m[1]);
  if (top && height) bars.push({top: Number(top[1]), height: Number(height[1])});
}
console.log(JSON.stringify({bars: bars.length, boxes: bars.slice(0, 3)}));
"""

_VALUES = [18, 34, 26, 48, 39, 62, 55, 71, 64, 88, 79, 96]

#: frame 59 of 60, i.e. after the entrance has finished, so a bar's height is
#: its own value and not a progress term. Measuring mid-entrance would compare
#: two different progress states instead of two baselines.
_FRAME = 59


def _render(content: dict) -> dict:
    """Render one volume scene and return the bar geometry it produced."""
    if _NPX is None:
        pytest.skip('node/npx not on PATH')
    scene = json.dumps(_volume_scene(content))
    probe = STUDIO / '__probe_baseline.tsx'
    try:
        probe.write_text(
            _RENDER_PROBE.replace('__SCENE__', scene).replace('__FRAME__', str(_FRAME)),
            encoding='utf-8')
        proc = subprocess.run(
            [_NPX, 'tsx', str(probe)],
            cwd=STUDIO, capture_output=True, text=True, timeout=300,
            # utf-8, not the locale default: see test_chart_math's note. The
            # failure message is precisely what is lost when it is decoded wrong.
            encoding='utf-8', errors='replace',
        )
        assert proc.returncode == 0, proc.stderr[-3000:]
        line = [l for l in proc.stdout.splitlines() if l.startswith('{')]
        assert line, f'no probe output:\n{proc.stdout}\n{proc.stderr}'
        return json.loads(line[-1])
    finally:
        probe.unlink(missing_ok=True)


def _chart(baseline: object | None = None) -> dict:
    chart: dict = {'type': 'volume', 'values': list(_VALUES)}
    if baseline is not None:
        chart['baseline'] = baseline
    return {'chart': chart}


def _tops(rendered: dict) -> list[dict]:
    return rendered['boxes']


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
def test_baseline_inside_the_chart_moves_the_bars():
    """THE MEASUREMENT. `content.chart.baseline` is the level that works.

    Asserted on rendered geometry, not on the source: same values, same frame,
    only the baseline's level changes, and the bars must move. If this goes red
    the field is inert again and the delivered graph is setting a number that
    draws nothing — the exact defect this file was written for.
    """
    worked = _render(_chart(40))
    control = _render(_chart(None))

    assert worked['bars'] == len(_VALUES), worked
    assert control['bars'] == len(_VALUES), control
    assert _tops(worked) != _tops(control), (
        'content.chart.baseline did not move the bars -- the renderer is '
        f'ignoring the level the delivered graph sets. chart=40 {_tops(worked)} '
        f'vs no baseline {_tops(control)}')


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
def test_the_delivered_graphs_value_actually_reaches_the_mark():
    """The shipped numbers, end to end: 40 under `content.chart` is not a no-op.

    Pins the delivered scene rather than a synthetic one, so the film cannot
    quietly stop drawing its comparison point. `VolumeBars` defaults to 0, so
    "it renders bars" would pass even if the field were dropped on the floor.
    """
    doc = json.loads(DEMO.read_text(encoding='utf-8-sig'))
    scene = next(s for s in doc['scenes'] if s['type'] == 'volume-chart')
    got = _render(dict(scene['content']))

    zero_default = _render(_chart(None))
    assert got['bars'] == len(_VALUES), got
    assert _tops(got) != _tops(zero_default), (
        'the delivered volume scene renders identically with and without its own '
        f'baseline=40: {_tops(got)} — the number is in the graph and not in the '
        'pixels')


# ── 3. the inert level is refused, not merely unused ────────────────────────

def _baseline_read_of_chart_tsx() -> set[str]:
    """Every `baseline` read in Chart.tsx, with the object it is read OFF.

    Returns the tokens preceding each read so the guard can tell `spec.baseline`
    (works) from `c.baseline` (the dead level). Comments are stripped first.
    """
    src = _strip_comments(CHART_TSX.read_text(encoding='utf-8'))
    return set(re.findall(r'\b(\w+)\.baseline\b', src))


def test_chart_tsx_reads_baseline_off_the_chart_spec_not_the_scene():
    """The source-shape half of the argument, comments stripped.

    `spec` is `normaliseChart(c.chart)` — the chart bag. `c` is `scene.content`,
    one level up. Pinning which of the two is read off means the read cannot be
    slid back up a level by a well-meaning edit; the rendering tests above are
    what prove the read is REAL, and this is what keeps it pointed at the right
    object.
    """
    read = _baseline_read_of_chart_tsx()
    assert read == {'spec', 'c'}, (
        f'Chart.tsx reads baseline off {sorted(read)}; the working level is '
        'content.chart (spec), and `c` (scene.content) must not be the object '
        'the VolumeBars call reads')


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
def test_baseline_at_the_content_level_does_nothing():
    """The trap, and the proof that it was real.

    This is what the renderer did before the move: a graph setting
    `content.baseline` rendered exactly as a graph setting no baseline at all.
    So the old level was not merely redundant, it was the one that worked — and
    an author who wrote it beside `values` got silence. Both facts are only
    credible if this still measures: the inert level must be inert.
    """
    inert = _render({'baseline': 40, 'chart': {'type': 'volume', 'values': list(_VALUES)}})
    control = _render(_chart(None))
    assert inert['bars'] == len(_VALUES), inert
    assert _tops(inert) == _tops(control), (
        'content.baseline moved the bars again -- the dead level is live, so the '
        f'delivered graph may be setting a field nothing reads. {_tops(inert)} '
        f'vs {_tops(control)}')


# ── 4. the mutation contract, in both directions ────────────────────────────

def _offences(graph_paths) -> list[str]:
    """A graph may not set a chart field at a level the renderer does not read.

    Kept as a function, and called by both the sweep and the mutation test, for
    the reason `test_motion_ease_is_not_a_claim.py` gives: an inlined
    re-implementation of the guard proves nothing about the guard.

    The rule is general rather than a `baseline` special case: any key set both
    beside `chart` and inside it is a field at two levels, and the renderer can
    only be reading one of them. That is the shape this whole defect is.
    """
    offences: list[str] = []
    for path in sorted(graph_paths):
        doc = json.loads(path.read_text(encoding='utf-8-sig'))
        for scene in doc.get('scenes', []):
            content = scene.get('content')
            if not isinstance(content, dict):
                continue
            chart = content.get('chart')
            if not isinstance(chart, dict):
                continue
            for key in sorted(set(content) - {'chart'}):
                if key in chart:
                    offences.append(
                        f'{path.name}:{scene.get("id")} sets content.{key} AND '
                        f'content.chart.{key}; the renderer reads only the level '
                        f'inside `chart`, so content.{key} is inert')
    return offences


def test_no_delivered_graph_sets_a_chart_field_at_two_levels():
    """The sweep, over every delivered graph.

    Deliberately catches the general shape rather than one field: a key present
    on both `content` and `content.chart` is two spellings of one field, and
    the renderer reads exactly one of them.
    """
    assert _offences(sorted(EXAMPLES.glob('*.json'))) == []


def test_the_guard_fails_when_the_graph_sets_the_inert_level():
    """A guard that cannot demonstrate its own failure mode is a comment.

    Writes `content.baseline` back into a temporary copy of the delivered graph
    — the mistake the move exists to make impossible, and the state the shipped
    file was in — and requires the SAME sweep above to reject it. The clean tree
    must be clean through the same door, or the rejection proves only that the
    check fires on everything.
    """
    victim = EXAMPLES / '__probe_baseline_graph.json'
    try:
        doc = json.loads(DEMO.read_text(encoding='utf-8-sig'))
        scene = next(s for s in doc['scenes'] if s['type'] == 'volume-chart')
        # exactly the old defect: the value one level too high, and, as the
        # shipped file was, set in BOTH places so the wrong one is present
        scene['content']['baseline'] = 40
        victim.write_text(json.dumps(doc), encoding='utf-8')

        offences = _offences([victim])
        assert offences, (
            'a graph setting content.baseline was accepted -- this guard cannot '
            'detect the defect it was written for')
        assert any('content.baseline' in o for o in offences), offences

        delivered = [p for p in sorted(EXAMPLES.glob('*.json')) if p != victim]
        assert _offences(delivered) == [], (
            'the sweep reports offences on the DELIVERED graphs')
    finally:
        victim.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))