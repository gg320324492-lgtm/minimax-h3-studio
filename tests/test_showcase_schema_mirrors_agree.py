"""The two showcase-v1 mirrors must return the SAME VERDICT on the same graph (P11, defect 3).

THE DEFECT THIS EXISTS FOR.

`studio/src/schemas/showcase-v1.ts` (zod) and
`pipeline/schemas/showcase-v1.schema.json` (JSON Schema) are two spellings of one
contract, and they disagreed about unknown keys:

  * the zod side used bare `z.object({...})`, which silently STRIPS undeclared
    keys and still returns `success: true`;
  * the JSON Schema side set `additionalProperties: false` at six sites, so it
    REJECTED the same bytes.

Measured on the delivered graphs before the fix: `showcase_demo.json` passed zod
and failed the JSON Schema, on `_note`. That is the "silently ineffective field"
class the last three commits removed -- except here the field was not merely
ineffective, the two halves of the contract disagreed about whether it existed.

A SECOND, LARGER FINDING, FOUND ONLY BECAUSE THIS FILE RUNS A REAL VALIDATOR.

`definitions/Track` was referenced by eight properties (`Camera.translateX`,
`.translateY`, `.translateZ`, `.rotateX/Y/Z`, `.scale`, `.focus`) and defined
NOWHERE. So the schema could not be compiled by any conforming validator:

    can't resolve reference #/definitions/Track from id #

Nothing caught it because nothing ever RAN this file -- `test_showcase_schema_parity.py`
compares it with regexes. A schema that cannot compile is also a schema that can
never disagree with its mirror, because it never answers at all. That is not
safety, it is silence, and it is the reason the six `additionalProperties: false`
sites below were never measured against a real graph.

WHAT IS PROVEN HERE, AND WHAT IS NOT.

    Proven:  both mirrors ACCEPT every delivered graph, REJECT every graph carrying
             an undeclared key, and agree with each other on every case run.
    NOT proven: that the two mirrors are semantically identical in general. They
             are checked case by case, not by proof. A future field that differs
             in a way none of these cases exercise would NOT be caught here.

THE TRAPS THIS FILE IS BUILT AROUND.

  * A guard asserting a TOKEN APPEARS IN TEXT passes by reading its own comment.
    Both schema files now carry long explanations of the strip-versus-reject
    defect. So nothing below asserts a substring of either schema: every
    assertion runs the two validators on real documents.
  * `read_text`/`write_text` silently flips CRLF to LF, and both mirrors are CRLF.
    Nothing here writes them.
  * The comment in `showcase-v1.ts` explains that `_note` is stripped. A naive
    `assert '_note' not in parsed` would therefore be testing the comment's
    subject rather than the schema's behaviour.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / 'studio'
SCHEMAS = STUDIO / 'src' / 'schemas'
EXAMPLES = ROOT / 'pipeline' / 'examples'
TS_MIRROR = SCHEMAS / 'showcase-v1.ts'
JSON_SCHEMA = ROOT / 'pipeline' / 'schemas' / 'showcase-v1.schema.json'

_NPX = shutil.which('npx') or shutil.which('npx.cmd')
needs_node = pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')

#: The six sites where the JSON Schema declares `additionalProperties: false`.
#: Measured, not assumed -- `test_the_json_schema_is_strict_where_it_claims` proves
#: the value rather than trusting this list to still be right.
STRICT_SITES = [
    ('(root)', ()),
    ('/properties/format', ('properties', 'format')),
    ('/definitions/Scene', ('definitions', 'Scene')),
    ('/definitions/Camera', ('definitions', 'Camera')),
    ('/definitions/Motion', ('definitions', 'Motion')),
    ('/definitions/Transition', ('definitions', 'Transition')),
]

#: Object-valued bags that stay OPEN by design. Strictness covers the graph's own
#: vocabulary; these are free-form payload the scene components interpret, and
#: closing them would be a large breaking change to every delivered graph.
#:
#: `StyleBible` WAS on this list until P12 made it `.strict()` /
#: `additionalProperties: false`, and that is the one deliberate move between the
#: two kinds of object this schema contains. It is worth being precise about
#: which is which, because the distinction is what makes the change defensible:
#:
#:   * `Scene.layout` and `Scene.content` are keyed by whatever the scene
#:     components choose to interpret. Nothing enumerates them, so an unknown key
#:     there is a version skew between a scene and a graph, not a typo.
#:   * `StyleBible`'s TEN top-level keys are enumerated, declared, and consumed.
#:     The resolver binds each by name. So an unknown top-level key is not a
#:     payload a component might understand later -- it is a section that does
#:     not exist, and with stripping on it vanished without a word.
#:
#: The BAG INTERIOR is still open and is not touched by this: `palette.card`,
#: `spacing.gutter` and the rest remain free-form, because `mergeSection` filters
#: by the default's own keys. `additionalProperties: false` here governs the
#: style bible's top level only.
OPEN_BAGS = [
    ('Scene.layout', ('definitions', 'Scene', 'properties', 'layout')),
    ('Scene.content', ('definitions', 'Scene', 'properties', 'content')),
]


def _dig(doc: dict, path: tuple[str, ...]) -> dict:
    """Walk a path into the schema. An empty path is the document root."""
    node = doc
    for step in path:
        node = node[step]
    return node


# ── 1. structural: the schema is a schema ──────────────────────────────────

def test_the_json_schema_compiles():
    """THE FINDING. `$ref` to a definition that does not exist.

    Before P11 defect 3 this threw for every caller, so the file had never been
    validated by anything. The check is structural -- every `$ref` in the document
    resolves against a definition that is actually present -- because that is the
    property Ajv failed on, and it fails on it without needing node.
    """
    import re

    raw = JSON_SCHEMA.read_text(encoding='utf-8')
    refs = sorted(set(re.findall(r'"\$ref"\s*:\s*"([^"]+)"', raw)))
    assert refs, 'no $ref found at all -- is this still a $ref-based schema?'

    doc = json.loads(raw)
    defined = set(doc['definitions'])
    unresolved = [r for r in refs if r.rsplit('/', 1)[-1] not in defined]
    assert not unresolved, (
        f'the JSON Schema refs definitions that do not exist: {unresolved} '
        f'(defined: {sorted(defined)}). A validator cannot compile this, so it '
        'can never agree with the zod mirror -- it just never answers.')


def test_the_json_schema_is_strict_where_it_claims():
    """Six sites carry `additionalProperties: false`. Check the value, not the claim."""
    doc = json.loads(JSON_SCHEMA.read_text(encoding='utf-8'))
    wrong = []
    for name, path in STRICT_SITES:
        if _dig(doc, path).get('additionalProperties') is not False:
            wrong.append(name)
    assert not wrong, (
        f'these sites no longer reject unknown keys: {wrong}. Either zod has been '
        'relaxed to match, or these were edited without the other mirror being '
        'touched -- either way the two mirrors now disagree.')


def test_the_open_bags_are_still_open():
    """The other direction: closing a bag is a breaking change, so pin it too.

    A guard that only checked "strict" would go green if someone made
    `Scene.content` strict, which rejects every delivered graph.
    """
    doc = json.loads(JSON_SCHEMA.read_text(encoding='utf-8'))
    wrong = []
    for name, path in OPEN_BAGS:
        value = _dig(doc, path).get('additionalProperties')
        if value is False:
            wrong.append(name)
    assert not wrong, (
        f'these free-form bags are now closed: {wrong}. They are payload the '
        'scene components interpret, not graph vocabulary.')


# ── 2. runtime: BOTH validators, on real documents ─────────────────────────

#: One probe, one run: every case below, run through zod AND Ajv in the same
#: process, so "the mirrors agree" is a single measured fact rather than two
#: suites that could each drift.
AGREEMENT_PROBE = r"""
import fs from 'fs';
import Ajv from 'ajv';
import {ShowcaseSchema} from './src/schemas/showcase-v1';

