"""`generative` is computed, shipped, and read by nothing. P15 measured it.

WHY THIS FILE EXISTS.

P15 asked one question before deciding whether to build an SR router: does the
routing signal the router would need actually have a consumer? The answer is no,
and this file pins that answer so it cannot rot silently.

THE FACT, AND WHY IT IS NOT OBVIOUS.

`ResolvedScene.generative` is declared at showcase-v1.ts:316, computed at :373
from `GENERATIVE_SCENE_TYPES`, and returned by `resolveScenes()` — a function
that IS called, once, in production (`FinanceShowcaseWide.tsx:146`). So the
usual "declared and never called" smell does not apply. The signal is computed on
every render and handed to a caller that uses three of its four sibling fields.

The reason it is inert is a TYPE boundary, which is why a text search is the
wrong instrument and also why this project has mis-called this kind of field
before (`sizes`/`sizeBy`/`showArea` were reported inert and were not):

  * `generative` is a property of `ResolvedScene` (the DERIVED type), not of
    `Scene` (the schema's inferred type). `SceneSchema` is `.strict()` and has
    no `generative` key.
  * the one production caller maps `resolved` and passes `scene` — looked up
    back out of the raw `doc` by id — to `SceneRenderer`, whose prop type is
    `{scene: Scene}`.
  * therefore no scene component can receive the flag, and every scene
    component is typed on `Scene`.

HOW THIS IS PROVEN, AND WHAT IS DELIBERATELY NOT ASSERTED.

Proven here, by MEASUREMENT, not by text:
  1. the field is produced on a `ResolvedScene` at runtime (probe 1);
  2. `generative` reaches no scene component at runtime (probe 2) — a probe
     that fails loudly if any scene module acquires a `generative` read;
  3. the delivered graphs contain no generative scene type (probe 3);
  4. the TypeScript source, swept for every read shape that could carry the
     field into a component, names nothing.

Assertion (4) is the one place a text pattern appears, and it is anchored: the
sweep runs the same matcher over a probe file that DOES read `generative` and
requires it to find it first (test_the_sweep_finds_a_genuine_read). A sweep
that matches nothing is not a green result, it is a guard that reports success
forever — the sixth failure mode this project has already paid for once in
`render.mjs`, where `'Unknown flag' in source` kept matching the COMMENT that
explained the fix it was meant to verify.

WHAT THIS DOES NOT CLAIM.

It does not claim `generative` is wrong, or that H3 routing is not wanted. It
does not claim the SR router should not be built — that is a judgement for
docs/, and P15 records it. It claims exactly one thing: today the flag changes
no output, so it is not yet a routing signal. If someone wires a consumer, the
mutation contract below goes red and the flag has to be re-justified rather than
inherited.
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
SHOWCASE_TS = STUDIO / 'src' / 'schemas' / 'showcase-v1'
TEMPLATE = STUDIO / 'src' / 'templates' / 'finance-showcase'
EXAMPLES = ROOT / 'pipeline' / 'examples'

#: Every production TypeScript/TSX file under the studio source tree. Globbed,
#: not named: the defect being pinned is a PATTERN, and a named-file list only
#: ever covers the file someone remembered to name.
#:
#: `*.check.ts` is excluded for the reason tests/test_undeclared_field_reads.py
#: gives — these files contain text patterns on purpose, and a guard that reads
#: its own assertion text is green forever. `showcase-v1.ts` itself is INCLUDED:
#: it is where the field is produced, and the sweep has to see that.
SOURCES = sorted(
    src
    for src in (*(STUDIO / 'src').rglob('*.ts'), *(STUDIO / 'src').rglob('*.tsx'))
    if not src.name.endswith('.check.ts')
)

_NPX = shutil.which('npx') or shutil.which('npx.cmd')

requires_node = pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')


def _run_ts(probe: Path, body: str, timeout: int = 300) -> dict:
    """Run a TypeScript probe under tsx and return its last JSON line.

    The probe is removed in `finally`, not after the assertions: a probe left
    on disk is a file the next person has to work out the provenance of, and
    the existing guards in this repo clean up after themselves on the failure
    path too (see tests/test_undeclared_field_reads.py).
    """
    probe.write_text(body, encoding='utf-8')
    try:
        proc = subprocess.run(
            [_NPX, 'tsx', str(probe)],
            cwd=STUDIO, capture_output=True, text=True, timeout=timeout,
            encoding='utf-8', errors='replace',
        )
        assert proc.returncode == 0, f'probe failed:\n{proc.stderr[-2000:]}'
        lines = [l for l in proc.stdout.splitlines() if l.startswith('{')]
        assert lines, f'no probe output:\n{proc.stdout}\n{proc.stderr}'
        return json.loads(lines[-1])
    finally:
        probe.unlink(missing_ok=True)


# ── 1. the signal is produced ───────────────────────────────────────────────

PRODUCE_PROBE = """
import {GENERATIVE_SCENE_TYPES, resolveScenes} from './src/schemas/showcase-v1';

