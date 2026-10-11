"""A chart type's DEFAULT must be the picture its type is named for (P47).

THE FAILURE THIS IS BUILT FOR
-----------------------------
`area` and `line` dispatch to the same mark and were rendered byte-identical
unless the graph spelled out `showArea: true` -- because `option()` returns
`DEFAULT_CHART_OPTIONS[key]` for an absent value, so it never returns undefined
and `option(...) ?? defaultArea` could only ever take its left side. The
delivered `charts_demo.json` then set that option on the LINE scene and not on
the AREA one, so the two scenes shipped with their appearances swapped, inside
a film that had passed visual acceptance.

EVERY EXISTING GUARD WAS GREEN, and it is worth being precise about why,
because "add a test" is not a fix for a class:

  * the A/B matrix asks whether FLIPPING an option moves pixels. `showArea`
    moves 400,053 px. It is alive. The matrix was measuring a different
    question -- an option being live says nothing about whether its DEFAULT is
    right for the type it lands on;
  * `test_chart_registry` checks the option is NAMED in the reader file;
  * `TYPE_OPTIONS` checks the NAME is documented for the type;
  * the P45 VLM criterion asks whether the numbers the graph declared were
    printed, not whether the picture is the picture its type names.

So the shape is: **an option that is live, whose default is wrong for its own
type.** It produces a wrong picture and no red anywhere. It is the table
cousin of the failure `TYPE_OPTIONS` records one level up -- that one made an
option INERT, this one makes a DEFAULT wrong -- and neither is reachable by
asking whether the option works.

WHAT THIS ASKS INSTEAD
----------------------
Every criterion renders real frames and reads real pixels. None asserts that a
NAME appears in a source file: this project has been fooled by text-existence
assertions eleven times, and a guard that grepped for `defaultArea` would have
been perfectly green on the defect it was written for.

Three questions, deliberately different:

  1. `no_two_chart_types_may_render_the_same_picture`. Of the whole set: are
     these distinct pictures? No expectation table and no per-type claim -- a
     relation among types, which nothing here can satisfy by getting one type
     wrong in a new way.
  2. `every_type_default_row_must_move_pixels`. Of the mechanism: does the new
     per-type table have a row nobody reads? This is what stops the fix from
     becoming the sixth declaration in this repository that is written down and
     read by nothing.
  3. `the_area_type_must_carry_the_fill_and_the_line_type_must_not`. The one
     question (1) and (2) cannot answer: WHICH of the pair has the fill. Both
     are symmetric, so a row attached to the WRONG type satisfies both
     perfectly -- which is exactly what the delivered graph did.

HOW NARROW THIS IS, AND WHY IT WILL NOT MISFIRE
----------------------------------------------
The risk with a guard like this is a false-positive machine. "Every chart type
now needs an expectation written about it" is how a rendering guard becomes a
thing people route around. Concretely:

  * Criteria 1 and 2 assert only INEQUALITY between real renders. They cannot
    fire on a legitimate design change: the only way two types come to render
    the same picture is for one to stop being a distinct mark.
  * Criterion 2 fires only on a row that changes nothing, and such a row is
    either redundant (it restates the shared default) or attached to a mark
    that never reads the option. Both should be deleted, so there is no correct
    code it can reject.
  * Criterion 3 is the ONLY place a claim about how a chart should look enters,
    and it is one claim about one pair. It is not taste:
    `studio/scripts/p46_chart_probe.py` defines the line chart in this
    repository's own vocabulary as "a single thin line drawn through a series
    of points, with no area filled in beneath it". Filled and not-filled are
    therefore defined for this pair BY CONTRAST in a committed file, so a chart
    carrying the fill is not a line chart by that definition rather than by my
    preference. Scoping it to that one pair is what keeps it from
    generalising into a taste machine over the other eight types.

THE THRESHOLDS ARE MEASURED, NOT PICKED
---------------------------------------
Both numbers below come off real renders of this renderer, and both were
wrong when chosen by eye. The first draft asserted "every type's frame carries
more than 0.5% ink", which would have failed `bubble` (0.104%) and `sparkline`
(0.193%) for being SMALL rather than for being ABSENT -- measuring one mark on
another mark's scale, which is the recurring failure wearing a new hat. What is
actually true is that `frame_ink` reads pure backdrop as exactly 0.000000
(three crops of a real render containing nothing but backdrop: the top 40 rows,
the bottom 40 rows and the left gutter, all 0.000000), while the six types
measured between 0.104% and 32.6%. So the floor for "is the subject on the
frame at all" is zero, exactly, and anything above it is a subject.

WHAT IT CANNOT DO, stated so nobody relies on it
-----------------------------------------------
Nothing here decides whether a heatmap ramp runs the right way, whether a rank
table's deltas are legible, or whether any other default is the RIGHT default
for its type. Two structurally different marks cannot collide, so for seven of
the six types here criterion 1 is close to a tautology; the `line`/`area` pair
carries the content, and the docstring says so rather than letting a count of
six imply coverage that is not there. The guard also cannot catch a criterion
that has been rewritten to always pass in a way that still contains a
comparison -- that is what `each_criterion_is_asked_to_reject_what_it_should_
reject` is for, and it states its own limit too.

Run:
    python -m pytest tests/test_chart_type_defaults_are_real.py -q

The measured half renders: 7 single-frame renders, against the A/B matrix's 52
and behind no environment flag. That is deliberate. Every guard that could have
caught this defect was either opt-in or absent, so an opt-in guard here would
reproduce the failure it is written for. If node or the studio tree is missing
it SKIPS, and says what it did not check; a render that FAILS fails the test,
because a guard that steps aside when its instrument breaks is the vacuous pass
this file argues against.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'charts'
OPTIONS_TS = TEMPLATE / 'options.ts'
TYPES_TSX = TEMPLATE / 'types.tsx'
GRAPHS = ROOT / 'pipeline' / 'examples' / 'charts_demo.json'
STILL = ROOT / 'studio' / 'bin' / 'still.mjs'
STUDIO = ROOT / 'studio'

sys.path.insert(0, str(ROOT / 'studio' / 'scripts'))
from ab_field import frame_ink  # noqa: E402

_NODE = shutil.which('node')

#: The scene every render is built from. A real shipped scene, so the design
#: tokens, the camera and the motion preset are the ones the film uses -- a
#: synthetic scene could be judged by properties of itself.
SOURCE_SCENE = 'c01_bar'

#: Settled, and not near the end. `lifecycle.ts` gives the exit
#: max(EXIT_MIN=6, round(duration*EXIT_SHARE=0.08)) frames, so in a 150-frame
#: scene the exit starts at 138 and frame 140 is already leaving. MEASURED by
#: `p46_chart_control.py`: frames 60 and 100 differ by 0 px on every type,
#: while 140 differs from 100 by 387,430 px on `bar`. A criterion evaluated on
#: an exiting frame is evaluated on a half-drawn chart.
FRAME = 100

#: The types that read ONE payload -- `values`, and optionally `labels`. Read
#: from `Chart.tsx`, which dispatches exactly these to `Bar`/`Line`/`Area`/
#: `Bubble`/`VolumeBars`/`SparklineSlot` off `spec.values` (bubble falls back
#: to `values` when there is no `series`). One payload is the whole point: if
#: the data also changed, a pixel difference would no longer isolate the TYPE,
#: and the type would stop being what was measured.
#:
#: `slope`, `heatmap` and `rank` are deliberately NOT here. They read
#: `before`/`after`, `rows` and `items`, so putting them on this payload would
#: change the data as well as the type, and their membership in the pairwise
#: check would be vacuous -- worse than absent, because it would inflate the
#: count.
PAYLOAD_TYPES = ('bar', 'line', 'area', 'volume', 'sparkline', 'bubble')

#: Two types must differ by more than antialiasing, not merely by a tint. The
#: smallest difference between any two of the six types above is 1,827 px
#: (`bubble` against `sparkline`), and the pair this defect was about is
#: 279,623 px. 500 sits 3.6x below the smallest real pair, so it excludes
#: per-pixel noise without excluding a real mark, and it is 560x the defect.
MIN_PAIR_DIFF = 500

#: The floor for "is the subject on this frame at all". MEASURED: `frame_ink`
#: on pure backdrop reads exactly 0.000000 (top 40 rows, bottom 40 rows and
#: left gutter of a real render), and the six types read 0.104% (bubble) to
#: 32.6% (volume). An invented 0.5% floor would have failed bubble and
#: sparkline for being small rather than absent.
BLANK_INK = 0.0

#: A filled area is many times the ink of a bare line. MEASURED: 17.6x on the
#: shared payload below and 18.5x on the delivered `c02_line`/`c03_area` pair.
#: 3.0 sits an order of magnitude inside both, so ordinary data changes cannot
#: push a legitimate pair under it -- and what it has to catch (the sides
#: swapped) puts the ratio near 0.06, nowhere near the line.
INK_RATIO = 3.0

pytestmark = pytest.mark.skipif(
    _NODE is None or not STILL.is_file(),
    reason='node/studio tree absent; chart-type defaults are NOT checked here',
)


# ── reading the source, as INPUT to a render (never as the assertion) ────────

def _ts_block(src: str, start: str) -> str:
    """The body of one `export const NAME ... = { … };` declaration."""
    assert start in src, f'{start!r} not found in options.ts — the table moved'
    tail = src.split(start, 1)[1]
    assert '\n};' in tail, f'{start!r} has no closing brace — the table changed shape'
    return tail.split('\n};', 1)[0]


def _strip_ts_comments(src: str) -> str:
    """A comment cannot contribute a row.

    Same rule as `ab_field._strip_ts_comments`, for the same reason: a name in a
    doc comment is not a name in a program. Applied to the SLICED block, not to
    the file, so a comment elsewhere cannot move the block boundary.
    """
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'//[^\n]*', '', src)


def _ts_literal(raw: str) -> object:
    """A TypeScript literal as its Python value.

    A STRING for `false` is not a cosmetic slip here. The first draft of this
    guard returned `'false'` as text, wrote `showArea: "false"` into a render
    props file, and got a frame identical to the silent one -- because a
    non-empty string is truthy, so the area filled anyway. The guard then
    reported the one correct row in the table as INERT, which is what a guard
    that measures the wrong thing looks like from the outside.
    """
    if raw in ('true', 'false'):
        return raw == 'true'
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    return float(raw)


def _type_default_rows() -> dict[str, dict[str, object]]:
    """`TYPE_DEFAULT_ROWS`, parsed. This ENUMERATES the inputs to a render.

    The assertion that matters is on pixels. Parsing is how the guard learns
    which rows exist so it can require each one to do something; it is not a
    check that the table is spelled a particular way, and a row this parser
    cannot see fails the anti-vacuity assertion below rather than passing
    quietly.
    """
    src = OPTIONS_TS.read_text(encoding='utf-8')
    block = _strip_ts_comments(_ts_block(src, 'export const TYPE_DEFAULT_ROWS'))
    rows: dict[str, dict[str, object]] = {}
    for m in re.finditer(r'(\w+)\s*:\s*\{([^}]*)\}', block):
        entries: dict[str, object] = {}
        for k, v in re.findall(r"(\w+)\s*:\s*(true|false|-?[\d.]+|'[^']*')", m.group(2)):
            entries[k] = _ts_literal(v)
        rows[m.group(1)] = entries
    return rows


def _shared_default(key: str) -> object:
    """`DEFAULT_CHART_OPTIONS[key]`, read from the source.

    Read rather than restated, for the reason `test_chart_geometry.py` gives: a
    copied literal here keeps describing a default the renderer no longer has,
    and every assertion below would stay green while measuring the wrong thing.
    """
    src = OPTIONS_TS.read_text(encoding='utf-8')
    block = _ts_block(src, 'export const DEFAULT_CHART_OPTIONS')
    m = re.search(r'\b' + re.escape(key) + r'\s*:\s*(true|false|-?[\d.]+|\'[^\']*\')', block)
    assert m, f'DEFAULT_CHART_OPTIONS.{key} is gone — the assertion below is stale'
    return _ts_literal(m.group(1))


# ── the judgements, as functions so the self-test can drive them ─────────────

def _has_the_fill(candidate: Path, reference: Path, ratio: float = INK_RATIO) -> bool:
    """Does `candidate` carry a filled region that `reference` does not?

    Two-sided ON PURPOSE. Distinctness ("these frames differ") cannot say WHICH
    side has the fill, and a table row attached to the wrong type still
    satisfies distinctness. Comparing the INK the two renders put on the frame
    can say it: the region under a curve is thousands of times more pixels than
    a stroked path, so the side that has it is the heavier one.

    Two different instruments on purpose: the pairwise check diffs frames with
    numpy, this reads ink through `ab_field.frame_ink`'s per-row backdrop
    model. Neutering one therefore cannot quietly neuter the other.
    """
    return frame_ink(candidate) > ratio * frame_ink(reference)


def _frames_differ(a: Path, b: Path, tol: int = 8) -> int:
    """Differing pixel count; -1 when the two cannot be compared at all."""
    import numpy as np
    from PIL import Image

    ia = np.asarray(Image.open(a).convert('RGB')).astype(np.int16)
    ib = np.asarray(Image.open(b).convert('RGB')).astype(np.int16)
    if ia.shape != ib.shape:
        return -1
    return int((np.abs(ia - ib) > tol).any(axis=2).sum())


# ── rendering ────────────────────────────────────────────────────────────────

class _Renderer:
    """Renders one chart type on one payload.

    Two things copied from `ab_field`, because both have bitten this repository:
    the scratch bundle goes NEXT TO THE OUTPUT rather than into the system temp
    (125 leftover bundles, 58 GB, filled a C: drive), and the frame is matched
    by EXACT NAME (`next(glob(...))` once picked up a stale frame and reported a
    confident zero).
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.scratch = self.root / 'scratch'
        self.scratch.mkdir(exist_ok=True)
        self.public = self.root / 'public'
        self.public.mkdir(exist_ok=True)
        self._cache: dict[tuple, Path] = {}

    def frame(self, chart_type: str, options: dict | None = None) -> Path:
        key = (chart_type, json.dumps(options or {}, sort_keys=True))
        if key in self._cache:
            return self._cache[key]

        tag = f'{chart_type}-{hashlib.sha256(key[1].encode()).hexdigest()[:8]}'
        out = self.root / tag
        if out.exists():
            shutil.rmtree(out)

        scene = json.loads(json.dumps(_source_scene()))
        scene['id'] = f'p47_{chart_type}'
        chart = scene['content']['chart']
        chart['type'] = chart_type
        # SILENT: every declared option is dropped, so the TYPE alone decides
        # what is drawn. This is the case the A/B matrix never renders -- it
        # always flips an option the graph has already set, which is why
        # `showArea` measured 400,053 px and told nobody that its default was
        # wrong for the type it landed on.
        for k in [k for k in chart if k not in ('type', 'values', 'labels')]:
            chart.pop(k)
        for k, v in (options or {}).items():
            chart[k] = v

        doc = {k: v for k, v in json.loads(GRAPHS.read_text(encoding='utf-8')).items()
               if k != 'scenes'}
        doc['scenes'] = [scene]
        props = self.root / f'{tag}.json'
        props.write_bytes(json.dumps(doc, ensure_ascii=False, indent=1).encode('utf-8'))

        env = {**os.environ,
               'TMPDIR': str(self.scratch), 'TMP': str(self.scratch),
               'TEMP': str(self.scratch),
               'REMOTION_SCRATCH_DIR': str(self.scratch)}
        proc = subprocess.run(
            [_NODE, str(STILL), '--comp', 'FinanceShowcaseWide', '--props', str(props),
             '--out', str(out), '--frames', str(FRAME), '--public-dir', str(self.public)],
            cwd=str(STUDIO), capture_output=True, text=True, timeout=1800,
            encoding='utf-8', errors='replace', env=env,
        )
        if proc.returncode != 0:
            # A render that fails must FAIL THE TEST, never skip it.
            raise AssertionError(
                f'still failed for type {chart_type!r} on frame {FRAME}.\n'
                f'stdout:\n{proc.stdout[-4000:]}\nstderr:\n{proc.stderr[-4000:]}'
            )
        png = out / f'f{FRAME:05d}.png'
        assert png.is_file(), f'{png} was not written — a stale-frame comparison follows'
        self._cache[key] = png
        return png


