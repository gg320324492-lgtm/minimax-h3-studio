"""A file path named in a source comment must be a file you can actually open.

THE FAILURE THIS EXISTS FOR. Eight scene files carried this line, verbatim and
byte-identical, directly above their `design/tokens` import:

    // Fonts and scaling are NOT theme-scoped, so importing them is correct.
    // Everything that IS theme-scoped (palette, type, spacing, shadow) must come
    // from useDesign() — see tests/test_design_system.py  <- never existed

The trailing note is mine and the original ended at `...py.`; it is here so the
guard scans this file too and does not special-case its own quotations. The
quotation is otherwise exact so it can be diffed against the eight files.

That path was never on disk and appears nowhere in `git log --all`. It was an
instruction to go read a guard that did not exist, pointing at the one rule in
this repository most worth enforcing — and eight copies of it, so changing one
file would have made seven look wrong. Nothing failed for as long as it stood,
because no test ever opened the path.

WHAT IS CHECKED, AND WHY IT IS NOT `assert 'x.py' in src`.

The obvious cheap version asserts the string appears in the file, which is a
statement about TEXT and not about the FILESYSTEM: it stays green when the file
is renamed, moved, or deleted, which is the entire failure. So every citation
here is resolved to a `Path` and `Path.exists()` is called on it. A comment that
points nowhere is red whether or not the pointing is well-formatted.

DOCSTRINGS ARE READ, AND THAT IS NOT A DETAIL.

P33's `comment_blocks` reads Python through `tokenize`, which yields COMMENT
tokens — and a module docstring is a STRING token, not a COMMENT. Measured over
this tree: 127 citation sites live in docstrings and 96 of them are invisible to
a comments-only reader. The two defects this work order was written for are both
in docstrings (`locked_fields.py`'s module docstring claimed `content` was at
`showcase-v1.ts:100`; `locked_fields_brand_mutation.py`'s Usage line pointed at a
script that never existed). A guard that read only `#` comments would have
reported this file's own subject matter as clean.

HOW "CURRENT REFERENCE" IS TOLD FROM "HISTORICAL STATEMENT".

The requirement is that a legitimate historical note — "this test used to live in
`tests/old.py`, which has since been deleted" — must not be red. The criterion
here is NOT tense, hedging words, or any NLP: those are unmeasurable and this
project has been burned by confident prose that reads exactly like a live
reference. It is two mechanical facts:

  1. GIT. `git log --all -- <path>` non-empty means the path existed at some
     point in this repository's history. A path that was real and was later
     deleted is a historical reference, and a comment may say so.
  2. MARKERS. A small closed vocabulary — `no longer`, `used to`, `deleted`,
     `renamed to`, `was`, `historically`, `gone` — inside the SAME comment block
     as the citation.

Either one exempts a missing path. A path missing from disk with NEITHER is a
phantom: it never existed and nothing says it was supposed to. That is the B1
shape exactly, and it is red.

This is honestly partial, and the partiality is deliberate. Git-history absence
is not proof of never-having-existed for a path that was never committed (an
untracked scratch file someone deleted), and marker matching will false-negative
on a historical note phrased in a way the vocabulary misses. Both directions
err toward RED, because the cost asymmetry is not symmetric: a false positive is
one exemption line in `_EXEMPT`, while a false negative is a comment that sends
a reader to a file that is not there and reads as an assertion while doing it.
The exemption list is therefore kept as short as the tree allows and each entry
says which of the two facts it is relying on.

WHAT IS DELIBERATELY NOT HERE.

Changelog prose, P-numbers, and dates are not citations and are not parsed.
Nor is this a general "comments must be true" guard: `test_brand_lock_comment_
honesty.py` owns the narrower claim-vs-constant property, and this file does not
duplicate it. Line-number citations are handled separately below.
"""
from __future__ import annotations

import ast
import io
import re
import subprocess
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Directories whose source comments are held to this rule. `out/**` is a render
#: artefact tree and `studio/public/jobs/**` is gitignored staging, so neither is
#: source anyone maintains.
SOURCE_DIRS = ('studio/src', 'studio/scripts', 'pipeline', 'tests')

