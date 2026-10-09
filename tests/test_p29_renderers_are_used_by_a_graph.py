"""P29 — every RENDERER is used by at least one TRACKED graph. (B-4's closure.)

THE DEFECT THIS GUARDS.

P26 gave nine declared-but-unrendered scene types real components, seven of them
programmatic:

    browser-window  stat-card  card-grid  data-table  quote  logo  outro

P26's evidence for each was a SINGLE FRAME (`docs/P26_MISSING_RENDERERS.md`
§2.3, seven A-frames read by eye). That is not film-level acceptance, and the
reason it stayed that way is not negligence — it is that no graph asked for any
of them. Both delivered graphs (`showcase_demo.json`, `charts_demo.json`) use
only renderers that already existed. So the seven were never in a film, and
P27's B-4 recorded exactly that: single-frame forensics, zero whole-film
acceptance.

The cause and the cure are the same object here. Because the gap's cause is "no
graph uses these renderers", the closing move is a graph that uses them:
`pipeline/graphs/p29_new_renderer_showcase.json`. This file is what stops the
next renderer from shipping with the same hole.

WHAT IT ASSERTS.

    every key of `SCENE_RENDERERS` appears as a scene `type` in at least one
    graph tracked by git.

The two deliberately-unrendered types (`video`, `data-plane-3d`) are NOT in
`SCENE_RENDERERS` — they live in `UNRENDERED_SCENE_TYPES` — so requiring
coverage of a RENDERER cannot ask for them. That is the point of splitting the
two maps in P26: this guard can be total over renderers without inventing a
requirement that a generative shot exist on this machine.

WHY THE CRITERION IS A COVERAGE COMPUTATION AND NOT A SUBSTRING (the 4.9 lesson,
the seventh recurrence).

This project has been fooled by text-presence assertions seven times. The most
instructive is 4.9's first guard, whose criterion was "the number 520 exists
somewhere in the repo" — a mutation that deleted the real `windowWidth: 520`
survived it, because 520 also appeared in an unrelated fixture. So:

  * the RENDERER side is a parsed KEY SET of the real `SCENE_RENDERERS` object
    literal, comment-stripped, off the real file — the same parse
    `test_p26_scene_type_coverage.py` already pins to, reused by import rather
    than re-implemented so the two cannot drift;
  * the GRAPH side is the set of `scenes[].type` values in graphs that `git
    ls-files` reports, parsed as JSON — not a grep for a type name, which would
    be satisfied by this file's own docstring.

Both halves are required to be non-empty (`test_the_corpus_is_not_vacuous`),
because a parse that silently matched nothing reports "every renderer is
unused" (red, wrong reason) or "every renderer is used" (GREEN, no reason at
all) depending on which side failed.

WHY "TRACKED" IS PART OF THE CRITERION AND NOT A DETAIL.

An untracked file is a scratch copy. Counting one would let a renderer pass this
guard on the strength of an artefact that does not exist for anyone else — the
same mistake `test_p16_...` records for a reference-analysis JSON sitting on disk
but untracked. `git ls-files` is what makes the claim reproducible, and it is the
same primitive `tests/test_showcase_schema_parity.py::test_source_graphs_are_tracked`
already uses for the render inputs.

WHY THE NEW GRAPH LIVES IN `pipeline/graphs/` AND NOT `pipeline/examples/`.

Measured, not guessed. P29 copied the graph into `pipeline/examples/` as a
tracked file and ran the whole suite, then removed it again (git status was
byte-identical before and after). The result was EXACTLY ONE failure:

  * `tests/test_pipeline_validates_the_schema.py::test_the_probe_set_is_what_this_file_claims`
    — `assert len(names) == 36` became `assert 37 == 36`, because `_probes()`
    adds one `delivered: <name>` entry per `EXAMPLES.glob('*.json')`. This is a
    hard-coded COUNT, so it cannot be satisfied from the graph's side, and the
    work order for P29 forbids editing an existing guard to get a green suite.
    Everything else — 558 passed — including every other examples/ sweep.

A second guard was checked and did NOT fire:
`tests/test_style_bible_no_dumb_declarations.py::test_the_one_key_the_demo_graph_sets_is_reachable`
asserts `sbc.keys_in_graphs() == {'typography': ['showcase_demo.json']}`, an exact
set equality, which any example graph carrying a `style_bible` would break. This
graph ships none, so it is unaffected — confirmed by the same suite run.

So the cost of this location is real and is recorded rather than hidden: the
graph is invisible to the `pipeline/examples` sweeps — the zod/JSON-Schema mirror
agreement check, the three-validator load check, the beat/binding checks, the
generative-scene sweep. This file therefore carries the two checks that matter
most for a graph that no other guard will read:

  * `test_the_p29_graph_loads_on_the_pipeline_validator` runs it through
    `scene_graph._validate`, which is one of the three validators
    `test_showcase_mirrors_agree_on_values.py` requires of a delivered graph.
    That call reaches the JSON Schema mirror (`additionalProperties: false` at
    the root and on Scene), so the Ajv half of the verdict IS covered.
  * `test_the_two_mirrors_agree_about_the_p29_graph` runs zod AND Ajv on it and
    requires the same verdict from both — the one thing the examples/ sweep would
    have supplied and the Python validator cannot.

Moving the graph into `pipeline/examples/` later is a one-line move plus a
one-number update to that count assertion. It is deliberately NOT done here,
because relaxing an existing guard to make a suite green is the thing this
project has been bitten by seven times.

WHAT THIS FILE DOES NOT DO.

It does not assert that a renderer draws WELL. That is a render's job; P29's
acceptance lives in `docs/P29_NEW_RENDERER_ACCEPTANCE.md` and in the frames it
names. It does not duplicate `test_p26_scene_type_coverage.py`, which judges the
SCHEMA against the RENDERER; this judges the RENDERER against DELIVERED GRAPHS.
And it does not require every declared type to be covered — `video` and
`data-plane-3d` have no renderer at all, which P26 already recorded as a
decision in `UNRENDERED_SCENE_TYPES`.

WHAT P29 FOUND BY RUNNING THE MUTATIONS INSTEAD OF ASSUMING THEY WOULD DIE.

Three mutations were run against the version of this file the previous agent
left behind. Two died. The third did not:

  * deleting the `quote` scene -> red (the guard, plus two others);
  * making `renderer_coverage` return `[]` -> red, because the two
    discrimination tests ask the CRITERION directly;
  * overwriting the guard's own verdict with `uncovered = []` -> **GREEN, 8
    passed.** Both discrimination tests ask `renderer_coverage`; neither asks
    the guard. The one thing the suite actually runs was unobserved.

So `test_the_guard_itself_goes_red_on_a_corpus_with_a_hole` was added: it runs
the guard in a subprocess against a corpus with a hole and requires that
subprocess to FAIL. A criterion can be rigged; a guard can also simply be
deleted, and only a test that runs the guard itself can tell.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_TSX = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'FinanceShowcaseWide.tsx'
P29_GRAPH = ROOT / 'pipeline' / 'graphs' / 'p29_new_renderer_showcase.json'

#: The node runner the existing mirror checks use (`test_showcase_schema_mirrors_
#: agree.py` has the same three lines). Reused rather than reinvented so the skip
#: condition is the same one the rest of the suite already honours: no npx means
#: SKIP, never a green that means nothing.
STUDIO = ROOT / 'studio'
_NPX = shutil.which('npx') or shutil.which('npx.cmd')
needs_node = pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')

sys.path.insert(0, str(ROOT / 'tests'))
# The renderer-side parse is IMPORTED, not copied. test_p26_scene_type_coverage
# already pins it to the real file with `test_the_maps_are_the_real_ones`, and
# `visual_qa.py` reads the same two maps the same way; a third implementation
# here would be a third thing to keep in step.
from test_p26_scene_type_coverage import rendered_scene_types  # noqa: E402

sys.path.insert(0, str(ROOT / 'pipeline'))
import scene_graph as sg  # noqa: E402

#: Where a DELIVERED graph may live. Both are read; a graph in either counts.
GRAPH_DIRS = ('pipeline/examples', 'pipeline/graphs')

#: The seven P26 renderers this task exists to cover. Named explicitly so the
#: failure message can say which capability went back to being unreachable, and
#: so the set is a decision on the record rather than an accident of subtraction.
P29_RENDERERS = frozenset({
    'browser-window', 'stat-card', 'card-grid', 'data-table', 'quote', 'logo', 'outro',
})


def _git() -> str:
    return shutil.which('git') or r'C:\Program Files\Git\cmd\git.exe'


def _graph_dirs() -> list[str]:
    """Where to look, allowing a meta-test to point the guard at a fixture.

    `P29_GRAPH_DIRS` overrides the two real directories. It exists for exactly
    one test — the one that runs the GUARD ITSELF in a subprocess against a
    corpus with a hole — because that test has to hand the guard a corpus git
    does not know about. It is unset in every normal run, so the guard's
    production behaviour is the `GRAPH_DIRS` branch below and nothing else.
    """
    override = os.environ.get('P29_GRAPH_DIRS')
    if override:
        return [p for p in override.split(os.pathsep) if p]
    return list(GRAPH_DIRS)


def tracked_graphs() -> list[Path]:
    """Every tracked scene graph, from git — not from a directory listing.

    `git ls-files` over both directories, filtered to `.json`. An UNTRACKED file
    is excluded by construction, which is the point: this guard's claim is that
    the coverage is reproducible for anyone who checks out the repository.

    Under the `P29_GRAPH_DIRS` override there is no repository to ask, so that
    branch is a plain listing and is ONLY reachable from the meta-test below.
    """
    override = os.environ.get('P29_GRAPH_DIRS')
    if override:
        paths: list[Path] = []
        for d in _graph_dirs():
            paths.extend(sorted(Path(d).glob('*.json')))
        return sorted(paths)
    out = subprocess.run(
        [_git(), 'ls-files', '--', *_graph_dirs()],
        cwd=str(ROOT), capture_output=True, text=True, encoding='utf-8', errors='replace')
    paths = []
    for line in out.stdout.splitlines():
        rel = line.strip()
        if rel.endswith('.json') and (ROOT / rel).exists():
            paths.append(ROOT / rel)
    return sorted(paths)


def graph_scene_types(path: Path) -> list[str]:
    doc = json.loads(path.read_text(encoding='utf-8-sig'))
    scenes = doc.get('scenes')
    if not isinstance(scenes, list):
        return []
    return [s['type'] for s in scenes if isinstance(s, dict) and isinstance(s.get('type'), str)]


def renderer_coverage(graphs: dict[str, list[str]], renderers: set[str]) -> list[str]:
    """Renderers no graph asks for — the pure function the guard asserts on.

    Taken as arguments so the discrimination tests below can feed it a corpus
    with a hole in it without touching the repository.
    """
    used: set[str] = set()
    for types in graphs.values():
        used |= set(types)
    return sorted(renderers - used)


# ── the guard ───────────────────────────────────────────────────────────────

def test_every_renderer_is_used_by_a_tracked_graph():
    """THE GUARD. A renderer no graph asks for is a renderer with no film.

    This is B-4. It was green-with-a-hole before P29: the seven keys were real
    components with single-frame evidence and no graph anywhere named them, so
    nothing in the pipeline could ever put them on a screen.
    """
    graphs = {p.name: graph_scene_types(p) for p in tracked_graphs()}
    renderers = rendered_scene_types()
    uncovered = renderer_coverage(graphs, renderers)
    assert not uncovered, (
        'these renderers are reachable in SCENE_RENDERERS but NO tracked graph '
        f'asks for them: {uncovered}\n'
        f'tracked graphs scanned: {sorted(graphs)}\n'
        'A renderer nothing renders is not a capability. Either add a scene that '
        'uses it, or — if it genuinely cannot be drawn — remove it from the map '
        'and record the reason in UNRENDERED_SCENE_TYPES, which is the decision '
        'table P26 built for exactly this case.')


def test_the_corpus_is_not_vacuous():
    """Both halves of the coverage computation must be real.

    A renderer parse that matched nothing would make `renderers` empty and the
    guard trivially true; a graph parse that matched nothing would make every
    renderer uncovered. The first is GREEN for the wrong reason and is the one
    that has to be pinned.
    """
    renderers = rendered_scene_types()
    assert len(renderers) >= 20, (
        f'SCENE_RENDERERS parsed to only {len(renderers)} keys: {sorted(renderers)}. '
        'The guard would then be asserting coverage of almost nothing.')
    assert 'quote' in renderers and 'kpi-hero' in renderers, renderers

    graphs = tracked_graphs()
    assert graphs, (
        'no tracked scene graph found under ' + ', '.join(GRAPH_DIRS) +
        ' — the coverage sweep is vacuous, which is not a passing result.')
    names = {p.name for p in graphs}
    assert {'showcase_demo.json', 'charts_demo.json'} <= names, (
        f'the two pre-existing delivered graphs are missing from the corpus: {sorted(names)}. '
        'If they moved, this guard is scanning a different set than it was written for.')


def test_the_p29_graph_actually_uses_the_seven_renderers():
    """The attribution: name the graph that closes B-4, and hold it to that.

    Without this, the coverage guard could stay green because some OTHER graph
    grew a `quote` scene, and the file that was added for B-4 could quietly stop
    covering anything while the suite reported the gap closed.
    """
    p = P29_GRAPH
    assert p.exists(), 'the P29 graph is gone; B-4 is open again'
    used = set(graph_scene_types(p))
    assert P29_RENDERERS <= used, (
        f'the P29 graph no longer uses {sorted(P29_RENDERERS - used)}. It was added '
        'to make these seven reachable by a film; if it stops, the closure is undone.')


def test_the_p29_graph_loads_on_the_pipeline_validator():
    """The validity check this graph does NOT inherit by living outside examples/.

    `pipeline/examples/*.json` is swept by
    `test_showcase_mirrors_agree_on_values.py::test_every_delivered_graph_loads_on_all_three_validators`.
    A graph in `pipeline/graphs/` is not, so it is checked here against the same
    Python validator.

    WORTH BEING PRECISE ABOUT WHAT THIS COVERS, because an earlier draft of this
    file claimed "zod and Ajv are not re-run" and that was only half right.
    `scene_graph._validate` starts with `schema().iter_errors(doc)`, and that
    schema is `pipeline/schemas/showcase-v1.schema.json` -- the SAME file Ajv
    compiles, with `additionalProperties: false` at the root and on the Scene
    definition. So the Ajv half of the verdict IS reached here. What is not
    reached is zod: the TypeScript mirror. `test_the_two_mirrors_agree` below
    closes that, and it is the only reason this graph is not simply unvalidated.
    """
    p = P29_GRAPH
    doc = json.loads(p.read_text(encoding='utf-8-sig'))
    problems = sg._validate(doc)
    assert not problems, f'p29_new_renderer_showcase.json no longer validates: {problems}'

    declared = {s['type'] for s in doc['scenes']}
    from test_p26_scene_type_coverage import declared_scene_types  # noqa: E402
    unknown = sorted(declared - declared_scene_types())
    assert not unknown, f'the graph names scene types SceneType does not declare: {unknown}'


#: A minimal zod-vs-Ajv probe over ONE file, run through the same `npx tsx`
#: mechanism `test_showcase_schema_mirrors_agree.py` already uses. It takes the
#: graph path as argv[2] rather than hard-coding a directory, because the whole
#: point is to point it at a file the examples/ sweep does not reach.
_MIRROR_PROBE = r"""
import fs from 'fs';
import Ajv from 'ajv';
import {ShowcaseSchema} from './src/schemas/showcase-v1';

