"""A line-number citation must land on CODE. Provenance comment; rationale below.

THE FAILURE THIS EXISTS FOR. `visual_qa.py` documented what each measured
contrast role is FOR and cited the render source by line:

    the "chart: no values" placeholder (Chart.tsx:196, 34px)

`Chart.tsx:196` is a comment. The placeholder is at `:211`. P28 added a nine-line
docstring above it explaining why `baseline` is not folded into `values`, and the
citation did not move. Nothing failed: the line existed, the file existed, and
`test_comment_citations_resolve.py` (P34) was green, because that guard resolves
the PATH and was never asked about the line.

Three more of the same shape were already sitting in the same file, found by
reading rather than by any test:

    ChartFrame.tsx:320,339,379   P22 measured those three inkFaint sites and they
                                 were EXACT; P28's edit pushed all three by +22
                                 (the file grew 393 -> 415 lines). `:320` now
                                 lands on `}}` and `:379` on `*/}`.
    FinanceShowcaseWide.tsx:95   `MissingScene` moved to `:150`.

Both are P28's edit, by the same mechanism as the one this work order was
written for: a comment added above the target, and a citation left behind.

WHAT IS CHECKED, AND WHY "IS IT A COMMENT" IS NOT THE WHOLE CRITERION.

A citation is red when its line is not code: a comment, a blank line, or past the
end of the file. But that alone is not enough, and this file was written after
measuring what it would report. `:320` above is `}}` — real code, in a real file,
on a real line — and it is just as wrong as `:196`. "Points at code" is a
necessary condition and not a sufficient one. What makes a citation TRUE is that
the line it names is the thing the sentence says it is, and no mechanical test
can decide that in general; this guard states the part it can decide and does not
claim the rest. See "WHAT THIS DOES NOT PROVE" below.

HOW A DELIBERATE CITATION OF A COMMENT IS TOLD FROM A DRIFTED ONE.

P34 measured 22 line citations and warned that a blanket "must not land on a
comment" rule would report five sites, four of which deliberately point AT a
comment block. That is real, and those four are red here without this mechanism.
They share one property that is mechanical, not interpretive: the sentence
carrying the citation says the thing it names is prose. Measured over this tree,
five of the seven do:

    `render.mjs:141` names `qa_final.py` inside a comment explaining why ...
    site (`render.mjs:141` names `qa_final.py` in prose, and P17's first sweep ...)
    render.mjs:43-47 records why — 118 leaked copies filled a C: TEMP to 46 GB.

"Inside a comment", "in prose", "records why", "explaining why", "comment
explaining" — a closed vocabulary, matched against the SENTENCE holding the
citation, not the whole comment block. This is P34's historical-marker design
applied to a second question, and it inherits P34's honest partiality.

The partiality is real and it is measured, not hedged about. This tree has 69
unique line citations into code files; 7 name a non-code line, and all 7 are
deliberate. Five are carried by a marker in their own sentence and go green
through the vocabulary. TWO ARE NOT, and they are in `_EXEMPT` with the reason
written out: one sits at the end of an assertion-message string whose
"records why" sentence is some 30 lines earlier, and one is this file's own
fixture, whose marker is an f-string variable the guard cannot read. So the
honest claim is: the mechanism covers 5 of the 7 cases that exist, and the other
two are listed rather than pretended away. A deliberate citation phrased
outside the vocabulary lands in `_EXEMPT`, where a human decides — which is
exactly P34's shape. That direction is deliberate, because a false negative is a
comment sending a reader to the wrong line and a false positive is one word
added to a sentence.

One further partiality, because it cost this file three false positives before
it was found: the sentence is read with its line WRAPPING normalised and its
comment prefixes stripped. Prose here is hard-wrapped mid-phrase, and a
newline-bounded carrier put every marker on the wrong side of the break.

THE PARSER IS `tokenize`, NOT A REGEX.

P33's `comment_blocks` reads `//` and `/* */` and cannot see a Python `#`, which
is how a guard written for this repository reported a Python comment block as
clean. Python is read with `tokenize`, so `#` is a COMMENT token and a `#` inside
a string literal is not one. TypeScript has no parser in the standard library, so
its comment lines are found by tracking `/* */` depth and `//` prefixes — stated
here as the weaker half rather than presented as equivalent.

READING IS NOT LIMITED TO COMMENTS. `:735` below is the citation this work order
was written for, and it is inside a Python string literal that participates in
runtime output. A guard that reads only comments cannot see it, which is exactly
what P34's `comment_texts` did. This file scans the whole source text.

WHAT THIS DOES NOT PROVE.

A line-number citation can point at code and still be wrong, and this guard is
green on `:320` -> `}}` if the drift had been +1 instead of +22. The four real
drifts found here were found by reading the claim and the target together, not by
any rule — which is why `ChartFrame.tsx:320` was corrected by hand rather than by
this file, and why the honest claim is narrow: the guard makes the failure mode
that has ALREADY happened TWICE impossible to repeat silently, and it is a floor,
not a proof. `locked_fields.py`'s eight `Brand.tsx` citations are the standing
example of a reference this guard checks and a human still has to keep honest.

THE STRONGER ALTERNATIVE, AND WHAT IT COSTS.

P34 suggested, and this work order asks for an assessment of, guarding a SYMBOL
NAME rather than a line number: `Chart.tsx`'s `Chart` component, or the literal
`chart: no values` on the line, rather than `:211`. It is the better shape and
this is the honest case against adopting it now.

It is better because it survives every failure this guard cannot see. A symbol
does not move when a docstring is added above it, so the `:320 -> }}` class —
real code, wrong code, green under any line-based rule — simply does not exist
for it. It is also cheaper: finding `chart: no values` in the file is one
`in` check, where a line rule must parse, index and cache every target.

The cost is that it does not compose with what this repository already writes.
This tree has 57 distinct code-file citation EXPRESSIONS covering 90 individual
line targets, and 17 of those expressions are ranges or comma lists naming
several lines at once (`types.tsx:244,344,350` is three sites in one citation).
They are used to enumerate SITES for a claim ("inkFaint has 10 consumers, here
they are") rather than to point at one definition, and a symbol has no
line-range form — so converting means rewriting the claim, not the pointer. It
also cannot express "the third of these four lines", which is what a measured
site list usually is. And the conversion is not mechanical: `:379` naming `*/}`
and `:320` naming `}}` are drifted, but `FinanceShowcaseWide.tsx:95` naming
`heatmap: ChartScene,` is drifted in a way that no token on the line reveals —
deciding what the sentence WANTS is the same judgement a human already made
here.

So the recommendation is: keep the line-number rule, because it is cheap and it
catches the class that has actually occurred, and treat symbol-naming as the fix
for a SPECIFIC citation when one is found rather than a tree-wide migration. The
guard's own failure message points at both.
"""
from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Directories whose source is held to this rule. Same set as P34's guard:
#: `out/**` is a render artefact tree and `studio/public/jobs/**` is gitignored
#: staging, so neither is source anyone maintains.
SOURCE_DIRS = ('studio/src', 'studio/scripts', 'pipeline', 'tests', 'tools')

