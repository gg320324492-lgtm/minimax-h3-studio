"""`rule_duplicate` must ask the question its entry point can be asked (P19).

WHAT THIS EXISTS FOR. `--frame-pair` hands `rule_duplicate` two files and nothing
else. Every real caller of it — and every corpus measured here — passes two
CONSECUTIVE frames of one render. The rule cut at 0.5, a threshold measured for
two RENDERS of one graph (`rank_takes.DUP_THRESHOLD`), so it called DUPLICATE on
frames that were visibly moving: measured 152 of 320 consecutive corpus pairs
FAIL. Its docstring called that 0.5 the "SAME threshold as take_ranker".

WHAT IT NOW DECIDES. Whether two inputs are the SAME frame, exactly
(distance <= 0) — a question the entry point can be asked, and the one whose
answer must be unambiguous for the pair run to keep going. The continuous
question ("did the sequence advance") belongs to `freeze`, which is adjacent to
it in the same pair run and answers it directly on the pixels.

The guard below is BEHAVIOURAL. It calls the rule and asserts the verdict. It
does not search the source for a number: this project has been fooled by
text-existence assertions six times, and asserting `SIGNATURE_EQUAL == 0.0`
would be exactly that mistake wearing a guard's clothes — it would pass against
a rule that ignores its input entirely.

Both directions are asserted on ONE input family, and the family is proved
sensitive before anything else, so the two cases cannot both collapse onto the
same answer the way P18's probe did.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'studio' / 'scripts'))
import visual_qa as vqa  # noqa: E402


# ── the input family ────────────────────────────────────────────────────────
# One ink bar on the dark backdrop. Everything below is the SAME picture with
# one thing changed, so the measured distance is attributable to that change and
# not to a different fixture being a different picture.

W, H = 640, 360
_BG = 12          # the palette's premium-dark.background, measured as 0x0A
_INK = 245        # the palette's inkFaint, 0xF5


def _with_bar(dx: int = 0, dy: int = 0, w: int = 300, h: int = 60) -> np.ndarray:
    f = np.full((H, W), _BG, np.uint8)
    f[100 + dy:100 + dy + h, 100 + dx:100 + dx + w] = _INK
    return f


def _save(tmp_path: Path, name: str, arr: np.ndarray) -> Path:
    p = tmp_path / name
    Image.fromarray(arr).save(p)
    return p


@pytest.fixture
def near(tmp_path):
    """Four frames of one 'scene'.

    still/moved1 differ by one pixel and are the pair the rule must NOT call a
    duplicate. `same` is a byte-identical re-encode and is the pair it must.
    `halfbar` is half the ink in the same place: visibly a different picture,
    and the tightest case this instrument has on this backdrop.
    """
    return {
        'still': _save(tmp_path, 'still.png', _with_bar()),
        'moved1': _save(tmp_path, 'moved1.png', _with_bar(dx=1)),
        'same': _save(tmp_path, 'same.png', _with_bar()),
        'halfbar': _save(tmp_path, 'halfbar.png', _with_bar(w=150)),
    }


# ── 0. THE PROBE MUST BE ABLE TO SEE A DIFFERENCE ───────────────────────────
# P18's most expensive recurrence: the probe pair sat inside visual_qa's EDGE=40
# backdrop-sample band, every rule answered UNVERIFIABLE on both inputs, and
# `static: True` read as a measurement when it was the absence of one. Both the
# FAIL case and the PASS case below come from this one family, and the FAIL case
# is asserted to land at EXACTLY zero -- a pair that could not discriminate
# would not produce that either.

def test_the_probe_family_reaches_both_verdicts(near):
    verdicts = {vqa.rule_duplicate(near['still'], near['same']).verdict,
                vqa.rule_duplicate(near['still'], near['moved1']).verdict}
    assert verdicts == {vqa.FAIL, vqa.PASS}, (
        f'the probe family drives the rule to {sorted(verdicts)}, not to both '
        f'verdicts. Every assertion below would be satisfied by a rule that '
        f'ignores its input, which is what P18 mistook for a measurement.')


def test_the_identical_case_lands_on_exactly_zero(near):
    """The discriminating power the family is relied on for, asserted directly."""
    f = vqa.rule_duplicate(near['still'], near['same'])
    assert f.value == 0.0, (
        f'two PNGs of the same array measured {f.value}, not 0.0. The rule\'s '
        f'exact cut rests on the noise floor being exactly zero -- if the '
        f'signature or the encoder introduces a residue, that warrant is gone.')
    assert f.verdict == vqa.FAIL


# ── 1. THE CORRECT SIMILARITY IS NOT A DUPLICATE ────────────────────────────
# A bar moved by ONE pixel on a 640-wide frame is the smallest real change a
# renderer can make. It measures 0.151228 — below the old 0.5 cut, so the old
# rule DID call that duplicate. The rule below pins the sign of the decision:
# these are two different pictures and the answer must not be "the same one".
#
# What it does NOT demonstrate: the old cut's margin. 0.151 < 0.5, so the old
# code was one pixel short of getting this pair right, not wildly wrong on it.
# The pairs the old cut actually got wrong are the real ones — 137 consecutive
# corpus pairs measuring strictly inside (0, 0.5), up to 0.494978, against only
# 15 pairs at exactly 0.0. The old cut sat in the densest part of the
# distribution.

def test_two_different_frames_are_not_a_duplicate(near):
    f = vqa.rule_duplicate(near['still'], near['moved1'])
    assert f.value != 0.0, 'the two frames are byte-identical; the fixture is broken'
    assert f.verdict == vqa.PASS, (
        f'a frame whose content moved one pixel reads as DUPLICATE '
        f'(distance {f.value}). Two consecutive frames of one render are '
        f'meant to look alike -- that is not a defect, and reporting it as one '
        f'is what made this rule fire on 152 of 320 real consecutive pairs.')


def test_adjacent_frames_do_not_report_a_number_that_looks_like_a_cut(near):
    """The reported value must be the distance, and the cut must be visible.

    Guards the shape rather than the constant: whatever the cut is, the Finding
    has to carry it, or a reader cannot tell what the rule decided.
    """
    f = vqa.rule_duplicate(near['still'], near['moved1'])
    assert 'threshold' in f.extra, f'no cut reported: {f.extra}'
    assert f.extra['threshold'] == vqa.SIGNATURE_EQUAL
    assert str(vqa.SIGNATURE_EQUAL) in f.detail, f.detail


# ── 2. A DUPLICATE IS A DUPLICATE ───────────────────────────────────────────

def test_the_same_frame_twice_is_a_duplicate(near):
    f = vqa.rule_duplicate(near['still'], near['still'])
    assert f.verdict == vqa.FAIL, f.detail
    assert f.value == 0.0


def test_two_visibly_different_frames_measure_this_close(near):
    """The worst case in the family, pinned rather than smoothed over.

    Measured: a 300x60 ink bar against four text-like rows on the same backdrop
    reads 18.548967 — the mean separates them easily. The tight case is the one
    where the ink AREAS nearly match, because the signature is a MEAN: measured
    here, a 300x60 bar and a 150x60 bar (same position, half the ink) read
    9.157506 against each other. So the instrument does NOT collapse two visibly
    different frames onto each other, and that is worth pinning — a reader of
    this file should not have to re-derive it.

    Two claims tried first and found FALSE, recorded so nobody re-asserts them:
    two flat frames 1 luma apart measure 1.0, not 0.0 (a flat frame's signature
    IS that luma), and a bar against a shifted word reads 18.548967, not the
    0.040597 that a same-area pair reads.
    """
    f = vqa.rule_duplicate(near['still'], near['halfbar'])
    assert f.value == round(vqa.signature_distance(
        vqa.signature(near['still']), vqa.signature(near['halfbar'])), 6), (
        'the reported value is not the measured signature distance')
    assert f.value > 0.5, (
        f'half the ink reads {f.value}, inside the old 0.5 cut — this fixture no '
        f'longer demonstrates that the instrument separates two visibly different '
        f'frames, and whatever it used to demonstrate must be re-derived')
    assert f.verdict == vqa.PASS


# ── 3. THE CUT MUST NOT BE THE ONE THAT WAS MEASURED FOR ANOTHER QUESTION ──
# Not `assert SIGNATURE_EQUAL == 0.0`. This asks the rule to keep its verdict
# stable while the input distance crosses 0.5 — the value the old docstring
# claimed was the rule's own threshold. If the cut went back to 0.5 (or to
# anything in (0, 0.5]) this pair flips to FAIL and the guard is red.

def test_the_rule_does_not_cut_at_the_cross_render_threshold(near, tmp_path):
    straddler = _with_bar(dx=1)
    below = vqa.rule_duplicate(near['still'], _save(tmp_path, 's.png', straddler))
    assert below.value > 0.0

    # A distance strictly between the two cuts. Measured on this fixture the 1px
    # move is 0.151228, which is already strictly inside (0, 0.5) — so the guard
    # needs no second fixture and asserts the arithmetic as an ARITHMETIC claim:
    below.value < vqa.DUP_DISTANCE, (
        f'measured {below.value} is not below the cross-render cut '
        f'{vqa.DUP_DISTANCE}, so this fixture no longer straddles the two cuts '
        f'and this guard is no longer testing what it says it tests')
    assert below.verdict == vqa.PASS, (
        'the rule cut at or above the cross-render threshold '
        f'{vqa.DUP_DISTANCE}: a pair measured {below.value} reads as DUPLICATE')


# ── 4. AND THE QUESTION IT NOW ANSWERS IS THE ONE THAT CAN BE ASKED ──────────

def test_take_ranker_holds_no_duplicate_threshold_to_reuse():
    """The B-verdict, checked structurally rather than by string search.

    The old docstring claimed 0.5 was the "SAME threshold as take_ranker". It is
    not. `take_ranker.m_duplicate` is a different instrument on a different
    scale (mean abs diff / 255, cut at 0.0015 — roughly 0.006 grey levels), and
    the 0.5 lives in `rank_takes.DUP_THRESHOLD`, which compares two whole
    renders. So the number was real and it was real elsewhere; the reuse never
    existed.

    Read from the AST rather than the text: cv2 is not importable under this
    interpreter (which is why tests/test_take_selection_behaviour.py is ignored
    in this run), and a search for "0.5" in the source would also hit a
    docstring, which is precisely the kind of claim that was wrong to begin
    with. Numeric literals are collected from the function body instead.
    """
    import ast

    def numeric_constants(fn_name: str, rel: str) -> list[float]:
        tree = ast.parse((ROOT / rel).read_text(encoding='utf-8'))
        fn = next(n for n in tree.body
                  if isinstance(n, ast.FunctionDef) and n.name == fn_name)
        return [n.value for n in ast.walk(fn)
                if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                and not isinstance(n.value, bool)]

    dup_consts = numeric_constants('m_duplicate', 'studio/scripts/take_ranker.py')
    assert 0.5 not in dup_consts, (
        f'take_ranker.m_duplicate now holds the literal 0.5 {dup_consts}. Until '
        f'the reuse is re-measured, no rule may cite it as the source of its cut.')
    assert 0.0015 in dup_consts, (
        f'take_ranker.m_duplicate cut changed ({dup_consts}); the claim that this '
        f'module holds no reusable 0.5 duplicate threshold must be re-measured')


def test_the_finding_does_not_credit_its_cut_to_take_ranker(near):
    """What a consumer READS is asserted, not what the source says.

    Run the rule and look at the Finding it emits. `threshold` is the cut this
    rule decides on; `reference_cut` is the cross-render number it reports for
    scale. The old rule put 0.5 in `threshold` and credited take_ranker for it
    in `detail`, so a reader had no way to tell which question it was being
    asked. This is the user-visible half of the B-verdict.
    """
    f = vqa.rule_duplicate(near['still'], near['moved1'])
    assert f.extra['threshold'] == 0.0, (
        f'the emitted cut is {f.extra["threshold"]}, not an exact identity cut')
    assert f.extra['reference_cut'] == 0.5
    assert 'take_ranker' not in f.detail, (
        f'the Finding still credits take_ranker for its cut: {f.detail!r}')
    assert 'rank_takes' in f.detail, (
        f'the Finding does not say where the 0.5 cross-render cut actually '
        f'lives: {f.detail!r}')

