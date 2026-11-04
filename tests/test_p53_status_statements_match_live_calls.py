"""P53 — a note that OPENS with a verdict word is a status claim; it must
match what the rule actually answers, and this file answers it by calling.

THE FAILURE THIS EXISTS FOR (P52, measured not argued).

`MEASURED_NOTE`'s own header (`studio/scripts/qa_layers.py`) states the
purpose of the dict: the notes are kept beside the table "so a guard can
assert the layer without the measurement drifting out of the file that
states it." Before P53 no guard read the status sentences at all:

  * `test_p40` guards NUMBERS — its grammar is a closed collection NAME plus
    a verb plus a digit. "UNVERIFIABLE on all 333 corpus frames when no
    --declared-px is supplied" contains no collection name and no size
    claim, so P52's change (`e027040`: the verdict moved from UNVERIFIABLE
    to UNAVAILABLE-always) slid through it without a red.
  * `test_p18` re-derives three selected facts by calling rules
    (`rule_contrast` still FAILs, `rule_contrast_frame` still UNAVAILABLE,
    `rule_missing_asset` still ignores props) — a transcription of SOME of
    the prose into Python. `font_size`'s status sentence had no
    transcription, so after P52 it lay false and green: the note said the
    rule answers UNVERIFIABLE without an argument and is "dead in this CLI
    as shipped"; the rule answered UNAVAILABLE and still measured.

THE CRITERION, AND WHY IT IS NOT A TEXT MATCHER.

Prose that mentions verdicts is everywhere and mostly not a claim: "30 of
333 corpus frames FAIL" is a corpus count, "safe_area says UNVERIFIABLE and
clipping says FAIL" is conditional on a padX=0 frame, "It used to be emitted
... which made that path exit 1" is history. A matcher scanning note bodies
for verdict words would fire on all of it — the broad false-positive machine
this project's P51 ruling forbids: a criterion must be decidable and name
its positive and negative classes.

So the anchor is POSITIONAL and CLOSED, not a search:

    a note makes a live status claim iff its FIRST TOKEN, stripped of
    trailing punctuation, is one of the four verdict constants the module
    that owns verdicts defines (visual_qa.PASS/FAIL/UNAVAILABLE/
    UNVERIFIABLE — imported as data, not re-typed).

For each claimed note, this file calls the rule under the condition the
prose states and asserts the verdict equals the note's first token. The
conditions are NOT machine-parsed (that is the matcher trap); they are
hand-registered pairs (condition label, callable) reviewed against the
sentence, and the VERDICT is measured live rather than written down. What
the guard actually proves is "word == live answer"; the pairing of the word
to the right condition is the human review, which is exactly where P52
went wrong once the pairing existed only in prose.

THE POSITIVE CLASS (today's anchors — the set itself is asserted):

  font_size      "UNAVAILABLE on every frame, with or without --declared-px"
  aspect         "UNVERIFIABLE on all 333 corpus frames run as --frame"
  contrast_frame "UNAVAILABLE on every frame"

theme_contrast's note opens with "P22." — a count (8 of 24 pairs), not a
claim that the rule answers FAIL for a condition; its verdict-stability is
guarded by `test_p18`'s live call. blur opens with "30" — a corpus count.
Both stay outside the anchor, deliberately.

THE NEGATIVE CLASS (what a working guard must refuse):

  * a note claiming a verdict the rule does not answer on that condition
    (planted in `test_the_guard_can_say_no`);
  * a note whose claim drifted out of position — an unanchored new claim
    cannot hide, because the anchor set is asserted equal to the probe set
    (`test_the_anchor_set_is_still_the_probe_set`): prose that starts
    leading with a verdict word without a registered probe goes red, and so
    does a probe whose prose stopped leading with one. A legitimate change
    to either side goes red the same way and is the point — red means
    "change knowingly", as in P40's registry.
  * font_size's second half: the note also claims the instrument still
    MEASURES (bands, median, min, max, and the ratio when --declared-px is
    supplied). A future change that returns UNAVAILABLE from a rule that no
    longer measures would leave the verdict word true and the sentence
    false; `test_the_measurement_half_of_the_claim_holds` catches it by
    reading `extra` from the live call. P52's lesson is that the claim is
    two facts — the verdict AND the measurement — and this guard holds both.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / 'studio' / 'scripts')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import visual_qa as vqa  # noqa: E402
import qa_layers as ql  # noqa: E402

#: Closed vocabulary. Imported from the module that owns verdicts, so adding a
#: fifth verdict there cannot silently escape here.
_VERDICT_WORDS = {vqa.PASS, vqa.FAIL, vqa.UNAVAILABLE, vqa.UNVERIFIABLE}


def leading_verdict_claim(note: str) -> str | None:
    """The note's first token iff it is one of the four verdict words."""
    first = note.strip().split(None, 1)[0].rstrip(':,.;')
    return first if first in _VERDICT_WORDS else None