#: Extension alternation, LONGEST FIRST. Written as `js|json` this silently
#: matches `foo.js` out of `foo.json` and every `.json` citation silently stops
#: being checked — Python's `re` is first-alternative-wins, unlike POSIX grep,
#: which is longest-match. That bug was in the first draft of this file and it
#: removed 6 of the 8 genuinely-missing citations from the report.
_EXTS = r'(?:tsx|json|mjs|py|ts|js|md|css|sh)'

#: The same extensions as a set, for the sentence splitter, which has to tell
#: `foo.py.` (a filename, sentence continues) from `see it.` (a full stop).
#: Matched anchored AT the dot so the differing widths cannot mis-slice.
_EXT_AT_DOT = re.compile(r'\.(?:tsx|json|mjs|py|ts|js|md|css|sh)(?![\w])')

#: A repo-rooted path with a known extension. The root prefix is required so
#: that prose like "see the schema" or a bare `values` never becomes a claim.
_PATH_RE = re.compile(r'\b((?:tests|studio|pipeline|docs|tools)/[A-Za-z0-9_./-]*\.'
                      + _EXTS + r')\b')

#: A pytest node id: a path, `::`, then a test name. Resolving these proves the
#: FUNCTION exists, not merely the file — the B1 replacement cites one, and a
#: citation that survives its target's rename is the same failure one level up.
_NODE_RE = re.compile(r'\b((?:tests|studio|pipeline|docs|tools)/[A-Za-z0-9_./-]*\.py)'
                      r'::([A-Za-z_][A-Za-z0-9_]*)')

#: Bare basename references (`Brand.tsx`, `render.mjs`) — real citation form,
#: used heavily by `locked_fields.py`. Resolved by basename search, so a rename
#: that leaves the comment behind is caught the same way a moved path is.
#: `Three.js` is excluded explicitly: it is a library, not a file in this tree.
_BARE_RE = re.compile(r'(?<![\w/.-])([A-Z][A-Za-z0-9_]*\.tsx|render\.mjs)\b')

#: Closed vocabulary marking a citation as NOT a live pointer. Checked against
#: the SENTENCE carrying the citation, not the whole comment block.
#:
#: Two families, and the second matters as much as the first. "Used to" and
#: "deleted" mark a path that WAS real. "Never existed" and "does not exist"
#: mark a path a comment is asserting is absent — the negative-assertion case,
#: which is how `test_p16_reference_is_not_an_input_free_measurement.py` talks
#: about `docs/reference_analysis.json`, which does not exist on purpose. Both
#: are statements ABOUT
#: non-existence, so neither is a pointer a reader can follow, and neither
#: should be red. A marker must not merely appear somewhere in the file: the
#: sentence is the unit, because this file's own docstring quotes a phantom path
#: while separately explaining that phantom paths are the failure — under a
#: whole-block rule the guard exempted itself.
_HISTORICAL_MARKERS = (
    # was real, is not any more
    'no longer', 'used to', 'deleted', 'renamed to', 'renamed from',
    'historically', 'was removed', 'has gone', 'formerly',
    # was never real / is asserted absent
    'never existed', 'never on disk', 'does not exist', 'no such file',
)

#: Missing paths that are legitimate, each with the fact that exempts it.
#: Kept short on purpose; every entry is a place a future false positive can be
#: paid for in one line instead of by loosening the rule.
#:
#: - `studio/public/jobs/x/props.json` — no such file; "x" is a placeholder
#:   directory in a CLI Usage example, never a path anyone can open.
_EXEMPT: dict[str, str] = {
    'studio/public/jobs/x/props.json':
        'Usage example in visual_qa.py\'s docstring; "x" is a placeholder '
        'directory, not a path anyone can open.',
}


# ── reading source, comments AND docstrings ─────────────────────────────────