const raw = JSON.parse(fs.readFileSync('../pipeline/schemas/showcase-v1.schema.json', 'utf8'));
const validate = new Ajv({strict: false}).compile(raw);
const doc = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const z = ShowcaseSchema.safeParse(doc);
const j = validate(doc) === true;
console.log('MIRRORRESULT ' + JSON.stringify({
  zod: z.success,
  jsonSchema: j,
  agree: z.success === j,
  zodIssues: z.success ? [] : z.error.issues.map((i: any) => i.path.join('.') + ': ' + i.message),
}));
"""


@needs_node
def test_the_two_mirrors_agree_about_the_p29_graph():
    """The gap that living outside `pipeline/examples/` actually opens.

    Measured, not assumed. `pipeline/graphs/` is invisible to
    `test_showcase_schema_mirrors_agree.py`, whose `delivered` sweep is a
    `readdirSync('../pipeline/examples')`. That guard exists to prove the zod
    mirror and the JSON Schema mirror return the SAME verdict on every delivered
    graph -- so a graph that guard never reads is a graph nobody has proved the
    two mirrors agree about. This runs both on it directly.

    Skip, never lie: with no npx the node half cannot run, and this file says so
    rather than reporting a pass it did not earn.
    """
    probe = STUDIO / '__probe_p29_mirrors.mts'
    try:
        probe.write_text(_MIRROR_PROBE, encoding='utf-8')
        proc = subprocess.run(
            [_NPX, 'tsx', str(probe), str(P29_GRAPH)],
            cwd=str(STUDIO), capture_output=True, text=True, timeout=600,
            encoding='utf-8', errors='replace',
        )
        assert proc.returncode == 0, f'probe failed:\n{proc.stdout}\n{proc.stderr}'
        line = [ln for ln in proc.stdout.splitlines() if ln.startswith('MIRRORRESULT ')]
        assert line, f'no probe result:\n{proc.stdout}\n{proc.stderr}'
        result = json.loads(line[-1][len('MIRRORRESULT '):])

        assert result['agree'], (
            'the two schema mirrors disagree about p29_new_renderer_showcase.json: '
            f'zod={result["zod"]} jsonSchema={result["jsonSchema"]}; '
            f'zod issues={result["zodIssues"]}. The graph lives outside the '
            'examples/ sweep, so nothing else would notice.')

        # Direction, not just agreement: two mirrors that were both permissive
        # would also "agree". The graph must be ACCEPTED by both.
        assert result['zod'], f'zod rejects the P29 graph: {result["zodIssues"]}'
        assert result['jsonSchema'], 'the JSON Schema mirror rejects the P29 graph'
    finally:
        probe.unlink(missing_ok=True)


# ── discrimination: the check MUST be able to say no ────────────────────────

def test_the_coverage_check_can_say_no():
    """Kills the always-passes implementation, on a corpus with a hole in it.

    The real corpus currently covers every renderer, so a guard that has only
    ever seen a healthy input has not been shown to be able to fail. Removing one
    renderer from the GRAPH side must report it; the renderer side is untouched,
    so the report can only come from the coverage computation.
    """
    renderers = {'a', 'b', 'c'}
    full = {'g1.json': ['a', 'b'], 'g2.json': ['c']}
    assert renderer_coverage(full, renderers) == []

    # drop the only graph that asks for `c`
    holed = {'g1.json': ['a', 'b'], 'g2.json': []}
    assert renderer_coverage(holed, renderers) == ['c']

    # a renderer nobody asks for at all
    assert renderer_coverage({'g1.json': ['a']}, renderers) == ['b', 'c']

    # an empty corpus reports every renderer, not none — the direction that
    # would otherwise hide a broken graph parse behind a green guard
    assert renderer_coverage({}, renderers) == ['a', 'b', 'c']


def test_a_graph_that_is_not_tracked_does_not_count():
    """The 'tracked' half, measured rather than asserted.

    An untracked file in a scanned directory is the exact shape of the P16
    lesson (an artefact on disk that nobody else has). This builds one, asks the
    same discovery function, and requires it to be invisible.
    """
    stray = ROOT / 'pipeline' / 'graphs' / '__p29_untracked_probe.json'
    stray.write_text(json.dumps({
        'version': 1, 'project': 'probe',
        'format': {'width': 1920, 'height': 1080, 'fps': 60},
        'scenes': [{'id': 's', 'type': 'kpi-hero', 'durationInFrames': 60}],
    }), encoding='utf-8')
    try:
        names = {p.name for p in tracked_graphs()}
        assert '__p29_untracked_probe.json' not in names, (
            'an untracked file was counted as a delivered graph; this guard would '
            'pass on coverage that does not exist for anyone who clones the repo')
        # ...and the file is on disk, so the exclusion is a decision, not an
        # accident of the file not existing
        assert stray.exists()
    finally:
        stray.unlink(missing_ok=True)


def test_the_guard_is_red_when_a_graph_stops_using_a_renderer():
    """End-to-end on the REAL corpus shape: the real renderer set, a holed corpus.

    Feeds `renderer_coverage` the actual keys parsed out of
    `FinanceShowcaseWide.tsx` and a corpus built from the real graphs with one
    scene's type deleted. The guard's own arithmetic must name that renderer.
    """
    real = {p.name: graph_scene_types(p) for p in tracked_graphs()}
    assert real, 'fixture assumption: the tracked corpus is non-empty'
    renderers = rendered_scene_types()

    holed = json.loads(json.dumps(real))
    target = sorted(P29_RENDERERS - set().union(*holed.values()))
    assert not target, 'fixture assumption: the P29 graph is what covers the seven'
    holed['p29_new_renderer_showcase.json'] = [
        t for t in holed['p29_new_renderer_showcase.json'] if t != 'quote']

    reported = renderer_coverage(holed, renderers)
    assert 'quote' in reported, (
        f'deleting the only quote scene from the graph did not report quote as '
        f'uncovered; reported {reported}. The criterion is not tracking the corpus.')
    # and the mutation is the ONLY thing that changed
    before = renderer_coverage(real, renderers)
    assert before == [], before


def test_the_guard_itself_goes_red_on_a_corpus_with_a_hole(tmp_path):
    """Closes the hole mutation 3 found: the guard could be a no-op and stay green.

    The two discrimination tests above exercise `renderer_coverage` — the
    CRITERION — directly. That catches a criterion rigged to always pass, and it
    caught one (P29 mutation 2). It does NOT catch the guard's own body being
    rigged: P29 mutation 3 overwrote the guard's verdict with `uncovered = []`
    and the whole file still reported 8 passed, because every other test asks
    the helper, not the guard. A guard whose body can be emptied without
    anything noticing is not a guard.

    So this runs the guard ITSELF, in a subprocess, against a corpus that has a
    hole in it, and requires that subprocess to FAIL. A neutered guard passes
    there, which is exactly what makes this red.

    The fixture corpus is handed over through `P29_GRAPH_DIRS` because it is not
    in the repository and `git ls-files` cannot see it.
    """
    fixture_dir = tmp_path / 'holed_corpus'
    fixture_dir.mkdir()
    for p in tracked_graphs():
        shutil.copy2(p, fixture_dir / p.name)
    holed = fixture_dir / P29_GRAPH.name
    doc = json.loads(holed.read_text(encoding='utf-8'))
    doc['scenes'] = [s for s in doc['scenes'] if s['type'] != 'quote']
    holed.write_text(json.dumps(doc), encoding='utf-8')

    env = dict(os.environ, P29_GRAPH_DIRS=str(fixture_dir))
    proc = subprocess.run(
        [sys.executable, '-m', 'pytest',
         f'{Path(__file__).resolve()}::test_every_renderer_is_used_by_a_tracked_graph',
         '-q', '--no-header', '-p', 'no:cacheprovider'],
        cwd=str(ROOT), capture_output=True, text=True, timeout=600,
        env=env, encoding='utf-8', errors='replace')
    assert proc.returncode != 0, (
        'the guard PASSED against a corpus whose only quote scene had been deleted. '
        'Its body can be neutered without anything noticing, which means it is not '
        'currently enforcing anything.\n'
        f'--- guard subprocess stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}')


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
