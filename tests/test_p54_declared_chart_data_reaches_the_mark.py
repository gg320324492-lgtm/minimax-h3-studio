"""A data key a graph DECLARES must reach the frame that graph renders (P54).

THE DEFECT THIS IS BUILT FOR
----------------------------
`c05_bubble` in `pipeline/examples/charts_demo.json` declares

    "values": [12, 28, 45, 66, 88, 100],
    "sizes":  [8, 22, 40, 61, 79, 95],

and `Chart.tsx` handed the mark `sizes: spec.series?.[0]?.sizes` -- a read of a
key this graph does not have. So `types.tsx`'s `series.sizes ?? series.values`
took its right side and the bubbles were sized by the Y value. MEASURED on this
tree before the repair: setting `sizes` to all-1 changed **0 px**; changing
`values[0]` from 12 to 11 changed **5,923 px**. The declared radius encoding was
a sentence nothing read, inside a picture that looked correct, because the
substitute was the other channel of the same series and it happened to be
monotone in the same direction.

WHY AN EXISTENCE CHECK CANNOT CATCH THIS CLASS
----------------------------------------------
The substitute is not `undefined` and not a blank frame. It is *another real
array*, drawn into *the same marks*. So:

  * "does the scene render?" -- yes, and it renders beautifully;
  * "is `sizes` mentioned in the reader file?" -- yes, at `Chart.tsx:137` and
    in the bubble dispatch, which is the `FIELD_READERS` shape this project has
    already been fooled by (`enterFrames` was "read" from inside a comment, and
    the registry said so until the comment-stripping check refused it);
  * "is the option alive?" -- `sizeBy` is, and the A/B matrix measures it
    moving pixels. An OPTION being live says nothing about a DATA key arriving.

The class is therefore not "a field with no reader". It is: **a value the graph
supplied was silently replaced by a different value the graph also supplied.**
The only instrument that can see that is a differential on the thing the graph
declares, measured on the frame.

WHAT IS ASKED, AND WHY IT IS NOT A FALSE-POSITIVE MACHINE
---------------------------------------------------------
For every chart scene of every tracked graph, and for every DATA key that scene
declares, render the scene once as declared and once with ONLY that key changed
(shape and length preserved). The two frames must differ. Three things keep that
honest:

  1. it iterates the keys the GRAPHS declare, not a table somebody maintains,
     so a new graph widens the check by itself and a renamed key cannot slip
     through a stale row;
  2. a key that is legitimately declared-and-not-rendered is not forbidden --
     it goes in `WAIVED`, with a reason, and `test_the_waiver_table_is_live`
     turns a waiver red when the key starts moving again, so the table cannot
     accumulate as an excuse. P43 ruled "declared, no renderer" a LEGAL
     decision; the answer to that is a named, auditable list, not a weaker
     criterion;
  3. every probe is compared against that scene's OWN baseline, rendered in the
     same bundle from the same graph header, and the baseline is required to
     carry ink -- so "0 px" can only mean the field is inert, never that the
     render came back empty.

WHAT THIS DOES NOT COVER, said plainly: an option that is read but whose
DEFAULT is wrong for its type is P47's (`test_chart_type_defaults_are_real.py`,
plus `options.check.ts`, which walks `Object.keys(DEFAULT_CHART_OPTIONS)` and so
structurally cannot see a data key -- `sizes` is not in that list and never
will be); a declared scene TYPE with no renderer is P43's. This file covers the
data half of `content.chart`, which no existing guard walks.

Run:
    python -m pytest tests/test_p54_declared_chart_data_reaches_the_mark.py -q

The render half needs node and the studio tree; it SKIPS when they are absent
and FAILS when a render it started comes back wrong -- a guard that steps aside
when its instrument breaks is the vacuous pass this file argues against.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'studio' / 'scripts'
STILL = ROOT / 'studio' / 'bin' / 'still.mjs'
STUDIO = ROOT / 'studio'

sys.path.insert(0, str(SCRIPTS))
from ab_field import frame_ink  # noqa: E402

_NODE = shutil.which('node')

pytestmark_render = pytest.mark.skipif(
    _NODE is None or not STILL.is_file(),
    reason='node/studio tree absent; the render-backed P54 checks did NOT run',
)

#: The keys of `content.chart` that carry DATA. Everything else on that bag is
#: an option (declared in `charts/options.ts`, resolved by `option()`, guarded
#: by P47's `options.check.ts`). `type` is the discriminator, not a channel.
#: A graph that declares a key in neither list is named by
#: `test_no_declared_chart_key_escapes_the_sweep` -- an unclassified key is an
#: unguarded one, which is how this defect stayed invisible.
DATA_KEYS = ('values', 'sizes', 'labels', 'rowLabels', 'colLabels', 'rows',
             'items', 'before', 'after', 'baseline', 'series')

#: A declared data key that is ALLOWED not to reach the frame, with the reason.
#: EMPTY as measured on this tree: all 19 declared keys move pixels, the
#: smallest by 7,832 px. It exists because P43 ruled a declared field with no
#: renderer a legitimate decision -- the answer to that is to name it here, not
#: to weaken the criterion.
WAIVED: dict[tuple[str, str], str] = {}

#: Every scene in the sweep is forced to this length so one frame number is
#: settled in every scene. `lifecycle.ts` puts the exit at
#: max(6, round(duration * 0.08)) frames from the end, so frame 100 of 150 is
#: 38 frames clear of it -- the same settled frame P47 measures on.
DUR = 150
FRAME = 100


# ── the graphs, and what they declare ───────────────────────────────────────

def _chart_graphs() -> list[Path]:
    """Every graph in the tree's graph directories that has a chart scene.

    A directory walk rather than a hard-coded file list: the point of this
    guard is that a NEW graph's declared keys are covered without anybody
    remembering to add a row.
    """
    found = []
    for d in ('pipeline/examples', 'pipeline/graphs'):
        for p in sorted((ROOT / d).glob('*.json')):
            try:
                doc = json.loads(p.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if any(isinstance((s.get('content') or {}).get('chart'), dict)
                   for s in doc.get('scenes', [])):
                found.append(p)
    return found


def _mutate(key: str, val):
    """Change the declared channel, keeping its shape and its length.

    A mutation that changed the NUMBER of marks would measure the count, not
    the channel, and would move pixels for a field nobody reads.
    """
    if key == 'baseline':
        return val + 37
    if key == 'items':
        return [{'label': f'q{i}', 'value': 3 + 7 * i, 'previous': 9 - i}
                for i, _ in enumerate(val)]
    if key == 'rows':
        return [[(v + 31) % 97 for v in row] for row in val]
    if key == 'series':
        return [{**s, 'values': [v + 9 for v in s['values']]} for s in val]
    if isinstance(val, list) and val and all(isinstance(v, str) for v in val):
        return [f'zz{i}' for i in range(len(val))]
    if (isinstance(val, list) and val
            and all(isinstance(v, (int, float)) for v in val)):
        return [v * 0.35 + 4 for v in val]
    raise AssertionError(f'no mutation defined for data key {key}={val!r}')


def _probes(graph: Path) -> list[tuple[str, str, dict, dict]]:
    """(scene id, data key, baseline scene, mutated scene) for one graph."""
    doc = json.loads(graph.read_text(encoding='utf-8'))
    out = []
    for scene in doc.get('scenes', []):
        chart = (scene.get('content') or {}).get('chart')
        if not isinstance(chart, dict):
            continue
        for key in sorted(set(chart) & set(DATA_KEYS)):
            base = json.loads(json.dumps(scene))
            base['durationInFrames'] = DUR
            mutated = json.loads(json.dumps(scene))
            # showcase-v1.ts:242 requires `^[a-z0-9_]+$` for a scene id, so the
            # camelCase key name is lowered. A schema rejection here would look
            # like a render failure and is not a finding about the renderer.
            mutated['id'] = f"{scene['id']}__{key.lower()}"
            mutated['durationInFrames'] = DUR
            mutated['content']['chart'][key] = _mutate(key, chart[key])
            out.append((scene['id'], key, base, mutated))
    return out


# ── rendering: one bundle per graph, one still per scene ─────────────────────

def _render(scratch: Path, header: dict, scenes: list[dict]) -> Path:
    """Render `scenes` and return the PNG directory.

    `still.mjs` takes GLOBAL frame numbers, so scene i is measured at
    i * DUR + FRAME: a one-bundle sweep whose frame numbers cannot drift onto a
    neighbour's frames -- the confident-zero shape that rendering scene 5 at
    "frame 70" of the whole film produces.
    """
    doc = dict(header)
    doc['scenes'] = scenes
    scratch.mkdir(parents=True, exist_ok=True)
    props = scratch / 'props.json'
    props.write_bytes(json.dumps(doc, ensure_ascii=False).encode('utf-8'))
    dest = scratch / 'png'
    dest.mkdir(exist_ok=True)
    public = scratch / 'public'   # empty on purpose: the real one is 773 MB/bundle
    public.mkdir(exist_ok=True)
    env = {**os.environ, 'TMPDIR': str(scratch), 'TMP': str(scratch),
           'TEMP': str(scratch), 'REMOTION_SCRATCH_DIR': str(scratch)}
    proc = subprocess.run(
        [_NODE, str(STILL), '--comp', 'FinanceShowcaseWide', '--props', str(props),
         '--out', str(dest),
         '--frames', ','.join(str(i * DUR + FRAME) for i in range(len(scenes))),
         '--public-dir', str(public)],
        cwd=str(STUDIO), capture_output=True, text=True, timeout=3600,
        encoding='utf-8', errors='replace', env=env)
    if proc.returncode != 0:
        raise AssertionError(
            f'still failed:\n{proc.stdout[-2500:]}\n{proc.stderr[-2500:]}')
    return dest


def _f(dest: Path, pos: int) -> Path:
    return dest / f'f{pos * DUR + FRAME:05d}.png'


def _changed_px(a: Path, b: Path) -> int:
    ia = np.asarray(Image.open(a).convert('RGB')).astype(np.int16)
    ib = np.asarray(Image.open(b).convert('RGB')).astype(np.int16)
    if ia.shape != ib.shape:
        raise AssertionError(f'{a} and {b} are different sizes; not comparable')
    return int((np.abs(ia - ib) > 0).sum())


@pytest.fixture(scope='module')
def sweep(tmp_path_factory):
    """Every (scene, declared data key) probe of every tracked graph, rendered.

    Module-scoped: the whole sweep is one bundle per graph and ~30 stills, and
    every test below reads the same frames. Rows carry their own `dest`, so a
    second graph is measured against its own header, not charts_demo's.
    """
    rows = []
    for graph in _chart_graphs():
        doc = json.loads(graph.read_text(encoding='utf-8'))
        header = {k: v for k, v in doc.items() if k != 'scenes'}
        scenes: list[dict] = []
        base_of: dict[str, int] = {}
        for sid, key, base, mutated in _probes(graph):
            if sid not in base_of:
                base_of[sid] = len(scenes)
                scenes.append(base)
            mpos = len(scenes)
            scenes.append(mutated)
            rows.append({'graph': graph.name, 'sid': sid, 'key': key,
                         'base': base_of[sid], 'mut': mpos, 'dest': None})
        dest = _render(tmp_path_factory.mktemp(f'p54-{graph.stem}'), header, scenes)
        for r in rows:
            if r['dest'] is None and r['graph'] == graph.name:
                r['dest'] = dest
    return rows


# ── the judgement, as a function so the self-test can drive it ──────────────

def _arrived(changed: int, baseline_ink: float) -> tuple[bool, str]:
    """Did the declared channel reach the frame? (arrived, why).

    A function taking numbers, because the only way to prove a criterion can
    say NO is to hand it a case it must reject -- `test_the_criterion_can_say_no`.

    `baseline_ink` is not decoration. A zero-change result on a frame with no
    subject means "you measured an empty picture", and that has to be
    distinguishable from "this field is inert"; the two are well-formed
    sentences that look identical from outside. `frame_ink` is the repository's
    own instrument (the per-row backdrop model `measure_frame.py` uses) and
    reads pure backdrop as exactly 0.000000.
    """
    if baseline_ink <= 0.0:
        return False, f'baseline ink {baseline_ink:.6f}% -- no subject on frame'
    if changed == 0:
        return False, '0 px changed while only this channel moved'
    return True, f'{changed} px changed'


# ── 1. the class ────────────────────────────────────────────────────────────

@pytestmark_render
def test_every_declared_data_key_reaches_the_frame(sweep):
    """The graphs' declared data channels, measured on the frames."""
    failures = []
    for r in sweep:
        changed = _changed_px(_f(r['dest'], r['base']), _f(r['dest'], r['mut']))
        ink = frame_ink(_f(r['dest'], r['base']))
        arrived, why = _arrived(changed, ink)
        if not arrived and (r['sid'], r['key']) not in WAIVED:
            failures.append(f"{r['graph']} {r['sid']}.{r['key']}: {why} "
                            f'(baseline ink {ink:.6f}%)')
    assert not failures, (
        'a data key the graph declares does not reach the frame:\n  '
        + '\n  '.join(failures)
        + '\n\nThe picture still looks right, which is the point: the mark '
          'substitutes ANOTHER declared channel for this one -- for `bubble` '
          'it is `series.sizes ?? series.values`, sizing the radius by the Y '
          'value. Add the reader, move the key to where the renderer looks, or '
          'waive it in WAIVED with a reason. Do not loosen this criterion.')


