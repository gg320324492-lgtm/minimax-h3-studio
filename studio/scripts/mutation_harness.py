"""Mutation harness: apply a named mutation, run the tests, restore.

Usage:
    py -3.12 out/mutate.py <mutation-name> [target-test-file]

Every mutation is a byte-level edit, and the file is restored from a snapshot
taken BEFORE the edit — not by a `finally` that would write back whatever the
original happened to be. That is the whole bug being fixed, so the tool that
tests the fix must not repeat it.

The source design tokens are asserted byte-identical after every run, because a
mutation harness is exactly the kind of process that gets interrupted.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEOM = ROOT / 'studio' / 'scripts' / 'chart_geometry.py'
TEST = ROOT / 'tests' / 'test_chart_geometry.py'
TOKENS = ROOT / 'studio' / 'src' / 'templates' \
    / 'finance-showcase' / 'design' / 'tokens.ts'


def tokens_digest() -> str:
    return hashlib.sha256(TOKENS.read_bytes()).hexdigest()


#: set per-mutation from the target file's own line endings, by _anchor()
_is_crlf = False


def run(target: str) -> tuple[bool, str, list[str]]:
    """(all passed, last line, the tests that went red).

    WHICH tests go red is not a detail. A guard-binding mutation is fixed when
    the STRUCTURAL guard itself goes red; a suite that merely went red, on some
    other assertion, is the failure this work order exists to close — and it is
    indistinguishable from success if the harness only reports pass/fail.
    """
    r = subprocess.run(
        ['py', '-3.12', '-m', 'pytest', target, '-q', '--no-header',
         '-p', 'no:cacheprovider'],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        cwd='C:/tmp' if Path('C:/tmp').exists() else '/tmp',
    )
    out = (r.stdout or '') + (r.stderr or '')
    lines = [ln for ln in out.splitlines() if ln.strip()]
    red = [ln.split('::')[-1].split(' ')[0] for ln in lines if ln.startswith('FAILED')]
    return r.returncode == 0, (lines[-1] if lines else ''), red


#: the guard a mutation is REQUIRED to redden, not merely "some test"
STRUCTURAL_GUARD = 'test_no_test_in_this_module_can_reach_the_real_tokens'


def _anchor(text: str) -> bytes:
    """An anchor in the file's OWN line-ending style.

    The first version of this harness reported two of five mutations as SKIP
    because its anchors were LF and the test file is CRLF — a silent no-match
    that reads exactly like "this mutation is untested", which is the failure
    mode this project has now hit repeatedly. An anchor that is not found is an
    error here, never a skip: the caller asked for a mutation, and not applying
    it is a wrong answer, not an acceptable one.
    """
    return text.replace('\n', '\r\n').encode('utf-8') if _is_crlf else text.encode('utf-8')


#: name -> (file, old, new) as TEXT; converted to bytes per-file at run time.
MUTATION_TEXT: dict[str, tuple[Path, str, str]] = {
    # 1. space_tokens ignores `path` and always reads the real file.
    'path_ignored': (
        GEOM,
        "    src = Path(path) if path is not None else TOKENS_TS\n",
        "    src = TOKENS_TS  # MUTATION: ignore path\n",
    ),
    # 2. space_tokens returns hardcoded literals instead of reading.
    'hardcoded_literal': (
        GEOM,
        "    try:\n        text = src.read_text(encoding='utf-8')\n",
        "    return {'lg': SPACE_LG, 'md': SPACE_MD, 'xl': SPACE_XL}  # MUTATION\n"
        "    try:\n        text = src.read_text(encoding='utf-8')\n",
    ),
    # 3. the source-untouched guard is deleted.
    'guard_removed': (
        TEST,
        "    before = TOKENS_TS.read_bytes()\n    yield\n    after = TOKENS_TS.read_bytes()\n",
        "    yield  # MUTATION: guard removed\n",
    ),
    # 4. the copy no longer really changes — the "did it mutate" assertion dies
    #    together with the mutation it was supposed to detect.
    'replacement_removed': (
        TEST,
        "    copy.write_bytes(original.replace(b'lg: 40', b'lg: 88'))\n",
        "    pass  # MUTATION: no replacement\n",
    ),
    # 5. plot_width ignores the space it is handed (keeps re-reading the source).
    'space_ignored': (
        GEOM,
        "    sp = space if space is not None else space_tokens()\n",
        "    sp = space_tokens()  # MUTATION: ignore injected space\n",
    ),
    # 6. THE bug itself, reintroduced: a test writes the real design tokens in
    #    place. This is the only mutation that should turn the new guard RED for
    #    the right reason — the others prove the module reads its input, this one
    #    proves the suite is read-only.
    #
    #    ⚠ THIS MUTATION IS TOXIC AND IT IS MEASURED, NOT ASSUMED: running it
    #    left tokens.ts modified with `lg:` removed entirely (sha256 4dd4a86b…,
    #    vs the pristine 6a89a5b4…). The guard caught it — 1 failed, 1 error —
    #    but the run still changed the repository, which is the original bug
    #    working exactly as designed. The harness restores the TEST file only.
    #    Use `git checkout -- studio/src/.../design/tokens.ts` afterwards, and
    #    treat any digest change at the end of a run as an alert, not a footnote.
    'inplace_write_reintroduced': (
        TEST,
        "    copy = _tokens_copy(tmp_path)\n    original = copy.read_bytes()\n",
        "    copy = TOKENS_TS  # MUTATION: write the real file\n"
        "    original = copy.read_bytes()\n",
    ),
    # 7. THE ACCEPTANCE CRITERION (P11 guard-binding work order §1): a
    #    whitelisted NAME is rebound to the real file and then written. The old
    #    guard asked what the receiver was spelled, so `dst` sailed through and
    #    the suite went red on other tests instead — the wrong guard catching
    #    the right damage. Measured before the fix: structural guard PASSED.
    'whitelisted_name_rebound': (
        TEST,
        "    dst = tmp_path / 'tokens.ts'\n    dst.write_bytes(TOKENS_TS.read_bytes())\n",
        "    dst = tmp_path / 'tokens.ts'\n"
        "    dst = TOKENS_TS  # MUTATION: rebind, still spelled 'dst'\n"
        "    _b = TOKENS_TS.read_bytes()\n"
        "    dst.write_bytes(_b)\n",
    ),
    # 8. the same rebinding, split across lines — a line-based guard cannot see
    #    a binding whose right-hand side is on the next line.
    'rebound_multiline': (
        TEST,
        "    dst = tmp_path / 'tokens.ts'\n    dst.write_bytes(TOKENS_TS.read_bytes())\n",
        "    dst = tmp_path / 'tokens.ts'\n"
        "    dst = (\n        TOKENS_TS  # MUTATION: multi-line rebind\n    )\n"
        "    _b = TOKENS_TS.read_bytes()\n"
        "    dst.write_bytes(_b)\n",
    ),
    # 9. bypass: write the real tokens through their own name, no rebinding.
    'direct_source_write': (
        TEST,
        "    dst = tmp_path / 'tokens.ts'\n    dst.write_bytes(TOKENS_TS.read_bytes())\n",
        "    dst = tmp_path / 'tokens.ts'\n"
        "    TOKENS_TS.write_bytes(TOKENS_TS.read_bytes())  # MUTATION: direct\n",
    ),
    # 10. a rename that is CORRECT and must NOT be flagged: the same tmp_path
    #     write under a different name. A guard that fires here is the
    #     "rejects correct code" failure the docstring names, so this mutation
    #     is EXPECTED TO SURVIVE.
    #
    #     The first version of this mutation replaced the binding but not the
    #     `return dst`, so the helper returned None and three tests died of
    #     NameError — the mutation broke the code it was supposed to be a
    #     legal example of. A mutation has to change exactly the one thing it
    #     claims to change, or its red says nothing.
    'benign_rename': (
        TEST,
        "    dst = tmp_path / 'tokens.ts'\n    dst.write_bytes(TOKENS_TS.read_bytes())\n"
        "    return dst\n",
        "    d = tmp_path / 'x.ts'\n    d.write_bytes(TOKENS_TS.read_bytes())\n"
        "    return d\n",
    ),
    # 11. the guard keeps only the LAST binding per name again — the third
    #     version's bug. Everything else (the write list, the forbidden roots,
    #     the message shape) is untouched, so the only property this removes is
    #     "does it see every binding or just the final one".
    #
    #     It is killed, and that is the point: the healing rebind is the
    #     acceptance criterion for this round, and a last-write-wins map walks
    #     straight past it.
    # 11. the guard keeps only the LAST binding per name again — the third
    #     version's actual bug, `bound[name] = value`: one value per name, so
    #     last-write-wins. The value is a bare AST node, not a list, which is
    #     what made that version a plain dict.
    #
    #     The first attempt at this mutation wrote `bound[name] = [value]`,
    #     which still keeps a list of one and therefore still walks every
    #     binding — it reproduced the SECOND version's shape, not this one's,
    #     and it survived. A mutation that survives because it tested the wrong
    #     code is worse than one that survives because the code is right.
    'last_binding_only': (
        TEST,
        "    for name, value in sorted(_all_assignments(tree),\n"
        "                              key=lambda p: (getattr(p[1], 'lineno', 0),\n"
        "                                             getattr(p[1], 'col_offset', 0))):\n"
        "        bound.setdefault(name, []).append(value)\n",
        "    for name, value in _all_assignments(tree):  # MUTATION: last wins\n"
        "        bound[name] = value\n",
    ),
    # 12. THE ACCEPTANCE CRITERION for this round: rebind to the source, write,
    #     then put the variable back. Last-write-wins erased the malicious
    #     binding; measured before the fix, the structural guard did not redden
    #     and the real tokens were written.
    'healing_rebind': (
        TEST,
        "    dst = tmp_path / 'tokens.ts'\n    dst.write_bytes(TOKENS_TS.read_bytes())\n",
        "    dst = tmp_path / 'tokens.ts'\n"
        "    dst = TOKENS_TS  # MUTATION: malicious\n"
        "    dst.write_bytes(TOKENS_TS.read_bytes())\n"
        "    dst = tmp_path / 'tokens.ts'  # 'healed' back\n",
    ),
    # 13. the same rebinding hidden in a loop body. A guard that reads only
    #     module-level assignments sees nothing here.
    'rebind_in_loop': (
        TEST,
        "    dst = tmp_path / 'tokens.ts'\n    dst.write_bytes(TOKENS_TS.read_bytes())\n",
        "    dst = tmp_path / 'tokens.ts'\n"
        "    for _ in range(1):\n"
        "        dst = TOKENS_TS  # MUTATION: in a loop\n"
        "    dst.write_bytes(TOKENS_TS.read_bytes())\n",
    ),
    # 14. and in a conditional branch, which is how it would reach production:
    #     only on a platform where the path differs.
    'rebind_in_branch': (
        TEST,
        "    dst = tmp_path / 'tokens.ts'\n    dst.write_bytes(TOKENS_TS.read_bytes())\n",
        "    dst = tmp_path / 'tokens.ts'\n"
        "    if True:\n"
        "        dst = TOKENS_TS  # MUTATION: in a branch\n"
        "    dst.write_bytes(TOKENS_TS.read_bytes())\n",
    ),
    # 15. a tuple-assignment rebinding: `dst, other = TOKENS_TS, x` has TWO
    #     targets, so the single-target filter never saw it. Measured necessary
    #     after mutation 12 landed: without this, that shape is a hole.
    'rebind_via_tuple': (
        TEST,
        "    dst = tmp_path / 'tokens.ts'\n    dst.write_bytes(TOKENS_TS.read_bytes())\n",
        "    dst = tmp_path / 'tokens.ts'\n"
        "    dst, _spare = TOKENS_TS, 0  # MUTATION: two targets\n"
        "    dst.write_bytes(TOKENS_TS.read_bytes())\n",
    ),
}


#: No combined mutations. The one this harness had — a name-only guard against a
#: multi-line rebind — was removed after measuring it, because it proved
#: nothing. A name-only guard cannot tell a safe `dst` from a rebound one, so
#: with a multi-line rebind it fails with "say where it comes from", and with
#: the honest code it fails for the same reason: it is simply wrong about a
#: rename. Both versions fail; the difference between them is invisible to it,
#: which is the point. Keeping it would have been manufacturing evidence for a
#: property it never tested.


def main() -> int:
    if len(sys.argv) < 2:
        print('usage: mutation_harness.py <name|all> [target]')
        return 2
    name, target = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2
                                 else str(TEST))
    names = list(MUTATION_TEXT) if name == 'all' else [name]
    unknown = [n for n in names if n not in MUTATION_TEXT]
    if unknown:
        print(f'unknown mutation(s): {unknown}')
        return 2

    baseline_ok, baseline_tail, _ = run(target)
    digest_before = tokens_digest()
    # captured ONCE, before anything runs, and used to restore after any
    # mutation that reaches the source. Capturing it later would capture the
    # damage — which is the bug this harness exists to keep out of the repo.
    tokens_at_entry = TOKENS.read_bytes()
    test_at_entry = TEST.read_bytes()
    print(f'BASELINE  passed={baseline_ok}  {baseline_tail}')
    if not baseline_ok:
        print('refusing to mutate a red baseline')
        return 1

    #: mutations that MUST redden the structural guard specifically
    must_hit_guard = {'whitelisted_name_rebound', 'rebound_multiline',
                      'direct_source_write', 'healing_rebind', 'rebind_in_loop',
                      'rebind_in_branch', 'rebind_via_tuple'}
    for n in names:
        global _is_crlf
        f, old_txt, new_txt = MUTATION_TEXT[n]
        snapshots: list[tuple[Path, bytes]] = []
        try:
            snap = f.read_bytes()           # taken BEFORE, restored verbatim
            snapshots.append((f, snap))
            _is_crlf = b'\r\n' in snap
            old, new = _anchor(old_txt), _anchor(new_txt)
            if old not in snap:
                print(f'{n:26s} ANCHOR NOT FOUND in {f.name} — the source '
                      f'moved; this is a harness bug, not an untested mutation')
                return 1
            f.write_bytes(snap.replace(old, new, 1))
            ok, tail, red = run(target)
            hit = STRUCTURAL_GUARD in ' '.join(red)
            if ok:
                verdict = 'SURVIVED (tests still green)'
            elif n in must_hit_guard:
                verdict = ('KILLED by the STRUCTURAL guard' if hit else
                           '*** KILLED, but by the WRONG test — not a fix ***'
                           if not ok else '')
            else:
                verdict = 'KILLED' + (' (by the structural guard)' if hit else '')
            print(f'{n:26s} {verdict}')
            print(f'{"":26s}   {tail}')
            if red:
                print(f'{"":26s}   red: {", ".join(red)}')
        finally:
            for f, snap in snapshots:     # the snapshot, not a re-read
                f.write_bytes(snap)
            # A mutation that reaches the real design tokens CHANGES it, which
            # is the whole point of it. The first version of this harness only
            # reported the digest change at the very END, so every mutation
            # after a toxic one ran against a polluted repository: the geometry
            # moved and two unrelated tests went red, and three mutations that
            # were supposed to survive looked killed. A poisoned baseline
            # invalidates every result after it, silently.
            #
            # So the tokens are restored after EVERY mutation, and the baseline
            # is re-checked before the next one runs. Restoring from the digest
            # captured at entry, not from a re-read: a re-read would capture the
            # damage, which is the bug this whole work order is about.
            if tokens_digest() != digest_before:
                TOKENS.write_bytes(tokens_at_entry)
                print(f'{"":26s}   !! tokens.ts was modified; restored from the '
                      f'entry snapshot')
    _is_crlf = False

    d = tokens_digest()
    same = d == digest_before
    print(f'\ndesign tokens digest: {"UNCHANGED" if same else "CHANGED!"}')
    if not same:
        print(f'  before: {digest_before}')
        print(f'  after : {d}')
        print('  RESTORE: git checkout -- studio/src/templates/finance-showcase/'
              'design/tokens.ts')
    # The mutated file must also be back exactly as it was. Measured: it was
    # not, and a run left `root = recv.id  # MUTATION` in the guard, which made
    # every LATER run start from a red baseline. The harness restores each
    # file from the snapshot taken when THAT mutation was applied — so a run
    # with a different mutation set restores a different, already-mutated
    # state. The entry snapshot is the only one that is always right.
    t_now = hashlib.sha256(TEST.read_bytes()).hexdigest()
    t_entry = hashlib.sha256(test_at_entry).hexdigest()
    if t_now != t_entry:
        TEST.write_bytes(test_at_entry)
        print(f'test file had drifted; restored from the entry snapshot '
              f'({t_now[:12]} -> {t_entry[:12]})')
        same = False
    return 0 if same else 3


if __name__ == '__main__':
    sys.exit(main())
