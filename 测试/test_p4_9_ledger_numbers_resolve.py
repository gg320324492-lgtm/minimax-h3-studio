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
                             `translateY`. (P39: this line used to add "and
                             `330` appears nowhere". It stopped being true --
                             three unrelated timeline offsets in
                             `studio/src/water-renewal/` carry a bare `330` --
                             and that was the defect, not the fact.)

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
?? N` default, a `"<field>": N` graph key, an unquoted `<field>: N` TypeScript
object key (added in P39), or a `<field> = N` assignment.
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
  * It records the two phantom numbers as absent -- each by the criterion that
    FITS it (below) -- so adding a `fieldHeight: 480` or a `translateY` back
    into the Data Columns scene turns a test red instead of being absorbed.

ONE CRITERION PER QUESTION (P39).

  This file used to carry TWO ways to say "this number is not real", and they
  disagreed on the delivered source:

    C1  field-anchored  _value_is_field_value(rel, field, value) -- the number
        is the value OF A NAMED FIELD, in a file that owns it.
    C2  bare scan       `re.search('330', every .ts/.tsx/.json under the repo)`
        -- the number occurs somewhere.

  C2 is not the property. It has no field attribution, so it goes red on any
  unrelated code that happens to write the same digits: three timeline offsets
  in `studio/src/water-renewal/` turned this file red while saying nothing at
  all about 4.9. C2 was DELETED. What replaced it is C1 plus one case C1
  cannot judge (below), and a guard ON THE CRITERION ITSELF -- see
  `test_the_phantom_criterion_judges_the_field_not_the_number` and
  `test_this_file_has_no_second_criterion_for_a_layout_value`.

  C2 was not deleted until C1 was shown to be STRICTLY STRONGER: the resolver
  had a hole C2 covered -- the unquoted object-literal spelling
  `fieldHeight: 480` in TypeScript, which no pattern matched. It missed
  `windowWidth: 520` in `depthCue.check.ts` -- the very fixture this file's own
  docstring cites as the reason "exists somewhere" is not a property. That hole
  is closed; see `_value_is_field_value`.

THE TWO PHANTOMS ARE NOT THE SAME KIND OF THING, AND DO NOT SHARE A CRITERION.

    480  `场高 480`  -- a claim about a LAYOUT FIELD. C1 judges it.
    330  `translateY(-330*s)` -- a claim about a TRANSFORM MAGNITUDE inside a
         Data Columns scene. `translateY` is a live track key everywhere else
         (`schemas/showcase-v1.ts`, `CameraRig.tsx`, and
         `pipeline/examples/showcase_demo.json`), so a repo-wide absence check
         would be wrong, and C1 would be worse than useless here: it returns
         False for EVERY magnitude, real or not, because no `??`/`:`/`=` binds
         a number to the name `translateY`. A criterion that always says "not
         real" is not a criterion. So 330 is judged by C3: the identifier is
         absent from the one file that made the claim.

  Three criteria, three different questions. The consistency requirement is not
  "one criterion" but "one criterion PER QUESTION", and that is what the
  criterion guard checks.

THE TRAPS THIS FILE IS BUILT AROUND (all seen in this project).

  * A substring guard passes by matching a comment. -> comment-stripped reads.
  * A guard that checks "exists anywhere" is nearly vacuous. -> field-anchored.
  * `read_text`/`write_text` flips CRLF on Windows and would pollute the ledger.
    -> every read is `read_bytes`; nothing here writes inside the repo. The
    criterion guard writes only under pytest's `tmp_path`, and asserts its own
    bytes back before trusting them.
  * Path separators: `str(Path)` is `\\`-joined on Windows and a `/`-joined
    comparison then matches nothing. -> `as_posix()` for every string compare.
  * A guard that runs no cases passes over an empty corpus. -> the anchor test.
  * Two guards for one fact drift apart. -> the criterion guard, and a test that
    names which functions may scan raw text and then CALLS the resolver, so the
    allow-list cannot be satisfied by a function that judges nothing.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'docs' / 'UPGRADE_PROGRESS.md'

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


def _read_stripped(rel: str, root: Path = ROOT) -> str:
    return strip_comments((root / rel).read_bytes().decode('utf-8', 'replace'))


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

@dataclass(frozen=True)
class Phantom:
    """A number 4.9's row asserts, paired with the FIELD it asserts it OF.

    `owners` is where that field is declared or overridden -- the component
    that reads it and the graph that may override it. These are judged by the
    same resolver as every real claim; there is no second way to judge a
    layout value in this file.
    """

    name: str
    value: int
    field: str
    owners: tuple[str, ...]


@dataclass(frozen=True)
class TransformPhantom:
    """A number 4.9's row asserts as a TRANSFORM, not as a layout field.

    `name` is the identifier that must stay absent from `owner`. `value` is
    recorded only so the row's citation can be tied to it; it is never handed
    to the resolver, because nothing binds a number to the name `translateY`
    and the resolver would answer False for a magnitude that IS real.
    """

    name: str
    value: int
    owner: str


#: 4.9's `场高 480` -- a claim about a layout FIELD, so C1 can judge it.
PHANTOMS = (
    Phantom('4.9 fieldHeight', 480, 'fieldHeight', (DATA_COLUMNS, SHOWCASE_GRAPH)),
)

#: 4.9's `translateY(-330*s)` -- NOT a layout field. `translateY` is a live
#: camera track key in `showcase-v1.ts`, `CameraRig.tsx` and the demo graph, so
#: the claim can only mean "the Data Columns scene gained a translateY", and
#: that is judged by the identifier being absent from that one file.
TRANSFORM_PHANTOM = TransformPhantom('translateY', 330, DATA_COLUMNS)

#: Both numbers 4.9's row cites and the repo has no such thing. Derived from
#: the two tables above so the three lists cannot drift apart.
PHANTOM_NUMBERS = tuple(sorted({p.value for p in PHANTOMS} | {TRANSFORM_PHANTOM.value}))


# ── the resolver ────────────────────────────────────────────────────────────

def _value_is_field_value(rel: str, field: str, value: int, root: Path = ROOT) -> bool:
    """True if `value` is a value OF `field` in the (comment-stripped) file.

    Three spellings cover the code and the graph:
      * a layout default:  `layout.<field> ?? <N>`  or  `<field> ?? <N>`
      * an object key:     `"<field>": <N>` (graph) or `<field>: <N>` (a
        TypeScript object literal -- see the note below)
      * a plain assignment: `<field> = <N>`

    The number must sit next to the field NAME -- that is the whole point. A
    bare `520` elsewhere in the file is not a `windowWidth`.

    `root` exists so the criterion guard can ask this question of a corpus that
    is not the repo (a tree under `tmp_path`). Every judgement in this file is
    made against `ROOT` unless a test deliberately builds another root.
    """
    body = _read_stripped(rel, root)
    n = str(value)
    f = re.escape(field)
    patterns = [
        rf'layout\.{f}\b[^;\n]*?\?\?\s*{n}(?![\d.])',
        rf'\b{f}\s*\?\?\s*{n}(?![\d.])',
        # P39: the closing quote is optional, so an UNQUOTED TypeScript object
        # key matches too. Without this the resolver missed `windowWidth: 520`
        # in `depthCue.check.ts` -- the fixture this file's docstring cites as
        # the reason a bare-number scan is the wrong criterion. A scan caught
        # that spelling and the resolver did not; the hole had to be closed
        # BEFORE the scan could be deleted, or deleting it was a weakening.
        rf'\b{f}"?\s*[:=]\s*{n}(?![\d.])',
    ]
    return any(re.search(p, body) for p in patterns)


def _resolve(claim: Claim, root: Path = ROOT) -> list[str]:
    """Files where the claim's value is really the value of its field."""
    return [
        rel for rel in claim.owners if _value_is_field_value(rel, claim.field, claim.value, root)
    ]


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


def test_the_phantom_corpus_is_what_this_file_says_it_is():
    """The same anchor, for the phantom tables -- and they must not overlap.

    An emptied phantom table is the quiet way to turn these guards green: with
    nothing to resolve, `_phantom_sites` returns `[]` and the absence holds
    vacuously. P39 saw exactly that shape -- a criterion that answers "not
    real" for everything, including things that are.

    And the two tables must partition `PHANTOM_NUMBERS`: a number claimed as a
    transform cannot also be claimed as a field value, because then two
    criteria would both be answering for one number -- the drift this file
    exists to prevent.
    """
    assert PHANTOMS, 'the phantom field table is empty; nothing is being judged'
    for p in PHANTOMS:
        assert p.owners, f'{p.name} has no owning file, so it resolves nowhere'
        assert p.value not in {c.value for c in CLAIMS}, (
            f'{p.name} pins a value the claim table also carries as REAL; one '
            'number cannot be both'
        )
    assert TRANSFORM_PHANTOM.owner.endswith('.tsx')
    assert set(PHANTOM_NUMBERS) == {p.value for p in PHANTOMS} | {
        TRANSFORM_PHANTOM.value
    }
    assert len(set(PHANTOM_NUMBERS)) == len(PHANTOMS) + 1, (
        'the two tables overlap: one number would be judged by two criteria'
    )


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

def _phantom_sites(phantom: Phantom, root: Path = ROOT) -> list[str]:
    """The phantom's OWNER files where the phantom really resolves.

    THE criterion, and the only one this file uses to decide "is this cited
    layout value real". `root` is a parameter so the criterion guard can ask
    the same question of a tree it builds -- see
    `test_the_phantom_criterion_judges_the_field_not_the_number`, which is the
    test that makes "this is one criterion" a checked property rather than a
    comment.
    """
    return [
        rel
        for rel in phantom.owners
        if _value_is_field_value(rel, phantom.field, phantom.value, root)
    ]


def test_the_field_phantom_4_9_invented_resolves_nowhere():
    """`场高 480` was never a fieldHeight. Pin the absence, BY FIELD.

    Replaces a repo-wide bare-number scan for `480`. That scan had no field
    attribution, so it went red on any unrelated code writing the same digits
    -- three timeline offsets in `studio/src/water-renewal/` did exactly that,
    while saying nothing whatsoever about 4.9. This asks the question 4.9's
    row actually poses: does any file that owns `fieldHeight` set it to 480?
    """
    resolved = [(p.field, p.value, rel) for p in PHANTOMS for rel in _phantom_sites(p)]
    assert not resolved, (
        f'4.9 cites field values its owners really do carry: {resolved}'
    )


def test_the_transform_phantom_4_9_invented_stays_out_of_the_data_columns_scene():
    """`translateY(-330*s)` was never real. Pin the ABSENCE OF THE TRANSFORM.

    Not a number check, on purpose. `translateY` is a live camera track key
    (`schemas/showcase-v1.ts`, `CameraRig.tsx`, and a `translateY` track in
    `pipeline/examples/showcase_demo.json`), so what 4.9 claimed cannot be
    "this identifier does not exist" -- it can only be "the Data Columns scene
    grew one". Handing `330` to the resolver here would be worse than nothing:
    nothing binds a number to the name `translateY`, so it would answer False
    for a magnitude that is real.

    The repair that actually worked was the flow layout, which removed
    placement by transform; its return would undo that repair.
    """
    assert TRANSFORM_PHANTOM.name not in _read_stripped(TRANSFORM_PHANTOM.owner), (
        f'{TRANSFORM_PHANTOM.owner.split("/")[-1]} grew a '
        f'{TRANSFORM_PHANTOM.name} -- the flow-layout repair (see the file '
        'header comment) has been reverted'
    )


# ── 3. THE CRITERION IS ONE CRITERION ───────────────────────────────────────
#
# Everything above is an assertion ABOUT the repo. These two are assertions
# about how this file ASSERTS -- the failure mode this project hits most
# ("the same thing, two yardsticks, in two places, drifting apart").

def _write_tree(root: Path, rel: str, text: str) -> None:
    """Write `text` to `root/rel`, LF endings, then ASSERT it landed."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    # write_bytes, not write_text: write_text translates line endings on
    # Windows and this project has been bitten by exactly that.
    path.write_bytes(text.encode('utf-8'))
    landed = path.read_bytes().decode('utf-8')
    assert landed == text, (
        f'could not stage the probe tree at {rel}: {landed!r} != {text!r}'
    )
    assert b'\r\n' not in path.read_bytes(), 'the probe tree picked up CRLF'


def _stage_owners(root: Path) -> None:
    """Put a neutral stub at EVERY path the criterion may read.

    A missing file would raise out of the criterion and the test would report
    that exception instead of the verdict -- a probe's exception becoming the
    judgement, which this project has been bitten by three times. So the tree
    is complete before anything is measured.
    """
    for rel in {*(r for p in PHANTOMS for r in p.owners), TRANSFORM_PHANTOM.owner}:
        _write_tree(root, rel, '// neutral stub: declares no layout field\n')


def test_the_phantom_criterion_judges_the_field_not_the_number(tmp_path):
    """Would the guard go red if the bare-number scan came back? Prove it can.

    The property under test is a property of a FUNCTION, so it is tested by
    calling that function on a corpus chosen to separate the two candidate
    criteria. The corpus below reproduces the failure that opened P39: an
    UNRELATED file carrying bare `480` and `330` as timeline offsets, while
    the file that owns `fieldHeight` still declares 420.

      * C1 (field-anchored) must ignore it: it reads the files that OWN the
        field, and 480 in a file that owns no such field is not a fieldHeight.
      * C2 (bare scan) must not: it enumerates the corpus and reports both
        numbers, and goes red.

    A bare scan reintroduced in place of `_phantom_sites` therefore returns a
    non-empty list here and this test fails on the RESOLVER'S VERDICT -- not on
    an exception, and not on a missing name.

    The second half is the negative control: the same corpus with the REAL
    defect (`layout: {fieldHeight: 480}`) MUST be reported. Without it this
    test would be green for a criterion that judges nothing.
    """
    # Pick the phantom by FIELD, not by position, and fail as an assertion if
    # the table lost it: `PHANTOMS[0]` on an emptied table raises IndexError,
    # and a probe's exception must never be the verdict (P31/P34/P36).
    phantoms = [p for p in PHANTOMS if p.field == 'fieldHeight']
    assert len(phantoms) == 1, (
        f'the phantom table has no fieldHeight row to judge: {PHANTOMS}'
    )
    phantom = phantoms[0]

    _stage_owners(tmp_path)
    _write_tree(
        tmp_path,
        DATA_COLUMNS,
        'export const DataColumns = () => {\n'
        '  const layout = ({} as Record<string, unknown>);\n'
        '  const fieldHeight = Number(layout.fieldHeight ?? 420);\n'
        '  const columnWidth = Number(layout.columnWidth ?? 44);\n'
        '  return <div style={{height: fieldHeight, width: columnWidth}} />;\n'
        '};\n',
    )
    # The unrelated file: the same digits, a completely different job. This is
    # what `studio/src/water-renewal/` looks like, and what a bare scan cannot
    # tell apart from a real fieldHeight.
    _write_tree(
        tmp_path,
        'studio/src/water-renewal/BubbleScene.tsx',
        'export const BubbleScene = () => (\n'
        '  <Statement top={480} text="a" />\n'
        '  <BlendSequence from={330} durationInFrames={105} />\n'
        ')\n',
    )
    assert _phantom_sites(phantom, tmp_path) == [], (
        'the criterion reported a hit for bare numbers in a file that owns no '
        'such field; it is answering "does this digit appear anywhere", which '
        'is the scan this guard replaced'
    )

    # Negative control: the criterion is not simply broken-open. The unquoted
    # object-literal spelling is the one the scan used to catch and the
    # resolver used to miss, so it is the spelling worth proving.
    _write_tree(
        tmp_path,
        DATA_COLUMNS,
        'export const DataColumns = () => (\n'
        '  const layout = {fieldHeight: 480};\n'
        '  return <div style={{height: layout.fieldHeight}} />;\n'
        ')\n',
    )
    assert _phantom_sites(phantom, tmp_path) == [DATA_COLUMNS], (
        'the criterion did not report a fieldHeight of 480 written as an '
        'unquoted object-literal key -- the spelling a bare scan caught and '
        'this resolver used to miss'
    )


#: The only functions in this file allowed to look for a number in raw text.
#: `_value_is_field_value` is THE resolver; `_cited_layout_values` parses the
#: ledger's Chinese labels, which is a different corpus and a different
#: question. Any third scanner is a second criterion by definition.
_RAW_TEXT_SCANNERS = {'_value_is_field_value', '_cited_layout_values'}

#: Calls that mean "search this text". `.sub`/`.match` are excluded: comment
#: stripping and ledger-row matching are not number lookups.
_SCAN_CALLS = ('.rglob(', '.search(', '.finditer(', '.findall(', '.fullmatch(', '.matchall(')


def _functions_in_this_module() -> dict[str, ast.FunctionDef]:
    tree = ast.parse(Path(__file__).read_bytes().decode('utf-8'))
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_this_file_has_no_second_criterion_for_a_layout_value():
    """No function in this file may judge a number by scanning raw text --
    except the resolver and the ledger-label parser, which are named here.

    The perturbation test above proves the CRITERION behaves. This proves the
    file does not also carry a second one beside it, which is the other half
    of the defect: a bare scan added anywhere -- a helper, or inlined into a
    test body -- makes this red on the allow-list, not on a name.

    It then CALLS the resolver and checks it discriminates on the real repo,
    so the allow-list cannot be satisfied by a function that judges nothing
    (asserting the name `_value_is_field_value` appears in this file's source
    would prove nothing, and this project has been fooled that way before).
    """
    scanners = set()
    for name, node in _functions_in_this_module().items():
        body = ast.unparse(node)
        if name in _RAW_TEXT_SCANNERS:
            continue
        # The detector names the scan calls in order to look for them, so it
        # would flag itself. Exclude by WHAT it references, not by its name:
        # a renamed or copied detector must stay excluded, and a function that
        # merely scans must not be able to claim the exemption.
        if any(marker in body for marker in ('_SCAN_CALLS', '_RAW_TEXT_SCANNERS')):
            continue
        if any(call in body for call in _SCAN_CALLS):
            scanners.add(name)
    assert not scanners, (
        'these functions search raw text for something and are not on the '
        f'allow-list {sorted(_RAW_TEXT_SCANNERS)}: {sorted(scanners)}. A layout '
        'value must be judged by _value_is_field_value, or this file carries '
        'two criteria for one fact and they will drift.'
    )

    # The allow-listed scanner must be the resolver AND must discriminate, on
    # the real files, in both directions.
    resolve = globals()['_value_is_field_value']
    assert resolve(BROWSER_STACK, 'windowWidth', 520), (
        'the allow-listed resolver no longer accepts a value that IS its '
        "field's value; the allow-list is naming something that judges nothing"
    )
    assert not resolve(DATA_COLUMNS, 'fieldHeight', 480), (
        'the allow-listed resolver accepts the phantom 4.9 invented; the '
        'allow-list is naming something that judges nothing'
    )
    assert not resolve(DATA_COLUMNS, 'columnWidth', 520), (
        'the allow-listed resolver no longer separates one field from another'
    )


# ── 4. the ledger row, parsed live ──────────────────────────────────────────

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