@pytestmark_render
def test_the_waiver_table_is_live(sweep):
    """A waiver is a claim about the CURRENT renderer, not a permanent exit.

    Two ways this table rots: a key waived that actually DOES move (the waiver
    hides nothing and must go), and a waiver whose reason was never really
    written. Both are red here, so the escape hatch cannot be widened by
    accretion -- which is how an allowlist turns a guard back into decoration.
    """
    stale = []
    for r in sweep:
        if (r['sid'], r['key']) not in WAIVED:
            continue
        changed = _changed_px(_f(r['dest'], r['base']), _f(r['dest'], r['mut']))
        if changed > 0:
            stale.append(f"{r['sid']}.{r['key']} moves {changed} px "
                         'but is still waived')
    assert not stale, 'stale waivers: ' + '; '.join(stale)
    for (sid, key), reason in WAIVED.items():
        assert isinstance(reason, str) and len(reason.strip()) >= 20, (
            f'{sid}.{key} is waived without a reason long enough to read')
    # and the table must only ever name things the sweep actually probes, or a
    # typo in a waiver is a silent exit for a key that was never inert
    probed = {(r['sid'], r['key']) for r in sweep}
    unprobed = [f'{sid}.{key}' for (sid, key) in WAIVED if (sid, key) not in probed]
    assert not unprobed, (
        f'waived but never probed (typo, or the key left the graph): {unprobed}')


