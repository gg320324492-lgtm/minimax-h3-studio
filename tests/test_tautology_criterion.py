"""The guard of the guard.

`test_locked_fields_wiring.py` refuses to test its own criterion and says why:

    "a test rewriting its own source: six silent CRLF patch failures, and one
     `git checkout --` that discarded uncommitted work"
    ...
    "Weakening the checks above leaves the suite fully green. 'The guard is
     still there' is not the same claim as 'the guard works'."

The first clause is about a test *writing its own source file at runtime*.
Everything below is a pure function of an `ast` tree parsed from a string
literal in this file, or of trees parsed from other files' text -- so running
this module does not write anything. That is measured, not promised:
`test_this_guard_writes_nothing_to_disk` hashes every file under `tests/`
before and after the whole scan and fails if a single byte moved.

The second clause is not an argument against testing the criterion, it is the
argument FOR this file. P50 narrowed one copy of the criterion to
`test.values[0]`; three copies of a judgement is how that happened. There is
now one criterion (`tautology_criterion.py`) and one place that pins it.
"""

import ast
import hashlib
from pathlib import Path

import pytest

from tautology_criterion import (
    ALL_RULES, DEFAULT_RULES, is_constant_truth, is_excluded_middle,
    is_neutered, is_self_comparison, offenders,
)

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / 'tests'


def fired(stmt: str) -> bool:
    """Run the REAL criterion over one assertion spelled as a string."""
    tree = ast.parse(f'def test_probe():\n    {stmt}\n')
    return bool(offenders(tree))


# ── the defect space, and what each historical criterion caught ──────────────
# The last three columns are the MEASURED coverage of the three criteria that
# existed before this file, reproduced from a 20-shape run. They are written
# down here so the claim in tautology_criterion's docstring cannot rot into
# prose: if a rule is ever removed, the row for it is the thing that goes stale,
# and `test_the_merged_criterion_is_the_measured_union` is what checks it.
DEFECTS = [
    # (shape,                                                  c1, c2, c3)
    ('assert True',                                            True,  True,  True),
    ('assert True or X',                                       True,  True,  True),
    ('assert X or True',                                       True,  True,  False),
    ('assert X or Y or True',                                  True,  True,  False),
    ('assert (X or True) and Y',                               False, True,  False),
    ('assert X == X',                                          True,  False, False),
    ('assert not False',                                       False, False, False),
    ('assert 1',                                               True,  False, False),
    ('assert X and False',                                     False, False, False),
    ('assert X or not X',                                      False, False, False),
    ('assert f() == f()',                                      True,  False, False),
    ('assert X is None or True',                               True,  True,  False),
    ('assert X > 0 or True',                                   True,  True,  False),
    ('assert True if X else Y',                                False, False, False),
    ('assert X is None or X is not None',                      False, False, False),
    ('assert f() != f()',                                      True,  False, False),
]

# Correct assertions the criterion must leave alone. A guard that flags these
# is the false-positive machine, and a rule that fires on correct code gets
# switched off -- at which point it cannot catch anything either.
LEGITIMATE = [
    'assert a or b',
    'assert X == Y',
    'assert X is not None',
    'assert len(xs) == 0 or "skip" in msg',
    'assert returncode != 0 or not rows',
    'assert a == b or c == d',
]


def test_the_criterion_flags_every_shape_it_claims_to():
    """Each shape the criterion is supposed to catch, caught.

    The shapes it does NOT claim are named in
    `test_the_three_shapes_only_the_locked_fields_rule_caught` and
    `test_the_known_gaps_are_named_here`, so they cannot be forgotten quietly.
    """
    claimed = [s for s, c1, c2, c3 in DEFECTS if c2 or c3]
    missed = [s for s in claimed if not fired(s)]
    assert not missed, (
        f'the criterion stopped flagging {missed}. These are always-true '
        f'assertions; a neutered assertion keeps its message and its line and '
        f'survives review.')


def test_the_three_shapes_only_the_locked_fields_rule_caught():
    """The measured cost of not merging locked_fields_wiring in wholesale.

    `test_locked_fields_wiring.py` catches three shapes that the p42 and p27
    criteria were both blind to -- `X == X` and its relatives. The merged
    criterion does NOT catch them, and that is deliberate rather than an
    oversight:

      * the rule that catches them (`is_self_comparison`) was MEASURED to fire
        on `test_pipeline_validates_the_schema.py:332`,
        `assert sg.schema() is sg.schema()`, where `sg.schema` is `lru_cache`d
        and the identity of the two results is the whole point;
      * there is no sound syntactic way to separate `X == X` (a mistake) from
        `f() is f()` (a cache-identity check) -- they are the same tree. A
        heuristic fitted to the one example in this repository would be a rule
        with an unmeasured blind spot, which is how this file came to exist.

    So the capability STAYS in `test_locked_fields_wiring.py`, where it is
    applied to that file's eleven contract tests and its false positive does
    not arise. It is not duplicated into the repo-wide default set.

    If a future change makes any of these fire, this test goes red and that is
    GOOD NEWS: move the shape into DEFECTS, re-measure, and record it.
    """
    locked_only = [s for s, c1, c2, c3 in DEFECTS
                   if c1 and not (c2 or c3) and not fired(s)]
    assert locked_only == ['assert X == X', 'assert f() == f()',
                           'assert f() != f()'], (
        f'the measured gap closed or grew: {locked_only}. Re-measure the four '
        f'criteria and record the result before changing this test.')
    for stmt in locked_only:
        assert not fired(stmt), (
            f'`{stmt}` is now caught by the default rules. That is an '
            f'improvement -- but check it against '
            f'`sg.schema() is sg.schema()` first, because the rule that would '
            f'catch it is the one with a measured false positive.')


