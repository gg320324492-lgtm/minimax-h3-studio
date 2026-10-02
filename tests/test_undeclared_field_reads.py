"""No code may read a showcase-v1 field the schema does not declare.

THE DEFECT THIS EXISTS FOR (P11, defect 1).

`FinanceShowcaseWide.tsx` read a top-level `doc.audio` and rendered an `<Audio>`
from it. `ShowcaseSchema` never declared `audio` and has no `.passthrough()`,
so zod stripped the key on every parse and the branch was permanently
unreachable — while `safeParse` still returned `success: true`. The failure was
not loud: a graph with a music bed validated clean and rendered silent.

The trap this file is built around is that deleting the branch fixes ONE read
site and says nothing about the next one. The cast that made it typecheck —
`(doc as unknown as {audio?: ...}).audio` — is a shape anyone can write again,
for any field, in any template, and it will typecheck just as quietly. So the
guard below is a SWEEP over production source rather than a check on one file:
the defect is a pattern, and a named-file assertion only ever covers the file
someone remembered to name.

WHAT IS AND IS NOT PROVEN HERE.

    Proven:  every property this module reads off a parsed showcase document is
             declared by the schema that parsed it, and a document carrying an
             undeclared key does not reach the renderer.
    NOT proven: that the film is good, or that the renderer honours the fields
             that ARE declared. Six declared fields are inert and stay inert
             (`notes`, `audioEvents`, `transitionOut`, `focus`, `ease`,
             `chart.baseline`) — they are ledger entries, not this file's job,
             and conflating "declared" with "read" is how a guard starts
             promising things nobody checked.

The rule it enforces is therefore the narrow one that is actually true: a
production file may not reach into a showcase document for a field the schema
does not name. A declared-but-unread field is inert (a lie in the other
direction, tracked separately). An UNDECLARED field read through a cast is a
silent failure (this file's job).
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
SHOWCASE_TS = SCHEMAS / 'showcase-v1.ts'
JSON_SCHEMA = ROOT / 'pipeline' / 'schemas' / 'showcase-v1.schema.json'

#: Every production TypeScript source that can render a showcase graph. The
#: sweep globs rather than naming files — see the module docstring.
#:
#: `*.check.ts` is EXCLUDED on purpose, for the reason `test_p8_format_scale.py`
#: gives: these guards look for text patterns, and a check file is full of them
#: deliberately. A guard that reads its own assertion text is the sixth failure
#: mode this project has.
SOURCES = sorted(
    src
    for src in (*SCHEMAS.rglob('*.ts'), *TEMPLATE.rglob('*.ts'), *TEMPLATE.rglob('*.tsx'))
    if not src.name.endswith('.check.ts')
)


def _top_level_schema_keys() -> set[str]:
    """Top-level properties declared by `ShowcaseSchema`, read from the SOURCE.

    Parsed out of the zod literal rather than by running zod, so this sweep does
    not depend on a node runtime — a Python-side guard that can still fail when
    node is unavailable is worth more than one that cannot.

    Matches the `.object({` marker, not a whole line: P11 defect 3 wrapped the
    declaration to attach `.strict()`, which moved the brace onto its own line.
    A parser pinned to the old spelling goes red on a refactor, and a guard that
    cries wolf on reshapes is a guard people stop reading. The body is bounded by
    "no intervening `export const`" rather than by the first `})`.
    """
    src = SHOWCASE_TS.read_text(encoding='utf-8')
    m = re.search(
        r'export const ShowcaseSchema = [^=]*?\.object\(\{\r?\n'
        r'((?:(?!export const)[\s\S])*?)'
        r'\r?\n  \}\)\r?\n  \.strict\(\);', src, re.S)
    assert m, (
        'could not find ShowcaseSchema in showcase-v1.ts. If the declaration was '
        'reshaped again, update this parser rather than reading the failure as a '
        'schema problem.')
    return set(re.findall(r'^\s{4}(\w+):', m.group(1), re.M))


def _read_of_docs(src: Path) -> list[tuple[int, str]]:
    """Fields read off a showcase document, as (line number, property name).

    Matches the three shapes a cast into a showcase document takes in this
    codebase, all of which are `as`-cast reads because the field is not on the
    inferred type:

      (doc as unknown as {foo?: ...}).foo
      (doc as any).foo
      doc['foo']          — bracket access on a parsed doc

    A `.foo` read WITHOUT a cast is deliberately not matched: if the field is
    declared, TypeScript checks it, and if it is not declared the file does not
    compile. The undeclared case can only survive by casting, so casting is
    exactly what is worth hunting.
    """
    text = src.read_text(encoding='utf-8')
    hits: list[tuple[int, str]] = []

    # `(x as unknown as {a?: T}).b` / `(x as any).b` — the cast names the shape,
    # so the property is read off the RIGHT of the paren, not the cast itself.
    # The cast body tolerates ONE level of nesting, because the real line was
    # `{ audio?: { src: string } }` — a `[^}]*?` body stops at the inner brace
    # and the guard silently matches nothing. A sweep that matches nothing is
    # worse than no sweep: it is a guard that reports green forever.
    body = r'\{(?:[^{}]|\{[^{}]*\})*\}'
    casted = re.compile(r'\bas\s+unknown\s+as\s*' + body + r'\s*\)\s*\.\s*(\w+)', re.S)
    for m in casted.finditer(text):
        hits.append((text[: m.start()].count('\n') + 1, m.group(1)))

    anycast = re.compile(r'\bas\s+any\)\s*\.\s*(\w+)')
    for m in anycast.finditer(text):
        hits.append((text[: m.start()].count('\n') + 1, m.group(1)))

    bracket = re.compile(r"""(?:doc|parsed\.data|rawProps)\s*\[\s*['"](\w+)['"]\s*\]""")
    for m in bracket.finditer(text):
        hits.append((text[: m.start()].count('\n') + 1, m.group(1)))

    return hits


# ── 1. the schema, read structurally ───────────────────────────────────────

def test_top_level_schema_keys_are_what_this_file_expects():
    """Anchors the sweep: if the schema's shape moves, this fails loudly rather
    than letting the guard below pass vacuously over a regex that no longer
    matches anything."""
    keys = _top_level_schema_keys()
    assert keys == {'version', 'project', '_note', 'style_bible', 'format', 'bpm', 'scenes'}, keys
    # The defect: `audio` is not among them, and that is the whole reason the
    # template's branch was dead. Asserted so the day someone wires it, this
    # file says so out loud.
    assert 'audio' not in keys
    # `_note` IS among them, as of P11 defect 3. It was previously absent and
    # stripped by zod, which meant a graph's provenance comment was legal on the
    # JSON Schema side in name only and had no declared type anywhere. It is now
    # declared on BOTH mirrors as `string`, and the comment below says why it is
    # allowed to be one of the few keys that is declared and never read.
    assert '_note' in keys


def test_no_production_source_reads_an_undeclared_showcase_field():
    """The sweep. Fails if any production file reads a field off a showcase
    document that the schema does not declare."""
    declared = _top_level_schema_keys()
    offences: list[str] = []
    for src in SOURCES:
        for line, field in _read_of_docs(src):
            if field not in declared:
                offences.append(
                    f'{src.relative_to(ROOT)}:{line} reads `{field}`, '
                    f'which ShowcaseSchema does not declare '
                    f'(declared: {sorted(declared)})')
    assert not offences, (
        'code reads a field the schema strips on parse — a silent failure, '
        'because safeParse still succeeds:\n  ' + '\n  '.join(offences))


def test_the_sweep_would_catch_the_defect_it_was_written_for():
    """The mutation contract, in the direction that matters: re-introduce the
    original cast and this file must notice.

    A guard that cannot demonstrate its own failure mode is a comment. This
    writes the exact line P11 deleted into a temporary copy of the template and
    re-runs the same reader over it.
    """
    declared = _top_level_schema_keys()
    original = "const audio = (doc as unknown as { audio?: { src: string } }).audio;"

    probe = TEMPLATE / '__probe_read.ts'
    try:
        probe.write_text(original + '\n', encoding='utf-8')
        found = _read_of_docs(probe)
        assert [f for _, f in found if f not in declared] == ['audio'], found
    finally:
        probe.unlink(missing_ok=True)


def test_the_delivered_graphs_declare_exactly_what_the_schema_declares():
    """A graph is authored against the schema, so an undeclared top-level key in
    a delivered graph is the other half of the same defect: it is silently
    dropped on the way to the renderer.

    `_note` is the one exception and it is checked as a KNOWN exception rather
    than waved through — it is a human-facing provenance note, not a graph
    field, and it is stripped rather than read by anything.
    """
    declared = _top_level_schema_keys()
    examples = ROOT / 'pipeline' / 'examples'
    for graph_path in sorted(examples.glob('*.json')):
        doc = json.loads(graph_path.read_text(encoding='utf-8-sig'))
        # `_note` is a provenance comment, not a graph field, and zod strips it
        # like any other undeclared key. It is ALLOWED here and nothing reads it;
        # the point of this test is that no unread key creeps back in wearing a
        # field's name.
        extra = sorted(set(doc) - declared - {'_note'})
        assert extra == [], (
            f'{graph_path.name} declares top-level {extra}, which ShowcaseSchema '
            f'strips on the way to the renderer')
        assert 'audio' not in doc, (
            f'{graph_path.name} sets top-level audio. It validates and renders '
            f'silent — that is the defect, reintroduced from the data side.')


# ── 2. runtime: the strip, measured rather than assumed ─────────────────────

_NPX = shutil.which('npx') or shutil.which('npx.cmd')

RUNTIME_PROBE = """
import {ShowcaseSchema} from './src/schemas/showcase-v1';

const base = (extra = {}) => ({
  version: 1,
  project: 'p',
  format: {width: 1920, height: 1080, fps: 60},
  scenes: [{id: 's01', type: 'kpi-hero', durationInFrames: 30}],
  ...extra,
});

const withAudio = base({audio: {src: 'audio/bgm_main.m4a', volume: 0.4}});
const r = ShowcaseSchema.safeParse(withAudio);
console.log(JSON.stringify({
  success: r.success,
  keys: r.success ? Object.keys(r.data) : [],
  audioSurvived: r.success ? ('audio' in r.data) : null,
}));
"""


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
def test_zod_rejects_an_undeclared_top_level_audio_at_runtime(tmp_path):
    """The measurement behind every comment in this file, re-taken.

    The source sweep proves nobody READS `audio`. This proves the other half --
    that zod REJECTS it, so a graph carrying `audio` cannot load at all.

    This assertion used to be `success is True` plus `audioSurvived is False`:
    the strip WAS the defect, and this test pinned it as the contract. That was
    the cost of leaving the two mirrors to disagree, and it was paid until P11
    defect 3 made both mirrors strict. `ShowcaseSchema` is `.strict()` now, so a
    re-added `.passthrough()` would be a live regression rather than a comment.

    If someone genuinely wants `audio` back, that is a feature request: it needs a
    declaration AND a reader, and this test is the thing that says so out loud.
    """
    probe = STUDIO / '__probe_audio.mts'
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
            f'zod ACCEPTS a top-level `audio` key: {got}. It is stripping again, '
            'which means a graph asking for a music bed would validate and render '
            'silent -- the P11 defect, reintroduced.')
        assert got['keys'] == [], got
    finally:
        probe.unlink(missing_ok=True)