@pytestmark_render
def test_the_sweep_measured_real_frames_of_every_chart_scene(sweep):
    """Prove the object under test exists before measuring it.

    A sweep whose baselines all came back blank would report every field inert
    -- or, with the criterion inverted, every field alive. Either way it would
    be measuring nothing, and both readings are confident.
    """
    scenes = {r['sid'] for r in sweep}
    assert len(scenes) >= 9, (
        f'the sweep covers {len(scenes)} chart scenes; charts_demo alone ships '
        '10, so the graph walk is not finding the tracked graphs')
    blank = [r['sid'] for r in sweep if frame_ink(_f(r['dest'], r['base'])) <= 0.0]
    assert not blank, f'these scenes rendered no subject at all: {sorted(set(blank))}'

    movers = [_changed_px(_f(r['dest'], r['base']), _f(r['dest'], r['mut']))
              for r in sweep if (r['sid'], r['key']) not in WAIVED]
    assert movers and all(m > 0 for m in movers), (
        f'not every declared key moved; the smallest was {min(movers) if movers else "n/a"} px')
    # MEASURED floor, so a reader can see the >0 threshold is not doing the
    # work: the smallest real mover in this sweep is 7,832 px
    # (`c04_slope.labels`), three orders of magnitude above one antialiased
    # edge. If the minimum ever lands near that edge, the sweep has stopped
    # measuring channels and started measuring noise.
    assert min(movers) > 1000, (
        f'smallest mover is {min(movers)} px, no longer comfortably above '
        'antialiasing -- re-measure before trusting a >0 threshold')


