"""P12.2 — a ScenePlanner was NOT built, and this file is why (verdict C).

Work order: `docs/WORKORDER_P38_SCENE_PLANNER.md`. The measurement record and the
(a)/(b)/(c) answers are in `docs/P12_2_SCENE_PLANNER.md`.

WHAT THIS FILE IS. It is not a guard on a planner, because there is no planner.
It is a guard on the PREMISES of the verdict not to build one. A verdict recorded
only in a document rots silently: the moment someone adds an intent source, or
repairs the beat instrument, or gives `generate_graph` a reason to touch scene
types, the reasons this project declined the work are gone and nobody notices.
So each premise is asserted here, against the real modules, and each goes RED on
the day it stops holding. That is what makes "we measured and decided not to"
different from "we decided not to and stopped looking".

THE THREE PREMISES, AND WHAT EACH ONE IS MEASURED AGAINST.

  (a) There is no intent source to plan FROM. `generate_graph(brief)` takes a
      brief whose `scenes` are ALREADY typed, and puts them in the graph
      unchanged — verified by identity, not by looking similar. A planner that
      chose scene types would be re-deciding a decision the brief already made.
      And the gate that catches an unrenderable type already exists and already
      fires: P21's `rule_graph_scene_renderable`, exercised here end to end.

  (b) There is no duration criterion. The one function nominated for the job,
      `scene_graph.beat_aligned_durations`, cannot report a problem on ANY
      input — see `test_the_nominated_duration_authority_is_a_tautology`, which
      feeds it a 1-frame scene beside a 4999-frame scene. Meanwhile every
      delivered graph drifts 12.8-13.9 frames off the beat on the timeline the
      renderer actually ships. An instrument that answers "no problems" to a
      question nobody asked is not a criterion.

  (c) A Storyboard layer would be an identity. `generate_graph(brief).graph
      ['scenes'] IS brief['scenes']` — measured, not asserted from a reading of
      the source. So a Storyboard sitting between them has nothing to add: every
      field it carried would be either copied straight through (an identity, the
      exact defect P36 recorded as `tuple(str(x) for x in strings)`) or invented
      with no consumer, which is `chartLanguage`, `audioLanguage` and
      `LOCKED_SCENE_TYPES`.

WHY THE HELPERS BELOW EXIST SEPARATELY FROM THE ASSERTIONS.

`unrendered_gaps` and `shipped_beat_drift` are pure functions so the
discrimination tests can ask them questions with a hole in them. A guard whose
only caller is a test that currently passes has never been shown it can fail —
this project has been fooled that way ten times.

WHY NOTHING HERE READS `docs/P12_2_SCENE_PLANNER.md`. The document is prose and
prose is not evidence; a number in a document can be stale while the document
still reads true. Every claim above is recomputed from `pipeline/`,
`studio/src/templates/finance-showcase/` and the real validator.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
# `visual_qa` lives beside the scripts, not on the package path; the same
# sys.path line test_p21_props_path_gates_the_deliverable.py uses.
sys.path.insert(0, str(ROOT / 'studio' / 'scripts'))

from pipeline import scene_graph  # noqa: E402
from pipeline.director.style_bible import generate_graph  # noqa: E402

# The renderability tables are IMPORTED from P26's parse rather than written
# here. P21 is the project's own scar for this: two call sites holding one
# constant, only one of them reading it. A second spelling of "which types can
# be drawn" in this file would be the same defect wearing a different hat.
from test_p26_scene_type_coverage import (  # noqa: E402
    declared_scene_types,
    rendered_scene_types,
    unrendered_scene_types,
)

EXAMPLES = ROOT / 'pipeline' / 'examples'
GRAPHS = ROOT / 'pipeline' / 'graphs'
TEMPLATE_TSX = (ROOT / 'studio' / 'src' / 'templates'
                / 'finance-showcase' / 'FinanceShowcaseWide.tsx')

#: The three delivered graphs, and the tempo each one declares. `showcase_demo`
#: and `charts_demo` were re-tempoed by 41947f6; `p29_...` was authored at 126.
DELIVERED = (
    EXAMPLES / 'showcase_demo.json',
    EXAMPLES / 'charts_demo.json',
    GRAPHS / 'p29_new_renderer_showcase.json',
)


# ── pure helpers, so the discrimination tests can ask them ───────────────────

def unrendered_gaps(scene_types, rendered: set[str]) -> list[str]:
    """Scene types with no renderer — the condition P21's gate reports on."""
    return sorted({t for t in scene_types if t not in rendered})


