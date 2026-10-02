"""One question must not have two numbers (P20).

WHAT THIS EXISTS FOR. `rank_takes.rank_shot` and `select_takes._auto_rank` both
ask "are these two whole takes the same generation?" — same instrument
(`take_ranker.signature_distance`, mean abs difference of a 0..255 grayscale
signature), same population (takes within ONE shot directory), same inputs
(`TakeMetrics._sig`). One cut at `rank_takes.DUP_THRESHOLD`; the other at a
hardcoded `1.0` typed straight into the comparison. Change the threshold and
one call site moves while the other does not, and nothing says so.

THE GUARD CALLS BOTH FUNCTIONS. It does not grep the source for a constant
name or a number: this project has been fooled by text-existence assertions six
times, and the seventh was P19's own first guard. A loop that ignores its input
passes a text assertion just as happily. So the tests below run the real
`rank_shot` and the real `_auto_rank` and compare the `redundant_with` verdicts
they produce on the same input family.

WHAT IS STUBBED, AND WHY IT IS STILL A REAL CALL. Both functions begin by
analysing every mp4 in the shot directory. `analyze` is the ONLY thing in
either path that decodes a video, it needs cv2 (absent from the interpreter
that runs this suite), and it is upstream of the question being guarded. It is
replaced with a stub that returns metrics carrying the family's signatures;
the loop under test — the comparison, the threshold, the ordering — is the
repo's own code, unedited. `test_the_family_produces_both_verdicts` runs first
and fails if the family cannot discriminate, so "both agreed" can never be an
artefact of a family that only produces one answer.

WHY ONE NUMBER AND NOT TWO (ruling A). Measured, not assumed:
  * population — the 12 shot dirs on disk are exactly `select_takes`'s 12
    `shot_targets`; only S05A (4 takes) and S06 (2 takes) hold more than one,
    so 7 pairs reach either loop;
  * distribution — those 7 within-shot pairs measure {0.000} ∪ [34.543,
    62.820]. The 0.000 is the S06 same-seed rerun; the rest are genuinely
    different generations. 0.5 and 1.0 both sit inside the empty gap between.
No measurement separates 0.5 from 1.0 — both call exactly one pair a duplicate.
But a second literal is not free: it is a second number to keep in step, and it
widens the blind spot (a near-duplicate at 0.7 is caught by 0.5, missed by
1.0). Hence one owner, imported.

THE THIRD RULER IS NOT FORCED EQUAL. `visual_qa.rule_duplicate` is a third
`signature_distance`, but P19 gave it `SIGNATURE_EQUAL = 0.0` because
`--frame-pair` hands it two CONSECUTIVE FRAMES of one render — a different
population, and one the corpus provably does not separate. That difference is
recorded here with its evidence, not hidden by asserting all three agree.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

try:                                     # the measurement below is drivable
    import pytest                          # from 3.10, which has cv2 but no
    HAVE_PYTEST = True                    # pytest, so keep the import optional
except ImportError:
    pytest = None
    HAVE_PYTEST = False

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'studio' / 'scripts'
sys.path.insert(0, str(SCRIPTS))

# cv2 lives only in the 3.10 interpreter and take_ranker imports it at module
# scope. Nothing this file's guards exercise touches a cv2 symbol, so a stub is
# enough to import the modules here. Without it the file would have to be
# --ignore'd like test_take_selection_behaviour.py, and a guard nobody runs is
# not a guard.
#
# The stub is installed ONLY when a real cv2 cannot be imported: it would
# otherwise shadow the genuine module and silently disarm the corpus
# measurement at the bottom of this file (P20's own first draft did exactly
# that, and `test_measured_within_shot_distribution` failed with
# "module 'cv2' has no attribute 'VideoCapture'" under a real 3.10 run).
CV2_IS_REAL = True
try:
    import cv2 as _cv2_probe          # noqa: F401
except ImportError:
    CV2_IS_REAL = False
    # A FAILED `import cv2` leaves `sys.modules['cv2'] = None`, and None is not
    # absent — `sys.modules.setdefault('cv2', stub)` is therefore a NO-OP after
    # a failed import, and every later `import take_ranker` fails on it.
    # P20's first draft used setdefault and shipped exactly that: select_takes
    # printed "take_ranker unavailable (No module named 'cv2')" at import,
    # `_RANKER` stayed None, and _auto_rank's guard clause returned an empty
    # list on every case — so the mutation test passed while measuring nothing.
    # Assign, do not setdefault, and the guard below asserts it took effect.
    sys.modules['cv2'] = types.ModuleType('cv2')

import rank_takes  # noqa: E402
import take_ranker  # noqa: E402
import visual_qa  # noqa: E402

# select_takes lives in the project's own scripts dir and does its ffmpeg_env
# setup at import time; it has no package, so its directory goes on the path.
sys.path.insert(0, str(ROOT / 'ceo_mindread_ep01' / 'scripts'))
import select_takes  # noqa: E402


SIZE = (10, 112, 64)   # take_ranker.pixel_signature's own output shape


# ── the input family ────────────────────────────────────────────────────────
# Distances are taken from the MEASURED within-shot distribution
# {0.000} ∪ [34.543, 62.820] rather than invented. The pixels are synthetic —
# `analyze` is stubbed, so nothing here is a claim about corpus pixels; the
# real-corpus measurement lives in test_measured_within_shot_distribution below.
FAMILY = [
    # (name, distance between the two takes, note)
    ('same_seed_rerun', 0.0, 'measured: EP01 S06_T01 vs S06_T02 == 0.000'),
    ('near_duplicate_in_the_gap', 0.7,
     'inside the empty gap; 0.5 calls it DUPLICATE, 1.0 does not'),
    ('different_generation_low', 34.543, 'measured: S05A_v1 vs S05A_v2'),
    ('different_generation_high', 62.820, 'measured: S05A_T01 vs S05A_v1'),
]


def _stub(take_id, sig):
    """A TakeMetrics carrying `sig`, with the shape both loops read."""
    m = take_ranker.TakeMetrics(take_id=take_id, path=f'<{take_id}>')
    m._sig = sig
    m.score = 0.5
    return m


def _shot_dir(root, sig_a, sig_b):
    """A shot directory with two takes, and the stub `analyze` that feeds them.

    The .mp4 files are empty placeholders and are never decoded: `analyze`, the
    only decoder in either path, is what reads them, and it is the stub. The
    loop that consumes the signatures is the repo's own.
    """
    raw = root / 'SX'
    root.mkdir(exist_ok=True)
    raw.mkdir(exist_ok=True)
    (raw / 'A_T01.mp4').write_bytes(b'')
    (raw / 'B_T01.mp4').write_bytes(b'')
    sigs = {'A_T01': sig_a, 'B_T01': sig_b}

    def fake_analyze(path, take_id=None):
        return _stub(Path(path).stem, sigs[Path(path).stem])

    return raw, fake_analyze


def _verdicts(monkeypatch, tmp_path, distance):
    """Run BOTH real loops on one distance and return their verdicts.

    Returns {'rank_takes': 'B_T01'|None, 'select_takes': ...}.
    """
    sig_a = np.zeros(SIZE, np.float32)
    sig_b = np.full(SIZE, distance, np.float32)
    # a fresh directory per case: the loops mutate TakeMetrics in place, and a
    # shared one would carry `redundant_with` from the previous case
    raw, fake_analyze = _shot_dir(tmp_path / f'case_{distance!r}', sig_a, sig_b)

    # take_ranker.analyze is replaced because both modules hold their own name
    # binding: rank_takes did `from take_ranker import ... analyze`, and
    # select_takes reached it as `_RANKER.analyze`. Patching only one leaves the
    # other calling the real decoder, which has no cv2 here — that is how this
    # file's first draft produced "the family only ever produces {False}".
    monkeypatch.setattr(take_ranker, 'analyze', fake_analyze)
    monkeypatch.setattr(rank_takes, 'analyze', fake_analyze)

    out = {}
    rt_metrics, _, _ = rank_takes.rank_shot('SX', raw)
    out['rank_takes'] = next((m.redundant_with for m in rt_metrics
                              if m.take_id == 'B_T01'), '<missing take>')

    # rank_shot takes the shot directory itself; _auto_rank takes the ROOT and
    # appends the shot id (its own `shot_dir = raw_root / shot_id`). Passing the
    # shot dir to both makes _auto_rank look in raw/SX, find nothing, and return
    # an empty list — which reads as "no take ever collides" rather than as an
    # error. That is the harness's first draft's bug, not the code's.
    st_metrics, _, st_err = select_takes._auto_rank('SX', raw.parent)
    assert st_err is None, f'_auto_rank failed on the family: {st_err}'
    out['select_takes'] = next((m.redundant_with for m in st_metrics
                                if m.take_id == 'B_T01'), '<missing take>')
    return out


# ── 1. the family is sensitive, BEFORE anything is asserted about it ─────────

def test_the_guard_is_actually_armed():
    """The guard must be running against the code, not against a stub.

    This file's first draft shipped a guard that could not fail: a failed
    `import cv2` left `sys.modules['cv2'] = None`, so the `setdefault` that was
    supposed to install a stub installed nothing, `import take_ranker` then
    failed, select_takes printed "take_ranker unavailable", and `_auto_rank`
    returned an empty list on EVERY case — including the case that should have
    caught the mutation. The mutation test read "6 passed".

    An armed guard is checked before it is trusted. A rule that cannot run
    reports the same "no disagreement" as a rule that ran and agreed.
    """
    assert select_takes._RANKER is not None, (
        'select_takes could not import take_ranker, so _auto_rank short-circuits '
        'to an empty list and every verdict below is vacuous. stderr will say '
        '"take_ranker unavailable" — fix the import (usually the cv2 stub) '
        'before reading any other result in this file.')
    assert select_takes._DUP_THRESHOLD is not None, (
        'select_takes fell back to a null threshold (import failed); its loop is '
        'not the one this file guards')
    assert take_ranker.signature_distance is rank_takes.signature_distance, (
        'rank_takes did not bind take_ranker.signature_distance; it is holding '
        'a different implementation and this guard is measuring the wrong ruler')


def test_the_family_produces_both_verdicts(monkeypatch, tmp_path):
    """Proved first, so "both loops agree" cannot collapse onto "both say no".

    P18's probe landed entirely inside one side of its own threshold and read
    like a rule that ignores its input. If this family could only ever produce
    DUPLICATE (or only ever NOT-DUPLICATE), it would not discriminate between
    the two call sites and every agreement assertion below would be vacuous.
    """
    seen = set()
    for name, distance, note in FAMILY:
        v = _verdicts(monkeypatch, tmp_path, distance)['rank_takes']
        seen.add(v is not None)
        print(f'  {name:28s} distance={distance:<9.3f} '
              f'duplicate={v is not None}   ({note})')
    assert seen == {True, False}, (
        f'the input family only ever produces {seen} — it cannot discriminate '
        f'between the two call sites, so every agreement assertion built on it '
        f'would be vacuous')


# ── 2. THE GUARD: one question, one answer ──────────────────────────────────

def test_the_two_call_sites_answer_identically(monkeypatch, tmp_path):
    """The same comparison must not have two answers."""
    disagreements = []
    for name, distance, note in FAMILY:
        v = _verdicts(monkeypatch, tmp_path, distance)
        if v['rank_takes'] != v['select_takes']:
            disagreements.append(
                f'{name} (distance {distance:.3f}, {note}): rank_takes says '
                f'{v["rank_takes"]!r}, select_takes says {v["select_takes"]!r} '
                f'(rank_takes compares against '
                f'DUP_THRESHOLD={rank_takes.DUP_THRESHOLD!r}, select_takes '
                f'against {_select_takes_threshold()!r})')
    assert not disagreements, (
        'the same comparison has two answers. Same instrument, same population, '
        'same inputs:\n  ' + '\n  '.join(disagreements))


def _select_takes_threshold():
    """The number select_takes' loop compares against."""
    return getattr(select_takes, '_DUP_THRESHOLD', '<missing>')