@pytest.fixture(scope='module')
def renderer(tmp_path_factory) -> _Renderer:
    return _Renderer(tmp_path_factory.mktemp('p47_chart_defaults'))


@pytest.fixture(scope='module')
def silent(renderer: _Renderer) -> dict[str, Path]:
    """One render per type, shared by every criterion that needs it."""
    return {t: renderer.frame(t) for t in PAYLOAD_TYPES}


def _source_scene() -> dict:
    doc = json.loads(GRAPHS.read_text(encoding='utf-8'))
    for scene in doc['scenes']:
        if scene['id'] == SOURCE_SCENE:
            return scene
    raise AssertionError(f'{SOURCE_SCENE} is not in {GRAPHS} — the fixture moved')


# ── 0. prove the object under test exists before measuring it ────────────────

def test_the_measured_objects_exist_before_they_are_measured(silent):
    """The recurring failure starts here, so it is asserted first.

    Each frame must exist AND carry ink above the measured backdrop floor of
    exactly 0.000000. "The option does nothing" and "you rendered the wrong
    frame" are indistinguishable from outside, and both are well-formed
    sentences.
    """
    assert len(silent) == len(PAYLOAD_TYPES), 'not every type was rendered'
    for t, p in silent.items():
        assert p.is_file(), f'{t}: {p} does not exist'
        ink = frame_ink(p)
        assert ink > BLANK_INK, (
            f'the {t} frame measures {ink} ink — the backdrop itself reads '
            f'{BLANK_INK} (measured, on three crops of a real render). The '
            'subject is not on this frame, so every criterion below would be '
            'measuring an empty picture and saying so with confidence.'
        )


