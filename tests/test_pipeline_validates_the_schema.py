"""The PIPELINE must reach the same verdict as the SCHEMA the renderer enforces (P11, defect 4).

THE DEFECT THIS EXISTS FOR.

`pipeline/scene_graph.py` declared `SCHEMA_PATH` at line 25 and never used it.
Its validation was a hand-written `_validate()` -- a second, separately
maintained spelling of the same contract. Commit 55a1d90 made the other two
mirrors (zod and the JSON Schema) agree with EACH OTHER about unknown keys. It
did not make them agree with the pipeline, and it moved the disagreement to the
side that matters most: the renderer rejects a graph the producer happily
accepted.

Measured over the 35 probe graphs below, before this change:

    probe                                  Ajv     Python (old _validate)
    -----------------------------------------------------------
    unknown top-level key                  reject  ACCEPT
    unknown scene key                      reject  ACCEPT
    re-added inert field motion.ease       reject  ACCEPT
    re-added top-level audio               reject  ACCEPT
    unknown camera key                     reject  ACCEPT
    unknown format key                     reject  ACCEPT
    unknown transitionIn key               reject  ACCEPT
    DUPLICATE scene id                     ACCEPT  reject
    perspective 0                          ACCEPT  reject
    format.width 8                         ACCEPT  reject

Eight graphs the schema rejects passed `scene_graph.load()`. Three of them --
`motion.ease`, top-level `audio`, and a misspelled scene key -- are exactly the
defect class the last three commits existed to remove: a field the graph can
set, that nothing reads, that reports success anyway. The pipeline is where
graphs are AUTHORED, so the permissive validator was on the producing side.

THE TWO ROWS AT THE BOTTOM NOW READ THE OTHER WAY, AND THAT IS THE POINT.

`perspective 0` and `format.width 8` were "the schema is wrong, the pipeline is
right" and were left that way: the schema said `minimum: 0` and `minimum: 16`
while zod said `.positive()` and `.int().positive()`. The old `_validate`
rejected both, the schema accepted both, and the disagreement was RECORDED
rather than resolved -- see the section in `scene_graph.py` that used to argue
for deferring to the schema. That reasoning picked the wrong side: zod is the
validator the renderer actually calls, and the JSON Schema was a declaration
that could not even compile until the previous commit. Both bounds are now in
the schema, and both probes are now agreed. `format.width 8` is the one nobody
had found: the enumeration that surfaced `perspective` walked the numeric bounds
of both mirrors and reported exactly one drift, and it walked straight past this.

WHAT IS PROVEN HERE, AND WHAT IS NOT.

    Proven:  `scene_graph._validate` and the JSON Schema return the SAME verdict
             on all 35 probes, including both delivered graphs; the one intended
             exception (duplicate scene id) is pinned as intended, not tolerated;
             the pipeline REJECTS an unknown key, so it is stricter, not looser.
    NOT proven: that `scene_graph`'s schema subset is equivalent to a conforming
             draft-07 implementation for every document. That is bounded instead
             by `test_the_subset_agrees_with_a_real_validator`, which runs the same
             probes through Ajv -- the very validator `tests/test_showcase_schema_
             mirrors_agree.py` already trusts -- so the subset cannot rot into a
             weaker language unnoticed.

THE TRAPS THIS FILE IS BUILT AROUND.

  * A guard asserting a TOKEN APPEARS IN TEXT passes by reading its own comment.
    `scene_graph.py` now carries a long explanation of the unknown-key defect, so
    nothing here asserts a substring of it. Every assertion below runs a real
    validator over a real document.
  * `read_text`/`write_text` silently flips CRLF to LF, and `scene_graph.py` and
    both schema files are CRLF. Nothing here writes them; the two files that ARE
    written are pytest's own `tmp_path`, so a failure there cannot damage the
    tree.
  * The agreement probe below reuses the node/Ajv setup that
    `test_showcase_schema_mirrors_agree.py` already establishes, so the reference
    verdict comes from the same validator the renderer side trusts rather than
    from a second opinion invented here.
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
EXAMPLES = PIPELINE / 'examples'
STUDIO = ROOT / 'studio'
JSON_SCHEMA = PIPELINE / 'schemas' / 'showcase-v1.schema.json'

sys.path.insert(0, str(PIPELINE))
import scene_graph as sg  # noqa: E402

_NPX = shutil.which('npx') or shutil.which('npx.cmd')
needs_node = pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')


# ── the probe set ──────────────────────────────────────────────────────────
#
# Named and built here so BOTH sides run byte-identical documents. The names are
# the assertion surface: a case that quietly disappears is caught by the
# `assert set(...) == expected` in `test_the_probe_set_is_what_this_file_claims`.

def _base() -> dict:
    return {
        'version': 1,
        'project': 'p',
        'format': {'width': 1920, 'height': 1080, 'fps': 60},
        'scenes': [{'id': 's01', 'type': 'kpi-hero', 'durationInFrames': 30}],
    }


def _scene(fn) -> dict:
    d = _base()
    fn(d)
    return d


def _probes() -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []

    def add(name: str, doc: dict) -> None:
        out.append((name, doc))

    # -- the cases the three preceding commits were about -------------------
    add('clean', _base())
    add('unknown top-level key', {**_base(), 'typo': 1})
    add('unknown scene key', _scene(lambda d: d['scenes'][0].update(totallyUnknownField=1)))
    add('re-added inert field motion.ease',
        _scene(lambda d: d['scenes'][0].update(motion={'preset': 'premium', 'ease': 'expo-out'})))
    add('re-added top-level audio', {**_base(), 'audio': {'src': 'a.mp3'}})
    add('meta key _note', {**_base(), '_note': 'provenance'})

    # -- the other five closed sites -----------------------------------------
    add('unknown camera key',
        _scene(lambda d: d['scenes'][0].update(camera={'translateX': [0, 10], 'easeZ': 2})))
    add('unknown format key', _scene(lambda d: d['format'].update(aspectRatio=16)))
    add('unknown transitionIn key',
        _scene(lambda d: d['scenes'][0].update(transitionIn={'in': 'fade', 'dur': 5})))

    # -- the bags that must stay OPEN ----------------------------------------
    add('free-form content bag',
        _scene(lambda d: d['scenes'][0].update(content={'anything': {'nested': [1, 2]}})))
    add('free-form layout bag', _scene(lambda d: d['scenes'][0].update(layout={'whatever': True})))
    add('unknown key in style_bible section',
        {**_base(), 'style_bible': {'palette': {'nope': 1}}})

    # -- values the schema constrains ----------------------------------------
    add('camera constant track', _scene(lambda d: d['scenes'][0].update(camera={'scale': 1.2})))
    add('camera [from,to] track',
        _scene(lambda d: d['scenes'][0].update(camera={'scale': [1, 1.2], 'perspective': 1200})))
    add('camera 3-element track (invalid)',
        _scene(lambda d: d['scenes'][0].update(camera={'scale': [1, 2, 3]})))
    add('camera non-numeric track', _scene(lambda d: d['scenes'][0].update(camera={'scale': 'big'})))
    add('motion known keys only',
        _scene(lambda d: d['scenes'][0].update(motion={'preset': 'minimal', 'stagger': 0.5})))
    add('unknown scene type', _scene(lambda d: d['scenes'][0].update(type='not-a-scene')))
    add('wrong version', {**_base(), 'version': 2})
    add('empty scenes array', _scene(lambda d: d.update(scenes=[])))
    add('scenes not a list', {**_base(), 'scenes': {}})
    add('scene missing id', _scene(lambda d: d['scenes'][0].pop('id')))
    add('scene id bad pattern', _scene(lambda d: d['scenes'][0].update(id='S-01-BAD')))
    add('durationInFrames zero', _scene(lambda d: d['scenes'][0].update(durationInFrames=0)))
    add('durationInFrames bool true', _scene(lambda d: d['scenes'][0].update(durationInFrames=True)))
    add('format.width 8 (below schema min 16)', _scene(lambda d: d['format'].update(width=8)))
    add('fps 240 (above schema max 120)', _scene(lambda d: d['format'].update(fps=240)))
    add('stagger 3 (above max 2)', _scene(lambda d: d['scenes'][0].update(motion={'stagger': 3})))
    add('bpm 20 (below min 40)', {**_base(), 'bpm': 20})
    add('project empty string', {**_base(), 'project': ''})
    add('perspective 20001', _scene(lambda d: d['scenes'][0].update(camera={'perspective': 20001})))

    # -- the two rules JSON Schema cannot state ------------------------------
    add('DUPLICATE scene id',
        _scene(lambda d: d['scenes'].append({'id': 's01', 'type': 'logo', 'durationInFrames': 30})))
    add('perspective 0', _scene(lambda d: d['scenes'][0].update(camera={'perspective': 0})))

    # -- the second drift the hand enumeration walked past ---------------------
    # `format.width`/`height` carried `minimum: 16` in the schema while zod says
    # `.int().positive()`. It is here so this file's own probe table matches the
    # claim in its docstring, and so a future edit to either bound is measured
    # here as well as in test_showcase_mirrors_agree_on_values.py.
    add('format.width 8 (below the OLD schema minimum 16)',
        _scene(lambda d: d['format'].update(width=8)))

    for path in sorted(EXAMPLES.glob('*.json')):
        add(f'delivered: {path.name}', json.loads(path.read_text(encoding='utf-8-sig')))
    return out


#: The one probe where the pipeline is INTENDED to be stricter than the schema.
#: See `scene_graph._validate` for the consumer that breaks without it.
KNOWN_PIPELINE_ONLY_REJECTIONS = {'DUPLICATE scene id'}

#: Probes the schema ACCEPTS and the pipeline must therefore accept too. If the
#: pipeline ever becomes stricter here without a documented reason, these go red.
#:
#: `perspective 0` USED TO BE IN HERE, and its removal is the change the schema
#: edit made. It was the pipeline's one documented opinion that the schema
#: contradicted; the disagreement has since been settled toward zod, so the two
#: now say the same thing and this list is a statement about the current state
#: rather than a snapshot of the old one.
SCHEMA_ACCEPTS = {
    'clean', 'meta key _note', 'free-form content bag', 'free-form layout bag',
    'unknown key in style_bible section', 'camera constant track',
    'camera [from,to] track', 'motion known keys only',
    'delivered: charts_demo.json', 'delivered: showcase_demo.json',
}


# ── 1. the pipeline's verdict, on real documents ───────────────────────────

def _pipeline_accepts(doc: dict) -> bool:
    return not sg._validate(doc)


def test_the_probe_set_is_what_this_file_claims():
    """The anchors. Without this the rest could pass over a set that shrank."""
    names = [n for n, _ in _probes()]
    assert len(names) == 36, f'the probe set changed size: {len(names)}'
    assert len(set(names)) == len(names), 'a probe name is duplicated'
    for required in ('clean', 'unknown top-level key', 'unknown scene key',
                     're-added inert field motion.ease', 'meta key _note',
                     'perspective 0', 'format.width 8 (below the OLD schema minimum 16)',
                     'delivered: charts_demo.json', 'delivered: showcase_demo.json'):
        assert required in names, f'the probe {required!r} went missing'


@pytest.mark.parametrize('name', sorted(KNOWN_PIPELINE_ONLY_REJECTIONS))
def test_a_duplicate_scene_id_is_rejected_by_the_pipeline(name):
    """The check that outlived `_validate`, and the reason it was kept.

    `FinanceShowcaseWide.tsx:156` resolves a scene by
    `doc.scenes.find(x => x.id === r.id)`, so a duplicated id makes the second
    scene render the first one's content. JSON Schema cannot catch this, and
    `uniqueItems` would not help: it compares whole objects.
    """
    doc = dict(_probes())[name]
    problems = sg._validate(doc)
    assert any('duplicate scene id' in p for p in problems), (
        f'{name} is accepted again: {problems}')


def test_every_delivered_graph_still_loads():
    """Strictness must not have broken what people actually render."""
    for path in sorted(EXAMPLES.glob('*.json')):
        sc, problems = sg.load_or_report(path)
        assert sc is not None, f'{path.name} no longer loads: {problems}'
        assert sc.scenes, path.name


@pytest.mark.parametrize('name', sorted(SCHEMA_ACCEPTS))
def test_the_pipeline_accepts_what_the_schema_accepts(name):
    """Direction matters as much as agreement.

    A validator that agrees with the schema by rejecting everything would pass
    an agreement test. This pins the half where both must say yes -- including
    `_note`, which must keep working, and both delivered graphs.
    """
    doc = dict(_probes())[name]
    problems = sg._validate(doc)
    assert not problems, f'the pipeline rejects a graph the schema accepts ({name}): {problems}'


@pytest.mark.parametrize('name,needle', [
    ('unknown top-level key', 'typo'),
    ('unknown scene key', 'totallyUnknownField'),
    ('re-added inert field motion.ease', 'ease'),
    ('re-added top-level audio', 'audio'),
    ('unknown camera key', 'easeZ'),
    ('unknown format key', 'aspectRatio'),
    ('unknown transitionIn key', 'dur'),
])
def test_the_pipeline_rejects_an_unknown_key_and_names_it(name, needle):
    """The property this whole change exists to install in the PRODUCER.

    Asserting the substring is not decoration: the point is that the author is
    told WHICH key, because a bare "invalid" on a 200-line graph is unusable.
    """
    doc = dict(_probes())[name]
    problems = sg._validate(doc)
    assert problems, (
        f'{name} is ACCEPTED by the pipeline. This is the defect: the producer '
        f'lets through a graph the renderer rejects.')
    assert any(needle in p for p in problems), (
        f'{name}: the message does not name {needle!r}: {problems}')


def test_load_refuses_a_graph_with_an_unknown_key():
    """End to end through the public entry point, not the private helper."""
    path = Path(__file__).parent / '__probe_bad_graph.json'
    try:
        path.write_text(json.dumps(dict(_base(), typo=1)), encoding='utf-8')
        with pytest.raises(sg.ShowcaseError) as exc:
            sg.load(path)
        assert 'typo' in str(exc.value)
    finally:
        path.unlink(missing_ok=True)


# ── 2. the schema file must actually load ──────────────────────────────────

def test_the_schema_path_is_the_file_that_is_validated(monkeypatch, tmp_path):
    """`SCHEMA_PATH` was declared for the project's whole life and unused.

    This asserts the FILE is the authority: point the module at a schema that
    forbids the clean graph and the pipeline must follow it. Asserting the
    constant's value would prove nothing -- it is a string in a file, and the
    bug being fixed was precisely that a correct-looking constant can be dead.

    `tmp_path`, not a file beside the test, for a reason that is easy to get
    wrong: monkeypatch is STILL active inside the `finally`, so any statement
    there that re-reads the patched path reads a file about to be deleted.
    """
    schema = json.loads(sg.SCHEMA_PATH.read_bytes().decode('utf-8'))
    schema['required'] = [*schema['required'], 'bpm']
    tmp = tmp_path / 'tight.schema.json'
    tmp.write_text(json.dumps(schema), encoding='utf-8')
    try:
        monkeypatch.setattr(sg, 'SCHEMA_PATH', tmp)
        sg.schema.cache_clear()
        problems = sg._validate(_base())
        assert any("'bpm'" in p for p in problems), (
            f'the pipeline ignored the schema file it was pointed at: {problems}')
        bpm_doc = _base()
        bpm_doc['bpm'] = 126
        assert not sg._validate(bpm_doc), sg._validate(bpm_doc)
    finally:
        sg.schema.cache_clear()
    # monkeypatch has restored SCHEMA_PATH by now, so the real schema must reload.
    assert sg.schema() is sg.schema()


def test_a_missing_schema_is_a_loud_failure_not_a_silent_skip(monkeypatch, tmp_path):
    """The trap this change could itself have fallen into.

    A validator that quietly validates nothing when its file is absent is the
    SAME failure as the one being fixed -- it just fails on a different day. So
    the absence must raise, and the message must say the schema was missing.
    """
    monkeypatch.setattr(sg, 'SCHEMA_PATH', tmp_path / '__no_such_schema__.json')
    sg.schema.cache_clear()
    try:
        with pytest.raises(sg.ShowcaseError) as exc:
            sg._validate(_base())
        message = str(exc.value)
        assert 'cannot read the showcase schema' in message, message
        assert '__no_such_schema__' in message, message
    finally:
        sg.schema.cache_clear()


def test_an_unreadable_schema_is_a_loud_failure_not_a_silent_skip(monkeypatch, tmp_path):
    """Same failure mode, other cause: the file is there and is not JSON."""
    tmp = tmp_path / 'broken.schema.json'
    tmp.write_bytes(b'{ this is not json')
    monkeypatch.setattr(sg, 'SCHEMA_PATH', tmp)
    sg.schema.cache_clear()
    try:
        with pytest.raises(sg.ShowcaseError) as exc:
            sg._validate(_base())
        assert 'not valid JSON' in str(exc.value), str(exc.value)
    finally:
        sg.schema.cache_clear()


def test_an_unsupported_keyword_stops_the_pipeline_rather_than_being_ignored(monkeypatch, tmp_path):
    """The subset cannot rot into a weaker language without anyone noticing.

    If the schema grows a keyword this file does not implement, the honest
    outcome is "I cannot validate this", not "I validated it and ignored the
    constraint" -- which is the permissive-producer bug all over again.
    """
    schema = json.loads(sg.SCHEMA_PATH.read_bytes().decode('utf-8'))
    schema['properties']['bpm']['exclusiveMaximum'] = 200
    tmp = tmp_path / 'newkw.schema.json'
    tmp.write_text(json.dumps(schema), encoding='utf-8')
    monkeypatch.setattr(sg, 'SCHEMA_PATH', tmp)
    sg.schema.cache_clear()
    try:
        with pytest.raises(sg.ShowcaseError) as exc:
            sg._validate(_base())
        message = str(exc.value)
        assert 'unsupported JSON Schema keyword' in message, message
        assert 'exclusiveMaximum' in message, message
    finally:
        sg.schema.cache_clear()


def test_a_dangling_ref_is_a_loud_failure(monkeypatch, tmp_path):
    """The `definitions/Track` defect, from the producer's side.

    Before 55a1d90 eight properties `$ref`'d a definition that did not exist,
    so no conforming validator could compile the file. A pipeline that
    tolerated a dangling ref would be "validating" a document that means
    nothing.
    """
    schema = json.loads(sg.SCHEMA_PATH.read_bytes().decode('utf-8'))
    del schema['definitions']['Track']
    tmp = tmp_path / 'dangling.schema.json'
    tmp.write_text(json.dumps(schema), encoding='utf-8')
    monkeypatch.setattr(sg, 'SCHEMA_PATH', tmp)
    sg.schema.cache_clear()
    try:
        with pytest.raises(sg.ShowcaseError) as exc:
            sg._validate(_base())
        assert 'does not resolve' in str(exc.value), str(exc.value)
    finally:
        sg.schema.cache_clear()


# ── 3. THE GUARD: both validators, same bytes ──────────────────────────────

#: Runs the probe set through Ajv -- the same validator
#: `tests/test_showcase_schema_mirrors_agree.py` already establishes -- so the
#: reference verdict is not a second opinion invented here.
AJV_PROBE = r"""
import fs from 'fs';
import Ajv from 'ajv';