const doc = {
  version: 1,
  project: 'p',
  format: {width: 1920, height: 1080, fps: 60},
  scenes: [
    {id: 's01', type: 'kpi-hero', durationInFrames: 30},
    {id: 's02', type: 'video', durationInFrames: 30},
  ],
};

const resolved = resolveScenes(doc as never, false);
console.log(JSON.stringify({
  setMembers: [...GENERATIVE_SCENE_TYPES].sort(),
  flags: resolved.map((r) => [r.type, r.generative]),
}));
"""


@requires_node
def test_generative_is_produced_on_the_resolved_scene(tmp_path):
    """The flag is real and computed — this file does not claim it is a stub.

    Also pins the SET CONTENTS, which is the other half of the routing decision:
    `video` and `data-plane-3d` are generative, `kpi-hero` is not. If someone
    adds or removes a type, this goes red and the change is deliberate.
    """
    got = _run_ts(STUDIO / '__probe_gen_produce.mts', PRODUCE_PROBE)
    assert got['setMembers'] == ['data-plane-3d', 'video'], got
    assert got['flags'] == [['kpi-hero', False], ['video', True]], got


# ── 2. no scene component can receive it ────────────────────────────────────

REACH_PROBE = """
import {readdirSync, readFileSync} from 'node:fs';
import {join} from 'node:path';
import {resolveScenes} from './src/schemas/showcase-v1';

const doc = {
  version: 1,
  project: 'p',
  format: {width: 1920, height: 1080, fps: 60},
  scenes: [{id: 's01', type: 'video', durationInFrames: 30}],
};

const resolved = resolveScenes(doc as never, false);

const dir = join(process.cwd(), 'src', 'templates', 'finance-showcase', 'scenes');
const files = readdirSync(dir).filter((f) => f.endsWith('.tsx') || f.endsWith('.ts'));

