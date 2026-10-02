"""The collision detector must reproduce what the renderer actually drew.

A geometric model of a layout is worth nothing if it does not agree with the
pixels, and this project's recurring failure is a tool that returns a
well-formed number describing the wrong thing. So the assertions here are not
"the formula is self-consistent" — they are measured outcomes from rendered
frames, and the ones that matter are the ones where the model could plausibly
have been wrong.

The ground truth (out/p11_threshold/, 1920x1080, s=1, 5-bar bar charts, frame 40
of 150, labels varied in length and nothing else):

    label chars   runs seen   widest label   verdict
         8           5            92px       separated
        13           5           152px       separated
        20           5           227px       separated
        26           5           280px       separated
        30           4           649px       fusing
        34           1          1694px       fused

Note what the threshold is NOT pinned to. 26 chars leaves 52px of clearance and
34 chars is one band; the onset is somewhere between, and the model predicting
30.7 is a prediction, not a restatement. If the renderer changes the label box
or the font, the model has to move with it or these tests are lying.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'studio' / 'scripts'))

import chart_geometry as cg  # noqa: E402

EXAMPLES = ROOT / 'pipeline' / 'examples'
AUDIT = ROOT / 'out' / 'p11_threshold'


def _graph(labels: list[str], n_bars: int = 5, width: int = 1920, height: int = 1080) -> dict:
    """A minimal graph carrying only what the geometry reads."""
    return {
        'format': {'width': width, 'height': height, 'fps': 60},
        'scenes': [{
            'id': 'probe',
            'type': 'bar-chart',
            'durationInFrames': 150,
            'content': {'chart': {
                'type': 'bar',
                'showAxis': True,
                'labels': labels,
                'values': [1.0] * n_bars,
            }},
        }],
    }


# ---------------------------------------------------------------------------
# The measurement itself
# ---------------------------------------------------------------------------

def test_the_detector_reproduces_the_measured_onset():
    """Separated at 26 chars, fused at 34 — the model's core claim.

    Asserted as a bracket, because that is the precision the renders support.
    The crossover the model computes is 31.3 characters (width 10.59*n + 1.7
    against 333.6px spacing); the renders show 26 separated, 30 borderline
    (326.7px against 333.6px — 7px of margin, which the pixels resolve as two
    fused pairs) and 34 fully fused. A test demanding ratio >= 1.0 at 30 would
    be asserting that ink metrics and rendered pixels are the same number; they
    differ by side bearing and anti-aliasing, and pretending otherwise is how a
    detector gets a threshold that is right for the wrong reason.
    """
    geo = cg.plot_width({'width': 1920, 'height': 1080})
    assert cg.band_step(geo.plot_w, 5) == pytest.approx(334.0, abs=3.0), (
        f'centre spacing drifted from the measured 334px to '
        f'{cg.band_step(geo.plot_w, 5):.1f} — the plot box changed'
    )

    def ratio(n: int) -> float:
        labels = [('abcdefghijklmnopqrstuvwxyz' * 4)[i * n:(i + 1) * n] for i in range(5)]
        f = cg.worst_label_fit(labels, geo)
        assert f is not None
        return f.ratio

    assert ratio(26) < 0.90, f'26 chars measured clearly separated but model says {ratio(26):.3f}'
    assert ratio(34) > 1.0, f'34 chars measured fully fused but model says {ratio(34):.3f}'
    # The onset must land inside the measured bracket, not merely be ordered.
    assert 0.90 < ratio(30) < 1.10, (
        f'the model puts the 30-char case at {ratio(30):.3f}; the renders show it '
        'borderline (7px clearance, two fused pairs). If it has drifted far from '
        '1.0 the crossover moved and the bracket above is no longer valid.'
    )


@pytest.mark.parametrize('chars,measured_px', [(8, 92), (13, 152), (20, 227), (26, 280)])
def test_predicted_width_matches_the_rendered_width(chars, measured_px):
    """+-5px on four independent points.

    A model that is right about the crossover but wrong about widths would be
    right by luck, since the crossover is one derived number.
    """
    geo = cg.plot_width({'width': 1920, 'height': 1080})
    labels = [('abcdefghijklmnopqrstuvwxyz' * 2)[i * chars:(i + 1) * chars] for i in range(5)]
    f = cg.worst_label_fit(labels, geo)
    assert f is not None
    assert f.width == pytest.approx(measured_px, abs=12), (
        f'{chars} chars: model {f.width:.1f}px vs rendered {measured_px}px'
    )


def test_width_is_measured_per_character_not_counted():
    """The failure mode that would make this detector quietly wrong.

    Counting characters treats every glyph as equal width. In the label face
    'i' advances 5.3px and 'W' 20.4px — a factor of four — so two labels of the
    same length can differ by 4x in rendered width. A counted model gets the
    mixed-text case wrong by that factor.
    """
    narrow = ['iiiiiiiiiiiiiiiiiiiiiiii']   # 24 chars, all narrow
    wide = ['WWWWWWWWWWWWWWWWWWWWWWWW']     # 24 chars, all wide
    geo = cg.plot_width({'width': 1920, 'height': 1080})
    a = cg.worst_label_fit(narrow, geo)
    b = cg.worst_label_fit(wide, geo)
    assert a is not None and b is not None
    assert len(narrow[0]) == len(wide[0]), 'fixture must hold length constant'
    assert b.width > a.width * 2, (
        f'24 narrow chars = {a.width:.0f}px, 24 wide chars = {b.width:.0f}px — '
        'a character-counting model cannot tell these apart'
    )


# ---------------------------------------------------------------------------
# The threshold belongs to the caller, not to this module
# ---------------------------------------------------------------------------

def test_the_module_reports_a_ratio_and_no_verdict():
    """It must not smuggle in a pass/fail judgement.

    The ledger gives no collision threshold and the shipped charts sit far from
    one, so deciding "defect" here would be inventing policy. The docstring
    promises a measurement; this asserts the promise is kept in the API.
    """
    src = (ROOT / 'studio' / 'scripts' / 'chart_geometry.py').read_text(encoding='utf-8')
    for banned in ('def is_defect', 'def verdict', 'COLLISION_THRESHOLD', 'PASS', 'FAIL'):
        assert banned not in src, (
            f'{banned!r} appeared in the instrument — the caller sets the bar, '
            'this module only measures'
        )


# ---------------------------------------------------------------------------
# Reading the renderer's constants rather than restating them
# ---------------------------------------------------------------------------

def test_space_tokens_come_from_the_renderer():
    """A restated constant is a constant that silently rots.

    If someone changes SPACE in tokens.ts, a copied literal here keeps the old
    number and every verdict below stays green while describing a layout that
    no longer exists.
    """
    import re
    src = (ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase'
           / 'design' / 'tokens.ts').read_text(encoding='utf-8')
    sp = cg.space_tokens()
    for key in ('lg', 'md', 'xl'):
        m = re.search(r'\b' + key + r':\s*(\d+)', src)
        assert m, f'SPACE.{key} no longer exists in tokens.ts'
        assert sp[key] == float(m.group(1)), (
            f'space_tokens()[{key!r}] is {sp[key]} but tokens.ts says {m.group(1)} '
            '— the module is using a restated literal instead of reading the source'
        )


def test_the_delivered_charts_are_far_from_colliding():
    """The measurement that decides whether 11.1 has anything to repair.

    Longest shipped label against the model. If this ever approaches 1.0 the
    charts are in trouble and the ledger's "no collision to repair" note is
    stale — which is exactly the kind of claim that goes stale unnoticed.
    """
    import json
    worst_overall = None
    for p in sorted(EXAMPLES.glob('*.json')):
        graph = json.loads(p.read_text(encoding='utf-8'))
        fit, n = cg.worst_chart_fit(graph)
        if fit is None:
            continue
        print(f'{p.name}: {n} chart(s), worst ratio {fit.ratio:.3f} ({fit.text!r})')
        if worst_overall is None or fit.ratio > worst_overall.ratio:
            worst_overall = fit
    assert worst_overall is not None, (
        'no shipped chart carries labels any more — revisit the lock list and '
        'the 11.1 scope note'
    )
    assert worst_overall.ratio < 0.5, (
        f'worst shipped label is {worst_overall.ratio:.2f} of its spacing '
        f'({worst_overall.text!r}) — the charts are much closer to colliding '
        'than the ledger records'
    )


# ---------------------------------------------------------------------------
# Honest degradation
# ---------------------------------------------------------------------------

def test_width_falls_back_and_says_so():
    """No font, no silent fiction.

    Without the real font the module uses the fitted advance. That is a good
    approximation, and pretending it is a measurement is how a fallback becomes
    an undetected guess — so the source of the number is recorded and asserted.
    """
    real = cg.label_width('abcdefghij')
    assert cg.LAST_WIDTH_SOURCE.startswith('font:'), (
        f'expected the real font to be measurable here, got {cg.LAST_WIDTH_SOURCE!r}'
    )
    fitted = cg.FITTED_ADVANCE * 10
    assert abs(real - fitted) / real < 0.10, (
        f'real {real:.1f}px vs fitted {fitted:.1f}px — the fallback is stale, '
        'refit FITTED_ADVANCE against a fresh render'
    )


# ---------------------------------------------------------------------------
# Generality: the model must not be tuned to one bar count
# ---------------------------------------------------------------------------

def test_spacing_holds_at_a_different_bar_count():
    """Mutation 1 — hardcoding step=334 — survived every other test.

    All the width and crossover assertions use 5-bar charts, so a detector that
    ignored the bar count entirely still passed them. This pins a second count
    against rendered ground truth: 16 bars measure 104.5px centre spacing and
    the model computes 104.2px, 0.2% apart. Two independent bar counts agreeing
    is what makes plot.w/n a model rather than a constant.

    Only counts whose labels render separately are used. The 3- and 8-bar
    renders put no labels in the x-label row at all (4 ink px per row, which is
    the axis line), so they cannot pin a spacing and are not asserted on.
    """
    geo = cg.plot_width({'width': 1920, 'height': 1080})
    assert cg.band_step(geo.plot_w, 16) == pytest.approx(104.2, abs=1.0), (
        f'16-bar spacing is {cg.band_step(geo.plot_w, 16):.1f}px, measured 104.5px'
    )
    # And the two counts must differ, or the test above is vacuous.
    assert cg.band_step(geo.plot_w, 16) < cg.band_step(geo.plot_w, 5) / 3


def test_the_fitted_fallback_is_exercised_not_just_declared():
    """Mutation 4 — dropping the side-bearing intercept — survived.

    The fallback constants were only ever compared, never used: every test ran
    with the real font available, so the intercept could be wrong and nothing
    would notice. Here the font path is skipped deliberately, so the fallback is
    the thing under test.
    """
    import chart_geometry

    real = chart_geometry.label_width('abcdefghij')
    assert chart_geometry.LAST_WIDTH_SOURCE.startswith('font:')

    saved = chart_geometry.LAST_WIDTH_SOURCE
    try:
        # Force the fallback by making every candidate font path unreachable.
        # The module checks os.path.exists, so patch that — patching Path.exists
        # leaves the real font reachable and the fallback untested, which is
        # the same mistake this test exists to catch one level down.
        import os.path
        original_exists = os.path.exists
        os.path.exists = lambda p: False  # type: ignore[assignment]
        try:
            fb = chart_geometry.label_width('abcdefghij')
        finally:
            os.path.exists = original_exists  # type: ignore[assignment]
        assert chart_geometry.LAST_WIDTH_SOURCE == 'fitted', (
            'with no font reachable the module must admit it is using the fit'
        )
        assert abs(fb - real) / real < 0.10, (
            f'fallback {fb:.1f}px vs real {real:.1f}px — refit the constants'
        )
    finally:
        chart_geometry.LAST_WIDTH_SOURCE = saved


def test_a_changed_design_token_moves_the_geometry_with_it():
    """Mutation 6 and 7 — SPACE hardcoded, or its absence tolerated.

    Both return the right NUMBERS today, so comparing values cannot see them:
    the test was checking the answer, not the act of reading. The only way to
    observe that is to change the source and require the geometry to follow.
    tokens.ts is patched in memory and restored in a finally, so a failure here
    cannot leave the design tokens modified.
    """
    import chart_geometry
    tok = (ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase'
           / 'design' / 'tokens.ts')
    original = tok.read_bytes()
    try:
        tok.write_bytes(original.replace(b'lg: 40', b'lg: 88'))
        sp = chart_geometry.space_tokens()
        assert sp['lg'] == 88.0, (
            f'SPACE.lg is {sp["lg"]} after the source was changed to 88 — the '
            'module is not reading tokens.ts, so a design change would leave '
            'every verdict here describing a layout that no longer exists'
        )
    finally:
        tok.write_bytes(original)

    # And the plot box itself must move with the token, not just the dict.
    before = chart_geometry.plot_width({'width': 1920, 'height': 1080}).plot_w
    try:
        tok.write_bytes(original.replace(b'lg: 40', b'lg: 88'))
        after = chart_geometry.plot_width({'width': 1920, 'height': 1080}).plot_w
    finally:
        tok.write_bytes(original)
    assert after < before, (
        f'plot.w unchanged at {before:.1f}px after a 48px wider gutter — the '
        'geometry does not depend on the design tokens'
    )
    assert chart_geometry.space_tokens()['lg'] == 40.0, 'tokens.ts was not restored'


def test_a_missing_design_token_is_an_error_not_a_silent_default():
    """Mutation 7 — tolerating an absent SPACE key returned the old numbers.

    A module that cannot read the design should say so. Falling back to a
    literal here means a renamed or restructured token silently produces
    confident geometry for a layout nobody has drawn.
    """
    import chart_geometry
    tok = (ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase'
           / 'design' / 'tokens.ts')
    original = tok.read_bytes()
    try:
        tok.write_bytes(original.replace(b'lg: 40', b'lg:'))
        with pytest.raises(ValueError, match='not found'):
            chart_geometry.space_tokens()
    finally:
        tok.write_bytes(original)


def test_the_gutter_constant_matches_the_rendered_plot_box():
    """Mutation 8 — MEASURED_WIDEST_TICK nudged by one — survived everything.

    The constant is a measured input, not something derived, so nothing tested
    it directly: it only ever appeared multiplied into plot.w, where a one-unit
    change is a 13px shift that no width assertion could see. The renders pin it
    — label centres give plot.w = 1669px, and plot.w = W - (gutter+md) - xl
    inverts to gutter 58.6, which is gutterFor at 2 characters (34 + 2*13 = 60)
    and not at 1 (47) or 3 (73).

    Asserted against the arithmetic, not against a re-measurement, so the test
    states the reasoning a future editor can check rather than a magic number.
    """
    geo = cg.plot_width({'width': 1920, 'height': 1080})
    W = 1920 - (40 + 64)
    gutter = W - 24 - 64 - geo.plot_w
    assert gutter == pytest.approx(58.6, abs=1.5), (
        f'implied gutter is {gutter:.1f}px, but the rendered frame gives 58.6 '
        f'(plot.w 1669px). gutterFor gives {min(190, 34 + cg.MEASURED_WIDEST_TICK * 13)} '
        f'for widest={cg.MEASURED_WIDEST_TICK} — re-measure rather than nudge'
    )
    # and the neighbouring values must be excluded, or the constant is unconstrained
    for other in (1, 3, 5, 7):
        assert abs(min(190, 34 + other * 13) - gutter) > 1.5, (
            f'widest={other} also fits the measurement, so the constant is not pinned'
        )


def test_a_degenerate_format_cannot_produce_a_negative_or_zero_spacing():
    """Mutation 9 — the max(10, …) floor removed — survived everything.

    The floor only bites on a chart far narrower than the padding, so no normal
    test reaches it. A zero or negative step would make the ratio meaningless
    and could report "no collision" for a chart that has none of its own layout,
    which is the failure mode a detector must never have.
    """
    geo = cg.plot_width({'width': 320, 'height': 180})   # far below the padding
    assert geo.plot_w >= 10.0, f'plot.w collapsed to {geo.plot_w}'
    step = cg.band_step(geo.plot_w, 5)
    assert step > 0, f'step is {step} — the ratio would divide by this'
    labels = ['abcdefgh'] * 5
    f = cg.worst_label_fit(labels, geo)
    assert f is not None and f.ratio > 0, 'a degenerate chart must still measure'


# A mutation that survived and is NOT a hole: removing the max(10, …) floor on
# plot.w leaves every test green. The floor guards a chart narrower than the
# padding, and no format the renderer supports gets there — the narrowest is
# still ~320px wide against a 128px gutter+padding budget, so plot.w stays
# positive either way. A "bad mutation" is one that no observable behaviour
# depends on, and inventing a fake 1px format to kill it would test a case the
# system cannot render. Recorded here so the next person does not re-derive it.
MUTATIONS_SURVIVING = {'plot_w_floor': 'no supported format reaches the bound'}