def shipped_beat_drift(sc: scene_graph.Showcase) -> dict[str, float]:
    """Distance from each SHIPPED scene start to the nearest beat, in frames.

    `beat_snap=False` on purpose. That is the mode `FinanceShowcaseWide.tsx:201`
    calls, so it is the timeline the film is cut on. The grid here is `sc.bpm`,
    which is what a beat means for this graph.
    """
    return {r.id: sc.beat_distance_frames(r.startFrame)
            for r in sc.resolve(beat_snap=False)}


def durations_of(doc: dict) -> list[int]:
    return [s['durationInFrames'] for s in doc['scenes']]


def mean_off_grid(values, step: float) -> float:
    """Mean distance from each value to the nearest whole multiple of `step`.

    The measurement behind "these graphs were authored on a different grid".
    """
    return sum(abs(v - round(v / step) * step) for v in values) / len(values)


def brief_with(scene_type: str, *, extra_scene_key: str | None = None) -> dict:
    """A brief carrying NO style bible — `generate_graph` supplies one."""
    scene: dict = {'id': 's01', 'type': scene_type, 'durationInFrames': 150}
    if extra_scene_key is not None:
        scene[extra_scene_key] = {'not': 'a declared key'}
    return {
        'project': 'p12_2_guard',
        'format': {'width': 1920, 'height': 1080, 'fps': 60},
        'scenes': [scene],
    }


def load_graph(doc: dict, tmp_path: Path):
    """`scene_graph.load()` for real, on the real JSON Schema.

    Written through `write_bytes` because `write_text` translates line endings
    on Windows and a re-encoded graph is not the graph the generator produced.
    """
    path = tmp_path / 'graph.json'
    path.write_bytes(json.dumps(doc).encode('utf-8'))
    return scene_graph.load(path)


# ── (a) there is no intent source to plan FROM ──────────────────────────────

def test_generate_graph_passes_the_briefs_scenes_through_unchanged():
    """THE PREMISE. It plans no scenes, so there is nothing for a planner to add.

    Checked two ways on purpose. Equality alone would survive an implementation
    that rebuilt an identical list; identity (`is`) is what makes this a
    pass-through rather than a reconstruction, and it is the claim the whole
    (c) answer rests on. If a future change makes `generate_graph` filter,
    reorder or rewrite scenes, this goes red and (c) has to be re-measured.
    """
    brief = brief_with('bar-chart')
    generated = generate_graph(brief)
    assert generated.graph['scenes'] == brief['scenes'], (
        'generate_graph rewrote the brief\'s scenes. That is not necessarily wrong '
        '— but it means it is doing something a ScenePlanner was declined for '
        'doing inside the StyleBible generator, and P12.2 must be re-measured.')
    assert generated.graph['scenes'] is brief['scenes'], (
        'generate_graph now builds a new scenes list rather than carrying the '
        'brief\'s. Equality holds but identity does not: the scenes are being '
        're-derived somewhere, and that derivation is a planner by another name. '
        f'Got: {generated.graph["scenes"]}')


def test_generate_graph_places_no_restraint_on_the_scene_type(tmp_path):
    """A brief naming an unrendered type produces a graph, unchallenged.

    This is the shape of the hole (a) was asked about. It is asserted POSITIVE
    (`== ['video']` and a clean load) rather than as "no error was raised",
    because "did not raise" is also what a broken guard looks like.
    """
    generated = generate_graph(brief_with('video'))
    assert [s['type'] for s in generated.graph['scenes']] == ['video']
    load_graph(generated.graph, tmp_path)  # must not raise
    # `video` is genuinely unrendered, per P26's table read off the real template.
    assert 'video' in set(unrendered_scene_types()), (
        'fixture assumption: `video` must be in UNRENDERED_SCENE_TYPES. If a '
        'renderer was added, point this fixture at the type that is still '
        'unrendered — do not weaken the assertion.')


