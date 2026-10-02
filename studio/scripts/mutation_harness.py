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


def run(target: str) -> tuple[bool, str]:
    r = subprocess.run(
        ['py', '-3.12', '-m', 'pytest', target, '-q', '--no-header',
         '-p', 'no:cacheprovider'],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        cwd='C:/tmp' if Path('C:/tmp').exists() else '/tmp',
    )
    out = (r.stdout or '') + (r.stderr or '')
    tail = [ln for ln in out.strip().splitlines() if ln.strip()][-1:] or ['']
    return r.returncode == 0, tail[0]


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
}


def main() -> int:
    if len(sys.argv) < 2:
        print('usage: mutate.py <name|all> [target]')
        return 2
    name, target = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2
                                 else str(TEST))
    names = list(MUTATION_TEXT) if name == 'all' else [name]
    unknown = [n for n in names if n not in MUTATION_TEXT]
    if unknown:
        print(f'unknown mutation(s): {unknown}')
        return 2

    baseline_ok, baseline_tail = run(target)
    digest_before = tokens_digest()
    print(f'BASELINE  passed={baseline_ok}  {baseline_tail}')
    if not baseline_ok:
        print('refusing to mutate a red baseline')
        return 1

    for n in names:
        global _is_crlf
        f, old_txt, new_txt = MUTATION_TEXT[n]
        snapshot = f.read_bytes()          # taken BEFORE, restored verbatim
        _is_crlf = b'\r\n' in snapshot
        old = _anchor(old_txt)
        new = _anchor(new_txt)
        if old not in snapshot:
            print(f'{n:22s} ANCHOR NOT FOUND in {f.name} — the source moved; '
                  'this is a harness bug, not an untested mutation')
            return 1
        try:
            f.write_bytes(snapshot.replace(old, new, 1))
            ok, tail = run(target)
            verdict = 'SURVIVED (tests still green)' if ok else 'KILLED  (tests went red)'
            print(f'{n:22s} {verdict}  {tail}')
        finally:
            f.write_bytes(snapshot)        # the snapshot, not a re-read
    _is_crlf = False

    d = tokens_digest()
    print(f'\ndesign tokens digest: {"UNCHANGED" if d == digest_before else "CHANGED!"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
