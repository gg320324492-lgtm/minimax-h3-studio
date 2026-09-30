"""P7.0 guard: a declared chart field must have a reader, and must move pixels.

P7 is the phase most likely to reproduce the failure this project has now hit
three times — a field that is declared, looks like a capability, and changes
nothing. The demo graph carried fifteen style_bible keys and one worked. The
reviewer's instruction for P7 was to answer "who reads this field?" BEFORE
writing the schema, and to hold every declaration to A/B pixel evidence.

The expensive half of that — two real renders and a pixel diff — is
`studio/scripts/ab_field.py`, run deliberately rather than on every suite run.
What is pinned here is the cheap half, on synthetic images, so the suite stays
portable and fast:

  - an inert field is DETECTED, not reported as a tidy zero
  - a live field is localised, so a change that moves the whole frame is
    distinguishable from one that moves the thing the field names
  - the registry refuses an option whose registered reader never mentions it

Measured, not asserted: the harness was run against a field known to be inert
(`style_bible.cameraLanguage.perspective` on the demo graph, where every scene
sets its own perspective) and reported 0 changed pixels, "INERT", exit 1. Run
against a live one (`typography.numericDisplay.tracking`) it reported 1.59% of
pixels, confined to the hero figure.

Run:
  python -m pytest tests/test_chart_fields.py -q
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'studio' / 'scripts' / 'ab_field.py'


def _load():
    spec = importlib.util.spec_from_file_location('ab_field', SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ab = _load()


def _frame(tmp_path: Path, name: str, frame: int, changed_box=None) -> Path:
    """A near-black frame named the way still.mjs names it."""
    img = np.zeros((1080, 1920, 3), dtype=np.uint8) + 10
    if changed_box:
        x0, y0, x1, y1 = changed_box
        img[y0:y1, x0:x1, :] = 240
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(d / ab.frame_name(frame))
    return d


def _identical(tmp_path: Path, name: str, frame: int, changed_box=None) -> Path:
    return _frame(tmp_path, name, frame, changed_box)


def test_identical_frames_report_nothing_changed(tmp_path):
    a = _frame(tmp_path, 'a', 400)
    b = _frame(tmp_path, 'b', 400)
    res = ab.diff_dir(a, b, 400)
    assert res['changed'] == 0
    assert res['box'] is None
    assert res['pct'] == 0.0
    assert res['frame'] == 400


def test_a_stale_frame_in_the_directory_cannot_be_compared(tmp_path):
    """The defect this whole guard nearly shipped with.

    `diff_dir` used to take `next(dir.glob('*.png'))` from each side. The output
    directory was never emptied, so a frame left by an earlier run got compared
    against this run's frame — two different frames of the same film, reported
    as a percentage to two decimals and a bounding box, indistinguishable from a
    real result. Verified: it returned "2.89% changed, box (600,400,899,599)"
    for two IDENTICAL images, having compared frame 200 against frame 400.

    A guard that will return a confident verdict for any field is worse than no
    guard, because it hands inert fields a pass. So the pairing is by exact
    filename, and a missing one is an error naming what IS there.
    """
    a = _frame(tmp_path, 'a', 400)
    a_frame200 = _frame(tmp_path, 'a', 200, changed_box=(600, 400, 900, 600))
    b = _frame(tmp_path, 'b', 400)

    # asking for frame 400 must find frame 400, ignoring the stale one
    res = ab.diff_dir(a, b, 400)
    assert res['changed'] == 0, 'the stale frame 200 was compared instead of frame 400'

    # asking for a frame that is not there must REFUSE, not compare something else
    with pytest.raises(FileNotFoundError) as exc:
        ab.diff_dir(a, b, 500)
    assert 'f00500.png' in str(exc.value)
    assert 'f00200.png' in str(exc.value), (
        f'the error must name what IS in the directory, so the cause is obvious: {exc.value}'
    )


def test_a_changed_field_is_localised_not_frame_wide(tmp_path):
    """The useful signal is not "something moved" but "what moved".

    A field that repaints the whole frame has almost certainly leaked into
    something global, and the region is how you notice.
    """
    a = _frame(tmp_path, 'a2', 400)
    b = _frame(tmp_path, 'b2', 400, changed_box=(700, 400, 900, 500))
    res = ab.diff_dir(a, b, 400)
    assert res['changed'] == 200 * 100
    assert res['box'] == (700, 400, 899, 499)
    assert 0.0 < res['pct'] < 1.0, 'a localised change must not read as frame-wide'


def test_registry_rejects_an_option_whose_reader_ignores_it():
    """A registry that only checks its own bookkeeping cannot tell an inert
    option from a working one — the check has to look at the reader's source."""
    import types
    fake = types.SimpleNamespace()
    real = ab.ROOT
    ab.FIELD_READERS.clear()
    ab.FIELD_READERS.update({
        # a file that exists and does NOT mention showArea
        'showArea': 'common/projection.ts',
        # a reader path that does not exist at all
        'strokeWidth': 'charts/does-not-exist.tsx',
    })
    try:
        problems = ab.check_registry()
    finally:
        ab.FIELD_READERS.clear()
        ab.ROOT = real
    joined = ' | '.join(problems)
    assert 'showArea' in joined and 'inert' in joined, (
        f'an option whose reader never mentions it must be flagged inert: {problems}'
    )
    assert 'does-not-exist' in joined, f'a missing reader must be flagged: {problems}'