# ── 1. the class: these types are a set, not a bag ───────────────────────────

def test_no_two_chart_types_may_render_the_same_picture(silent):
    """`area` and `line` rendered byte-identically here for a month.

    This is the general form of the defect, and it holds no expectation about
    any particular type: it says only that the set of types is a set. A default
    that is wrong for its own type shows up as a type collapsing onto one of
    its siblings, which is exactly what `area` did.

    It cannot fire on a legitimate change. The only way two types come to
    render the same picture is for one of them to stop being a distinct mark.
    """
    collapsed: list[str] = []
    for i, a in enumerate(PAYLOAD_TYPES):
        for b in PAYLOAD_TYPES[i + 1:]:
            changed = _frames_differ(silent[a], silent[b])
            assert changed >= 0, f'{a} vs {b}: frames are different sizes — not comparable'
            if changed < MIN_PAIR_DIFF:
                collapsed.append(f'{a}|{b} differ by only {changed} px')
    assert not collapsed, (
        f'these chart types render the same picture with the graph saying '
        f'nothing: {collapsed}.\n'
        'A chart type that renders like another one has no effect on the frame, '
        'whatever its name says. That is the failure this file exists for: '
        '`area` was `line`, because `option()` never returns undefined, so '
        '`option(...) ?? defaultArea` could only take its left side and the '
        'type default was unreachable. The option was very much alive -- the '
        'A/B matrix measured showArea moving 400,053 px -- and every guard was '
        'green, because "is the option live" and "is the default right for '
        'this type" are different questions.'
    )