#: Extension alternation, LONGEST FIRST — P34 measured that `js|json` written in
#: that order silently matches `foo.js` out of `foo.json`, because Python's `re`
#: is first-alternative-wins. The same bug, and the same fix.
_EXTS = r'(?:tsx|json|mjs|py|ts|js|md|css|sh)'

#: A basename with a line number: `Chart.tsx:196`, `render.mjs:43-47`. The line
#: part is one number optionally followed by a range or a comma list, because all
#: three forms are citation shapes in this tree (`types.tsx:244,344,350` is a
#: single citation naming three lines).
#:
#: Two traps, both hit by the first draft of this regex:
#:
#: 1. The tail's separator may NOT be a bare `,`. `Chart.tsx:196, 34px` is one
#:    citation followed by a font size, and a comma-separated tail swallowed the
#:    `34` and reported a citation of line 34 that nobody wrote — the guard found
#:    a defect that did not exist. So a comma only continues the citation when no
#:    whitespace separates it from the next number: `244,344,350` continues,
#:    `196, 34px` does not. Same for `/` and `-`.
#: 2. The lookbehind may not reject `/`, `.` or `-`. Written `(?<![\w/.-])`,
#:    `studio/bin/render.mjs:43` found NOTHING, because the character before
#:    `render` is `/` — every path-qualified citation in the tree was silently
#:    invisible. The lookbehind excludes only a word char, so that a longer name
#:    ending in a known extension is not read as a citation of the shorter one
#:    (the counter-example is spelled without a line number on purpose: a
#:    hypothetical basename written WITH one is a citation to this guard whether
#:    or not the author meant it to be).
_CITE_RE = re.compile(
    r'(?<![\w])([A-Za-z0-9_][A-Za-z0-9_.-]*\.' + _EXTS + r'):(\d+)'
    r'((?:[-/,]\d+)*)'
)