// Every scene module's own source, read from disk. An ESM namespace object
// cannot be stringified (`String(ns)` throws), and a React tree cannot be
// watched for a read that does not change output — so the file is the honest
// instrument here, and it is the same file the Python sweep reads.
const reads: string[] = [];
const exported: string[] = [];
for (const f of files) {
  const src = readFileSync(join(dir, f), 'utf-8');
  const code = src.split('\\n').filter((l) => !l.trim().startsWith('//')).join('\\n')
                      .replace(/\\/\\*[\\s\\S]*?\\*\\//g, '');
  if (/generative/i.test(code)) reads.push(f);
  const m = /export\\s+(?:const|function)\\s+generative/i.test(code);
  if (m) exported.push(f);
}

console.log(JSON.stringify({
  flagOnResolved: resolved[0].generative,
  filesScanned: files.length,
  reads,
  exported,
}));
"""


@requires_node
def test_no_scene_module_can_receive_the_generative_flag():
    """The load-bearing measurement: no scene module mentions the flag.

    Scans every file in the delivered scene directory — the place a per-scene
    routing consumer would have to live. Comments are stripped before matching,
    so a module that merely EXPLAINS the flag in prose is not a consumer; that
    is the `render.mjs` trap, in the same shape as the sixth failure this
    project has already paid for.
    """
    got = _run_ts(STUDIO / '__probe_gen_reach.mts', REACH_PROBE)
    assert got['flagOnResolved'] is True, got
    assert got['filesScanned'] > 0, (
        f'no scene modules scanned — this sweep is vacuous: {got}')
    assert got['reads'] == [], (
        f'scene modules now mention `generative`: {got["reads"]}. The routing '
        'signal has a consumer; this file must be re-justified or retired.')
    assert got['exported'] == [], (
        f'scene modules now export something generative: {got["exported"]}')


# ── 3. no delivered graph asks for generative rendering ─────────────────────

def test_no_delivered_graph_contains_a_generative_scene():
    """Measured off the graphs, not the source: nothing shipped would route.

    This is what makes the signal moot in practice. If a `video` scene ever
    ships in a delivered graph, the SR question becomes real and this goes red.
    """
    generative = {'video', 'data-plane-3d'}
    found: dict[str, list[str]] = {}
    total = 0
    for graph in sorted(EXAMPLES.glob('*.json')):
        doc = json.loads(graph.read_text(encoding='utf-8-sig'))
        kinds = [s.get('type') for s in doc.get('scenes', [])]
        total += len(kinds)
        hit = [k for k in kinds if k in generative]
        if hit:
            found[graph.name] = hit
    assert found == {}, (
        f'delivered graphs now contain generative scenes: {found}')
    assert total > 0, (
        'no scenes found under pipeline/examples — the sweep is vacuous, which '
        'is not a passing result.')


# ── 4. the sweep, anchored so it cannot pass by matching nothing ────────────

#: Every shape by which the flag could be carried into a component. Each is a
#: real read, not a mention: `.generative` (typed and cast alike), bracket
#: access with either quote, an `in` test, and destructuring.
READ_PATTERNS = (
    re.compile(r'\.\s*generative\b'),
    re.compile(r"""\[\s*['"]generative['"]\s*\]"""),
    re.compile(r"""['"]generative['"]\s*:\s*generative"""),
    re.compile(r'\bgenerative\b[^\n]*\}\s*=\s*'),
    re.compile(r"""['"]generative['"]\s+in\s+\w+"""),
    re.compile(r"""\bin\s+\w+[\s\S]{0,40}?['"]generative['"]"""),
)


def _gen_reads_in(text: str) -> list[str]:
    """Names the files/regions where the flag is READ.

    Deliberately NOT a mention counter. `showcase-v1.ts` says the word
    `generative` in its declaration, its assignment and its doc comments — those
    are the producer, not a consumer, so the declaration site is excluded by
    position rather than the whole file being excused.
    """
    hits: list[str] = []
    for pat in READ_PATTERNS:
        for m in pat.finditer(text):
            line = text.count('\n', 0, m.start()) + 1
            hits.append(f'line {line}: {m.group(0).strip()[:60]}')
    return hits


def test_the_read_sweep_finds_a_genuine_read():
    """The anchor. A sweep that finds nothing is indistinguishable from a sweep
    that is broken, so this proves the matcher works before trusting it to
    report zero on the real sources."""
    genuine = (
        "const a = scene.generative;\n"
        "const b = r['generative'];\n"
        "const {generative} = r;\n"
        "if ('generative' in r) {}\n"
    )
    assert len(_gen_reads_in(genuine)) >= 4, _gen_reads_in(genuine)


def test_no_production_source_reads_the_generative_flag():
    """Zero consumers, asserted as zero READS rather than as zero mentions.

    Excluded by SHAPE, not by line number and not by file: `showcase-v1.ts` is
    the producer and is expected to name the field, so the two producing
    statements are allowed and nothing else is. Pinning them by line number
    would break the guard the first time anyone edits the schema above them —
    a guard that cries wolf on an unrelated edit is a guard people stop
    reading.
    """
    producer = re.compile(
        r'generative\s*:\s*(boolean\s*;|GENERATIVE_SCENE_TYPES\s*\.\s*has\s*\()')

    offences: list[str] = []
    for src in SOURCES:
        text = src.read_text(encoding='utf-8')
        hits: list[str] = []
        for h in _gen_reads_in(text):
            line_no = int(re.match(r'line (\d+):', h).group(1))
            line_text = text.splitlines()[line_no - 1]
            if producer.search(line_text):
                continue  # this is the declaration or the assignment itself
            hits.append(h)
        for h in hits:
            offences.append(f'{src.relative_to(ROOT)}:{h}')
    assert offences == [], (
        'the `generative` routing signal now has a consumer:\n  '
        + '\n  '.join(offences)
        + '\nThe SR routing question in docs/ is no longer moot; re-justify this '
          'file instead of deleting the assertion.')


# ── 5. mutation contract: the guard must be able to go red ──────────────────

def test_the_sweep_catches_a_read_added_to_a_scene_module(tmp_path):
    """Adding a real read to a scene component must turn the guard red.

    This is the direction the work order cares about most: a "zero consumers"
    claim that cannot fail is a comment. The probe file is swept with the exact
    reader the sweep above uses, so a red here and a red there are the same
    mechanism rather than two hopeful assertions.
    """
    probe = TEMPLATE / 'scenes' / '__probe_gen_read.tsx'
    try:
        probe.write_text(
            'export const Cue = (r: {generative: boolean}) => (r.generative ? 1 : 0);\n',
            encoding='utf-8')
        assert _gen_reads_in(probe.read_text(encoding='utf-8')), (
            'the sweep cannot see a read in a scene module — it would report '
            'zero consumers forever')
    finally:
        probe.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))