# ── the P46 instruments agree, measured on the same real frames ──────────────

def test_the_p46_chart_measurer_agrees_on_these_real_frames(silent):
    """The instrument that was told `area` is inert, re-asked on real frames.

    `p46_chart_control.INERT_TYPES` was `{'area'}` — a literal under a comment
    reading "MEASURED INERT, not assumed", with nothing that re-measured it. P47
    made `area` distinguishable, so that constant went quietly false while its
    own comment kept saying MEASURED. The instrument now derives the set from
    the frames (`measured_inert_types`) and refuses rather than guessing when
    the evidence is incomplete.

    This runs it on the frames the test above really rendered, so the
    instrument and the thing it measures are checked against each other rather
    than each against its own idea. It costs no render: the frames are already
    on disk, which is the point — a second renderer in a second file would have
    measured its own copy and agreed with itself.
    """
    import p46_chart_control as ctl

    inert = ctl.measured_inert_types({t: [p] for t, p in silent.items()})
    assert 'area' not in inert, (
        'the P46 chart control, measuring REAL renders, still reports `area` '
        'as inert. Either the renderer regressed to drawing a bare line for an '
        'area chart, or the measurer is wrong — and both of those are exactly '
        'what this assertion exists to notice.'
    )
    assert inert == set(), (
        f'the P46 measurer reports {sorted(inert)} inert on these frames, but '
        'the frames are pairwise distinct. The two instruments disagree, and '
        'the one that is easier to believe is not the one that rendered them.'
    )
    # and the refusal path, on the same frames
    with pytest.raises(SystemExit):
        ctl.scorable_types({'bar': [silent['bar']]})


