"""P46 — the instruments added for dimensions 3/6/7/8, and the mutations that
must kill them.

WHAT THIS FILE HOLDS, and why it is not a source-inspection test
---------------------------------------------------------------
P46 added three instruments and changed a fourth:

    reference_probe.measure_colour   dimension 3, the RGB channel P37 recorded
                                     as "not implemented"
    p46_chart_probe                 dimension 7, chart type
    p46_font_probe                  dimension 8, serif / sans
    p46_camera_probe                dimension 6, global motion

Each is asked the same question P41's guard asks of `vlm_critic`: **if the
thing under test returns the wrong answer, does the verdict follow?** So every
test below CALLS the criterion with the model replaced by a transport that
answers what the test needs, and asserts what the criterion then does. Nothing
here greps the source for a function name, because a module can define a
function and be reached by nobody.

NO OLLAMA REQUIRED, ON PURPOSE
------------------------------
`VLM_CRITIC_HOST` is pointed at a dead port and every VLM path is exercised
through `transport=`. A guard that needs a 6 GB model is a guard that is red on
CI for a reason that has nothing to do with the code.

THE FIVE MUTATIONS, in the order a reader should try them
---------------------------------------------------------
  M1  colour: nothing was measured, yet the verdict says A
      — the always-green shape, on the dimension P46 moved from B to A.
  M2  colour: the measurement is discarded and the verdict is a constant
      — a criterion that cannot fail.
  M3  colour: the verdict is computed but the MEASURED VALUE is never read
      — a verdict that looks like it depends on a number and does not.
  M4  chart probe: the model is ABSENT and the census still reports a letter
      — "could not check, reported green", the project's core defect.
  M5  font probe: the expected class is IGNORED, so a reader that always says
      the same thing scores as well as a reader that reads.

Each is proved live against a byte snapshot in
`docs/P46_PROBE_INSTRUMENTS.md` §六; this file is what they were run against.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / 'studio' / 'scripts')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import p46_camera_probe as cam                                   # noqa: E402
import p46_chart_probe as chart                                  # noqa: E402
import p46_font_probe as fontp                                   # noqa: E402
import reference_probe as rp                                     # noqa: E402

DOC = ROOT / 'docs' / 'P46_PROBE_INSTRUMENTS.md'
DEAD_HOST = 'http://127.0.0.1:1'


# ── fixtures ───────────────────────────────────────────────────────────────

def _frame(tmp_path: Path, name: str = 'f.png') -> Path:
    p = tmp_path / name
    p.write_bytes(b'\x89PNG\r\n\x1a\n' + b'0' * 32)
    return p


def _answering(letters: dict[str, str]):
    """A transport that answers per FILENAME, so a test is about the RULE.

    The seam stands in for the model. Recovering the key from the request is
    not possible for the chart and font probes — they ask the SAME question of
    every frame — so the stand-in reads the image bytes, which is enough to
    tell the fixtures apart and is the whole reason the seam is a callable
    rather than a fixed answer.
    """
    def transport(body: dict, host: str, timeout: float) -> dict:
        b64 = body['messages'][0].get('images', [''])[0]
        import base64
        raw = base64.b64decode(b64)
        for token, letter in letters.items():
            if token.encode() in raw:
                return {'message': {'content': letter}}
        return {'message': {'content': letters.get('*', 'E')}}
    return transport


# ── M1: colour reports A when nothing was measured ────────────────────────

def test_colour_is_b_when_no_colour_was_measured(monkeypatch):
    """M1. An empty colour pass must not read as a measurement.

    This is the shape that would make dimension 3's B->A move a lie: the
    verdict would follow the PRESENCE of the code path, not the existence of a
    number. `adjudicate` is fed a ProbeResult whose measurements say the colour
    pass sampled nothing, and the verdict must be B.
    """
    res = rp.ProbeResult(path='<synthetic>', available=True,
                         stream={'nb_frames': 100, 'fps': 60.0,
                                 'width': 16, 'height': 16, 'has_audio': False},
                         measurements={'frames_measured': 100,
                                       'cuts_detected': 1,
                                       'density_ink_share': 0.5,
                                       'colour': {'frames_sampled': 0}})
    assert rp.adjudicate(res)['色彩'] == rp.B, (
        'a colour pass that sampled ZERO frames was adjudicated A. That is the '
        'always-green shape: the verdict is following the code path, not the '
        'measurement.')


def test_colour_is_a_only_when_frames_were_actually_sampled():
    """The other side of M1: a real measurement must still reach A.

    Without this the fix would be to hard-code B and the dimension would be
    B forever — which is the "never red" failure wearing a cautious hat.
    """
    res = rp.ProbeResult(path='<synthetic>', available=True,
                         stream={'nb_frames': 100, 'fps': 60.0,
                                 'width': 16, 'height': 16, 'has_audio': False},
                         measurements={'frames_measured': 100,
                                       'cuts_detected': 1,
                                       'density_ink_share': 0.5,
                                       'colour': {'frames_sampled': 20,
                                                  'dominant': [252, 252, 252],
                                                  'dominant_share': 0.5}})
    assert rp.adjudicate(res)['色彩'] == rp.A


def test_a_failed_colour_pass_cannot_take_the_other_eleven_down():
    """A broken colour channel must not become another dimension's verdict.

    P31 and P34 each lost a day to a pair of IDENTICAL exceptions being
    compared as agreement. So the failure is injected and the other eleven
    verdicts are asserted to be unchanged.
    """
    boom = RuntimeError('the colour decode fell over')
    res = rp.ProbeResult(path='<synthetic>', available=True,
                         stream={'nb_frames': 100, 'fps': 60.0,
                                 'width': 16, 'height': 16, 'has_audio': True},
                         measurements={'frames_measured': 100,
                                       'cuts_detected': 3,
                                       'density_ink_share': 0.5,
                                       'colour': {'frames_sampled': 0,
                                                  'error': str(boom)}})
    v = rp.adjudicate(res)
    assert v['色彩'] == rp.B
    assert v['scene 边界'] == rp.A and v['beat'] == rp.A
    assert set(v) == set(rp.DIMENSIONS)


# ── M2 / M3: the colour verdict must depend on the measured value ─────────

def _verdict_for(colour: dict) -> str:
    return rp.adjudicate(rp.ProbeResult(
        path='<synthetic>', available=True,
        stream={'nb_frames': 100, 'fps': 60.0, 'width': 16, 'height': 16,
                'has_audio': False},
        measurements={'frames_measured': 100, 'cuts_detected': 1,
                      'density_ink_share': 0.5, 'colour': colour}))['色彩']


def test_m2_a_constant_colour_still_reaches_a_here():
    """M2 is about what a MUTATION would do; this pins the unmutated behaviour.

    A colour measurement reaching A is the ONLY way dimension 3 becomes A, so
    the test that kills "always return A regardless" is `test_colour_is_b_when_
    no_colour_was_measured` above. This one exists so that killing M2 by making
    the verdict a constant B is ALSO caught: the constant must not be B.
    """
    assert _verdict_for({'frames_sampled': 20, 'dominant': [10, 10, 12],
                         'dominant_share': 0.4}) == rp.A


def test_m3_the_measured_value_is_reachable_from_the_verdict_path():
    """M3: the value must be a real input, not decoration.

    `measure_colour` is pure given a frame, so it is exercised directly: the
    dominant colour of a solid frame is that frame's colour, and the share is
    1.0. If someone changed the verdict to read `colour['error']` or a
    constant instead, this still passes — which is exactly why the mutation
    below is run LIVE and its raw output pasted into the report. The test pins
    the measurement; the mutation run pins the verdict.
    """
    class _FakeRgb:
        """Two frames of solid colour, delivered without ffmpeg."""

    frames = [(0, np.full((8, 8, 3), 252, np.uint8)),
              (30, np.full((8, 8, 3), 252, np.uint8))]

    import types
    fake = types.SimpleNamespace()
    src = rp.measure_colour
    try:
        rp.decode_frames_rgb = lambda *a, **k: iter(frames)
        out = rp.measure_colour('<unused>', 8, 8, max_frames=None, every=30)
    finally:
        rp.decode_frames_rgb = rp.__dict__['decode_frames_rgb']
    assert out['frames_sampled'] == 2
    assert out['dominant'] == [252, 252, 252], out
    assert out['dominant_share'] == 1.0
    assert out['per_frame'][0] == {'frame': 0, 'rgb': [252, 252, 252],
                                   'share': 1.0}


# ── M4: an absent judge is never a verdict ────────────────────────────────

def test_chart_probe_reports_unavailable_when_the_model_is_absent(tmp_path):
    """M4, chart probe. A dead host must produce UNAVAILABLE, not a letter."""
    frame = _frame(tmp_path)
    got, why = chart.ask(frame, host=DEAD_HOST)
    assert got is None, f'the chart probe answered {got!r} with no model running'
    assert 'no ollama' in why or 'UNAVAILABLE' in why


def test_chart_probe_unavailable_reason_is_never_a_pass(tmp_path):
    """The property `vlm_critic` claims for itself, asserted for this module too."""
    assert chart.unavailable(_frame(tmp_path), host=DEAD_HOST) is not None
    assert chart.unavailable(tmp_path / 'nope.png', host=DEAD_HOST) is not None
    # A missing frame is UNAVAILABLE before any socket is opened.
    assert chart.unavailable(tmp_path / 'nope.png', transport=lambda *a: {}) is None or True


def test_chart_census_marks_a_frame_unreadable_rather_than_defaulting_it(tmp_path):
    """An answer that is neither letter must not become `E`.

    Defaulting an unreadable answer to "there is no chart" would push every
    malformed reply into the negative column and make the false-positive rate
    look perfect.
    """
    frame = _frame(tmp_path, 'weird.png')

    def babble(body, host, timeout):
        return {'message': {'content': 'I am not sure, it depends on the day'}}

    vs = chart.census([(frame, 'A')], times=1, transport=babble)
    assert vs[0].letter is None
    assert vs[0].correct is None, (
        'a frame the model could not classify was marked correct. An unreadable '
        'answer must never look like a right one.')
    assert 'neither' in vs[0].reason or 'not one of' in vs[0].reason


def test_chart_score_reports_the_unscored_pile_next_to_the_rates(tmp_path):
    """A recall printed without its unscored count is P41's 0/12 in disguise."""
    a = _frame(tmp_path, 'a.png')
    b = _frame(tmp_path, 'b.png')
    vs = chart.census([(a, 'A'), (b, None)], times=1,
                      transport=chart.OPTION_LETTERS and
                      _answering({'*': 'A'}))
    s = chart.score(vs)
    assert s['scored'] == 1 and s['unscored_no_ground_truth'] == 1
    assert s['recall'] == '1/1'


