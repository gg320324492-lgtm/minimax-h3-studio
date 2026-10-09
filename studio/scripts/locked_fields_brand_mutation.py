"""P30 mutation harness for the brand lock guard.

Usage:  py -3.12 E:/Minimax-H3/_p30_mutation_run.py [name|all]

Protocol, in the order this project has been burned in:
  1. snapshot the target BYTES at entry
  2. refuse to run a mutation whose anchor does not match (a mutation reported
     as "untested" because the source moved is a number nobody checked)
  3. AFTER writing, re-read the file and ASSERT the mutation is present —
     a mutation that silently failed to apply proves nothing
  4. print the full `FAILED ::test_name` lines from `-rf` plus the file:line
  5. restore from the entry snapshot BYTES (not text: `write_text` translates
     line endings on Windows — P17 polluted 1101 lines that way)
  6. compare the entry sha256 at exit

Output is `-rf` raw output, not a verdict word: a test name and a line number
can be checked by a reader; "MUTATION KILLED" cannot.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# This harness prints pytest output that may contain characters the Windows
# console codepage rejects. Reconfigure THIS process's stdout only — the pytest
# subprocess is deliberately left alone, because exporting PYTHONIOENCODING
# into the suite is what breaks test_visual_qa.py.
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
LOCKED = ROOT / 'studio' / 'scripts' / 'locked_fields.py'
REPO = ROOT.as_posix()          # embedded into the probe source below
TARGETS = [
    str(ROOT / 'tests' / 'test_brand_lock_wiring.py'),
    str(ROOT / 'tests' / 'test_locked_fields.py'),
    str(ROOT / 'tests' / 'test_locked_fields_wiring.py'),
]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


_PROBE = r'''
import copy, json, sys
sys.path.insert(0, r"@REPO@/studio/scripts")
import locked_fields as lf
B = json.load(open(r"@REPO@/pipeline/graphs/p29_new_renderer_showcase.json", encoding="utf-8"))
C = json.load(open(r"@REPO@/pipeline/examples/charts_demo.json", encoding="utf-8"))
bi = [i for i, s in enumerate(B["scenes"]) if s.get("type") == "logo"][0]
ni = [i for i, s in enumerate(B["scenes"]) if s.get("type") == "browser-window"][0]
out = {}
a = copy.deepcopy(B); a["scenes"][bi]["type"] = "bar-chart";      out["brand_reroute"] = len(lf.diff_locked(B, a))
a = copy.deepcopy(B); a["scenes"][bi]["content"]["name"] = "X";  out["brand_rename"]  = len(lf.diff_locked(B, a))
a = copy.deepcopy(B); a["scenes"][ni]["type"] = "card-grid";     out["nonbrand_reroute"] = len(lf.diff_locked(B, a))
a = copy.deepcopy(B); a["scenes"][bi]["durationInFrames"] += 7;  out["lever_on_brand"] = len(lf.diff_locked(B, a))
a = copy.deepcopy(C); a["scenes"][0].setdefault("content", {})["name"] = "Z"
out["chart_gets_a_name"] = len(lf.diff_locked(C, a))
out["identity_diff"] = len(lf.diff_locked(B, copy.deepcopy(B)))
a = copy.deepcopy(B); del a["scenes"][bi];                      out["brand_scene_deleted"] = len(lf.diff_locked(B, a))
print(json.dumps(out, sort_keys=True))
'''


def _probe() -> str:
    """The observable behaviour of the lock, as six numbers.

    A mutation whose bytes are in the file but which leaves this identical is
    INERT: it changed no behaviour, so a green suite afterwards proves nothing
    about the guard. Reporting that as "survived" is how P21/P22/P24 each
    produced a `NameError` and called it a result.
    """
    src = _PROBE.replace('@REPO@', REPO)
    p = subprocess.run([sys.executable, '-c', src], cwd=tempfile.gettempdir(),
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return (p.stdout.strip() or f'PROBE ERROR rc={p.returncode}: {p.stderr.strip()[-400:]}')


#: name -> (old_bytes, new_bytes). Bytes, not str, for reason 5 above.
MUTATIONS: dict[str, tuple[bytes, bytes]] = {}

# ── M1: the brand rule is absent from diff_locked — i.e. TODAY'S STATE ──────
_M1_OLD = (
    b"    scene_seen: set[tuple[int, str, str]] = set()\n"
    b"    emit(before, after, True, iter_scene_locked, scene_seen)\n"
    b"    emit(after, before, False, iter_scene_locked, scene_seen)\n"
)
_M1_NEW = (
    b"    scene_seen: set[tuple[int, str, str]] = set()\n"
    b"    # MUTATION M1: the brand rule is not wired into diff_locked at all.\n"
)
MUTATIONS['M1_brand_rule_absent_from_diff_locked'] = (_M1_OLD, _M1_NEW)

# ── M2: the pass IS called, but the rule never emits ──────────────────────
# Differs from M1 on purpose: M1 kills the call site, M2 kills the walker. A
# guard that only catches M1 would be satisfied by re-adding the two emit lines
# while leaving the rule unable to produce anything.
#
# ⚠️ The first attempt at this was `if False: return`, which is a NO-OP: the
# branch never runs, the generator still yields, and the whole suite stayed
# green — which read exactly like "the guard missed a real mutation". The bytes
# were in the file. The behaviour was not. Hence _probe() below: a mutation
# that does not move the probe is reported INERT, never SURVIVED.
_M2_OLD = (
    b"        stype = scene.get('type')\n"
    b"        if stype not in LOCKED_SCENE_TYPES:\n"
)
_M2_NEW = (
    b"        stype = scene.get('type')\n"
    b"        if stype not in LOCKED_SCENE_TYPES or True:  # MUTATION M2\n"
)
MUTATIONS['M2_rule_never_emits'] = (_M2_OLD, _M2_NEW)

# ── M3: OVER-LOCK — the rule emits for EVERY scene type ───────────────────
# This is where the work order's `if False:` lands: neutering the scene-type
# filter does not disable the rule, it universalises it. It catches strictly
# more, so it passes every "does the lock catch?" test and would read as
# hardening. Only the non-brand tests can see it.
_M3_OLD = (
    b"        stype = scene.get('type')\n"
    b"        if stype not in LOCKED_SCENE_TYPES:\n"
    b"            continue\n"
)
_M3_NEW = (
    b"        stype = scene.get('type')\n"
    b"        if False:  # MUTATION M3: no scene-type filter, over-lock\n"
    b"            continue\n"
)
MUTATIONS['M3_rule_emits_for_every_scene_type'] = (_M3_OLD, _M3_NEW)

# ── M4: a legitimate 11.1 lever gets locked ───────────────────────────────
MUTATIONS['M4_lock_a_legitimate_lever'] = (
    b"    LockRule('labels', 'identity', 'axis labels are the data, not decoration'),\n",
    b"    LockRule('labels', 'identity', 'axis labels are the data, not decoration'),\n"
    b"    LockRule('durationInFrames', 'copy', 'MUTATION M4: locked a 11.1 lever'),\n",
)

# ── M5: the whole brand scene is locked, wordmark included ────────────────
# The blunt over-lock: one finding per changed key, so the seven levers that
# live on the SAME scene stop working. Passes every "is the brand caught?" test.
_M5_OLD = b"        yield i, sid, f'scenes[{i}].type', _SCENE_TYPE_RULE, stype\n"
_M5_NEW = (
    b"        yield i, sid, f'scenes[{i}]', _SCENE_TYPE_RULE, dict(scene)\n"
)
MUTATIONS['M5_lock_the_whole_brand_scene'] = (_M5_OLD, _M5_NEW)


def run(name: str, baseline: str) -> int:
    old, new = MUTATIONS[name]
    snapshot = LOCKED.read_bytes()
    entry_sha = hashlib.sha256(snapshot).hexdigest()
    try:
        if snapshot.count(old) != 1:
            print(f'!! {name}: anchor matched {snapshot.count(old)} times, expected 1. '
                  f'NOT APPLIED — this is an error, not a skip.')
            return 2
        LOCKED.write_bytes(snapshot.replace(old, new, 1))
        # (3) prove it landed, then prove it MOVED something
        landed = LOCKED.read_bytes()
        if landed.count(new) != 1 or landed == snapshot:
            print(f'!! {name}: mutation did NOT land. Refusing to report a result.')
            LOCKED.write_bytes(snapshot)
            return 2
        print(f'== {name}: bytes landed ({len(new) - len(old):+d}), anchor was '
              f'{old.strip().splitlines()[0][:52]!r}')
        probe = _probe()
        print(f'== probe: {probe}')
        if probe == baseline:
            print(f'!! {name}: INERT — behaviour identical to the unmutated baseline.')
            print('!! A green suite below this line would prove NOTHING about the guard.')
            print('!! Not counting this as "survived"; the mutation needs rewriting.')
            return 3
        print('== probe moved vs baseline -> the mutation is live, result below is real')
        proc = subprocess.run(
            [sys.executable, '-m', 'pytest', *TARGETS, '-q', '-rf', '--no-header', '--tb=line'],
            cwd=tempfile.gettempdir(), capture_output=True, text=True,
            encoding='utf-8', errors='replace')
        print(proc.stdout[-9000:])
        print(f'-- pytest exit code: {proc.returncode}')
        return proc.returncode
    finally:
        LOCKED.write_bytes(snapshot)
        after = hashlib.sha256(LOCKED.read_bytes()).hexdigest()
        print(f'== restored {LOCKED.name}: sha256 {after[:16]} '
              f'{"MATCHES entry snapshot" if after == entry_sha else "*** MISMATCH ***"}')


if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'all'
    names = list(MUTATIONS) if which == 'all' else [which]
    _BASELINE = _probe()
    print(f'== BASELINE probe (unmutated): {_BASELINE}')
    print(f'== baseline sha256: {_sha(LOCKED)[:16]}')
    for n in names:
        run(n, _BASELINE)
        print()
