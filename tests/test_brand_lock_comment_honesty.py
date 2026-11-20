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
    `BRAND_CONTENT_KEYS = <literal>` must state what the module actually holds;
  * any `showcase-v1.ts:A-B` reference must point at a range that really
    contains one of the locked scene types.

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
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'studio' / 'scripts'))

import locked_fields as lf  # noqa: E402

BRAND_TSX = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'scenes' / 'Brand.tsx'
SCHEMA_TS = ROOT / 'studio' / 'src' / 'schemas' / 'showcase-v1.ts'
LOCKED_FIELDS_PY = ROOT / 'studio' / 'scripts' / 'locked_fields.py'


# ── reading the source under test ──────────────────────────────────────────

def comment_blocks(src: str, path: Path | None = None) -> list[str]:
    """Every block and line comment in a source file, each as one string.

    A block is returned with its `*` continuation prefixes stripped and its
    lines joined, because a claim is allowed to wrap mid-literal — the one this
    file was written for does: `LOCKED_SCENE_TYPES = frozenset(` and
    `{'logo', 'outro'})` are on different lines.

    Python is read through `tokenize` rather than a `#` regex, because a `#`
    inside a string literal is not a comment and this file is about not being
    fooled by text that merely looks like something. A regex version of this
    function found no comments at all in `locked_fields.py` and made the
    citation guard below fail for the wrong reason — which is at least louder
    than passing for the right one.
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


# ── line references, the second way that comment rotted ────────────────────

def test_a_showcase_v1_line_reference_points_at_a_locked_scene_type():
    """`showcase-v1.ts:36` used to be cited for the `logo` enum entry.

    `logo` is at line 82 and `outro` at 83; line 36 is a paragraph about Zod
    strictness. The reference was presumably true once and was not updated when
    P12 grew the file — the same failure as the value claims above, in a
    different notation. Which types must appear is derived from the lock, not
    written here.
    """
    schema = SCHEMA_TS.read_text(encoding='utf-8').splitlines()
    refs: list[tuple[int, int]] = []
    for block in comment_blocks(BRAND_TSX.read_text(encoding='utf-8'), BRAND_TSX):
        for m in re.finditer(r'showcase-v1\.ts:(\d+)(?:-(\d+))?', block):
            lo = int(m.group(1))
            refs.append((lo, int(m.group(2)) if m.group(2) else lo))

    assert refs, (
        'no showcase-v1.ts line reference left in Brand.tsx. That is legitimate '
        'if the comment was rewritten, but the line references are no longer '
        'being checked and this guard should be revisited, not left to rot.'
    )

    wanted = frozenset(lf.LOCKED_SCENE_TYPES)
    bogus = [r for r in refs
             if not wanted & set(re.findall(r"'([^']*)'", '\n'.join(schema[r[0] - 1:r[1]])))]
    assert not bogus, (
        f'{BRAND_TSX.name} cites showcase-v1.ts line(s) {bogus} for the locked '
        f'scene type(s) {sorted(wanted)}, but those lines contain none of them. '
        'An unmaintained line reference sends a reader to the wrong code and '
        'they will not always notice — that is the whole point of this file.'
    )


# ── the coupling that punishes editing a heavily-cited file ────────────────

def _is_comment_line(line: str) -> bool:
    s = line.strip()
    return not s or s.startswith(('//', '*', '/*'))


def test_comments_elsewhere_that_cite_brand_tsx_by_line_still_land_on_code():
    """Growing this file's comment must not silently break citations INTO it.

    `locked_fields.py` cites Brand.tsx by line number eight times — `Brand.tsx:93`
    is `{name}`, `:156-157` is Outro's `c.name`/`c.tagline` — and those numbers
    are only true as long as Brand.tsx keeps its length. Rewriting a comment
    block here added 35 lines and pushed every one of those citations into the
    middle of the new comment, where they still "resolve" to text and still read
    as a confident claim. Nothing failed.

    The check is deliberately weak — a cited line must not be blank or a
    comment — because the alternative is guessing what a citation was *meant*
    to point at. It cannot catch every wrong line; it catches the common one,
    which is a file that moved under a citation that was right yesterday.

    A citation to a comment line is legal in principle (several point at
    `locked_fields.py`'s own ruling notes), so if one appears here it will need
    an exemption rather than a quieter assertion.
    """
    cited: list[tuple[int, int]] = []
    for block in comment_blocks(LOCKED_FIELDS_PY.read_text(encoding='utf-8'), LOCKED_FIELDS_PY):
        for m in re.finditer(r'Brand\.tsx:(\d+)(?:-(\d+))?', block):
            lo = int(m.group(1))
            cited.append((lo, int(m.group(2)) if m.group(2) else lo))

    assert cited, (
        'no Brand.tsx line citation found in locked_fields.py. Either the '
        'citations were removed — which is fine — or the notation changed and '
        'this guard is no longer checking anything.'
    )

    lines = BRAND_TSX.read_text(encoding='utf-8').splitlines()
    landed_on_comment = [(lo, hi) for lo, hi in cited
                         if any(_is_comment_line(l) for l in lines[lo - 1:hi])]

    assert not landed_on_comment, (
        f'locked_fields.py cites {BRAND_TSX.name} at line(s) {landed_on_comment}, '
        'and those lines are blank or comments — the file has moved under the '
        'citation. Editing a comment here changes the line numbers eight '
        'citations depend on; keep this file the same length, or re-derive them '
        f'in {LOCKED_FIELDS_PY.name} at the same time.'
    )
