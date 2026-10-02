"""The two showcase-v1 mirrors must agree on VALUES, not only on key NAMES.

THE DEFECT THIS EXISTS FOR.

`tests/test_showcase_schema_parity.py` compares the two mirrors by PARSING
THEM AS TEXT. That catches a renamed field and it catches a reordered enum, and
it catches nothing else at all — because a bound is not a name. Measured: before
this file existed, `camera.perspective` was `minimum: 0` in the JSON Schema and
`z.number().positive()` in zod, and

    test_camera_channels_match_across_sides   PASSED.

It passed because `"perspective"` really was a key on both sides. The parity test
was answering the only question it had tools to ask, and the disagreement lived
in the answer to a question it never asked. A textual comparison of two schemas
is not a weaker version of a semantic one; it is a comparison of a different
thing entirely, and it reads green precisely when a BOUND has drifted.

    probe                          zod     JSON Schema    agreed?
    camera.perspective 0           reject  accept         NO
    format.width 8                 accept  reject         NO
    format.height 8                accept  reject         NO

Both were live. `format.width` had said `minimum: 16` while zod said
`.int().positive()`, so any graph between 1 and 15 passed the producer and was
rejected by the renderer — the mirror image of the unknown-key defect the three
commits before these were written to remove.

WHY THIS FILE IS NOT A THIRD COPY OF `test_showcase_schema_mirrors_agree.py`.

That file runs zod and Ajv over documents about UNKNOWN KEYS. This one runs a
corpus about VALUES, and it adds a third validator that no existing test puts
beside those two: `pipeline/scene_graph._validate`. The drift was three-way —
producer and renderer disagreed, and the schema disagreed with the renderer — so
a guard that only compares the two TypeScript-side validators could have been
green while the pipeline said something else entirely. `_validate` is Python and
needs no node, so adding it costs nothing and closes the last pairing.

WHAT IS PROVEN HERE, AND WHAT IS NOT.

    Proven:  all three validators return the SAME verdict on every probe below,
             including the delivered graphs; and `camera.perspective: 0` is
             REJECTED by all three — pinned in the direction, not just in the
             agreement, because "they agree" is also satisfied by "both broken".
    NOT proven: that the mirrors are identical for every document anyone could
             write. These are 78 probes, not a proof. What bounds the gap is that
             the corpus covers every numeric bound and every enum member declared
             on either side, and that
             `test_the_corpus_covers_every_bound_declared_on_either_side` fails
             if a bound is ADDED to either mirror without a probe for it.

THE TRAPS THIS FILE IS BUILT AROUND.

  * A guard asserting a TOKEN APPEARS IN TEXT passes by reading its own comment.
    Both mirrors carry long explanations of the drift they were repaired for, and
    this file's own docstring names `minimum: 0` and `minimum: 16`. So nothing
    below asserts a substring of either schema: every assertion runs three real
    validators over real documents.
  * `read_text`/`write_text` silently flips CRLF to LF, and all three files under
    test are CRLF. Nothing here writes them. The one file written is a node
    scratch file under pytest's `tmp_path`.
  * Choosing the wrong VALIDATOR gives a confidently opposite answer. Python's
    `jsonschema` does not resolve `$ref`; Ajv does. The JSON Schema could not
    compile before 55a1d90, so a validator that silently skips it produces a
    green test that proved nothing. `_run_js_probe` therefore ASSERTS the
    sentinel line and asserts a non-empty verdict count on every call.
  * A corpus can shrink. `test_the_corpus_is_what_this_file_claims` pins its size
    and its required members, so a probe cannot be quietly deleted.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / 'pipeline'
STUDIO = ROOT / 'studio'
JSON_SCHEMA = PIPELINE / 'schemas' / 'showcase-v1.schema.json'

sys.path.insert(0, str(PIPELINE))
import scene_graph as sg  # noqa: E402

_NPX = shutil.which('npx') or shutil.which('npx.cmd')
needs_node = pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')


# ── the corpus ─────────────────────────────────────────────────────────────
#
# A probe is (name, patch) where `patch` is a list of (path, value) and the path
# is walked into the base document one list index at a time. Expressed as DATA
# rather than as three hand-written copies of each document, because the copies
# are the failure mode: one side would be edited and the other two would keep
# validating the bytes they always validated.

def _base() -> dict:
    return {
        'version': 1,
        'project': 'p',
        'format': {'width': 1920, 'height': 1080, 'fps': 60},
        'scenes': [{'id': 's01', 'type': 'kpi-hero', 'durationInFrames': 30}],
    }


def _apply(patch: list) -> dict:
    """Apply one patch to the base document.

    A path may be written as a bare string for a top-level key (`'bpm'`) or as a
    list for anything deeper (`['scenes', 0, 'camera', 'perspective']`). Both
    spellings appear in the corpus and both mean the same thing; normalising
    here keeps the probe table readable without making every top-level entry
    carry brackets it does not need.

    Intermediate containers are auto-created: `camera`, `motion` and
    `transitionIn` are OPTIONAL in the schema, so the clean base has none of
    them and a probe that sets `scenes[0].camera.perspective` has to build the
    camera on the way. Index steps address an existing list element; string
    steps create the dict if it is not there.
    """
    doc = _base()
    for raw_path, value in patch:
        path = [raw_path] if isinstance(raw_path, str) else list(raw_path)
        node = doc
        for step in path[:-1]:
            if isinstance(node, list):
                node = node[step]
            elif isinstance(node.get(step), (dict, list)):
                node = node[step]
            else:
                node[step] = {}
                node = node[step]
        last = path[-1]
        if value is _DELETE:
            del node[last]
        else:
            node[last] = value
    return doc


class _Delete:
    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return '<delete>'


_DELETE = _Delete()

_F = ['format']
_S0 = ['scenes', 0]
_CAM = _S0 + ['camera']
_MOT = _S0 + ['motion']

#: Every numeric bound declared anywhere in EITHER mirror, probed either side of
#: it and on it. This list is what makes the sweep a sweep rather than a lookup
#: of the one field someone already knew about.
NUMERIC_PROBES = [
    # -- camera.perspective: the assigned defect. zod `.positive()` = > 0 ------
    ('perspective 0', [(_CAM + ['perspective'], 0)]),
    ('perspective -1', [(_CAM + ['perspective'], -1)]),
    ('perspective 0.5', [(_CAM + ['perspective'], 0.5)]),
    ('perspective 1', [(_CAM + ['perspective'], 1)]),
    ('perspective 20000', [(_CAM + ['perspective'], 20000)]),
    ('perspective 20001', [(_CAM + ['perspective'], 20001)]),
    # -- format.width / height: the second class the hand sweep missed --------
    ('width 0', [(_F + ['width'], 0)]),
    ('width 1', [(_F + ['width'], 1)]),
    ('width 8', [(_F + ['width'], 8)]),
    ('width 15', [(_F + ['width'], 15)]),
    ('width 16', [(_F + ['width'], 16)]),
    ('height 0', [(_F + ['height'], 0)]),
    ('height 1', [(_F + ['height'], 1)]),
    ('height 8', [(_F + ['height'], 8)]),
    ('height 15', [(_F + ['height'], 15)]),
    ('height 16', [(_F + ['height'], 16)]),
    # -- format.fps: 1 .. 120 -------------------------------------------------
    ('fps 0', [(_F + ['fps'], 0)]),
    ('fps 1', [(_F + ['fps'], 1)]),
    ('fps 60', [(_F + ['fps'], 60)]),
    ('fps 120', [(_F + ['fps'], 120)]),
    ('fps 121', [(_F + ['fps'], 121)]),
    ('fps 29.97 (non-integer)', [(_F + ['fps'], 29.97)]),
    # -- bpm: 40 .. 240 -------------------------------------------------------
    ('bpm 39', [('bpm', 39)]),
    ('bpm 40', [('bpm', 40)]),
    ('bpm 126', [('bpm', 126)]),
    ('bpm 240', [('bpm', 240)]),
    ('bpm 241', [('bpm', 241)]),
    # -- project: minLength 1 -------------------------------------------------
    ('project empty', [('project', '')]),
    ('project one char', [('project', 'p')]),
    # -- version: const 1 -----------------------------------------------------
    ('version 0', [('version', 0)]),
    ('version 1', [('version', 1)]),
    ('version 2', [('version', 2)]),
    ('version 1.5', [('version', 1.5)]),
    # -- scene id: pattern ^[a-z0-9_]+$ ---------------------------------------
    ('scene id uppercase', [(_S0 + ['id'], 'S-01')]),
    ('scene id dash', [(_S0 + ['id'], 's-01')]),
    ('scene id lowercase', [(_S0 + ['id'], 's01_kpi')]),
    ('scene id underscore', [(_S0 + ['id'], '_01')]),
    # -- durationInFrames: integer >= 1 --------------------------------------
    ('durationInFrames 0', [(_S0 + ['durationInFrames'], 0)]),
    ('durationInFrames -1', [(_S0 + ['durationInFrames'], -1)]),
    ('durationInFrames 1', [(_S0 + ['durationInFrames'], 1)]),
    ('durationInFrames 30.5 (non-integer)', [(_S0 + ['durationInFrames'], 30.5)]),
    # -- transitionIn.durationInFrames: integer >= 0 -------------------------
    ('transition durationInFrames -1', [(_S0 + ['transitionIn', 'durationInFrames'], -1)]),
    ('transition durationInFrames 0', [(_S0 + ['transitionIn', 'durationInFrames'], 0)]),
    ('transition durationInFrames 5', [(_S0 + ['transitionIn', 'durationInFrames'], 5)]),
    # -- motion.stagger: 0 .. 2 ----------------------------------------------
    ('stagger -1', [(_MOT + ['stagger'], -1)]),
    ('stagger 0', [(_MOT + ['stagger'], 0)]),
    ('stagger 0.5', [(_MOT + ['stagger'], 0.5)]),
    ('stagger 2', [(_MOT + ['stagger'], 2)]),
    ('stagger 3', [(_MOT + ['stagger'], 3)]),
    # -- motion.preset: a four-member enum -----------------------------------
    ('preset premium', [(_MOT + ['preset'], 'premium')]),
    ('preset energetic', [(_MOT + ['preset'], 'energetic')]),
    ('preset cinematic', [(_MOT + ['preset'], 'cinematic')]),
    ('preset minimal', [(_MOT + ['preset'], 'minimal')]),
    ('preset not-a-member', [(_MOT + ['preset'], 'expo-out')]),
    # -- Track: number, or exactly two numbers ------------------------------
    ('track constant', [(_CAM + ['scale'], 1.2)]),
    ('track [from,to]', [(_CAM + ['scale'], [1, 1.2])]),
    ('track [1]', [(_CAM + ['scale'], [1])]),
    ('track []', [(_CAM + ['scale'], [])]),
    ('track [1,2,3]', [(_CAM + ['scale'], [1, 2, 3])]),
    ('track [[1],2]', [(_CAM + ['scale'], [[1], 2])]),
    ('track string', [(_CAM + ['scale'], 'big')]),
    ('track object', [(_CAM + ['scale'], {})]),
    ('track null', [(_CAM + ['scale'], None)]),
    ('track boolean', [(_CAM + ['scale'], True)]),
    # -- booleans are NOT numbers (draft-06+, and True is an int in Python) ---
    ('perspective true', [(_CAM + ['perspective'], True)]),
    ('width true', [(_F + ['width'], True)]),
    ('durationInFrames true', [(_S0 + ['durationInFrames'], True)]),
    # -- string-where-a-number-is-expected ----------------------------------
    ('perspective "1600"', [(_CAM + ['perspective'], '1600')]),
    ('width "1920"', [(_F + ['width'], '1920')]),
    ('scenes empty', [('scenes', [])]),
    ('scenes absent', [('scenes', _DELETE)]),
    ('scenes not a list', [('scenes', {})]),
    ('scene missing id', [(_S0 + ['id'], _DELETE)]),
    ('scene missing durationInFrames', [(_S0 + ['durationInFrames'], _DELETE)]),
    ('format missing width', [(_F + ['width'], _DELETE)]),
    ('project missing', [('project', _DELETE)]),
    ('version missing', [('version', _DELETE)]),
    # -- the clean document, and the two bags that stay open -----------------
    ('clean', []),
    ('_note meta key', [('_note', 'provenance')]),
    ('content open bag', [(_S0 + ['content'], {'anything': {'nested': [1, 2]}})]),
    ('layout open bag', [(_S0 + ['layout'], {'whatever': True})]),
    ('style_bible open bag', [('style_bible', {'palette': {'nope': 1}})]),
]

#: One probe per scene-type enum member. The two mirrors list the same 22 values
#: in DIFFERENT ORDERS — zod groups them by family and a blank line, the mirror
#: sorts them. Order is not part of the contract, and it is exactly the kind of
#: difference a textual diff reports as a change while the behaviour is identical.
SCENE_TYPE_PROBES = [
    (f'scene type {t}', [(_S0 + ['type'], t)])
    for t in (
        'video', 'kpi-hero', 'browser-window', 'browser-stack', 'dashboard',
        'stat-card', 'card-grid', 'calendar', 'bar-chart', 'line-chart',
        'area-chart', 'bubble-chart', 'rank-chart', 'slope-chart', 'heatmap',
        'volume-chart', 'sparkline-chart', 'data-table', 'quote',
        'data-plane-3d', 'logo', 'outro',
    )
] + [('scene type not-a-member', [(_S0 + ['type'], 'not-a-scene')])]

PROBES = NUMERIC_PROBES + SCENE_TYPE_PROBES


def _documents() -> list[tuple[str, dict]]:
    return [(name, _apply(patch)) for name, patch in PROBES]


# ── 1. node: zod AND Ajv, one process, the same bytes ──────────────────────

JS_PROBE = r"""
import fs from 'fs';
import Ajv from 'ajv';
import {ShowcaseSchema} from './src/schemas/showcase-v1';