def test_no_declared_chart_key_escapes_the_sweep():
    """Every key a tracked graph puts on `content.chart` is classified.

    The hole this closes is coverage rot, not the defect itself: if a graph
    starts declaring a channel that is in neither `DATA_KEYS` (probed here, in
    pixels) nor the option registry (probed by P47's `options.check.ts` and the
    A/B matrix), then the only guard walking the data half of `content.chart`
    simply never looks at it -- and the next `sizes` arrives as a key nobody
    classified, which is how this one hid.

    The option surface is read from `ab_field.FIELD_READERS`, the registry
    `test_chart_registry` already holds to account, rather than parsed out of
    `options.ts` a second time. Two tables that agree by copy-paste are one
    table too many.
    """
    from ab_field import FIELD_READERS

    options = set(FIELD_READERS)
    unclassified = []
    for graph in _chart_graphs():
        doc = json.loads(graph.read_text(encoding='utf-8'))
        for scene in doc.get('scenes', []):
            chart = (scene.get('content') or {}).get('chart')
            if not isinstance(chart, dict):
                continue
            for key in chart:
                if key in DATA_KEYS or key in options or key == 'type':
                    continue
                unclassified.append(f'{graph.name} {scene["id"]}.{key}')
    assert not unclassified, (
        'chart keys that are neither a data channel this sweep probes nor an '
        f'option the registry knows: {unclassified}.\nAdd each to DATA_KEYS '
        '(with a mutation in _mutate) or to charts/options.ts + FIELD_READERS. '
        'An unclassified key is an unguarded key.')