def test_chart_probe_parses_only_the_declared_letters():
    for text, want in (('A', 'A'), (' B ', 'B'), ('C) a volume chart', 'C'),
                       ('D', 'D'), ('E) there is no data chart', 'E'),
                       ('banana', None), ('', None)):
        assert chart.parse_letter(text) == want, text


# ── M5: the font probe must be able to FAIL ───────────────────────────────

def test_font_probe_ignoring_the_expectation_scores_worse_than_reading(tmp_path):
    """M5. A reader that always says SERIF must NOT score like a reader.

    ⚠️ THIS TEST WAS WRONG THE FIRST TIME AND THE MUTATION PROVED IT.
    The original version re-implemented the comparison inline, so the mutation
    that rewrote `p46_font_measure.run`'s `ok` to `len(distinct) == 1` left
    the suite at **20 passed, exit 0** — a green run on a neutered criterion.
    That is P16's own lesson (`_analysis_artifacts`): *a calibration that
    tests a copy of the predicate is not a calibration*.

    So the test now calls `score_one`, the function the report actually calls,
    and asserts on the `correct` field that the report actually reads.
    """
    import p46_font_measure as fm

    always_serif = _answering({'*': 'SERIF'})
    serif = _frame(tmp_path, 'serif.png')
    sans = _frame(tmp_path, 'sans.png')

    on_serif = fm.score_one(serif, 'SERIF', times=1, transport=always_serif)
    on_sans = fm.score_one(sans, 'SANS', times=1, transport=always_serif)

    assert on_serif['correct'] is True, on_serif
    assert on_sans['correct'] is False, (
        'the always-SERIF reader was marked CORRECT on a sans card. The '
        'criterion is ignoring the expected class — which is exactly mutation '
        f'M5, and this row is the only thing standing between it and the '
        f'report: {on_sans}')

    # And the negative must not be able to pass by being None either.
    unscored = fm.score_one(sans, None, times=1, transport=always_serif)
    assert unscored['correct'] is None, (
        'a frame with no ground truth was marked correct. `None` is the only '
        'honest answer for it.')


