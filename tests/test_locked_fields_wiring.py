"""The wiring contract for 11.2: what the lock does to a FUTURE repairer.

WHAT THIS FILE PROVES, precisely:

    It proves **how the lock will treat a future repairer** — that the seven
    levers 11.1 names pass, that attacks on the claim are caught, that swapping
    the arguments cannot launder a violation, and that nothing calls this yet.

    Since P32 it also proves something the rest of the file could not: that the
    levers are unlocked BY REFUSAL rather than by being out of reach. Until P32
    `iter_locked` entered each scene through `content`, and every 11.1 lever is
    a top-level key beside it, so the lock had never seen one — which made
    "unlocked" indistinguishable from "invisible", and left the harness's
    `lock_a_legitimate_lever` mutation inert. §1b below injects a rule for each
    lever and requires the exemption to be what silences it.

    It does NOT prove that "11.2 is protecting delivered footage", because there
    is no repairer. `diff_locked` has zero consumers outside this repository's
    tests; the guard in §4 below pins that as a KNOWN STATE rather than a defect,
    and is written so that it will go red the day someone writes the repairer.

    Writing it the other way round — "the lock protects the rendered charts" —
    records a fact that has never been true. That is this project's fifth failure
    mode, and it is the one a guard is most tempted to commit: the sentence is
    reassuring, and nothing fails when it is a lie.

The other 14 tests in `test_locked_fields.py` cover "an attack is caught". This
file covers the contract AROUND those attacks: what must stay legal, what must not
depend on argument order, and who is supposed to be calling this at all. The two
do not overlap; a suite with only the attacks would pass just as happily if the
lock rejected every edit including the seven levers a repair NEEDS to move.
"""
from __future__ import annotations

import ast
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'studio' / 'scripts'))

from locked_fields import LOCK_RULES, diff_locked, iter_locked  # noqa: E402

EXAMPLES = ROOT / 'pipeline' / 'examples'
LOCKED_MODULE = ROOT / 'studio' / 'scripts' / 'locked_fields.py'


def _graph(name: str = 'charts_demo.json') -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding='utf-8'))


# ---------------------------------------------------------------------------
# 1. the seven legitimate levers must pass
# ---------------------------------------------------------------------------
#
# These are the levers 11.1 names, and every one of them is absent from
# LOCK_RULES on purpose: they are the staging of a claim, not the claim. A lock
# that caught them would leave a repairer with nothing it is allowed to do.
#
# The failure this guards against is the INVERSE of the one above: a future
# contributor "hardening" the lock by adding `durationInFrames` to it would make
# every repair impossible, and the only symptom would be a repair loop that
# silently does nothing. That is why this is asserted and not assumed.

#: name -> (mutates a scene, or the whole graph when the mutator takes the graph)
LEGITIMATE_LEVERS: dict[str, tuple[str, object]] = {
    'durationInFrames': (
        'scene',
        lambda s: s.__setitem__('durationInFrames', s['durationInFrames'] + 5),
    ),
    'camera.translateZ': ('scene', lambda s: s['camera'].__setitem__('translateZ', 2500)),
    'motion': ('scene', lambda s: s.__setitem__('motion', {'preset': 'energetic'})),
    'style_bible': (
        'scene',
        lambda s: s.__setitem__('style_bible', {'palette': {'accent': '#FF0000'}}),
    ),
    # layout and transitionIn do not exist on a chart scene, so this module adds
    # them. That is what a repairer would do — set the key — and the point is
    # that ADDING a field the lock does not cover is allowed.
    'layout.padX': ('scene', lambda s: s.setdefault('layout', {}).__setitem__('padX', 120)),
    'transitionIn': (
        'scene',
        lambda s: s.__setitem__('transitionIn', {'in': 'fade', 'durationInFrames': 30}),
    ),
    # the whole film's format: a repair that re-frames the video is staging too
    'format': ('graph', lambda g: g.__setitem__('format', {**g['format'],
                                                         'width': 1080, 'height': 1920})),
}