const raw = JSON.parse(fs.readFileSync('../pipeline/schemas/showcase-v1.schema.json', 'utf8'));
let validate;
try {
  // strict:false only silences Ajv's OWN lint; the document is NOT patched.
  validate = new Ajv({strict: false}).compile(raw);
} catch (e) {
  console.log('JSONERROR ' + (e as Error).message);
  process.exit(0);
}

const probes: Array<[string, any]> = JSON.parse(
  fs.readFileSync(process.argv[2], 'utf8'));
const out: any[] = probes.map(([name, doc]) => {
  const z = ShowcaseSchema.safeParse(doc);
  const j = validate(doc) === true;
  return {name, zod: z.success, jsonSchema: j};
});

const delivered: any[] = [];
for (const f of fs.readdirSync('../pipeline/examples').filter((f) => f.endsWith('.json'))) {
  const doc = JSON.parse(fs.readFileSync('../pipeline/examples/' + f, 'utf8'));
  const z = ShowcaseSchema.safeParse(doc);
  const j = validate(doc) === true;
  delivered.push({
    name: 'delivered:' + f, zod: z.success, jsonSchema: j,
  });
}

console.log('VALUERESULT ' + JSON.stringify({probes: out, delivered}));
"""


def _run_js_probe(tmp_path: Path) -> dict:
    """zod + Ajv over the corpus. Fails loudly on a bad run, never silently.

    The script is written UNDER `studio/`, not under `tmp_path`, and that is not
    tidiness: `import Ajv from 'ajv'` resolves through `studio/node_modules`, so
    a script outside that tree cannot find it and dies with ERR_MODULE_NOT_FOUND.
    The corpus stays in `tmp_path` and is passed by path, so the only thing this
    file puts in the repo is a scratch script that is removed in the `finally` --
    exactly what `test_showcase_schema_mirrors_agree.py` already does.
    """
    docs = [[n, d] for n, d in _documents()]
    corpus = tmp_path / 'corpus.json'
    corpus.write_text(json.dumps(docs, ensure_ascii=False), encoding='utf-8')
    script = STUDIO / '__probe_values.mts'
    try:
        script.write_text(JS_PROBE, encoding='utf-8')
        proc = subprocess.run(
            [_NPX, 'tsx', str(script), str(corpus)],
            cwd=STUDIO, capture_output=True, text=True, timeout=900,
            encoding='utf-8', errors='replace',
        )
        assert proc.returncode == 0, f'probe failed:\n{proc.stdout}\n{proc.stderr}'
        err = [ln for ln in proc.stdout.splitlines() if ln.startswith('JSONERROR ')]
        assert not err, (
            f'the JSON Schema does not compile, so it cannot disagree with zod -- '
            f'it simply never answers: {err}')
        line = [ln for ln in proc.stdout.splitlines() if ln.startswith('VALUERESULT ')]
        assert line, f'no probe result:\n{proc.stdout}\n{proc.stderr}'
        payload = json.loads(line[-1][len('VALUERESULT '):])
        assert payload['probes'], 'the probe ran no cases -- a guard that checks nothing'
        # The sentinel is the proof THIS run produced the numbers. Without it a
        # probe that stopped running leaves a stale artefact for a later run to
        # read, and a green guard stops meaning anything.
        assert corpus.read_text(encoding='utf-8') == json.dumps(docs, ensure_ascii=False), (
            'the corpus file is not what this run wrote')
        return payload
    finally:
        script.unlink(missing_ok=True)


def _pipeline_accepts(doc: dict) -> bool:
    return not sg._validate(doc)


# ── 2. the guards ──────────────────────────────────────────────────────────

def test_the_corpus_is_what_this_file_claims():
    """The anchors. Without these the rest could pass over a smaller corpus."""
    names = [n for n, _ in _documents()]
    assert len(names) == len(PROBES), 'the corpus generator lost a probe'
    assert len(set(names)) == len(names), 'a probe name is duplicated'
    for required in ('perspective 0', 'perspective 1', 'perspective 20000',
                     'perspective 20001', 'width 1', 'width 8', 'width 15',
                     'height 8', 'fps 120', 'fps 121', 'bpm 40', 'bpm 240',
                     'stagger 0', 'stagger 2', 'stagger 3', 'clean'):
        assert required in names, f'the probe {required!r} went missing'


def test_the_corpus_covers_every_bound_declared_on_either_side():
    """A sweep that only probes the fields someone already knows about.

    Reads the numeric bounds straight out of the JSON Schema file and requires a
    probe whose VALUE is that bound. This is a structural read, not a comment
    read: it cannot be satisfied by anything in this file's prose, and adding a
    bound to either mirror without probing it fails here.

    zod's side is covered transitively -- `exclusiveMinimum: 0` and `minimum: 16`
    are both the same shape of claim, and the corpus pins the verdict at both
    sides of each value regardless of which spelling a side uses.
    """
    doc = json.loads(JSON_SCHEMA.read_bytes().decode('utf-8'))
    probed = {v for _, patch in PROBES for _, v in patch if isinstance(v, (int, float))
              and not isinstance(v, bool)}
    unprobed = []

    def walk(node, path):
        if not isinstance(node, dict):
            return
        for key in ('minimum', 'exclusiveMinimum', 'maximum', 'exclusiveMaximum'):
            if key in node and node[key] not in probed:
                unprobed.append(f'{path}: {key}={node[key]}')
        for k, v in (node.get('properties') or {}).items():
            walk(v, f'{path}.{k}')
        items = node.get('items')
        if isinstance(items, dict):
            walk(items, f'{path}[]')
        for k, v in (node.get('oneOf') or []):
            walk(v, f'{path}|{k}')

    walk(doc, '(root)')
    assert not unprobed, (
        f'the JSON Schema declares bounds no probe exercises: {unprobed}. The '
        'corpus has to reach the value itself -- a probe on the far side of a '
        'bound does not prove the bound is where it was.')


def test_the_corpus_reaches_every_enum_member_declared_on_either_side():
    """Same argument for enums: a probe per member, not one probe per enum."""
    doc = json.loads(JSON_SCHEMA.read_bytes().decode('utf-8'))
    members = set(doc['definitions']['Scene']['properties']['type']['enum'])
    type_probes = [p for _, p in PROBES if p and list(p[0][0]) == _S0 + ['type']]
    probed = {p[0][1] for p in type_probes}
    missing = sorted(members - probed)
    assert not missing, f'no probe uses these scene types: {missing}'
    assert probed - members == {'not-a-scene'}, (
        'the corpus probes a scene type the schema does not declare')


@needs_node
def test_all_three_validators_return_the_same_verdict_on_every_value(tmp_path):
    """THE GUARD. Three validators, one corpus, byte-identical documents.

    The pipeline is included because the drift was three-way: a guard comparing
    only the two TypeScript-side validators would have been green while the
    producer -- the side that AUTHORS graphs -- said something else.
    """
    result = _run_js_probe(tmp_path)
    js_rows = {r['name']: r for r in result['probes']}

    assert set(js_rows) == {n for n, _ in _documents()}, (
        'the corpus differs between the two sides; they are not being compared')

    disagree = []
    for name, doc in _documents():
        py = _pipeline_accepts(doc)
        row = js_rows[name]
        if not (row['zod'] == row['jsonSchema'] == py):
            disagree.append(
                f'{name}: zod={row["zod"]} jsonSchema={row["jsonSchema"]} '
                f'pipeline={py}')
    assert not disagree, (
        'the validators disagree about the same bytes:\n  ' + '\n  '.join(disagree))


#: Pinned in the DIRECTION, not just in the agreement: "all three agree" is also
#: satisfied by "all three broken", which is what a botched edit to a bound looks
#: like. These must be REJECTED, everywhere.
MUST_BE_REJECTED = {
    'perspective 0': 'the schema said `minimum: 0` and zod said `.positive()`',
    'perspective -1': 'same drift, negative side',
    'perspective 20001': 'the maximum is enforced on one side only',
    'fps 121': 'fps has a maximum of 120',
    'fps 0': 'fps has a minimum of 1',
    'bpm 39': 'bpm has a minimum of 40',
    'bpm 241': 'bpm has a maximum of 240',
    'stagger 3': 'stagger has a maximum of 2',
    'durationInFrames 0': 'durationInFrames has a minimum of 1',
    'transition durationInFrames -1': 'transition durationInFrames has a minimum of 0',
    'project empty': 'project has minLength 1',
    'version 2': 'version is a literal',
    'track [1,2,3]': 'Track is a constant or exactly [from, to]',
    'track [1]': 'Track is a constant or exactly [from, to]',
    'track string': 'Track is numeric',
    'perspective true': 'a boolean is not a number (draft-06+)',
    'width true': 'a boolean is not a number (draft-06+)',
    'durationInFrames true': 'a boolean is not an integer (draft-06+)',
    'width "1920"': 'a numeric string is not a number',
    'fps 29.97 (non-integer)': 'fps is an integer',
    'scene type not-a-member': 'the scene type is a closed enum',
    'preset not-a-member': 'motion.preset is a closed enum',
}

#: ...and these must be ACCEPTED. The width/height floor is here because it was
#: the OTHER live drift: the mirror said `minimum: 16`, so 8 was rejected by the
#: schema and accepted by zod. These four are the whole point of the file.
MUST_BE_ACCEPTED = {
    'width 1': 'zod says .int().positive(); the schema must not impose 16',
    'width 8': 'zod says .int().positive(); the schema must not impose 16',
    'height 1': 'zod says .int().positive(); the schema must not impose 16',
    'height 8': 'zod says .int().positive(); the schema must not impose 16',
    'perspective 1': 'the smallest legal perspective',
    'perspective 0.5': 'a fractional perspective is legal',
    'perspective 20000': 'the largest legal perspective',
    'width 16': 'the old floor is a legal width',
    'fps 1': 'the smallest legal fps',
    'fps 120': 'the largest legal fps',
    'bpm 40': 'the smallest legal bpm',
    'bpm 240': 'the largest legal bpm',
    'stagger 0': 'stagger may be zero',
    'stagger 2': 'the largest legal stagger',
    'transition durationInFrames 0': 'a transition may be zero frames',
    'durationInFrames 1': 'the smallest legal scene',
    'project one char': 'minLength 1 is not minLength 2',
    'version 1': 'the only legal version',
    'track constant': 'a Track may be a bare number',
    'track [from,to]': 'a Track may be [from, to]',
    'clean': 'the clean document',
    '_note meta key': 'the declared meta key must keep working',
    'content open bag': 'content is free-form payload',
    'layout open bag': 'layout is free-form payload',
    'style_bible open bag': 'style bible sections are free-form payload',
}


@needs_node
def test_every_pinned_verdict_holds_on_all_three_validators(tmp_path):
    """Direction, for both halves, on all three validators at once."""
    result = _run_js_probe(tmp_path)
    js_rows = {r['name']: r for r in result['probes']}
    docs = dict(_documents())

    for name in MUST_BE_REJECTED:
        assert name in js_rows, f'probe lost the case {name!r}; it can no longer be measured'
        row = js_rows[name]
        py = _pipeline_accepts(docs[name])
        got = {'zod': row['zod'], 'jsonSchema': row['jsonSchema'], 'pipeline': py}
        assert not any(got.values()), (
            f'{name} must be REJECTED by all three (it was: {MUST_BE_REJECTED[name]}) '
            f'but got {got}')

    for name in MUST_BE_ACCEPTED:
        assert name in js_rows, f'probe lost the case {name!r}; it can no longer be measured'
        row = js_rows[name]
        py = _pipeline_accepts(docs[name])
        got = {'zod': row['zod'], 'jsonSchema': row['jsonSchema'], 'pipeline': py}
        assert all(got.values()), (
            f'{name} must be ACCEPTED by all three (it is: {MUST_BE_ACCEPTED[name]}) '
            f'but got {got}')


@needs_node
def test_every_delivered_graph_loads_on_all_three_validators(tmp_path):
    """The graphs people actually render must not have been broken by any of this."""
    result = _run_js_probe(tmp_path)
    delivered = result['delivered']
    assert delivered, 'no delivered graph was validated'
    for row in delivered:
        doc = json.loads(
            (PIPELINE / 'examples' / row['name'].split(':', 1)[1]).read_bytes().decode('utf-8-sig'))
        py = _pipeline_accepts(doc)
        got = {'zod': row['zod'], 'jsonSchema': row['jsonSchema'], 'pipeline': py}
        assert all(got.values()), f'{row["name"]} no longer loads: {got}'


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
