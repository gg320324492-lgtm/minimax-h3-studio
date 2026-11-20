"""The brand lock must actually stop a repair. P30.

`LOCKED_SCENE_TYPES` existed from P11 to P30 with a comment promising that brand
meaning "must survive a repair", three tests pinning its VALUE, and no code
reading it. Those three tests stayed green the entire time, because pinning the
value of a constant says the constant is spelled correctly, not that anything
observes what it means. Measured before P30: rerouting the `logo` scene to
`bar-chart` reported 0 violations, and `by_kind['brand']` was `[]`.

**So nothing in this file asserts that a name exists.** Every test here calls
`diff_locked` and looks at what comes back. That is the only question the ledger
is actually asking — "can a repair move the brand?" — and the only one that can
go red when the answer changes.

The three questions this guard has to answer:

  1. Does the lock CATCH? Rerouting a brand scene, renaming it, deleting it, or
     deleting its wordmark are all violations, reported with kind `brand`.
  2. Does the lock STOP AT THE BRAND? Everything that is not the brand keeps
     moving. 11.1 names the levers; a lock that blocks them leaves a repair loop
     unable to repair anything, and the only symptom is a loop that silently
     does nothing. That is the failure a lock is most tempted into, because it
     always "passes" the tests above it.
  3. Is the constant WIRED or merely PRESENT? `test_the_lock_follows_the_set_it
     _is_given` re-points `LOCKED_SCENE_TYPES` at a different scene type at
     runtime and asserts the lock follows. A hardcoded `'logo'` literal fails it;
     reading the constant passes it. This is the P21 shape — two call sites, one
     of them holding a literal — measured rather than hoped about.

Graph choice: `pipeline/graphs/p29_new_renderer_showcase.json` is the only
shipped graph containing a `logo` scene. `test_the_fixture_really_has_a_brand_
scene` says so out loud, because a guard that passes because its fixture has no
brand scene proves nothing.
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


def _brand_graph() -> dict:
    return json.loads(BRAND_GRAPH.read_text(encoding='utf-8'))


def _chart_graph() -> dict:
    return json.loads(CHART_GRAPH.read_text(encoding='utf-8'))


def _brand_index(graph: dict) -> int:
    idx = [i for i, s in enumerate(graph['scenes']) if s.get('type') == 'logo']
    assert idx, (
        f'{BRAND_GRAPH.name} has no scene of type "logo". Every test below reads '
        'as "the lock said nothing", which is exactly what it would have said for '
        'the right reason — fix the fixture, not the assertions.'
    )
    return idx[0]


def _first_of_type(graph: dict, type_name: str) -> int:
    idx = [i for i, s in enumerate(graph['scenes']) if s.get('type') == type_name]
    assert idx, f'fixture assumption: no {type_name!r} scene in this graph'
    return idx[0]


def _describe(violations: list) -> str:
    return '; '.join(f'{v.rule.kind} {v.path} {v.before!r}->{v.after!r}'
                      for v in violations) or '(none)'


# ---------------------------------------------------------------------------
# 0. the fixture, stated so the tests below cannot pass vacuously
# ---------------------------------------------------------------------------

def test_the_fixture_really_has_a_brand_scene():
    """Measure the object before measuring the lock. P20/P21/P22 each produced a
    `NameError` from measuring something that was not there."""
    graph = _brand_graph()
    idx = _brand_index(graph)
    assert graph['scenes'][idx]['content'].get('name'), (
        'the logo scene carries no content.name, so the wordmark half of this '
        'guard has nothing to lock'
    )
    assert lf.iter_scene_locked(graph), (
        'iter_scene_locked found nothing in the one shipped graph that HAS a '
        'brand scene — the brand lock is not wired'
    )


# ---------------------------------------------------------------------------
# 1. the lock catches
# ---------------------------------------------------------------------------

BRAND_ATTACKS: dict[str, tuple[object, str]] = {
    # name -> (mutator, expected rule key)
    'reroute the brand scene to a chart': (
        lambda g, i: g['scenes'][i].__setitem__('type', 'bar-chart'), 'type'),
    'reroute the brand scene to another brand-shaped scene': (
        lambda g, i: g['scenes'][i].__setitem__('type', 'outro'), 'type'),
    'rename the wordmark': (
        lambda g, i: g['scenes'][i]['content'].__setitem__('name', 'ACME'), 'name'),
    'delete the wordmark': (
        lambda g, i: g['scenes'][i]['content'].pop('name'), 'name'),
}


@pytest.mark.parametrize('attack', sorted(BRAND_ATTACKS))
def test_an_attack_on_the_brand_is_caught(attack):
    mutate, expected_key = BRAND_ATTACKS[attack]
    before = _brand_graph()
    idx = _brand_index(before)
    after = copy.deepcopy(before)
    mutate(after, idx)

    violations = lf.diff_locked(before, after)
    assert violations, (
        f'{attack!r} changed a brand-locked field and diff_locked said nothing. '
        'This is the P29/P30 state: LOCKED_SCENE_TYPES exists, is documented, and '
        'is read by nobody.'
    )
    keys = {v.rule.key for v in violations}
    assert expected_key in keys, (
        f'{attack!r} was caught as {sorted(keys)}, expected {expected_key!r}. A '
        f'lock reporting the wrong reason is a different lock. Got: {_describe(violations)}'
    )
    assert all(v.rule.kind == 'brand' for v in violations), (
        'brand moves must be reported as kind "brand", which is the ledger\'s '
        f'third noun and the by_kind bucket that read [] before P30. Got: {_describe(violations)}'
    )


def test_inventing_a_wordmark_where_there_was_none_is_caught():
    """The direction only the reverse `emit()` pass can see.

    Nothing in `iter_locked(before)` has a `name` to compare against, so a
    single-direction diff reports nothing at all — which is exactly how the
    second `emit()` was found missing for content fields in P21. The brand rule
    is a third place that could lose the same way.
    """
    before = _brand_graph()
    idx = _brand_index(before)
    stripped = copy.deepcopy(before)
    stripped['scenes'][idx]['content'].pop('name')

    invented = copy.deepcopy(stripped)
    invented['scenes'][idx]['content']['name'] = 'ACME'

    violations = lf.diff_locked(stripped, invented)
    assert violations, (
        'writing a wordmark onto a brand scene that had none produced no '
        'finding. A repair may not author the brand either.'
    )
    assert any(v.rule.kind == 'brand' for v in violations), _describe(violations)


def test_deleting_the_brand_scene_entirely_is_caught():
    """Deletion, not editing. The loss of a scene is the easiest way to lose a
    brand mark and the one a collision repair reaches for last."""
    before = _brand_graph()
    idx = _brand_index(before)
    after = copy.deepcopy(before)
    del after['scenes'][idx]

    violations = lf.diff_locked(before, after)
    assert violations, (
        'removing the brand scene from the graph produced no finding. A repair '
        'may not achieve a brand lock by deleting the scene that carries it.'
    )
    assert any(v.rule.kind == 'brand' for v in violations), _describe(violations)


def test_an_untouched_brand_graph_produces_no_findings():
    """The other direction, on the brand scene specifically. A lock that fires on
    an identical graph would make every reroute test above pass for free."""
    graph = _brand_graph()
    assert lf.diff_locked(graph, copy.deepcopy(graph)) == [], (
        'diff_locked reports a difference between a graph and itself — the brand '
        'rule is comparing something it should not be'
    )


@pytest.mark.parametrize('attack', sorted(BRAND_ATTACKS))
def test_brand_violations_survive_argument_order(attack):
    """`diff_locked` already has this invariant for content fields; a second
    code path that lacks it would let a repairer launder a rename by swapping
    its arguments."""
    mutate, _key = BRAND_ATTACKS[attack]
    a = _brand_graph()
    idx = _brand_index(a)
    b = copy.deepcopy(a)
    mutate(b, idx)
    forward = lf.diff_locked(a, b)
    reverse = lf.diff_locked(b, a)
    assert len(forward) == len(reverse), (
        f'{attack!r}: forward found {len(forward)}, reverse found {len(reverse)}. '
        f'Forward: {_describe(forward)}. Reverse: {_describe(reverse)}.'
    )


# ---------------------------------------------------------------------------
# 2. the lock stops at the brand — 11.1's levers, on the BRAND scene
# ---------------------------------------------------------------------------
#
# The levers are checked on a `logo` scene, not on a chart. That is the whole
# point: a brand lock that locks the scene wholesale, or that fires on every key
# under it, passes every test in section 1 and leaves a repairer nothing.

LEVERS_ON_THE_BRAND_SCENE: dict[str, object] = {
    'durationInFrames': lambda s: s.__setitem__(
        'durationInFrames', s.get('durationInFrames', 100) + 40),
    'camera.translateZ': lambda s: s.setdefault('camera', {}).__setitem__(
        'translateZ', 2500),
    'motion': lambda s: s.__setitem__('motion', {'preset': 'energetic'}),
    'layout.padX': lambda s: s.setdefault('layout', {}).__setitem__('padX', 120),
    'style_bible': lambda s: s.__setitem__(
        'style_bible', {'palette': {'accent': '#FF0000'}}),
    'transitionIn': lambda s: s.__setitem__(
        'transitionIn', {'in': 'fade', 'durationInFrames': 30}),
    'transitionOut': lambda s: s.__setitem__(
        'transitionOut', {'out': 'fade', 'durationInFrames': 30}),
    'notes': lambda s: s.__setitem__('notes', 'a repair left a note'),
}


@pytest.mark.parametrize('lever', sorted(LEVERS_ON_THE_BRAND_SCENE))
def test_the_11_1_levers_still_pass_on_a_brand_scene(lever):
    mutate = LEVERS_ON_THE_BRAND_SCENE[lever]
    before = _brand_graph()
    idx = _brand_index(before)
    after = copy.deepcopy(before)
    mutate(after['scenes'][idx])

    violations = lf.diff_locked(before, after)
    assert violations == [], (
        f'the brand lock rejected {lever!r} on a `logo` scene. 11.1 lists these '
        f'as the repair loop\'s legitimate moves; locking them makes repair '
        f'impossible, and impossible looks exactly like working until someone '
        f'tries. Caught: {_describe(violations)}'
    )


def test_the_whole_film_format_still_passes_on_a_graph_carrying_a_brand_scene():
    before = _brand_graph()
    after = copy.deepcopy(before)
    after['format'] = {**after['format'], 'width': 1080, 'height': 1920}
    assert lf.diff_locked(before, after) == [], (
        f'the brand lock rejected a re-frame of the whole film. Caught: '
        f'{_describe(lf.diff_locked(before, after))}'
    )


def test_a_non_brand_scene_may_be_rerouted_freely():
    """Over-lock, direction one: only a BRAND scene's type is locked.

    This is the assertion that makes the mutation "emit for every scene type"
    red. Such a mutation passes every test in section 1 — it catches strictly
    more — so without this it would look like hardening.
    """
    before = _brand_graph()
    idx = _first_of_type(before, 'browser-window')
    after = copy.deepcopy(before)
    after['scenes'][idx]['type'] = 'card-grid'

    violations = lf.diff_locked(before, after)
    assert violations == [], (
        f'repointing a non-brand scene\'s type was reported as a brand '
        f'violation. The brand lock is scoped to LOCKED_SCENE_TYPES; a rule that '
        f'applies to every scene type would make every repair impossible. '
        f'Caught: {_describe(violations)}'
    )


def test_a_non_brand_scene_may_carry_its_own_name():
    """Over-lock, direction two, and the reason the brand lock is keyed on the
    scene TYPE rather than added to LOCK_RULES.

    `_RULES_BY_KEY` matches a content key in EVERY scene. Had `name` been added
    to LOCK_RULES, a future scene with a `name` that is not the brand — a product
    name, a person's name — would have been locked by the brand rule, silently,
    and no existing test would have said so. `content` is
    `z.record(z.string(), z.unknown())` (showcase-v1.ts), so that scene is not
    hypothetical; it is only unwritten.
    """
    before = _chart_graph()
    after = copy.deepcopy(before)
    after['scenes'][0].setdefault('content', {})['name'] = 'something else'
    assert lf.diff_locked(before, after) == [], (
        'a bar-chart scene carrying content.name was locked by the brand rule. '
        'The brand lock must be scoped to LOCKED_SCENE_TYPES, not applied by '
        'content key everywhere.'
    )

    # and the same edit IS caught once the scene really is a brand scene
    brand = _brand_graph()
    brand_idx = _brand_index(brand)
    brand_after = copy.deepcopy(brand)
    brand_after['scenes'][brand_idx]['content']['name'] = 'something else'
    assert lf.diff_locked(brand, brand_after), (
        'the lock distinguishes nothing between a chart\'s content.name and a '
        'logo\'s content.name — the scene-type scoping is not doing anything'
    )


# ---------------------------------------------------------------------------
# 3. the constant is WIRED, not merely present
# ---------------------------------------------------------------------------

def test_the_lock_follows_the_set_it_is_given(monkeypatch):
    """The P21 shape, measured: a constant that one call site reads while
    another holds a literal.

    Re-point `LOCKED_SCENE_TYPES` at a scene type that is not `logo` and assert
    the lock moves with it. Reading the constant passes; hardcoding `'logo'`
    fails. Nothing here knows the value is `{'logo'}` — which is the point: the
    three tests that DID know are what let this run unchecked for a year.
    """
    before = _brand_graph()
    quote_idx = _first_of_type(before, 'quote')

    monkeypatch.setattr(lf, 'LOCKED_SCENE_TYPES', frozenset({'quote'}))
    after = copy.deepcopy(before)
    after['scenes'][quote_idx]['type'] = 'bar-chart'

    violations = lf.diff_locked(before, after)
    assert violations, (
        'LOCKED_SCENE_TYPES was re-pointed at "quote" and rerouting the quote '
        'scene was still allowed. diff_locked is not reading the constant — it '
        'has its own copy of the list, or a literal.'
    )

    # and the lock must NOT stay on logo once the set moved
    still_locking_logo = copy.deepcopy(before)
    logo_idx = _brand_index(before)
    still_locking_logo['scenes'][logo_idx]['type'] = 'bar-chart'
    assert lf.diff_locked(before, still_locking_logo) == [], (
        'after re-pointing LOCKED_SCENE_TYPES at "quote", the logo scene is '
        'still protected — the constant is not the only source of truth'
    )


def test_the_brand_content_keys_are_read_too(monkeypatch):
    """Same question for the second half of the lock. `BRAND_CONTENT_KEYS` is
    the constant, so re-pointing it must move the wordmark lock with it."""
    before = _brand_graph()
    idx = _brand_index(before)
    tagline = before['scenes'][idx]['content'].get('tagline')
    assert tagline, 'fixture assumption: the logo scene carries a tagline'

    monkeypatch.setattr(lf, 'BRAND_CONTENT_KEYS', ('tagline',))
    monkeypatch.setattr(lf, '_BRAND_RULES', {
        'tagline': lf.LockRule('tagline', 'brand', 'mutated')})

    after = copy.deepcopy(before)
    after['scenes'][idx]['content']['tagline'] = 'enterprise lending'
    assert lf.diff_locked(before, after), (
        'BRAND_CONTENT_KEYS was re-pointed at "tagline" and rewriting the '
        'tagline was still allowed — the key list is read from somewhere else'
    )

    after2 = copy.deepcopy(before)
    after2['scenes'][idx]['content']['name'] = 'ACME'
    assert lf.diff_locked(before, after2) == [], (
        'after re-pointing BRAND_CONTENT_KEYS at "tagline", the wordmark is '
        'still locked — there is a second, unwired source of brand keys'
    )


# ---------------------------------------------------------------------------
# 4. coverage: (c) — what by_kind and unexercised now say
# ---------------------------------------------------------------------------

def test_by_kind_brand_is_no_longer_empty():
    """`by_kind['brand']` read `[]` before P30. The kind was RESERVED from P11 —
    declared in the LockRule comment, listed in coverage_report's tuple, allowed
    by the wiring test — with no rule ever using it, which is why the ledger
    could only report "fact 9 / copy 4 / identity 1" while naming three nouns.
    No fourth kind was needed; the slot was already built."""
    cov = lf.coverage_report({'brand': _brand_graph()})
    assert cov['by_kind']['brand'], (
        f"by_kind['brand'] is still empty: {cov['by_kind']['brand']}. Either the "
        'brand rule is unwired or coverage_report is no longer counting it.'
    )
    assert set(cov['by_kind']['brand']) == {'type', *lf.BRAND_CONTENT_KEYS}, (
        f"by_kind['brand'] lists {cov['by_kind']['brand']}; it should name exactly "
        f"the scene type rule plus BRAND_CONTENT_KEYS {list(lf.BRAND_CONTENT_KEYS)}"
    )
    for kind in ('fact', 'copy', 'identity'):
        assert cov['by_kind'][kind], f'{kind} bucket emptied — unrelated regression'


def test_the_brand_lock_is_visible_in_coverage():
    """A lock that cannot be seen in its own coverage report has invisible blind
    spots, which is the failure `coverage_report` exists to prevent."""
    graph = _brand_graph()
    fixture_types = {s.get('type') for s in graph['scenes']}
    assert {'logo', 'outro'} <= fixture_types, (
        f'the fixture no longer carries both brand scenes, so every claim below '
        f'reads as "the lock reached everything that was there" whether or not '
        f'it did. Fix the fixture, not the assertions: {sorted(fixture_types)}'
    )
    cov = lf.coverage_report({'brand': graph})
    scene_locks = cov.get('scene_locks')
    assert scene_locks, (
        'coverage_report has no scene_locks section, so the brand lock is '
        'invisible in the one place its blind spots are supposed to show'
    )
    assert scene_locks['unexercised'] == [], (
        f'the only shipped graph with a brand scene reports unexercised '
        f'{scene_locks["unexercised"]}; the lock is not reaching it'
    )
    # ⚠️ P31: this used to read `== ['logo']`. P30 wrote the literal while
    # `outro` was an OPEN question, and leaving it would have turned the ruling
    # into a red suite instead of a recorded decision. It is now computed from
    # the fixture rather than pinned, because coverage_report's job is to
    # describe the graph it was handed — and the `unexercised` assertion above,
    # not this one, is what carries the weight.
    assert set(scene_locks['exercised_scene_types']) == (
        fixture_types & set(lf.LOCKED_SCENE_TYPES)), (
        f'coverage_report reports exercised scene types '
        f'{scene_locks["exercised_scene_types"]} for a graph holding '
        f'{sorted(fixture_types)}; it is not describing what it was given'
    )
    assert scene_locks['exercised_content_keys'] == sorted(lf.BRAND_CONTENT_KEYS), (
        scene_locks)


def test_coverage_of_the_example_graphs_reports_the_brand_lock_as_unexercised():
    """The blind spot is real and must be visible rather than silent.

    `pipeline/examples/*.json` contains no `logo` scene, so over THOSE graphs the
    brand lock is genuinely unexercised. Saying so is the fix; not saying so is
    what P11 did.
    """
    graphs = {p.name: json.loads(p.read_text(encoding='utf-8'))
              for p in sorted((ROOT / 'pipeline' / 'examples').glob('*.json'))}
    scene_locks = lf.coverage_report(graphs)['scene_locks']
    assert scene_locks['exercised_scene_types'] == [], (
        'the example graphs are supposed to carry no brand scene; if one now '
        'does, this assertion is stale and should be re-read rather than deleted'
    )
    assert set(lf.LOCKED_SCENE_TYPES) <= set(scene_locks['unexercised']), (
        f'the brand lock is not reported as a blind spot over the example '
        f'graphs: {scene_locks}'
    )


def test_the_field_rule_coverage_contract_is_unchanged():
    """`unexercised` means "a LOCK_RULES key no graph hits" and nothing else.

    It is asserted by `test_every_rule_is_exercised_by_the_shipped_graphs` and
    cited in the ledger as zero. Widening it to cover the brand lock would
    silently redefine a number other documents quote — so the brand lock got its
    own `scene_locks` section instead of being folded in here.
    """
    graphs = {p.name: json.loads(p.read_text(encoding='utf-8'))
              for p in sorted((ROOT / 'pipeline' / 'examples').glob('*.json'))}
    cov = lf.coverage_report(graphs)
    assert cov['unexercised'] == [], cov['unexercised']
    assert cov['rules'] == len(lf.LOCK_RULES) == 14, (
        f'P30 must not add to or remove from the 14 LOCK_RULES: {cov["rules"]}'
    )


# ---------------------------------------------------------------------------
# 5. the standing decisions a reader has to know about
# ---------------------------------------------------------------------------

def test_the_rulings_are_recorded_in_the_source():
    """Both product questions are now RULED (P31), and the source says so.

    P30 wrote them down as open and pinned the note so it could not be quietly
    deleted. That worked — and it created the next obligation: a source that
    still reads "still has to decide" beside a constant that already decided is
    a comment that outlived its decision, which is the specific failure the note
    was written to prevent. So this now asserts the note is present, names BOTH
    questions, and no longer advertises them as open.

    ⚠️ This is a text assertion about a text record, which is the one place a
    text assertion is the right tool: the subject IS the prose. It is NOT how
    the lock itself is verified — that is `diff_locked`, above, and nothing in
    this file claims otherwise.
    """
    src = (ROOT / 'studio' / 'scripts' / 'locked_fields.py').read_text(encoding='utf-8')
    note = src.split('THE TWO RULINGS A READER HAD TO MAKE', 1)
    assert len(note) == 2, (
        'the brand rulings were removed from locked_fields.py. They were the '
        'evidence for two decisions someone will eventually ask about; say '
        'which way in the commit message if they are being reversed.'
    )
    assert 'WHAT A READER STILL HAS TO DECIDE' not in src, (
        'the source still advertises the brand questions as undecided while '
        'LOCKED_SCENE_TYPES and BRAND_CONTENT_KEYS now decide them. The note '
        'was updated in P31; this header is what it replaced.'
    )
    for ruled_question in ('outro', 'tagline'):
        assert ruled_question in note[1], (
            f'the rulings note no longer mentions {ruled_question!r}, which was '
            'decided in P31'
        )
    assert note[1].count('RULED') >= 2, (
        'the note names both questions but records neither as ruled — it reads '
        'as open while the constants decide'
    )
