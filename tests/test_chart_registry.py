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
    measured = {dotted.rsplit('.', 1)[-1] for _, _, dotted, _ in matrix.MATRIX}
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
