"""Locked fields: the part of a repair that is not allowed to happen (P11, task 11.2).

The ledger reads "锁定项保护（核心文案/品牌 logo/数值事实）" and that is the whole
specification. It is short enough to implement exactly rather than approximately,
which matters here because the alternative — a repair loop that quietly edits a
number to make a collision go away — produces a video that is wrong and looks
right. That failure is worse than the collision it was repairing.

Why a path list and not a type. `content` is `z.record(z.string(), z.unknown())`
in showcase-v1.ts:100, so there is no type boundary to lean on: every field in
every scene is `unknown`, including the ones that must not move. A lock therefore
has to be written down explicitly, and the cost of writing it down is that it can
be incomplete — which is why `LOCK_RULES` is exported and counted in the tests,
and why `coverage_report()` exists to print what the shipped graphs actually hit.

Three kinds, from the ledger's three nouns:

  * 数值事实 — the numbers the video asserts. `chart.values` is the sharpest case:
    it is simultaneously the data and the thing a collision repair wants to
    shorten. 11.2 exists mostly to say that does not happen.
  * 核心文案 — the sentences that carry the message.
  * 品牌 — `logo` is a scene TYPE in showcase-v1.ts:82, so the brand mark is a
    scene, not a field. It is locked as a SCENE, by a different mechanism than
    the other two (see `LOCKED_SCENE_TYPES`), because `_RULES_BY_KEY` matches a
    content key in EVERY scene and a brand lock must not apply to a scene that
    merely happens to carry a key called `name`. Two things are locked: the
    scene's `type`, so a repair cannot reroute it to a chart to make it fit, and
    its `content.name`, the wordmark, so it cannot buy the same clearance by
    renaming. Both come back as ordinary `LockedField`s.

Deliberately NOT locked, and the reason is the audit rather than taste:
`durationInFrames`, `camera`, `motion`, `layout`, `style_bible`, `format` and
`transitionIn/Out` are exactly the levers 11.1 names. Locking them would make
the repair loop unable to do anything at all. The boundary this module draws is
"the claim" versus "the staging of the claim" — you may move how a number is
presented, never what it says.

Usage:
    from locked_fields import LockedField, diff_locked, coverage_report
    violations = diff_locked(before, after)
    if violations:
        raise ...
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

__all__ = [
    'LockRule', 'LOCK_RULES', 'LockedField', 'iter_locked', 'iter_scene_locked',
    'LOCKED_SCENE_TYPES', 'BRAND_CONTENT_KEYS',
    'diff_locked', 'locked_paths', 'coverage_report', 'main',
]


@dataclass(frozen=True)
class LockRule:
    """One lockable field, named by where it sits under a scene's `content`.

    `key` is a plain key, not a dotted path, because everything measured in this
    project lives one level under `content` (see coverage_report). A rule with a
    dotted `key` is accepted and walked, so a nested chart option can be locked by
    adding a rule rather than by changing the walker.
    """
    key: str
    kind: str          # 'fact' | 'copy' | 'brand' | 'identity'
    why: str


# --------------------------------------------------------------------------
# The lock list. Read this as the answer to "what may a repair never touch?"
# --------------------------------------------------------------------------

LOCK_RULES: tuple[LockRule, ...] = (
    # --- 数值事实 ---------------------------------------------------------
    LockRule('value', 'fact', 'the headline number is the claim'),
    LockRule('values', 'fact', 'the plotted series is the claim'),
    LockRule('baseline', 'fact', 'a comparison point is a claim about the past'),
    LockRule('delta', 'fact', 'a delta is a derived claim; recomputing it is the producer\'s job'),
    LockRule('prefix', 'fact', 'a currency or magnitude prefix changes what the number means'),
    LockRule('suffix', 'fact', 'a unit suffix changes what the number means'),
    LockRule('unit', 'fact', 'declaring the unit is stating the fact'),
    LockRule('seed', 'fact', 'a seed determines every generated number behind it'),
    LockRule('columnSeed', 'fact', 'same, for the column heights'),

    # --- 核心文案 ---------------------------------------------------------
    LockRule('headline', 'copy', 'the sentence the scene exists to say'),
    LockRule('caption', 'copy', 'the sentence that qualifies the number above it'),
    LockRule('month', 'copy', 'a date label is a fact about time'),

    # --- 品牌 -------------------------------------------------------------
    # Nothing in this tuple locks the brand, and that is deliberate: `logo` is a
    # scene TYPE, so the key `name` under its `content` is indistinguishable here
    # from any other scene's `content.name` — `LOCK_RULES` matches a key in every
    # scene. The brand lock is `LOCKED_SCENE_TYPES` + `BRAND_CONTENT_KEYS`, below.
    LockRule('highlight', 'copy', 'the one element the scene points at'),

    # --- 身份 -------------------------------------------------------------
    LockRule('labels', 'identity', 'axis labels are the data, not decoration'),
)

_RULE_BY_KEY: dict[str, LockRule] = {r.key: r.key for r in LOCK_RULES}
_RULES_BY_KEY: dict[str, LockRule] = {r.key: r for r in LOCK_RULES}

# --------------------------------------------------------------------------
# The brand lock. A scene TYPE, plus the content keys that are the brand ON a
# scene of that type. Read by `diff_locked` via `iter_scene_locked` — P11 wrote
# this constant and three tests read it, and no production code did, so until
# P30 the third noun in the ledger had no rule behind it and `by_kind['brand']`
# was `[]` by construction rather than by measurement.
# --------------------------------------------------------------------------

#: Scene types that carry brand meaning and must survive a repair: they may not
#: be rerouted to another type, and see `BRAND_CONTENT_KEYS` for what they carry.
#:
#: `outro` joined `logo` in P31 by ruling, not by measurement: Brand.tsx:156-157
#: reads the same `c.name` and `c.tagline` as `Logo` (:122-123) and renders them
#: through the same `Lockup`, so the outro displays the same wordmark. Before it,
#: a repair that edited ONLY the outro's wordmark reported zero violations.
LOCKED_SCENE_TYPES: frozenset[str] = frozenset({'logo', 'outro'})

#: The `content` keys that ARE the brand, on a scene whose `type` is in
#: LOCKED_SCENE_TYPES. `name` is the wordmark — Brand.tsx defines a lockup as
#: "a MARK (procedural, derived from tokens), a WORDMARK (the brand line from
#: content), optionally a TAGLINE". The mark is procedural, so `content.name` is
#: the only part of the lockup the graph owns and a repair could edit.
#:
#: `tagline` joined it in P31 by ruling, over one measured asymmetry: Brand.tsx:93
#: renders `{name}` unconditionally while :95 gates the tagline behind a ternary,
#: so a brand scene with NO tagline is a legal authored state. That asymmetry
#: decides what the LOCK may do, not what a graph may contain — see the note
#: below, which argues the direction explicitly rather than leaving it implied.
BRAND_CONTENT_KEYS: tuple[str, ...] = ('name', 'tagline')

_SCENE_TYPE_RULE = LockRule(
    'type', 'brand',
    'rerouting a brand scene to a chart is the move this lock exists to stop')
_BRAND_RULES: dict[str, LockRule] = {
    k: LockRule(k, 'brand',
                'the wordmark is the claim; shortening or substituting it to '
                'make a collision go away is the brand version of dropping a '
                'chart label')
    for k in BRAND_CONTENT_KEYS
}

# ── THE TWO RULINGS A READER HAD TO MAKE — both made, P31 ──────────────────
#
# P30 left these open and wrote them down rather than guessing, because a guess
# reads as settled the moment it becomes code. The user has now ruled on both.
# The record is kept rather than deleted: the evidence behind each ruling is
# the thing a later reader needs and cannot reconstruct from the constant alone.

# 1. Is `outro` a brand scene? — RULED: YES (P31), so it is in
#    LOCKED_SCENE_TYPES. MEASURED: Brand.tsx:156-157 reads `c.name` and
#    `c.tagline` — the identical two keys `Logo` reads at :122-123 — and renders
#    them through the same `Lockup`, adding only `cta`/`sub`. The outro displays
#    the same wordmark. `pipeline/graphs/p29_new_renderer_showcase.json` agrees:
#    `p29_outro` carries the same `content.name` as `p29_logo`. Before this
#    ruling, "edit the outro's wordmark" was the one brand move that reported
#    ZERO violations.
#
# 2. Should `content.tagline` be locked? — RULED: YES (P31), so it is in
#    BRAND_CONTENT_KEYS, and this one carried a real edge case:
#
#      Brand.tsx:93  renders `{name}` unconditionally.
#      Brand.tsx:95  renders `{tagline ? (...) : null}` — CONDITIONALLY.
#
#    So a brand scene carrying no tagline is a legal authored state, and
#    `iter_scene_locked` is right to yield nothing for a key that is absent
#    (`if key in content`). That is the whole of the asymmetry, and it decides
#    what the LOCK may do — not what a graph may contain. A graph may still be
#    authored with no tagline; once one is authored, a repair may not move it,
#    and by the same reasoning as `name` a repair may not DELETE one or
#    INVENT one. The direction is therefore SYMMETRIC, exactly as for `name`,
#    whose absence renders an empty `<div>` and is nonetheless locked.
#
#    The alternative reading — treat "invent a tagline" as legal because the
#    renderer copes with absence — was rejected on this ground: a lock governs
#    the REPAIR LOOP, not the renderer's ability to cope. It would also need a
#    per-key exception inside a flat key list, which is precisely the invisible
#    special case this file keeps warning against.
#
# Both rulings live in LOCKED_SCENE_TYPES / BRAND_CONTENT_KEYS and NOT in
# LOCK_RULES, which matches a content key in EVERY scene. `content` is
# `z.record(z.string(), z.unknown())`, so `name` or `tagline` there would lock a
# future non-brand scene's byline or product name.


@dataclass(frozen=True)
class LockedField:
    """A locked value found at a concrete location in a concrete graph."""
    scene_index: int
    scene_id: str
    path: str          # 'scenes[3].content.chart.values'
    rule: LockRule
    before: Any
    after: Any

    def __str__(self) -> str:
        return (f'  {self.rule.kind:8} {self.path}\n'
                f'           before={self.before!r}\n'
                f'           after ={self.after!r}\n'
                f'           why: {self.rule.why}')


def _walk(node: Any, prefix: str) -> Iterator[tuple[str, Any]]:
    """Yield (dotted path, value) for every nested dict/list under `node`."""
    if isinstance(node, dict):
        for k, v in node.items():
            p = f'{prefix}.{k}'
            yield p, v
            yield from _walk(v, p)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            p = f'{prefix}[{i}]'
            yield p, v
            yield from _walk(v, p)


def iter_locked(graph: dict) -> Iterator[tuple[int, str, str, LockRule, Any]]:
    """Yield (scene_index, scene_id, path, rule, value) for every locked field.

    Walks the whole content subtree rather than only the top level, so a locked
    key nested inside `chart` is found without the rule knowing where it sits.
    """
    scenes = graph.get('scenes') or []
    for i, scene in enumerate(scenes):
        sid = str(scene.get('id', f'#{i}'))
        content = scene.get('content')
        if not isinstance(content, dict):
            continue
        for path, value in _walk(content, f'scenes[{i}].content'):
            leaf = path.rsplit('.', 1)[-1]
            rule = _RULES_BY_KEY.get(leaf)
            if rule is not None:
                yield i, sid, path, rule, value


def iter_scene_locked(graph: dict) -> Iterator[tuple[int, str, str, LockRule, Any]]:
    """Yield the same 5-tuple `iter_locked` yields, for SCENE-level locks.

    Two things are locked per brand scene: its `type` (so it cannot be rerouted)
    and each key in BRAND_CONTENT_KEYS (so it cannot be renamed). Same tuple
    shape as `iter_locked` on purpose — `diff_locked` runs both passes through
    one `emit()`, so there is one place where a lock becomes a `LockedField`,
    and no second return path for a caller to forget to check. The P21 lesson
    was two call sites holding one constant and only one of them reading it.
    """
    scenes = graph.get('scenes') or []
    for i, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        stype = scene.get('type')
        if stype not in LOCKED_SCENE_TYPES:
            continue
        sid = str(scene.get('id', f'#{i}'))
        yield i, sid, f'scenes[{i}].type', _SCENE_TYPE_RULE, stype
        content = scene.get('content')
        if not isinstance(content, dict):
            continue
        for key, rule in _BRAND_RULES.items():
            if key in content:
                yield i, sid, f'scenes[{i}].content.{key}', rule, content[key]


def locked_paths(graph: dict) -> dict[str, Any]:
    """path -> value, for logging or for a report."""
    return {path: value for _, _, path, _, value in iter_locked(graph)}


def _diff_values(before: Any, after: Any, path: str) -> list[tuple[str, Any, Any]]:
    """Leaves that differ, as (path, before, after).

    A list is compared element-wise so a repair that drops one label is reported
    at the label rather than as the whole array changing. Numeric equality is
    exact: 1 and 1.0 are the same number and compare equal in Python, which is
    the right call for a lock.
    """
    if isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            return [(path, before, after)]
        out: list[tuple[str, Any, Any]] = []
        for i, (b, a) in enumerate(zip(before, after)):
            out += _diff_values(b, a, f'{path}[{i}]')
        return out
    if isinstance(before, dict) and isinstance(after, dict):
        out = []
        for k in set(before) | set(after):
            if k not in before or k not in after:
                return [(f'{path}.{k}', before.get(k), after.get(k))]
            out += _diff_values(before[k], after[k], f'{path}.{k}')
        return out
    if before != after:
        return [(path, before, after)]
    return []


def diff_locked(before: dict, after: dict) -> list[LockedField]:
    """Every locked field the proposed repair would change.

    Union of both graphs' locked paths, so a repair that DELETES a locked field
    is caught as well as one that edits it — deletion is the move most likely to
    make a collision disappear, and it is exactly as much a lie as editing.

    Two passes run through ONE `emit()`: `iter_locked` for content fields, and
    `iter_scene_locked` for the brand scene-type lock. They keep separate `seen`
    sets on purpose — see the note in `emit`.
    """
    out: list[LockedField] = []

    def emit(scenes: dict, other: dict, primary: bool,
             walk: Any, seen: set[tuple[int, str, str]]) -> None:
        for idx, sid, path, rule, value in walk(scenes):
            anchor = _anchor(idx, path, rule)
            if anchor in seen:
                continue
            counterpart = _counterpart_path(other, idx, rule, path)
            other_value = _lookup(other, counterpart) if counterpart else None
            leaves = _diff_values(value, other_value, counterpart or path)
            if leaves:
                seen.add(anchor)
                for leaf_path, b, a in leaves:
                    # `primary` says which graph we are walking, not which side
                    # of the diff won. Walking `after` on the second pass finds
                    # fields the repair ADDED, and those still read before->after
                    # with respect to the caller's arguments.
                    lo, hi = (b, a) if primary else (a, b)
                    out.append(LockedField(
                        scene_index=idx, scene_id=sid,
                        path=leaf_path if primary else counterpart or path,
                        rule=rule, before=lo, after=hi))

    field_seen: set[tuple[int, str, str]] = set()
    emit(before, after, True, iter_locked, field_seen)
    emit(after, before, False, iter_locked, field_seen)
    scene_seen: set[tuple[int, str, str]] = set()
    emit(before, after, True, iter_scene_locked, scene_seen)
    emit(after, before, False, iter_scene_locked, scene_seen)
    return out


def _anchor(idx: int, path: str, rule: LockRule) -> tuple[int, str, str]:
    """Identity for "have I already reported this?", per pass.

    Content paths anchor on the leaf key, exactly as before P30. Scene-level
    paths anchor on the WHOLE path, which is what keeps the two namespaces from
    colliding: `content.chart.type` and a scene's own `type` are different
    claims about one scene, and if they shared an anchor the second one to be
    walked would be silently dropped. A lock that loses a finding because of an
    internal cache is the same failure as a lock that was never written.
    """
    if path.startswith(f'scenes[{idx}].content'):
        return (idx, rule.key, path.rsplit('.', 1)[-1])
    return (idx, rule.key, path)


def _counterpart_path(other: dict, idx: int, rule: LockRule, path: str) -> str | None:
    """The same logical field in the other graph, tolerating list-length shifts."""
    scenes = other.get('scenes') or []
    if idx >= len(scenes):
        return None
    marker = f'scenes[{idx}].content'
    if not path.startswith(marker):
        # A scene-level path (`scenes[3].type`) is already absolute — there is no
        # content subtree to rebase. Returning it unchanged is what lets a
        # DELETED brand scene report: `other` is shorter, this returns None, and
        # `_diff_values('logo', None, ...)` records the loss.
        return path
    tail = path.split(marker, 1)[-1]
    return f'{marker}{tail}'


def _lookup(graph: dict, path: str) -> Any:
    node: Any = graph
    for part in path.replace('[', '.[').split('.'):
        if not part:
            continue
        if part.startswith('['):
            i = int(part[1:-1])
            if not isinstance(node, list) or i >= len(node):
                return None
            node = node[i]
        else:
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
    return node


def coverage_report(graphs: dict[str, dict]) -> dict[str, Any]:
    """Which rules the shipped graphs actually exercise.

    A lock list is only as good as its blind spots, and an unexercised rule is
    indistinguishable from a correct one until something tries to move it.

    `unexercised` still means "a `LOCK_RULES` key that no graph hits" and nothing
    else — it is an asserted contract (`test_every_rule_is_exercised_by_the_
    shipped_graphs`) and the ledger records it as zero, so widening it would
    silently redefine a number that is already cited elsewhere. The brand lock
    is not in `LOCK_RULES` and would therefore be INVISIBLE here, which is the
    one failure this function exists to prevent — so it gets its own section,
    `scene_locks`, with the same exercised/unexercised vocabulary.
    """
    used: dict[str, list[str]] = {}
    keys_used: dict[str, list[str]] = {}
    types_hit: set[str] = set()
    for name, g in graphs.items():
        for _, _, path, rule, _ in iter_locked(g):
            used.setdefault(rule.key, []).append(f'{name}:{path}')
        for _idx, _sid, path, rule, value in iter_scene_locked(g):
            if rule is _SCENE_TYPE_RULE:
                # A scene TYPE is reported by its own NAME ('logo') — that is
                # what a reader checks against LOCKED_SCENE_TYPES. Its rule key
                # is 'type', and counting the two in one namespace made every
                # graph report the logo scene as unexercised.
                if isinstance(value, str):
                    types_hit.add(value)
            else:
                keys_used.setdefault(rule.key, []).append(f'{name}:{path}')
    return {
        'rules': len(LOCK_RULES),
        'exercised': len(used),
        'unexercised': sorted({r.key for r in LOCK_RULES} - set(used)),
        'hit_counts': {k: len(v) for k, v in sorted(used.items())},
        # 'brand' was a reserved kind from P11 with zero rules in it — the
        # reason the ledger could only ever report "fact 9 / copy 4 / identity 1".
        # No fourth kind was needed; the slot was already built.
        'by_kind': {
            k: (sorted([_SCENE_TYPE_RULE.key, *_BRAND_RULES]) if k == 'brand'
                else sorted(r.key for r in LOCK_RULES if r.kind == k))
            for k in ('fact', 'copy', 'brand', 'identity')
        },
        'scene_locks': {
            'locked_scene_types': sorted(LOCKED_SCENE_TYPES),
            'locked_content_keys': sorted(BRAND_CONTENT_KEYS),
            'exercised_scene_types': sorted(types_hit),
            'exercised_content_keys': sorted(keys_used),
            'unexercised': sorted(
                (set(LOCKED_SCENE_TYPES) - types_hit)
                | (set(BRAND_CONTENT_KEYS) - set(keys_used))),
            'hit_counts': {k: len(v) for k, v in sorted(keys_used.items())},
        },
    }


def main(argv: list[str] | None = None) -> int:
    """`diff_locked before.json after.json` — exit 1 if a locked field moved."""
    import argparse
    import sys

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('before', type=Path)
    ap.add_argument('after', type=Path)
    ap.add_argument('--coverage', type=Path, help='also report lock coverage over a graph')
    args = ap.parse_args(argv)

    before = json.loads(args.before.read_text(encoding='utf-8'))
    after = json.loads(args.after.read_text(encoding='utf-8'))

    if args.coverage and args.coverage.exists():
        cov = coverage_report({args.coverage.name: json.loads(
            args.coverage.read_text(encoding='utf-8'))})
        print(f'lock coverage: {cov["exercised"]}/{cov["rules"]} rules exercised')
        if cov['unexercised']:
            print(f'  never exercised by this graph: {cov["unexercised"]}')

    bad = diff_locked(before, after)
    for f in bad:
        print(f)
    if bad:
        print(f'\n{len(bad)} locked field(s) would change — a repair may not do this',
              file=sys.stderr)
        return 1
    print('no locked field changed')
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())