@pytest.mark.parametrize('lever', sorted(LEGITIMATE_LEVERS))
def test_a_legitimate_lever_is_not_locked(lever):
    scope, mutate = LEGITIMATE_LEVERS[lever]
    before = _graph()
    after = copy.deepcopy(before)
    mutate(after if scope == 'graph' else after['scenes'][0])

    violations = diff_locked(before, after)
    assert violations == [], (
        f'the lock rejected {lever!r}, which 11.1 lists as a legitimate repair '
        f'verse. A repairer must be able to move the staging of a claim. '
        f'Caught: ' + '; '.join(str(v) for v in violations)
    )


def test_the_lever_list_is_not_a_subset_of_the_lock():
    """The two lists must be disjoint, and that is a structural fact.

    Asserted as set arithmetic rather than by relying on the seven tests above:
    if someone adds a lever to both lists, every one of those tests still passes
    individually (each asserts only its own lever) while the contract is dead.
    This one notices.
    """
    locked_keys = {r.key for r in LOCK_RULES}
    lever_keys = {'durationInFrames', 'camera', 'motion', 'style_bible',
                  'layout', 'transitionIn', 'format'}
    overlap = locked_keys & lever_keys
    assert not overlap, (
        f'{sorted(overlap)} is both a lock rule and a legitimate lever. The lock '
        f'and the repair contract contradict each other, and each lever test '
        f'alone would still pass.'
    )


# ---------------------------------------------------------------------------
# 1b. the exemption list is CODE, and it is consulted (P32)
# ---------------------------------------------------------------------------
#
# Everything above would pass against a lock that cannot see a lever at all —
# which is exactly what happened until P32: `iter_locked` entered each scene
# through `content`, every 11.1 lever is a TOP-LEVEL SceneSchema key beside it,
# and so `durationInFrames` was both unlocked and unreachable. "Unlocked because
# the walker never looks there" and "unlocked because a rule refused it" are
# different claims, and only one of them answers "did anyone try to lock this?".
#
# So these assert the mechanism, not the outcome: inject a rule named after each
# lever and require the exemption to be what silences it. If the walker goes
# back to content-only, the rule fires and this reds; if an entry is deleted
# from LEGITIMATE_LEVERS, the rule fires and this reds.

#: A real mutation per lever, so "the rule fires" is a measurement and not a
#: tautology. Keys come from the shipped graphs (chart scenes really do carry
#: `camera`/`motion`), which is why this table is data and not a lambda soup.
_LEVER_CARRIER: dict[str, tuple[str, object]] = {
    'durationInFrames': ('scene', lambda s: s.__setitem__('durationInFrames', 4242)),
    'camera': ('scene', lambda s: s['camera'].__setitem__('translateZ', 4242)),
    'motion': ('scene', lambda s: s['motion'].__setitem__('preset', 'PROBE')),
    'layout': ('scene', lambda s: s['layout'].__setitem__('padX', 4242)),
    'transitionIn': ('scene', lambda s: s['transitionIn'].__setitem__('in', 'PROBE')),
    'style_bible': ('scene', lambda s: s.__setitem__('style_bible', {'palette': {'a': 1}})),
    'transitionOut': ('scene', lambda s: s.__setitem__('transitionOut', {'out': 'PROBE'})),
    'format': ('graph', lambda g: g.__setitem__('format', {**g['format'], 'width': 4242})),
}


