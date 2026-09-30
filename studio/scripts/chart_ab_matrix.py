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
#: How a row must be measured, which decides its frame. Recorded here rather than
#: left in a reviewer's head, because getting it wrong produces a zero that reads
#: exactly like a finding — which is how a live option got reported dead once, and
#: how a live matrix row nearly got called a bug.
#:
#:   SETTLED  — the marks have fully arrived and the subject fills the frame. Every
#:              option about how a mark LOOKS or is emphasised. On a
#:              mid-entrance frame these change nothing, by construction.
#:   ENTERING — the marks are still arriving and the frame is mostly empty. The only
#:              place an option about TIMING can show itself. On a settled frame
#:              these are identically zero, and "identically zero" is exactly what
#:              a dead option looks like, too.
SETTLED = 'settled'
ENTERING = 'entering'


MATRIX: list[tuple[int, int, str, object, str]] = [
    # bar — scene 0, frames 0..150
    (0, 120, 'scenes.0.content.chart.emphasisIndex', 0, SETTLED),
    (0, 120, 'scenes.0.content.chart.valueFormat', 'int', SETTLED),
    (0, 120, 'scenes.0.content.chart.showGrid', False, SETTLED),
    (0, 120, 'scenes.0.content.chart.barWidthRatio', 0.9, SETTLED),
    (0, 120, 'scenes.0.content.chart.showAxis', False, SETTLED),
    (0, 120, 'scenes.0.content.chart.axisLabel', 'RENAMED UNIT', SETTLED),
    # line — scene 1, frames 150..300
    (1, 270, 'scenes.1.content.chart.showArea', False, SETTLED),
    (1, 270, 'scenes.1.content.chart.curve', 'step', SETTLED),
    (1, 270, 'scenes.1.content.chart.strokeWidth', 1, SETTLED),
    (1, 270, 'scenes.1.content.chart.showValues', True, SETTLED),
    # bubble — scene 4, frames 600..750
    (4, 720, 'scenes.4.content.chart.sizeBy', 'none', SETTLED),
    (4, 720, 'scenes.4.content.chart.showValues', False, SETTLED),
    # slope — scene 3, frames 450..600
    (3, 570, 'scenes.3.content.chart.showEndLabels', False, SETTLED),
    (3, 570, 'scenes.3.content.chart.emphasisIndex', 0, SETTLED),
    # heatmap — scene 5, frames 750..900
    (5, 870, 'scenes.5.content.chart.showCellValues', False, SETTLED),
    (5, 870, 'scenes.5.content.chart.emphasisIndex', 0, SETTLED),
    # rank — scene 6, frames 900..1050
    (6, 1020, 'scenes.6.content.chart.showRankDelta', False, SETTLED),
    (6, 1020, 'scenes.6.content.chart.emphasisIndex', 0, SETTLED),
    # volume — scene 7, frames 1050..1200
    (7, 1170, 'scenes.7.content.chart.emphasisIndex', 5, SETTLED),
    # sparkline — scene 8, frames 1200..1350
    (8, 1320, 'scenes.8.content.chart.strokeWidth', 2, SETTLED),
    # ── motion options, measured MID-ENTRANCE ────────────────────────────────
    # These change nothing on a settled frame, because by then every mark has
    # finished arriving. Measuring them on frame 120 and calling the result a
    # finding would be exactly the "zero that looks like a conclusion" mistake
    # the guard now refuses — so the frame here is chosen INSIDE the animation.
    # enterFrames 34 + stagger 2*4 puts the bar scene's last bar arriving around
    # frame 44, so 25 is mid-flight for all five.
    (0, 25, 'scenes.0.content.chart.staggerFrames', 30, ENTERING),
    # enterFrames is CAPPED at the scene's intro share (34%), so it can only be
    # measured where the cap is not what binds. On a 150-frame scene the cap is 51
    # and both 34 and 90 clamp to 51 — the option is genuinely inert there. That is
    # correct behaviour and a useless measurement, so it is measured on scene 9,
    # which is 600 frames: cap 204, so 34 and 120 give different entrances.
    (9, 1440, 'scenes.9.content.chart.enterFrames', 120, ENTERING),
    (9, 1440, 'scenes.9.content.chart.staggerFrames', 40, ENTERING),
    (4, 720, 'scenes.4.content.chart.deemphasis', 1.0, SETTLED),
    # ── P7.3 rows ─────────────────────────────────────────────────────────────
    # sparkline joins the shared lifecycle (it used to render complete at frame
    # 0), so its entrance must be measurable. The scene is 150 frames, so the
    # CAP still binds high values (51) — but a LOW value shortens the entrance
    # (34*1.4+2*11 clamps to 36), and at local frame 20 the two dash offsets
    # differ. Measured where the stroke is still drawing: ENTERING.
    (8, 1220, 'scenes.8.content.chart.enterFrames', 10, ENTERING),
    # theme reaches the chart marks: the heat ramp follows PALETTE.ink, so a
    # light theme must change the cells' fill, not only the backdrop. Charts had
    # no light-theme pixel evidence at all before this row.
    (5, 870, 'scenes.5.theme', 'premium-light', SETTLED),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(ROOT / 'out' / 'chart_ab.md'))
    ap.add_argument('--scratch', default=str(ROOT / 'out' / 'ab_matrix'))
    args = ap.parse_args()

    import json
    doc = json.loads(GRAPH.read_text(encoding='utf-8'))
    scratch = Path(args.scratch)
    # The absolute frame span of each scene. `--frame` is absolute, and a scene-
    # local frame written here measures a different scene entirely — which produced
    # a confident zero, in this very table.
    SCENE_SPANS: dict[int, tuple[int, int]] = {}
    cursor = 0
    for _i, _sc in enumerate(doc['scenes']):
        _n = int(_sc["durationInFrames"])
        SCENE_SPANS[_i] = (cursor, cursor + _n)
        cursor += _n

    rows: list[dict] = []
    inert: list[str] = []
    for scene, frame, dotted, value, kind in MATRIX:
        current, err = ab_field.check_value(doc, dotted, json.dumps(value))
        assert err is None, f'{dotted}: {err}'
        res = ab_field.ab_field(GRAPH, dotted, current, frame, scratch)
        ink = ab_field.frame_ink(Path(res['a']))
        option = dotted.rsplit('.', 1)[-1]
        verdict = 'LIVE' if res['changed'] else 'INERT'
        if not res['changed']:
            inert.append(f'{dotted} (frame {frame}, ink {ink:.2f}%)')
        # Provenance, because a number nobody can re-run is a rumour. The review
        # could not reproduce a row of this table and had no way to tell WHICH
        # chart it had measured — every number here carries its graph, its exact
        # dotted path, its frame, and which scene and chart type that is.
        sc = doc['scenes'][scene]
        rows.append({
            'option': option,
            'kind': kind,
            'span': SCENE_SPANS.get(scene, ('?', '?')),
            'scene': scene,
            'scene_type': sc['type'],
            'chart_type': (sc.get('content', {}).get('chart', {}) or {}).get('type'),
            'path': dotted,
            'was': ab_field._get_path(doc, dotted)[1],
            'now': current,
            'frame': frame,
            'ink': ink,
            'changed': res['changed'],
            'pct': res['pct'],
            'box': res['box'],
            'verdict': verdict,
        })
        print(f'  {verdict:5s} {sc["type"]:14s} {option:16s} {res["changed"]:7d} px  frame {frame}',
              flush=True)

    lines = [
        '# P7.1 chart option A/B evidence',
        '',
        'Each row: one option changed on a frame where the subject is on screen, the',
        'graph rendered twice, the pixels differenced. A row of zeros is a declared',
        'option nobody reads — the failure the registry check cannot see, because the',
        'name IS in the file, on the wrong component.',
        '',
        '**Every row is independently re-runnable.** The exact command is given, so a',
        'number here can be checked rather than believed:',
        '',
        '```',
        'python studio/scripts/ab_field.py --props pipeline/examples/charts_demo.json \\',
        '    --set <path>=<now> --frame <frame> --out out/ab',
        '```',
        '',
        '| option | measured | scene | scene frames | chart type | path | was -> now | frame | ink | px | % | region | verdict |',
        '|---|---|---|---|---|---|---|---:|---:|---:|---:|---|---|',
    ]
    for r in rows:
        lines.append(
            f'| `{r["option"]}` | `{r["kind"]}` | {r["scene"]} {r["scene_type"]} '
            f'| `{r["span"]}` | `{r["chart_type"]}` '
            f'| `{r["path"]}` | `{r["was"]}` -> `{r["now"]}` | {r["frame"]} '
            f'| {r["ink"]:.1f}% | {r["changed"]} | {r["pct"]:.2f} | {r["box"]} | {r["verdict"]} |'
        )
    lines += ['', f'**{len(rows) - len(inert)} of {len(rows)} options are live.**',
              f'Generated from `{GRAPH.name}` at {len(doc["scenes"])} scenes.', '']
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
