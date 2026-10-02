"""locked_fields.py must refuse the moves a repair loop would want to make (P11, task 11.2).

The ledger says "锁定项保护（核心文案/品牌 logo/数值事实）" and nothing more. A
guard written against a paraphrase of that spec would test the paraphrase, so
every rule here is asserted in BOTH directions:

  * the move is caught — a repair that shortens labels, edits a value or
    rewrites a headline is rejected;
  * the legitimate move is NOT caught — duration, camera, motion, layout and
    style_bible are exactly the levers 11.1 names, and a lock that blocked them
    would make the repair loop unable to repair anything. A guard that only ever
    says "no" passes every test in this file.

`coverage_report` gets its own test for the same reason: a rule that no shipped
graph exercises is indistinguishable from a correct one, and a lock list whose
blind spots are invisible is a lock list that gets trusted past its reach.
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

EXAMPLES = sorted((ROOT / 'pipeline' / 'examples').glob('*.json'))


def _graph(name: str) -> dict:
    return json.loads((ROOT / 'pipeline' / 'examples' / name).read_text(encoding='utf-8'))


@pytest.fixture(scope='module')
def charts():
    return _graph('charts_demo.json')


@pytest.fixture(scope='module')
def showcase():
    return _graph('showcase_demo.json')


def _scene_with(graph: dict, key: str) -> int:
    for i, s in enumerate(graph['scenes']):
        if key in (s.get('content') or {}):
            return i
    raise AssertionError(f'no scene carries content.{key}; the fixture assumption is wrong')


# ---------------------------------------------------------------------------
# 数值事实
# ---------------------------------------------------------------------------

def test_editing_a_value_is_caught(charts):
    after = copy.deepcopy(charts)
    after['scenes'][0]['content']['chart']['values'][2] = 1
    bad = lf.diff_locked(charts, after)
    assert len(bad) == 1
    assert bad[0].rule.kind == 'fact'
    assert bad[0].before == 52100000 and bad[0].after == 1
    assert 'values[2]' in bad[0].path, 'reported at the element, not the whole array'


def test_a_value_change_is_caught_in_either_direction(charts):
    """diff_locked is not order-dependent: swapping the graphs must not launder it."""
    after = copy.deepcopy(charts)
    after['scenes'][0]['content']['chart']['values'][2] = 1
    assert len(lf.diff_locked(after, charts)) == 1


def test_a_repair_may_not_shorten_labels(charts):
    """The move 11.2 exists to stop.

    Shortening labels is the only lever that can clear a chart collision, and it
    is a lie: the axis labels are the data. This is the whole task in one test.
    """
    after = copy.deepcopy(charts)
    del after['scenes'][0]['content']['chart']['labels'][3]
    bad = lf.diff_locked(charts, after)
    assert len(bad) == 1
    assert bad[0].rule.kind == 'identity'
    assert 'Signups' in json.dumps(bad[0].before)


def test_deleting_a_whole_locked_field_is_caught(charts):
    """Deletion clears a collision just as well as editing does, so it is caught too."""
    after = copy.deepcopy(charts)
    after['scenes'][0]['content']['chart'].pop('values')
    assert len(lf.diff_locked(charts, after)) == 1


def test_a_prefix_change_is_a_change_of_meaning(showcase):
    """`prefix` is locked because 'M' and '' are not the same number."""
    i = _scene_with(showcase, 'prefix')
    after = copy.deepcopy(showcase)
    after['scenes'][i]['content']['prefix'] = ''
    assert len(lf.diff_locked(showcase, after)) == 1


# ---------------------------------------------------------------------------
# 核心文案
# ---------------------------------------------------------------------------

def test_rewriting_a_headline_is_caught(showcase):
    i = _scene_with(showcase, 'headline')
    before = showcase['scenes'][i]['content']['headline']
    after = copy.deepcopy(showcase)
    after['scenes'][i]['content']['headline'] = 'Q3'
    bad = lf.diff_locked(showcase, after)
    assert len(bad) == 1
    assert bad[0].rule.kind == 'copy'
    assert bad[0].before == before and bad[0].after == 'Q3'


# ---------------------------------------------------------------------------
# The other direction: legitimate repairs must still be allowed through
# ---------------------------------------------------------------------------

def test_the_levers_11_1_names_are_not_locked(charts):
    """A guard that only says "no" would pass every other test in this file.

    11.1 names padding / scale / font / camera / stagger / duration. Those are how
    a repair is supposed to work; if any of them trips the lock the feature is
    inert, and inert is indistinguishable from working until someone tries it.
    """
    after = copy.deepcopy(charts)
    after['scenes'][0]['durationInFrames'] = 200
    after['scenes'][0]['camera']['translateZ'] = [0, 300]
    after['scenes'][0]['motion'] = {'preset': 'calm'}
    after['scenes'][0]['layout'] = {'padX': 240}
    after['scenes'][0]['style_bible'] = {'typography': {'density': 'airy'}}
    after['scenes'][0]['transitionIn'] = {'type': 'fade', 'frames': 12}
    assert lf.diff_locked(charts, after) == [], '11.1 levers are blocked by the lock'


def test_reformatting_a_value_without_changing_it_is_allowed(charts):
    """1 and 1.0 are the same number; a repair that re-encodes one is not a lie."""
    after = copy.deepcopy(charts)
    after['scenes'][0]['content']['chart']['values'][2] = float(52100000)
    assert lf.diff_locked(charts, after) == []


def test_an_identical_graph_produces_no_findings(charts):
    assert lf.diff_locked(charts, copy.deepcopy(charts)) == []


def test_a_repair_touching_another_scene_does_not_trip_the_lock(charts):
    """Guards against an over-broad comparison that reports the whole document."""
    other = next(i for i, s in enumerate(charts['scenes'])
                 if 'values' in ((s.get('content') or {}).get('chart') or {})
                 and i != 0)
    assert other is not None, 'fixture assumption: a non-first scene must carry values'
    after = copy.deepcopy(charts)
    after['scenes'][other]['content']['chart']['values'][0] = 7
    bad = lf.diff_locked(charts, after)
    assert len(bad) == 1 and bad[0].scene_index == other


# ---------------------------------------------------------------------------
# Coverage: the lock list's blind spots
# ---------------------------------------------------------------------------

def test_every_rule_is_exercised_by_the_shipped_graphs():
    """An unexercised rule is indistinguishable from a correct one."""
    graphs = {p.name: json.loads(p.read_text(encoding='utf-8')) for p in EXAMPLES}
    cov = lf.coverage_report(graphs)
    assert cov['unexercised'] == [], (
        f'lock rules no shipped graph ever hits: {cov["unexercised"]} — either the '
        'graph lost that field or the rule is wrong'
    )
    assert cov['rules'] >= 10, 'the ledger names three kinds; a list this short is not covering them'


def test_the_three_kinds_from_the_ledger_are_all_present():
    """核心文案 / 品牌 / 数值事实 — the ledger's nouns, as machine-checkable kinds."""
    kinds = {r.kind for r in lf.LOCK_RULES}
    assert {'fact', 'copy', 'identity'} <= kinds, kinds
    assert lf.LOCKED_SCENE_TYPES == {'logo'}, (
        'the ledger names 品牌 logo; it is a scene type in showcase-v1.ts:36, so '
        'locking the type is the only thing a field-rule system can check'
    )


def test_content_is_an_open_dict_so_a_type_cannot_do_this_work():
    """States why the rules are explicit rather than derived — and would catch
    the day someone types `content` and the derivation silently stops matching."""
    src = (ROOT / 'studio' / 'src' / 'schemas' / 'showcase-v1.ts').read_text(encoding='utf-8')
    line = [l for l in src.splitlines() if 'content:' in l and 'z.record' in l]
    assert line, 'content is no longer an open record — revisit the lock list'

def test_a_locked_field_added_where_none_existed_is_caught(charts):
    """The direction that only the second emit() pass covers.

    A repair that ADDS a locked key to a scene that had none — inventing a
    caption, or back-filling a value — has nothing for `iter_locked(before)` to
    compare against, so a single-direction diff sees no change at all. Mutation C
    removed the second emit() and every other test in this file stayed green,
    which is why this one exists.
    """
    after = copy.deepcopy(charts)
    scene = after['scenes'][3]
    scene.setdefault('content', {})['caption'] = 'recovered'
    bad = lf.diff_locked(charts, after)
    assert len(bad) == 1, f'a caption invented on a scene without one must be caught, got {bad}'
    assert bad[0].rule.kind == 'copy'
    assert bad[0].after == 'recovered'