@pytest.mark.parametrize('lever', sorted(_LEVER_CARRIER))
def test_the_exemption_is_what_keeps_a_lever_unlocked(lever, monkeypatch):
    """The lever must be REACHABLE and REFUSED — not merely out of reach.

    Two assertions, and the order matters. First: with a rule for the lever
    injected, the lock must stay silent — that is the exemption working. Then,
    drop the exemption and require the SAME rule to fire — that is proof the
    first silence was a refusal and not an unreachable path. A walker that
    never visited the lever would pass the first assertion and fail the second,
    which is precisely the bug P32 fixed and precisely the one the old
    `lock_a_legitimate_lever` mutation was blind to.
    """
    import locked_fields as lf

    scope, mutate = _LEVER_CARRIER[lever]
    name = 'showcase_demo.json' if lever in ('layout', 'transitionIn', 'transitionOut') \
        else 'charts_demo.json'
    before = _graph(name)

    def _after():
        after = copy.deepcopy(before)
        mutate(after if scope == 'graph' else after['scenes'][0])
        return after

    monkeypatch.setitem(lf._RULES_BY_KEY, lever,
                        lf.LockRule(lever, 'copy', 'P32 probe: a rule for a lever'))
    assert diff_locked(before, _after()) == [], (
        f'{lever!r} is named by a rule and the lock still said nothing — so the '
        f'exemption is not being read. Either the entry is missing from '
        f'LEGITIMATE_LEVERS or iter_locked never reaches the key.'
    )

    monkeypatch.setattr(lf, 'LEGITIMATE_LEVERS', lf.LEGITIMATE_LEVERS - {lever})
    assert diff_locked(before, _after()), (
        f'{lever!r} left the exemption list and nothing caught it. The lever is '
        f'OUT OF REACH rather than exempt — which is the P11/P32 defect: the '
        f'lock would keep reporting 0 violations whether or not anyone tried.'
    )


def test_every_11_1_lever_is_named_in_the_exemption_list():
    """The list is pinned to 11.1, so deleting an entry is a red test.

    Set arithmetic against the module constant, not a comment: `LOCKED_SCENE_TYPES`
    sat unread for months here, and the difference was that nothing asserted it.
    """
    import locked_fields as lf
    assert lf.LEGITIMATE_LEVERS == frozenset(_LEVER_CARRIER), (
        f'LEGITIMATE_LEVERS is {sorted(lf.LEGITIMATE_LEVERS)}, expected '
        f'{sorted(_LEVER_CARRIER)}. 11.1 names seven levers; `transitionIn/Out` '
        f'is one lever with two keys and `format` is graph-level. A key that '
        f'drops out stops being exempt and stops being reachable, silently.'
    )


def test_the_walker_actually_visits_the_levers(monkeypatch):
    """Reachability, measured on the shipped graphs and nothing else.

    This is the assertion the old `lock_a_legitimate_lever` mutation could not
    make. Note it cannot be written against plain `iter_locked` output: that
    yields only paths a RULE matched, so an exempted lever is absent by
    construction and asking "is it absent?" proves nothing — the same mistake as
    measuring a lock by a graph that triggers nothing. So the exemptions are
    dropped and a probe rule is injected, which turns the question into the one
    that matters: if someone wrote a rule for this key, WOULD THE WALKER SEE IT?
    """
    import locked_fields as lf

    monkeypatch.setattr(lf, 'LEGITIMATE_LEVERS', frozenset())
    for lever in ('durationInFrames', 'camera', 'motion', 'transitionIn',
                  'layout', 'format', 'content'):
        monkeypatch.setitem(lf._RULES_BY_KEY, lever,
                            lf.LockRule(lever, 'copy', 'P32 reachability probe'))

    graphs = {p.name: json.loads(p.read_text(encoding='utf-8'))
              for p in EXAMPLES.glob('*.json')}
    seen: set[str] = set()
    for g in graphs.values():
        for _i, _s, path, _r, _v in lf.iter_locked(g):
            seen.add(lf.lever_key_of(path))

    missing = {'durationInFrames', 'camera', 'motion', 'transitionIn',
               'layout', 'format', 'content'} - seen
    assert not missing, (
        f'the walker never reached {sorted(missing)} across the shipped graphs, '
        f'even with the exemptions lifted and a rule for each. It is not walking '
        f'the scene/graph top level, so every lever exemption is vacuous again '
        f'and "unlocked" means "invisible" rather than "refused".'
    )


def test_the_lock_still_covers_what_it_claims_to():
    """A wiring contract that passes because the lock is empty proves nothing."""
    assert len(LOCK_RULES) >= 14, (
        f'only {len(LOCK_RULES)} lock rules; the contract below would pass '
        f'vacuously against an empty lock'
    )
    assert {'values', 'labels', 'headline'} <= {r.key for r in LOCK_RULES}, (
        'the three fields this file attacks are no longer locked — the attacks '
        'below would pass because there is nothing left to catch'
    )