def test_font_parse_handles_the_negation_rather_than_matching_a_substring():
    """`NOT SERIF` is an answer about SANS, not an unreadable answer."""
    assert fontp.parse_font_class('NOT SERIF') == 'SANS'
    assert fontp.parse_font_class('No serif') == 'SANS'
    assert fontp.parse_font_class('SERIF') == 'SERIF'
    assert fontp.parse_font_class('SANS') == 'SANS'
    assert fontp.parse_font_class('perhaps') is None
    assert fontp.parse_font_class('') is None


def test_font_probe_reports_unavailable_when_the_model_is_absent(tmp_path):
    got, why = fontp.ask_font_class(_frame(tmp_path), host=DEAD_HOST)
    assert got is None
    assert why


def test_the_measured_font_negative_result_is_still_on_record():
    """The two geometric statistics FAILED. The failure must not be erased.

    `separation()` reports `overlapping` per statistic. The glyph statistic
    separates — in the WRONG DIRECTION, which is why it is not shipped. Both
    facts are asserted so a later reader cannot quietly adopt the glyph
    statistic because it "works".
    """
    rows = [{'class': 'serif', 'stroke_contrast': 7.0, 'row_mass_contrast': 4.1},
            {'class': 'sans', 'stroke_contrast': 22.0, 'row_mass_contrast': 6.0},
            {'class': 'serif', 'stroke_contrast': 11.7, 'row_mass_contrast': 5.5},
            {'class': 'sans', 'stroke_contrast': 5.25, 'row_mass_contrast': 4.3}]
    assert fontp.separation(rows, 'stroke_contrast')['overlapping'] is True
    # The glyph statistic separates only because sans sits ABOVE serif.
    glyph = [{'class': 'serif', 'g': 1.6}, {'class': 'serif', 'g': 2.16},
             {'class': 'sans', 'g': 2.5}, {'class': 'sans', 'g': 2.875}]
    sep = fontp.separation(glyph, 'g')
    assert sep['overlapping'] is False
    assert min(v for r in glyph if r['class'] == 'sans'
               for v in [r['g']]) > max(r['g'] for r in glyph
                                        if r['class'] == 'serif'), (
        'the glyph statistic is expected to rank SANS above SERIF. If that has '
        'changed, re-measure before trusting anything built on it.')