# ── 2. the mechanism: the new table has no row nobody reads ──────────────────

def test_every_type_default_row_must_move_pixels(renderer, silent):
    """The guard against the fix becoming the sixth dumb declaration.

    A row in `TYPE_DEFAULT_ROWS` that changes nothing is either redundant (it
    restates the shared default) or attached to a mark that never reads the
    option -- `bubble: {showArea: true}` would be exactly that, and it would sit
    in the source looking official forever. So each row is rendered twice: once
    with the graph silent, once with the graph stating the SHARED default
    explicitly. A row that does not separate those two renders is not doing
    anything.

    Which is also why it cannot misfire: a row whose value EQUALS the shared
    default has nothing to assert, and should be deleted rather than kept.
    """
    rows = _type_default_rows()
    assert rows, (
        'TYPE_DEFAULT_ROWS parsed empty. Either the table is gone or the parser '
        'has drifted — and an empty row set makes every assertion below pass '
        'without having rendered or checked anything.'
    )

    inert: list[str] = []
    for chart_type, entries in sorted(rows.items()):
        assert chart_type in PAYLOAD_TYPES, (
            f'TYPE_DEFAULT_ROWS has a row for {chart_type!r}, which is not one '
            f'of the types this guard renders ({list(PAYLOAD_TYPES)}). Extend '
            'PAYLOAD_TYPES or drop the row — do not leave it unchecked.'
        )
        for key, value in sorted(entries.items()):
            shared = _shared_default(key)
            assert isinstance(value, bool) or isinstance(value, (int, float, str)), (
                f'{chart_type}.{key} parsed as {type(value).__name__}, which is '
                'not something that can be written into a props file and mean '
                'what it means here.'
            )
            explicit = renderer.frame(chart_type, {key: shared})
            changed = _frames_differ(silent[chart_type], explicit)
            assert changed >= 0, f'{chart_type}/{key}: frames are different sizes'
            if changed == 0:
                inert.append(f'{chart_type}.{key}={value!r} (stated explicitly '
                             f'as {shared!r} it changes nothing)')
    assert not inert, (
        f'these per-type default rows change no pixels: {inert}.\n'
        'A row in that table is a declaration, and this is the project\'s '
        'standing failure: fifteen style_bible keys on the demo graph with one '
        'effective, showArea registered against a component that ignored it, '
        'the camera language wired but inert. A row that does not move the '
        'render is either redundant or attached to a mark that never reads the '
        'option, and both should be deleted rather than left looking official.'
    )


