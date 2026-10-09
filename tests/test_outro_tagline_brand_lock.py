"""`outro` and `content.tagline` must actually be stopped, by a repair. P31.

P30's guard (`test_brand_lock_wiring.py`) established the shape of the problem
this file extends. Its first line is that pinning the VALUE of a constant is not
a guard: `LOCKED_SCENE_TYPES` read `frozenset({'logo'})` with three tests
asserting that value, and a repair that rerouted the logo scene reported zero
violations. So **nothing here asserts what a constant contains.** Every test
calls `diff_locked` and asserts on what comes back.

WHAT P31 RULED, and what each ruling had to survive:

  1. `outro` joins `logo` in `LOCKED_SCENE_TYPES`. Brand.tsx:156-157 reads the
     same `c.name` and `c.tagline` as `Logo` (:122-123) and renders them through
     the same `Lockup`, so the outro shows the same wordmark. Before this, the
     one brand move that reported nothing was "edit the outro's wordmark".
  2. `content.tagline` joins `name` in `BRAND_CONTENT_KEYS`. This one carried
     an edge case the first did not — see THE ASYMMETRY below.

THE ASYMMETRY, AND WHY IT DID NOT CHANGE THE DIRECTION.

    Brand.tsx:93   {name}                       — rendered unconditionally
    Brand.tsx:95   {tagline ? (...) : null}    — rendered CONDITIONALLY

So a brand scene carrying no tagline is a legal authored state, and that is
real evidence. What it does not decide is who may CREATE one. The lock governs
the repair loop, not the renderer's ability to cope: a graph may still be
authored with no tagline, and once one is authored a repair may not move it —
edit, delete or invent. This is the same direction `name` already has, and `name`
is not schema-required either; its absence renders an empty `<div>` and is
nonetheless locked. `test_a_brand_scene_may_lack_a_tagline` is the other half of
that argument: the ruling must not make the legal state illegal.

THE `{'scenes': [...]}` SHAPE, PROVED BEFORE IT IS RELIED ON.

`iter_scene_locked` reads `graph['scenes']`. Hand it a bare scene and it finds
nothing, reports nothing, and every assertion below would pass because it
measured the wrong object — which is exactly how the P30 verification measured
"0 violations" and nearly recorded it as a result. So `_graph()` builds the real
shape, and `test_the_fixture_shape_catches_the_known_brand_scene` drives the
whole guard through it on the case that was already true before P31. If that
fails, the outro results below mean nothing and the failure says so.

Graph: `pipeline/graphs/p29_new_renderer_showcase.json`, the only shipped graph
carrying a `logo` or an `outro`. `test_the_fixture_really_has_both_brand_scenes`
says so out loud, because a guard that passes because its fixture lacks the
thing under test proves nothing.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'studio' / 'scripts'))

import locked_fields as lf  # noqa: E402

BRAND_GRAPH = ROOT / 'pipeline' / 'graphs' / 'p29_new_renderer_showcase.json'
CHART_GRAPH = ROOT / 'pipeline' / 'examples' / 'charts_demo.json'


def _full_graph() -> dict:
    return json.loads(BRAND_GRAPH.read_text(encoding='utf-8'))


def _graph(*scenes: dict) -> dict:
    """A minimal graph in the shape `iter_scene_locked` actually reads."""
    return {'scenes': list(scenes)}


def _scene_of_type(graph: dict, type_name: str) -> dict:
    found = [s for s in graph['scenes'] if s.get('type') == type_name]
    assert found, (
        f'{BRAND_GRAPH.name} has no scene of type {type_name!r}. Every test below '
        'reads as "the lock said nothing", which is exactly what it would say '
        'for the right reason — fix the fixture, not the assertions.'
    )
    return copy.deepcopy(found[0])


def _describe(violations: list) -> str:
    return '; '.join(f'{v.rule.kind} {v.path} {v.before!r}->{v.after!r}'
                     for v in violations) or '(none)'


def _violations(before: dict, after: dict) -> list:
    return lf.diff_locked(before, after)


# ---------------------------------------------------------------------------
# 0. the fixture and the shape, stated so the rest cannot pass vacuously
# ---------------------------------------------------------------------------

def test_the_fixture_really_has_both_brand_scenes():
    graph = _full_graph()
    types = [s.get('type') for s in graph['scenes']]
    for needed in ('logo', 'outro'):
        assert needed in types, (
            f'the P29 graph carries no {needed!r} scene, so the P31 guard has '
            f'nothing to measure: {types}'
        )
    for idx in [i for i, t in enumerate(types) if t in ('logo', 'outro')]:
        content = graph['scenes'][idx].get('content') or {}
        assert content.get('name') and content.get('tagline'), (
            f'scenes[{idx}] ({types[idx]}) carries no name/tagline, so the '
            'wordmark and tagline halves of this guard have nothing to lock'
        )


def test_the_fixture_shape_catches_the_known_brand_scene():
    """⚠️ FIRST, before anything about outro: prove the `{'scenes': [...]}`
    shape is a shape the lock can see, by driving the case P30 already covered.

    If this fails, every `outro` result in this file is measuring the wrong
    object. This is the check the P30 verification skipped.
    """
    logo = _scene_of_type(_full_graph(), 'logo')
    assert 'scenes' in _graph(logo), 'the guard helper is not building the real shape'

    before = _graph(logo)
    renamed = copy.deepcopy(before)
    renamed['scenes'][0]['content']['name'] = 'ACME'

    violations = _violations(before, renamed)
    assert violations, (
        'renaming the LOGO wordmark through the `{\'scenes\': [...]}` shape '
        'reported nothing. Either the shape is wrong or the lock is dead — and '
        'every outro assertion in this file is measured the same way.'
    )
    assert {v.rule.key for v in violations} == {'name'}, _describe(violations)
    assert all(v.rule.kind == 'brand' for v in violations), _describe(violations)


# ---------------------------------------------------------------------------
# 1. ruling 1 — the outro's wordmark is caught
# ---------------------------------------------------------------------------

OUTRO_ATTACKS: dict[str, object] = {
    'rewrite the outro wordmark':
        lambda s: s['content'].__setitem__('name', 'ACME'),
    'delete the outro wordmark':
        lambda s: s['content'].pop('name'),
    'reroute the outro to a chart':
        lambda s: s.__setitem__('type', 'bar-chart'),
    'rewrite the outro tagline':
        lambda s: s['content'].__setitem__('tagline', 'enterprise lending'),
    'delete the outro tagline':
        lambda s: s['content'].pop('tagline'),
}


def _outro_before() -> dict:
    return _graph(_scene_of_type(_full_graph(), 'outro'))


def test_inventing_a_tagline_where_there_was_none_is_caught():
    """The direction the conditional render made a genuine question.

    Brand.tsx:95 renders the tagline behind a ternary, so its absence is legal.
    The ruling is that a REPAIR may not create one — `diff_locked` walks both
    graphs, so this is the second `emit()` pass doing the work. Without it the
    whole ruling would be one-directional and the surprising half unguarded.
    """
    bare = _outro_before()
    bare['scenes'][0]['content'].pop('tagline')

    invented = copy.deepcopy(bare)
    invented['scenes'][0]['content']['tagline'] = 'financial infrastructure'

    violations = _violations(bare, invented)
    assert violations, (
        'writing a tagline onto a brand scene that had none produced no finding. '
        'A repair may not author the brand, in either direction.'
    )
    assert {v.rule.key for v in violations} == {'tagline'}, _describe(violations)
    assert all(v.rule.kind == 'brand' for v in violations), _describe(violations)


@pytest.mark.parametrize('attack', sorted(OUTRO_ATTACKS))
def test_outro_attacks_are_caught(attack):
    """Every brand move on an `outro` scene reports, through `diff_locked`."""
    before = _outro_before()
    after = copy.deepcopy(before)
    OUTRO_ATTACKS[attack](after['scenes'][0])

    violations = _violations(before, after)
    assert violations, (
        f'{attack!r} changed a brand-locked field on an outro scene and '
        'diff_locked said nothing. This is the P30 state one scene type over: '
        'LOCKED_SCENE_TYPES holds a value nothing observes.'
    )
    assert all(v.rule.kind == 'brand' for v in violations), (
        'outro brand moves must report as kind "brand". '
        f'Got: {_describe(violations)}'
    )
    assert {v.path.split('.')[-1] for v in violations} <= {'name', 'tagline', 'type'}, (
        f'expected the finding to sit on the type or a brand content key: '
        f'{_describe(violations)}'
    )


def test_deleting_the_outro_scene_entirely_is_caught():
    before = _outro_before()
    after = copy.deepcopy(before)
    del after['scenes'][0]
    violations = _violations(before, after)
    assert violations, (
        'removing the outro scene produced no finding — the brand mark is lost '
        'by deletion exactly as much as by an edit.'
    )
    assert all(v.rule.kind == 'brand' for v in violations), _describe(violations)


def test_an_untouched_outro_graph_produces_no_findings():
    """The other direction. Without this, every attack above passes for free —
    a lock that fires on an unchanged graph reports them all, correctly."""
    graph = _outro_before()
    assert _violations(graph, copy.deepcopy(graph)) == [], (
        'diff_locked reports a difference between the outro graph and itself'
    )


# ---------------------------------------------------------------------------
# 2. the lock STOPS at the brand — on the newly-locked outro
# ---------------------------------------------------------------------------
#
# The outro joined the lock in P31 and none of these levers were ever checked on
# it. A lock that widens to a new scene type without re-running this direction
# is exactly how 11.1 quietly stops working.

OUTRO_LEVERS: dict[str, object] = {
    'durationInFrames': lambda s: s.__setitem__(
        'durationInFrames', s.get('durationInFrames', 100) + 40),
    'camera': lambda s: s.setdefault('camera', {}).__setitem__('translateZ', 2500),
    'motion': lambda s: s.__setitem__('motion', {'preset': 'energetic'}),
    'layout': lambda s: s.setdefault('layout', {}).__setitem__('padX', 120),
    'style_bible': lambda s: s.__setitem__('style_bible', {'palette': {'accent': '#FF0000'}}),
    'transitionIn': lambda s: s.__setitem__(
        'transitionIn', {'in': 'fade', 'durationInFrames': 30}),
    'transitionOut': lambda s: s.__setitem__(
        'transitionOut', {'out': 'fade', 'durationInFrames': 30}),
    'format': lambda s: s.__setitem__('format', {'width': 1080, 'height': 1920}),
    'notes': lambda s: s.__setitem__('notes', 'a repair left a note'),
    # `cta` and `sub` are the outro's OWN copy — Brand.tsx:154-155 reads them
    # and Lockup does not. Locking them would be the over-lock the ruling was
    # NOT made about: it locked the brand, not the call to action.
    'cta': lambda s: s['content'].__setitem__('cta', 'Book a walkthrough'),
    'sub': lambda s: s['content'].__setitem__('sub', 'meridian.example'),
}


@pytest.mark.parametrize('lever', sorted(OUTRO_LEVERS))
def test_11_1_levers_still_pass_on_an_outro_scene(lever):
    before = _outro_before()
    after = copy.deepcopy(before)
    OUTRO_LEVERS[lever](after['scenes'][0])

    violations = _violations(before, after)
    assert violations == [], (
        f'the brand lock rejected {lever!r} on an `outro` scene. 11.1 names the '
        'first seven as the repair loop\'s legitimate moves; a lock that blocks '
        'them looks exactly like working right up until someone tries to use '
        f'it. Caught: {_describe(violations)}'
    )


def test_a_brand_scene_may_lack_a_tagline():
    """The other half of the Brand.tsx:95 asymmetry: the ruling must not make
    the renderer's legal state illegal.

    A graph authored with no tagline on a brand scene has to be perfectly
    quiet — otherwise the lock would force every author to invent a tagline
    before they could be repaired, which is a lock on authoring rather than on
    repair, and is the reason the direction was argued rather than assumed.
    """
    bare = _outro_before()
    bare['scenes'][0]['content'].pop('tagline')

    assert _violations(bare, copy.deepcopy(bare)) == [], (
        'a brand scene with no tagline reports a violation against itself'
    )
    # and a repair that changes staging, not the lockup, is still allowed there
    staged = copy.deepcopy(bare)
    staged['scenes'][0]['durationInFrames'] += 30
    assert _violations(bare, staged) == [], (
        '11.1 levers are blocked on a tagline-less brand scene'
    )
    # and a non-brand key may be added to it freely
    annotated = copy.deepcopy(bare)
    annotated['scenes'][0]['content']['sub'] = 'a new subtitle'
    assert _violations(bare, annotated) == [], (
        'a non-brand content key was blocked on a brand scene'
    )


def test_a_non_brand_scene_may_carry_its_own_name_and_tagline():
    """Over-lock, and the reason both rulings stay off `LOCK_RULES`.

    `_RULES_BY_KEY` matches a content key in EVERY scene and `content` is
    `z.record(z.string(), z.unknown())`. Had `name` or `tagline` been added to
    LOCK_RULES, a future scene whose `name` is a person or a product would be
    locked by the brand rule, silently, and no other test would have said so.
    """
    graph = json.loads(CHART_GRAPH.read_text(encoding='utf-8'))
    assert graph['scenes'][0].get('type') not in lf.LOCKED_SCENE_TYPES, (
        'charts_demo gained a brand scene; this test is now measuring the wrong '
        'thing and its fixture needs re-reading'
    )
    after = copy.deepcopy(graph)
    content = after['scenes'][0].setdefault('content', {})
    content['name'] = 'a product name'
    content['tagline'] = 'a product tagline'

    assert _violations(graph, after) == [], (
        'a bar-chart scene carrying its own name/tagline was locked by the '
        'brand rule. The brand lock is scoped to LOCKED_SCENE_TYPES, not '
        f'applied by content key everywhere. Caught: {_describe(_violations(graph, after))}'
    )


def test_a_non_brand_scene_type_may_still_be_rerouted():
    """Over-lock, direction one, re-checked now that the set has two members.

    This is the assertion that makes the "emit for every scene type" mutation
    red. Such a mutation catches strictly MORE, so it passes every
    "does the lock catch?" test in this file and would read as hardening.
    """
    before = _graph(_scene_of_type(_full_graph(), 'quote'))
    after = copy.deepcopy(before)
    after['scenes'][0]['type'] = 'stat-card'

    assert _violations(before, after) == [], (
        'repointing a NON-brand scene\'s type reported a brand violation. The '
        f'brand lock is scoped to LOCKED_SCENE_TYPES. Caught: {_describe(_violations(before, after))}'
    )


def test_the_lock_follows_the_constant_for_the_new_type(monkeypatch):
    """P30 proved the scene-type channel reads the constant; `outro` is new
    territory for it, so re-point the constant and watch the lock move."""
    before = _graph(_scene_of_type(_full_graph(), 'quote'))
    monkeypatch.setattr(lf, 'LOCKED_SCENE_TYPES', frozenset({'quote'}))
    after = copy.deepcopy(before)
    after['scenes'][0]['type'] = 'stat-card'

    assert _violations(before, after), (
        'LOCKED_SCENE_TYPES was re-pointed at "quote" and rerouting a quote '
        'scene was still allowed — diff_locked is not reading the constant'
    )


# ---------------------------------------------------------------------------
# 3. coverage now describes both rulings
# ---------------------------------------------------------------------------

def test_coverage_reports_both_rulings_reaching_the_graph():
    cov = lf.coverage_report({'brand': _full_graph()})
    scene_locks = cov['scene_locks']
    assert scene_locks['unexercised'] == [], (
        f'the only shipped graph with brand scenes reports blind spots '
        f'{scene_locks["unexercised"]}'
    )
    assert set(scene_locks['exercised_scene_types']) == {'logo', 'outro'}, (
        f'coverage_report exercises {scene_locks["exercised_scene_types"]}; both '
        'ruled scene types should be reached by the graph that carries both'
    )
    assert set(scene_locks['exercised_content_keys']) == {'name', 'tagline'}, (
        f'coverage_report exercises content keys {scene_locks["exercised_content_keys"]}; '
        'both ruled brand keys should be reached by the graph that carries both'
    )
    assert set(cov['by_kind']['brand']) == {'type', 'name', 'tagline'}, cov['by_kind']