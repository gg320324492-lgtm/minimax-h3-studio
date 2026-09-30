"""A/B every representative chart option and write the evidence to a report.

P7 discipline: a chart option that is declared and never read is the failure
this project has now hit three times. The registry check catches an option whose
name is missing from the file registered against it — but it cannot catch a name
that is present on the WRONG component, which is exactly what `showArea` was
(registered against types.tsx, and present there, on the Area component, inert
for every `line` chart).

So the options are measured instead: change one, render twice, count the pixels
and name the region. A row of all zeros is a row of inert options.

    python studio/scripts/chart_ab_matrix.py --out out/chart_ab.md

Not part of `pytest tests/`: it is 24 renders. It is a gate you run
deliberately, and its output is a committed record rather than a pass/fail.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(r'E:\Minimax-H3')
sys.path.insert(0, str(ROOT / 'studio' / 'scripts'))

import ab_field  # noqa: E402

GRAPH = ROOT / 'pipeline' / 'examples' / 'charts_demo.json'

# scene index in charts_demo.json, the settled frame for that scene, and the
# option under test with the value to substitute.
#
# The frame matters: a field measured on a frame that does not show its subject
# reports zero and looks like a finding. Each scene is 150 frames and its marks
# have finished entering well before the end, so the frame below is the last
# quarter of the scene.
MATRIX: list[tuple[int, int, str, object]] = [
    # bar — scene 0, frames 0..150
    (0, 120, 'scenes.0.content.chart.emphasisIndex', 0),
    (0, 120, 'scenes.0.content.chart.valueFormat', 'int'),
    (0, 120, 'scenes.0.content.chart.showGrid', False),
    (0, 120, 'scenes.0.content.chart.barWidthRatio', 0.9),
    (0, 120, 'scenes.0.content.chart.showAxis', False),
    (0, 120, 'scenes.0.content.chart.axisLabel', 'RENAMED UNIT'),
    # line — scene 1, frames 150..300
    (1, 270, 'scenes.1.content.chart.showArea', False),
    (1, 270, 'scenes.1.content.chart.curve', 'step'),
    (1, 270, 'scenes.1.content.chart.strokeWidth', 1),
    (1, 270, 'scenes.1.content.chart.showValues', True),
    # bubble — scene 4, frames 600..750
    (4, 720, 'scenes.4.content.chart.sizeBy', 'none'),
    (4, 720, 'scenes.4.content.chart.showValues', False),
    # slope — scene 3, frames 450..600
    (3, 570, 'scenes.3.content.chart.showEndLabels', False),
    (3, 570, 'scenes.3.content.chart.emphasisIndex', 0),
    # heatmap — scene 5, frames 750..900
    (5, 870, 'scenes.5.content.chart.showCellValues', False),
    (5, 870, 'scenes.5.content.chart.emphasisIndex', 0),
    # rank — scene 6, frames 900..1050
    (6, 1020, 'scenes.6.content.chart.showRankDelta', False),
    (6, 1020, 'scenes.6.content.chart.emphasisIndex', 0),
    # volume — scene 7, frames 1050..1200
    (7, 1170, 'scenes.7.content.chart.emphasisIndex', 5),
    # sparkline — scene 8, frames 1200..1350
    (8, 1320, 'scenes.8.content.chart.strokeWidth', 2),
    # ── motion options, measured MID-ENTRANCE ────────────────────────────────
    # These change nothing on a settled frame, because by then every mark has
    # finished arriving. Measuring them on frame 120 and calling the result a
    # finding would be exactly the "zero that looks like a conclusion" mistake
    # the guard now refuses — so the frame here is chosen INSIDE the animation.
    # enterFrames 34 + stagger 2*4 puts the bar scene's last bar arriving around
    # frame 44, so 25 is mid-flight for all five.
    (0, 25, 'scenes.0.content.chart.staggerFrames', 30),
    (0, 25, 'scenes.0.content.chart.enterFrames', 90),
    (4, 720, 'scenes.4.content.chart.deemphasis', 1.0),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(ROOT / 'out' / 'chart_ab.md'))
    ap.add_argument('--scratch', default=str(ROOT / 'out' / 'ab_matrix'))
    args = ap.parse_args()

    import json
    doc = json.loads(GRAPH.read_text(encoding='utf-8'))
    scratch = Path(args.scratch)

    rows: list[tuple[str, int, float, str, str]] = []
    inert: list[str] = []
    for scene, frame, dotted, value in MATRIX:
        current, err = ab_field.check_value(doc, dotted, json.dumps(value))
        assert err is None, f'{dotted}: {err}'
        res = ab_field.ab_field(GRAPH, dotted, current, frame, scratch)
        ink = ab_field.frame_ink(Path(res['a']))
        option = dotted.rsplit('.', 1)[-1]
        verdict = 'LIVE' if res['changed'] else 'INERT'
        if not res['changed']:
            inert.append(f'{dotted} (frame {frame}, ink {ink:.2f}%)')
        print(f'  {verdict:5s} {option:16s} {res["changed"]:7d} px  frame {frame}', flush=True)
        rows.append((option, res['changed'], res['pct'], str(res['box']), verdict))

    lines = [
        '# P7.1 chart option A/B evidence',
        '',
        'Each row: one option changed on a frame where the subject is on screen,',
        'the graph rendered twice, the pixels differenced. A row of zeros is a',
        'declared option nobody reads — the failure the registry check cannot see.',
        '',
        '| option | changed px | % | region | verdict |',
        '|---|---:|---:|---|---|',
    ]
    for option, changed, pct, box, verdict in rows:
        lines.append(f'| `{option}` | {changed} | {pct:.2f} | {box} | {verdict} |')
    lines += ['', f'**{len(rows) - len(inert)} of {len(rows)} options are live.**', '']
    if inert:
        lines.append('Inert (declared, changes nothing on screen):')
        lines += [f'- `{i}`' for i in inert]
    else:
        lines.append('No inert options.')

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'\n{len(rows) - len(inert)}/{len(rows)} live -> {out}')
    return 1 if inert else 0


if __name__ == '__main__':
    sys.exit(main())