const raw = JSON.parse(fs.readFileSync('../pipeline/schemas/showcase-v1.schema.json', 'utf8'));
let validate;
try {
  // strict:false only silences Ajv's OWN lint. The document is NOT patched:
  // before this change it could not compile at all.
  validate = new Ajv({strict: false}).compile(raw);
} catch (e) {
  console.log('JSONERROR ' + (e as Error).message);
  process.exit(0);
}

const base = () => ({
  version: 1,
  project: 'p',
  format: {width: 1920, height: 1080, fps: 60},
  scenes: [{id: 's01', type: 'kpi-hero', durationInFrames: 30}],
});
const withScene = (fn: (d: any) => void) => () => { const d = base(); fn(d); return d; };

const cases: Array<[string, any]> = [
  ['clean', base()],
  ['top-level unknown key', {...base(), typo: 1}],
  ['motion unknown key (the motion.ease defect)', withScene(d => { d.scenes[0].motion = {preset: 'premium', ease: 'expo-out'}; })()],
  ['camera unknown key', withScene(d => { d.scenes[0].camera = {translateX: [0, 10], easeZ: 2}; })()],
  ['scene unknown key', withScene(d => { d.scenes[0].ease = 'expo-out'; })()],
  ['transitionIn unknown key', withScene(d => { d.scenes[0].transitionIn = {in: 'fade', dur: 5}; })()],
  ['format unknown key', withScene(d => { d.format.aspectRatio = 16; })()],
  ['meta key _note', {...base(), _note: 'provenance'}],
  ['free-form content bag', withScene(d => { d.scenes[0].content = {anything: {nested: [1, 2]}}; })()],
  ['free-form layout bag', withScene(d => { d.scenes[0].layout = {whatever: true}; })()],
  ['style bible sections', {...base(), style_bible: {palette: {accent: '#f00'}, spacing: {gutter: 4}}}],
  ['camera constant track', withScene(d => { d.scenes[0].camera = {scale: 1.2}; })()],
  ['camera [from,to] track', withScene(d => { d.scenes[0].camera = {scale: [1, 1.2], perspective: 1200}; })()],
  ['camera 3-element track (invalid)', withScene(d => { d.scenes[0].camera = {scale: [1, 2, 3]}; })()],
  ['camera non-numeric track', withScene(d => { d.scenes[0].camera = {scale: 'big'}; })()],
  ['motion known keys only', withScene(d => { d.scenes[0].motion = {preset: 'minimal', stagger: 0.5}; })()],
  ['empty scenes array (invalid)', withScene(d => { d.scenes = []; })()],
  ['unknown scene type', withScene(d => { d.scenes[0].type = 'not-a-scene'; })()],
  ['wrong version', {...base(), version: 2}],
];