def test_select_takes_compares_against_the_shared_constant():
    """select_takes must not grow a number of its own again."""
    assert hasattr(select_takes, '_DUP_THRESHOLD'), (
        'select_takes no longer exposes the threshold its loop compares '
        'against; the guard above is reading a name the loop does not use')
    assert select_takes._DUP_THRESHOLD == rank_takes.DUP_THRESHOLD, (
        f'select_takes compares against {select_takes._DUP_THRESHOLD!r} while '
        f'rank_takes compares against {rank_takes.DUP_THRESHOLD!r} — the same '
        f'question must not have two numbers')


def test_the_threshold_is_still_inside_the_measured_gap():
    """0.5 must remain the measured gap, not drift away from it."""
    assert rank_takes.DUP_THRESHOLD == 0.5, (
        f'DUP_THRESHOLD moved to {rank_takes.DUP_THRESHOLD!r}; the measured '
        f'distribution that put 0.5 inside the gap {{0.000}} u [34.543, '
        f'62.820] has to be re-measured before it moves')
    assert 0.0 < rank_takes.DUP_THRESHOLD < 34.543, (
        'DUP_THRESHOLD left the empty gap between the measured duplicate '
        'atom (0.000) and the nearest genuine pair (34.543)')


# ── 3. the third ruler: recorded, not forced equal ──────────────────────────