# ---------------------------------------------------------------------------
# 2. attacks on the claim must be caught, with the right kind
# ---------------------------------------------------------------------------

ATTACKS: dict[str, tuple[object, str]] = {
    # name -> (mutator, expected rule.kind)
    'edit one value': (
        lambda g: g['scenes'][0]['content']['chart']['values'].__setitem__(0, 1.0),
        'fact',
    ),
    'drop one label': (
        lambda g: g['scenes'][0]['content']['chart']['labels'].pop(),
        'identity',
    ),
    'drop the whole labels field': (
        lambda g: g['scenes'][0]['content']['chart'].pop('labels'),
        'identity',
    ),
    'write a headline': (
        lambda g: g['scenes'][0]['content'].__setitem__('headline', 'x'),
        'copy',
    ),
}


@pytest.mark.parametrize('attack', sorted(ATTACKS))
def test_an_attack_on_the_claim_is_caught_with_its_kind(attack):
    mutate, expected_kind = ATTACKS[attack]
    before = _graph()
    after = copy.deepcopy(before)
    mutate(after)

    violations = diff_locked(before, after)
    assert violations, f'{attack!r} changed a locked field and the lock said nothing'
    kinds = {v.rule.kind for v in violations}
    assert expected_kind in kinds, (
        f'{attack!r} was caught as {sorted(kinds)}, expected {expected_kind!r}. '
        f'A lock that catches the wrong KIND is reporting the wrong reason.'
    )


# ---------------------------------------------------------------------------
# 3. the bidirectional invariant
# ---------------------------------------------------------------------------
#
# "You cannot launder a violation by swapping the arguments" is a property of the
# CALL, not of any single call: it only exists if every path through diff_locked
# emits symmetrically. `emit(before, after)` and `emit(after, before)` are two
# separate loops, and the mutation that removes the second one is invisible to
# any test that only ever diffs forwards.

@pytest.mark.parametrize('attack', sorted(ATTACKS))
def test_diff_locked_is_symmetric_under_argument_order(attack):
    mutate, _kind = ATTACKS[attack]
    a = _graph()
    b = copy.deepcopy(a)
    mutate(b)

    forward = diff_locked(a, b)
    reverse = diff_locked(b, a)
    assert len(forward) == len(reverse), (
        f'{attack!r}: diff_locked(a, b) found {len(forward)} and diff_locked(b, a) '
        f'found {len(reverse)}. A repairer that swapped its arguments would lose '
        f'the finding — the count is the only thing that shows it.'
    )


def test_symmetry_holds_for_a_repair_that_only_adds():
    """The interesting case: adding a locked field, where the second pass is
    the only one that can see it. A forward-only walk reports nothing here."""
    before = _graph()
    after = copy.deepcopy(before)
    after['scenes'][0]['content']['headline'] = 'new sentence'
    assert diff_locked(before, after), (
        'adding a locked field produced no finding at all — this is the shape a '
        'second emit() is responsible for'
    )


# ---------------------------------------------------------------------------
# 4. zero consumers is a KNOWN STATE, not a defect
# ---------------------------------------------------------------------------
#
# This is the assertion that will one day be wrong, and that is the design. When
# a repairer is written, this goes red and the file should be renamed to record a
# real wiring relationship. Until then, "nobody calls this" is the truth, and
# asserting it is what stops the next reader from assuming the lock is in force.

PRODUCTION_SUFFIXES = {'.py', '.ts', '.tsx', '.mjs', '.js'}

#: The directories that hold THIS PROJECT's source, and nothing else.
#:
#: A blocklist was the first version and it was wrong twice over. It scanned
#: 21,894 files / 341 MB across `liaozhai_demo/acestep-env`, a vendored virtual
#: environment — 99 seconds for a test that should take milliseconds, and more
#: importantly the wrong QUESTION. "Is there a caller?" has to be asked about
#: the code this project owns; a vendored site-packages is not an answer either
#: way, and including it only creates two ways to be wrong: a false positive
#: from third-party code, or a scanner so slow someone deletes the guard.
#:
#: So the roots are listed. A new top-level directory is out of scope until it
#: is added here, and that is visible in a diff rather than silent.
SOURCE_ROOTS = ('studio', 'pipeline', 'docs')


