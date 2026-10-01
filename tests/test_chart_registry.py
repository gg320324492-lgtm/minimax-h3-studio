"""The chart option surface and the registry must be the same set (P7.1).

The registry (Python, `ab_field.FIELD_READERS`) and the declared option surface
(TypeScript, `charts/options.ts`) are two lists that have to agree. They can
drift, and either direction of drift is the failure this project keeps meeting:

  - a key in TYPE_OPTIONS with no registry entry  -> a chart field nobody vouches for
  - a registry entry with no TYPE_OPTIONS key      -> a field the guard claims to
    police that no chart can actually receive

So the two are compared here, key for key, rather than trusted.

Everything else in this file checks that the engine's guards are load-bearing:
that a declared option really is read by the file registered against it, and
that the maths has teeth (mutation-checked, see tests/test_chart_math.py).

Run:
  python -m pytest tests/test_chart_registry.py -q
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / 'studio'
TEMPLATE = STUDIO / 'src' / 'templates' / 'finance-showcase'
OPTIONS_TS = TEMPLATE / 'charts' / 'options.ts'


def _load_ab():
    spec = importlib.util.spec_from_file_location('ab_field', STUDIO / 'scripts' / 'ab_field.py')
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ab = _load_ab()


def _declared_option_keys() -> set[str]:
    """The option names declared in TYPE_OPTIONS, read out of the source.

    Parsed rather than imported because this suite is pytest-on-Python and the
    TypeScript checks are reached through tsx. What matters is that the two
    SOURCE files agree, not that a third copy agrees with both.

    TYPE_OPTIONS is the declaration — ALL_OPTION_KEYS is derived from it at
    runtime with `new Set(...flat())`, so it has no literals to read.
    """
    src = OPTIONS_TS.read_text(encoding='utf-8')
    block = src.split('export const TYPE_OPTIONS', 1)[1].split('};', 1)[0]
    return set(re.findall(r"'([A-Za-z]+)'", block))


def test_registry_names_exactly_the_declared_option_surface():
    declared = _declared_option_keys()
    registered = set(ab.FIELD_READERS)
    missing = declared - registered
    extra = registered - declared
    assert not missing, (
        f'declared in charts/options.ts but absent from FIELD_READERS: {sorted(missing)}. '
        f'A chart option with no registry entry is a field nobody vouches for.'
    )
    assert not extra, (
        f'registered in FIELD_READERS but not declared in charts/options.ts: {sorted(extra)}. '
        f'The guard claims to police a field no chart can receive.'
    )
    assert declared, 'ALL_OPTION_KEYES parsed empty — the parser is wrong, not the table'


def test_every_registered_option_is_actually_read_by_its_registered_reader():
    """The half a registry cannot check by itself.

    A registry that only confirms its own entries exist would happily vouch for
    an option no component reads — which is precisely the demo graph's fifteen
    style_bible keys, one of which worked.
    """
    problems = ab.check_registry()
    assert not problems, f'registry problems:\n' + '\n'.join(problems)


def test_neither_path_filters_options_by_the_documented_table():
    """Two gates, not one.

    `option()` stopped consulting TYPE_OPTIONS, but `pickOptions` was still
    filtering the graph's bag by ALL_OPTION_KEYS — which is derived from
    TYPE_OPTIONS. So a value could still be discarded at the ENTRY, before
    option() saw it, and the docstring claiming otherwise was simply untrue. A
    false statement in a comment about a design guarantee is the same class of
    error this project has now hit several times, in a place that looks like a
    promise.
    """
    adapter = (TEMPLATE / 'charts' / 'Chart.tsx').read_text(encoding='utf-8')
    # slice to the next top-level declaration, not to the first `};` — the
    # function opens with `const out = {};` and a shorter slice sees only that
    pick = adapter.split('const pickOptions', 1)[1].split('export const normaliseChart', 1)[0]
    # from the arrow onwards, so the docstring that NAMES ALL_OPTION_KEYS in
    # order to explain why it is not used does not trip the check
    body = pick[pick.index('=> {') + 3:]
    assert 'ALL_OPTION_KEYS' not in body, (
        'pickOptions must not filter by ALL_OPTION_KEYS — it is derived from '
        'TYPE_OPTIONS, and a stale table would discard a value the graph set'
    )
    assert 'DEFAULT_CHART_OPTIONS' in body, (
        'pickOptions must key off the defaults, which TypeScript guarantees '
        'complete because the object is typed ChartOptions'
    )


def test_options_and_data_are_separated_in_the_adapter():
    """`content.chart` is one bag, but options and data are different things.

    If the adapter passed the whole bag as options, an unrecognised key would
    become a silently-ignored prop and a typo in a data key could be read as an
    option. So only declared keys are lifted out.
    """
    src = (TEMPLATE / 'charts' / 'Chart.tsx').read_text(encoding='utf-8')
    assert 'pickOptions' in src, 'the adapter must separate options from data'
    assert 'ALL_OPTION_KEYS' in src, 'the separation must be driven by the declared surface'
    assert 'options={spec}' not in src, (
        'the whole bag must not be passed as options — that is the conflation this split exists to stop'
    )


def test_no_chart_mark_owns_its_own_scale():
    """A mark that computes its own domain can disagree with the axis it is drawn
    against — readable and wrong at the same time, which is the worst kind of
    chart bug because nobody notices."""
    src = (TEMPLATE / 'charts' / 'types.tsx').read_text(encoding='utf-8')
    assert 'useFrame' in src, 'marks must take their scale from the frame'
    # domainFor / niceTicks decide the scale; a mark must not call them
    for fn in ('domainFor', 'niceTicks('):
        assert fn not in src, (
            f'types.tsx calls {fn} — a mark must not derive its own domain; '
            f'the frame owns it and hands it down'
        )


def test_marks_are_measured_against_the_audited_tools():
    """Two engines exist in this project: the pixel measurer (audited through
    three versions) and the field A/B (audited after the stale-frame defect).
    P7 marks must be checkable with one of them, which means every chart option
    needs a graph that renders it — asserted by the A/B runs, not here."""
    assert (STUDIO / 'scripts' / 'measure_frame.py').exists()
    assert (STUDIO / 'scripts' / 'ab_field.py').exists()
    # and the maths is reachable without React, so it can be checked
    scale = (TEMPLATE / 'charts' / 'scale.ts').read_text(encoding='utf-8')
    assert 'react' not in scale, 'the maths must stay importable without React'


@pytest.mark.parametrize('chart_type', ['bar', 'line', 'area', 'slope', 'bubble',
                                        'heatmap', 'rank', 'sparkline', 'volume'])
def test_every_declared_chart_type_has_a_mark(chart_type):
    """A type in CHART_TYPES with no mark is a type that renders nothing."""
    src = (TEMPLATE / 'charts' / 'types.tsx').read_text(encoding='utf-8')
    dispatch = src.split('export const MARK', 1)[1]
    assert f'{chart_type}:' in dispatch, f'{chart_type} is declared but not dispatched'


def test_every_declared_option_has_a_b_measurement():
    """The discipline, made mechanical.

    A source-level check cannot tell an option that is read from one that is
    merely NAMED in the right file — `showArea` was registered against
    types.tsx, present in types.tsx, and inert for every `line` chart. The A/B is
    the only check that can, so every declared option must appear in the matrix.

    Adding an option without measuring it is therefore a failing test, not a
    capability nobody has looked at.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'chart_ab_matrix', STUDIO / 'scripts' / 'chart_ab_matrix.py')
    assert spec and spec.loader
    matrix = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(matrix)

    declared = _declared_option_keys()
    measured = {dotted.rsplit('.', 1)[-1] for _, _, dotted, _v, _k in matrix.MATRIX}
    missing = sorted(declared - measured)
    assert not missing, (
        f'declared chart options with no A/B evidence: {missing}. Run '
        f'studio/scripts/chart_ab_matrix.py and add a row for each.'
    )


