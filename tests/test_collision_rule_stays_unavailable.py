"""`collision` must stay UNAVAILABLE until someone sets a threshold.

The geometry instrument exists and is validated — chart_geometry.py measures
label width against centre spacing from the chart options, agreeing with
rendered frames to 0.2% at 5 and 16 bars. That is the easy part.

What is missing is a THRESHOLD, and this file exists to make that absence
explicit rather than let it get filled in by whoever is nearest. The temptation
is concrete: the instrument is right there, it returns a number, and turning
that number into PASS/FAIL is a two-line change that would make the QA report
look more complete. It would also be an invented policy — the ledger names no
collision threshold, and the delivered charts measure 0.278, so any cut point
would be a preference dressed as a measurement.

This is the same distinction the four verdicts exist for, applied at the point
where it is hardest: an instrument that works, reporting a state it cannot yet
decide.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'studio' / 'scripts'))

import visual_qa as vqa  # noqa: E402
import chart_geometry as cg  # noqa: E402


def _collision_detail() -> str:
    for f in vqa.unavailable_findings():
        if f.rule == 'collision':
            return f.detail
    raise AssertionError('collision is no longer reported as unavailable — read why')


def test_collision_is_still_unavailable():
    assert 'collision' in vqa.UNIMPLEMENTED, (
        'collision left UNIMPLEMENTED without a replacement — either it now has '
        'a verdict (and a threshold to justify it) or it belongs here'
    )
    finding = next(f for f in vqa.unavailable_findings() if f.rule == 'collision')
    assert finding.verdict == vqa.UNAVAILABLE
    assert finding.value is None, 'an unavailable rule must not carry a number'
    assert not finding.trusted, 'an unavailable rule is by definition untrusted'


def test_the_reason_names_the_instrument_and_the_missing_piece():
    """The reason has to say BOTH what exists and what does not.

    Only saying "no detector" is now false and would send the next person
    rebuilding what chart_geometry.py already does. Only saying "instrument
    ready" would imply the rule is one line from a verdict, which is exactly
    the gap nobody should close by accident.
    """
    detail = _collision_detail()
    assert 'chart_geometry' in detail, (
        'the reason must name the instrument that now exists, or the next '
        f'reader rebuilds it. Current reason: {detail!r}'
    )
    assert 'threshold' in detail.lower(), (
        f'the reason must name what is actually missing. Current: {detail!r}'
    )


def test_the_reason_states_the_instrument_is_built_not_still_missing():
    """Mutations A2 and A3 survived a check for the WORD 'chart_geometry'.

    Both rewrote the sentence around the word and left it in place, so
    'the instrument is built' and 'no threshold has been set' both had to be
    asserted as statements rather than as substrings. A token that survives
    every rewording of the sentence around it is not evidence of anything.
    """
    d = _collision_detail().lower()
    assert 'instrument is built' in d or 'instrument now exists' in d, (
        'the reason must state that the detector EXISTS — otherwise the next '
        f'person rebuilds what chart_geometry.py already does. Current: {d[:120]!r}'
    )
    assert 'no threshold' in d, (
        'the reason must state that no threshold has been set — that is the '
        f'actual blocker. Current: {d[:120]!r}'
    )
    assert 'unavailable' in d, 'the reason must not read as if the rule decides'


def test_the_reason_carries_the_measurement_not_a_guess():
    """It should cite numbers someone can re-run, or it is folklore."""
    detail = _collision_detail()
    for token in ('334', '104', '0.278'):
        assert token in detail, (
            f'{token!r} missing from the collision reason — a claim about the '
            f'instrument with no numbers in it is not checkable. Current: {detail!r}'
        )


def test_the_delivered_charts_really_do_measure_0_278():
    """Guards the number quoted in the reason above.

    The reason tells a future reader the shipped charts sit at 0.278. If that
    stops being true the sentence becomes a lie that nobody notices, because
    prose in a code comment is not re-derived the way a test is.
    """
    import json
    worst = None
    for p in sorted((ROOT / 'pipeline' / 'examples').glob('*.json')):
        fit, _n = cg.worst_chart_fit(json.loads(p.read_text(encoding='utf-8')))
        if fit and (worst is None or fit.ratio > worst.ratio):
            worst = fit
    assert worst is not None
    assert f'{worst.ratio:.3f}' == '0.278', (
        f'the collision reason quotes 0.278 but the shipped charts now measure '
        f'{worst.ratio:.3f} ({worst.text!r}) — update the sentence or the code'
    )


def test_setting_a_threshold_requires_editing_this_file():
    """Make the decision expensive on purpose.

    If a threshold is ever set, this test fails and points at the file that
    records why one was not. That is the intended workflow: the person choosing
    the threshold has to state it, and the reason string is updated with it.
    """
    src = Path(__file__).read_text(encoding='utf-8')
    assert 'THRESHOLD_NOT_SET' in src, (
        'this file is the record that no collision threshold exists; if that '
        'changed, rename the assertion deliberately rather than quietly'
    )
    assert not hasattr(cg, 'COLLISION_THRESHOLD'), (
        'chart_geometry.py must not grow a threshold constant — the instrument '
        'measures, the caller decides, and a threshold inside the instrument is '
        'a verdict wearing a lab coat'
    )


def test_the_other_rules_keep_their_original_reasons():
    """overflow and broken_font keep their reasons; flicker moved in P23.

    Only `collision` and `flicker` were rewritten, each by a work order that
    measured why, and each under its own behavioural guard. This file pins
    the other two, whose reasons still stand. flicker used to appear here as
    ('flicker', 'time-series') -- a substring check on prose that pinned a
    sentence which P23 measured to be FALSE (the corpus does provide a
    sequence). Pinning a false sentence is worse than pinning none, so it was
    removed rather than re-worded; tests/test_p23_flicker_stays_unavailable
    .py now guards that rule behaviourally.
    """
    for rule, needle in (('overflow', 'three attempts failed'),
                         ('broken_font', 'font-file')):
        detail = vqa.UNIMPLEMENTED[rule]
        assert needle in detail, f'{rule} reason was rewritten: {detail!r}'