# ── the probes: one entry per claim, each entry a list of (condition, call) ──
#
# The condition label is the prose's own words; the callable is how this file
# instantiates it on the synthetic frames qa_layers documents at PROBE_*
# (not the gitignored corpus — a guard that needs out/ passes on the machine
# that made it and dies on a clone, the reason stated in qa_layers'
# `_emitted_names`).

_PROBES: dict[str, list[tuple[str, object]]] = {
    'font_size': [
        ('no --declared-px', lambda: vqa.rule_font_size(ql._probe_content())),
        ('--declared-px 20.0', lambda: vqa.rule_font_size(ql._probe_content(), 20.0)),
        ('a frame with no ink at all', lambda: vqa.rule_font_size(ql._probe_flat())),
    ],
    'aspect': [
        ('run as --frame with no declared format',
         lambda: vqa.rule_aspect((ql.PROBE_W, ql.PROBE_H), None)),
    ],
    'contrast_frame': [
        ('the content probe frame', lambda: vqa.rule_contrast_frame(ql._probe_content())),
        ('the flat probe frame', lambda: vqa.rule_contrast_frame(ql._probe_flat())),
    ],
}


def claimed_notes(notes: dict[str, str]) -> dict[str, str]:
    """The notes that open with a verdict word -> the word they claim."""
    out = {}
    for key, value in notes.items():
        word = leading_verdict_claim(value)
        if word is not None:
            out[key] = word
    return out


def disagreements(claims: dict[str, str], answers: dict[str, list[str]]) -> list[str]:
    """Pure comparison: every rule's claimed word must equal every measured
    verdict under the conditions the note states. Synthetic input in,
    problems out — which is what `test_the_guard_can_say_no` exploits."""
    problems = []
    for key in sorted(claims):
        for verdict in answers.get(key, []):
            if verdict != claims[key]:
                problems.append(
                    f'{key}: the note opens "{claims[key]}" but the rule '
                    f'answered "{verdict}" on the registered condition')
    return problems


# ── the guard ────────────────────────────────────────────────────────────────

def test_the_anchor_set_is_still_the_probe_set():
    """A status claim cannot enter unprobed or leave unregistered — the
    drift P52 produced happened precisely because the claim lived in prose
    that no probe covered."""
    anchor = set(claimed_notes(ql.MEASURED_NOTE))
    assert anchor == set(_PROBES), (
        f'the verdict-led notes {sorted(anchor)} and the registered probes '
        f'{sorted(_PROBES)} differ. Either a new note opens with a verdict '
        f'word and needs a probe (register the condition the prose states), '
        f'or a note stopped opening with one and the probe must go with it — '
        f'a claim that changed position is a claim that changed.')


