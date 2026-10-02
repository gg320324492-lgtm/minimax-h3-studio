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
    'diff_always_empty': (
        LOCKED,
        "    b_by_path = {p: v for _, _, p, _, v in iter_locked(before)}\n",
        "    return []  # MUTATION\n"
        "    b_by_path = {p: v for _, _, p, _, v in iter_locked(before)}\n",
    ),
    # 4. the second emit() is removed. diff_locked(a, b) and diff_locked(b, a)
    #    then find different counts, which is the bidirectional invariant.
    'drop_second_emit': (
        LOCKED,
        "    emit(before, after, primary=True)\n    emit(after, before, primary=False)\n",
        "    emit(before, after, primary=True)  # MUTATION: second pass removed\n",
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