def test_the_unrenderable_type_is_gated_downstream_and_the_gate_fires():
    """The gate for (a) EXISTS and FIRES, end to end, on a generated graph.

    This is why the verdict is "do not build" and not "the capability is
    missing". P21's `rule_graph_scene_renderable` reads the same `SCENE_RENDERERS`
    map the template dispatches on, and it already reports a graph naming `video`
    as FAIL with the offending scene index. A planner-side type filter would be a
    SECOND gate on the same fact — which is the P21 defect (one constant, two
    call sites, one of them read) restated as two gates and one of them read.

    The FAIL is asserted on the rule's own verdict, not on its prose.
    """
    from visual_qa import rule_graph_scene_renderable  # noqa: PLC0415

    finding = rule_graph_scene_renderable(
        {'scenes': [{'id': 's01', 'type': 'video', 'durationInFrames': 150}]})
    assert finding.verdict == 'FAIL', (
        f'the renderability gate did not fire on an unrenderable type; it '
        f'reported {finding.verdict!r}. Either the gate regressed or the '
        f'fixture type is no longer unrendered: {finding.detail}')
    assert finding.extra['gaps'] == [{'index': 0, 'type': 'video'}], (
        f'the gate fired but did not name the offending scene: {finding.extra}')
    # ...and the same graph with a rendered type passes, so the gate is not a
    # constant FAIL wearing a rule's name (the both-directions requirement).
    ok = rule_graph_scene_renderable(
        {'scenes': [{'id': 's01', 'type': 'bar-chart', 'durationInFrames': 150}]})
    assert ok.verdict == 'PASS', f'a renderable type was reported {ok.verdict!r}: {ok.detail}'


def test_the_unrendered_set_is_the_two_generative_types_not_nine():
    """Why "avoid 9 of 22" is stale, and what the real avoidance rule is.

    The work order was written against P26's original decision table. P29
    (`a7f02b8`) accepted seven new renderers, so the unrendered set is now the
    two GENERATIVE types and nothing else. A planner built to avoid "the nine"
    would be avoiding seven types that now render fine while the two that do not
    render went in unmentioned. The rule that survives is the set difference,
    not a list.
    """
    declared, rendered = declared_scene_types(), rendered_scene_types()
    assert len(declared) == 22, f'SceneType now declares {len(declared)}: {sorted(declared)}'
    assert len(rendered) == 20, f'SCENE_RENDERERS now names {len(rendered)}: {sorted(rendered)}'
    assert unrendered_scene_types() == {'video', 'data-plane-3d'}, (
        f'the unrendered set is {sorted(unrendered_scene_types())}. This number is '
        'measured, not assumed — if it moved, the rule for choosing scene types '
        'moved with it and P12.2 has to be re-measured.')


# ── (b) there is no duration criterion ──────────────────────────────────────

def test_the_nominated_duration_authority_is_a_tautology():
    """THE PREMISE, in the sharpest form available. It cannot say no.

    `beat_aligned_durations` resolves with `beat_snap=True`, which ROUNDS each
    start onto the beat grid by construction, and then measures how far each
    start is from the beat grid. It compares a rounded value against the thing
    it was rounded from. P12's verdict (`docs/DIRECTOR_SCOPE_VERDICT.md` §6.2)
    nominated it as the thing a duration-aware generator should consume; it is
    structurally incapable of reporting a problem.

    The input is chosen to be unanswerable in the most obvious way: a 1-frame
    scene and a 4999-frame scene, six scenes, a real tempo. Any criterion with a
    threshold finds something here. This one returns an empty list.

    Asserted as an EXACT empty list rather than "did not raise", because the
    difference between "found nothing" and "crashed and nobody looked" is the
    difference between a measurement and an absence.
    """
    doc = {
        'project': 'tautology_probe', 'bpm': 126,
        'format': {'width': 1920, 'height': 1080, 'fps': 60},
        'scenes': [{'id': f's{i}', 'type': 'bar-chart', 'durationInFrames': d}
                   for i, d in enumerate([1, 3, 7, 997, 4999, 13])],
    }
    reported = scene_graph.beat_aligned_durations(doc)
    assert reported == [], (
        'beat_aligned_durations now reports something on an absurd input. If that '
        'is a repair rather than a regression, it is no longer a tautology, a '
        'duration criterion EXISTS, and P12.2(b) must be re-decided on its '
        f'strength. It reported: {reported}')