def test_type_options_is_not_a_runtime_gate():
    """A declared surface that can silence a working option will, eventually.

    `TYPE_OPTIONS.volume` omitted `emphasisIndex`; the runtime filter then threw
    every volume chart's emphasis away while the registry check still reported
    the option as read. The table is documentation now, and this asserts the
    filter is gone so it cannot come back.
    """
    src = (TEMPLATE / 'charts' / 'options.ts').read_text(encoding='utf-8')
    body = src.split('export const option =', 1)[1]
    assert 'TYPE_OPTIONS[chart]' not in body, (
        'option() must not filter by TYPE_OPTIONS at runtime — a stale table '
        'would silently discard a value the graph set'
    )
    assert 'void chart;' in body, 'the chart type is documentation now; say so'


def _component(src: str, start: str, end: str) -> str:
    """The body of one component, between two anchors, or a loud failure."""
    assert start in src, f'{start!r} not found — the component moved or was renamed'
    tail = src.split(start, 1)[1]
    assert end in tail, f'{end!r} not found after {start!r}'
    return tail.split(end, 1)[0]


def test_no_chart_mark_hardcodes_a_colour():
    """A colour literal in a mark is a value that works on one theme.

    The heat ramp shipped as rgba(245,242,234,·) — the DARK theme's ink — so on
    paper a higher value turned whiter, i.e. fainter. Themes own colour; marks
    own geometry. Comments are stripped first, because the fix's own comment
    names the literal it replaced, and a check that flags its own explanation
    teaches people to delete the explanation.
    """
    src = ab._strip_ts_comments(
        (TEMPLATE / 'charts' / 'types.tsx').read_text(encoding='utf-8')
    )
    import re
    hexes = re.findall(r'#[0-9a-fA-F]{6}\b', src)
    assert not hexes, f'types.tsx hardcodes colour literals: {hexes}'
    assert 'rgba(' not in src, 'types.tsx builds a colour from raw rgba()'


