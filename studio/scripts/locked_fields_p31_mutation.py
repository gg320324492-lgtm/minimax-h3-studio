"""P31 mutation harness for the `outro` / `tagline` brand-lock guard.

Usage:  py -3.12 E:/Minimax-H3/studio/scripts/locked_fields_p31_mutation.py [name|all]

Protocol, inherited from `locked_fields_brand_mutation.py` (P30) in the order
this project has been burned in:
  1. snapshot the target BYTES at entry
  2. refuse to run a mutation whose anchor does not match exactly once — a
     mutation reported "untested" because the source moved is a number nobody
     checked
  3. AFTER writing, re-read and ASSERT the new bytes are present — a mutation
     that silently failed to apply proves nothing
  4. run the behavioural PROBE and compare it against the unmutated baseline.
     **Identical means INERT, not "survived"** — see `_probe()` below
  5. only then run pytest and print the full `-rf` FAILED lines plus the exit
     code. Raw output, not a verdict word: a test name and a line number can be
     checked by a reader, "MUTATION KILLED" cannot
  6. restore from the entry snapshot BYTES, never text — `write_text` translates
     line endings on Windows and P17 polluted 1101 lines that way
  7. compare the entry sha256 at exit

The probe is the part P30 learned the hard way. `if False: return` lands its
bytes in the file and leaves the suite green; "the mutation survived" and "the
mutation did nothing" are different claims with the same green output. So
`X_INERT_no_op_branch` is included below as a DELIBERATELY dead mutation: it
exists so the harness can be seen reporting INERT rather than claiming a kill
it did not earn.
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
    str(ROOT / 'tests' / 'test_outro_tagline_brand_lock.py'),
    str(ROOT / 'tests' / 'test_brand_lock_wiring.py'),
    str(ROOT / 'tests' / 'test_locked_fields.py'),
    str(ROOT / 'tests' / 'test_locked_fields_wiring.py'),
]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


#: Every observable this guard claims. The baseline is this dict with the
#: rulings in force; a mutation that leaves it identical changed no behaviour
#: and its green suite proves nothing about the guard.
_PROBE = r'''
import copy, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"@REPO@/studio/scripts")
import locked_fields as lf
B = json.load(open(r"@REPO@/pipeline/graphs/p29_new_renderer_showcase.json", encoding="utf-8"))
C = json.load(open(r"@REPO@/pipeline/examples/charts_demo.json", encoding="utf-8"))

def one(g, t):
    return copy.deepcopy([s for s in g["scenes"] if s.get("type") == t][0])

def wrap(s):
    # ⚠️ DEEP COPY, and the first version of this file did not. `wrap` returned
    # {"scenes": [s]} holding the SAME dict, so `wrap(o).pop("tagline")` also
    # popped it off `o` and every later measurement ran against a corrupted
    # fixture. That made the BASELINE probe die with KeyError: 'tagline', and
    # the harness then compared two identical *error strings* and printed
    # "INERT" — a false verdict in the exact place this harness exists to
    # prevent one. `run()` now refuses to compare a PROBE ERROR at all.
    return {"scenes": [copy.deepcopy(s)]}

out = {}

# --- ruling 1: the outro's wordmark is locked -----------------------------
o = one(B, "outro")
a = wrap(o); a["scenes"][0]["content"]["name"] = "X";  out["outro_rename"]   = len(lf.diff_locked(wrap(o), a))
a = wrap(o); a["scenes"][0]["content"].pop("name");    out["outro_delname"]  = len(lf.diff_locked(wrap(o), a))
a = wrap(o); a["scenes"][0]["type"] = "bar-chart";     out["outro_reroute"]  = len(lf.diff_locked(wrap(o), a))

# --- ruling 2: the tagline is locked, both directions --------------------
a = wrap(o); a["scenes"][0]["content"]["tagline"] = "X"; out["outro_retag"] = len(lf.diff_locked(wrap(o), a))
a = wrap(o); a["scenes"][0]["content"].pop("tagline");   out["outro_deltag"] = len(lf.diff_locked(wrap(o), a))
bare = wrap(o); bare["scenes"][0]["content"].pop("tagline")
a = copy.deepcopy(bare); a["scenes"][0]["content"]["tagline"] = "NEW"
out["outro_invent_tag"] = len(lf.diff_locked(bare, a))

# --- the logo baseline the whole shape was proved on ---------------------
l = one(B, "logo")
a = wrap(l); a["scenes"][0]["content"]["name"] = "X"
out["logo_rename"] = len(lf.diff_locked(wrap(l), a))

# --- over-lock directions: all of these MUST stay 0 ---------------------
a = wrap(one(B, "quote")); a["scenes"][0]["type"] = "stat-card"
out["nonbrand_reroute"] = len(lf.diff_locked(wrap(one(B, "quote")), a))
a = wrap(o); a["scenes"][0]["durationInFrames"] += 40
out["lever_on_outro"] = len(lf.diff_locked(wrap(o), a))
a = wrap(o); a["scenes"][0]["content"]["cta"] = "Z"
out["outro_cta"] = len(lf.diff_locked(wrap(o), a))
a = copy.deepcopy(C); a["scenes"][0].setdefault("content", {})["name"] = "Z"
out["chart_gets_name"] = len(lf.diff_locked(C, a))
a = copy.deepcopy(C); a["scenes"][0].setdefault("content", {})["tagline"] = "Z"
out["chart_gets_tagline"] = len(lf.diff_locked(C, a))
out["identity"] = len(lf.diff_locked(B, copy.deepcopy(B)))
out["bare_identity"] = len(lf.diff_locked(bare, copy.deepcopy(bare)))
print(json.dumps(out, sort_keys=True))
'''


def _probe() -> str:
    """The observable behaviour of the lock, as a dict of counts.

    A mutation whose bytes are in the file but which leaves this identical is
    INERT: it changed no behaviour, so a green suite afterwards proves nothing
    about the guard. Reporting that as "survived" is how P21/P22/P24 each
    produced a `NameError` and called it a result.
    """
    src = _PROBE.replace('@REPO@', REPO)
    p = subprocess.run([sys.executable, '-c', src], cwd=tempfile.gettempdir(),
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return (p.stdout.strip() or f'PROBE ERROR rc={p.returncode}: {p.stderr.strip()[-400:]}')


#: name -> (old_bytes, new_bytes). Bytes, not str, for reason 6 above.
MUTATIONS: dict[str, tuple[bytes, bytes]] = {}

# ── R1: `outro` is dropped from the locked scene types ───────────────────
_R1_OLD = b"LOCKED_SCENE_TYPES: frozenset[str] = frozenset({'logo', 'outro'})"
_R1_NEW = b"LOCKED_SCENE_TYPES: frozenset[str] = frozenset({'logo'})"
MUTATIONS['R1_outro_dropped_from_locked_scene_types'] = (_R1_OLD, _R1_NEW)

# ── R2: `tagline` is dropped from the brand content keys ─────────────────
_R2_OLD = b"BRAND_CONTENT_KEYS: tuple[str, ...] = ('name', 'tagline')"
_R2_NEW = b"BRAND_CONTENT_KEYS: tuple[str, ...] = ('name',)"
MUTATIONS['R2_tagline_dropped_from_brand_content_keys'] = (_R2_OLD, _R2_NEW)

# ── R3: the whole brand channel is removed from diff_locked (P30's M1) ───
_R3_OLD = (
    b"    scene_seen: set[tuple[int, str, str]] = set()\n"
    b"    emit(before, after, True, iter_scene_locked, scene_seen)\n"
    b"    emit(after, before, False, iter_scene_locked, scene_seen)\n"
)
_R3_NEW = (
    b"    scene_seen: set[tuple[int, str, str]] = set()\n"
    b"    # MUTATION R3: the brand channel is not wired into diff_locked at all.\n"
)
MUTATIONS['R3_brand_channel_removed_from_diff_locked'] = (_R3_OLD, _R3_NEW)

# ── R4: OVER-LOCK — the rule emits for EVERY scene type (P30's M3) ───────
# The one that must stay red. It catches strictly MORE, so it passes every
# "does the lock catch?" test in the suite and reads as hardening. P30 measured
# 65 passed under it. Only the over-lock tests can see it, and that property is
# the thing P31 has to keep.
_R4_OLD = (
    b"        stype = scene.get('type')\n"
    b"        if stype not in LOCKED_SCENE_TYPES:\n"
    b"            continue\n"
)
_R4_NEW = (
    b"        stype = scene.get('type')\n"
    b"        if False:  # MUTATION R4: no scene-type filter, over-lock\n"
    b"            continue\n"
)
MUTATIONS['R4_rule_emits_for_every_scene_type'] = (_R4_OLD, _R4_NEW)

# ── X: DELIBERATELY INERT. Not a guard result — a harness self-test. ─────
# Dead code in front of the real filter. The bytes land; the behaviour does not
# move; a naive reading calls it "survived". The probe below must report INERT.
_X_OLD = (
    b"        stype = scene.get('type')\n"
    b"        if stype not in LOCKED_SCENE_TYPES:\n"
)
_X_NEW = (
    b"        stype = scene.get('type')\n"
    b"        if False:  # MUTATION X: never executes\n"
    b"            pass\n"
    b"        if stype not in LOCKED_SCENE_TYPES:\n"
)
MUTATIONS['X_INERT_dead_branch_no_op'] = (_X_OLD, _X_NEW)


def run(name: str, baseline: str, run_pytest: bool = True) -> int:
    # A crashed probe measures nothing. Comparing two identical ERROR strings
    # reports "INERT" — which is a real verdict — about two runs that both
    # failed to measure. The first version of this harness did exactly that and
    # nearly recorded it as a result.
    if baseline.startswith('PROBE ERROR'):
        print(f'!! {name}: the BASELINE probe did not run, so there is nothing to '
              f'compare against. {baseline}')
        print('!! Refusing to report any verdict.')
        return 4

    old, new = MUTATIONS[name]
    snapshot = LOCKED.read_bytes()
    entry_sha = hashlib.sha256(snapshot).hexdigest()
    try:
        if snapshot.count(old) != 1:
            print(f'!! {name}: anchor matched {snapshot.count(old)} times, expected 1. '
                  f'NOT APPLIED — this is an error, not a skip.')
            return 2
        LOCKED.write_bytes(snapshot.replace(old, new, 1))
        # (3) prove it landed, then (4) prove it MOVED something
        landed = LOCKED.read_bytes()
        if landed.count(new) != 1 or landed == snapshot:
            print(f'!! {name}: mutation did NOT land. Refusing to report a result.')
            LOCKED.write_bytes(snapshot)
            return 2
        print(f'== {name}: bytes landed ({len(new) - len(old):+d}), anchor was '
              f'{old.strip().splitlines()[0][:56]!r}')
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
    if _BASELINE.startswith('PROBE ERROR'):
        print('!! the baseline probe did not run — every verdict below would be '
              'about an error string. Stopping.')
        sys.exit(4)
    for n in names:
        run(n, _BASELINE)
        print()