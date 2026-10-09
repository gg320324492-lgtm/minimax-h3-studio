"""Mutation harness for the 11.2 wiring guard.

Usage:  py -3.12 studio/scripts/locked_fields_mutation.py [name|all]

Reports, per mutation: the full `FAILED ::test_name` lines pytest prints under
-rf, and the file:line each one failed on. The reason this is the whole output
format and not a verdict word: two rounds in a row, the agent running this work
reported an acceptance criterion as met and the reviewer could not reproduce
it. A verdict string cannot be checked by a reader; a test name and a line
number can.

Nothing here writes to the source design tokens, so unlike the geometry harness
there is no poisoned-baseline hazard to guard against — but the test file IS
the mutation target, so it is restored from the snapshot taken at entry, and
the end-of-run check compares against it for the same reason as before: a
harness that restores a stale snapshot writes the damage back on the next run.

TWO ANCHORS HERE WERE DEAD UNTIL P34, AND THE LEDGER COUNTED THEM AS KILLED.
`diff_always_empty` and `drop_second_emit` anchored on lines P30 deleted when
it rewrote `diff_locked`. The anchor check caught it — "ANCHOR NOT FOUND", exit
1 — which is the correct behaviour, and it also means neither mutation had run
since P30 while a "4/4 killed" line still counted them. Repaired in place, with
the reasoning at each anchor. Both are now killed by real tests AND verified to
move `diff_locked`'s actual output, because a red suite proves nothing about a
guard if the mutation was inert.

WHAT THIS HARNESS DOES NOT HAVE, AND THE BRAND ONE DOES: a `_probe()` that
measures the lock's behaviour before and after. `returncode` and a list of
FAILED lines cannot tell a live mutation from one that landed and changed
nothing. Verified out of band for P34; adding the probe here is the obvious
next step and is not done because it is a behaviour change to a harness whose
output other ledger entries are quoted against.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCKED = ROOT / 'studio' / 'scripts' / 'locked_fields.py'
TEST = ROOT / 'tests' / 'test_locked_fields_wiring.py'


def _is_crlf() -> bool:
    return b'\r\n' in TEST.read_bytes()


def _anchor(text: str) -> bytes:
    return text.replace('\n', '\r\n').encode('utf-8') if _is_crlf() else text.encode('utf-8')


#: name -> (file, old, new) as TEXT. An anchor that does not match is an ERROR,
#: never a skip: a mutation reported as "untested" because the source moved is a
#: number nobody checked.
MUTATIONS: dict[str, tuple[Path, str, str]] = {
    # 1. lock a legitimate lever: 11.1's repair loop would become unable to move
    #    the staging of a claim, and the only symptom is a loop that does nothing.
    'lock_a_legitimate_lever': (
        LOCKED,
        "    LockRule('labels', 'identity', 'axis labels are the data, not decoration'),\n",
        "    LockRule('labels', 'identity', 'axis labels are the data, not decoration'),\n"
        "    LockRule('durationInFrames', 'copy', 'MUTATION: locked a legitimate lever'),\n",
    ),
    # 2. drop the labels rule entirely: the identity attack stops being caught.
    'drop_labels_rule': (
        LOCKED,
        "    LockRule('labels', 'identity', 'axis labels are the data, not decoration'),\n",
        "",
    ),
    # 3. diff_locked never reports anything.
    #    ANCHOR REPAIRED (P34): this used to anchor on
    #    `b_by_path = {p: v for _, _, p, _, v in iter_locked(before)}`, which P30
    #    deleted when it rewrote `diff_locked` into the two-pass `emit()` form.
    #    The harness correctly refused it ("ANCHOR NOT FOUND"), so this mutation
    #    had not run since P30 while the ledger still counted it in "4/4 killed".
    #    The intent — the whole diff is suppressed — is now anchored on the
    #    function's own return, which is the only line every version has had.
    'diff_always_empty': (
        LOCKED,
        "def diff_locked(before: dict, after: dict) -> list[LockedField]:\n",
        "def diff_locked(before: dict, after: dict) -> list[LockedField]:\n"
        "    return []  # MUTATION: diff_locked never reports anything\n",
    ),
    # 4. the second emit() is removed. diff_locked(a, b) and diff_locked(b, a)
    #    then find different counts, which is the bidirectional invariant.
    #    ANCHOR REPAIRED (P34): P30 turned the two 3-argument `emit()` calls into
    #    four 5-argument ones (two walks x two directions), so the old anchor
    #    `emit(before, after, primary=True)` / `emit(after, before, primary=False)`
    #    stopped existing too. This now removes the reverse pass of the FIRST
    #    walk only — dropping all four would also kill the brand lock and would
    #    no longer be the bidirectional-invariant mutation it claims to be.
    'drop_second_emit': (
        LOCKED,
        "    emit(after, before, False, iter_locked, field_seen)\n",
        "    # MUTATION: the reverse pass of the content walk is removed\n",
    ),
    # 5. the zero-consumer self-check is deleted: the guard can no longer notice
    #    itself being weakened.
    'drop_self_check': (
        TEST,
        "        want = probe.resolve()\n",
        "        want = probe.resolve()\n        return  # MUTATION: self-check removed\n",
    ),
    # 6. the zero-consumer assertion is deleted from the test file itself.
    'drop_zero_consumer_assert': (
        TEST,
        "    consumers = _production_consumers()\n",
        "    consumers = []  # MUTATION\n",
    ),
    # 7. the attack assertions stop requiring a violation.
    'attacks_always_pass': (
        TEST,
        "    assert violations, f'{attack!r} changed a locked field and the lock said nothing'\n",
        "    assert True  # MUTATION\n",
    ),
    # 8. the symmetry assertion compares nothing.
    'symmetry_tautology': (
        TEST,
        "    assert len(forward) == len(reverse), (\n",
        "    assert len(forward) == len(forward) or True, (  # MUTATION\n",
    ),
    # 9. an attack test neutered to `assert True` — which is still an ast.Assert,
    #    so the first version of the self-check (count assertions) passed it.
    'attack_neutered_to_true': (
        TEST,
        "    assert violations, f'{attack!r} changed a locked field and the lock said nothing'\n",
        "    assert violations is not None or True  # MUTATION\n",
    ),
    # 10. the self-check itself neutered: if the tautology detector can be
    #     turned off, nothing above it is protected any more.
    'selfcheck_neutered': (
        TEST,
        "    assert not tautological, (\n",
        "    assert not tautological or True, (  # MUTATION\n",
    ),
    # 11. the zero-consumer test stops calling the scanner at all.
    'zero_consumer_no_scan': (
        TEST,
        "    consumers = _production_consumers()\n",
        "    consumers = _production_consumers()\n"
        "    consumers = []  # MUTATION: scanned, then discarded\n",
    ),
}


def run(target: str) -> tuple[int, list[str], list[str]]:
    """(returncode, FAILED lines, 'file:line: AssertionError' lines)."""
    r = subprocess.run(
        ['py', '-3.12', '-m', 'pytest', target, '-q', '--no-header', '-rf',
         '-p', 'no:cacheprovider'],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        cwd='/tmp',
    )
    out = (r.stdout or '') + (r.stderr or '')
    lines = out.splitlines()
    failed = [ln.strip() for ln in lines if ln.strip().startswith('FAILED')]
    where = [ln.strip() for ln in lines
             if ln.strip().endswith('AssertionError') and ':' in ln
             and 'tests' in ln.lower()]
    return r.returncode, failed, where


def main() -> int:
    if len(sys.argv) < 2:
        print('usage: locked_fields_mutation.py <name|all> [target]')
        return 2
    name = sys.argv[1]
    target = sys.argv[2] if len(sys.argv) > 2 else str(TEST)
    names = list(MUTATIONS) if name == 'all' else [name]
    unknown = [n for n in names if n not in MUTATIONS]
    if unknown:
        print(f'unknown mutation(s): {unknown}')
        return 2

    rc, failed, where = run(target)
    t0 = TEST.read_bytes()
    print(f'BASELINE  returncode={rc}  failed={len(failed)}')
    if rc != 0:
        print('refusing to mutate a red baseline')
        for f in failed:
            print(f'  {f}')
        return 1

    for n in names:
        f, old_txt, new_txt = MUTATIONS[n]
        snap = f.read_bytes()
        old, new = _anchor(old_txt), _anchor(new_txt)
        if old not in snap:
            print(f'\n{n}: ANCHOR NOT FOUND in {f.name} — the source moved. '
                  f'This is a harness bug, not an untested mutation.')
            f.write_bytes(snap)
            return 1
        try:
            f.write_bytes(snap.replace(old, new, 1))
            rc, failed, where = run(target)
            print(f'\n=== {n} ===')
            print(f'  returncode={rc}  failed={len(failed)}')
            for line in failed:
                print(f'  {line}')
            for line in where[:4]:
                print(f'  at {line}')
        finally:
            f.write_bytes(snap)

    now = hashlib.sha256(TEST.read_bytes()).hexdigest()
    entry = hashlib.sha256(t0).hexdigest()
    print(f'\ntest file digest: {"UNCHANGED" if now == entry else "CHANGED!"}')
    if now != entry:
        TEST.write_bytes(t0)
    return 0 if now == entry else 3


if __name__ == '__main__':
    sys.exit(main())