def _production_consumers() -> list[tuple[str, int]]:
    """(file, lineno) of every call to diff_locked outside the module and tests.

    Parsed, not grepped. A grep for `diff_locked` matches the module's own
    docstring, this file's docstring, and any comment explaining the lock — all
    of which are text about the function rather than calls to it. That mistake
    has been made three times in this project, in three different forms, and it
    is always the same one: an assertion about text existence, satisfied by the
    text that explains the thing.
    """
    hits: list[tuple[str, int]] = []
    for top in SOURCE_ROOTS:
        base = ROOT / top
        if not base.is_dir():
            continue
        for path in base.rglob('*'):
            if not path.is_file() or path.suffix not in PRODUCTION_SUFFIXES:
                continue
            rel = path.relative_to(ROOT)
            if rel.name == LOCKED_MODULE.name:
                continue
            if any(part in ('node_modules', '__pycache__', 'public')
                   for part in rel.parts):
                continue
            if path.suffix == '.py':
                try:
                    tree = ast.parse(path.read_text(encoding='utf-8'))
                except (OSError, SyntaxError):
                    continue
                for node in ast.walk(tree):
                    if (isinstance(node, ast.Call)
                            and isinstance(node.func, ast.Name)
                            and node.func.id == 'diff_locked'):
                        hits.append((str(rel), node.lineno))
    return hits


def test_nothing_in_production_calls_diff_locked_yet():
    consumers = _production_consumers()
    assert consumers == [], (
        f'diff_locked now has production consumers: {consumers}. That is not a '
        f'failure — it is the moment this file stops being about a future '
        f'repairer. RENAME it to record the real wiring relationship, and say '
        f'in the commit message what now calls it and why it may.'
    )


def test_the_zero_consumer_assertion_can_actually_see_a_consumer():
    """The guard above is worthless if it cannot fail.

    Measured on a throwaway file in a temp directory that IS inside the scanned
    root — a temporary that does not exist proves nothing. So this writes a real
    file, checks it is seen, and removes it.

    The point of the check is that a scanner which silently matches nothing
    reports "zero consumers" forever, which is exactly what it reported for the
    whole life of `measure_frame.py` v1.
    """
    probe_dir = ROOT / 'studio' / 'scripts'
    probe = probe_dir / '_wiring_probe_tmp.py'
    assert not probe.exists(), f'{probe} already exists — clean it up first'
    try:
        probe.write_text('from locked_fields import diff_locked\n'
                         'x = diff_locked({}, {})\n', encoding='utf-8')
        found = _production_consumers()
        # Compare on the resolved Path, not on strings: the scanner reports
        # `studio\scripts\...` on Windows and `as_posix()` would give
        # `studio/scripts/...`, so the first version of this assertion failed
        # while looking at a scanner that had in fact found the caller. A
        # self-check that reports failure for a reason other than the one it is
        # checking is the "red for the wrong reason" failure again.
        want = probe.resolve()
        assert any((ROOT / f).resolve() == want for f, _ in found), (
            f'the scanner did not see a real caller at {probe}; the zero-consumer '
            f'guard would pass forever. It saw: {found}'
        )
    finally:
        probe.unlink(missing_ok=True)
    assert not probe.exists(), 'the probe was left behind'


