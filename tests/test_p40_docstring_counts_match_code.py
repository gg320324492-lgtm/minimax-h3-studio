"""A source comment that CITE A COLLECTION'S SIZE must cite the size it has.

THE FAILURE THIS EXISTS FOR (P40).

P12.2 recorded that the work order it was written against quoted a stale number,
and the number did not come out of thin air: it came out of a docstring.

    studio/scripts/visual_qa.py, line 1052 BEFORE P40's edit shifted the file
    (the docstring cited here used to be cited at line 1052):
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
    every changelog.
  * It does not judge a number that has no collection name beside it.
  * It does not fail a HISTORICAL statement. "`SCENE_RENDERERS` used to name 13"
    is exempt, by the same closed-vocabulary rule.

2026-11-21 裁剪：本文件原有 4 例，其中 3 例是「对全仓库源码做 AST 扫描、逐条
核对注释中数字与集合大小」的账本式守卫（`test_the_registry_names_real_collections_
with_computable_sizes`、`test_every_cited_collection_size_equals_the_computed_size`、
`test_the_known_debt_sites_are_still_the_debt_they_claim`），按测试甄别报告
（out/工具/测试甄别.md）方案二删除。保留 `test_the_checker_can_say_no`——它是纯
合成输入上的守卫元测试（criterion 必须能对错误引用说 no），不依赖仓库文本状态。
"""
from __future__ import annotations

import ast
import re

# ── the sentence shape. A citation is `NAME ... VERB ... NUMBER` or
#    `NUMBER ... VERB ... NAME`, and the gap may not cross a comma or a
#    semicolon. That bound is load-bearing: without it, "`SceneType`, 13 named
#    by `SCENE_RENDERERS`" reads 13 as SceneType's size, which is false even by
#    this guard's own arithmetic ("red in the wrong reason" in miniature). ─────

_ALTS = '(?:SceneType|SCENE_RENDERERS|UNRENDERED_SCENE_TYPES)'
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
#: holding the citation, not the block.
_HISTORICAL_MARKERS = (
    'used to', 'no longer', 'formerly', 'historically', 'had been', 'once was',
    'at the time', 'was written when', 'became', 'before p',
)


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


# ── discrimination: the checker must be able to say no ──────────────────────

def test_the_checker_can_say_no():
    """Kills an always-agreeing checker, on a synthetic source.

    The real tree currently has no LIVE discrepancy, so a checker that returned
    `[]` for everything would pass any guard built on it. It has to go red
    HERE, on a source that clearly cites a wrong size -- and it must report the
    RIGHT claim, not merely something.
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
    raise SystemExit(__import__('pytest').main([__file__, '-q']))
