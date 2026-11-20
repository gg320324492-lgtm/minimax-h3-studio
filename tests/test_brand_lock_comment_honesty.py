"""A comment that states a constant's value must state the value the code has.

THE FAILURE THIS EXISTS FOR. `Brand.tsx` carried a header comment saying
`LOCKED_SCENE_TYPES = frozenset({'logo'})`, "The lock itself is untouched", and
"`tests/test_locked_fields.py` still pins it". All three were TRUE when P26
wrote them. P30 then wired the lock into `diff_locked`, P31 added `outro` and
`tagline`, and P30 rewrote that test's guard from a constant pin into a
behavioural one. Nothing edited the comment. So it described a world that had
stopped existing while reading, to anyone who had not memorised the history, as
the present tense — which is how it was written.

This is not "who got it wrong". It is the same failure as the 4.9 ledger entries:
a record that did not follow the ruling. So the fix is not careful wording, it
is a guard that would have gone red.

WHAT IS AND IS NOT GUARDED HERE, and why the line is drawn narrowly.

Guarded, in this one file:

  * any comment that states `LOCKED_SCENE_TYPES = <literal>` or
    `BRAND_CONTENT_KEYS = <literal>` must state what the module actually holds.

Not guarded, deliberately: every other comment in the repository. Timestamps,
"this bug happened in P9", changelog prose and historical asides are all legal
and mostly still true; a guard over them would drown in false positives and get
switched off, which is worse than not having one. This file guards the one
narrow property that actually bit.

THE CRITERION IS DERIVED, NEVER HARD-CODED.

The rule above reads `lf.LOCKED_SCENE_TYPES` and `lf.BRAND_CONTENT_KEYS` at test
time. The expected values appear nowhere in this file. That matters because the
failure being guarded is precisely a constant changing without anyone updating a
record — a guard that asserted "the comment says {'logo', 'outro'}" AND "the
constant is {'logo', 'outro'}" would have stayed green through both P30 and P31
while asserting two copies of the same lie. Here the constant is read, and the
comment is measured against it.

`test_the_criterion_can_still_say_no` is the other half. A guard whose predicate
was edited to always agree is green forever and protects nothing, so the
predicate is exercised against the ORIGINAL P26 text — the exact comment this
file was written for — and is required to reject it.

2026-11-21 裁剪：本文件原有 5 例，其中 2 例以「行号引用落点在仓库文件的第几行」为
断言对象（`test_a_showcase_v1_line_reference_points_at_a_locked_scene_type`、
`test_comments_elsewhere_that_cite_brand_tsx_by_line_still_land_on_code`），属
账本类，按测试甄别报告（out/工具/测试甄别.md）方案二删除。保留的 3 例：2 例守卫
元测试（guard 仍在岗、criterion 仍能说 no）与 1 例诚实性检查本身。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'studio' / 'scripts'))

import locked_fields as lf  # noqa: E402

BRAND_TSX = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'scenes' / 'Brand.tsx'


# ── reading the source under test ──────────────────────────────────────────

def comment_blocks(src: str, path: Path | None = None) -> list[str]:
    """Every block and line comment in a source file, each as one string.

    A block is returned with its `*` continuation prefixes stripped and its
    lines joined, because a claim is allowed to wrap mid-literal — the one this
    file was written for does: `LOCKED_SCENE_TYPES = frozenset(` and
    `{'logo', 'outro'})` are on different lines.

    Python is read through `tokenize` rather than a `#` regex, because a `#`
    inside a string literal is not a comment and this file is about not being
    fooled by text that merely looks like something.
    """
    if path is not None and path.suffix == '.py':
        import io
        import tokenize
        out: list[str] = []
        try:
            for tok in tokenize.generate_tokens(io.StringIO(src).readline):
                if tok.type == tokenize.COMMENT:
                    out.append(tok.string.lstrip('#').strip())
        except (tokenize.TokenError, IndentationError, SyntaxError):
            return []
        return out

    out = []
    for m in re.finditer(r'/\*.*?\*/', src, re.S):
        body = m.group(0).splitlines()[1:-1] if m.group(0).startswith('/*') else []
        lines = [l.strip().lstrip('*').strip() for l in body]
        out.append(' '.join(l for l in lines if l))
    for line in src.splitlines():
        s = line.strip()
        if s.startswith('//'):
            out.append(s[2:].strip())
    return out


def _quoted(s: str) -> frozenset[str]:
    return frozenset(re.findall(r"'([^']*)'", s))


def claimed_literal(block: str, name: str) -> str | None:
    """The literal a comment assigns to `name`, or None if it assigns none.

    Only a parenthesised literal counts. A comment that merely NAMES the
    constant makes no claim about its value and is not this guard's business —
    over-reaching here is how a text guard turns into a false-positive machine.
    """
    m = re.search(re.escape(name) + r'\s*=\s*((?:frozenset)?\([^)]*\))', block)
    return m.group(1) if m else None


def claims_in(block: str) -> dict[str, frozenset[str]]:
    """Constants whose value `block` states, mapped to what it says they are."""
    out: dict[str, frozenset[str]] = {}
    for name in ('LOCKED_SCENE_TYPES', 'BRAND_CONTENT_KEYS'):
        lit = claimed_literal(block, name)
        if lit is not None:
            out[name] = _quoted(lit[lit.index('(') + 1:lit.rindex(')')])
    return out


def claim_is_true(block: str) -> bool:
    """THE CRITERION. Every value `block` states agrees with the module.

    Reads the constants out of `locked_fields` rather than comparing against
    literals written here, so the expected value moves when a ruling moves.
    """
    for name, claimed in claims_in(block).items():
        actual = frozenset(getattr(lf, name))
        if claimed != actual:
            return False
    return True


# ── the property ───────────────────────────────────────────────────────────

def test_the_brand_lock_comment_states_what_the_lock_actually_holds():
    """The header comment's claims about the two constants must be true now."""
    blocks = comment_blocks(BRAND_TSX.read_text(encoding='utf-8'), BRAND_TSX)

    wrong = [(name, sorted(claimed), sorted(frozenset(getattr(lf, name))))
             for block in blocks
             for name, claimed in claims_in(block).items()
             if claimed != frozenset(getattr(lf, name))]

    assert not wrong, (
        'a comment in Brand.tsx states a value the code does not hold:\n'
        + '\n'.join(f'  {n}: comment says {c}, code holds {a}' for n, c, a in wrong)
        + '\nThis is the failure P30 and P31 caused by accident: the ruling moved, '
          'the record did not. Update the comment to the current value — do not '
          'change the lock to match the comment.'
    )


