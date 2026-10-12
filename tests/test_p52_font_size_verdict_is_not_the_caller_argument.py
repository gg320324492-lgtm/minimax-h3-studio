"""P52 — `rule_font_size`'s verdict was the caller's argument, not the frame.

WHAT WAS WRONG
--------------
`rule_font_size(a, declared_px, scale)` measured ink bands off the pixels and
then decided on `declared_px < MIN_TYPE_PX`. One frame, two invocations:

    --declared-px 20  ->  PASS
    --declared-px 5   ->  FAIL

with every pixel identical. So the `--frame` gate could be moved by changing a
command-line number, which is P22's shape one rule over — there, a constant
reported as a per-frame measurement; here, an ARGUMENT reported as one.

WHAT IS ASSERTED HERE, AND BY WHAT MEANS
----------------------------------------
Every claim is reached by CALLING `vqa.main(argv)` or `vqa.rule_font_size(...)`
and reading the verdict, the exit code and the report. Nothing greps the source
and nothing asserts that a name merely exists. The fixture frames are built
here, in the test, rather than read from the gitignored corpus — a guard that
needs `out/p13_probe` passes on the machine that made it and fails on a clone.

The question this file exists to answer is the one the defect poses:

    "IF THE CALLER CHANGED --declared-px AND NOTHING ELSE, WOULD THE VERDICT MOVE?"

and the second one, which is the trap the obvious fix falls into:

    "IF ONE 2px ACCENT RULE APPEARED ON AN OTHERWISE IDENTICAL FRAME,
     WOULD THE VERDICT MOVE?"

The second matters because the tempting repair is to swap `declared_px` for the
measured `median`. That does not close the hijack, it relocates it onto the
measurement — and on a real corpus frame it is one pixel wide.
`out/p13_probe/full_a/0002.png` measures bands `[6, 201]`, median 103.5px; add
one 2px accent rule and the bands are `[2, 6, 201]`, median 6.0px, which flips
`median < 12` from PASS to FAIL. `_frame_plus_accent_rule` below rebuilds that
exact geometry, so the mutation is killed on a fact and not on a preference.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / 'studio' / 'scripts')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import visual_qa as vqa  # noqa: E402


# ── fixtures ────────────────────────────────────────────────────────────────
#
# Sized to clear `backdrop_model`'s own trust check (content clear of the EDGE
# columns and the RING rows) and of `text_band_heights`' 25%-of-width cut, so
# the rule produces bands instead of refusing. Every test that reads a band
# first asserts the band it expected — a fixture that quietly stopped
# producing one would make the rest of the file pass on nothing.

def _frame(rects, w: int = 1920, h: int = 1080, bg: int = 12, ink: int = 245):
    f = np.full((h, w, 3), bg, dtype=int)
    for y0, y1, x0, x1 in rects:
        f[y0:y1, x0:x1] = ink
    return f


#: bands [6, 201] — the measured `full_a/0002.png` geometry.
_MIXED = ((100, 301, 800, 1001), (500, 506, 200, 301))
#: the same frame with ONE 2px accent rule added: bands [2, 6, 201].
_MIXED_PLUS_RULE = _MIXED + ((700, 702, 400, 451),)
#: one band of 201px — a frame carrying nothing small.
_BIG_TYPE = ((100, 301, 800, 1001),)
#: one band of 7px — a frame carrying nothing large.
_TINY_TYPE = ((100, 107, 800, 1001),)


def _bands(a) -> list[int]:
    m, trusted, _ = vqa.model_mask(a)
    assert trusted, 'fixture tripped the backdrop trust check; it would prove nothing'
    return sorted(int(b) for b in vqa.text_band_heights(a, m))


def _write(tmp_path: Path, name: str, a) -> Path:
    from PIL import Image
    p = tmp_path / name
    Image.fromarray(a.astype('uint8')).save(p)
    return p


def _font(findings_json) -> list[dict]:
    return [f for f in findings_json if f['rule'] == 'font_size']


def _run(argv, capsys):
    code = vqa.main([str(a) for a in argv])
    out = capsys.readouterr().out
    return code, json.loads(out)


# ── 1. the caller cannot move the verdict ───────────────────────────────────

def test_the_verdict_is_identical_on_one_frame_at_every_declared_size(tmp_path, capsys):
    """THE headline guard, and the defect in one assertion.

    The same PNG is run through the real CLI five times, changing only
    `--declared-px`. Two frames' worth of difference between a passing and a
    failing gate used to live entirely in that argument.
    """
    frame = _write(tmp_path, 'mixed.png', _frame(_MIXED))
    assert _bands(vqa.load(frame)) == [6, 201], 'fixture changed; it is measuring nothing now'

    readings, codes = [], []
    for declared in ('5', '11.25', '12', '20', '1000'):
        code, findings = _run(['--frame', frame, '--declared-px', declared, '--json'], capsys)
        codes.append(code)
        hit = _font(findings)
        assert len(hit) == 1, f'expected one font_size finding, got {len(hit)}: {findings}'
        readings.append(hit[0])

    verdicts = {r['verdict'] for r in readings}
    assert len(verdicts) == 1, (
        'the verdict followed `--declared-px`. It is '
        f'{sorted(verdicts)} across declared sizes 5, 11.25, 12, 20 and 1000 on '
        'ONE frame with no pixel changed. That is the defect: the caller, not '
        'the picture, is choosing what the gate says.')
    assert len(set(codes)) == 1, (
        f'the exit code followed `--declared-px`: {codes}. The gate is supposed '
        'to be about the frame.')


def test_the_declared_size_moves_the_ratio_and_nothing_else(tmp_path):
    """`declared_px` is not garbage and was not deleted.

    It carries the ratio — what the graph declared against what the picture
    shows — and that reading still moves when the declaration moves. What it no
    longer does is decide anything.
    """
    a = _frame(_MIXED)
    big = vqa.rule_font_size(a, declared_px=20.0)
    small = vqa.rule_font_size(a, declared_px=5.0)

    assert big.extra['measured_over_declared'] != small.extra['measured_over_declared'], (
        'the ratio stopped moving with the declaration. That is the measurement '
        'being lost rather than un-gated, which is a different defect.')
    assert big.extra['measured_over_declared'] == pytest.approx(103.5 / 20.0)
    assert small.extra['measured_over_declared'] == pytest.approx(103.5 / 5.0)
    assert big.extra['band_px'] == small.extra['band_px'] == [6, 201], (
        'the same frame measured different bands on the two calls')
    assert big.verdict == small.verdict


# ── 2. the finding has no verdict for anything to hijack ────────────────────

def test_the_finding_carries_no_number_and_claims_no_trust(tmp_path):
    """An UNAVAILABLE finding with a `value` on it is inventing a threshold.

    This is the convention `rule_contrast_frame` established and P22's guard
    pinned: a number on a finding whose instrument does not exist reads as a
    measurement and is consumed as one.
    """
    f = vqa.rule_font_size(_frame(_MIXED), declared_px=20.0)
    assert f.verdict == vqa.UNAVAILABLE, f.verdict
    assert f.value is None, (
        f'UNAVAILABLE must carry no number; {f.value} would be a threshold '
        'invented rather than measured')
    assert not f.trusted, (
        'a finding with no instrument must not claim a trusted one — that is '
        'how an absent instrument gets read as a clean bill of health')
    assert f.extra['bands'] == 2
    assert f.extra['measured_median_px'] == pytest.approx(103.5)


def test_it_is_unavailable_and_not_unverifiable(tmp_path, capsys):
    """UNVERIFIABLE exits 1. Shipping that would be P22's mistake repeated.

    P22 moved `contrast` off the frame path rather than leaving it red; the
    parallel mistake here would be to answer "I have no instrument" with the
    word that exits non-zero, which makes `--frame` permanently non-zero for a
    reason no frame can cause. So this asserts the exit code, not the spelling.
    """
    frame = _write(tmp_path, 'mixed.png', _frame(_MIXED))
    code, findings = _run(
        ['--frame', frame, '--declared-px', '20',
         '--props', _props(tmp_path), '--json'], capsys)
    assert code == 0, (
        f'--frame exited {code} on a frame with nothing wrong with it. '
        'font_size has no verdict to contribute and every other rule on this '
        'path passes, so this must not be a way of re-adding a permanent red.')
    assert _font(findings)[0]['verdict'] == vqa.UNAVAILABLE


def _props(tmp_path: Path) -> Path:
    p = tmp_path / 'props.json'
    p.write_text(json.dumps({'format': {'width': 1920, 'height': 1080, 'fps': 60},
                             'scenes': []}), encoding='utf-8')
    return p


# ── 3. the obvious fix does not survive: measurement hijack ─────────────────

def test_one_more_2px_accent_rule_does_not_move_the_verdict(tmp_path):
    """THE trap, rebuilt from a measured case.

    `out/p13_probe/full_a/0002.png` measures `[6, 201]` — median 103.5px. Add
    one 2px accent rule and it measures `[2, 6, 201]` — median 6.0px. Any
    criterion of the form `median < MIN_TYPE_PX` therefore goes PASS -> FAIL on
    a one-pixel design change, on a real frame, and would make 58 of 298
    corpus frames hinge on whether they happen to carry a hairline.

    The verdict must not move. The MEASUREMENT must: the assertion below is
    what stops this test from passing on a rule that had simply stopped looking.
    """
    before = vqa.rule_font_size(_frame(_MIXED), declared_px=20.0)
    after = vqa.rule_font_size(_frame(_MIXED_PLUS_RULE), declared_px=20.0)

    assert before.extra['band_px'] == [6, 201]
    assert after.extra['band_px'] == [2, 6, 201], 'fixture changed; it is measuring nothing now'
    assert before.extra['measured_median_px'] != after.extra['measured_median_px'], (
        'the two frames measured the same median, so the fixtures are not the '
        'two frames this test claims and it would prove nothing')
    assert before.verdict == after.verdict, (
        f'a single 2px accent rule moved the verdict: {before.verdict} -> '
        f'{after.verdict}. The caller-argument hijack was replaced by a '
        'measurement hijack, which is the same defect wearing a different '
        'name — and here it is one pixel wide.')


def test_frames_whose_type_differs_do_not_produce_a_verdict(tmp_path):
    """The positive/negative pair, and the honest answer that they do not exist.

    A frame carrying one 7px band and a frame carrying one 201px band are about
    as opposite as this instrument can make them. A bar applied to the bands
    separates them, which is exactly why it is wrong: the 201px band is a day
    tile on `f760_a.png`, not type, and the 7px band may be an accent rule
    rather than a glyph. There is no reading of `text_band_heights` that tells
    the two apart without glyph recognition.
    """
    big = vqa.rule_font_size(_frame(_BIG_TYPE), declared_px=20.0)
    tiny = vqa.rule_font_size(_frame(_TINY_TYPE), declared_px=20.0)
    assert big.extra['band_px'] == [201] and tiny.extra['band_px'] == [7], (
        'the fixtures changed; this test would be comparing nothing')
    assert big.verdict == tiny.verdict, (
        f'the bands alone decided the verdict ({big.verdict} vs {tiny.verdict}). '
        'If a criterion here can tell a 7px band from a 201px one, it is '
        'applying the readability bar to marks, not to type.')


# ── 4. the rule still reads the frame ───────────────────────────────────────

def test_the_rule_still_measures_the_pixels_it_is_handed():
    """Without this, "no verdict" would be indistinguishable from "not looking".

    The whole claim of this change is that the measurement survives and only the
    gate went away. Two frames that differ must report different numbers.
    """
    a = vqa.rule_font_size(_frame(_BIG_TYPE), declared_px=20.0)
    b = vqa.rule_font_size(_frame(_TINY_TYPE), declared_px=20.0)
    assert a.extra['band_px'] != b.extra['band_px']
    assert a.extra['measured_median_px'] != b.extra['measured_median_px']
    assert 'median 201px' in a.detail and 'median 7px' in b.detail, (
        'the reading does not quote what it measured, so a machine consumer has '
        f'only the verdict to go on — and there is none: {a.detail} / {b.detail}')


def test_the_reading_says_why_it_cannot_decide():
    """A refusal that does not say why trains the next reader to route around it.

    Read off the returned Finding, not out of the source: the work order for
    this rule forbids a guard that asserts a string appears in a file.
    """
    f = vqa.rule_font_size(_frame(_MIXED), declared_px=20.0)
    assert f.detail, 'the refusal carries no reason'
    assert 'bands mix type with marks' in f.detail, f.detail
    assert '1..6' in f.detail, f.detail
    assert 'glyph recognition' in f.detail, f.detail


def test_every_declared_size_reaches_the_report_with_its_own_ratio(tmp_path, capsys):
    """The JSON a machine consumer reads carries the same separation.

    P22's guard insisted on this because a consumer that sees a per-frame FAIL
    it cannot act on is worse than no report at all. Here: one finding, always
    the same verdict, and the declaration present as DATA.
    """
    frame = _write(tmp_path, 'mixed.png', _frame(_MIXED))
    code, findings = _run(['--frame', frame, '--declared-px', '5', '--json'], capsys)
    hit = _font(findings)
    assert len(hit) == 1
    assert hit[0]['extra']['declared_px'] == 5.0
    assert hit[0]['extra']['measured_over_declared'] == pytest.approx(103.5 / 5.0)
    assert hit[0]['verdict'] == vqa.UNAVAILABLE
    assert code == 1, (
        'the frame is 1920x1080 but no --props was supplied, so `aspect` is '
        'UNVERIFIABLE and the exit code is legitimately 1; what must not '
        'happen is a font_size FAIL contributing to it')


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))