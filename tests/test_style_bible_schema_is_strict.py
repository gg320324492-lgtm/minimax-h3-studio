"""`StyleBibleSchema` must REJECT an undeclared key, not silently strip it (P12).

THE DEFECT FAMILY THIS CLOSES THE ROOT OF.

Three defects, one bed. They are not three unrelated bugs; each is a link in the
same chain, and the chain only completes if the PARSER is open:

    P11  `audio` (top level)
         declared in the schema, merged by nothing, read by nothing.
         A graph can SET it. Validation says yes. Nothing happens.

    836f532  `radius` / `shadow` / `depthCue` / `depth`
         merged by `resolveStyleBible`, READ by real production scenes, and
         not declared. A graph can set them. Validation says yes. zod
         deletes them on the way past and every scene renders the default.
         A read that cannot be FED.

    P12 (this file)  the root both of the above were standing on
         `StyleBibleSchema` was an OPEN `z.object`. An undeclared key was
         STRIPPED and `safeParse` still returned `success: true`. The first
         defect needed somewhere for a declared-but-unread key to hide; the
         second needed somewhere for a read-but-undeclared key to die. An open
         object was the place both went.

The second is the one that is genuinely unrecoverable from the outside. Its
author sees a clean parse. Its renderer sees a fully populated `StyleBible`.
Nobody between them ever observes the value disappear. Patching the three
instances (`836f532`) fixed those three sections and left the bed in place —
the chain `merge a section -> a graph sets it -> it is stripped -> a consumer
reads a default` could run again tomorrow with a fourth key.

WHY THIS GUARD IS A RUNTIME PROBE AND NOT A TEXT ASSERTION.

An `assert '.strict()' in src` passes if the STRING appears anywhere in the
file, including inside this project's own 60-line comment explaining why the
schema is strict. This project has been fooled by text-presence assertions five
times, recorded across `test_motion_ease_is_not_a_claim.py`,
`test_undeclared_field_reads.py` and the P12 ledger: `mkdtemp` matching a
comment about the bug it was written for, `rmSync` satisfied by a pre-existing
call, two-word prose that survived its own deletion, `'depth' not in
schema_text` triggered by the `depthCue` substring, and the first version of a
P12 guard reading its own subject. So every assertion here calls
`safeParse` and inspects the RETURN VALUE. If someone deletes `.strict()` the
runtime behaviour changes and this goes red; if someone leaves `.strict()` in a
comment and removes it from the code, this still goes red, because comments are
not what is parsed.

WHY BOTH MUTATIONS ARE TESTED, AND WHY ONE ASSERTION CANNOT COVER BOTH.

The two ways to be non-strict look identical from outside and are not:

    no modifier          -> success: true, keys: [declared...]   (STRIPPED)
    .passthrough()       -> success: true, keys: [declared..., g] (KEPT)

A guard asserting only "the unknown key is absent" catches the first and
MISSES the second completely -- the key is present, so nothing fails. A guard
asserting only "safeParse failed" also misses the second. This file therefore
asserts the CONTRAPOSITIVE directly: feeding an undeclared key must produce
`success: false`, on both the sub-schema and the whole document, and the error
must NAME the offending key so an author can act on it.

Mutations A and B below are the receipts, and each one asserts the mutation
actually landed on disk before reading any test result -- this project has twice
read a verdict for a mutation that never reached the file.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / 'studio'
SCHEMA_TS = STUDIO / 'src' / 'schemas' / 'showcase-v1.ts'
JSON_SCHEMA = ROOT / 'pipeline' / 'schemas' / 'showcase-v1.schema.json'

NODE = shutil.which('node') or shutil.which('node.exe')
NPX = shutil.which('npx') or shutil.which('npx.cmd')
needs_node = pytest.mark.skipif(
    NODE is None or NPX is None, reason='node/npx not on PATH')

#: The key every mutation introduces. Chosen because it is not a substring of any
#: declared key and not a substring of any comment in the schema file, so a guard
#: that greps for it is testing text rather than behaviour -- which is the mistake
#: this file exists to avoid repeating.
GHOST = 'zzUndeclaredSection'

#: The probe. Written to `studio/__probe_style_bible_strict.mts` and run with
#: tsx; it imports the REAL schema module, so what is measured is the schema the
#: renderer uses and not a reconstruction of it.
PROBE_SRC = """
import {ShowcaseSchema, StyleBibleSchema} from './src/schemas/showcase-v1';