def comment_texts(src: str, suffix: str) -> list[str]:
    """Every comment and every docstring in one source file, as plain strings.

    Python is read twice on purpose: `tokenize` for `#` comments (a `#` inside a
    string literal is not a comment, and a regex cannot tell) and `ast` for
    docstrings (which are STRING tokens, so `tokenize` alone never yields them).
    A parse failure returns what was collected rather than raising, because a
    file that fails to parse is a different test's problem, not this one's — but
    it is never silently treated as "no citations found".
    """
    if suffix == '.py':
        out: list[str] = []
        try:
            for tok in tokenize.generate_tokens(io.StringIO(src).readline):
                if tok.type == tokenize.COMMENT:
                    out.append(tok.string)
        except (tokenize.TokenError, IndentationError, SyntaxError):
            pass
        try:
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, (ast.Module, ast.FunctionDef,
                                     ast.AsyncFunctionDef, ast.ClassDef)):
                    doc = ast.get_docstring(node, clean=False)
                    if doc:
                        out.append(doc)
        except SyntaxError:
            pass
        return out

    out = []
    for line in src.splitlines():
        s = line.strip()
        if s.startswith('//'):
            out.append(s[2:])
    for m in re.finditer(r'/\*.*?\*/', src, re.S):
        block = m.group(0).splitlines()
        body = block[1:-1] if block and block[0].lstrip().startswith('/*') else block
        out.append(' '.join(l.strip().lstrip('*').strip() for l in body))
    return out


def source_files() -> list[Path]:
    files: list[Path] = []
    for d in SOURCE_DIRS:
        files.extend(sorted(p for p in (ROOT / d).rglob('*')
                            if p.is_file() and p.suffix in
                            ('.py', '.ts', '.tsx', '.mjs', '.js')))
    return files


def citations_in(text: str) -> list[tuple[str, str, str]]:
    """(kind, reference, carrier_line) for every citation in ONE comment.

    Takes comment text, not source: extraction happens once, in `unresolved`.
    The first draft passed already-extracted comment text back through
    `comment_texts`, which stripped nothing and found nothing — and the guard
    reported the tree as clean while its own negative-control test failed. A
    guard that cannot see its own fixtures is worse than no guard.

    The carrier line is the sentence the citation actually sits in, and it is
    what the historical-marker test reads. The first draft tested markers
    against the WHOLE comment block, which is far too generous: this file's own
    module docstring cites `tests/test_design_system.py`, which never existed,
    while separately explaining that such a path is a phantom, and it exempted
    itself. A marker 2000 characters away in the same block says nothing about
    this citation. The phrase must not straddle a line break: the carrier ends
    at the newline, so `never` alone marks nothing.
    """
    out: list[tuple[str, str, str]] = []

    def carrier(pos: int) -> str:
        """The sentence around `pos`: bounded by `;`/newline, and by a `.` that
        is NOT part of a filename or an initial.

        The first version split on any `.`, which truncated every carrier at
        `tests/test_design_system` — the sentence it was supposed to judge. The
        guard then reported four of its own quotations as unmarked. A splitter
        that cuts inside the thing it is examining cannot judge it.
        """
        start = max(text.rfind(c, 0, pos) for c in ';\n') + 1
        end = len(text)
        for i in range(pos, len(text)):
            ch = text[i]
            if ch in ';\n':
                end = i
                break
            if ch != '.':
                continue
            # A `.` ends a sentence only when what follows starts a new one:
            # not a digit (3.12, v1.2), not a word char (foo.py), not a lone
            # capital initial (J. Doe).
            nxt = text[i + 1:i + 2]
            if nxt.isdigit():
                continue
            # `foo.py.` — a known extension is part of a FILENAME, not a full
            # stop. Without this the sentence ends AT the citation and whatever
            # the author wrote after it is never read, so the marker test
            # judges a fragment. Anchored regex, not manual slicing:
            # extensions differ in width (`py` is 2, `json` is 4) and an
            # off-by-one silently blinds the test to the sentence it reads.
            if _EXT_AT_DOT.match(text, i):
                continue
            if i + 2 < len(text) and nxt.isupper() and text[i + 2] == ' ':
                continue
            if i + 2 < len(text) and nxt.isalpha() and text[i + 2].islower():
                continue
            end = i
            break
        return text[start:end]

    for m in _NODE_RE.finditer(text):
        out.append(('node', f'{m.group(1)}::{m.group(2)}', carrier(m.start())))
    for m in _PATH_RE.finditer(text):
        out.append(('path', m.group(1), carrier(m.start())))
    for m in _BARE_RE.finditer(text):
        out.append(('bare', m.group(1), carrier(m.start())))
    return out