def test_the_delivered_graphs_drift_on_the_timeline_the_renderer_ships():
    """The other half of (b): the drift is real, and nobody was measuring it.

    `FinanceShowcaseWide.tsx:201` resolves with `beat_snap=False`, so the
    shipped timeline is a plain back-to-back layout and its scene starts land
    wherever the authored durations put them. Every delivered graph drifts by
    more than ten frames — which is not a rounding wobble, it is the grid being
    ignored — and `beat_aligned_durations` reports zero problems on all three.

    Read against the tautology above, these two tests are one measurement: the
    instrument says the film is on the beat, and the film is not.
    """
    for path in DELIVERED:
        doc = json.loads(path.read_text(encoding='utf-8'))
        fmt = doc['format']
        sc = scene_graph.Showcase(
            project=doc['project'], width=fmt['width'], height=fmt['height'],
            fps=fmt['fps'], bpm=float(doc['bpm']), scenes=doc['scenes'])
        drift = shipped_beat_drift(sc)
        off_beat = {k: v for k, v in drift.items() if v > 0.5 + 1e-6}
        assert off_beat, (
            f'{path.name} has no off-beat scene starts on its shipped timeline. '
            'Either the durations were re-authored onto the beat grid — which '
            'would be a decision worth recording — or this measurement is '
            'broken, since it now agrees with the tautology for a live reason.')
        worst = max(off_beat.values())
        assert worst > 1.0, (
            f'{path.name} drifts by at most {worst:.3f} frames, which is inside '
            'the half-a-frame rounding bound this project already accepts. The '
            'premise that these graphs ignore the grid no longer holds at a '
            'magnitude worth reporting.')
        assert scene_graph.beat_aligned_durations(doc) == [], (
            f'beat_aligned_durations and the shipped timeline now disagree about '
            f'{path.name}. One of the two changed; re-decide (b).')


def test_the_three_delivered_graphs_follow_three_different_duration_rules():
    """Why there is no rule to copy, measured rather than asserted.

    * `showcase_demo`: 229/229/114/229 are whole beats at the OLD tempo of 126
      (`round(8 * 28.5714) = 229`, `round(4 * 28.5714) = 114`) — left behind when
      41947f6 corrected the declared tempo to 128.998.
    * `charts_demo`: 150 x9 and 600, every one a multiple of 10 frames.
    * `p29_...`: 150/120/210/180/160/100/200, again all multiples of 10 frames.

    So the corpus demonstrates a whole-beat rule, a tenth-second rule, and one
    graph that is still on the tempo it was written against. There is no single
    convention to derive, and picking one would be a decision about delivered
    frames dressed as an inference from the data.
    """
    demo = json.loads((EXAMPLES / 'showcase_demo.json').read_text(encoding='utf-8'))
    beat_at_126 = (60.0 / 126.0) * 60
    beat_at_declared = (60.0 / float(demo['bpm'])) * 60
    assert demo['bpm'] == 128.998, (
        f"showcase_demo now declares bpm {demo['bpm']}; the premise that its "
        'durations were authored against 126 no longer holds by inspection.')
    values = durations_of(demo)
    assert values == [229, 229, 114, 229], f'showcase_demo durations moved: {values}'
    assert mean_off_grid(values, beat_at_126) < 0.5, (
        'showcase_demo is no longer on the 126-bpm grid; re-derive the claim '
        'before quoting it.')
    assert mean_off_grid(values, beat_at_declared) > 1.0, (
        'showcase_demo now agrees with its own declared tempo, so the "authored '
        'against the old tempo" account of its durations is wrong.')

    for name in ('charts_demo.json', 'p29_new_renderer_showcase.json'):
        path = EXAMPLES / name if (EXAMPLES / name).exists() else GRAPHS / name
        values = durations_of(json.loads(path.read_text(encoding='utf-8')))
        assert mean_off_grid(values, 10) == 0.0, (
            f'{name} is no longer wholly on the 10-frame grid: {values}. The '
            'three-rules claim needs re-measuring.')