# ── 2. the criterion must be able to say NO ─────────────────────────────────

def test_the_criterion_can_say_no(tmp_path):
    """A criterion that always answers "arrived" makes every test above green
    forever, and no render can show it. So the judgement is driven here with
    synthetic frames: one pair that differs, one that does not, and a blank
    baseline. It must answer all three correctly.

    Drawn, not rendered: this test is about the ARITHMETIC of the criterion, and
    making it depend on node would let the instrument's absence excuse a
    neutered judgement.
    """
    def make(seed: int) -> Path:
        rng = np.random.default_rng(seed)
        arr = np.full((240, 320, 3), (16, 17, 21), dtype=np.uint8)
        ys, xs = rng.integers(0, 240, 60), rng.integers(0, 320, 60)
        arr[ys, xs] = (200, 200, 210)
        p = tmp_path / f'c{seed}.png'
        Image.fromarray(arr, 'RGB').save(p)
        return p

    a, b = make(1), make(2)
    same = tmp_path / 'same.png'
    shutil.copyfile(a, same)
    blank = tmp_path / 'blank.png'
    Image.fromarray(np.full((240, 320, 3), (16, 17, 21), dtype=np.uint8),
                    'RGB').save(blank)

    ink_a = frame_ink(a)
    assert ink_a > 0.0, f'the fixture itself draws no ink ({ink_a})'

    ok, why = _arrived(_changed_px(a, b), ink_a)
    assert ok, f'the criterion rejected a pair that differs: {why}'

    dead, why_dead = _arrived(_changed_px(a, same), ink_a)
    assert not dead, (
        'the criterion called an identical pair "arrived" -- it cannot say NO, '
        f'which is the same as not testing ({why_dead})')

    empty_ink = frame_ink(blank)
    empty, why_empty = _arrived(0, empty_ink)
    assert not empty and 'ink' in why_empty, (
        'a blank baseline must be reported as "no subject", not as a verdict '
        f'about the field ({why_empty}, ink={empty_ink:.6f})')