def _basename_index() -> dict[str, list[Path]]:
    idx: dict[str, list[Path]] = {}
    for d in ('studio', 'pipeline', 'tests', 'docs'):
        for p in (ROOT / d).rglob('*'):
            if p.is_file() and 'node_modules' not in p.parts:
                idx.setdefault(p.name, []).append(p)
    return idx


def _in_git_history(rel: str) -> bool:
    """Did this path ever exist in this repository's history?

    Cached per path for the run: this shells out to git, and a full sweep makes
    a few hundred calls. A missing git binary is answered False, which fails
    toward red — the conservative direction, and stated rather than assumed.
    """
    r = subprocess.run(['git', 'log', '--all', '--oneline', '--', rel],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    if r.returncode != 0:
        return False
    return bool(r.stdout.strip())


def _test_names_in(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except (OSError, SyntaxError):
        return set()
    return {n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


# ── the criterion ───────────────────────────────────────────────────────────

def unresolved(src: str, suffix: str, basename_idx: dict[str, list[Path]],
               history: dict[str, bool]) -> list[str]:
    """Every citation in one file that does not land on something real.

    THE CRITERION. Three resolution rules, in order:

      node  -> the file must exist AND define the named function.
      path  -> the file must exist, or be exempt (see `_EXEMPT` / git history).
      bare  -> exactly one file in the tree must carry that basename.

    A citation whose block carries a historical marker is skipped before any of
    that, because "this used to be at tests/old.py" is a true statement about a
    file that is gone and must not be red.
    """
    problems: list[str] = []
    for text in comment_texts(src, suffix):
        for kind, ref, carrier in citations_in(text):
            # Historical markers must sit in the SENTENCE holding the citation.
            if any(marker in carrier.lower() for marker in _HISTORICAL_MARKERS):
                continue
            if kind == 'node':
                path_s, _, func = ref.partition('::')
                target = ROOT / path_s
                if not target.exists():
                    problems.append(f'{ref} — the file does not exist')
                elif func not in _test_names_in(target):
                    problems.append(
                        f'{ref} — {path_s} exists but defines no function '
                        f'{func!r}; the test this comment points at was renamed '
                        f'or removed')
            elif kind == 'path':
                # An elided path (`studio/src/.../design/tokens.ts`) names no
                # single file and is a deliberate abbreviation, not a broken
                # reference. Requiring it to resolve would be a false positive
                # on correct prose. It is skipped, not exempted.
                if '...' in ref:
                    continue
                if (ROOT / ref).exists():
                    continue
                if ref in _EXEMPT:
                    continue
                if ref not in history:
                    history[ref] = _in_git_history(ref)
                if history[ref]:
                    continue
                problems.append(
                    f'{ref} — not on disk, never in `git log --all`, and no '
                    f'historical marker in the comment. This is the shape of the '
                    f'eight `tests/test_design_system.py` citations.')
            else:  # bare
                hits = basename_idx.get(ref, [])
                if len(hits) == 1:
                    continue
                if len(hits) > 1:
                    problems.append(
                        f'{ref} — {len(hits)} files in the tree share this '
                        f'basename, so the citation does not identify one')
                else:
                    problems.append(
                        f'{ref} — no file in the tree carries this basename')
    return problems


# ── the properties ──────────────────────────────────────────────────────────

def test_every_path_cited_in_a_source_comment_is_a_file_you_can_open():
    """The B1 property, over comments AND docstrings."""
    idx = _basename_index()
    history: dict[str, bool] = {}
    bad: list[str] = []
    for p in source_files():
        rel = p.relative_to(ROOT).as_posix()
        src = p.read_text(encoding='utf-8', errors='replace')
        for problem in unresolved(src, p.suffix, idx, history):
            bad.append(f'  {rel}: {problem}')
    assert not bad, (
        'source comments cite paths that do not resolve:\n' + '\n'.join(bad)
        + '\n\nA comment that sends a reader to a file that is not there is not a '
          'note, it is an assertion that happens to be unreadable. Either point '
          'it at something real, or mark it as historical — see the module '
          'docstring for what "historical" has to mean here.')


def test_the_criterion_can_still_say_no():
    """The criterion must reject what it was written for.

    A criterion edited to always agree is green forever and protects nothing, and
    nothing else in this file would notice. The strings below are the ORIGINAL
    B1 citation and the original A6 line reference, verbatim.
    """
    idx = _basename_index()
    history: dict[str, bool] = {}

    phantom = ('// from useDesign() — see tests/test_design_system.py.\n')
    problems = unresolved(phantom, '.ts', idx, history)
    assert problems, (
        'the criterion accepted the original `tests/test_design_system.py` '
        'citation. It cannot fail, so the guard it powers cannot guard.')

    stale_node = ('// see tests/test_showcase_schema_parity.py::'
                  'test_that_was_renamed_last_week\n')
    problems = unresolved(stale_node, '.ts', idx, history)
    assert problems, (
        'the criterion accepted a node id naming a function that does not '
        'exist. A citation that survives its target being renamed is the same '
        'failure one level up.')

    assert not unresolved('// see tests/test_locked_fields.py\n', '.ts', idx, history), (
        'the criterion rejected a citation that DOES resolve. It is not '
        'discriminating, it is refusing everything.')


def test_a_historical_statement_is_not_a_violation():
    """The other direction: a legal note about a deleted file must stay green.

    Without this the guard cannot tell 'points at nothing' from 'says it is
    gone', and a maintainer hitting a red on a true historical note has to
    choose between fixing the rule or ignoring it. Ignoring it is what happens.
    """
    idx = _basename_index()
    history: dict[str, bool] = {}
    for phrase in ('no longer', 'used to', 'deleted', 'renamed to'):
        note = (f'// this test {phrase} live in tests/test_design_system.py, '
                f'which is gone.\n')
        assert not unresolved(note, '.ts', idx, history), (
            f'a comment saying a path {phrase!r} was red. That is a true '
            f'statement about a file that no longer exists and the guard must '
            f'allow it — otherwise it is a false-positive machine, and a false-'
            f'positive machine gets switched off.')


def test_the_scan_is_not_vacuous():
    """This file must be reading comments at all.

    `unresolved` returning `[]` for everything is the failure mode of every
    regex-based comment reader, and P33 hit it: a `#` regex finds no comments in
    a docstring-heavy Python file and the guard goes green for the wrong reason.
    """
    src = ('"""Docstring citing tests/test_locked_fields.py."""\n'
           '# comment citing tests/test_locked_fields.py\n')
    idx = _basename_index()
    history: dict[str, bool] = {}
    assert not unresolved(src, '.py', idx, history), (
        'fixture citations should all resolve')
    # ...and the docstring alone must be enough to prove docstrings are read.
    doc_only = '"""See tests/test_design_system.py for the rule."""\n'
    assert unresolved(doc_only, '.py', idx, history), (
        'a docstring-only citation produced no finding. Either docstrings are '
        'not being read, or the criterion cannot fail. 96 of the citation sites '
        'in this tree are in docstrings, so this is not a corner case.')


def test_deleting_a_citation_is_not_a_failure():
    """Fewer citations must stay green; only wrong ones are red.

    Stated because the work order asked for it explicitly. A guard that required
    a minimum citation count would be a guard that punishes deletion, and the
    correct response to a stale comment is to delete the citation.
    """
    idx = _basename_index()
    history: dict[str, bool] = {}
    assert not unresolved('// nothing is cited here\n', '.ts', idx, history)
    assert not unresolved('// see tests/test_locked_fields.py\n', '.ts', idx, history)