# ── 3. the direction: WHICH of the pair has the fill ─────────────────────────

def test_the_area_type_must_carry_the_fill_and_the_line_type_must_not(silent):
    """Criteria 1 and 2 are both symmetric, and that is the hole.

    Move the single row in `TYPE_DEFAULT_ROWS` from `area` to `line` and both
    of them stay green: the two types still differ from each other, and the row
    still separates two renders. The picture is simply the wrong way round --
    which is what the delivered graph did, for the same reason.

    So the direction has to be asked. This is the one claim about how a chart
    should look in the file, and it is not taste: `p46_chart_probe.OPTIONS`
    defines the line chart as "a single thin line drawn through a series of
    points, with no area filled in beneath it", so filled and not-filled are
    defined for this pair BY CONTRAST in a committed file. A chart with the
    fill is not a line chart by that definition.
    """
    assert _has_the_fill(silent['area'], silent['line']), (
        'the `area` type renders less ink than `line` — the per-type default is '
        'on the wrong row, or `area` fell back to the shared default. Measured: '
        f'area {frame_ink(silent["area"]):.3f}% ink, '
        f'line {frame_ink(silent["line"]):.3f}% ink.'
    )
    assert not _has_the_fill(silent['line'], silent['area']), (
        'the `line` type carries more ink than `area` — the fill is on the '
        'wrong type. A line chart that fills under its curve is not a line '
        'chart; see p46_chart_probe.OPTIONS.'
    )


# ── the delivered graph must not carry the inversion any more ────────────────