const out: any[] = [];
for (const [name, doc] of cases) {
  const z = ShowcaseSchema.safeParse(doc);
  const j = validate(doc);
  out.push({name, zod: z.success, jsonSchema: j === true, agree: z.success === (j === true)});
}

const delivered: any[] = [];
for (const f of fs.readdirSync('../pipeline/examples').filter((f) => f.endsWith('.json'))) {
  const doc = JSON.parse(fs.readFileSync('../pipeline/examples/' + f, 'utf8'));
  const z = ShowcaseSchema.safeParse(doc);
  const j = validate(doc);
  delivered.push({
    name: 'delivered:' + f,
    zod: z.success,
    jsonSchema: j === true,
    agree: z.success === (j === true),
  });
}

console.log('JSONRESULT ' + JSON.stringify({cases: out, delivered}));
"""


def _run_agreement_probe(tmp_path: Path) -> dict:
    """Run the probe and return its parsed result. Fails loudly on a bad run."""
    probe = STUDIO / '__probe_mirrors.mts'
    try:
        probe.write_text(AGREEMENT_PROBE, encoding='utf-8')
        proc = subprocess.run(
            [_NPX, 'tsx', str(probe)],
            cwd=STUDIO, capture_output=True, text=True, timeout=600,
            encoding='utf-8', errors='replace',
        )
        assert proc.returncode == 0, f'probe failed:\n{proc.stdout}\n{proc.stderr}'
        line = [ln for ln in proc.stdout.splitlines() if ln.startswith('JSONRESULT ')]
        assert line, f'no probe result:\n{proc.stdout}\n{proc.stderr}'
        payload = line[-1][len('JSONRESULT '):]
        parsed = json.loads(payload)
        assert 'error' not in parsed, (
            f'the JSON Schema did not compile: {parsed["error"]}')
        return parsed
    finally:
        probe.unlink(missing_ok=True)


@needs_node
def test_the_two_mirrors_return_the_same_verdict_on_every_case():
    """THE GUARD. Run both validators over the same documents and compare.

    Written as one probe that reports a verdict PAIR per case, so a disagreement
    is a data difference rather than two independent tests that each report their
    own truth and nobody notices the pair.
    """
    result = _run_agreement_probe(Path('.'))
    rows = result['cases'] + result['delivered']

    assert rows, 'the probe ran no cases -- a guard that checks nothing'
    disagree = [r for r in rows if not r['agree']]
    assert not disagree, (
        'the two mirrors disagree about the same bytes:\n  '
        + '\n  '.join(
            f"{r['name']}: zod={r['zod']} jsonSchema={r['jsonSchema']}" for r in disagree))


@needs_node
def test_a_graph_carrying_an_unknown_key_does_not_validate_on_either_side():
    """The property that makes a typo fail LOUDLY instead of silently.

    Asserting only agreement (above) would pass if both mirrors were permissive
    together, or both broken. This pins the direction: unknown key => rejected.
    """
    result = _run_agreement_probe(Path('.'))
    by_name = {r['name']: r for r in result['cases']}

    must_fail = [
        'top-level unknown key',
        'motion unknown key (the motion.ease defect)',
        'camera unknown key',
        'scene unknown key',
        'transitionIn unknown key',
        'format unknown key',
    ]
    for name in must_fail:
        assert name in by_name, f'probe lost the case {name!r}; it can no longer be measured'
        row = by_name[name]
        assert row['zod'] is False, (
            f'zod ACCEPTS a graph with an unknown key ({name}) -- it is stripping '
            'again, which is the defect this change removed')
        assert row['jsonSchema'] is False, (
            f'the JSON Schema ACCEPTS a graph with an unknown key ({name}) -- its '
            'additionalProperties:false was removed')

    must_pass = [
        'clean',
        'meta key _note',
        'free-form content bag',
        'free-form layout bag',
        'style bible sections',
        'camera constant track',
        'camera [from,to] track',
        'motion known keys only',
    ]
    for name in must_pass:
        assert name in by_name, f'probe lost the case {name!r}'
        row = by_name[name]
        assert row['zod'] is True and row['jsonSchema'] is True, (
            f'a legitimate graph is now rejected ({name}): {row}')


@needs_node
def test_every_delivered_graph_parses_on_both_sides():
    """The graphs people actually render must not have been broken by strictness."""
    result = _run_agreement_probe(Path('.'))
    delivered = result['delivered']
    assert delivered, 'no delivered graph was validated'
    bad = [r for r in delivered if not (r['zod'] and r['jsonSchema'])]
    assert not bad, (
        'full strictness rejects a delivered graph:\n  '
        + '\n  '.join(f"{r['name']}: zod={r['zod']} jsonSchema={r['jsonSchema']}" for r in bad))


@needs_node
def test_a_track_rejects_values_it_has_no_spelling_for():
    """`Track` is the one definition that was missing, so it gets its own check.

    It is also the one place where "strict" has no meaning: a tuple is not a
    vocabulary. What matters is that the repaired definition rejects what the zod
    union rejects, so a 3-element track cannot pass one mirror and fail the other.
    """
    result = _run_agreement_probe(Path('.'))
    by_name = {r['name']: r for r in result['cases']}

    for name in ('camera 3-element track (invalid)', 'camera non-numeric track'):
        assert name in by_name, f'probe lost the case {name!r}'
        row = by_name[name]
        assert row['zod'] is False and row['jsonSchema'] is False, (
            f'both mirrors must reject {name}: {row}')

    for name in ('camera constant track', 'camera [from,to] track'):
        assert name in by_name
        row = by_name[name]
        assert row['zod'] is True and row['jsonSchema'] is True, (
            f'both mirrors must accept {name}: {row}')


# ── 3. the guard can go red ────────────────────────────────────────────────

MUTATION_PROBE = r"""
import fs from 'fs';
import Ajv from 'ajv';
import {ShowcaseSchema} from './src/schemas/showcase-v1';