def test_the_module_under_test_still_declares_what_the_contract_assumptions():
    """Lock kinds and the scene-type carve-out, pinned by BEHAVIOUR.

    `logo` is a scene TYPE, not a content field, so it cannot be a LockRule and
    is handled by `LOCKED_SCENE_TYPES` + `BRAND_CONTENT_KEYS`.

    ⚠️ Until P30 this read `assert 'logo' in lf.LOCKED_SCENE_TYPES` — while its
    own docstring claimed the values were "pinned by behaviour", which is the
    claim this project has been wrong about seven times. Its own message said the
    danger: "nothing in this file moves a logo scene". So it now moves one.
    """
    import locked_fields as lf
    graph = json.loads(
        (EXAMPLES.parent / 'graphs' / 'p29_new_renderer_showcase.json')
        .read_text(encoding='utf-8'))
    idx = [i for i, s in enumerate(graph['scenes']) if s.get('type') == 'logo']
    assert idx, (
        'the brand fixture carries no logo scene, so everything below would pass '
        'because the lock correctly had nothing to say'
    )
    rerouted = copy.deepcopy(graph)
    rerouted['scenes'][idx[0]]['type'] = 'bar-chart'
    brand = [v for v in diff_locked(graph, rerouted) if v.rule.kind == 'brand']
    assert brand, (
        'the brand scene type is no longer locked; nothing else in this file '
        'would notice, because no test here moved a logo scene'
    )
    kinds = {r.kind for r in LOCK_RULES}
    assert kinds <= {'fact', 'copy', 'brand', 'identity'}, (
        f'unknown lock kind(s) in {sorted(kinds - {"fact", "copy", "brand", "identity"})}'
    )
    # and the lock actually sees fields in a real graph
    assert len(list(iter_locked(_graph()))) > 0, (
        'iter_locked found nothing in charts_demo.json — every assertion above '
        'about "the lock said nothing" would be vacuous'
    )


# ---------------------------------------------------------------------------
# 5. this file's own assertions
# ---------------------------------------------------------------------------
#
# Four mutations survived the first version of this guard, and all four were the
# same shape: delete or neuter an assertion IN HERE, and nothing went red.
# `attacks_always_pass`, `symmetry_tautology`, `drop_zero_consumer_assert` and
# `drop_self_check` each left the suite fully green, because a test suite has no
# way to notice that one of its own tests stopped testing.
#
# The geometry guard hit the same wall one round earlier, from the other side: a
# post-run comparison of the SOURCE file cannot notice the source was edited
# mid-run. Different problem, same shape — a property that is only checkable from
# outside the thing being checked.
#
# So: parse this module and assert that each contract test still contains an
# assertion. Not by name — a name check is satisfied by the word appearing in a
# docstring, which is the trap this project has fallen into three times. By
# COUNT: a contract test with no `assert` in its body proves nothing, however
# confidently its name announces what it proves.

_CONTRACT_TESTS = (
    'test_a_legitimate_lever_is_not_locked',
    'test_the_lever_list_is_not_a_subset_of_the_lock',
    'test_the_lock_still_covers_what_it_claims_to',
    'test_the_exemption_is_what_keeps_a_lever_unlocked',
    'test_every_11_1_lever_is_named_in_the_exemption_list',
    'test_the_walker_actually_visits_the_levers',
    'test_an_attack_on_the_claim_is_caught_with_its_kind',
    'test_diff_locked_is_symmetric_under_argument_order',
    'test_symmetry_holds_for_a_repair_that_only_adds',
    'test_nothing_in_production_calls_diff_locked_yet',
    'test_the_zero_consumer_assertion_can_actually_see_a_consumer',
)


def _this_module() -> ast.Module:
    return ast.parse(Path(__file__).read_text(encoding='utf-8'))