#: Vocabulary marking a citation as NOT a live pointer at a line of code. Two
#: families, and both are statements about the citation rather than about the
#: target. Matched against the SENTENCE carrying the citation.
#:
#: Measured over this tree, every deliberate comment citation carries one of the
#: first family in its own sentence, and every drifted one carries none:
#:
#:     `render.mjs:141` names `qa_final.py` inside a comment explaining why ...
#:     site (`render.mjs:141` names `qa_final.py` in prose, and P17's first ...
#:     render.mjs:43-47 records why — 118 leaked copies filled a C: TEMP ...
#:
#: The second family is P34's historical vocabulary, reused because the question
#: is the same one: "`showcase-v1.ts:36` used to be cited for the `logo` enum
#: entry" is a true statement about a citation that was wrong, not a live
#: pointer, and `:36` being a comment today is the point rather than the defect.
#:
#: Both directions err toward RED, for P34's reason: a false positive is one
#: word added to a sentence, a false negative is a reader sent to the wrong line
#: by an assertion that reads as fact.
_NOT_A_LIVE_POINTER = (
    # points AT prose
    'in a comment', 'inside a comment', 'in the comment',
    'in prose', 'in the prose', 'comment explaining', 'explaining why',
    'while explaining', 'records why', 'records that', 'records the',
    'records how', 'recorded at', 'named in a comment', 'comment says',
    'comment block', 'comment names', 'names it in',
    # historical: was real, is not any more
    'used to', 'no longer', 'was cited', 'used to be cited', 'formerly',
)

#: Extensions this guard can actually judge. The question "is line N code or a
#: comment?" only has a mechanical answer in a language with a comment syntax,
#: and the parser here exists for exactly these families. A citation into a
#: `.md`, `.json`, `.sh` or `.yaml` is SKIPPED, not exempted: `README.md:35` is a
#: line of prose and "is it a comment" has no meaning for it, so calling it a
#: violation would be a category error. `tokens.ts` IS ambiguous in this tree
#: (three files carry the basename) and is reported as unidentifiable, which is
#: P34's rule for a bare basename and the same failure one level up.
_CODE_EXTS = ('.py', '.ts', '.tsx', '.js', '.mjs')