def test_the_tempo_nominated_by_the_reference_film_is_a_different_track():
    """Why 120.19 BPM is not a number to plan against.

    P37 measured ≈120.19 from the reference FILM, and its own record says so in
    as many words: a different audio track from P9's fitted 128.998, and the two
    are not to be discussed together. The rendered graph's tempo is the one
    measured from the track that is actually on this machine
    (`studio/public/audio/bgm_beats.json`), and `test_beat_grid.py` already
    pins that a graph's declared tempo must agree with it.

    So the candidate rules for scene duration were: 120.19 (a different song),
    128.998 (the right song, but `beat_snap` is off and nothing consults it),
    or 126 (what two of the three delivered graphs were written against). This
    test holds the middle one still so the (b) answer cannot be re-derived from
    a number that belongs to a different piece of audio.

    THE COMPARISON IS AN EQUALITY, NOT A SUBSET, AND THAT IS THE POINT.

    The first version of this assertion was `set(declared) <= {126, 128.998}`.
    Mutation A widened the right-hand side to admit 120.19 and the guard stayed
    green — a subset test cannot see its own bound widen, because widening a
    superset of a satisfied subset is always still satisfied. It took a poison
    mutation to notice, which is the entire argument for running them.

    So the claim is bidirectional now: the delivered graphs declare exactly these
    tempi, and 120.19 is specifically not among them. A graph adopting the
    reference film's tempo fails here instead of quietly making (b) wrong.
    """
    declared = {p.name: json.loads(p.read_text(encoding='utf-8')).get('bpm')
                for p in DELIVERED}
    assert declared == {'showcase_demo.json': 128.998,
                        'charts_demo.json': 128.998,
                        'p29_new_renderer_showcase.json': 126}, (
        f'the delivered graphs declare {declared}. Two claims are pinned by this: '
        'that the fitted 128.998 is what the graphs on this machine carry, and '
        'that 120.19 — the reference FILM\'s tempo, a different audio track per '
        'P37 — has not been copied in. If a graph moved, re-derive (b) rather '
        'than widening this.')
    assert 120.19 not in declared.values(), (
        'a delivered graph carries the reference film\'s tempo. P37 measured it '
        'from a DIFFERENT track; adopting it here would make every duration rule '
        'in this file compare against a tempo no delivered film uses.')
    analysis = ROOT / 'studio' / 'public' / 'audio' / 'bgm_beats.json'
    beats = json.loads(analysis.read_text(encoding='utf-8'))['beats']
    assert len(beats) >= 64, 'the beat analysis is too short to be the real one'


# ── (c) a Storyboard would be an identity ───────────────────────────────────

def test_there_is_no_storyboard_and_the_chain_has_no_hole_for_one(tmp_path):
    """The chain is Brief -> StyleBible -> SceneGraph today, and it validates.

    `generate_graph` takes a brief whose scenes are already typed and already
    carry their durations, adds the one style_bible key it can defend, and hands
    the result to `scene_graph.load()`. A Storyboard between those two ends
    would receive exactly what it is asked to emit. There is no layer underneath
    it to plan from and no field above it that wants its output.

    The brief carries a `browser-stack` because that is the ONLY scene type that
    consumes the depth cue, so it is the only brief shape in which P12.1 emits
    one. A brief of renderable-but-unrelated types produces `style_bible: {}` —
    measured, and itself part of the answer: the generator's one output is a
    function of a brief detail, not of a plan.
    """
    brief = brief_with('browser-stack')
    brief['scenes'][0]['content'] = {
        'windows': [{'title': f'w{i}', 'metric': str(i), 'bars': [1, 2, 3]}
                    for i in range(6)],
    }
    generated = generate_graph(brief)
    assert generated.emitted_keys == {'depthCue'}, (
        f'the generator emits {sorted(generated.emitted_keys)} now for a brief '
        'that P12.1 measured as emitting depthCue. A second key with a consumer '
        'is a change to what P36.1 measured; re-decide whether the Storyboard '
        'question is still the same question.')
    loaded = load_graph(generated.graph, tmp_path)
    assert [s['id'] for s in loaded.scenes] == ['s01']
    assert loaded.project == 'p12_2_guard'
    assert loaded.style_bible.get('depthCue') == list(generated.plan.ramp), (
        'the key survived parsing into the graph, but not with the value the '
        'plan derived. The plan and the document have parted ways.')


