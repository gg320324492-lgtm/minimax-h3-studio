"""`motion.ease` must not be a claim the renderer does not honour (P11, defect 2).

THE DEFECT THIS EXISTS FOR.

The delivered graph set `"ease": "expo-out"` on two scenes (`s01_kpi`, `s03_columns`),
`MotionSchema` declared `ease: z.string().optional()`, and nothing in the render path
ever read it. The only easing in the renderer is the hardcoded bezier at
`common/primitives.tsx:183`. So an author reading the graph had every reason to
believe `expo-out` shaped those scenes. It did not.

THE FIX WAS TO CLEAN, NOT TO WIRE, and this file is the argument plus the receipt.

Wiring was rejected on evidence (the long version lives in the comment above
`MotionSchema`); the short version is a type mismatch that is not a detail:

  * the call site needs FOUR NUMBERS -- `cubicBezierEase(0.16, 1, 0.3, 1)`;
  * the built-in table is `[n,n,n,n]` -- `MOTION.profiles[x].ease`;
  * the graph shipped the NAME `"expo-out"`, and no name->curve resolver exists
    anywhere in studio/src, studio/scripts or pipeline.

Honouring it would mean inventing that resolver, i.e. deciding on the author's
behalf that `expo-out` means [0.16, 1, 0.3, 1]. Retyping the field as a 4-number
bezier would reject every graph shipped today. The "read it, can't resolve it,
fall back to the hardcoded bezier" variant is the one this project has already paid
for: it swaps a lie you can read in the graph for a lie the code performs.

WHY THIS IS A SWEEP AND NOT A FILE CHECK.

The defect is a PATTERN, not a location. A test that greps one file covers only the
file someone remembered. This one walks every production source under the template
and asserts the SHAPE of the claim: no field may be set in a delivered graph that
no renderer reads. That generalises -- the same sweep catches `notes`,
`audioEvents`, `transitionOut` and `focus` if anyone re-adds them to a graph.

WHAT IS AND IS NOT PROVEN HERE.

    Proven:  no delivered graph sets a field the renderer cannot reach, and
             `motion.ease` is not declared, so it cannot be set again by accident.
    NOT proven: that the film looks good, or that `preset`/`stagger` are honoured
             with the right FEEL -- only that they are read at all.

THE TRAP THIS FILE IS BUILT AROUND.

A guard that asserts a TOKEN APPEARS IN TEXT passes by reading its own comment. The
schema comment above `MotionSchema` is forty lines long and names `ease` eight
times; a naive `assert 'ease' not in source` would go red on our own explanation.
So every assertion below runs against STRUCTURED data -- parsed JSON, a parsed zod
object literal -- or against a comment-stripped source, never raw substring of a
file that discusses the defect. `test_the_sweep_would_catch_the_defect_it_was_written_for`
proves that by feeding the sweep the original defect and requiring a hit.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / 'studio'
SCHEMAS = STUDIO / 'src' / 'schemas'
TEMPLATE = STUDIO / 'src' / 'templates' / 'finance-showcase'
EXAMPLES = ROOT / 'pipeline' / 'examples'
TS_MOTION = SCHEMAS / 'showcase-v1.ts'
JSON_SCHEMA = ROOT / 'pipeline' / 'schemas' / 'showcase-v1.schema.json'

#: Every production source that can render a showcase graph.
#:
#: `*.check.ts` is excluded for the reason `test_undeclared_field_reads.py` gives:
#: these guards hunt text patterns and a check file is full of them deliberately.
SOURCES = sorted(
    src
    for src in (*SCHEMAS.rglob('*.ts'), *TEMPLATE.rglob('*.ts'), *TEMPLATE.rglob('*.tsx'))
    if not src.name.endswith('.check.ts')
)


def _strip_comments(text: str) -> str:
    """Remove `//` line comments and /* */ blocks.

    Every assertion in this file that touches source text runs on this, because
    the file under test EXPLAINS the defect and would otherwise satisfy a
    substring search on its own commentary. This is the single most important
    helper here: without it, this guard could go green by matching the comment
    that documents the bug it is supposed to prevent.
    """
    text = re.sub(r'/\*(?:.|\n)*?\*/', '', text)
    return re.sub(r'//[^\n]*', '', text)


def _ts_motion_keys() -> set[str]:
    """Keys declared by the zod `MotionSchema`, read from the SOURCE.

    Parsed out of the zod literal rather than executed, so the sweep has no node
    dependency -- a Python guard that can still fail when node is unavailable is
    worth more than one that cannot. Comments are stripped first, so the long
    comment above the schema (which names `preset` and `stagger` while explaining
    why `ease` is gone) cannot inject phantom keys.

    The body pattern tolerates BOTH spellings of the declaration. P11 defect 3
    wrapped the object so it could be `.strict()`ed, which moved the `{` onto the
    next line:

        export const MotionSchema = z.object({        <- was
        export const MotionSchema = z                 <- now
          .object({
            preset: ...
          })
          .strict();

    A parser pinned to the old one-line form fails with "could not find
    MotionSchema" -- a guard that goes red on a REFACTOR and reads like a schema
    problem. The body is bounded by "no intervening `export const`" rather than by
    the first `})`, because `StyleBibleSchema` sits between here and the next
    `.strict()`ed block and a non-greedy match walks straight past it.
    """
    src = _strip_comments(TS_MOTION.read_text(encoding='utf-8'))
    m = re.search(
        r'export const MotionSchema = [^=]*?\.object\(\{\r?\n'
        r'((?:(?!export const)[\s\S])*?)'
        r'\r?\n  \}\)\r?\n  \.strict\(\);', src, re.S)
    assert m, (
        'could not find MotionSchema in showcase-v1.ts. If the declaration was '
        'reshaped again, update this parser -- and note that a parser which goes '
        'red on a reformat is how a schema guard stops being read.')
    return set(re.findall(r'^\s{4}(\w+):', m.group(1), re.M))


def _read_motion_props(src: Path) -> set[str]:
    """`motion.<prop>` reads in one source file, comments excluded.

    Matches both the optional-chain and bracket forms. `MOTION.profiles[x].ease`
    is deliberately NOT matched: that is a built-in token lookup, not a read of
    the graph, and conflating the two is exactly how `ease` got reported as
    "declared and unread" when in truth neither one was reachable from the graph.
    """
    text = _strip_comments(src.read_text(encoding='utf-8'))
    props = set(re.findall(r'\bmotion\??\.(\w+)', text))
    props |= set(re.findall(r"""\bmotion\??\[['"](\w+)['"]\]""", text))
    return props


def _all_read_motion_props() -> set[str]:
    read: set[str] = set()
    for src in SOURCES:
        read |= _read_motion_props(src)
    return read


def _offences(graph_paths) -> tuple[list[str], list[str]]:
    """The sweep, as a function, so the mutation test can run the REAL code.

    Returns (undeclared, unread). Extracting it is not cosmetic: when the mutation
    test was inlined it re-implemented this comparison, and because `ease` is now
    UNDECLARED rather than merely unread, the inlined copy -- which filtered on
    `k in declared` first -- matched nothing and the mutation "survived". A
    mutation test that re-implements the guard proves nothing about the guard.
    Both branches are reported so neither can hide behind the other.
    """
    read = _all_read_motion_props()
    declared = _ts_motion_keys()
    undeclared: list[str] = []
    unread: list[str] = []
    for graph_path in sorted(graph_paths):
        doc = json.loads(graph_path.read_text(encoding='utf-8-sig'))
        for scene in doc.get('scenes', []):
            sid = scene.get('id')
            for key in sorted((scene.get('motion') or {})):
                where = f'{graph_path.name}:{sid}'
                if key not in declared:
                    undeclared.append(
                        f'{where} sets motion.{key}, not declared by MotionSchema '
                        f'(declared: {sorted(declared)})')
                elif key not in read:
                    unread.append(
                        f'{where} sets motion.{key}, which no production source reads '
                        f'(read: {sorted(read)})')
    return undeclared, unread


# ── 1. the schema, read structurally ───────────────────────────────────────

def test_motion_ease_is_not_declared_anywhere():
    """The core claim, on both mirrors.

    `ease` must be absent from the zod schema AND from the JSON Schema mirror.
    Removing the DECLARATION is what stops the defect returning: with
    `additionalProperties: false` on the JSON side a re-added `ease` is rejected,
    and with zod it is silently stripped -- so a graph could again set a field
    the renderer never sees, and `safeParse` would still return success.
    """
    assert 'ease' not in _ts_motion_keys(), (
        'MotionSchema declares `ease` again. Unless a renderer now READS it, that '
        f'is a field a graph can set and never see: {sorted(_ts_motion_keys())}')

    js = json.loads(JSON_SCHEMA.read_text(encoding='utf-8'))
    motion = js['definitions']['Motion']
    assert 'ease' not in motion['properties'], (
        'the JSON Schema mirror still declares motion.ease; the two sides have '
        f'drifted: {sorted(motion["properties"])}')


def test_delivered_graphs_set_no_motion_field_the_renderer_cannot_read():
    """THE SWEEP. A graph may not set a `motion.*` field no renderer reads.

    This is the guard that would have caught the original defect, and it is the
    one that keeps working if the graph is edited again. It compares what the
    graphs actually SET against what production code actually READS, so it
    measures behaviour rather than the presence of a token.
    """
    read = _all_read_motion_props()
    assert read, (
        'no motion.* read found in production source -- the sweep is matching '
        'nothing, which is a guard that reports green forever, not a passing '
        'guard. Check SOURCES and _read_motion_props.')

    undeclared, unread = _offences(sorted(EXAMPLES.glob('*.json')))
    assert not undeclared, 'a graph sets a motion field the schema strips on parse:\n  ' + '\n  '.join(undeclared)
    assert not unread, (
        'a graph sets a motion field the renderer never reads -- it validates, '
        'renders, and changes nothing:\n  ' + '\n  '.join(unread))


def test_the_sweep_would_catch_the_defect_it_was_written_for():
    """The mutation contract. Feed the sweep the ORIGINAL defect; it must notice.

    A guard that cannot demonstrate its own failure mode is a comment. This writes
    the shipped `"ease": "expo-out"` back into a temporary copy of the demo graph
    and re-runs the same comparison over the same production sources.
    """
    victim = EXAMPLES / '__probe_ease_graph.json'
    try:
        doc = json.loads((EXAMPLES / 'showcase_demo.json').read_text(encoding='utf-8-sig'))
        doc['scenes'][0]['motion']['ease'] = 'expo-out'   # the original defect
        victim.write_text(json.dumps(doc), encoding='utf-8')

        # The REAL sweep, over the probe graph only -- not a re-implementation.
        undeclared, unread = _offences([victim])
        assert undeclared or unread, (
            'the sweep did NOT flag a graph that sets motion.ease -- this guard '
            'cannot detect the defect it was written for')
        assert any('ease' in o for o in undeclared + unread), (
            f'the sweep flagged the wrong field: {undeclared + unread}')
        # The clean tree must be clean through the same door, or the result above
        # only proves the sweep fires on everything. The probe is excluded: it
        # lives in EXAMPLES so `_offences([victim])` can use the real glob-free
        # path, and a control glob would otherwise find the defect we just wrote.
        delivered = [p for p in sorted(EXAMPLES.glob('*.json')) if p != victim]
        assert _offences(delivered) == ([], []), (
            'the sweep reports offences on the DELIVERED graphs')
        assert 'ease' not in _all_read_motion_props(), (
            'something reads motion.ease now; if it is a real reader the CLEAN '
            'decision should be revisited, and this test is telling you so')
    finally:
        victim.unlink(missing_ok=True)


def test_preset_and_stagger_are_still_read():
    """The narrowing must not become a no-op.

    `ease` was removed because nothing read it. `preset` and `stagger` ARE read --
    if a future edit strips those too, the sweep above would still be green while
    the motion block had become entirely inert. This pins the two that remain.
    """
    read = _all_read_motion_props()
    for field in ('preset', 'stagger'):
        assert field in read, (
            f'motion.{field} is declared and set by the delivered graphs but no '
            f'production source reads it either -- the motion block is now fully '
            f'inert (read: {sorted(read)})')


# ── 2. runtime: the schema really rejects/strips it ─────────────────────────

_NPX = shutil.which('npx') or shutil.which('npx.cmd')

RUNTIME_PROBE = """
import {ShowcaseSchema} from './src/schemas/showcase-v1';

const base = () => ({
  version: 1,
  project: 'p',
  format: {width: 1920, height: 1080, fps: 60},
  scenes: [{id: 's01', type: 'kpi-hero', durationInFrames: 30,
            motion: {preset: 'premium', ease: 'expo-out'}}],
});

const r = ShowcaseSchema.safeParse(base());
console.log(JSON.stringify({
  success: r.success,
  motionKeys: r.success ? Object.keys(r.data.scenes[0].motion ?? {}) : null,
  easeSurvived: r.success ? ('ease' in (r.data.scenes[0].motion ?? {})) : null,
}));
"""


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
def test_a_graph_setting_ease_is_rejected_not_stripped(tmp_path):
    """The measurement behind the decision, re-taken.

    This used to assert the OPPOSITE and the flip is the point. It read:

      * `success` is true -- zod strips the unknown key rather than rejecting,
        so a re-added `ease` fails LOUDLY nowhere at all;
      * `easeSurvived` is false -- the key never reaches the renderer.

    That is defect one, one level down, and it was the reason the DECLARATION had
    to be removed rather than merely unwired: with a strip, removing the
    declaration changed nothing observable, and a graph could set `ease` again.

    P11 defect 3 made both mirrors strict, so the strip is gone and the guarantee
    is now stronger than "the key does not reach the renderer": the graph does
    not load at all. `motionKeys` is null because there is no parsed document to
    read keys from, which is what `easeSurvived is False` used to be standing in
    for.
    """
    probe = STUDIO / '__probe_ease.mts'
    try:
        probe.write_text(RUNTIME_PROBE, encoding='utf-8')
        proc = subprocess.run(
            [_NPX, 'tsx', str(probe)],
            cwd=STUDIO, capture_output=True, text=True, timeout=300,
            encoding='utf-8', errors='replace',
        )
        assert proc.returncode == 0, proc.stderr[-2000:]
        line = [l for l in proc.stdout.splitlines() if l.startswith('{')]
        assert line, f'no probe output:\n{proc.stdout}\n{proc.stderr}'
        got = json.loads(line[-1])
        assert got['success'] is False, (
            f'zod ACCEPTS a graph that sets motion.ease: {got}. It is stripping '
            'the key and reporting success, which is the original defect one '
            'level down.')
        assert got['easeSurvived'] is None, (
            f'a document was parsed at all, so something is no longer strict: {got}')
        assert got['motionKeys'] is None, got
    finally:
        probe.unlink(missing_ok=True)


# ── 3. the comment cannot satisfy the guard ────────────────────────────────

def test_the_schema_comment_cannot_satisfy_the_guards():
    """The vacuity contract for this file, stated as an executable check.

    The schema comment above `MotionSchema` is forty lines of prose naming `ease`,
    `preset`, `stagger` and `motion.*` reads. Every parser in this file therefore
    strips comments first, and this test is what stops that strip from being
    quietly removed later -- which would let the guards pass on the very
    explanation of the defect they exist to prevent.

    It is written as a PROBE, not as a claim about the current comment. An earlier
    draft asserted "the schema comment contains a `motion.ease` phrase" and went
    red immediately -- the comment writes `motion.*`, and the sweep's pattern
    needs a word character after the dot, so it never matched. Asserting that the
    prose happens to feed the regex is exactly backwards: it pins the wording of
    a comment instead of pinning the behaviour of the strip. So the probe below
    injects the dangerous shape deliberately and requires the strip to remove it,
    which stays true no matter how the comment is later reworded.
    """
    probe = TEMPLATE / '__probe_comment_strip.ts'
    try:
        # A comment that WOULD satisfy the sweep if comments were not stripped --
        # the precise failure mode of "a guard that reads its own comment".
        probe.write_text(
            '/* motion.ease was removed */\n'
            '// motion.ease was removed\n'
            'const real = motion?.preset;\n',
            encoding='utf-8')
        text = probe.read_text(encoding='utf-8')

        found_naive = set(re.findall(r'\bmotion\??\.(\w+)', text))
        found_stripped = set(re.findall(r'\bmotion\??\.(\w+)', _strip_comments(text)))

        assert found_naive == {'ease', 'preset'}, sorted(found_naive)
        assert found_stripped == {'preset'}, (
            'the strip is not working: comment text is being parsed as production '
            f'reads ({sorted(found_stripped)})')
        # And the real helper agrees with the stripped reading.
        assert _read_motion_props(probe) == {'preset'}, (
            f'_read_motion_props disagrees with the stripped probe: '
            f'{sorted(_read_motion_props(probe))}')
    finally:
        probe.unlink(missing_ok=True)

    # Half 2 -- _ts_motion_keys. The zod literal must still yield exactly the two
    # real keys, which proves the DECLARATION, not the prose around it, is the source.
    assert _ts_motion_keys() == {'preset', 'stagger'}, sorted(_ts_motion_keys())


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))