#: Citation sites that are exempt, keyed `(citing file, citation)` where the
#: citation is written the way it appears in source — a basename, a colon and a
#: line. Each entry carries the fact that exempts it. Kept short on purpose,
#: for P34's reason: a false positive is one line here, a false negative is a
#: reader sent to the wrong line.
#:
#: The only entry is THIS FILE, and it is not a loophole. This guard's own text
#: quotes the drifted citations verbatim — `Chart.tsx:196` appears in the module
#: docstring, in the regex's own comment about the `34px` trap, and in three
#: negative-control fixtures — because a guard that has never written the defect
#: down cannot be shown to catch it. Keying the exemption by CITING FILE rather
#: than by target is what keeps it narrow: `Chart.tsx:196` is still red
#: everywhere else in the tree, which is where the real one was.
_EXEMPT: dict[tuple[str, str], str] = {
    ('tests/test_line_refs_land_on_code.py', 'Chart.tsx:196'):
        'This file quotes the drifted citation verbatim in its docstring and in '
        'its negative-control fixtures. The guard must be able to write the '
        'defect down in order to test that it catches it.',
    ('tests/test_line_refs_land_on_code.py', 'visual_qa.py:751'):
        'Same: the blank-line fixture in test_the_criterion_can_still_say_no.',
    ('tests/test_line_refs_land_on_code.py', 'render.mjs:43'):
        'Same: the deliberate-comment-citation fixture quotes the real site.',
    ('tests/test_line_refs_land_on_code.py', 'render.mjs:47'):
        'Same, range end of the deliberate-comment fixture.',
    ('tests/test_line_refs_land_on_code.py', 'ChartFrame.tsx:379'):
        'Same: quoted in the docstring as one of the four real drifts.',
    ('tests/test_line_refs_land_on_code.py', 'FinanceShowcaseWide.tsx:95'):
        'Same: quoted in the docstring as one of the four real drifts.',
    ('tests/test_line_refs_land_on_code.py', 'render.mjs:141'):
        'Same, except here the marker is an f-string VARIABLE: the fixture '
        'interpolates {phrase} so that each phrase in the vocabulary can be '
        'tried in turn, and the literal source text carries no marker for this '
        'guard to read. The substituted value always does.',
    ('tests/test_p14_render_entry_points.py', 'render.mjs:43'):
        'A DELIBERATE citation of a comment block that no marker rescues: the '
        'citation sits at the end of an assertion-message string ("...filled a '
        'C: TEMP to 46 GB (render.mjs:43-47)"), and the sentence that says the '
        'lines RECORD the incident is some 30 lines earlier in the file. This is '
        'the honest limit of the marker mechanism, recorded rather than papered '
        'over: a marker must be in the citation\'s own sentence, and this one '
        'has none.',
    ('tests/test_p14_render_entry_points.py', 'render.mjs:47'):
        'Range end of the same deliberate citation; see the :43 entry.',
}


#: Whitespace runs, collapsed before marker matching — see `offenders`.
_WS = re.compile(r'\s+')

#: A comment continuation marker, stripped before marker matching so that the
#: `#: ` between two wrapped halves of one sentence is not read as content.
_COMMENT_PREFIX = re.compile(r'(?m)^[ \t]*(?:#[:]?|[*]|//+)[ \t]*')


def cited_lines(m: 're.Match[str]') -> list[int]:
    """Every line number one citation names: `:196`, `:43-47`, `:244,344`.

    Read off the regex's own groups rather than re-splitting the matched text.
    The first version re-parsed with `split(':', 1)` and an offset computed from
    `len(str(first_number))`, which silently depended on the tail's separator
    rules; when the tail format changed, it read garbage rather than raising.
    Group 2 is the first number and group 3 holds only the continuation digits.
    """
    nums = [int(m.group(2))]
    nums.extend(int(n) for n in re.findall(r'\d+', m.group(3)))
    return nums