# ── 3. the QA rule may not check a field nothing can produce ────────────────

def test_visual_qa_does_not_read_fields_the_renderer_cannot_receive():
    """`rule_missing_asset` used to read `props['audio']`, `props['audioEvents']`
    and `props['narration']` — none of which a showcase graph can carry into the
    renderer. A rule that checks a structurally impossible field manufactures
    coverage it does not have; this keeps it honest about what it checks.
    """
    src = (STUDIO / 'scripts' / 'visual_qa.py').read_text(encoding='utf-8')
    m = re.search(r'def rule_missing_asset\(props: dict\).*?(?=\ndef |\nclass )', src, re.S)
    assert m, 'rule_missing_asset not found'
    body = m.group(0)
    # strip comments and docstrings: the rule explains WHY it no longer reads
    # these, and a guard that matched its own explanation would pass forever.
    code = re.sub(r'"""(?:.|\n)*?"""', '', body)
    code = re.sub(r'#.*', '', code)
    for field in ("'audio'", "'audioEvents'", "'narration'"):
        assert field not in code, (
            f'rule_missing_asset reads props[{field}], a field no showcase graph '
            f'can deliver to the renderer: {body[:400]}')


def test_visual_qa_still_checks_the_sfx_it_can():
    """The narrowing must not become a no-op. These four are hardcoded in the
    components, so nothing in the graph reports a rename and this rule is the
    only thing that would catch one."""
    src = (STUDIO / 'scripts' / 'visual_qa.py').read_text(encoding='utf-8')
    m = re.search(r'def rule_missing_asset\(props: dict\).*?(?=\ndef |\nclass )', src, re.S)
    assert m, 'rule_missing_asset not found'
    body = m.group(0)
    for asset in ('audio/sfx_whoosh.m4a', 'audio/sfx_impact.m4a',
                  'audio/sfx_ding.m4a', 'audio/sfx_riser.m4a'):
        assert asset in body, f'{asset} is no longer checked; the rule is now empty'

    public = STUDIO / 'public'
    for asset in ('audio/sfx_whoosh.m4a', 'audio/sfx_impact.m4a',
                  'audio/sfx_ding.m4a', 'audio/sfx_riser.m4a'):
        assert (public / asset).exists(), f'{asset} is checked but not on disk'


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))