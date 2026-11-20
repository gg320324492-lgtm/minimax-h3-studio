"""THE criterion for "this assertion asserts nothing" -- in one place.

There were three copies of this judgement in `tests/` before this module, and
they had drifted apart:

  * `test_locked_fields_wiring.py:594`  `is_tautology`  -- flagged `A == A`
    and bare constants, was blind to a nested `or`.
  * `test_p42_fade_is_not_a_freeze.py:478` `_tautology_offenders` -- walked the
    whole test subtree for `or True`, was blind to `A == A`.
  * `test_p27_visual_acceptance_is_repeatable.py:542` -- checked only
    `test.values[0]`, so it caught `True or X` and was blind to `X or True`.

Measured over a 20-shape space (the table is reproduced in
`test_tautology_criterion.py`, which runs the functions below against it):

    C1 == locked_fields_wiring    flags 10 of the 16 real defects
    C2 == p42                     flags  7 of the 16 real defects
    C3 == p27                     flags  2 of the 16 real defects
    C3 is a strict subset of both C1 and C2.

None of the three is a superset of the others, so "merge them" was not a safe
default. What the table made safe was a narrower, named decision:

  * C3 (p27) is a strict subset of C2, so collapsing C3 onto C2 loses nothing.
    That is the whole of the "three copies" problem for that file.
  * C2 and C1 are INCOMPARABLE -- C1 alone catches `X == X` and friends, C2
    alone catches the nested `(X or True) and Y`. Folding C1 in wholesale would
    have bought that coverage at the cost of a measured false positive, so it
    is NOT done. See `is_self_comparison` below for the measurement, and
    `test_the_three_shapes_only_the_locked_fields_rule_caught` for the shapes
    that remain covered only there.
  * C4, `test_p46_probe_instruments.py`, had no criterion at all. It now has
    one, by delegating here like p27 and p42 do.

So `DEFAULT_RULES` below is the measured union of the p42 and p27 criteria
(p27's being a subset of p42's) plus two rules neither had. It is deliberately
NOT a superset of `test_locked_fields_wiring.py`, and the reason is measured
rather than assumed. Every rule in it is a fact about the AST, not a guess
about truth.

THE GUARD, AND WHY IT IS NOT A GUARD OF A GUARD
----------------------------------------------
`test_locked_fields_wiring.py` deliberately refuses to build a test for its own
criterion, and gives two reasons: the project has a history of tests rewriting
their own source (six silent CRLF patch failures, one `git checkout --` that
discarded uncommitted work), and "the guard is still there" is not the same
claim as "the guard works".

The first reason is about a test *writing its own source file at runtime*. That
is what this module exists to make unnecessary: every function here is a pure
function of an `ast` tree, and `test_tautology_criterion.py` exercises them
against trees parsed from string literals in the test file itself. Running the
guard touches no file on disk. That claim is measured rather than promised --
the guard's own test hashes every file in `tests/` before and after it runs and
fails if any byte moved.

The second reason is not a reason against testing the criterion; it is the
reason this module exists. Three copies of a judgement is how a criterion gets
quietly narrowed in the first place: P50 narrowed one of them to
`values[0]`, which is the defect `test_tautology_criterion.py` now pins.

WHAT IS DELIBERATELY NOT IN THE DEFAULT RULE SET
-------------------------------------------------
`is_self_comparison` is here but is NOT part of `DEFAULT_RULES`, because it was
MEASURED to fire on a correct assertion that already exists in this repository:

    tests/test_pipeline_validates_the_schema.py:332
        assert sg.schema() is sg.schema()

`sg.schema` is `lru_cache`d, so two calls returning the same object is the
property being asserted, not a tautology. A criterion that flagged it would be
wrong, and the way to be wrong here is the dangerous way: a rule that fires on
correct code gets switched off, and then it cannot catch the defects either.

`is_neutered` and `is_constant_truth` were measured across every `test_*.py` in
this repository and fire only on genuine defects.
"""

import ast

__all__ = [
    'is_neutered',
    'is_constant_truth',
    'is_excluded_middle',
    'is_self_comparison',
    'DEFAULT_RULES',
    'ALL_RULES',
    'offenders',
]