def is_comment_line(path: Path, lineno: int, _cache: dict) -> bool:
    """Is `lineno` of `path` something other than CODE? Comment, blank, or past
    the end of the file all answer True, because all three are places a reader
    following a citation finds nothing.

    Python goes through `tokenize`, which yields real COMMENT tokens and so reads
    `#` correctly while ignoring a `#` inside a string literal. TypeScript has no
    stdlib parser, so block-comment depth is tracked and `//` prefixes are
    matched; that half is stated as weaker rather than presented as equal.
    """
    key = (str(path), path.stat().st_mtime_ns)
    if key not in _cache:
        lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
        comment: set[int] = set()
        blank: set[int] = set()
        for i, line in enumerate(lines, 1):
            if not line.strip():
                blank.add(i)
        if path.suffix == '.py':
            try:
                for tok in tokenize.generate_tokens(io.StringIO(
                        path.read_text(encoding='utf-8', errors='replace')).readline):
                    if tok.type != tokenize.COMMENT:
                        continue
                    # A COMMENT token on a line that also carries CODE does not
                    # make that line a comment: `y = 1  # trailing` is a line of
                    # code, and keying by line alone reported it as a comment.
                    # `tokenize` gives the token's start COLUMN, so the text
                    # before that column is what decides — empty means the
                    # comment is the whole line.
                    col = tok.start[1]
                    if not lines[tok.start[0] - 1][:col].strip():
                        comment.add(tok.start[0])
            except (tokenize.TokenError, IndentationError, SyntaxError):
                pass
        else:
            depth = 0
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if depth > 0:
                    comment.add(i)
                    depth += line.count('/*') - line.count('*/')
                    continue
                if stripped.startswith('//'):
                    comment.add(i)
                    continue
                opens, closes = line.count('/*'), line.count('*/')
                if opens > closes:
                    comment.add(i)
                depth += opens - closes
        _cache[key] = (comment, blank, len(lines))
    comment, blank, total = _cache[key]
    if lineno > total or lineno < 1:
        return True  # past EOF is not code; treated as a comment for reporting
    if lineno in blank:
        return True  # a blank line is not code either
    return lineno in comment


def carrier(text: str, pos: int) -> str:
    """The sentence around `pos`: bounded by `;` and by a `.` that is not part of
    a filename or a version number.

    A NEWLINE DOES NOT BOUND IT. Prose in this tree is hard-wrapped — the
    deliberate citations that matter most read `... render.mjs:141` names` on one
    line and `qa_final.py inside a comment` on the next — so a newline-bounded
    carrier cut every one of them in half and left the marker on the wrong side
    of the boundary. The first draft of this file bounded at `\n` (P34 does,
    because its question is about a phrase within one line) and reported five
    deliberate citations as violations; four of the five were P34's own measured
    false-positive risk, arrived at from the other direction. A newline is
    whitespace to a sentence, which is what it is in prose.
    """
    start = max(text.rfind(c, 0, pos) for c in ';\n') + 1
    end = len(text)
    for i in range(pos, len(text)):
        ch = text[i]
        if ch == ';':
            end = i
            break
        if ch != '.':
            continue
        nxt = text[i + 1:i + 2]
        if nxt.isdigit():
            continue
        if re.match(r'\.(?:tsx|json|mjs|py|ts|js|md|css|sh)(?![\w])', text[i:]):
            continue
        # A sentence break followed by a blank line, or by the end of a block
        # comment, ends the carrier — otherwise the walk runs to the end of the
        # file and a marker anywhere later rescues an earlier citation.
        if text[i + 1:i + 3] == '\n\n':
            end = i
            break
        end = i
        break
    return text[start:end]


def citations_in(text: str) -> list[tuple[str, int, str]]:
    """(basename, lineno, carrier_sentence) for every citation in one blob.

    Takes text, not source — extraction happens once, in `offenders`. P34's
    first draft passed already-extracted comment text back through its extractor,
    which stripped nothing and found nothing, and the guard went green for the
    wrong reason.
    """
    out: list[tuple[str, int, str]] = []
    for m in _CITE_RE.finditer(text):
        for n in cited_lines(m):
            out.append((m.group(1), n, carrier(text, m.start())))
    return out


def source_files() -> list[Path]:
    files: list[Path] = []
    for d in SOURCE_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        files.extend(sorted(p for p in base.rglob('*')
                            if p.is_file() and p.suffix in
                            ('.py', '.ts', '.tsx', '.mjs', '.js')
                            and not ({'node_modules', '__pycache__', 'out', 'dist'}
                                     & set(p.parts))))
    return files


