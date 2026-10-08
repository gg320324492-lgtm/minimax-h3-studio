"""A ledger row that names a LAYOUT VALUE must name one that exists, in the
place that gives it meaning.

WHY THIS FILE EXISTS.

`docs/UPGRADE_PROGRESS.md` row **4.9** is the only row in the ledger that is a
false entry rather than an open task, and it has been false TWICE. The second
time is the one this guard is built around. After the first false "已修" was
overturned, the row was rewritten with a *mechanism*:

    现已真正修复并重渲抽帧确认：间距 250、窗宽 520、translateZ 110；
    Data Columns 柱宽 44、场高 480、标题 `translateY(-330*s)` 上移

Measured against the repo, four of those six numbers resolve to a real layout
value and two do not exist anywhere:

    cited   field            reality
    250     spreadX          a DEFAULT (`BrowserStack.tsx:231`), and the graph
                             overrides it to 300 -- not the value in use
    520     windowWidth      real (graph override, effective)                 OK
    110     spreadZ          a DEFAULT (`BrowserStack.tsx:232`), graph overrides
                             to 150 -- not the value in use
    44      columnWidth      real (`DataColumns.tsx:39` default, effective)   OK
    480     fieldHeight      DOES NOT EXIST. Default is 420
                             (`DataColumns.tsx:38`); no graph sets it
    330     `translateY(-330*s)`  DOES NOT EXIST. `DataColumns.tsx` has no
                             `translateY`, and `330` appears nowhere

THE NARROW PROPERTY THIS GUARD GUARDS.

The two false entries share one shape: **the ledger wrote a number and the repo
has no such thing**. Scanning every number in the ledger would be hundreds of
false positives (timestamps, line numbers, `18.7s`, `0.278`). So the property is
narrowed to what actually went wrong: a number a fix RECORD cites as the value
OF A NAMED FIELD.

And it is narrowed further on purpose. The first version of this guard asked
only "does the number appear anywhere in the repo?", and a mutation that deleted
`windowWidth: 520` from BOTH the component default and the graph **survived**,
because `520` also appears in `depthCue.check.ts`'s fixture. Existing somewhere
is not the property. The property is: **the number is the value of the field it
is cited for.** So each claim names the file that owns the field, and the
resolver checks the number against THAT field in THAT file -- a `layout.<field>
?? N` default, a `"<field>": N` in the graph, or a `<field> = N` assignment.
Every read is comment-stripped, because the owning files carry prose that names
values the code does not use (`DataColumns.tsx`'s header names the OLD `520px`
field height; `render.mjs` names `qa_final.py` in a comment -- P17 was bitten by
exactly that).

WHAT THIS FILE DOES AND DOES NOT ASSERT.

  * It asserts, by RUNNING the resolver over the real files, that each cited
    number is the value of its field, outside comments.
  * It does NOT assert a substring of its own prose. Nothing here can be
    satisfied by its own docstring; the anchor test proves the corpus is
    non-empty and every resolver reads other files.
  * It records the two phantom numbers as absent, so adding a `fieldHeight: 480`
    or a `translateY(-330*s)` later turns a test red instead of being absorbed.

THE TRAPS THIS FILE IS BUILT AROUND (all seen in this project).

  * A substring guard passes by matching a comment. -> comment-stripped reads.
  * A guard that checks "exists anywhere" is nearly vacuous. -> field-anchored.
  * `read_text`/`write_text` flips CRLF on Windows and would pollute the ledger.
    -> every read is `read_bytes`; this file never writes.
  * Path separators: `str(Path)` is `\\`-joined on Windows and a `/`-joined
    comparison then matches nothing. -> `as_posix()` for every string compare.
  * A guard that runs no cases passes over an empty corpus. -> the anchor test.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'docs' / 'UPGRADE_PROGRESS.md'
SRC_ROOT = ROOT / 'studio' / 'src'
PIPELINE = ROOT / 'pipeline'

BROWSER_STACK = 'studio/src/templates/finance-showcase/scenes/BrowserStack.tsx'
DATA_COLUMNS = 'studio/src/templates/finance-showcase/scenes/DataColumns.tsx'
SHOWCASE_GRAPH = 'pipeline/examples/showcase_demo.json'


# ── comment stripping ───────────────────────────────────────────────────────
#
# Crude on purpose: it does not understand string literals, so it can only err
# by REMOVING more text than a real parser would, which can cause a false
# NEGATIVE (a real hit reported absent) -- and a false negative here is visible,
# because the anchor test and the "effective value" test both require hits. What
# it must never do is let a comment satisfy a hit, and it cannot: the text is
# gone before the search.

_TS_BLOCK = re.compile(r'/\*.*?\*/', re.S)
_TS_LINE = re.compile(r'(?m)//[^\n]*')


def strip_comments(text: str) -> str:
    return _TS_LINE.sub('', _TS_BLOCK.sub('', text))


def _read_stripped(rel: str) -> str:
    return strip_comments((ROOT / rel).read_bytes().decode('utf-8', 'replace'))


# ── the claims ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Claim:
    """One layout value a fix record cites, tied to the field it is the value OF.

    `owners` are the repo-relative files that may carry the value: the component
    with a `layout.<field> ?? N` default, and the graph that may override it.
    `effective` says whether THIS number is the one the delivered film uses.
    """

    name: str
    value: int
    field: str
    owners: tuple[str, ...]
    effective: bool
    #: (graph_field, value) the delivered graph actually uses, when not effective.
    effective_override: tuple[str, int] | None


CLAIMS = [
    Claim(
        'browser-stack spreadX default',
        250,
        'spreadX',
        (BROWSER_STACK, SHOWCASE_GRAPH),
        effective=False,
        effective_override=('spreadX', 300),
    ),
    Claim(
        'browser-stack spreadZ default',
        110,
        'spreadZ',
        (BROWSER_STACK, SHOWCASE_GRAPH),
        effective=False,
        effective_override=('spreadZ', 150),
    ),
    Claim(
        'browser-stack windowWidth',
        520,
        'windowWidth',
        (BROWSER_STACK, SHOWCASE_GRAPH),
        effective=True,
        effective_override=None,
    ),
    Claim(
        'data-columns columnWidth',
        44,
        'columnWidth',
        (DATA_COLUMNS, SHOWCASE_GRAPH),
        effective=True,
        effective_override=None,
    ),
    Claim(
        'data-columns fieldHeight default',
        420,
        'fieldHeight',
        (DATA_COLUMNS, SHOWCASE_GRAPH),
        effective=True,
        effective_override=None,
    ),
]

PHANTOM_NUMBERS = [480, 330]


# ── the resolver ────────────────────────────────────────────────────────────

def _value_is_field_value(rel: str, field: str, value: int) -> bool:
    """True if `value` is a value OF `field` in the (comment-stripped) file.

    Three spellings cover the code and the graph:
      * a layout default:  `layout.<field> ?? <N>`  or  `<field> ?? <N>`
      * a JSON graph key:  `"<field>": <N>`
      * a plain assignment: `<field> = <N>`

    The number must sit next to the field NAME -- that is the whole point. A
    bare `520` elsewhere in the file is not a `windowWidth`.
    """
    body = _read_stripped(rel)
    n = str(value)
    f = re.escape(field)
    patterns = [
        rf'layout\.{f}\b[^;\n]*?\?\?\s*{n}(?![\d.])',
        rf'\b{f}\s*\?\?\s*{n}(?![\d.])',
        rf'"{f}"\s*:\s*{n}(?![\d.])',
        rf'\b{f}\s*=\s*{n}(?![\d.])',
    ]
    return any(re.search(p, body) for p in patterns)


def _resolve(claim: Claim) -> list[str]:
    """Files where the claim's value is really the value of its field."""
    return [rel for rel in claim.owners if _value_is_field_value(rel, claim.field, claim.value)]