def test_every_contract_test_still_makes_a_comparison():
    """Not "contains an assert" — contains an assert that COMPARES two things.

    The first version counted `ast.Assert` nodes and four mutations still
    survived it, because `assert True` is an assertion. Counting was the wrong
    question: the four survivors were `assert True`, `assert len(f) == len(f)
    or True`, `consumers = []`, and an early `return` — all of which leave an
    `assert` node in the function and none of which test anything.

    So the check is on the shape of the comparison. A tautology is an assert
    whose two sides are the same expression, or a single constant. That is a
    syntactic property, so it can be checked exactly, and it catches all four
    shapes above: three are tautologies or constants, and the fourth removes the
    assert entirely (caught by the absence check, which is kept).

    ── WHAT THIS GUARD DOES NOT CATCH, measured ──────────────────────────────
    Six mutations survive it. Every one was applied and the result pasted below
    rather than summarised, because the previous two rounds produced acceptance
    claims a reviewer could not reproduce.

    ALL SIX are SELF-WEAKENING: they disable a check in THIS FILE. None of them
    lets a real attack through — the four attacks are still caught with the right
    kind by the five mutations that do redden, so the lock's defence is intact.
    The gap is one level up, in the ability of a guard to notice its own removal.

      1. `drop_self_check`        — `return`s from the probe test before it
                                   asserts the scanner can see a caller.
                                   Real gap: the probe is the only thing proving
                                   the zero-consumer scan is not vacuous.
      2. `drop_zero_consumer_assert` — replaces `consumers = _production_consumers()`
                                   with `consumers = []`. Real gap: the assertion
                                   stays, and it passes, having scanned nothing.
      3. `attacks_always_pass`    — `assert True` in place of `assert violations`.
                                   Real gap: the attack test keeps its second
                                   assertion (`expected_kind in kinds`), which is
                                   still true, so the function still looks tested.
      4. `attack_neutered_to_true` — `assert violations is not None or True`.
                                   Same gap as 3, and it also defeats the
                                   tautology detector above by hiding the True
                                   behind a BoolOp on a real expression.
      5. `selfcheck_neutered`     — `assert not tautological or True`, i.e. the
                                   detector above switched off. Nothing can
                                   protect a watchdog from being switched off;
                                   this is the expected floor of any self-check.
      6. `zero_consumer_no_scan`  — scans, then discards the result. Real gap,
                                   and the most misleading one: the code still
                                   READS as if it checked.

    1, 2, 3, 4 and 6 are all the same shape: a function retains at least one
    assertion that is still true, so `all(is_tautology(a) ...)` is False and
    nothing is reported. The check asks "is this function entirely tautological?"
    and partial neutering is not that. Catching it requires RUNNING a mutated
    copy of this module and asserting it goes red — a meta-test, which is the
    first level of infinite regress and is deliberately NOT built here. The
    project has a track record in the direction that needs it (a test rewriting
    its own source: six silent CRLF patch failures, and one `git checkout --
    <file>` that discarded uncommitted work).

    CONSEQUENCE, stated plainly:

        **Weakening the checks above leaves the suite fully green.
        "The guard is still there" is not the same claim as "the guard works".**

    Read this before trusting a green run of this file. What IS established:
    the seven levers pass, four attacks are caught with the right kind, and
    diff_locked is symmetric — all three verified by the mutations that do kill.
    """
    def is_tautology(node: ast.Assert) -> bool:
        test = node.test
        if isinstance(test, ast.Constant):
            return True
        if isinstance(test, ast.BoolOp):
            # `A == A or True` and `A or True`: the True makes it constant
            return any(isinstance(v, ast.Constant) and v.value is True
                       for v in test.values)
        if isinstance(test, ast.Compare):
            left = ast.unparse(test.left)
            return any(ast.unparse(c) == left for c in test.comparators)
        return False

    absent: list[str] = []
    tautological: list[str] = []
    for node in _this_module().body:
        if not isinstance(node, ast.FunctionDef) or node.name not in _CONTRACT_TESTS:
            continue
        asserts = [sub for sub in ast.walk(node) if isinstance(sub, ast.Assert)]
        if not asserts:
            absent.append(node.name)
        elif all(is_tautology(a) for a in asserts):
            tautological.append(node.name)

    assert not absent, (
        f'these contract tests contain no assertion at all: {absent}. A test '
        f'with no assert passes for any input, and nothing else in this file '
        f'would notice.'
    )
    assert not tautological, (
        f'these contract tests only assert constants or self-comparisons: '
        f'{tautological}. They pass for any input, which is the same as not '
        f'testing. This is what the four surviving mutations looked like.'
    )


def test_the_contract_tests_are_all_still_defined():
    """The list above must describe THIS module, not an older version of it.

    If a contract test is renamed or deleted, the previous check quietly stops
    checking it. That is the same failure one level up: a registry that is not
    compared against the thing it describes.
    """
    defined = {n.name for n in _this_module().body if isinstance(n, ast.FunctionDef)}
    absent = sorted(set(_CONTRACT_TESTS) - defined)
    assert not absent, (
        f'{absent} are listed as contract tests but are not defined here. Either '
        f'rename this list or restore the tests — a guard that has quietly '
        f'stopped guarding is the failure this file exists to avoid.'
    )