def test_every_status_word_equals_the_live_answer():
    """The guard itself: call, compare, report."""
    claims = claimed_notes(ql.MEASURED_NOTE)
    answers: dict[str, list[str]] = {}
    for key, conditions in _PROBES.items():
        got = []
        for label, fn in conditions:
            finding = fn()
            assert finding.verdict in _VERDICT_WORDS, (
                f'{key}: {label} answered {finding.verdict!r}, outside the '
                f'verdict vocabulary — the probe is broken, not the note')
            got.append(finding.verdict)
        answers[key] = got
    problems = disagreements(claims, answers)
    assert not problems, '\n'.join(problems)


def test_the_measurement_half_of_the_claim_holds():
    """font_size's note claims two things: the verdict AND that the rule
    still MEASURES. A guard on the verdict alone would still greenlight the
    old "dead" reading — an instrument that answers UNAVAILABLE and reports
    nothing. The measurement is read from the live call's extra."""
    no_declared = vqa.rule_font_size(ql._probe_content())
    for k in ('bands', 'band_px', 'measured_median_px', 'min', 'max'):
        assert k in no_declared.extra, (
            f'font_size: the note says the rule still measures and reports '
            f'{k} in extra; the live call does not ({sorted(no_declared.extra)})')
    assert no_declared.extra['bands'] >= 1, (
        'font_size: the content probe carries ink, so a measured band count '
        'of zero means the measuring half died — which is what the note '
        'denies')
    with_declared = vqa.rule_font_size(ql._probe_content(), 20.0)
    assert 'declared_px' in with_declared.extra and 'measured_over_declared' in with_declared.extra, (
        'font_size: the note says a supplied --declared-px still yields the '
        f'measured/declared ratio; extra carried {sorted(with_declared.extra)}')
    ratio = with_declared.extra['measured_over_declared']
    expected = round(with_declared.extra['measured_median_px'] / 20.0, 4)
    assert abs(ratio - expected) < 1e-9, (
        f'font_size: the reported ratio {ratio} is not median/declared '
        f'{expected} — the note says the ratio travels; a stale ratio is a '
        f'false claim wearing the right verdict word')


# ── the negative class ───────────────────────────────────────────────────────

def test_the_guard_can_say_no():
    """A guard that has only ever seen healthy claims has not been shown to
    be a guard. The comparison is pure, so a planted disagreement can be
    fed without touching the repo: a claim word that does not match the
    measured verdict must be reported, and a matching pair must not be —
    which is what makes a tautological or always-pass criterion go RED
    here rather than green everywhere (P53's mutation contract)."""
    # claims are words (what claimed_notes extracts), not note bodies — the
    # same spelling the live tests feed the same pure comparison.
    planted_wrong = dict(claimed_notes(ql.MEASURED_NOTE), font_size='UNVERIFIABLE')
    measured = {'font_size': ['UNAVAILABLE'], 'aspect': ['UNVERIFIABLE'], 'contrast_frame': ['UNAVAILABLE']}
    hits = disagreements(planted_wrong, measured)
    assert any('font_size' in h for h in hits), (
        f'a planted claim (UNVERIFIABLE) against a measured verdict '
        f'(UNAVAILABLE) was not reported: {hits}. The comparison has gone '
        f'vacuous — it cannot say no, so it is not a guard.')

    planted_right = claimed_notes(ql.MEASURED_NOTE)
    assert disagreements(planted_right, measured) == [], (
        'a true claim was reported — the comparison fires where it should '
        'stay silent, which is the false-positive half of the failure it '
        'exists for')

    # And the positional anchor itself must refuse a mid-sentence verdict:
    # blur's "30 of 333 corpus frames FAIL" is a count, not a claim this
    # guard is authorized to test. If the anchor ever became a text
    # matcher, this assert would go red with it.
    assert leading_verdict_claim(ql.MEASURED_NOTE['blur']) is None, (
        'the anchor stopped being positional — a note that opens with a '
        'corpus count but mentions FAIL mid-sentence is now "claimed", '
        'which is the broad-matcher failure P51 ruled out')
    assert leading_verdict_claim('UNAVAILABLE on every frame') == 'UNAVAILABLE', (
        'the anchor no longer recognises a positional claim — the guard '
        'itself is inert')


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