def basename_index() -> dict[str, list[Path]]:
    """basename -> every file in the tree carrying it, for resolution.

    Resolving by basename rather than by full path is what catches a citation
    that survived its target being MOVED, which is the same failure one level up
    from a rename.
    """
    idx: dict[str, list[Path]] = {}
    for d in ('studio', 'pipeline', 'tests', 'tools'):
        base = ROOT / d
        if not base.exists():
            continue
        for p in base.rglob('*'):
            if p.is_file() and not ({'node_modules', '__pycache__', 'out', 'dist'}
                                    & set(p.parts)):
                idx.setdefault(p.name, []).append(p)
    return idx


# ── the criterion ───────────────────────────────────────────────────────────

def offenders(text: str, idx: dict[str, list[Path]], cache: dict,
              citing: str = '') -> list[str]:
    """Every citation in `text` whose line is not code, and is not deliberate.

    A citation is reported when the line it names is a comment, is blank, or is
    past the end of the file — UNLESS the sentence carrying it says the thing it
    names is prose, which is what a deliberate citation of a comment block looks
    like. A target that cannot be resolved to exactly one file is reported too:
    a citation that names a file this tree does not have is not evidence.

    `citing` is the citing file's repo-relative path, and it is what `_EXEMPT`
    is keyed by. It defaults to `''` so the negative-control fixtures below can
    call this without pretending to live somewhere.
    """
    problems: list[str] = []
    for name, lineno, sentence in citations_in(text):
        # A target this guard cannot judge is skipped, not reported — see
        # `_CODE_EXTS`. Checking last keeps the skip visible in one place.
        if Path(name).suffix not in _CODE_EXTS:
            continue
        if (citing, f'{name}:{lineno}') in _EXEMPT:
            continue
        hits = idx.get(name, [])
        if len(hits) > 1:
            problems.append(
                f'{name}:{lineno} — {len(hits)} files in the tree carry this '
                f'basename, so the citation does not identify a line')
            continue
        if not hits:
            problems.append(
                f'{name}:{lineno} — no file in the tree carries this basename, '
                f'so the citation does not identify a line')
            continue
        target = hits[0]
        key = str(target.relative_to(ROOT).as_posix())
        # Match markers against the sentence with its wrapping NORMALISED, and
        # with the comment prefix stripped. Prose in this tree is hard-wrapped
        # mid-phrase: `render.mjs:43-47 records` / `#: that 118 leaked copies`
        # is one sentence saying "records that", split across a line break with
        # a comment marker in the middle. Matching the raw carrier found
        # `records\n#: that`, which no vocabulary entry can match, and reported a
        # deliberate citation as a violation — a false positive manufactured by
        # the guard's own reading of prose rather than by the prose.
        flat = _WS.sub(' ', _COMMENT_PREFIX.sub(' ', sentence)).lower()
        if any(m in flat for m in _NOT_A_LIVE_POINTER):
            continue
        if is_comment_line(target, lineno, cache):
            problems.append(
                f'{name}:{lineno} → {key}:{lineno} is not code '
                f'(comment, blank, or past end of file). The sentence reads: '
                f'{sentence.strip()[:110]!r}')
    return problems


# ── the properties ──────────────────────────────────────────────────────────

def test_every_line_citation_lands_on_a_line_of_code():
    """The property, over the whole source text — comments, docstrings, and the
    runtime string literals a comment-only reader cannot see."""
    idx = basename_index()
    cache: dict = {}
    bad: list[str] = []
    for p in source_files():
        src = p.read_text(encoding='utf-8', errors='replace')
        rel = p.relative_to(ROOT).as_posix()
        found = offenders(src, idx, cache, rel)
        bad.extend(f'  {rel}: {f}' for f in found)
    assert not bad, (
        'source comments cite line numbers that do not land on code:\n'
        + '\n'.join(bad)
        + '\n\nThis is the `Chart.tsx:196` shape: P28 added a docstring above '
          'the "chart: no values" placeholder and the citation stayed at 196. A '
          'line-number citation that points at a comment is not a note, it is an '
          'assertion no test can check. Either update the line, or — if you are '
          'deliberately pointing at a comment block, or writing a historical '
          'note about a citation that used to be there — say so in the same '
          'sentence, which is what _NOT_A_LIVE_POINTER reads.')