def test_the_delivered_graph_does_not_ask_a_line_chart_for_a_fill():
    """The graph half of the defect, pinned so it cannot come back alone.

    `c02_line` set `showArea: true` and `c03_area` said nothing, so the two
    shipped swapped. Under the corrected renderer the `area` type supplies its
    own fill, so the honest graph says nothing about the option on EITHER
    scene -- and saying nothing on `c03_area` is the point, because a graph
    that spelled it out there would go on proving nothing about whether a
    type's default reaches the pixels by itself.
    """
    doc = json.loads(GRAPHS.read_text(encoding='utf-8'))
    by_id = {s['id']: s for s in doc['scenes']}
    for scene_id, chart_type in (('c02_line', 'line'), ('c03_area', 'area')):
        assert scene_id in by_id, f'{scene_id} is not in {GRAPHS.name}'
        chart = by_id[scene_id]['content']['chart']
        assert chart.get('type') == chart_type, (
            f'{scene_id} declares chart.type={chart.get("type")!r}, '
            f'expected {chart_type!r}')
        assert 'showArea' not in chart, (
            f'{scene_id} ({chart_type}) sets showArea={chart["showArea"]!r}. The '
            'fill is the `area` type\'s own default and a line chart has none, '
            'so a graph that states it is either undoing the type or '
            're-introducing the inversion this fix removed.')


# ── 4. the judgements must be able to say NO ─────────────────────────────────

def test_each_criterion_is_asked_to_reject_what_it_should_reject(silent):
    """A criterion rigged to always pass is caught by RUNNING it, not reading it.

    A source-level guard can only see that a comparison EXISTS; rewriting
    `ink(area) > RATIO * ink(line)` as `ink(area) > -1` leaves every parse-based
    check perfectly green while the guard measures nothing. So the judgements
    are executed against input they must reject:

      * `_has_the_fill` must say NO to a candidate identical to its reference;
      * `_frames_differ` must say NO to a frame compared with itself, and YES
        to two frames this module has already proved differ.

    Every one of those fails if the corresponding function is rigged to a
    constant, and it costs no renders -- the frames are already on disk.

    WHAT IT DOES NOT DO: it cannot catch an extra `assert True` added beside a
    working assertion. That does not weaken the guard -- the real criterion is
    still there and still red on the defect -- so it is recorded rather than
    defended against.
    """
    assert not _has_the_fill(silent['line'], silent['line']), (
        '_has_the_fill accepted a frame as carrying a fill relative to ITSELF. '
        'The judgement cannot say no, so every assertion built on it passes '
        'without measuring anything.')
    assert not _has_the_fill(silent['area'], silent['area']), (
        '_has_the_fill accepted the area frame relative to itself — the same '
        'failure, stated against the other side.')
    assert _frames_differ(silent['area'], silent['line']) > 0, (
        '_frames_differ reported the two known-different frames as identical. '
        'Criterion 1 is then satisfied by construction, whatever is rendered.')
    assert _frames_differ(silent['line'], silent['line']) == 0, (
        '_frames_differ did not report a frame as identical to itself.')


# ── the criteria have not been quietly deleted ───────────────────────────────