def test_slope_draws_against_the_frame_scale():
    """A mark must not invent a scale beside the axis it is drawn against.

    The slope chart fit its own [min, max] while the frame drew ticks from the
    headroom-padded domain: measured, the top endpoint sat 36px above where the
    "60" tick said 61 belonged (tick spacing 210.5px per 10 units, line top
    y=58, frame-correct y=93). The old test only knew two function NAMES
    (domainFor / niceTicks) and missed this pattern entirely — so the assertions
    are about what the component must use and must not declare.
    """
    src = (TEMPLATE / 'charts' / 'types.tsx').read_text(encoding='utf-8')
    slope = _component(src, 'export const Slope', 'const Dot')
    assert 'f.yOf' in slope, 'Slope must draw against the frame scale'
    assert ': Extent' not in slope, 'Slope declares its own extent again'
    assert 'const domain' not in slope, 'Slope fits its own domain again'


def test_sparkline_is_on_the_shared_lifecycle():
    """The ninth mark used to ignore the timeline the other eight follow:

    no entrance, no exit fade — scene c09 popped in and out while every other
    chart scene arrived and left. presence and the shared entrance are what
    make nine marks read as one film.
    """
    src = (TEMPLATE / 'charts' / 'types.tsx').read_text(encoding='utf-8')
    spark = _component(src, 'export const Sparkline', 'export const VolumeBars')
    assert 'enterFor' in spark, 'Sparkline does not take the shared entrance'
    assert 'life.presence' in spark, 'Sparkline does not leave with the scene'
    assert 'strokeDashoffset' in spark, 'Sparkline does not draw on'


def test_type_options_matches_what_the_marks_actually_read():
    """Documentation drift in both directions, one test.

    sparkline gained enterFrames when it joined the lifecycle; slope LOST
    showValues because the slope mark never read it (it only moved the frame's
    headroom — a documented option that does something else is worse than an
    undocumented one).
    """
    src = (TEMPLATE / 'charts' / 'options.ts').read_text(encoding='utf-8')
    import re
    spark = re.search(r"sparkline:\s*\[([^\]]*)\]", src)
    assert spark, 'TYPE_OPTIONS.sparkline not found'
    assert "'enterFrames'" in spark.group(1), 'sparkline animates now; document its knob'
    slope = re.search(r"slope:\s*\[([^\]]*)\]", src)
    assert slope, 'TYPE_OPTIONS.slope not found'
    assert "'showValues'" not in slope.group(1), (
        'slope claims showValues but the slope mark never reads it'
    )


def test_the_bubble_frame_does_not_duplicate_the_marks_labels():
    """c05 rendered Mon..Sat twice: per-circle (right place) and along the
    frame's bottom row, where (i + 0.5) / n lies for a multi-row grid."""
    src = (TEMPLATE / 'charts' / 'Chart.tsx').read_text(encoding='utf-8')
    import re
    m = re.search(r'xLabels=\{([^}]*)\}', src)
    assert m, 'ChartFrame gets no xLabels prop — the assertion is stale'
    assert 'bubble' not in m.group(1), (
        f'bubble is in the frame xLabels condition ({m.group(1).strip()}) — '
        f'the frame and the mark would both draw the labels'
    )


def test_the_nine_marks_place_labels_with_the_by_y_variant():
    """The pure function is checked; this checks that anyone CALLS it.

    `declutterByY` is in `scale.check.ts` and its behaviour cannot rot. What
    nothing checked was the call sites: replacing `declutterByY` with plain
    `declutter` in `types.tsx` leaves the function correct, leaves all 110
    tests green, and leaves all three .check.ts files passing — because the
    regression is invisible at every level that exists.

    The defect that mutation reintroduces is the one P7.3 fixed by
    measurement: plain `declutter` assumes the labels arrive ordered by value,
    which holds for none of the nine marks (a bar chart's are in CATEGORY
    order), so it pushes labels down into the bars they belong to — two of them
    160px and 322px inside their own columns.

    So this forbids the plain variant at a call site, which is a stronger
    statement than "the function exists" and the only one that would have
    caught it.
    """
    src = (TEMPLATE / 'charts' / 'types.tsx').read_text(encoding='utf-8')
    plain = re.findall(r'(?<![\w.])declutter\s*\(', src)
    assert not plain, (
        f'types.tsx calls plain declutter() {len(plain)} time(s). Its ordering '
        f'assumption is that labels arrive sorted by value, which is false for '
        f'every mark that places a label; use declutterByY.'
    )
    calls = len(re.findall(r'(?<![\w.])declutterByY\s*\(', src))
    assert calls >= 1, 'types.tsx must actually place labels with declutterByY'