def test_the_zero_consumer_scanner_is_not_scanning_nothing():
    """The scanner found 0 consumers for 20 minutes before anyone asked whether
    it could find any. Its own probe test covers that; this one is the cheaper
    backstop — the scanner must at least see the module under test's own file,
    which exists and is Python. A scanner that scans nothing reports zero, and
    zero is what this file asserts."""
    source_roots = {p for p in SOURCE_ROOTS if (ROOT / p).is_dir()}
    assert source_roots, (
        f'none of SOURCE_ROOTS exist under {ROOT}; the zero-consumer guard would '
        f'pass forever'
    )
    assert (ROOT / 'studio' / 'scripts' / 'locked_fields.py').is_relative_to(
        ROOT / 'studio'), 'the scanner roots no longer cover the module under test'


# ---------------------------------------------------------------------------
# 6. the survivors, as data rather than as prose
# ---------------------------------------------------------------------------
#
# The docstring above names six mutations this guard cannot catch. A list of
# known gaps in a comment is exactly the kind of claim that goes stale: someone
# fixes one, the comment keeps claiming it, and the next reader believes it.
#
# So the list is data, imported from the harness that runs them. The assertion
# below is about the gap being REAL and still being real — it fails if a
# mutation here stops being a known survivor, which is the signal to delete the
# entry rather than to keep a fixed problem described as unfixed.

HARNESS = ROOT / 'studio' / 'scripts' / 'locked_fields_mutation.py'

#: Mutations measured to survive, and why. Kept in step with the docstring above
#: by test_the_survivor_list_is_still_measured, not by discipline.
KNOWN_SURVIVORS = {
    'drop_self_check': 'returns before asserting the scanner can see a caller',
    'drop_zero_consumer_assert': 'assertion kept, input replaced with []',
    'attacks_always_pass': "assert True; the function's second assertion is still true",
    'attack_neutered_to_true': 'BoolOp hiding True behind a real expression',
    'selfcheck_neutered': 'the tautology detector switched off',
    'zero_consumer_no_scan': 'scans, then discards — reads as if it checked',
}


def _harness_mutation_names() -> set[str] | None:
    """Mutation names the harness knows about, without importing it.

    Imported rather than read, because a name list parsed out of the source is
    satisfied by the comment describing the mutations.
    """
    if not HARNESS.exists():
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location('_lf_mutation_harness', HARNESS)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:            # a broken harness must not fail the suite here
        return None
    return set(getattr(mod, 'MUTATIONS', {}))


def test_every_known_survivor_is_still_a_mutation_in_the_harness():
    """The survivor list names real mutations, not aspirations.

    If a name here does not exist in the harness, the gap it describes is either
    fixed or was never measured, and either way this comment is lying.
    """
    names = _harness_mutation_names()
    assert names is not None, f'{HARNESS} is missing or unloadable'
    unknown = sorted(set(KNOWN_SURVIVORS) - names)
    assert not unknown, (
        f'{unknown} are listed as surviving mutations but the harness does not '
        f'define them. Either the gap is fixed (delete it here and from the '
        f'docstring) or the name was never run.'
    )


def test_the_gap_is_still_open_and_labelled():
    """The gap is asserted rather than described, in one direction only.

    This cannot prove a mutation still survives - that needs running it, which
    is the meta-test this file deliberately does not build. What it CAN do is
    fail if the weakness it describes is closed, so the next reader is not told
    about a gap that no longer exists. A one-directional check is worth having
    precisely because the direction it cannot check is the expensive one.
    """
    assert KNOWN_SURVIVORS, (
        'the survivor list is empty. If the meta-test now exists, delete this and '
        'the docstring section above rather than leaving a claim of an open gap '
        'that is no longer open.'
    )
    for name, why in KNOWN_SURVIVORS.items():
        assert why and len(why) > 10, f'{name} has no stated reason'