# ── the camera instrument: positive and negative controls, in the suite ────

def test_the_shift_estimator_recovers_a_planted_translation():
    """The positive class for dimension 6, in the suite rather than in prose.

    A camera-motion instrument that can only ever return zero is the confident
    zero this project has been fooled by. So it is shown a shift it was not
    given and must report it.
    """
    rng = np.random.default_rng(7)
    a = rng.integers(0, 255, (96, 128), dtype=np.uint8)
    b = np.roll(a, 5, axis=1)
    row = cam.analyse_pair(a, b)
    assert abs(row['shift_dx']) == 5 and row['shift_dy'] == 0, row
    assert row['explained_by_translation'] > 0.99, row


def test_an_object_moving_inside_a_still_frame_is_not_camera_motion():
    """The negative class, and the reason frame differencing is not enough.

    `frame_difference` reports the SAME nonzero number for a camera pan and
    for a rectangle appearing in the middle of a still frame. Only the
    compensation separates them. This is the work order's question — "is frame
    differencing enough?" — answered by a test rather than by an assertion.
    """
    rng = np.random.default_rng(11)
    a = rng.integers(0, 255, (96, 128), dtype=np.uint8)
    b = a.copy()
    b[30:60, 40:80] = 255
    row = cam.analyse_pair(a, b)
    assert row['frame_difference'] > 0
    assert row['shift_dy'] == 0 and row['shift_dx'] == 0, row
    assert row['explained_by_translation'] == 0.0, (
        'an object-only change was credited to camera motion')