def test_the_three_rulers_and_the_two_questions_they_answer():
    """There are three `signature_distance`s and TWO questions. Say so.

    Two must answer identically (the guards above). The third,
    `visual_qa.rule_duplicate`, answers a DIFFERENT question and must not be
    dragged to the same number: P19 moved it to `SIGNATURE_EQUAL = 0.0`
    because `--frame-pair` feeds it two CONSECUTIVE FRAMES of one render, and
    measured over the 329-frame corpus that no cut separates that population
    (best balance 0.9969, carried by ONE rerun pair).

    This asserts the DIFFERENCE and its reason rather than asserting the three
    agree. If someone merges the two questions later, this is the test that
    has to change — in the open, with its evidence.
    """
    assert visual_qa.SIGNATURE_EQUAL == 0.0, (
        'visual_qa.SIGNATURE_EQUAL moved; P19 set it against a measured '
        'frame-pair corpus, and that measurement must be redone first')
    assert rank_takes.DUP_THRESHOLD != visual_qa.SIGNATURE_EQUAL, (
        'rank_takes and visual_qa now use the SAME cut. That is correct only '
        'if they are also the same question; P19 measured that they are not '
        '(whole renders vs consecutive frames), so this is a regression')

    # same ARITHMETIC, different POPULATION — and the arithmetic still agrees
    a = np.zeros(SIZE, np.float32)
    b = np.full(SIZE, 34.543, np.float32)
    assert (take_ranker.signature_distance(a, b)
            == visual_qa.signature_distance(a, b)), (
        'the two implementations of signature_distance have drifted apart; '
        'P20 measured them bit-for-bit identical on 120 corpus pairs and 12 '
        'synthetic magnitudes')