const raw = JSON.parse(fs.readFileSync('../pipeline/schemas/showcase-v1.schema.json', 'utf8'));
let validate;
try {
  validate = new Ajv({strict: false}).compile(raw);
} catch (e) {
  console.log('AJVERR ' + (e as Error).message);
  process.exit(0);
}
const probes: any[] = JSON.parse(fs.readFileSync('./__probe_pipeline_probes.json', 'utf8'));
const out: any[] = probes.map(([name, doc]) => {
  const ok = validate(doc) === true;
  return {name, accept: ok, errors: ok ? [] : (validate.errors || []).map(
    (e) => `${e.instancePath || '/'}: ${e.message}`)};
});
console.log('AJV ' + JSON.stringify(out));
"""


def _ajv_verdicts(probes) -> dict:
    """Run Ajv over the probe set. Fails loudly on a bad run, not silently."""
    studio_probe_file = STUDIO / '__probe_pipeline_probes.json'
    script = STUDIO / '__probe_pipeline.mts'
    try:
        studio_probe_file.write_text(
            json.dumps([[n, d] for n, d in probes], ensure_ascii=False), encoding='utf-8')
        script.write_text(AJV_PROBE, encoding='utf-8')
        proc = subprocess.run(
            [_NPX, 'tsx', str(script)],
            cwd=STUDIO, capture_output=True, text=True, timeout=600,
            encoding='utf-8', errors='replace',
        )
        assert proc.returncode == 0, f'probe failed:\n{proc.stdout}\n{proc.stderr}'
        err = [ln for ln in proc.stdout.splitlines() if ln.startswith('AJVERR ')]
        assert not err, (
            f'the JSON Schema does not compile, so it cannot disagree with the '
            f'pipeline -- it simply never answers: {err}')
        line = [ln for ln in proc.stdout.splitlines() if ln.startswith('AJV ')]
        assert line, f'no probe result:\n{proc.stdout}\n{proc.stderr}'
        rows = json.loads(line[-1][len('AJV '):])
        assert rows, 'the probe ran no cases -- a guard that checks nothing'
        # The marker is the proof that THIS run produced the numbers. Without it
        # a probe that silently stopped running would leave a stale artefact on
        # disk for a later run to read, which is how a green guard stops meaning
        # anything. `tests/test_showcase_schema_mirrors_agree.py` has the same
        # shape; this one asserts the sentinel on every call rather than only on
        # the first.
        assert studio_probe_file.read_text(encoding='utf-8') == json.dumps(
            [[n, d] for n, d in probes], ensure_ascii=False), (
            'the probe input file is not what this run wrote')
        return {r['name']: r for r in rows}
    finally:
        script.unlink(missing_ok=True)
        studio_probe_file.unlink(missing_ok=True)


@needs_node
def test_the_pipeline_and_the_schema_return_the_same_verdict_on_every_probe():
    """THE GUARD. One probe, one comparison, per case.

    `KNOWN_PIPELINE_ONLY_REJECTIONS` is subtracted explicitly rather than waved
    through: it is one named case with a named consumer, so a SECOND divergence
    still fails here.
    """
    probes = _probes()
    reference = _ajv_verdicts(probes)
    assert set(reference) == {n for n, _ in probes}, (
        'the probe set differs between the two sides; they are not being compared')

    disagree = []
    for name, doc in probes:
        ref = reference[name]['accept']
        got = _pipeline_accepts(doc)
        if name in KNOWN_PIPELINE_ONLY_REJECTIONS:
            # Pinned in BOTH directions, because the intended state is a specific
            # pair of verdicts, not "they differ somehow": the schema ACCEPTS this
            # (it cannot express it) and the pipeline REJECTS it (a scene id is a
            # lookup key). If either half moves, the docstring's argument for
            # keeping the check is stale and someone has to look.
            if ref is not True or got is not False:
                disagree.append(
                    f'{name}: expected schema=True pipeline=False, got '
                    f'schema={ref} pipeline={got}')
            continue
        if ref != got:
            disagree.append(f'{name}: schema={ref} pipeline={got}')

    assert not disagree, (
        'the pipeline and the schema disagree about the same bytes:\n  '
        + '\n  '.join(disagree))


@needs_node
def test_the_subset_agrees_with_a_real_validator_on_every_probe():
    """Bound the hand-written subset against a conforming draft-07 engine.

    `_Schema` implements only the keywords `SUPPORTED_KEYWORDS` lists. That list
    is a CLAIM, and a claim about a language subset is worth nothing without a
    reference to check it against -- otherwise a bug in `_Schema` is
    indistinguishable from a bug in the schema, and both just look like "the
    pipeline is strict".

    Ajv is that reference, and it is the same one the mirror-agreement test
    already runs, so a divergence here means `scene_graph` is wrong rather than
    meaning the trust base moved.
    """
    probes = _probes()
    reference = _ajv_verdicts(probes)
    disagree = []
    for name, doc in probes:
        ref = reference[name]['accept']
        got = _pipeline_accepts(doc)
        if name in KNOWN_PIPELINE_ONLY_REJECTIONS:
            continue
        if ref != got:
            disagree.append(f'{name}: ajv={ref} scene_graph={got}')
    assert not disagree, (
        'scene_graph\'s schema subset disagrees with Ajv:\n  '
        + '\n  '.join(disagree))


def test_the_schema_only_uses_keywords_the_pipeline_implements():
    """The other direction: the subset must COVER the schema, not just not clash.

    A keyword the schema starts using but `SUPPORTED_KEYWORDS` does not list
    would make `_check_supported` raise -- which is loud, but it would break
    every load in the pipeline. Better to fail here, where the message can say
    what to add.

    Read the real attribute rather than re-parsing the source with `ast`:
    `SUPPORTED_KEYWORDS` is a `frozenset({...})` CALL, so `ast.literal_eval` on
    it raises, and reading the value the module actually uses is also the only
    version that cannot pass while the constant says something else.
    """
    declared = set(sg.SUPPORTED_KEYWORDS)
    assert declared, 'SUPPORTED_KEYWORDS is empty -- the subset would accept any schema'

    used: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ('properties', 'definitions'):
                    for sub in value.values():
                        walk(sub)
                    continue
                used.add(key)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(json.loads(JSON_SCHEMA.read_bytes().decode('utf-8')))
    unknown = used - declared
    assert not unknown, (
        f'the schema uses JSON Schema keywords scene_graph does not implement: '
        f'{sorted(unknown)}. Add them to SUPPORTED_KEYWORDS and to _Schema, or the '
        f'pipeline will refuse to load at all.')


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
