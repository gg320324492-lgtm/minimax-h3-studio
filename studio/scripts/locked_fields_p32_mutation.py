"""P32 mutation harness for the `iter_locked` reachability guard.

Usage:  py -3.12 E:/Minimax-H3/studio/scripts/locked_fields_p32_mutation.py [name|all]

Protocol, inherited from `locked_fields_p31_mutation.py` verbatim, because the
order is the lesson and not an accident of style:
  1. snapshot the target BYTES at entry
  2. refuse a mutation whose anchor does not match exactly once — "untested
     because the source moved" is a number nobody checked
  3. AFTER writing, re-read and ASSERT the new bytes are present
  4. run the behavioural PROBE and compare against the unmutated baseline.
     **Identical means INERT, not "survived"**
  5. only then run pytest, printing the full `-rf` FAILED lines and exit code
  6. restore from the entry snapshot BYTES — `write_text` translates line
     endings on Windows and P17 polluted 1101 lines that way
  7. compare the entry sha256 at exit

⚠️ WHY THIS HARNESS EXISTS AT ALL. `locked_fields_mutation.py` carries a
mutation named `lock_a_legitimate_lever` and the ledger listed it among the
four that "all kill". It was INERT: `iter_locked` entered each scene through
`content`, every 11.1 lever is a top-level SceneSchema key BESIDE it, so a rule
named after one could never fire on a real graph. The suite was green under it
and a reader was told there was a behavioural evidence chain. This file exists
so that claim is either measured or withdrawn.

The probe below measures the three things P32 actually changed, and the INERT
check is what stops a green suite from being reported as a kill: if the probe
equals the baseline, the mutation moved nothing and NO verdict is emitted.

`X_INERT_dead_branch_no_op` is carried over deliberately. It exists so the
harness can be SEEN reporting INERT rather than claiming a kill it did not earn.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# This harness prints pytest output that may contain characters the Windows
# console codepage rejects. Reconfigure THIS process's stdout only; the pytest
# subprocess is deliberately left alone, because exporting PYTHONIOENCODING into
# the suite is what breaks test_visual_qa.py.
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

LOCKED = ROOT / 'studio' / 'scripts' / 'locked_fields.py'
WIRING = ROOT / 'tests' / 'test_locked_fields_wiring.py'
REPO = ROOT.as_posix()
TARGETS = [
    str(ROOT / 'tests' / 'test_locked_fields_wiring.py'),
    str(ROOT / 'tests' / 'test_locked_fields.py'),
]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


#: Every observable this guard claims, as a dict of counts. The baseline is this
#: dict with the rulings in force; a mutation leaving it identical changed no
#: behaviour and its green suite proves nothing.
_PROBE = r'''
import copy, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"@REPO@/studio/scripts")
import locked_fields as lf

C = json.load(open(r"@REPO@/pipeline/examples/charts_demo.json", encoding="utf-8"))
S = json.load(open(r"@REPO@/pipeline/examples/showcase_demo.json", encoding="utf-8"))
B = json.load(open(r"@REPO@/pipeline/graphs/p29_new_renderer_showcase.json", encoding="utf-8"))
out = {}

# --- 1. the seven levers must stay UNLOCKED, on real shipped graphs -------
# ⚠️ {"scenes": [...]} SHAPE, not a bare scene. The command window measured
# P30 by passing a bare scene; `iter_locked` reads `graph['scenes']` and found
# nothing, reporting "0 of everything" — a measurement taken at the wrong scale.
def mut(g, scope, fn):
    a = copy.deepcopy(g)
    fn(a if scope == "graph" else a["scenes"][0])
    return a

def _edit1(s, key):
    if key == "durationInFrames":
        s["durationInFrames"] = 999
    elif key == "camera":
        s["camera"]["translateZ"] = 999
    elif key == "motion":
        s["motion"]["preset"] = "MUT"
    elif key == "layout":
        s["layout"]["padX"] = 999
    elif key == "transitionIn":
        s["transitionIn"]["in"] = "MUT"
    elif key == "style_bible":
        s["style_bible"] = {"palette": {"a": 1}}
    elif key == "format":
        s["format"]["width"] = 1080

# key -> (graph, scope). `layout`/`transitionIn` live on showcase_demo's chart
# scenes; charts_demo carries the rest. Chosen from the shipped files, so every
# edit below mutates a key that genuinely EXISTS — an edit that adds the key
# would prove nothing about a lever that is already there.
for _key, (_g, _scope) in (
    ("durationInFrames", (C, "scene")),
    ("camera", (C, "scene")),
    ("motion", (C, "scene")),
    ("layout", (S, "scene")),
    ("transitionIn", (S, "scene")),
    ("style_bible", (C, "scene")),
    ("format", (C, "graph")),
):
    out["lever_" + _key] = len(lf.diff_locked(
        _g, mut(_g, _scope, (lambda k: (lambda s: _edit1(s, k)))(_key))))

# --- 2. reachability: exemptions lifted + a rule per lever ---------------
# This is the measurement the old `lock_a_legitimate_lever` could not make.
saved_rules, saved_levers = lf._RULES_BY_KEY, lf.LEGITIMATE_LEVERS
lf.LEGITIMATE_LEVERS = frozenset()
probe_levers = ("durationInFrames", "camera", "motion", "layout",
                "transitionIn", "format")
for lev in probe_levers:
    lf._RULES_BY_KEY[lev] = lf.LockRule(lev, "copy", "P32 probe")
seen = set()
for g in (C, S, B):
    for _i, _s, p, _r, _v in lf.iter_locked(g):
        seen.add(lf.lever_key_of(p))
out["reach_count"] = len([k for k in probe_levers if k in seen])
out["reach_missing"] = sorted(k for k in probe_levers if k not in seen)

# --- 3. exemptions still REFUSE even with the rule present ---------------
# ⚠️ Written as a plain dict of small lambdas, not the nested-conditional
# lambda pyramid the first version used. That version had a syntax error and
# `run()` correctly refused to report a verdict for it — but a probe that does
# not parse measures nothing, and readability is what stops the next edit from
# reintroducing that.
lf._RULES_BY_KEY = dict(saved_rules)
lf.LEGITIMATE_LEVERS = saved_levers

def _edit(s, key):
    if key == "durationInFrames":
        s["durationInFrames"] = 999
    elif key == "camera":
        s["camera"]["translateZ"] = 999
    elif key == "motion":
        s["motion"]["preset"] = "MUT"
    elif key == "layout":
        s["layout"]["padX"] = 999
    elif key == "transitionIn":
        s["transitionIn"]["in"] = "MUT"
    elif key == "format":
        s["format"]["width"] = 1080

for lev in probe_levers:
    lf._RULES_BY_KEY[lev] = lf.LockRule(lev, "copy", "P32 probe")
    base = S if lev in ("layout", "transitionIn") else C
    scope = "graph" if lev == "format" else "scene"
    out["exempt_" + lev] = len(lf.diff_locked(base, mut(base, scope,
        (lambda k: (lambda s: _edit(s, k)))(lev))))
lf._RULES_BY_KEY = saved_rules
lf.LEGITIMATE_LEVERS = saved_levers

# --- 4. the claims must still be caught (regression floor) ---------------
out["attack_value"] = len(lf.diff_locked(C, mut(C, "scene",
    lambda s: s["content"]["chart"]["values"].__setitem__(0, 1.0))))
out["attack_labels"] = len(lf.diff_locked(C, mut(C, "scene",
    lambda s: s["content"]["chart"]["labels"].pop())))
out["attack_headline"] = len(lf.diff_locked(C, mut(C, "scene",
    lambda s: s["content"].__setitem__("headline", "x"))))
out["identity"] = len(lf.diff_locked(B, copy.deepcopy(B)))

# --- 5. brand lock untouched ---------------------------------------------
o = [s for s in B["scenes"] if s.get("type") == "outro"][0]
def wrap(s):
    return {"scenes": [copy.deepcopy(s)]}
out["outro_rename"] = len(lf.diff_locked(wrap(o), (lambda a: (a["scenes"][0]["content"].__setitem__("name", "X"), a)[1])(wrap(o))))
out["outro_reroute"] = len(lf.diff_locked(wrap(o), (lambda a: (a["scenes"][0].__setitem__("type", "bar-chart"), a)[1])(wrap(o))))

out["coverage"] = {k: v for k, v in sorted(lf.coverage_report(
    {"c": C, "s": S, "b": B}).items())
    if k in ("rules", "exercised", "unexercised", "by_kind", "hit_counts")}
print(json.dumps(out, sort_keys=True, default=str))
'''


def _probe() -> str:
    """The observable behaviour of the lock, as JSON.

    A mutation whose bytes are in the file but which leaves this identical is
    INERT: it changed no behaviour, so a green suite afterwards proves nothing
    about the guard. Reporting that as "survived" is how earlier rounds produced
    a `NameError` and called it a result.
    """
    src = _PROBE.replace('@REPO@', REPO)
    p = subprocess.run([sys.executable, '-c', src], cwd=tempfile.gettempdir(),
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return (p.stdout.strip() or f'PROBE ERROR rc={p.returncode}: {p.stderr.strip()[-400:]}')


#: name -> (target, old_bytes, new_bytes). Bytes, not str, for reason 6 above.
MUTATIONS: dict[str, tuple[Path, bytes, bytes]] = {}

# ── M1: drop a lever from the exemption list ─────────────────────────────
# The one the work order requires. Without the exemption, a rule for the lever
# FIRES, so the lever becomes locked and the repair loop is strangled — which is
# the exact harm 11.2 named. Expected: probe moves (exempt_* and reach_* change),
# suite goes RED.
_M1_OLD = b"""LEGITIMATE_LEVERS: frozenset[str] = frozenset({
    'durationInFrames', 'style_bible', 'layout', 'camera', 'motion',
    'transitionIn', 'transitionOut',
    'format',          # graph-level, not a SceneSchema key \xe2\x80\x94 showcase-v1.ts:319
})"""
_M1_NEW = b"""LEGITIMATE_LEVERS: frozenset[str] = frozenset({
    'style_bible', 'layout', 'camera', 'motion',
    'transitionIn', 'transitionOut',
    'format',          # graph-level, not a SceneSchema key \xe2\x80\x94 showcase-v1.ts:319
})"""
MUTATIONS['M1_drop_a_lever_from_the_exemption_list'] = (LOCKED, _M1_OLD, _M1_NEW)

# ── M2: the top-level traversal stops ────────────────────────────────────
# The pre-P32 shape, restored verbatim. Expected: `reach_missing` becomes the
# full lever list, suite goes RED on the reachability test.
#
# ⚠️ This anchor broke once, when a refactor moved `_emit_locked`'s call onto one
# line. The harness reported "anchor matched 0 times ... this is an error, not a
# skip" rather than silently passing the mutation off as tested — which is the
# behaviour reason 2 above exists. Re-anchored to the current shape.
_M2_OLD = (
    b"        # the scene's own keys, beside `content` \xe2\x80\x94 where the levers live\n"
    b"        top = {k: v for k, v in scene.items() if k != 'content'}\n"
    b"        for path, rule, value in _emit_locked(_walk(top, f'scenes[{i}]')):\n"
    b"            yield i, sid, path, rule, value\n"
)
_M2_NEW = (
    b"        # MUTATION M2: the top-level traversal is gone (the pre-P32 shape).\n"
)
MUTATIONS['M2_top_level_traversal_stops'] = (LOCKED, _M2_OLD, _M2_NEW)

# ── M3: the exemption check always passes ────────────────────────────────
# The criterion is neutered, so nothing is exempt. Expected: probe moves,
# suite goes RED on the seven lever tests.
_M3_OLD = b"        if lever_key_of(path) in LEGITIMATE_LEVERS:\n            continue\n"
_M3_NEW = b"        if False:  # MUTATION M3: the exemption check never fires\n            continue\n"
MUTATIONS['M3_exemption_criterion_always_passes'] = (LOCKED, _M3_OLD, _M3_NEW)

# ── X: DELIBERATELY INERT. Not a guard result — a harness self-test. ─────
# Dead code in front of the real check. The bytes land; the behaviour does not
# move; a naive reading calls it "survived". The probe must report INERT.
_X_OLD = (
    b"        if lever_key_of(path) in LEGITIMATE_LEVERS:\n"
    b"            continue\n"
)
_X_NEW = (
    b"        if False:  # MUTATION X: never executes\n"
    b"            pass\n"
    b"        if lever_key_of(path) in LEGITIMATE_LEVERS:\n"
    b"            continue\n"
)
MUTATIONS['X_INERT_dead_branch_no_op'] = (LOCKED, _X_OLD, _X_NEW)


def run(name: str, baseline: str, run_pytest: bool = True) -> int:
    # A crashed probe measures nothing. Comparing two identical ERROR strings
    # reports "INERT" — a real verdict — about two runs that both failed to
    # measure. Refuse to compare them at all.
    if baseline.startswith('PROBE ERROR'):
        print(f'!! {name}: the BASELINE probe did not run, so there is nothing to '
              f'compare against. {baseline}')
        print('!! Refusing to report any verdict.')
        return 4

    target, old, new = MUTATIONS[name]
    snapshot = target.read_bytes()
    entry_sha = hashlib.sha256(snapshot).hexdigest()
    try:
        if snapshot.count(old) != 1:
            print(f'!! {name}: anchor matched {snapshot.count(old)} times, expected 1. '
                  f'NOT APPLIED — this is an error, not a skip.')
            return 2
        target.write_bytes(snapshot.replace(old, new, 1))
        # (3) prove it landed, then (4) prove it MOVED something
        landed = target.read_bytes()
        if landed.count(new) != 1 or landed == snapshot:
            print(f'!! {name}: mutation did NOT land. Refusing to report a result.')
            target.write_bytes(snapshot)
            return 2
        print(f'== {name}: bytes landed ({len(new) - len(old):+d}) in {target.name}')
        probe = _probe()
        print(f'== probe: {probe}')
        if probe.startswith('PROBE ERROR'):
            print(f'!! {name}: the mutated probe did not run. {probe}')
            print('!! Refusing to report a verdict — a broken probe is not a green suite.')
            return 4
        if probe == baseline:
            print(f'!! {name}: INERT — behaviour identical to the unmutated baseline.')
            print('!! A green suite below this line would prove NOTHING about the guard.')
            print('!! NOT counting this as "survived"; the mutation needs rewriting.')
            if run_pytest:
                print('== (running the suite anyway, for the record — read nothing into it)')
                proc = subprocess.run(
                    [sys.executable, '-m', 'pytest', *TARGETS, '-q', '-rf', '--no-header', '--tb=line'],
                    cwd=tempfile.gettempdir(), capture_output=True, text=True,
                    encoding='utf-8', errors='replace')
                print(proc.stdout[-2500:])
                print(f'-- pytest exit code: {proc.returncode}')
            return 3
        print('== probe moved vs baseline -> the mutation is live, result below is real')
        if not run_pytest:
            return 0
        proc = subprocess.run(
            [sys.executable, '-m', 'pytest', *TARGETS, '-q', '-rf', '--no-header', '--tb=line'],
            cwd=tempfile.gettempdir(), capture_output=True, text=True,
            encoding='utf-8', errors='replace')
        print(proc.stdout[-9000:])
        print(f'-- pytest exit code: {proc.returncode}')
        return proc.returncode
    finally:
        target.write_bytes(snapshot)
        after = hashlib.sha256(target.read_bytes()).hexdigest()
        print(f'== restored {target.name}: sha256 {after[:16]} '
              f'{"MATCHES entry snapshot" if after == entry_sha else "*** MISMATCH ***"}')


if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'all'
    names = list(MUTATIONS) if which == 'all' else [which]
    unknown = [n for n in names if n not in MUTATIONS]
    if unknown:
        print(f'unknown mutation(s): {unknown}; known: {list(MUTATIONS)}')
        sys.exit(2)
    _BASELINE = _probe()
    print(f'== BASELINE probe (unmutated): {_BASELINE}')
    print(f'== baseline sha256 locked_fields.py: {_sha(LOCKED)[:16]}')
    print(f'== baseline sha256 test_locked_fields_wiring.py: {_sha(WIRING)[:16]}')
    if _BASELINE.startswith('PROBE ERROR'):
        print('!! the baseline probe did not run — every verdict below would be '
              'about an error string. Stopping.')
        sys.exit(4)
    rc = 0
    for n in names:
        rc |= run(n, _BASELINE)
        print()
    print(f'== final sha256 locked_fields.py: {_sha(LOCKED)[:16]}')
    print(f'== final sha256 test_locked_fields_wiring.py: {_sha(WIRING)[:16]}')
    sys.exit(0 if rc in (0, 1) else rc)