# ── 4. anti-drift: two copies of one function drift ─────────────────────────

def test_the_two_rulers_agree_across_the_range():
    """`visual_qa`'s copy of the instrument must stay equal to the original.

    P20 measured the two implementations bit-for-bit identical on all 120
    corpus pairs and on 12 synthetic magnitudes spanning 0..127.5. They are
    separate copies — visual_qa cannot import take_ranker (cv2), which
    `test_the_module_does_not_import_the_renderer` forbids — so drift is the
    risk and is checked rather than assumed.
    """
    rng = np.random.default_rng(20261003)
    base = rng.integers(0, 256, size=SIZE).astype(np.float32)
    for offset in (0.0, 1e-9, 1e-6, 0.001, 0.033, 0.5, 0.7, 1.0, 5.0,
                   34.5, 60.0, 127.5):
        other = (base + offset).astype(np.float32)
        d_tr = take_ranker.signature_distance(base, other)
        d_vq = visual_qa.signature_distance(base, other)
        assert repr(d_tr) == repr(d_vq), (
            f'the two signature_distance copies disagree at offset {offset}: '
            f'take_ranker {d_tr!r} vs visual_qa {d_vq!r}')


# ── 5. the measurement itself, where cv2 exists ──────────────────────────────
#
# The measurement lives in a PLAIN FUNCTION, not inside the test, so it can be
# driven directly by an interpreter that has cv2 but not pytest. py -3.10 on
# this machine has cv2 and NO pytest, so a test that only exists inside pytest
# would never have run: this file's measurement was verified by calling
# measure_within_shot_distribution() from a plain 3.10 script instead.