def test_the_criterion_leaves_correct_assertions_alone():
    """The false-positive half. Without this the criterion would be widened."""
    flagged = [s for s in LEGITIMATE if fired(s)]
    assert not flagged, (
        f'the criterion flags {flagged}, which assert real things. A rule that '
        f'fires on correct code gets switched off, and then it catches nothing.')


def test_the_criterion_is_not_the_p27_half_of_it():
    """P50's defect, pinned.

    P42's meta-guard was blind on the side that mattered: it looked only at
    `test.values[0]`, so it caught `assert True or X` and was blind to
    `assert X or True` -- the same neutering, spelled the other way round, and
    that spelling was sitting in P42's own file. Both spellings are required
    here, so narrowing the criterion to the first operand goes red.
    """
    for stmt in ('assert True or X', 'assert X or True',
                 'assert X or Y or True', 'assert (X or True) and Y'):
        assert fired(stmt), (
            f'`{stmt}` is always true and was not flagged. If this went red for '
            f'a reason about a rule that no longer exists, the criterion has '
            f'been narrowed -- that is the P50 defect, and it happened here.')


def test_the_merged_criterion_is_the_measured_union_of_p42_and_p27():
    """The superset claim, checked rather than asserted.

    Every shape that the p42 criterion or the p27 criterion caught must still be
    caught. If someone deletes a rule from DEFAULT_RULES, a shape only that rule
    caught goes un-flagged and this test fails naming the shape.
    """
    regressions = [s for s, c1, c2, c3 in DEFECTS
                   if (c2 or c3) and not fired(s)]
    assert not regressions, (
        f'{regressions} were caught by p42 or p27 and are not caught now. The '
        f'merged criterion must be a superset of both -- that is what makes '
        f'collapsing the copies safe rather than a narrowing.')


@pytest.mark.parametrize('shape', ['assert X and False',
                                   'assert X is None or X is not None'])
def test_the_known_gaps_are_named_here(shape):
    """Two shapes no rule catches. This test exists so they stay KNOWN.

    `assert X and False` is always FALSE, so it fails loudly on every run
    rather than passing silently -- a different failure from neutering, and
    out of scope for a criterion about assertions that assert nothing.

    `assert X is None or X is not None` IS always true and IS missed: the two
    operands are `X is None` and `not (X is None)`, which are each other's
    negation only after the `not` is seen. It is recorded here rather than
    fixed, because widening `is_excluded_middle` to reach it is a change to a
    shipped criterion and belongs in its own measured change.

    If a future change makes either of these fire, this test goes red and that
    is GOOD NEWS -- move the shape into DEFECTS and record the measurement.
    """
    assert not fired(shape), (
        f'`{shape}` is now flagged. That closes a documented gap -- move it '
        f'from this list into DEFECTS in the same commit.')


def test_the_self_comparison_rule_is_not_in_the_default_set():
    """The one rule that is measured to be wrong on this repository.

    `test_pipeline_validates_the_schema.py:332` asserts
    `sg.schema() is sg.schema()`. `sg.schema` is `lru_cache`d, so the identity
    of the two results IS the assertion. The rule is kept -- it catches real
    `X == X` neutering -- but it is not in DEFAULT_RULES, and this test is what
    stops that from being tidied away into a false positive.
    """
    assert is_self_comparison not in DEFAULT_RULES, (
        'is_self_comparison fires on a correct assertion in this repository '
        '(the lru_cache identity check). Putting it in DEFAULT_RULES makes the '
        'repo-wide guard red on correct code.')
    assert is_self_comparison in ALL_RULES, (
        'the rule should stay available, just not in the default set.')


def _hash_tests_dir() -> dict:
    return {p: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(TESTS.rglob('*.py'))}


def test_no_assertion_in_this_repository_asserts_nothing():
    """The guard itself, over every test file in the repository."""
    hits = []
    for p in sorted(TESTS.rglob('test_*.py')):
        hits += [(p, lineno, why) for lineno, why
                 in offenders(ast.parse(p.read_text(encoding='utf-8')))]
    pretty = [f'{p.relative_to(ROOT).as_posix()}:{n}  {why}' for p, n, why in hits]
    assert not hits, (
        f'{len(hits)} assertion(s) in tests/ assert nothing:\n  '
        + '\n  '.join(pretty)
        + '\n\nEach of these passed for any input, which is the same as not '
          'testing. Restore the real condition.')


def test_this_guard_writes_nothing_to_disk():
    """The claim that makes building this file safe, measured.

    `test_locked_fields_wiring.py` lists what happens when a test rewrites its
    own source: six silent CRLF patch failures and a `git checkout --` that
    discarded uncommitted work. The way to not be that test is to never write.
    This hashes every `.py` under `tests/`, runs the real scan, and hashes
    again: if a byte moved, the guard is doing the thing the docstring warns
    about and this fails.
    """
    before = _hash_tests_dir()
    assert before, 'no files found under tests/ -- the hash covered nothing'
    for p in sorted(TESTS.rglob('test_*.py')):
        offenders(ast.parse(p.read_text(encoding='utf-8')))
    after = _hash_tests_dir()
    changed = sorted(k.name for k in set(before) | set(after)
                     if before.get(k) != after.get(k))
    assert not changed, (
        f'running the guard changed {changed}. The criterion is a pure '
        f'function of a tree precisely so this cannot happen.')