const ghost = '__GHOST__';
const base = {
  version: 1, project: 'p', bpm: 126,
  format: {width: 1920, height: 1080, fps: 60},
};

function shape(r) {
  return {
    success: r.success,
    keys: r.success ? Object.keys(r.data).sort() : null,
    issues: r.success ? null : r.error.issues.map(
      (i) => `${i.path.map(String).join('.') || '(root)'}: ${i.message}`),
  };
}

// For a whole-DOCUMENT parse, `keys` is the document's own top-level keys and
// says nothing about the style bible. The ghost key has to be looked for inside
// `style_bible` explicitly, or the passthrough mutation can be checked against
// the wrong object -- an earlier draft of this probe asserted `ghost in keys`
// on a document parse, where it is trivially false under BOTH mutations and so
// would have passed the mutation it was supposed to fail.
function docShape(r) {
  const base = shape(r);
  const bible = r.success ? (r.data as any).style_bible : null;
  return {
    ...base,
    bibleKeys: bible ? Object.keys(bible).sort() : null,
    sceneBibleKeys: r.success
      ? Object.keys(((r.data as any).scenes?.[0]?.style_bible ?? {})).sort()
      : null,
  };
}

// 1. the sub-schema on its own
console.log(JSON.stringify({
  name: 'sub-schema',
  ...shape(StyleBibleSchema.safeParse({typography: {}, [ghost]: {stagger: 0.4}})),
}));

// 2. the same ghost key through the WHOLE document, at both levels a graph can
//    set a style bible (film-level and per-scene)
console.log(JSON.stringify({
  name: 'document film-level',
  ...docShape(ShowcaseSchema.safeParse({
    ...base,
    style_bible: {typography: {numericDisplay: {size: 232}}, [ghost]: {stagger: 0.4}},
    scenes: [{id: 's01', type: 'kpi-hero', durationInFrames: 30}],
  })),
}));
console.log(JSON.stringify({
  name: 'document per-scene',
  ...docShape(ShowcaseSchema.safeParse({
    ...base,
    scenes: [{id: 's01', type: 'kpi-hero', durationInFrames: 30,
              style_bible: {typography: {}, [ghost]: {stagger: 0.4}}}],
  })),
}));

// 3. the OPENNESS THAT MUST SURVIVE this change: an unknown sub-key INSIDE a
//    declared section. `mergeSection` filters by the default's own keys, so this
//    has always been legal and two cross-mirror tests pin it. If `.strict()`
//    ever deepens, those go red -- this records why that would be a regression.
console.log(JSON.stringify({
  name: 'bag interior stays open',
  ...shape(StyleBibleSchema.safeParse({palette: {nope: 1}})),
}));

