"""P26 — every `SceneType` is either RENDERED or a recorded DECISION not to.

THE DEFECT THIS GUARDS.

`SceneType` (`showcase-v1.ts`) declares 22 scene types; `SCENE_RENDERERS`
(`FinanceShowcaseWide.tsx`) registered 13; the other 9 fell through to
`MissingScene`, which renders the type's own name and the words "not implemented
in P4" for the whole scene. The ledger's line 3.2 read "20 种 scene 类型注册" and
was struck through as done — "registered" was mistaken for "renderable". P21's
`graph_scene_renderable` reports a GRAPH that uses such a type; it does not say
anything about the SCHEMA's own declaration being ahead of the renderer. That is
the gap this file closes.

WHAT IT ASSERTS.

    every value of `SceneType` is a key of `SCENE_RENDERERS`
                    OR a key of `UNRENDERED_SCENE_TYPES` (with a reason)
                    and no key is in both.

`UNRENDERED_SCENE_TYPES` is a decision table exported by the template: the types
deliberately left to `MissingScene`, each with a reason. After P26 it holds
exactly `{video, data-plane-3d}` — the two `GENERATIVE_SCENE_TYPES` — and the
second assertion below pins that the set of unrendered types is a SUBSET of the
generative set, so a programmatic type cannot be left unrendered by accident:
leaving one out requires it to be routed to another engine AND named here.

WHY THE CRITERION IS A SET DIFFERENCE AND NOT A SUBSTRING (the 4.9 lesson).

This project has been fooled by text-presence assertions seven times. The most
instructive is 4.9's first guard, whose criterion was "the number 520 exists
somewhere in the repo" — a mutation that deleted the real `windowWidth: 520`
survived it, because 520 also appeared in an unrelated fixture. Its fix was to
make the criterion an ATTRIBUTION: the number must be the value of the field it
is cited for, in the file that owns it. Same idea here. The question is not "does
the string 'quote' appear in the template" — it appears in a comment, in the
ledger, in this docstring. The question is "is `quote` a KEY of the map the
renderer actually dispatches on", so both maps are parsed to key SETS and
compared as sets. A key deleted from `SCENE_RENDERERS` that is not recorded in
`UNRENDERED_SCENE_TYPES` is then a type in neither set, which is red.

WHY THE ASSERTIONS READ THE REAL FILES (and the self-tests do not).

Every capability claim here is derived from the two real source files, comment
stripped — the same read `visual_qa.py`'s `declared_scene_types` /
`rendered_scene_types` do, and the same reason: the suite must stay runnable with
nothing but pytest, so a node subprocess is not an option. The parse is held to
the files by `test_the_maps_are_the_real_ones`, which asserts the parses are
non-empty and their sizes are consistent — a parser that silently matched nothing
would otherwise report every type as a gap or none, and both are wrong.

The DISCRIMINATION tests (`test_the_partition_check_can_say_no`) are fed
SYNTHETIC source text, because the whole point is that the real files currently
pass: a guard that has only ever seen a healthy input has not been shown to be
able to fail. A mutation that makes the checker return "no gaps" unconditionally
has to go red HERE, on an input that clearly has a gap.

WHAT THIS FILE DOES NOT DO.

It does not assert that a rendered type draws WELL — that is a render's job, and
docs/P26_MISSING_RENDERERS.md records the stills. It does not duplicate
`graph_scene_renderable` (P21), which judges a GRAPH; this judges the SCHEMA
against the RENDERER. And it does not assert the reason STRINGS' wording, only
that each unrendered type carries one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase'
TEMPLATE_TSX = TEMPLATE / 'FinanceShowcaseWide.tsx'
SCHEMA_TS = ROOT / 'studio' / 'src' / 'schemas' / 'showcase-v1.ts'


# ── comment stripping (a comment is not a key) ──────────────────────────────

def _strip_comments(text: str) -> str:
    """Drop `//` and `/* */` comments, preserving line count.

    Load-bearing, and this project has the scar: `render.mjs:141` names
    `qa_final.py` inside a comment, and a sweep that could not tell a comment
    from a call site once reported it as an H3 reference. Here the risk is the
    opposite direction — the template's prose NAMES several of these types
    ("a graph asking for a bar chart got a frame that said …"), so a matcher that
    read comments would find keys the map does not have.
    """
    out = re.sub(r'/\*[\s\S]*?\*/', lambda m: '\n' * m.group(0).count('\n'), text)
    return re.sub(r'//[^\n]*', '', out)


# ── the three parses, all off real source ───────────────────────────────────

def declared_scene_types(text: str | None = None) -> set[str]:
    """Every value `SceneType` declares, from the zod enum."""
    src = text if text is not None else SCHEMA_TS.read_text(encoding='utf-8')
    m = re.search(r'export const SceneType\s*=\s*z\.enum\(\[(.*?)\]\)', src, re.S)
    if not m:
        raise ValueError('SceneType enum not found in showcase-v1.ts; teach this '
                         'parser the new shape rather than reading zero types')
    body = _strip_comments(m.group(1))
    return {x.strip().strip('\'"') for x in body.split(',') if x.strip()}


def _map_keys(text: str, const_name: str) -> set[str]:
    """Keys of a `const NAME ... = { ... };` object literal at column 0.

    Anchored to the declaration and closed on the `};` at the start of a line, so
    it cannot run into the next object. A line with no `:` after comment-stripping
    (blank, or a stray brace) is skipped.
    """
    m = re.search(
        rf'(?:export\s+)?const {re.escape(const_name)}\b[^=]*=\s*\{{(.*?)\n\}};',
        _strip_comments(text), re.S)
    if not m:
        raise ValueError(
            f'{const_name} not found in FinanceShowcaseWide.tsx; the guard has to '
            'be taught the new shape — returning an empty set here would mark '
            'every type a gap (or none), and both are wrong.')
    keys: set[str] = set()
    for line in m.group(1).split('\n'):
        line = line.strip().rstrip(',')
        if not line or ':' not in line:
            continue
        keys.add(line.split(':', 1)[0].strip().strip('\'"'))
    return keys


def rendered_scene_types(text: str | None = None) -> set[str]:
    src = text if text is not None else TEMPLATE_TSX.read_text(encoding='utf-8')
    return _map_keys(src, 'SCENE_RENDERERS')


def unrendered_scene_types(text: str | None = None) -> set[str]:
    src = text if text is not None else TEMPLATE_TSX.read_text(encoding='utf-8')
    return _map_keys(src, 'UNRENDERED_SCENE_TYPES')


def generative_scene_types(text: str | None = None) -> set[str]:
    """The `GENERATIVE_SCENE_TYPES` set from the schema, read as text."""
    src = text if text is not None else SCHEMA_TS.read_text(encoding='utf-8')
    m = re.search(r'GENERATIVE_SCENE_TYPES\s*=\s*new Set<.*?>\(\[(.*?)\]\)', src, re.S)
    if not m:
        # fall back to the Python mirror's spelling if the zod one is reshaped
        raise ValueError('GENERATIVE_SCENE_TYPES not found in showcase-v1.ts')
    return {x.strip().strip('\'"') for x in _strip_comments(m.group(1)).split(',') if x.strip()}


def partition_gaps(declared: set[str], rendered: set[str],
                   unrendered: set[str]) -> dict[str, list[str]]:
    """The partition, as a pure function of three sets.

    Returns the four ways it can be wrong, each as a sorted list, so a caller can
    assert on the exact failure and a mutation can be aimed at one of them:

      * `uncovered`  — declared, but in NEITHER map (no renderer, not recorded)
      * `both`       — in BOTH maps (contradiction: rendered AND declared missing)
      * `phantom_renderers` / `phantom_unrendered` — keys not declared at all
    """
    return {
        'uncovered': sorted(declared - rendered - unrendered),
        'both': sorted(rendered & unrendered),
        'phantom_renderers': sorted(rendered - declared),
        'phantom_unrendered': sorted(unrendered - declared),
    }


# ── the guard ───────────────────────────────────────────────────────────────

def test_every_scene_type_is_rendered_or_recorded_as_unrendered():
    """THE GUARD. The schema and the renderer must agree, type by type.

    A type in `SceneType` that is in neither map renders the MissingScene
    placeholder for its whole duration — the P26 defect. A type in both maps is a
    contradiction.
    """
    gaps = partition_gaps(declared_scene_types(), rendered_scene_types(),
                          unrendered_scene_types())
    assert not any(gaps.values()), (
        'the schema and the renderer disagree about which scene types can be '
        f'drawn:\n  uncovered (no renderer, not recorded): {gaps["uncovered"]}\n'
        f'  in both maps: {gaps["both"]}\n'
        f'  renderer keys not in SceneType: {gaps["phantom_renderers"]}\n'
        f'  unrendered keys not in SceneType: {gaps["phantom_unrendered"]}\n'
        'A type with a renderer that is DELETED from SCENE_RENDERERS but not '
        'recorded in UNRENDERED_SCENE_TYPES lands in `uncovered` — that is the '
        'regression this catches.'
    )


def test_the_maps_are_the_real_ones():
    """The parse is held to the files, so a broke parser cannot report a pass.

    A pattern that matched nothing would make `rendered` and `unrendered` empty,
    and then `uncovered` would be ALL of `SceneType` — red, but for the wrong
    reason and naming the wrong cause. A pattern that matched the whole file
    would make both huge and `phantom_*` huge — also red, also for the wrong
    reason. This asserts the shapes are the ones the docstring claims, so a red
    above means what it says.
    """
    declared = declared_scene_types()
    rendered = rendered_scene_types()
    unrendered = unrendered_scene_types()
    generative = generative_scene_types()

    assert len(declared) == 22, f'SceneType parsed to {len(declared)} types: {sorted(declared)}'
    assert 'kpi-hero' in declared and 'video' in declared, declared
    assert len(rendered) >= 20, f'SCENE_RENDERERS parsed to {len(rendered)}: {sorted(rendered)}'
    assert 'kpi-hero' in rendered and 'bar-chart' in rendered, rendered
    # The map's VALUE is a component name; the parse must have taken the key.
    assert not any(v.endswith('.tsx') for v in rendered), rendered
    assert unrendered == {'video', 'data-plane-3d'}, (
        f'UNRENDERED_SCENE_TYPES is {sorted(unrendered)}. This set is a DECISION, '
        'not an accident (see its comment in FinanceShowcaseWide.tsx); changing '
        'it changes what "the film cannot draw this" means, so re-measure first.')
    assert generative == {'video', 'data-plane-3d'}, generative


def test_the_unrendered_set_is_explained_by_the_generative_routing():
    """The ATTRIBUTION. `unrendered` must be a subset of what needs another engine.

    The whole reason a type may be left to `MissingScene` is that it is routed to
    something other than the Remotion motion engine (`GENERATIVE_SCENE_TYPES`) and
    that engine is not here. If a PROGRAMMATIC type were left unrendered, this
    goes red — which is the shape of the mistake P26 exists to prevent: leaving a
    drawable type out for lack of time rather than lack of capability.
    """
    unrendered = unrendered_scene_types()
    generative = generative_scene_types()
    assert unrendered <= generative, (
        f'{sorted(unrendered - generative)} are declared unrendered but are NOT '
        'generative. A programmatic scene type must have a renderer; only a type '
        'that needs another engine (and has none here) may stay a placeholder.')


def test_every_unrendered_type_carries_a_reason():
    """A recorded decision needs its reason, or it is a TODO wearing a table.

    Read from the object's VALUES: each unrendered key must map to a non-empty
    string. An empty reason is how "deliberately not built" decays into "nobody
    got to it".
    """
    src = _strip_comments(TEMPLATE_TSX.read_text(encoding='utf-8'))
    m = re.search(r'(?:export\s+)?const UNRENDERED_SCENE_TYPES\b[^=]*=\s*\{(.*?)\n\};', src, re.S)
    assert m, 'UNRENDERED_SCENE_TYPES not found'
    reasons: dict[str, str] = {}
    for line in m.group(1).split('\n'):
        line = line.strip().rstrip(',')
        if not line or ':' not in line:
            continue
        key, val = line.split(':', 1)
        reasons[key.strip().strip("'\"")] = val.strip().strip("'\"")
    assert set(reasons) == unrendered_scene_types(), (
        f'the reason table and the key parse disagree: {sorted(reasons)}')
    empty = sorted(k for k, v in reasons.items() if len(v) < 12)
    assert not empty, f'unrendered types with no real reason: {empty}'


# ── discrimination: the check MUST be able to say no ────────────────────────

def test_the_partition_check_can_say_no():
    """Kills the always-passes implementation, on inputs that clearly have a gap.

    The real files currently pass the guard, so a guard that "has never failed"
    proves nothing about whether it CAN. These three synthetic cases each break
    the partition in a different way and each must be reported:

      * a declared type in NEITHER map        -> uncovered
      * a key in BOTH maps                    -> both
      * a map key that the schema does not declare -> phantom
    """
    declared = {'a', 'b'}
    # a is unrendered-and-recorded: the healthy shape
    assert not any(partition_gaps(declared, {'b'}, {'a'}).values())
    # a is in neither -> uncovered
    assert partition_gaps(declared, {'b'}, set())['uncovered'] == ['a']
    # a is in both -> both
    assert partition_gaps(declared, {'a', 'b'}, {'a'})['both'] == ['a']
    # renderer names a type the schema never declared -> phantom
    assert partition_gaps(declared, {'a', 'b', 'z'}, set())['phantom_renderers'] == ['z']
    # ...and the parsed maps from the real files are the only reason the guard is
    # currently green, so assert they parse to something.
    assert rendered_scene_types() and unrendered_scene_types()


def test_a_renderer_key_deleted_from_the_map_would_be_uncovered():
    """Run the guard's own parse over a MUTATED copy of the real template.

    This is the end-to-end version of the case above, on the actual file text:
    delete one rendered key from `SCENE_RENDERERS` (comment-stripped, so it is a
    real deletion) and the partition must report that type as uncovered. If the
    parse were fuzzy — matching the type name in a comment — the deletion would
    not register and this would pass, which is the 4.9 failure recreated.
    """
    text = TEMPLATE_TSX.read_text(encoding='utf-8')
    before = rendered_scene_types(text)
    assert 'quote' in before, 'fixture assumption: quote must be a rendered key'

    # remove exactly the `quote: Quote,` entry from the map body
    mutated = re.sub(r'\n\s*quote:\s*Quote,', '', text, count=1)
    after = rendered_scene_types(mutated)
    assert after == before - {'quote'}, (
        f'deleting the quote entry from SCENE_RENDERERS changed the parsed keys '
        f'by {sorted(before ^ after)}, not by exactly {{quote}}. The parse is not '
        'tracking the map body.')
    gaps = partition_gaps(declared_scene_types(), after, unrendered_scene_types(mutated))
    assert gaps['uncovered'] == ['quote'], (
        f'a rendered key removed without a record must fall in `uncovered`; got '
        f'{gaps}')


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