def test_the_graph_the_generator_produces_really_validates(tmp_path):
    """Both directions of the validator, so "it validates" is not a no-op claim.

    A guard that only ever runs the accepting case is satisfied by a validator
    call that was removed, or moved, or wrapped in a try that swallows. So the
    rejecting case runs too, and it rejects for the right reason: a scene key
    the schema's closed vocabulary does not declare.
    """
    ok = generate_graph(brief_with('quote'))
    loaded = load_graph(ok.graph, tmp_path)
    assert loaded.totalFrames == 150

    # Only `ShowcaseError` is caught. Any other exception is a bug in this test
    # and must surface as one — a probe's crash is not a verdict (P31, P34, P36
    # each lost a cycle to that).
    bad = generate_graph(brief_with('quote', extra_scene_key='ease'))
    with pytest.raises(scene_graph.ShowcaseError) as excinfo:
        load_graph(bad.graph, tmp_path)
    assert 'ease' in str(excinfo.value), (
        f'the validator rejected the graph for an unrelated reason: '
        f'{excinfo.value}')


def test_the_delivered_graphs_are_all_still_loadable():
    """The three graphs the corpus claims are three regimes of is a floor, not a
    ceiling: whatever P12.2 concludes, they must keep loading.

    Cheap, and it is the assertion that would catch a verdict being written
    against a corpus that has since rotted.
    """
    for path in DELIVERED:
        loaded = scene_graph.load(path)
        assert loaded.scenes, f'{path.name} loaded with no scenes'
        assert loaded.totalFrames == sum(
            int(s['durationInFrames']) for s in loaded.scenes)


# ── discrimination: the helpers must be able to say no ──────────────────────

def test_the_helpers_can_say_no():
    """Kills an always-returns-empty implementation of either helper.

    The real inputs above currently find problems, so a helper hardcoded to
    return nothing would pass those and this is what it would fail.
    """
    rendered = {'bar-chart', 'quote', 'logo'}
    assert unrendered_gaps(['bar-chart', 'quote', 'logo'], rendered) == []
    assert unrendered_gaps(['bar-chart', 'video'], rendered) == ['video']
    assert unrendered_gaps(['video', 'data-plane-3d'], rendered) == [
        'data-plane-3d', 'video']
    # a type the schema never declared is a different defect (zod's), so this
    # helper reports it as unrendered rather than pretending to know better
    assert unrendered_gaps(['not-a-type'], rendered) == ['not-a-type']

    assert mean_off_grid([100, 200, 300], 10) == 0.0
    assert mean_off_grid([105], 10) == 5.0
    assert mean_off_grid([229, 114], (60.0 / 126.0) * 60) < 0.5


def test_the_renderers_are_the_real_ones_and_the_template_is_the_source():
    """The parse is held to the files, so a broke parser cannot report a pass.

    Mirrors P26's `test_the_maps_are_the_real_ones`. If `rendered_scene_types()`
    matched nothing, `unrendered` would be all 22 and the gate test above would
    fail for the wrong reason; if it matched the whole file, `rendered` would be
    huge and `test_the_unrendered_set_is_the_two_generative_types_not_nine`
    would fail for the wrong reason. Either way a red means something, which is
    the only reason to check.
    """
    src = TEMPLATE_TSX.read_text(encoding='utf-8')
    assert 'SCENE_RENDERERS' in src, 'the template no longer declares the map'
    assert rendered_scene_types(), 'the renderer parse matched nothing'
    assert 'bar-chart' in rendered_scene_types() and 'quote' in rendered_scene_types()


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))