const raw = JSON.parse(fs.readFileSync('../pipeline/schemas/showcase-v1.schema.json', 'utf8'));
let validate: ((d: unknown) => boolean) | null = null;
let compileError = '';
try {
  validate = new Ajv({strict: false}).compile(raw);
} catch (e) {
  compileError = (e as Error).message;
}

const doc = () => ({
  version: 1,
  project: 'p',
  format: {width: 1920, height: 1080, fps: 60},
  scenes: [{id: 's01', type: 'kpi-hero', durationInFrames: 30,
            motion: {preset: 'premium', ease: 'expo-out'}}],
});
const d = doc();
console.log('JSONMUT ' + JSON.stringify({
  compileError,
  zod: ShowcaseSchema.safeParse(d).success,
  jsonSchema: validate ? validate(d) === true : false,
}));
"""


def _run_mutation_probe() -> dict:
    probe = STUDIO / '__probe_mut.mts'
    try:
        probe.write_text(MUTATION_PROBE, encoding='utf-8')
        proc = subprocess.run(
            [_NPX, 'tsx', str(probe)],
            cwd=STUDIO, capture_output=True, text=True, timeout=600,
            encoding='utf-8', errors='replace',
        )
        assert proc.returncode == 0, f'probe failed:\n{proc.stdout}\n{proc.stderr}'
        line = [ln for ln in proc.stdout.splitlines() if ln.startswith('JSONMUT ')]
        assert line, f'no probe result:\n{proc.stdout}\n{proc.stderr}'
        return json.loads(line[-1][len('JSONMUT '):])
    finally:
        probe.unlink(missing_ok=True)


@needs_node
def test_a_graph_with_an_unknown_key_is_rejected_by_both_mirrors_right_now():
    """The current tree, measured — so this file's own claims stay honest.

    Kept as a test rather than a comment because the whole argument of the change
    is that the unknown key is REJECTED. If a future edit relaxes one side, this
    goes red before the more structural tests get a chance to explain why.
    """
    got = _run_mutation_probe()
    assert got['compileError'] == '', (
        f'the JSON Schema does not compile any more: {got["compileError"]}')
    assert got['zod'] is False, (
        f'zod accepts a graph whose scene.motion carries `ease`: {got}')
    assert got['jsonSchema'] is False, (
        f'the JSON Schema accepts the same graph: {got}')


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))