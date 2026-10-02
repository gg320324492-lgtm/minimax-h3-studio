"""No dumb declarations in style_bible (P12, third deliverable).

THE DEFECT THIS EXISTS FOR.

A style_bible key is a claim: "the film will look different because the graph
said so." The claim is only true if all four links in
`style_bible_consumption.py` hold — declared, merged by the resolver,
republished by `useDesign()`, and read by a scene. Break any link and the graph
still validates, still renders, and changes nothing: the declaration is a lie
that costs an operator the belief that editing the graph does anything.

`StyleBibleSchema` WAS an OPEN `z.object` with no `.strict()`, so an undeclared
key was stripped rather than rejected — a dumb declaration was not merely legal,
it was invisible. Nothing else in the suite would have noticed one.

P12 closed that half: the schema is `.strict()` now, so an undeclared key is a
hard error and `test_style_bible_schema_is_strict.py` guards it BEHAVIOURALLY,
by calling `safeParse` and asserting the returned value rather than by looking
for a substring. That file is the parser half of this defect. THIS file is the
half strictness cannot reach: a section the schema DECLARES and the resolver
never merges. There is no undeclared key in that chain — validation is
perfectly happy — and the declaration is still a lie. `chartLanguage` and
`audioLanguage` are both such keys today, and that is the P11 direction, whose
repair (delete the declaration, or wire the consumer) is a different decision
from this one.

This is the mirror of `test_undeclared_field_reads.py`. That file stops code
reading a field the schema strips; this one stops a graph declaring a field
nothing reads. Both exist because the two halves can fail independently and
each half alone looks correct.

WHAT IS AND IS NOT PROVEN HERE.

    Proven:  every style_bible key in a delivered graph survives the parser,
             reaches the resolver, is republished by useDesign(), and is read
             off useDesign() by at least one production scene.
    NOT proven: that the scene honours the value, or that the value is
               well-formed — `mergeSection` silently drops a sub-key whose type
               does not match the default, which is a real failure mode with no
               guard behind it (see `test_motion_ease_is_not_a_claim.py` for
               the same shape). "Reaches a render decision" is the claim being
               made, and it is the claim this file checks.

The mutations below are the contract. A guard that cannot demonstrate its own
failure mode is a comment, and this project has four of those already.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import style_bible_consumption as sbc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / 'pipeline' / 'examples' / 'showcase_demo.json'
NODE = shutil.which('node') or shutil.which('node.exe')


def _tsx_command(probe: Path) -> list[str]:
    """How to run a `.mts` probe on THIS machine.

    `shutil.which('npx')` on Windows resolves to `npx.CMD`, and `CreateProcess`
    cannot execute a `.CMD` directly — subprocess raises `FileNotFoundError`
    while `which` insists the file is right there. That is the failure this
    helper exists to absorb; the first version of this test hit it.

    A shell wrapper is used for the `.CMD` case only, and only because there is
    no other way to run it. When `tsx` is installed as a plain executable the
    command is invoked directly, with no shell in the path at all.
    """
    tsx = shutil.which('tsx')
    if tsx and not tsx.lower().endswith('.cmd'):
        return [tsx, str(probe)]
    npx = shutil.which('npx') or shutil.which('npx.cmd')
    if npx:
        return [os.environ.get('COMSPEC', 'cmd.exe'), '/c', npx, 'tsx', str(probe)]
    assert NODE is not None, 'neither tsx, npx nor node is on PATH'
    return [NODE, str(probe)]


# ── 1. the chain itself is real, and is what this file thinks it is ─────────

def test_style_bible_schema_is_open_so_this_guard_is_needed():
    """Anchors the premise. WAS: "if someone adds `.strict()` ... re-derive this
    file". Someone did, and this is the re-derivation.

    `.strict()` landed on `StyleBibleSchema` in P12. The original version of this
    test asserted the schema was OPEN and told the reader to re-derive the file
    if it stopped being; it now asserts the opposite, for a stated reason, so the
    premise still cannot rot silently.

    WHAT CHANGED AND WHAT DID NOT. An undeclared style_bible key is now a hard
    error instead of a silent strip, so `ghostKey` in a graph fails loudly rather
    than vanishing. The argument this file is built on — "a declaration nothing
    reads is a lie, and nothing in the toolchain can see it" — is WEAKENED but
    NOT void, and the residue is what still needs measuring:

      * gone: a graph declaring a key the schema strips. That is now impossible
        to express; the parser rejects it. `test_style_bible_schema_is_strict.py`
        owns that half, behaviourally, via `safeParse`.
      * STILL HERE, and still invisible from the data side: a key the schema
        DECLARES and the resolver never merges. `chartLanguage` and
        `audioLanguage` are both declared on both mirrors today, and neither is
        bound by `styleBible.tsx`. The graph sets one, validation passes, and
        nothing renders differently — strictness does not touch this, because
        there is no undeclared key anywhere in the chain. That is the P11
        direction and a different repair (delete the declaration or wire the
        consumer); it is deliberately out of P12's scope.

    So the file's guard is now measuring the second half, and the first half has
    moved next door rather than disappeared.
    """
    assert sbc.style_bible_is_strict() is True, (
        'StyleBibleSchema is open again. An undeclared style_bible key is being '
        'STRIPPED with success: true, which is the P12 defect returning: a '
        'section merged by the resolver and read by a scene can no longer be fed '
        'from a graph, and nothing will say so. Re-read this file AND '
        'test_style_bible_schema_is_strict.py.')


def test_the_derivation_is_not_vacuous():
    """A sweep that matches nothing reports green forever.

    This is the failure mode named in `test_undeclared_field_reads.py` and it is
    worth a test of its own rather than a comment: the parser regexes here match
    `z.object`, `merge*`, and `useDesign()` destructures, and any of them can
    stop matching after a lawful refactor while the guard below keeps passing.

    So the index is asserted to be non-empty AND to contain the exports a scene
    genuinely reads. If a rename moves `useDesign()` to another spelling, this
    goes red instead of the guard going quietly blind.
    """
    index = sbc.destructured_exports()
    assert index, (
        'no useDesign() destructure matched anywhere. The consumer link is '
        'vacuous: every key would look unreachable or, if the resolver link '
        'also stopped matching, look fine.')
    assert {'PALETTE', 'TYPE', 'MOTION', 'SPACE'} <= set(index), sorted(index)
    # and the resolver half is not vacuous either
    assert sbc.resolver_bindings(), 'no resolver binding matched'
    assert sbc.declared_style_bible_keys(), 'no declared style_bible key matched'


def test_the_guard_excludes_the_resolver_itself():
    """`styleBible.tsx` names every export because it DEFINES them.

    Counting it as a consumer made every bound key look reachable on the
    strength of the very code being measured — the guard reading its own
    subject. Asserted rather than left to the comment in the module, because
    this is exactly the class of bug that produces a green suite over a red
    renderer, and it was a real bug in the first version of this file.
    """
    hits = sbc.consumers_of('PALETTE')
    assert hits, 'PALETTE should have real consumers'
    assert not any('design/styleBible.tsx' in h for h in hits), hits


# ── 2. the verdict: each of the seven keys ─────────────────────────────────

def test_reachability_of_every_declared_key():
    """The measurement, pinned so a refactor that changes it is a visible diff.

    `audioLanguage` and `chartLanguage` are the two that die at link 2: the
    schema declares them, they are open records, and `resolveStyleBible` never
    mentions either name. The other eight reach a scene.

    WAS SEVEN. P12 declared `radius`, `shadow` and `depthCue`, so the three
    that used to die at link 1 now run the whole chain; the two that die at
    link 2 are untouched by that change and remain the whole of the
    dumb-declaration set.
    """
    report = sbc.reachability_report()
    assert set(report) == {
        'palette', 'typography', 'spacing', 'radius', 'shadow', 'depthCue',
        'cameraLanguage', 'motionLanguage', 'chartLanguage', 'audioLanguage',
    }, sorted(report)

    states = {k: v[0] for k, v in report.items()}
    assert states == {
        'palette': 'reachable',
        'typography': 'reachable',
        'spacing': 'reachable',
        # P12: declared, so these now survive the parser and run the chain.
        # Before it they were `no-declaration` and every scene read a default.
        'radius': 'reachable',
        'shadow': 'reachable',
        'depthCue': 'reachable',
        'cameraLanguage': 'reachable',
        'motionLanguage': 'reachable',
        # declared by both mirrors, merged by nothing, read by nothing.
        # The P11 direction. Untouched by P12 — see
        # docs/STYLE_BIBLE_STRIPPED_SECTIONS.md section 6.
        'chartLanguage': 'no-resolver-binding',
        'audioLanguage': 'no-resolver-binding',
    }, states


def test_the_two_unconsumed_keys_are_dumb_declarations_today():
    """Spelled out rather than derived, because the whole point of P12 is the
    Director Agent question and this is the answer to half of it.

    Two of the seven declared keys cannot change a single pixel. A Director
    that emits a StyleBible from the schema would emit these by default, and
    every one would be a claim the film ignores.
    """
    assert sbc.unreachable_declared_keys() == {
        'chartLanguage': 'no-resolver-binding',
        'audioLanguage': 'no-resolver-binding',
    }


def test_no_merged_section_is_outside_the_schema_anymore():
    """The inverse defect, now MEASURED AT ZERO. Read this as a tombstone.

    `resolveStyleBible` used to merge `radius`, `shadow`, `depth` and `depthCue`
    into the bible while `StyleBibleSchema` declared none of them. Scenes read
    the corresponding `useDesign()` exports, so the code looked wired end to
    end — but zod stripped the input on parse, `safeParse` returned
    `success: true`, and every scene silently rendered the default.

    This is P11's `audio` defect rotated ninety degrees: not a read that cannot
    happen, but a read that cannot be FED. It was invisible from both ends —
    the graph author saw no error, and the renderer saw a populated object.

    P12 closed it. `radius`, `shadow` and `depthCue` are declared on both
    mirrors; `depth` had no consumer at all and its graph-facing plumbing was
    deleted (`tokens.ts`'s `DEPTH` table survives — deleting a token is a
    larger call). The difference this function measures is now EMPTY, and the
    assertion says so out loud rather than letting the ledger quietly become
    wrong in the other direction.

    The live guard against this recurring is
    `tests/test_style_bible_merges_only_declared.py`.
    """
    assert sbc.resolver_sections_outside_the_schema() == {}, (
        'a merged section is outside the schema again: '
        f'{sbc.resolver_sections_outside_the_schema()}. Every one of these is '
        'merged by the resolver, consumed by a scene, and STRIPPED on parse — '
        'the graph sets it, safeParse succeeds, and the scene renders the '
        'default. This is the P12 defect returning.')


# -- 3. the delivered graphs ---------------------------------------------

def test_no_delivered_graph_declares_a_key_nothing_reads():
    """The sweep the work order asked for: every key a graph actually sets must
    have at least one render-side consumer.

    Currently one key appears (`typography` in `showcase_demo.json`) and it is
    reachable, so this is green. It goes red the moment a graph grows a key the
    renderer ignores.
    """
    graph_keys = sbc.keys_in_graphs()
    report = sbc.reachability_report()
    offences: list[str] = []
    for key, where in sorted(graph_keys.items()):
        state = report.get(key, ('no-declaration', []))[0]
        if state != 'reachable':
            offences.append(
                f'{", ".join(where)} sets style_bible.{key} -> {state}. '
                f'The graph validates and renders unchanged.')
    assert not offences, (
        'a delivered graph declares a style_bible key with no render-side '
        'consumer:\n  ' + '\n  '.join(offences))


def test_the_one_key_the_demo_graph_sets_is_reachable():
    """Pins the count so a new key in the demo graph cannot slip in unnoticed.

    `typography` is the only style_bible key in either delivered graph. It sets
    `numericDisplay`, which IS a real role in `tokens.ts` (TYPE key 10 of 12)
    and IS read by `KpiHero.tsx:102/107/111` — the one graph-level declaration
    in this project that genuinely works, and the template a Director should
    copy.
    """
    assert sbc.keys_in_graphs() == {'typography': ['showcase_demo.json']}


# ── 4. mutations: the guard must be able to go red ─────────────────────────

def test_mutation_a_graph_key_with_no_consumer_is_caught(tmp_path):
    """MUTATION A, in-process.

    Adds `ghostKey` to the demo graph's `style_bible` — exactly the shape the
    work order names — and runs the real sweep over the real file. This is not
    a synthetic fixture: the offence is produced by the same
    `reachability()` the production test uses, so a green here would mean the
    sweep cannot see its own subject.
    """
    original = DEMO.read_bytes()
    try:
        doc = json.loads(original.decode('utf-8-sig'))
        doc['style_bible']['ghostKey'] = {'stagger': 0.4}
        DEMO.write_text(json.dumps(doc, indent=2), encoding='utf-8')

        found = sbc.keys_in_graphs()
        assert 'ghostKey' in found, found
        state, _ = sbc.reachability('ghostKey')
        assert state == 'no-declaration', state
    finally:
        DEMO.write_bytes(original)


def test_mutation_deleting_a_render_side_consumer_is_caught():
    """MUTATION B, in-process: remove the one real read of a reachable key.

    Deletes `cameraLanguage`'s only consumer — the `useDesign()` destructure in
    `CameraRig.tsx` — from a temporary copy of the template, and re-derives.
    The key must fall from `reachable` to `resolver-bound-but-unused`.

    This is the mutation that a text-presence guard would survive: the string
    `cameraLanguage` stays in `styleBible.tsx`, `CameraRig.tsx`'s own comments
    still discuss it at length, and the schema still declares it. Only a
    derivation that follows the retrieval path notices.
    """
    rig = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'common' / 'CameraRig.tsx'
    assert sbc.reachability('cameraLanguage')[0] == 'reachable'
    body = rig.read_bytes()
    needle = b'  const {camera: cameraDefaults} = useDesign();\r\n'
    assert needle in body, (
        'CameraRig no longer has the exact useDesign() destructure this test '
        'removes; update the mutation rather than reading a miss as a pass')
    try:
        rig.write_bytes(body.replace(needle, b'', 1))
        assert needle not in rig.read_bytes(), 'the mutation did not land'
        state, evidence = sbc.reachability('cameraLanguage')
        assert state == 'resolver-bound-but-unused', (state, evidence)
    finally:
        rig.write_bytes(body)


def test_mutation_renaming_a_render_side_export_is_caught():
    """MUTATION C, in-process: rename the export, keep every string intact.

    `useDesign()` publishes the palette as `PALETTE`; a plausible refactor
    renames the binding to `s.palette` and republishes it as `Color`. Nothing
    is deleted — every token still appears somewhere in the file — and the
    `b.palette -> StyleBible.palette` link is untouched. Only link 4 breaks.

    This is the mutation class that kills an `assert 'palette' in src` guard
    outright, and it is why the file has a derivation instead.
    """
    bible_tsx = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'design' / 'styleBible.tsx'
    assert sbc.reachability('palette')[0] == 'reachable'
    body = bible_tsx.read_bytes()
    # CRLF file: match the line terminator actually on disk, not the one a
    # previous work order guessed. Verified per-file before writing.
    needle = b'    PALETTE: s.palette,\r\n'
    assert needle in body, 'styleBible.tsx is not CRLF, or the export was renamed'
    try:
        bible_tsx.write_bytes(body.replace(needle, b'    Color: s.palette,\r\n', 1))
        assert needle not in bible_tsx.read_bytes(), 'the mutation did not land'
        exports = sbc.design_exports()
        assert exports['palette'] == 'Color', exports
        state, _ = sbc.reachability('palette')
        assert state == 'resolver-bound-but-unused', state
    finally:
        bible_tsx.write_bytes(body)


@pytest.mark.skipif(NODE is None, reason='node not on PATH')
def test_the_parser_really_rejects_an_undeclared_key(tmp_path):
    """The runtime half of mutation A. INVERTED in P12, deliberately.

    This used to assert that `ghostKey` PARSED and was then gone — the strip,
    which was the whole point: there was no error anywhere for one to catch. The
    schema is `.strict()` now, so the correct answer is the opposite verdict, and
    asserting the old one would be asserting the defect back into existence.

    It is kept rather than deleted for two reasons. It runs the probe through
    `ShowcaseSchema` end to end, which the derivation in this file cannot do at
    all — every other assertion here is regex-based and runs without node. And a
    file that documented the strip and quietly dropped the test would leave no
    receipt that the behaviour changed on purpose.

    The parse half (a key the schema strips) now lives in
    `test_style_bible_schema_is_strict.py`, which asserts it by REJECTION rather
    than by absence — `.passthrough()` also keeps unknown keys, so "the key is
    gone" would not have caught it.
    """
    probe = ROOT / 'studio' / '__probe_p12.mts'
    probe.write_text(
        "import {ShowcaseSchema} from './src/schemas/showcase-v1';\n"
        "const r = ShowcaseSchema.safeParse({\n"
        "  version: 1, project: 'p', bpm: 126,\n"
        "  format: {width: 1920, height: 1080, fps: 60},\n"
        "  style_bible: {typography: {numericDisplay: {size: 232}}, ghostKey: {stagger: 0.4}},\n"
        "  scenes: [{id: 's01', type: 'kpi-hero', durationInFrames: 30}],\n"
        "});\n"
        "console.log(JSON.stringify({\n"
        "  success: r.success,\n"
        "  keys: r.success ? Object.keys((r.data as any).style_bible).sort() : null,\n"
        "  issues: r.success ? null : r.error.issues.map(\n"
        "    (i) => `${i.path.map(String).join('.') || '(root)'}: ${i.message}`),\n"
        "}));\n",
        encoding='utf-8')
    try:
        proc = subprocess.run(
            _tsx_command(probe),
            cwd=ROOT / 'studio', capture_output=True, text=True, timeout=300,
            encoding='utf-8', errors='replace')
        line = [l for l in proc.stdout.splitlines() if l.startswith('{')]
        assert line, f'no probe output:\n{proc.stdout}\n{proc.stderr[-1500:]}'
        got = json.loads(line[-1])
        assert got['success'] is False, (
            f'a graph setting an undeclared style_bible key was ACCEPTED: {got}. '
            'The key is either being stripped with success: true — the P12 '
            'defect, still open — or passed through, which is the same problem '
            'wearing a different hat.')
        assert got['keys'] is None, got
        assert any('ghostKey' in i for i in (got['issues'] or [])), (
            f'the rejection does not name the offending key: {got}. An author '
            'would know their bible was refused and not which key was at fault.')
    finally:
        probe.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