# ── 3. two spellings, one rule: the second-truth-source question ────────────

@pytestmark_render
def test_the_two_spellings_of_a_channel_render_the_same_picture(tmp_path):
    """`chart.sizes` and `chart.series[0].sizes` are ONE channel, not two truths.

    The repair accepts the graph-level spelling because the renderer already
    accepts it for `values` (`spec.series?.[0]?.values ?? values`). That is only
    safe if it is the SAME rule with a defined winner, so it is measured on four
    frames from one bundle:

      flat      -- sizes beside values, the way every scene in charts_demo
                   spells its data;
      series_a  -- the same numbers inside `series[0]`, nothing at top level;
      both_same -- both spellings, agreeing;
      series_b  -- `series[0]` carrying a DIFFERENT array B, nothing at top
                   level: the reference for what "series wins" looks like;
      both_diff -- flat spelling A and `series[0]` B together.

    flat == series_a == both_same proves one channel with two spellings;
    both_diff == series_b proves the winner is `series[0]`, and
    both_diff != flat proves the graph-level spelling is not merely being read
    second by accident. If somebody later "accepts both" by concatenating,
    averaging or last-wins-ing these, this goes red.
    """
    doc = json.loads((ROOT / 'pipeline' / 'examples' / 'charts_demo.json')
                     .read_text(encoding='utf-8'))
    c05 = next(s for s in doc['scenes'] if s['id'] == 'c05_bubble')
    chart = c05['content']['chart']
    values, sizes = list(chart['values']), list(chart['sizes'])

    def scene(sid: str, ch: dict) -> dict:
        s = json.loads(json.dumps(c05))
        s['id'] = sid
        s['durationInFrames'] = DUR
        s['content']['chart'] = ch
        return s

    def series_only(sid: str, arr: list) -> dict:
        ch = {k: v for k, v in chart.items() if k not in ('values', 'sizes')}
        ch['series'] = [{'values': values, 'sizes': arr}]
        return scene(sid, ch)

    other = list(reversed(sizes))
    flat = scene('p54_flat', {**chart, 'values': values, 'sizes': sizes})
    series_a = series_only('p54_series_a', sizes)
    both_same = scene('p54_both_same', {**chart, 'series': [
        {'values': values, 'sizes': sizes}]})
    series_b = series_only('p54_series_b', other)
    both_diff = scene('p54_both_diff', {**chart, 'series': [
        {'values': values, 'sizes': other}]})

    header = {k: v for k, v in doc.items() if k != 'scenes'}
    dest = _render(tmp_path / 'spellings', header,
                   [flat, series_a, both_same, series_b, both_diff])
    f = [_f(dest, i) for i in range(5)]

    assert frame_ink(f[0]) > 0.0, 'the flat spelling rendered no subject at all'
    assert _changed_px(f[0], f[1]) == 0, (
        f'`chart.sizes` and `chart.series[0].sizes` render DIFFERENT pictures '
        f'({_changed_px(f[0], f[1])} px). Two spellings of one channel must '
        'agree, or the graph holds two truths about the same data.')
    assert _changed_px(f[0], f[2]) == 0, (
        'agreeing spellings disagreed -- the resolution depends on which one '
        'was written even when they say the same thing')
    assert _changed_px(f[4], f[3]) == 0, (
        f'with both spellings present the frame is not what `series[0]` alone '
        f'produces ({_changed_px(f[4], f[3])} px): the declared precedence '
        '(`series[0]` first, exactly as `values` resolves) is not what runs.')
    assert _changed_px(f[4], f[0]) > 0, (
        'the disagreeing pair rendered the same frame as the flat spelling, so '
        '`series[0].sizes` is not read at all and the precedence above is '
        'vacuous -- which is the shape a "fix" that only ever reads the '
        'graph-level key would have')
