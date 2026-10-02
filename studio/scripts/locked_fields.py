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
  * 品牌 — `logo` is a scene TYPE in showcase-v1.ts:36, so the brand mark is a
    scene, not a field. Locking the type is what stops a repair from rerouting
    it to a chart to make it fit.

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
    'LockRule', 'LOCK_RULES', 'LockedField', 'iter_locked',
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
    # `logo` is a scene type; locking it here is a no-op on content and the rule
    # is kept so the ledger's third noun has a machine-checkable counterpart.
    LockRule('highlight', 'copy', 'the one element the scene points at'),

    # --- 身份 -------------------------------------------------------------
    LockRule('labels', 'identity', 'axis labels are the data, not decoration'),
)

_RULE_BY_KEY: dict[str, LockRule] = {r.key: r.key for r in LOCK_RULES}
_RULES_BY_KEY: dict[str, LockRule] = {r.key: r for r in LOCK_RULES}

# Scene types that carry brand meaning and must survive a repair.
LOCKED_SCENE_TYPES: frozenset[str] = frozenset({'logo'})


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
    """
    b_by_path = {p: v for _, _, p, _, v in iter_locked(before)}
    a_by_path = {p: v for _, _, p, _, v in iter_locked(after)}

    # A path can change shape when its parent list changes length, so anchor on
    # (scene_index, leaf-rule) rather than on the path string alone.
    out: list[LockedField] = []
    seen: set[tuple[int, str, str]] = set()

    def emit(scenes: dict, other: dict, primary: bool) -> None:
        for idx, sid, path, rule, value in iter_locked(scenes):
            anchor = (idx, rule.key, path.rsplit('.', 1)[-1])
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

    emit(before, after, primary=True)
    emit(after, before, primary=False)
    return out


def _counterpart_path(other: dict, idx: int, rule: LockRule, path: str) -> str | None:
    """The same logical field in the other graph, tolerating list-length shifts."""
    scenes = other.get('scenes') or []
    if idx >= len(scenes):
        return None
    tail = path.split(f'scenes[{idx}].content', 1)[-1]
    return f'scenes[{idx}].content{tail}'


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
    """
    used: dict[str, list[str]] = {}
    for name, g in graphs.items():
        for _, _, path, rule, _ in iter_locked(g):
            used.setdefault(rule.key, []).append(f'{name}:{path}')
    return {
        'rules': len(LOCK_RULES),
        'exercised': len(used),
        'unexercised': sorted({r.key for r in LOCK_RULES} - set(used)),
        'hit_counts': {k: len(v) for k, v in sorted(used.items())},
        'by_kind': {k: sorted(r.key for r in LOCK_RULES if r.kind == k)
                    for k in ('fact', 'copy', 'brand', 'identity')},
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