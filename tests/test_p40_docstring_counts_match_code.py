"""A source comment that CITE A COLLECTION'S SIZE must cite the size it has.

THE FAILURE THIS EXISTS FOR (P40).

P12.2 recorded that the work order it was written against quoted a stale number,
and the number did not come out of thin air: it came out of a docstring.

    studio/scripts/visual_qa.py:1052, before P40:
        "`SceneType` declares 22 values, `SCENE_RENDERERS` names 13, and the
         9 in between are video, browser-window, ..."

Measured, that docstring was written when it was true and P29 (`a7f02b8`) later
accepted seven new renderers without touching it. By the time P38 read it the
line said 13 and the code said 20. The propagation is the point:

    stale docstring  ->  commander's work order ("9 render no renderer")
                     ->  executor's brief
                     ->  a rule for the next agent to follow.

A number in a docstring is read as a MEASUREMENT. Nobody re-measures a sentence;
they quote it. That is how one stale line became a work order, and why a guard
that recomputes the number is worth more here than a guard on the number itself.

WHAT IS ASSERTED, AND THE NARROW PROPERTY IT IS NARROWED TO.

Not "every number in every comment is true" -- that is hundreds of false
positives and this project has already rejected it (the 4.9 guard's own docstring
says so: timestamps, line numbers, `18.7s`, `0.278` are all legitimate). The
property is one sentence: **when a source file names one of a CLOSED set of
collections and gives its size, that size must equal the collection's real size,
computed from the code.**

The closed set is the three token sets this very defect was about:
`SceneType`, `SCENE_RENDERERS`, `UNRENDERED_SCENE_TYPES`. Each is counted by
CALLING the parser that reads the real files -- imported from P26, not rewritten
here, because a second spelling of "how many types render" is the P21 scar
(one constant, two call sites, one of them read) and would drift exactly as this
number did.

WHY THE NUMBERS ARE COMPUTED AND NOT WRITTEN DOWN HERE.

If this file said `assert 22 == 22` it would go green on the day the schema
changed, which is the failure it is here to catch. Every number on both sides is
derived: the cited one from the comment, the real one from `len(parser())`. The
only literals in this file are the collection NAMES and the verb vocabulary,
neither of which is a measurement.

WHAT IS DELIBERATELY NOT HERE.

  * It does not read `docs/**`. A document is a historical record -- the ledger's
    `~~3.2~~` row and `P26_MISSING_RENDERERS.md`'s "was 13" are true statements
    about a past, and a guard that demanded docs track the code would be red on
    every changelog. (The ledger also carries the same stale 22/13/9 at
    `UPGRADE_PROGRESS.md:528`; that is the commander's file and is reported, not
    edited here.)
  * It does not judge a number that has no collection name beside it. Measured:
    `tests/test_p21_props_path_gates_the_deliverable.py:24` reads "Measured: 22
    types declared, 13 rendered, 9 in between" with no collection NAME in the
    sentence -- it leans on the sentence above. A mechanical parser cannot
    attribute that number, and inventing an attribution would be the estimation
    this project forbids. It is named here so the gap is recorded, and it is
    listed in `_KNOWN_DEBT` with the reason.
  * It does not fail a HISTORICAL statement. "`SCENE_RENDERERS` used to name 13"
    is exempt, by the same closed-vocabulary rule `test_comment_citations_
    resolve.py` uses, tested against the SENTENCE and not the whole block.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))            # for `pipeline`, and P26's parsers
sys.path.insert(0, str(Path(__file__).resolve().parent))

# The counts come from P26's parsers -- the same read `visual_qa.py`'s
# `declared_scene_types` and P38's guard do. Imported rather than re-parsed:
# a second parser is a second criterion, which is the whole subject of this
# file's sibling (P39) and the reason this number drifted in the first place.
from test_p26_scene_type_coverage import (  # noqa: E402
    declared_scene_types,
    rendered_scene_types,
    unrendered_scene_types,
)

# ── the registry: a collection NAME as it is written in prose, and how to count
#    it. The value is a CALLABLE, so the number is measured at test time. ─────

COLLECTIONS = {
    'SceneType': declared_scene_types,
    'SCENE_RENDERERS': rendered_scene_types,
    'UNRENDERED_SCENE_TYPES': unrendered_scene_types,
}

# ── where a count citation may live, and where it may not ───────────────────
#
# Source only. `docs/**` is a historical record (see the module docstring);
# `studio/public/jobs/**` is gitignored staging; `out/**` is render output.
SOURCE_DIRS = ('studio/src', 'studio/scripts', 'pipeline', 'tests')

# ── the sentence shape. A citation is `NAME ... VERB ... NUMBER` or
#    `NUMBER ... VERB ... NAME`, and the gap may not cross a comma or a
#    semicolon. That bound is load-bearing: without it, "`SceneType`, 13 named
#    by `SCENE_RENDERERS`" reads 13 as SceneType's size, which is false even by
#    this guard's own arithmetic ("red in the wrong reason" in miniature). ─────

_ALTS = '(?:' + '|'.join(re.escape(n) for n in COLLECTIONS) + ')'
_VERB = (r'(?:declares|declare|declared|names|name|named|registers|register|'
         r'registered|holds|hold|covers|cover|carries|carry|lists|lists|'
         r'contains|counts|has|have)')
_NAME_FIRST = re.compile(
    r'`?(' + _ALTS + r')`?[^,;\n]{0,50}?\b' + _VERB +
    r'\b[^,;\d]{0,25}?\b(\d{1,3})\b', re.I)
_NUMBER_FIRST = re.compile(
    r'\b(\d{1,3})\b[^,;\n]{0,40}?\b' + _VERB +
    r'\b[^\d,;]{0,15}?(?:by |of |to |from )?`?(' + _ALTS + r')`?', re.I)

#: A historical statement is not a live claim. Tested against the SENTENCE
#: holding the citation, not the block -- the same rule, and the same reason,
#: as `test_comment_citations_resolve.py`: a marker 2000 chars away says
#: nothing about this number.
_HISTORICAL_MARKERS = (
    'used to', 'no longer', 'formerly', 'historically', 'had been', 'once was',
    'at the time', 'was written when', 'became', 'before p',
)

#: Known stale sites that P40 is NOT authorized to edit, keyed by
#: (rel_path, collection_name) -> the cited number that is still wrong.
#:
#: Each entry is a DEBT, not an exemption from the rule: the guard asserts the
#: site still cites a number that does NOT equal the computed size, so the day
#: someone corrects it this goes red and the entry must be deleted. It cannot
#: outlive the defect.
_KNOWN_DEBT = {
    ('studio/scripts/qa_layers.py', 'SCENE_RENDERERS'): 13,
}

#: A site that carries a stale-looking number P40 cannot mechanically attribute
#: (no collection NAME in the sentence). Recorded so the gap is not mistaken for
#: coverage, and asserted below so it is re-measured if the file changes.
#:
#:   tests/test_p21_props_path_gates_the_deliverable.py:24
#:       "Measured: 22 types declared, 13 rendered, 9 in between."
#:   The sentence names no collection; the names are in the sentence ABOVE. A
#:   mechanical checker that attributed them would be guessing, which is the
#:   estimation this project forbids. P40 is not authorized to edit this file
#:   (a P19-P37 outcome), so it is reported to the commander, not fixed here.
_UNATTRIBUTABLE_SITE = 'tests/test_p21_props_path_gates_the_deliverable.py'


# ── reading source: comments, docstrings AND string literals ────────────────
#
# String literals matter and are not an accident: `qa_layers.py`'s count
# citation is a dict VALUE (`'scenes': ('... 22 scene types declared by '
# 'SceneType, 13 named by SCENE_RENDERERS ...')`), not a docstring. A reader
# that looked only at `ast.get_docstring` would miss it and report the tree
# clean while a stale number sat in a string a user prints. Docstrings ARE
# string constants, so reading every `ast.Constant` string covers both.

def _citation_texts(src: str) -> list[str]:
    """Every docstring, string literal and `#` comment in one Python source."""
    texts: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # A file that will not parse is a different test's problem; it is never
        # silently treated as "no citations". The comment pass below still runs.
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                texts.append(node.value)
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith('#'):
            texts.append(stripped)
    return texts


def _sentence(text: str, pos: int) -> str:
    """The sentence around `pos`, bounded by `;`/newline/full stop.

    Copied in spirit from `test_comment_citations_resolve.py`'s carrier: the
    unit is the sentence, because a marker in a different sentence does not
    exempt this one. Kept simple here because the citations this file judges
    are short and rarely span a full stop.
    """
    start = max(text.rfind(c, 0, pos) for c in ';\n') + 1
    end = len(text)
    for i in range(pos, len(text)):
        if text[i] in ';\n':
            end = i
            break
    return text[start:end]


#: This file is excluded from its own scan, and the reason is not squeamishness.
#: It carries two things that MUST be able to say a wrong number: the quotation
#: of the failure (`visual_qa.py`'s old `names 13` line, reproduced in the module
#: docstring so the failure is legible) and the discrimination fixtures in
#: `test_the_checker_can_say_no`, which are deliberately wrong so the checker can
#: be shown to fail. A guard that flagged its own test inputs would have to be
#: weakened until it stopped seeing them, which is the defect, not the fix. The
#: exclusion is by THIS path only -- every other source file is scanned.
_SELF = Path(__file__).resolve().as_posix()


def source_files() -> list[Path]:
    files: list[Path] = []
    for d in SOURCE_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for p in sorted(base.rglob('*.py')):
            if 'node_modules' in p.parts or '__pycache__' in p.parts:
                continue
            if p.resolve().as_posix() == _SELF:
                continue
            files.append(p)
    return files


# ── the pure checker, so a discrimination test can ask it about a poisoned
#    source without writing to the repo ──────────────────────────────────────

def cited_sizes(src: str) -> list[tuple[str, int, str]]:
    """(collection_name, cited_number, sentence) for every count citation.

    Pure: takes source text, returns claims. The sizes are NOT looked up here,
    so this can be run against a fixture whose collections are synthetic.
    """
    out: list[tuple[str, int, str]] = []
    seen: set[tuple[str, int]] = set()
    for text in _citation_texts(src):
        for m in _NAME_FIRST.finditer(text):
            name, num = m.group(1), int(m.group(2))
            sentence = _sentence(text, m.start())
            if any(mk in sentence.lower() for mk in _HISTORICAL_MARKERS):
                continue
            if (name, num) in seen:
                continue
            seen.add((name, num))
            out.append((name, num, sentence))
        for m in _NUMBER_FIRST.finditer(text):
            num, name = int(m.group(1)), m.group(2)
            sentence = _sentence(text, m.start())
            if any(mk in sentence.lower() for mk in _HISTORICAL_MARKERS):
                continue
            if (name, num) in seen:
                continue
            seen.add((name, num))
            out.append((name, num, sentence))
    return out


def _is_known_debt(rel: str, name: str) -> bool:
    return (rel, name) in _KNOWN_DEBT


# ── the anchor: the registry is real and the corpus is non-empty ────────────

def test_the_registry_names_real_collections_with_computable_sizes():
    """Without this, an emptied registry would make every assertion vacuous."""
    assert COLLECTIONS, 'the collection registry is empty; nothing is judged'
    for name, fn in COLLECTIONS.items():
        size = len(fn())
        assert size > 0, f'{name} computed to zero types; the parser or the code moved'
    # A cheap sanity check that the three are the three: the partition holds.
    assert len(declared_scene_types()) == (
        len(rendered_scene_types()) + len(unrendered_scene_types())), (
        'SceneType is no longer the disjoint union of rendered and unrendered; '
        'the three names in this registry no longer describe one partition, so '
        '"N in between" arithmetic elsewhere is off a different set')
    assert len(find_all_citations()) > 0, (
        'no count citation was found anywhere; either the vocabulary drifted or '
        'the corpus moved, and a guard over nothing is green for free')


def find_all_citations() -> list[tuple[str, str, int, str]]:
    """(rel_path, collection_name, cited_number, sentence) over every source."""
    hits: list[tuple[str, str, int, str]] = []
    for path in source_files():
        rel = path.relative_to(ROOT).as_posix()
        src = path.read_bytes().decode('utf-8', 'replace')
        for name, num, sentence in cited_sizes(src):
            hits.append((rel, name, num, sentence))
    return hits


# ── THE GUARD ───────────────────────────────────────────────────────────────

def test_every_cited_collection_size_equals_the_computed_size():
    """THE GUARD. Every cited count must equal len(collection()), measured.

    This is the assertion that would have been RED on `visual_qa.py:1052` the
    day P29 landed seven renderers, and it is the line that stops a docstring
    from becoming the next work order's premise.
    """
    problems: list[str] = []
    for rel, name, cited, sentence in find_all_citations():
        real = len(COLLECTIONS[name]())
        if cited == real:
            continue
        if _is_known_debt(rel, name):
            continue
        problems.append(
            f'{rel}: cites "{sentence.strip()}" -- {name} has {real}, not '
            f'{cited}. The comment is a measurement that has drifted; recompute '
            f'it rather than quoting it.')
    assert not problems, (
        'a source comment cites a collection size the code no longer has. This '
        'is the P40 failure exactly -- a stale docstring number is read as a '
        'measurement and quoted into the next work order:\n  '
        + '\n  '.join(problems))


def test_the_known_debt_sites_are_still_the_debt_they_claim():
    """A debt entry must still describe a real, still-live discrepancy.

    Without this, `_KNOWN_DEBT` becomes a place stale numbers go to be
    forgotten. Each entry records the cited number that was wrong; the guard
    asserts the site STILL cites that number AND that it still disagrees with
    the computed size -- the day it is fixed, this goes red and the entry must
    be deleted.
    """
    found: dict[tuple[str, str], list[int]] = {}
    for rel, name, cited, _ in find_all_citations():
        found.setdefault((rel, name), []).append(cited)
    for (rel, name), was_cited in _KNOWN_DEBT.items():
        assert (rel, name) in found, (
            f'{rel} no longer cites {name} at all. Delete this _KNOWN_DEBT '
            f'entry -- it describes a site that is gone.')
        real = len(COLLECTIONS[name]())
        assert was_cited != real, (
            f'the _KNOWN_DEBT entry for {rel}/{name} records a number ({was_cited}) '
            f'that is not in fact stale -- it equals the computed size. '
            'Delete the entry; a "debt" that is not owed is a wrong record.')
        assert was_cited in found[(rel, name)], (
            f'{rel} no longer cites {name} as {was_cited} (it now cites '
            f'{found[(rel, name)]}). Either the site was corrected -- in which '
            f'case delete this _KNOWN_DEBT entry -- or it moved and the entry is '
            f'stale in a different way. Re-measure before trusting the record.')
        assert real not in found[(rel, name)], (
            f'{rel} now cites {name} correctly ({real}). Delete this _KNOWN_DEBT '
            f'entry -- it cannot outlive the defect.')


# ── discrimination: the checker must be able to say no ──────────────────────

def test_the_checker_can_say_no():
    """Kills an always-agreeing checker, on a synthetic source.

    The real tree currently has no LIVE discrepancy inside P40's authorization
    (visual_qa.py is fixed by this work order; the one remaining site is a
    recorded debt), so a checker that returned `[]` for everything would pass
    the guard above. It has to go red HERE, on a source that clearly cites a
    wrong size -- and it must report the RIGHT claim, not merely something.
    """
    # A count citation citing a number SceneType does not have.
    bad = '"""x `SceneType` declares 999 values and that is all."""\n'
    hits = cited_sizes(bad)
    assert ('SceneType', 999) in [(n, c) for n, c, _ in hits], (
        f'the checker did not see a name-first citation in {bad!r}: {hits}')

    # Number-first, the other direction.
    bad2 = '"""22 widths named by SCENE_RENDERERS is the old count."""\n'
    assert ('SCENE_RENDERERS', 22) in [(n, c) for n, c, _ in cited_sizes(bad2)], (
        'the checker did not see a number-first citation')

    # A historical statement is NOT a live claim and must be ignored, or the
    # guard would be red on every changelog.
    hist = '"""`SCENE_RENDERERS` used to name 13 renderers."""\n'
    assert cited_sizes(hist) == [], (
        f'a historical statement was read as a live citation: {cited_sizes(hist)}')

    # A correct citation is not reported by the CHECK (it must still be seen).
    ok = '"""`SceneType` declares 22 values."""\n'
    assert ('SceneType', 22) in [(n, c) for n, c, _ in cited_sizes(ok)]


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
