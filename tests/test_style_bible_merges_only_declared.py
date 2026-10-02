"""Every section `styleBible.tsx` merges must be DECLARED or ANNOTATED (P12).

THE DEFECT THIS EXISTS FOR — AND IT IS THE INVERSE OF P11's.

`StyleBibleSchema` is an OPEN `z.object`. zod's default for an undeclared key
is to STRIP it, not to reject it, so this:

    ShowcaseSchema.safeParse({style_bible: {radius: {card: 4}}})
    // -> { success: true, data: { style_bible: {} } }

passes validation, throws no warning, exits 0 — and the value is gone. The
resolver then merges a default that looks identical to a value the graph
chose. From the renderer's side the `StyleBible` object is FULLY POPULATED.
From the author's side the document validated. Nothing anywhere is wrong-looking,
and nothing anywhere is right.

Two guards in this suite look at the same key and are NOT interchangeable:

    test_undeclared_field_reads.py        (P11)  "the schema strips a field
                                             something READS"  -- fed, not eaten
    this file                            (P12)  "the schema strips a field
                                             that something READS"  -- read, not fed
    test_style_bible_no_dumb_declarations.py (P12) "the graph DECLARES a field
                                             nothing reads"      -- declared, unread

Read that table carefully, because the middle and right columns are the pair
this project confuses most often. P11's `audioLanguage` and P12's `radius` are
the SAME KEY from opposite ends:

    audioLanguage : DECLARED in the schema, merged by NOTHING, read by nothing.
                    The graph can say it; the film does not change.
                    Fix: add a consumer, or delete the declaration.
    radius        : NOT declared, merged by the resolver, read by KpiHero:143
                    and BrowserStack:159. The film reads a value that the graph
                    can never author. safeParse says true.
                    Fix: declare it, or delete the merge.

Both are silent. Neither is found by the other. A suite carrying only one of
them leaves half the failure family unguarded, and this project has already
paid for that (the `audio` finding in P11 and the four stripped sections in
P12 were found in DIFFERENT passes, months apart, by different mechanisms).

WHAT THIS GUARD PROVES, AND WHAT IT DOES NOT.

    Proven:  every style_bible section that `resolveStyleBible` merges is
             reachable from a graph — either because `StyleBibleSchema`
             declares that key, or because the merge carries an explicit
             `not-graph-controlled` marker saying the author has decided the
             graph must NOT set it.
    NOT proven: that the schema and the resolver agree about SHAPE (radius is
             numbers, depthCue is a list) — `mergeList`/`mergeSection` filter
             by the default's own keys, so a shape mismatch degrades to a
             no-op rather than an error. That is a separate hole and it is
             recorded, not guarded, in docs/STYLE_BIBLE_STRIPPED_SECTIONS.md.
    NOT proven: anything at RUNTIME. This is a static derivation. The zod
             behaviour that makes the defect possible is proven separately, by
             running the real parser, in
             test_style_bible_no_dumb_declarations.py::test_the_parser_really_drops_an_undeclared_key.

WHY THIS IS A SET DIFFERENCE AND NOT A TEXT ASSERTION.

`assert 'radius' in schema_text` is the exact shape of guard this project has
been fooled by repeatedly — four times, catalogued in
`test_undeclared_field_reads.py`. Those failures were text assertions reading
a comment about the bug they were written for. This one would fail a second
way, which is worse: after P12 declared `radius`, the string `radius` appears in
showcase-v1.ts ANYWAY, inside the docstring explaining that it used to be
stripped. A text assertion would now pass for a schema that has been reverted,
and would have passed before the fix for the wrong reason. So nothing here
looks for a name in a file. Both sides are PARSED — the zod literal is read as
a key set, the resolver's merges are read as a binding map — and compared as
sets. Deleting the declaration breaks the guard even though the word survives.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import style_bible_consumption as sbc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STYLE_BIBLE_TSX = (
    ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'design'
    / 'styleBible.tsx')
SCHEMA_TS = ROOT / 'studio' / 'src' / 'schemas' / 'showcase-v1.ts'


# ── the annotation channel ─────────────────────────────────────────────────

#: A merge that carries this marker is exempt from the schema-declaration rule.
#:
#: The exemption is a MARKER IN THE RESOLVER, not a list in this file. A list
#: here would be the same defect one level down: a hand-maintained roster that
#: says "these are the allowed exceptions" and which nothing forces the code to
#: agree with — rename a merge and the roster keeps vouching for a section
#: that no longer exists. Putting the marker on the line it excuses means the
#: exemption is deleted by editing the thing it exempts, so the two cannot
#: drift apart.
MARKER = 'not-graph-controlled'

_MARKER_RE = re.compile(
    r'//[^\n]*%s[^\n]*' % re.escape(MARKER))


def annotated_sections() -> dict[str, str]:
    """Sections whose merge line in `styleBible.tsx` carries the marker.

    Returns `section -> the marker comment verbatim`, so a failure can print
    what the exemption claimed rather than just that one existed.
    """
    text = STYLE_BIBLE_TSX.read_text(encoding='utf-8')
    lines = text.split('\n')
    out: dict[str, str] = {}
    for i, line in enumerate(lines):
        if MARKER not in line:
            continue
        # the marker excuses the merge on the SAME or the NEXT non-comment line
        for j in (i, i + 1):
            if j >= len(lines):
                break
            target = lines[j]
            m = re.search(r"""section\('(\w+)'\)""", target)
            if m:
                out[m.group(1)] = line.strip().lstrip('/').strip()
                break
    return out


# ── 1. the guard can see at all ────────────────────────────────────────────

def test_both_sides_of_the_comparison_parse():
    """A difference computed from two empty sets is empty, and always agrees.

    This is the single most important test in the file. Every assertion below
    is `assert not (resolved - declared)`. If either parse silently returns
    nothing — because a refactor reshaped `z.object` or renamed `merge*` — the
    difference is empty and every guard below passes forever while proving
    nothing. That is not a hypothetical: this suite's own helper module was
    rewritten once already this project and the parser is regex-based for the
    reason that it must run without node.

    So the emptiness is asserted, and so is the presence of the specific keys
    the comparison turns on.
    """
    declared = sbc.declared_style_bible_keys()
    merged = sbc.resolver_bindings()

    assert declared, (
        'no StyleBibleSchema key parsed. The comparison in this file is over '
        'two sets; if one is empty every assertion below is vacuously true.')
    assert merged, (
        'no resolver binding parsed. Same vacuity, other side: nothing in '
        'styleBible.tsx was recognised as a merge.')

    # The keys the ruling in docs/STYLE_BIBLE_STRIPPED_SECTIONS.md turned on.
    # If these stop being parsed the guard has gone blind and would report
    # "everything is declared" for the wrong reason.
    for key in ('palette', 'typography', 'spacing', 'radius', 'shadow',
                'depthCue', 'cameraLanguage', 'motionLanguage'):
        assert key in declared, f'schema parser lost {key!r}: {sorted(declared)}'
        assert key in merged, f'resolver parser lost {key!r}: {sorted(merged)}'


# ── 2. the verdict ─────────────────────────────────────────────────────────

def test_every_merged_section_is_declared_or_annotated():
    """THE GUARD.

    The difference between what the resolver merges and what the schema
    declares, minus the sections explicitly marked `not-graph-controlled`,
    must be EMPTY.

    Before this file existed the difference was exactly:
        {radius, shadow, depth, depthCue}
    Four sections that were merged, consumed by scenes, and unreachable from
    any graph — while every parse of every graph reported success.
    """
    declared = sbc.declared_style_bible_keys()
    merged = sbc.resolver_bindings()
    excused = annotated_sections()

    undeclared = sorted(set(merged) - declared - set(excused))
    assert not undeclared, (
        'styleBible.tsx merges section(s) that no graph can feed:\n  ' +
        '\n  '.join(
            f'{k}: merged at design/styleBible.tsx, but StyleBibleSchema does '
            f'not declare {k!r} — zod strips it and safeParse still returns '
            f'success=true, so a scene reads the default while a graph author '
            f'reads a clean validation'
            for k in undeclared) +
        f'\n  declared: {sorted(declared)}'
        f'\n  merged:   {sorted(merged)}'
        f'\n  annotated: {sorted(excused)}')


def test_no_merged_section_lost_its_schema_declaration():
    """The other half of the difference, and the one a one-sided guard misses.

    Deleting a declaration from `StyleBibleSchema` while leaving the merge in
    `styleBible.tsx` produces the identical user-visible symptom — the value
    is stripped, the default is used, validation passes — but it is a
    DIFFERENT edit, and a guard written only as "every merge is declared" is
    satisfied by simply deleting the merge alongside the declaration.

    So this asserts the overlap is not merely "large enough": every section
    the resolver merges that has a consumer must actually be declared. It is
    the check that catches the mutation where someone removes a key from the
    schema and does not notice, because nothing else in the renderer changed.

    A merged section that `useDesign()` does not republish is NOT this
    assertion's business — that is `bound-but-not-exported`, the P11-direction
    defect, and it has its own guard. It used to raise KeyError here, which
    meant that under mutation A this file died on an EXCEPTION rather than on
    a statement about the defect. A guard that goes red for a reason other than
    the one it is guarding is not evidence of anything, so the unexported case
    is skipped explicitly and named in the report.
    """
    declared = sbc.declared_style_bible_keys()
    merged = sbc.resolver_bindings()
    exports = sbc.design_exports()

    unexported = sorted(k for k in merged if merged[k] not in exports)
    consumed = sorted(k for k in merged
                      if merged[k] in exports and sbc.consumers_of(exports[merged[k]]))
    lost = sorted(set(consumed) - declared)
    assert not lost, (
        'a section that scenes CONSUME lost its schema declaration:\n  ' +
        '\n  '.join(
            f'{k}: scenes read useDesign().{exports[merged[k]]}'
            f' (consumed at {", ".join(sbc.consumers_of(exports[merged[k]]))}), '
            f'but StyleBibleSchema no longer declares {k!r} — the graph value '
            f'will be stripped and the scene will silently fall back to the '
            f'default'
            for k in lost) +
        f'\n  (merged but not exported by useDesign(), out of scope here: '
        f'{unexported})')


def test_the_annotation_channel_is_not_becoming_a_dumping_ground():
    """An exemption that nothing constrains is a hole with a comment on it.

    `not-graph-controlled` exists so a section can be merged WITHOUT being
    graph-settable, deliberately. That is a legitimate verdict (ruling C in
    docs/STYLE_BIBLE_STRIPPED_SECTIONS.md) — but only if it stays rare. If the
    marker is used freely the guard above is satisfied by annotation instead of
    declaration, and the defect returns wearing a different hat.

    So the exemptions are pinned to a known, empty set. Not zero because the
    option must not be used — because TODAY the correct verdict for all four
    sections was A or B, and a marker appearing at all means someone has taken
    a decision this file has not been told about. Change it here, in the same
    commit that adds the marker, with the reasoning recorded.
    """
    excused = annotated_sections()
    assert excused == {}, (
        'styleBible.tsx marks section(s) as deliberately not graph-controlled: '
        f'{excused}. That is a valid verdict (ruling C) but it is a decision '
        'that belongs in docs/STYLE_BIBLE_STRIPPED_SECTIONS.md with its '
        'reasoning, and in the commit that adds the marker. Update the set '
        'below at the same time.')


def test_depth_is_gone_and_stays_gone():
    """Pinning ruling B.

    `depth` had a merge line, a `StyleBible` field, a `useDesign()` export and
    a `DEPTH` table in tokens.ts. The table stays; the graph-facing plumbing
    went, because it had zero consumers and `b.depth` could not exist. This
    asserts the plumbing is gone WITHOUT asserting the table is gone — the
    table is a token, and deleting a token is a larger call than this one.
    """
    src = STYLE_BIBLE_TSX.read_text(encoding='utf-8')
    stripped = sbc._strip_comments(src)
    assert 'b.depth' not in stripped, (
        'styleBible.tsx merges b.depth again. If DEPTH gained a consumer, '
        'that is worth a real ruling — do not restore the line quietly.')
    assert not re.search(r'^\s*DEPTH:\s*s\.', stripped, re.M), (
        'useDesign() republishes DEPTH again with no consumer to read it')
    # the token table itself must survive: this ruling removed a graph-facing
    # binding, not an asset.
    tokens = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' \
        / 'design' / 'tokens.ts'
    assert 'export const DEPTH = {' in tokens.read_text(encoding='utf-8'), (
        'the DEPTH table in tokens.ts is gone. Ruling B removed the graph '
        'plumbing only; deleting a token is a separate decision.')


# ── 3. mutations: the guard must be able to go red ─────────────────────────
#
# Both mutations below follow the work order's protocol: inject, ASSERT THE
# MUTATION IS IN THE FILE, re-derive, then restore. Two of this project's
# earlier guards reported "the mutation was caught" for a mutation that had
# never been written to disk — the number they printed was unrelated to the
# change. So the landing assertion comes first and is not optional.

def test_mutation_add_an_undeclared_merge_is_caught():
    """MUTATION A — the work order's first: add a merge with no declaration.

    Adds a `bleed` section to `resolveInvariant`, exactly the shape of the
    original defect, and requires the guard to go red for THAT reason. A real
    `b.bleed` reaching the merge is asserted first: without it this test would
    pass on a resolver that simply failed to parse the new line, which would
    be the guard going blind rather than catching anything.
    """
    assert 'bleed' not in sbc.declared_style_bible_keys()
    assert 'bleed' not in sbc.resolver_bindings()

    anchor = b'  motion: mergeSection({...MOTION} as unknown as Record<string, unknown>, b.motionLanguage),\r\n'
    body = STYLE_BIBLE_TSX.read_bytes()
    assert anchor in body, (
        'the mutation anchor is gone — styleBible.tsx was reshaped. Update '
        'this mutation rather than reading the miss as a pass.')

    injected = b'  bleed: mergeSection({bleed: 0} as Record<string, unknown>, b.bleed),\r\n'
    try:
        STYLE_BIBLE_TSX.write_bytes(body.replace(anchor, anchor + injected, 1))
        landed = STYLE_BIBLE_TSX.read_bytes()
        assert injected in landed, 'THE MUTATION DID NOT LAND — stop and check the write'

        bindings = sbc.resolver_bindings()
        assert 'bleed' in bindings, (
            f'the mutation is on disk but the resolver parser did not see it: '
            f'{sorted(bindings)}. The guard below would pass vacuously.')

        declared = sbc.declared_style_bible_keys()
        offenders = sorted(set(bindings) - declared - set(annotated_sections()))
        assert offenders == ['bleed'], (
            f'expected the guard to flag exactly [bleed], got {offenders}')
    finally:
        STYLE_BIBLE_TSX.write_bytes(body)
    assert STYLE_BIBLE_TSX.read_bytes() == body, 'restore failed'


def test_mutation_remove_a_declared_and_consumed_key_is_caught():
    """MUTATION B — the work order's second: drop a declared, consumed key.

    Removes `spacing` from `StyleBibleSchema`, leaving the merge, the
    `StyleBible` field and the `useDesign()` export untouched. This is the
    shape a careless schema edit takes, and it is the one the
    every-merge-is-declared assertion does NOT catch on its own: the merge is
    still there, so the forward direction still looks fine. Only noticing that
    a consumed section lost its declaration catches it.

    `spacing` is used rather than `radius` so the mutation cannot be confused
    with the P12 change under test.

    THE ANCHOR IS INDENTATION-AGNOSTIC, and that is a fix rather than a style
    preference. This used to delete the line by its exact two-space prefix, which
    was correct while `StyleBibleSchema` was a one-line `z.object({...})`. P12
    wrapped the object to attach `.strict()`, the keys moved to four spaces, and
    the same `str.replace` then removed only TWO leading spaces: the `spacing`
    line vanished as intended, the following key was left at six, and the parser
    — which matched keys at a fixed width — stopped seeing `radius`. The
    mutation then reported `radius` as an undeclared section and this test went
    red on a phantom of its own making. Matching up to the key name instead
    makes the mutation independent of how the object happens to be indented.
    """
    assert sbc.declared_style_bible_keys().__contains__('spacing')
    assert sbc.reachability('spacing')[0] == 'reachable'

    body = SCHEMA_TS.read_bytes()
    needle = re.compile(rb'\r?\n[ \t]+spacing: z\.record\(z\.string\(\), '
                        rb'z\.unknown\(\)\)\.optional\(\),')
    hits = needle.findall(body)
    assert len(hits) == 1, (
        f'the mutation anchor matched {len(hits)} times, expected 1. '
        'showcase-v1.ts may not be CRLF, or the key was renamed. Update the '
        'mutation; do not read the miss as a pass.')
    old = hits[0]
    new = needle.sub(b'', body, count=1)
    assert new != body, 'the mutation did not land'
    try:
        SCHEMA_TS.write_bytes(new)
        landed = SCHEMA_TS.read_bytes()
        assert old not in landed, 'THE MUTATION DID NOT LAND — stop and check the write'

        assert 'spacing' not in sbc.declared_style_bible_keys(), (
            'the declaration is still parsed as present; the schema parser and '
            'the file have diverged, so this test proves nothing.')

        # the forward guard alone does NOT fire, which is why the reverse
        # assertion in test_no_merged_section_lost_its_schema_declaration
        # exists at all.
        bindings = sbc.resolver_bindings()
        assert 'spacing' in bindings, 'the merge should be untouched by this mutation'

        consumed = {k for k in bindings
                    if bindings[k] in sbc.design_exports()
                    and sbc.consumers_of(sbc.design_exports()[bindings[k]])}
        lost = sorted(consumed & set(bindings) - sbc.declared_style_bible_keys())
        assert lost == ['spacing'], (
            f'expected exactly [spacing] to be reported as lost, got {lost}')
    finally:
        SCHEMA_TS.write_bytes(body)
    assert SCHEMA_TS.read_bytes() == body, 'restore failed'


# ── 4. the whole surface, pinned ───────────────────────────────────────────

def test_the_full_merged_set_is_what_the_ruling_says_it_is():
    """Pins the set, so an added or removed merge is a visible diff.

    A guard that only asserts a difference is EMPTY will happily accept a
    section that was deleted along with its consumer. Pinning the set means the
    list of merged sections has to be edited deliberately.
    """
    assert set(sbc.resolver_bindings()) == {
        'typography', 'spacing', 'radius', 'motionLanguage', 'cameraLanguage',
        'palette', 'shadow', 'depthCue',
    }, sorted(sbc.resolver_bindings())


def test_the_declared_set_is_what_the_two_mirrors_agree_on():
    """The zod side and the JSON Schema side must declare the same ten keys.

    The two mirrors are two spellings of one contract; a key added to one and
    not the other means a graph is accepted by one validator and silently
    mishandled by the other. `test_showcase_schema_parity.py` guards the
    mirrors generally — this pins the specific count, so adding an eleventh key
    has to be an edit in three files rather than a diff nobody reads.
    """
    import json
    js = ROOT / 'pipeline' / 'schemas' / 'showcase-v1.schema.json'
    doc = json.loads(js.read_text(encoding='utf-8'))
    mirror = set(doc['definitions']['StyleBible']['properties'])
    zod = sbc.declared_style_bible_keys()

    assert zod == mirror, (
        f'the mirrors declare different style_bible keys — zod only: '
        f'{sorted(zod - mirror)}; JSON Schema only: {sorted(mirror - zod)}')
    assert len(zod) == 10, sorted(zod)


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))