# ── the anchor ──────────────────────────────────────────────────────────────

def test_the_claim_corpus_is_what_this_file_says_it_is():
    """Without this, every other test could pass over an emptied corpus."""
    assert len(CLAIMS) == 5
    assert {c.field for c in CLAIMS} == {
        'spreadX', 'spreadZ', 'windowWidth', 'columnWidth', 'fieldHeight'
    }
    for c in CLAIMS:
        assert c.value > 0
        assert c.owners, f'{c.name} has no owning file, so it resolves nowhere'
        if c.effective:
            assert c.effective_override is None
        else:
            assert c.effective_override is not None
            assert c.effective_override[1] != c.value


# ── 1. every claim resolves to a real, ATTRIBUTED, non-comment value ─────────

def test_every_cited_layout_value_is_the_value_of_the_field_it_names():
    """THE GUARD. Each cited number must be a value OF ITS FIELD in its owner.

    "Appears somewhere in the repo" is not this test. It was, in the first
    version, and deleting `windowWidth: 520` from both the component and the
    graph left it GREEN, because `520` also lives in a `depthCue.check.ts`
    fixture. The number has to sit next to the field name, in a file that owns
    the field, with comments removed.
    """
    unresolved = []
    for c in CLAIMS:
        if not _resolve(c):
            unresolved.append(
                f'{c.name}: {c.value} is not a value of layout.{c.field} in '
                f'{c.owners}'
            )
    assert not unresolved, (
        'the P4 fix record cites layout values that are not the value of the '
        'field they name (comments excluded):\n  ' + '\n  '.join(unresolved)
    )