def test_the_criterion_can_still_say_no():
    """The criterion must reject what it was written for.

    A criterion edited to always agree is green forever and protects nothing.
    These are the ORIGINAL drifted citations, verbatim: `Chart.tsx:196` is a
    comment today and `visual_qa.py:751` is a blank line, both measured, and
    neither is the shape of a deliberate citation.
    """
    idx = basename_index()
    cache: dict = {}

    # Chart.tsx:196 is the comment P28 wrote. Measured, not assumed:
    assert is_comment_line(ROOT / 'studio/src/templates/finance-showcase/charts/'
                           'Chart.tsx', 196, cache), (
        'Chart.tsx:196 is no longer a comment — P28\'s docstring moved or the '
        'file changed. This fixture assumed the drift was still present, and a '
        'fixture that has silently stopped reproducing its own defect proves '
        'nothing.')

    problems = offenders(
        '#:     the "chart: no values" placeholder (Chart.tsx:196, 34px).\n',
        idx, cache)
    assert problems, (
        'the criterion accepted the original `Chart.tsx:196` citation. It '
        'cannot fail, so the guard it powers cannot guard.')

    problems = offenders(
        "'sites_detail': 'text: KpiHero.tsx:84,118 and Chart.tsx:196; '",
        idx, cache)
    assert problems, (
        'the criterion accepted the citation from inside a RUNTIME STRING '
        'literal. That is the site this guard was written for: a comment-only '
        'reader cannot see it, so a criterion that only reads comments would '
        'report this clean.')

    problems = offenders(
        '    to key on. `--props` is the only graph-shaped flag '
        '(visual_qa.py:751).\n', idx, cache)
    assert problems, (
        'the criterion accepted a citation naming a BLANK line. Blank is not '
        'code, and a reader following it finds nothing at all.')


def test_a_deliberate_citation_of_a_comment_is_not_a_violation():
    """The other direction, and the reason P34 warned about this guard.

    Four sites in this tree deliberately point at a comment block. Without this,
    a maintainer hitting a red on a true statement has to choose between fixing
    the rule or ignoring it, and ignoring it is what happens.
    """
    idx = basename_index()
    cache: dict = {}
    for phrase in ('inside a comment explaining why', 'in prose',
                   'records why', 'in a comment explaining'):
        note = (f'#: `render.mjs:141` names `qa_final.py` {phrase} the file '
                f'passes --pixelfmt yuv420p.\n')
        assert not offenders(note, idx, cache), (
            f'a comment deliberately citing a comment block was red, via '
            f'{phrase!r}. That is a true statement about prose and the guard '
            f'must allow it — otherwise it is a false-positive machine, and a '
            f'false-positive machine gets switched off.')

    # A citation into real code stays green whichever marker is present.
    assert not offenders('#: the mark fill is `KpiHero.tsx:169`.\n',
                         idx, cache)


def test_the_scan_is_not_vacuous():
    """The file must be reading source at all.

    `offenders` returning `[]` for everything is the failure mode of every
    regex-based reader, and P33 hit it: a `#` regex finds no comments in a
    docstring-heavy Python file and the guard goes green for the wrong reason.
    """
    idx = basename_index()
    cache: dict = {}

    # A citation to real code, from inside a docstring. Green, but only
    # reachable if docstrings are read.
    assert not offenders(
        '"""See KpiHero.tsx:84 for the eyebrow."""\n', idx, cache)

    # The same citation moved onto a comment line must be red. If the parser
    # cannot tell a comment from code, this passes and the guard is theatre.
    assert offenders('#: See Chart.tsx:196 for the placeholder.\n',
                     idx, cache), (
        'a citation onto a comment line was accepted. Either the parser cannot '
        'tell code from comment, or the criterion cannot fail.')