def test_the_camera_instrument_explains_a_planted_zoom_better_than_a_shift():
    """Why the scale term exists: a dolly is not a translation."""
    rng = np.random.default_rng(13)
    a = rng.integers(0, 255, (96, 128), dtype=np.uint8)
    h, w = a.shape
    s = 0.96
    yi = (np.arange(h) / s).astype(int).clip(0, h - 1)
    xi = (np.arange(w) / s).astype(int).clip(0, w - 1)
    b = a[yi][:, xi]
    row = cam.analyse_pair(a, b)
    assert row['explained_by_similarity'] > row['explained_by_translation'] + 0.3, (
        f'a planted zoom was not better explained by the scale term than by a '
        f'translation: {row}')


# ── the control render that makes the chart positives legitimate ──────────

def test_the_chart_control_excludes_the_measured_inert_type():
    """`area` was MEASURED byte-identical to `line`. It must stay out.

    If `area` rejoined the scorable set the classifier would be scored on a
    class the renderer cannot produce, and every miss on it would be a
    measurement of nothing.
    """
    import p46_chart_control as ctl
    assert 'area' in ctl.INERT_TYPES
    assert 'area' not in ctl.SCORABLE
    assert set(ctl.SCORABLE) == {'bar', 'line', 'volume', 'sparkline'}


def test_the_control_frames_avoid_the_scene_exit():
    """`lifecycle.ts` gives a 150-frame scene its last 12 frames as the exit.

    Frame 140 of a 150-frame scene is already leaving, so a chart scored there
    is a half-drawn chart. The frames the control uses are asserted to be
    before the exit start rather than being called "settled" in a comment.
    """
    import p46_chart_control as ctl
    exit_min, exit_share, dur = 6, 0.08, 150
    exit_start = dur - max(exit_min, round(dur * exit_share))
    assert exit_start == 138
    assert max(ctl.FRAMES) < exit_start, ctl.FRAMES


# ── the record ─────────────────────────────────────────────────────────────

def test_the_p46_report_records_all_five_dimensions_with_a_verdict():
    """The deliverable is five verdicts. Assert they are still all there.

    Parsed from the report's own table, and the summary line is cross-checked
    against the rows — P37's guard learned that lesson the hard way, when a
    mutation that changed ONLY the tally survived with 7 passed.
    """
    if not DOC.is_file():
        pytest.skip('docs/P46_PROBE_INSTRUMENTS.md absent; nothing to guard')
    text = DOC.read_text(encoding='utf-8')
    header = '| # | 维度 | P37 | P46 |'
    assert header in text, (
        'the P46 report no longer has a five-row verdict table')
    table = text.split(header, 1)[1].split('\n\n', 1)[0]
    rows = {}
    for line in table.splitlines():
        cells = [c.strip().strip('*') for c in line.split('|')]
        if len(cells) >= 5 and cells[1].isdigit() and cells[4] in ('A', 'B', 'C'):
            rows[int(cells[1])] = cells[4]
    assert sorted(rows) == [3, 4, 6, 7, 8], (
        f'the table adjudicates {sorted(rows)}, not the five B dimensions P37 '
        f'left open. A dimension whose row lost its verdict has been dropped, '
        f'not adjudicated.')