def test_the_effective_values_are_graph_overrides_not_just_defaults():
    """A default is not the value the film is made with; the override is.

    4.9 cited `spreadX 250` and `translateZ 110`, both DEFAULTS that
    `pipeline/examples/showcase_demo.json` overrides. The guard therefore has to
    know the graph's number too, or it would bless a number the film never uses.
    """
    for c in CLAIMS:
        if c.effective or c.effective_override is None:
            continue
        gf, gv = c.effective_override
        assert _value_is_field_value(SHOWCASE_GRAPH, gf, gv), (
            f'the delivered graph no longer sets {gf} to {gv}, so the claim table '
            f'({c.name}) is stale'
        )


def test_the_resolver_can_actually_say_no():
    """The predicate must DISCRIMINATE, or the guard is a no-op.

    This is the P16 failure, made into a test. There, the self-check tested a
    COPY of the predicate while the guard inlined its own, so five mutations
    that disabled the guard all survived. Here the same predicate the guard uses
    is fed known-false cases and must return False:

      * a value the repo does not carry for that field (windowWidth 999999);
      * the phantom `480` for `fieldHeight` -- the exact number 4.9 invented;
      * a value that exists in the file but for a DIFFERENT field (520 is real
        for windowWidth; it must not resolve as a `columnWidth`).

    An "always return True" edit to `_value_is_field_value` turns this red, which
    is the point: a guard whose criterion is constant is not a guard.
    """
    assert not _value_is_field_value(BROWSER_STACK, 'windowWidth', 999999), (
        'windowWidth 999999 must not resolve; the predicate returns True for '
        'anything, so the guard proves nothing'
    )
    assert not _value_is_field_value(DATA_COLUMNS, 'fieldHeight', 480), (
        'fieldHeight 480 is the phantom 4.9 invented; it must not resolve'
    )
    assert not _value_is_field_value(DATA_COLUMNS, 'columnWidth', 520), (
        '520 is a windowWidth, not a columnWidth; a value must resolve only for '
        'its own field'
    )
    # ...and it must still say yes where the value IS the field's value.
    assert _value_is_field_value(BROWSER_STACK, 'windowWidth', 520)
    assert _value_is_field_value(DATA_COLUMNS, 'columnWidth', 44)


# ── 2. the phantom numbers stay phantom ─────────────────────────────────────

def test_the_two_numbers_4_9_invented_still_exist_nowhere():
    """`场高 480` and `translateY(-330*s)` were never real. Pin the absence.

    Backwards-looking half: it records that on the delivered source these two
    numbers resolve to nothing at all, in any source or graph file, comments
    included. If a future change adds a `fieldHeight: 480` or a
    `translateY(-330*s)` the ledger pretended existed, this goes red.
    """
    files = sorted(
        [p for p in SRC_ROOT.rglob('*.ts')] + [p for p in SRC_ROOT.rglob('*.tsx')]
        + [p for p in PIPELINE.rglob('*.json')]
    )
    for value in PHANTOM_NUMBERS:
        pattern = re.compile(r'(?<![\d.])' + str(value) + r'(?![\d.])')
        hits = [
            p.relative_to(ROOT).as_posix()
            for p in files
            if pattern.search(p.read_bytes().decode('utf-8', 'replace'))
        ]
        # `480` may legitimately appear ONLY inside `48000` (an audio sample
        # rate) -- the lookahead excludes that, so a hit here is a real 480.
        assert hits == [], f'{value} now appears in: {hits}'

    # And `translateY` must stay out of the Data Columns scene: the ledger's
    # claimed fix was a `translateY` transform, and the repair that actually
    # worked (flow layout, so overlap is unrepresentable) removed placement by
    # transform entirely. Its return would undo the repair.
    body = _read_stripped(DATA_COLUMNS)
    assert 'translateY' not in body, (
        'DataColumns.tsx grew a translateY -- the flow-layout repair (see the '
        'file header comment) has been reverted'
    )