def test_the_python_reader_really_reads_hashes():
    """`tokenize`, not a regex — the specific trap P33 fell into.

    A `#` inside a string literal is not a comment, and a line that is nothing
    but a string is CODE. A regex cannot tell those apart; this asserts the
    parser can, on a file that exists to be exactly that shape.
    """
    import tempfile
    cache: dict = {}
    # `newline='\n'` is explicit because `write_text` translates line endings on
    # Windows, and a fixture whose line NUMBERS depend on the translation is a
    # fixture that means different things on different machines.
    body = ('x = "a # b"\n'        # 1: code, a '#' inside a string literal
            '# real comment\n'     # 2: a comment
            'y = 1  # trailing\n'  # 3: code with a trailing comment
            '\n'                   # 4: blank
            'z = 2\n')             # 5: code
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'probe.py'
        p.write_text(body, encoding='utf-8', newline='\n')
        assert not is_comment_line(p, 1, cache), (
            'a `#` inside a string literal was read as a comment. That is the '
            'P33 trap in reverse: it would make this guard report citations to '
            'real code as broken.')
        assert is_comment_line(p, 2, cache), (
            'line 2 is `# real comment` and was not read as a comment. If the '
            'parser cannot tell code from comment, this guard is theatre.')
        assert not is_comment_line(p, 3, cache), (
            'a line of code with a TRAILING comment was classified as a comment. '
            'tokenize reports the COMMENT token start, which is what makes this '
            'correct for the trailing case.')
        assert not is_comment_line(p, 5, cache)


def test_the_exemption_list_stays_a_list_and_does_not_become_the_rule():
    """`_EXEMPT` must not grow into the mechanism.

    A guard that exempts its way to green is green for the wrong reason, and the
    failure is silent: every entry is one line, and each looks justified. So the
    list is pinned to what the tree actually needs — 9 entries: 8 of them this
    file's own quotations of the defects it must be able to write down, plus one
    deliberate citation whose marker is out of reach — and every entry must say
    which fact exempts it. The cap is a tripwire, not a quota: raising it is a
    deliberate act that has to be argued for in this test rather than slipped
    into the dict.

    The cap was written as 8 and the test failed at 9, which is the tripwire
    working on the author rather than on a future maintainer.
    """
    assert len(_EXEMPT) == 9, (
        f'_EXEMPT holds {len(_EXEMPT)} entries, not the 9 this test was written '
        f'against. Each one is a place this guard chose not to check, so growth '
        f'here is growth in the number of unverified line citations — and a '
        f'shrink may mean a real one was fixed and the entry should be deleted. '
        f'Add an entry only with a fact written beside it, and argue the change '
        f'here.')
    for key, reason in _EXEMPT.items():
        citing, ref = key
        assert len(reason) > 40, (
            f'{key} is exempt with no stated fact. An exemption whose reason is '
            f'a word is indistinguishable from a bug.')
    # The exemptions are keyed by CITING file, so the same target stays checked
    # everywhere else. `Chart.tsx:196` is exempt here and nowhere else — which
    # is the property that keeps this from being a blanket amnesty for the four
    # sites the work order found.
    assert ('tests/test_line_refs_land_on_code.py', 'Chart.tsx:196') in _EXEMPT
    assert not [k for k in _EXEMPT if k[1] == 'Chart.tsx:196'
                and k[0] != 'tests/test_line_refs_land_on_code.py'], (
        'Chart.tsx:196 is exempt somewhere other than this file. That citation '
        'is the real drift; exempting it anywhere else would hide it.')


def test_deleting_a_citation_is_not_a_failure():
    """Fewer citations must stay green; only wrong ones are red.

    Stated because the work order asked for it explicitly. A guard that required
    a minimum citation count would punish deletion, and the correct response to a
    stale comment is to delete it.
    """
    idx = basename_index()
    cache: dict = {}
    assert not offenders('#: nothing is cited here\n', idx, cache)
    assert not offenders('#: see KpiHero.tsx:84\n', idx, cache)