def test_the_comment_actually_makes_the_claim_this_guard_checks():
    """Close the other direction: delete the comment and the guard must notice.

    `claim_is_true` is vacuously true of a comment that asserts nothing, so
    removal has to be a separate failure. Without this, the whole file could be
    gutted and stay green.
    """
    blocks = comment_blocks(BRAND_TSX.read_text(encoding='utf-8'), BRAND_TSX)
    claimed = {name for block in blocks for name in claims_in(block)}
    assert {'LOCKED_SCENE_TYPES', 'BRAND_CONTENT_KEYS'} <= claimed, (
        f'Brand.tsx comments state values for {sorted(claimed) or "nothing"}; this '
        'guard checks exactly two constants and now checks nothing. Either the '
        'header comment lost its claim, or it was reworded into a form the reader '
        'in _claimed_literal no longer recognises — both are worth knowing about.'
    )


def test_the_criterion_can_still_say_no():
    """The predicate must reject the comment this file was written for.

    A criterion edited to always agree is green forever and protects nothing,
    and nothing else in this file would notice. The text below is the ORIGINAL
    P26 comment, verbatim, so this also proves the predicate is not a dead
    branch that only ever sees today's text.
    """
    stale = (
        '`studio/scripts/locked_fields.py` carries `LOCKED_SCENE_TYPES = '
        'frozenset({\'logo\'})`, and its comment says why. The lock itself is '
        'untouched; `tests/test_locked_fields.py` still pins it.'
    )
    assert claims_in(stale)['LOCKED_SCENE_TYPES'] == {'logo'}, (
        'the fixture no longer parses the way the stale comment is written; the '
        'criterion is being tested against a string it cannot see'
    )
    assert not claim_is_true(stale), (
        'claim_is_true accepted the pre-P31 comment saying only {"logo"} while '
        'locked_fields.py holds {"logo", "outro"}. The criterion cannot fail, so '
        'the guard it powers cannot guard.'
    )


if __name__ == '__main__':
    raise SystemExit(__import__('pytest').main([__file__, '-q']))
