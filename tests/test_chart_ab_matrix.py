"""The A/B matrix as a test, so it stops being a report nobody has to run.

P7.1b left the matrix as a script and a committed report: `chart_ab_matrix.py`
plus `out/chart_ab.md`. Both are real evidence and neither is a gate. The
report can be three weeks old and the suite stays green, so the thing that was
supposed to make "a declared option nobody reads" impossible to ship was itself
only run when someone remembered — which is the failure mode the whole P7 line
was built against, one level up.

So the matrix is split in two by what it costs:

  - the cheap half runs always. It cross-checks the declaration surface against
    the measured surface, and it checks the rule the matrix's own docstring
    records having been broken once: a timing option measured on a settled frame
    is identically zero, and identically zero is what a dead option looks like.
  - the expensive half renders 26 rows twice and is opt-in via
    `H3_AB_MATRIX=1`, because 52 renders is not a unit test. CI can set it;
    a developer running the suite does not have to.

Run the renders with:

    H3_AB_MATRIX=1 python -m pytest tests/test_chart_ab_matrix.py -q
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'studio' / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import ab_field  # noqa: E402
import chart_ab_matrix as matrix  # noqa: E402

#: Options that describe WHEN a mark arrives. On a settled frame they are
#: identically zero by construction, and that zero is indistinguishable from a
#: field nobody reads — which is how a live row got reported dead once.
TIMING_OPTIONS = {'enterFrames', 'staggerFrames'}


def _measured_options() -> set[str]:
    return {path.split('.')[-1] for _, _, path, _, _ in matrix.MATRIX}


def test_every_registered_option_has_a_measured_row():
    """The declaration surface and the measured surface must not drift apart.

    `FIELD_READERS` is every option the chart API declares; a MATRIX row is the
    only proof that the option is read by the component it claims. An option
    added to the API with no row is exactly the state P7.1b shipped `showArea`
    in, so it is worth failing on rather than mentioning in a report.
    """
    missing = sorted(set(ab_field.FIELD_READERS) - _measured_options())
    assert not missing, (
        f'registered but never measured: {missing}. A registered option with no '
        f'A/B row is a claim, not evidence.'
    )


def test_no_row_claims_to_measure_an_option_the_registry_does_not_know():
    """The reverse drift: a row for something the chart API does not declare.

    `theme` is deliberately here and is not an option — it is a scene field, and
    it earns its row because the heat ramp follows it, which was the one place a
    light theme could change the backdrop and leave the marks untouched. So the
    exception is named rather than the assertion loosened.
    """
    extra = sorted(_measured_options() - set(ab_field.FIELD_READERS) - {'theme'})
    assert not extra, f'measured but not a declared option: {extra}'


def test_a_timing_option_is_never_measured_on_a_settled_frame():
    """The rule the matrix's own docstring records having been broken once.

    `enterFrames` capped a 150-frame scene's entrance at 51 frames, so both 34
    and 90 clamped to 51: the option was doing nothing at that duration and the
    measurement correctly reported nothing. Reading that as "the field is dead"
    would have deleted a live option. The escape was a 600-frame scene, and the
    rule that prevents the mistake recurring is that a timing row declares
    ENTERING.
    """
    wrong = [
        (path, kind)
        for _, _, path, _, kind in matrix.MATRIX
        if path.split('.')[-1] in TIMING_OPTIONS and kind != matrix.ENTERING
    ]
    assert not wrong, (
        f'timing options measured as {matrix.SETTLED}: {wrong}. On a settled '
        f'frame they are identically zero, which reads exactly like a dead field.'
    )


def test_every_row_declares_how_it_must_be_measured():
    for _, frame, path, _, kind in matrix.MATRIX:
        assert kind in (matrix.SETTLED, matrix.ENTERING), f'{path}: unknown kind {kind}'
        assert frame >= 0, f'{path}: negative frame'


@pytest.mark.skipif(
    os.environ.get('H3_AB_MATRIX') != '1',
    reason='52 renders; set H3_AB_MATRIX=1 to run the measured half',
)
def test_the_matrix_renders_and_no_row_is_inert(tmp_path, monkeypatch):
    """The measured half. Exit code 1 means at least one row moved zero pixels."""
    report = tmp_path / 'chart_ab.md'
    monkeypatch.setattr(sys, 'argv', ['chart_ab_matrix.py', '--out', str(report)])
    code = matrix.main()
    assert code == 0, (
        'the matrix found an inert option; the report above names it. A row of '
        'zeros is a declared option nobody reads.'
    )
    assert report.exists(), 'the matrix produced no report'