def test_the_criteria_are_still_present_and_still_measure_pixels():
    """Deleting a criterion must not leave the file looking complete.

    Each criterion must still CALL its judgement -- so it is still looking at
    pixels -- and the judgement must still contain a COMPARISON -- so it can
    still go red. The comparison is checked inside the HELPER rather than in
    the test: criterion 3's two assertions are `assert _has_the_fill(...)`,
    which contain no comparison of their own, and the first draft of this guard
    failed on exactly that and would have deleted a working criterion to satisfy
    itself.
    """
    src = Path(__file__).read_text(encoding='utf-8')
    tree = ast.parse(src)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    wanted = {
        'test_no_two_chart_types_may_render_the_same_picture': '_frames_differ',
        'test_every_type_default_row_must_move_pixels': '_frames_differ',
        'test_the_area_type_must_carry_the_fill_and_the_line_type_must_not':
            '_has_the_fill',
    }
    for name, helper in wanted.items():
        assert name in funcs, f'{name} is gone — this file no longer checks it'
        assert helper in funcs, f'{helper}() is gone — the judgement it drove is gone'
        called = {c.func.id for c in ast.walk(funcs[name])
                  if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        assert helper in called, (
            f'{name} no longer calls {helper}(), so it no longer looks at '
            'pixels. It is asserting about the source again, which is the '
            'failure this file was written against.')
        compares = [n for n in ast.walk(funcs[helper]) if isinstance(n, ast.Compare)]
        assert compares, (
            f'{helper}() contains no comparison, so it cannot go red however '
            'the frames come out.')


# ── the resolver itself, executed ────────────────────────────────────────────

_NPX = shutil.which('npx') or shutil.which('npx.cmd')
OPTION_CHECK = TEMPLATE / 'options.check.ts'


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
def test_the_resolver_cannot_discard_a_value_the_graph_set():
    """`options.check.ts`, executed — the property, not a token.

    Everything above is about what the pixels do. This one is about the thing
    that makes those pixels trustworthy in the first place, and it is the
    reason a per-type table is allowed to exist at all: `option()` must never
    be able to throw away a value the graph supplied. That is the property
    `TYPE_OPTIONS` lost when it was a runtime filter, and `tsx` strips types
    without checking them, so the annotation on the table is documentation to
    this process and nothing else.

    A source check can order two lines of text. Only running the resolver over
    9 types x 17 options x 19 probe values can show that no path through it
    discards a value -- and that `option('area','showArea')` (true) and
    `option('area','showArea',{showArea:false})` (false) stay DIFFERENT, which
    is the distinction `Area` needed and could not get.
    """
    assert OPTION_CHECK.is_file(), f'no executable check at {OPTION_CHECK}'
    proc = subprocess.run(
        [_NPX, 'tsx', str(OPTION_CHECK)], cwd=str(STUDIO),
        capture_output=True, text=True, timeout=600,
        encoding='utf-8', errors='replace',
    )
    assert proc.returncode == 0, (
        f'the option resolver check failed:\n{proc.stdout}\n{proc.stderr}'
    )
    # A run that printed nothing would be a run that measured nothing.
    assert 'all option checks passed' in proc.stdout, (
        f'the check exited 0 without reporting:\n{proc.stdout[-2000:]}'
    )


def test_the_check_actually_exercises_the_properties_a_render_cannot_show():
    """The check file must name what it proves, or it is decoration.

    Same rule `test_chart_lifecycle.py` applies to `lifecycle.check.ts`: a
    guard covering nothing is the failure this project keeps meeting, and the
    names are what makes the gap visible in review.
    """
    src = OPTION_CHECK.read_text(encoding='utf-8') if OPTION_CHECK.is_file() else ''
    for load_bearing in (
        'TYPE_DEFAULT_ROWS',   # the per-type table is consulted
        'CHART_TYPES',         # over every type, not the one that was broken
        'DEFAULT_CHART_OPTIONS',
        'undefined',           # the property the old dead branch assumed
        'discards a value',    # the property TYPE_OPTIONS lost
    ):
        assert load_bearing in src, (
            f'the option check never exercises {load_bearing!r}, so it is '
            'passing vacuously over the part that matters'
        )


# ── the fix itself is where it claims to be ──────────────────────────────────

def test_the_line_and_area_marks_are_no_longer_two_components_with_a_default_prop():
    """The unreachable prop is gone rather than left with a working fallback.

    `defaultArea` could never be read: `option()` substitutes the shared default
    for an absent value, so it never returns undefined. It is checked in the
    CODE here, comments stripped, because a name in a doc comment is not a name
    in a program -- the same reason `ab_field._strip_ts_comments` exists.
    """
    src = re.sub(r'/\*.*?\*/', '', TYPES_TSX.read_text(encoding='utf-8'), flags=re.S)
    src = re.sub(r'//[^\n]*', '', src)
    assert 'defaultArea' not in src, (
        'types.tsx still threads a `defaultArea` prop. It is unreachable -- the '
        'resolver it was combined with never returns undefined -- so it is a '
        'parameter that says something about the two types while controlling '
        'nothing.')
    assert re.search(r"option\(\s*'line'", src) is None, (
        "types.tsx still resolves showArea with a hard-coded 'line'. That "
        "resolves this scene's option against a chart type that is not this "
        'one, which is what made the real type unobservable from the mark.')