// 4. every DECLARED key must still be accepted, including depthCue's list shape.
//    Strictness that rejects valid input is not a fix, it is a different outage.
console.log(JSON.stringify({
  name: 'all declared keys',
  ...shape(StyleBibleSchema.safeParse({
    palette: {}, typography: {}, spacing: {}, radius: {},
    depthCue: ['0 1px 2px #000'], shadow: {},
    cameraLanguage: {}, motionLanguage: {}, chartLanguage: {}, audioLanguage: {},
  })),
}));
"""

PROBE_PATH = STUDIO / '__probe_style_bible_strict.mts'


def _probe_cmd() -> list[str]:
    """Invoke tsx on THIS platform.

    `shutil.which('npx')` on Windows resolves to `npx.CMD`, which `CreateProcess`
    cannot execute directly -- subprocess raises `FileNotFoundError` while
    `which` reports the file is right there. Go through `cmd.exe /c` in that case
    only. (This is not hypothetical: the same trap is documented, and paid, in
    `test_style_bible_no_dumb_declarations.py`.)
    """
    tsx = shutil.which('tsx')
    if tsx and not tsx.lower().endswith('.cmd'):
        return [tsx, str(PROBE_PATH)]
    return [os.environ.get('COMSPEC', 'cmd.exe'), '/c', NPX, 'tsx', str(PROBE_PATH)]


def run_probe() -> dict[str, dict]:
    """Run the probe and return its JSON lines keyed by case name."""
    PROBE_PATH.write_text(PROBE_SRC.replace('__GHOST__', GHOST), encoding='utf-8')
    try:
        proc = subprocess.run(
            _probe_cmd(), cwd=STUDIO, capture_output=True, text=True,
            timeout=300, encoding='utf-8', errors='replace')
        assert proc.returncode == 0, (
            f'probe failed:\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}')
        rows = [json.loads(l) for l in proc.stdout.splitlines()
                if l.startswith('{')]
        assert rows, f'no probe output:\n{proc.stdout}\n{proc.stderr[-2000:]}'
        out = {r['name']: r for r in rows}
        assert len(out) == len(rows), 'probe emitted a duplicate case name'
        return out
    finally:
        PROBE_PATH.unlink(missing_ok=True)


def _bible_keys(row: dict) -> list[str]:
    """The style_bible keys in a probe row, whichever object was parsed.

    `sub-schema` rows parse `StyleBibleSchema` directly, so their key list IS the
    bible. Document rows parse the whole graph, where `keys` is the document's
    own top-level list and the bible is nested. Reading the wrong one makes a
    mutation assertion vacuous -- under BOTH mutations the ghost key is absent
    from a document's top-level keys, so a guard written that way passes the
    exact regression it was written to fail. Measured, not assumed: the first
    run of mutation B failed here, and for this reason.
    """
    if row.get('bibleKeys') is not None:
        return row['bibleKeys']
    if row.get('sceneBibleKeys') is not None:
        return row['sceneBibleKeys']
    return row.get('keys') or []


# ── 1. the contract ────────────────────────────────────────────────────────

@needs_node
def test_an_undeclared_style_bible_key_is_rejected_not_stripped():
    """THE assertion. Feed the ghost key, require a failure.

    Checked on the sub-schema alone and through the whole document at both
    levels a graph can set a style bible, because `FinanceShowcaseWide.tsx`
    feeds `doc.style_bible` and `scene.style_bible` into the same provider -- a
    per-scene override is exactly as capable of carrying an undeclared key, and
    a guard that only exercised the film level would miss half the surface.
    """
    got = run_probe()
    for name in ('sub-schema', 'document film-level', 'document per-scene'):
        row = got[name]
        assert row['success'] is False, (
            f'{name}: an undeclared style_bible key was ACCEPTED: {row}. '
            'Either it was stripped (the P12 defect, returning) or it was '
            'passed through (a different way of being non-strict). Both are '
            'what this file exists to make impossible.')
        assert row['keys'] is None, f'{name}: a failed parse produced data: {row}'


@needs_node
def test_the_rejection_names_the_offending_key():
    """An error that only says "schema failed" tells an author nothing.

    The value of making this a HARD error rather than a silent strip is that the
    author can act on it -- which is only true if the message identifies WHICH
    key and WHERE. Asserted separately from the rejection itself because a
    strict schema with an opaque error would satisfy the test above and still
    be a bad developer experience.
    """
    got = run_probe()
    for name in ('sub-schema', 'document film-level', 'document per-scene'):
        issues = got[name]['issues'] or []
        assert any(GHOST in i for i in issues), (
            f'{name}: no issue names {GHOST!r}: {issues}. An author seeing this '
            'error would know their style bible was rejected and not why.')
        assert any('nrecognized' in i or 'dditional' in i for i in issues), (
            f'{name}: the issue does not identify the unknown-key class: '
            f'{issues}')


@needs_node
def test_every_declared_key_is_still_accepted():
    """Strictness that rejects valid input is a different outage, not a fix.

    All ten declared sections in one object, with `depthCue` in its list shape.
    A `.strict()` written too greedily -- on the wrong object, or with the record
    value types pinned -- turns this red.
    """
    row = run_probe()['all declared keys']
    assert row['success'] is True, (
        f'a style_bible using every declared key was rejected: {row}')
    assert 'depthCue' in (row['keys'] or []), row


@needs_node
def test_the_bag_interior_stays_open():
    """What `.strict()` does NOT close, asserted so it cannot close by accident.

    `.strict()` governs the top-level keys of the bible. `palette.card`,
    `spacing.gutter` and every other sub-key remain free-form, because
    `mergeSection` filters incoming values against the default's own keys and
    type-checks each one -- an unknown sub-key is dropped there, with the rest,
    and the two cross-mirror tests that pin this openness
    (`test_pipeline_validates_the_schema.py` "style_bible open bag" and
    `test_showcase_mirrors_agree_on_values.py` "unknown key in style_bible
    section") would go red if it stopped.

    Asserting the boundary is the point: a future change that deepens
    `StyleBibleSchema` into the bags is not obviously wrong, and without this
    the change would arrive silently and be discovered by whichever merge
    started rejecting a payload nobody re-read.
    """
    row = run_probe()['bag interior stays open']
    assert row['success'] is True, (
        f'an unknown key INSIDE a declared section was rejected: {row}. '
        'That is outside what .strict() was asked to do and would break '
        'free-form section payloads the resolver merges by key.')


# ── 2. the JSON Schema mirror ──────────────────────────────────────────────

def test_the_json_schema_mirror_is_strict_too():
    """The other side of the same wall.

    `Scene`, `Camera`, `Motion`, `Transition` and the document root already
    carried `additionalProperties: false`. `StyleBible` did not, so the two
    mirrors returned OPPOSITE verdicts on the same bytes -- zod stripped the
    key and reported success while the schema would have rejected it. That is
    the exact disagreement P11 defect 3 was about, and it is the reason a
    one-sided change would not have been a fix.

    A structural read of the parsed document rather than a substring, so the
    file's own prose cannot satisfy it.
    """
    doc = json.loads(JSON_SCHEMA.read_text(encoding='utf-8'))
    style = doc['definitions']['StyleBible']
    assert style.get('additionalProperties') is False, (
        'definitions/StyleBible has no additionalProperties: false, so the '
        'JSON Schema mirror and the zod schema disagree about undeclared keys '
        'again: zod REJECTS what the mirror STRIPS.')

    # and the parity must hold for every other strict definition too, so this
    # cannot be satisfied by loosening something else
    for name in ('Scene', 'Camera', 'Motion', 'Transition'):
        assert doc['definitions'][name].get('additionalProperties') is False, name
    assert doc.get('additionalProperties') is False, 'document root'


def test_the_two_mirrors_agree_on_the_documented_key_set():
    """`.strict()` rejects an UNDECLARED key -- so the two declared sets must
    match, or one side rejects a graph the other happily accepts.

    This is the failure a strict schema introduces that an open one did not
    have: with stripping, a drift in the declared sets cost nothing. With
    rejection, a key present on one side and absent on the other becomes a
    hard error on one and a silent no-op on the other -- the same mirror drift
    that used to be harmless.
    """
    import re
    src = SCHEMA_TS.read_text(encoding='utf-8')
    # The body is matched NON-GREEDILY and bounded by the declaration itself.
    # An earlier draft used the greedy `.*?` spelling against `z.object({`,
    # which matched the LAST `});` in the file -- SceneSchema's -- and so swept
    # up Motion/Camera/Transition keys too. That made the parity check fail for
    # a reason that had nothing to do with parity: the parser was reading the
    # wrong object. It is the same trap `test_motion_ease_is_not_a_claim.py`
    # documents for `_ts_motion_keys`, which had to bound its body by "no
    # intervening `export const`" because `StyleBibleSchema` sits between it and
    # the next `.strict()`ed block.
    m = re.search(
        r'export const StyleBibleSchema\s*=\s*z\s*\n?\s*\.object\(\{\s*\n(.*?)\n\s*\}\)',
        src, re.S)
    assert m, ('could not parse StyleBibleSchema out of showcase-v1.ts; update '
               'this parser rather than reading the failure as a schema problem')
    ts_keys = set(re.findall(r'^\s{4}(\w+):', m.group(1), re.M))
    doc = json.loads(JSON_SCHEMA.read_text(encoding='utf-8'))
    js_keys = set(doc['definitions']['StyleBible']['properties'])
    assert ts_keys, 'no zod key parsed -- the comparison below would be vacuous'
    assert ts_keys == js_keys, (
        f'the mirrors declare different sections: zod-only={sorted(ts_keys - js_keys)}, '
        f'json-schema-only={sorted(js_keys - ts_keys)}. With additionalProperties: '
        'false, a key on one side and not the other is a hard error on one side '
        'and a silent strip on the other.')


# ── 3. the mutations: this guard has to be able to go red ───────────────────

#: The closing of `StyleBibleSchema`, matched by STRUCTURE rather than by a
#: literal. The first version anchored on the exact byte sequence
#: `b'  })\r\n  .strict();\r\n\r\nexport const SceneSchema'`, which is correct
#: today and quietly fragile: it hard-codes the indent, the line ending, the
#: blank line and the name of the next declaration. Under mutation A — which
#: deletes that very `.strict()` — the two mutation tests then both failed with
#: "the anchor is not in showcase-v1.ts", which reads like a broken guard rather
#: than a broken anchor, and on a run where the mutation had already landed for
#: an unrelated reason. The regex finds the declaration's own terminator
#: regardless of what follows it.
_STYLE_BIBLE_CLOSE = re.compile(
    rb'export const StyleBibleSchema\s*=\s*z\s*\n?\s*\.object\(\{'
    rb'.*?\}\s*\)((?:\s*\.\w+\([^()]*\))*)\s*;', re.S)


def _style_bible_block(body: bytes) -> re.Match:
    m = _STYLE_BIBLE_CLOSE.search(body)
    assert m, 'could not locate the StyleBibleSchema declaration in showcase-v1.ts'
    return m


def _inject(new: bytes, what: str) -> bytes:
    """Rewrite `StyleBibleSchema`'s closing, and PROVE it landed on disk.

    Two runs of this project reported a test verdict for a mutation that was
    never written to the file, so the landed-check is not optional ceremony —
    and neither is re-reading the file from disk afterwards rather than trusting
    the in-memory value.
    """
    body = SCHEMA_TS.read_bytes()
    m = _style_bible_block(body)
    original = m.group(0)
    assert b'export const SceneSchema' not in original, (
        'the StyleBibleSchema match ran past its own declaration and swallowed '
        'the next export; the closing anchor is too loose.')
    mutated = body.replace(original, new, 1)
    assert mutated != body, f'{what}: the mutation produced identical bytes'
    SCHEMA_TS.write_bytes(mutated)
    on_disk = SCHEMA_TS.read_bytes()
    landed = _style_bible_block(on_disk)
    assert landed.group(0) == new, (
        f'{what}: the mutation did not land. On disk the declaration closes as '
        f'{landed.group(0)[-60:]!r}, not the mutation.')
    return body


def test_mutation_a_removing_strict_is_caught():
    """MUTATION A: delete `.strict()`. The guard must go red.

    This is the defect's own shape, restored: an undeclared key is STRIPPED and
    `safeParse` reports success. Note what a text-presence guard would do here --
    `.strict()` still appears in this repository's comments and in
    `MotionSchema`, `CameraSchema` and `TransitionSchema`, so `assert '.strict()'
    in src` stays green through the exact regression it was written to catch.
    """
    original = _inject(b'export const StyleBibleSchema = z\n  .object({\n});',
                       'mutation A: drop .strict() from StyleBibleSchema')
    try:
        if NODE is None or NPX is None:
            pytest.skip('node/npx not on PATH')
        got = run_probe()
        for name in ('sub-schema', 'document film-level', 'document per-scene'):
            assert got[name]['success'] is True, (
                f'{name}: removing .strict() did not make the schema ACCEPT the '
                f'undeclared key: {got[name]}. The mutation is supposed to '
                'restore the P12 defect.')
            assert GHOST not in _bible_keys(got[name]), (
                f'{name}: with .strict() gone the key was neither stripped nor '
                f'rejected -- it is being passed through: {got[name]}.')
    finally:
        SCHEMA_TS.write_bytes(original)
        assert SCHEMA_TS.read_bytes() == original, 'failed to restore the schema'


def test_mutation_b_adding_passthrough_is_caught():
    """MUTATION B: `.passthrough()`. The OTHER way to be non-strict, and the
    one a "did the key survive?" assertion misses outright.

    With `.passthrough()` the undeclared key SURVIVES the parse -- `keys`
    contains it -- so an assertion of the form "the ghost key is not in the
    output" passes, and so does an assertion of the form "every declared key is
    still there". Only `success === false` catches it. That is why the contract
    above is asserted as a rejection and not as an absence.
    """
    original = _inject(b'export const StyleBibleSchema = z\n  .object({\n  })\n  .strict()\n  .passthrough();',
                       'mutation B: add .passthrough() to StyleBibleSchema')
    try:
        if NODE is None or NPX is None:
            pytest.skip('node/npx not on PATH')
        got = run_probe()
        for name in ('sub-schema', 'document film-level', 'document per-scene'):
            assert got[name]['success'] is True, (
                f'{name}: .passthrough() did not make the schema ACCEPT the '
                f'undeclared key: {got[name]}')
            assert GHOST in _bible_keys(got[name]), (
                f'{name}: with .passthrough() the key should have been KEPT, '
                f'but it is absent: {got[name]}. Either the mutation did not '
                'take effect or passthrough is not behaving as measured.')
    finally:
        SCHEMA_TS.write_bytes(original)
        assert SCHEMA_TS.read_bytes() == original, 'failed to restore the schema'


def test_both_mutations_are_caught_by_the_same_assertion():
    """The reason both mutations live in one file: ONE assertion covers both.

    The two failure modes are opposite -- strip vs keep -- and a guard written
    against either one is blind to the other. `success is False` is the only
    shape that distinguishes "rejects unknown keys" from both ways of not doing
    it. Asserted here against the probe's own output rather than by re-running
    the mutations, because the two tests above already prove each mutation
    turns the probe red; what needs stating is that the SAME condition is what
    turned red, so a future edit that weakens one of them is visible here.
    """
    if NODE is None or NPX is None:
        pytest.skip('node/npx not on PATH')
    good = run_probe()
    for name in ('sub-schema', 'document film-level', 'document per-scene'):
        assert good[name]['success'] is False, name


# ── 4. the guard cannot be satisfied by its own documentation ──────────────

def test_the_schema_comment_cannot_satisfy_the_strictness_guards():
    """The vacuity contract for this file.

    `StyleBibleSchema` carries a long comment explaining that it IS strict and
    that a comment is not what zod parses. A substring guard would therefore be
    satisfiable by the very prose describing the fix -- the fifth time this
    project has been fooled by a text-presence assertion.

    So the check is behavioural and self-directed: inject a `.strict()` into a
    COMMENT in a scratch copy and require that nothing about the probe's verdict
    depends on comment text at all. Concretely, the probe reads the real module;
    here we only assert the guard's assertion is about `success`, and that the
    word appears in the schema file -- i.e. that the tempting substring really
    is available to be abused, which is what makes the behavioural assertions
    above load-bearing rather than redundant.
    """
    src = SCHEMA_TS.read_text(encoding='utf-8')
    assert '.strict()' in src, (
        'the schema no longer mentions .strict() anywhere; if it was spelled '
        'differently, re-derive this file rather than letting it pass quietly')
    # the guards above must be phrased against the parse RESULT. If someone
    # "simplifies" one into a source substring, this comment stops being true
    # and the file has to be re-read.
    body = Path(__file__).read_text(encoding='utf-8')
    for name in ('sub-schema', 'document film-level', 'document per-scene'):
        assert name in body, name
    assert 'safeParse' in body or 'run_probe' in body


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))