def measure_within_shot_distribution(raw=None):
    """Real corpus, real decoder: every within-shot take pair's distance.

    This is the population either loop can actually see — takes are paired
    within one shot directory, never across shots. Returns (duplicates,
    genuine) split at the threshold that is in force.
    """
    raw = raw or (ROOT / 'ceo_mindread_ep01' / '03_video_raw')
    takes = sorted(p for p in raw.glob('*/*.mp4') if p.is_file())
    if not takes:
        raise AssertionError(f'no takes found under {raw} — the corpus moved')

    sigs = {p.stem: take_ranker.pixel_signature(p) for p in takes}
    dists = []
    for shot in sorted({p.parent.name for p in takes}):
        ids = sorted(p.stem for p in (raw / shot).glob('*.mp4'))
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                dists.append(take_ranker.signature_distance(sigs[ids[i]],
                                                            sigs[ids[j]]))
    if not dists:
        raise AssertionError('no within-shot pairs to measure')

    dup = [d for d in dists if d < rank_takes.DUP_THRESHOLD]
    gen = [d for d in dists if d >= rank_takes.DUP_THRESHOLD]
    return dup, gen, len(dists)


def test_measured_within_shot_distribution():
    """Re-measure the distribution the ruling rests on. Needs a real decoder.

    The guards above are synthetic because `analyze` needs cv2, which the
    suite's interpreter lacks; this is where the real corpus is measured. It
    SKIPS — rather than lying — when there is no real cv2. Run where cv2
    exists, it asserts the {0.000} u [34.543, 62.820] gap ruling A cites.
    """
    if not HAVE_PYTEST:
        raise AssertionError('run under pytest')
    if not CV2_IS_REAL:
        pytest.skip('no real cv2 in this interpreter; the corpus cannot be '
                    'decoded (drive measure_within_shot_distribution() from '
                    'an interpreter that has cv2 — py -3.10 here)')
    dup, gen, n = measure_within_shot_distribution()
    print(f'\n  within-shot pairs n={n}: duplicates={[round(d, 3) for d in dup]} '
          f'genuine=[{min(gen):.3f}, {max(gen):.3f}]')
    assert dup, 'no duplicate at all — the corpus changed'
    assert max(dup) == 0.0, (
        f'duplicates are no longer exactly pixel-identical: {dup}')
    assert min(gen) > rank_takes.DUP_THRESHOLD, (
        f'a genuine pair now sits at {min(gen):.3f}, at or below the cut '
        f'{rank_takes.DUP_THRESHOLD} — the gap the threshold sits in has closed')
    # the figures ruling A quotes
    assert round(min(gen), 3) == 34.543, (
        f'the quoted lower bound moved to {min(gen):.3f}; the comments in '
        f'rank_takes.py and select_takes.py quote 34.543')
    assert round(max(gen), 3) == 62.820, (
        f'the quoted upper bound moved to {max(gen):.3f}; the comments in '
        f'rank_takes.py and select_takes.py quote 62.820')