def _is_literal_true(node) -> bool:
    """Is this node exactly the constant `True`?

    A VALUE check, not `isinstance(node, ast.Name)`. Since 3.8 a bare `True`
    parses to `ast.Constant`, never `ast.Name`, so the `ast.Name` version
    cannot match anything -- which is how five neutered assertions in P27's own
    file passed a guard that reported PASS.
    """
    return isinstance(node, ast.Constant) and node.value is True


def is_neutered(test) -> bool:
    """`assert True`, or an `or` carrying a literal `True` anywhere inside.

    Two shapes. `assert True` -- the condition IS the constant. And any `or` in
    the test subtree with a literal-True operand, wherever it sits: `X or True`,
    `True or X`, `X or Y or True`, and the nested `(X or True) and Y`, where
    the outer node is an `and` and the defect is one level down.

    This is a fact about the operator, not a guess about truth: an `or` is true
    when ANY operand is true, so an operand that is the constant `True` makes
    the expression true whatever the others evaluate to. A legitimate
    `assert a or b` cannot be flagged, because neither operand is literal
    `True`.

    It is the measured union of the p42 and p27 criteria: p42's version already
    walked the subtree, p27's checked only `values[0]`.
    """
    if _is_literal_true(test):
        return True
    return any(
        isinstance(sub, ast.BoolOp) and isinstance(sub.op, ast.Or)
        and any(_is_literal_true(v) for v in sub.values)
        for sub in ast.walk(test)
    )


def is_constant_truth(test) -> bool:
    """The test is a constant, so its value never depended on anything.

    Catches `assert 1`, `assert 'msg'` and `assert not False` -- truthiness of a
    literal, reached directly or through a `not`. `assert True if X else Y` is
    included: the condition is the literal `True` whenever X holds, and the
    `not` form is the constant `True` again.

    None of these were caught by the p42 or p27 criteria, or by the earlier
    `is_tautology`, and all of them assert nothing.
    """
    if isinstance(test, ast.Constant):
        return True
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return isinstance(test.operand, ast.Constant)
    if isinstance(test, ast.IfExp):
        return _is_literal_true(test.body) or _is_literal_true(test.orelse)
    return False


def is_excluded_middle(test) -> bool:
    """`X or not X` -- always true by excluded middle, with no literal in sight.

    The one shape in the space that no criterion in the repository caught, and
    the one that cannot be caught by looking for the constant `True`: there is
    no constant. Two operands that are each other's negation is the same fact
    about the operator that `or True` is.
    """
    if not isinstance(test, ast.BoolOp) or not isinstance(test.op, ast.Or):
        return False
    if len(test.values) != 2:
        return False
    a, b = test.values
    return (isinstance(b, ast.UnaryOp) and isinstance(b.op, ast.Not)
            and ast.dump(a) == ast.dump(b.operand))


def is_self_comparison(test) -> bool:
    """A comparison whose operand appears on both sides: `X == X`, `X is X`.

    ⚠️ NOT in `DEFAULT_RULES`, and it must not be added to them. It was measured
    to fire on a correct assertion in this repository --
    `test_pipeline_validates_the_schema.py:332`, `sg.schema() is sg.schema()`,
    where the identity of two calls is the point because the function is
    `lru_cache`d. See this module's docstring.
    """
    if not isinstance(test, ast.Compare):
        return False
    operands = [ast.unparse(test.left)] + [ast.unparse(c) for c in test.comparators]
    return len(operands) != len(set(operands))


DEFAULT_RULES = (is_neutered, is_constant_truth, is_excluded_middle)
ALL_RULES = DEFAULT_RULES + (is_self_comparison,)


def offenders(tree, rules=DEFAULT_RULES) -> list[tuple[int, str]]:
    """Every assertion in `tree` that one of `rules` says asserts nothing.

    Returns `(lineno, description)`. A tree is passed in rather than read from
    `__file__` on purpose: that is what lets the guard be exercised against a
    fixture without a test writing to its own source.
    """
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        for rule in rules:
            if rule(node.test):
                name = getattr(rule, '__name__', str(rule))
                found.append((node.lineno, f'{name}: {ast.unparse(node.test)}'))
                break
    return found