def test_registry_is_not_vacuous_while_p7_1_is_in_flight():
    """An empty registry must be a PROBLEM, not a green run.

    While P7.1 was in flight the check returned early because the chart
    directory did not exist yet, so a guard with nothing registered passed
    silently — the exact vacuous pass this mechanism exists to prevent.
    """
    import types
    ab.FIELD_READERS.clear()
    try:
        problems = ab.check_registry()
    finally:
        ab.FIELD_READERS.clear()
    assert problems, (
        'with an empty registry the guard must report that it has nothing to '
        'check, rather than passing vacuously'
    )
    assert 'empty' in problems[0]


def test_registry_check_does_not_depend_on_the_chart_directory():
    """The registry is the declaration; the directory is a separate fact.

    Coupling them meant that before P7.1 landed, no option was ever checked.
    """
    ab.FIELD_READERS.clear()
    ab.FIELD_READERS['showArea'] = 'common/projection.ts'  # reader exists, ignores it
    try:
        problems = ab.check_registry()
    finally:
        ab.FIELD_READERS.clear()
    assert any('showArea' in p and 'inert' in p for p in problems), (
        f'the registry must be checked even with no chart directory: {problems}'
    )


def test_set_path_builds_missing_intermediate_objects():
    """A/B must be able to probe any depth without the caller hand-building a
    whole document — otherwise nobody runs it on nested fields."""
    doc = {'scenes': [{'id': 's1'}]}
    ab._set_path(doc, 'style_bible.typography.heading.size', 96)
    assert doc['style_bible']['typography']['heading']['size'] == 96
    # existing structure is preserved, not clobbered
    assert doc['scenes'][0]['id'] == 's1'


def test_check_value_parses_literals_and_leaves_plain_strings():
    """The value the caller typed is not the value the graph should hold:
    `--set a=true` has to become a boolean, and `--set a=plain text` has to
    stay a string. Getting this backwards is how a CSS value ends up as the
    literal text "5px"."""
    doc: dict = {}
    value, err = ab.check_value(doc, 'a', 'true')
    assert err is None and value is True
    value, err = ab.check_value(doc, 'b', 'plain text')
    assert err is None and value == 'plain text'
    value, err = ab.check_value(doc, 'c', '[1, 2]')
    assert err is None and value == [1, 2]
    value, err = ab.check_value(doc, 'd', '-0.01em')
    assert err is None and value == '-0.01em', 'a CSS length is not JSON and must stay text'


# ── input validation ─────────────────────────────────────────────────────────
#
# Three bad inputs each produced a well-formed number before the guard refused
# them: `--frames` for `--frame` (silently the default 400), `tracking=5`
# against a field holding "-0.055em" (CSS rejects it, React drops it, the frame
# is byte-identical — so a typo reads as "this field is inert"), and measuring
# numericDisplay on frame 455 when that scene does not show the number. The
# principle from measure_frame.py — refuse rather than answer — extends to the
# inputs, not just the model.

def test_a_type_mismatch_against_the_current_value_is_refused():
    doc = {'style_bible': {'typography': {'numericDisplay': {'tracking': '-0.055em'}}}}
    value, err = ab.check_value(doc, 'style_bible.typography.numericDisplay.tracking', '5')
    assert value == 5
    assert err is not None, 'number into a string field must be refused'
    assert '-0.055em' in err and 'string' in err, 'the error must quote both values'


def test_a_matching_type_is_accepted():
    doc = {'style_bible': {'typography': {'numericDisplay': {'tracking': '-0.055em'}}}}
    value, err = ab.check_value(doc, 'style_bible.typography.numericDisplay.tracking', '-0.01em')
    assert err is None and value == '-0.01em'


def test_a_new_field_is_accepted_without_a_type_check():
    """Adding a field is a legitimate thing to probe; there is nothing to
    compare against, so the result is flagged as NEW rather than refused."""
    doc: dict = {}
    value, err = ab.check_value(doc, 'layout.spreadX', '300')
    assert err is None and value == 300
    assert ab._get_path(doc, 'layout.spreadX') == (False, None)


def test_booleans_and_numbers_are_not_confused():
    """Python's bool is an int; a guard that treats True as 1 would accept a
    type error it is supposed to catch."""
    doc = {'a': True, 'b': 1, 'c': '1'}
    assert ab._type_name(True) == 'bool'
    assert ab._type_name(1) == 'number'
    _, err = ab.check_value(doc, 'a', '1')
    assert err is not None, 'True -> 1 must be refused as a type mismatch'
    _, err = ab.check_value(doc, 'b', 'true')
    assert err is not None
    _, err = ab.check_value(doc, 'c', '1')
    assert err is not None


def test_frame_ink_distinguishes_a_blank_frame_from_a_busy_one(tmp_path):
    """So a zero-change verdict can say whether the frame showed anything.

    'this field does nothing' and 'you measured a frame that does not show the
    subject' are indistinguishable from outside, and the second is the more
    common mistake.
    """
    blank = _frame(tmp_path, 'blank', 10) / ab.frame_name(10)
    busy = _frame(tmp_path, 'busy', 10, changed_box=(600, 400, 1200, 700)) / ab.frame_name(10)
    assert ab.frame_ink(blank) < 0.5
    assert ab.frame_ink(busy) > 5.0


def test_a_misspelled_flag_is_an_error_not_a_default(tmp_path):
    """`--frames` where `--frame` was meant used to fall through to the default
    and describe frame 400 while the caller believed they had asked for 455."""
    import tempfile
    with pytest.raises(SystemExit) as exc:
        ab.main(['--props', str(ROOT / 'pipeline' / 'examples' / 'showcase_demo.json'),
                 '--set', 'style_bible.typography.numericDisplay.tracking=-0.01em',
                 '--frames', '455'])
    assert exc.value.code == 2, 'a misspelled flag must exit 2, not fall through'