# ── 3. the ledger row, parsed live ──────────────────────────────────────────

_ROW_4_9 = re.compile(r'^\|\s*4\.9\s*\|')

#: The ledger is written in Chinese; a field is named by a label, and the value
#: follows it. Only a number that sits right after one of these labels is a
#: LAYOUT-VALUE CLAIM. Every other number in the cell is prose -- `330→250` and
#: `560→520` describe the FIRST false entry's disproven claims, and a `532b584`
#: is a commit. Treating all of them as claims is the "hundreds of false
#: positives" failure the work order names; the label is what makes a number a
#: claim, and it is the same field-attribution idea the code resolver uses.
_FIELD_LABEL = {
    'spreadX': r'间距',
    'windowWidth': r'窗宽',
    'spreadZ': r'translateZ',
    'columnWidth': r'柱宽',
    'fieldHeight': r'场高',
}


def _ledger_4_9_cell() -> str:
    for line in LEDGER.read_bytes().decode('utf-8').splitlines():
        if _ROW_4_9.match(line):
            return line
    raise AssertionError('the 4.9 row is gone from the ledger -- update this guard')


def _cited_layout_values(cell: str) -> list[tuple[str, int]]:
    """(field, value) pairs the cell cites: a number right after a field label.

    A number with no field label in front of it is not a layout-value claim.
    """
    out = []
    for field, label in _FIELD_LABEL.items():
        # `间距 250` / `窗宽 520` / `translateZ 110` -- label, whitespace, a 2-4
        # digit value NOT followed by an arrow. The negative lookahead is the
        # whole reason this is narrow: the cell also writes `间距 330→250` and
        # `窗宽 560→520`, which describe the FIRST false entry's disproven
        # claims (old->new). That `330` is history, not a value 4.9 asserts, and
        # treating it as a claim is exactly the false positive this guard is
        # supposed to avoid.
        for m in re.finditer(label + r'\s*(\d{2,4})(?!\s*→)(?!\d)', cell):
            out.append((field, int(m.group(1))))
    return out


def test_the_ledger_4_9_row_cites_only_values_this_guard_can_resolve():
    """SKIP until the row is reconciled, then assert.

    The row still carries `场高 480` and `translateY(-330*s)`, and the commander
    owns the ledger (the executor reports, the commander edits). A guard that
    went red here would fail the whole suite on a row the executor is forbidden
    to touch. So this SKIPS, loudly, naming the field/values that do not resolve
    -- and the moment the row is corrected it RUNS and asserts, so the skip
    cannot outlive the defect.
    """
    cell = _ledger_4_9_cell()
    cited = _cited_layout_values(cell)
    assert cited, (
        'the 4.9 row names no layout field this guard can resolve; the guard has '
        'drifted from the row (fields: '
        f'{sorted(c.field for c in CLAIMS)})'
    )

    resolvable = {(c.field, c.value) for c in CLAIMS}
    live_phantoms = [
        (f, v) for f, v in cited if (f, v) not in resolvable and v in set(PHANTOM_NUMBERS)
    ]
    if live_phantoms:
        pytest.skip(
            'the 4.9 row cites a value that resolves to nothing in the repo for its '
            f'field {live_phantoms}; the commander reconciles the row, not the '
            'executor. This asserts as soon as the row stops naming a phantom.'
        )

    unresolved = [
        (f, v) for f, v in cited if (f, v) not in resolvable and 40 <= v <= 9999
    ]
    assert not unresolved, (
        f'4.9 cites values for fields that are not the real value of that field: '
        f'{unresolved}'
    )


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
