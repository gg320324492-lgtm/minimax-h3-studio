"""Derive which style_bible keys a renderer can actually reach (P12).

This module is the READ side of the P12 guard. It answers one question
mechanically, from source text, so the answer cannot drift away from the code
the way a hand-written list of "keys we support" would:

    given a style_bible key set in a graph, can the renderer see it at all?

WHY THIS IS DERIVED AND NOT ASSERTED (P12, third deliverable).

The defect this exists for is a *dumb declaration*: a key a graph sets that no
render decision depends on. The project has paid for this several times already
— `notes` / `audioEvents` / `transitionOut` / `focus` / `ease` /
`chart.baseline` were all "declared", and `tests/test_undeclared_field_reads.py`
documents the first case at length. A guard written as `assert 'palette' in src`
proves a string appears somewhere, which is a fact about TEXT and not about
BEHAVIOUR. This project has been fooled by text-presence assertions four times
(`mkdtemp` matching a comment about the bug it was written for, `rmSync`
satisfied by a pre-existing call, two-word prose that survived its own deletion,
and a check file reading its own sibling's assertion). So nothing here asserts
that a key name occurs in a file. Everything below derives a CHAIN and requires
every link to hold:

    graph key
      --[1. StyleBibleSchema declares it]-->              survives zod parse
      --[2. resolveStyleBible merges b.<key>]-->          reaches StyleBible
      --[3. useDesign() republishes that field]-->        reaches a scene
      --[4. a production .tsx names the export]-->        drives a render decision

All four links are required. Link 1 is the one that is easy to forget and it is
not decorative. It WAS open — `StyleBibleSchema` was a bare `z.object` with no
`.strict()`, so a key it did not name was silently dropped on parse, and
`styleBible.tsx` bound four sections (`radius`, `shadow`, `depth`, `depthCue`)
that no declared key could populate. Those four were consumed by scenes and
still unreachable from a graph: the same defect as P11's `audio` in the
opposite direction, not a read that cannot happen but a read that cannot be
fed.

P12 closed both ends of that in sequence. `836f532` declared the three sections
that had consumers and deleted the plumbing for `depth`, which had none.
`StyleBibleSchema` is now `.strict()`, so link 1 rejects rather than strips —
which is why the section below no longer treats an open bible as the premise,
and why the guards in this module measure REACHABILITY, not the parser's
leniency. Strictness moved the failure from "invisible" to "loud"; it did not
make any key reachable on its own, which is why links 2-4 are still measured
rather than assumed.

WHAT IS DELIBERATELY NOT PROVEN HERE.

`useDesign()` re-exports fields a scene may destructure and then not use — that
happens today (`RADIUS` is destructured at four sites and used at three). So
"named by a scene" is a deliberately generous final link: it proves a
declaration can reach a render decision, not that every scene honours it. That
is the same line `test_undeclared_field_reads.py` draws between "declared" and
"read", drawn here for the same reason — a guard that promises more than it
measures is the failure mode this project keeps meeting.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'src' if False else ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase'
STYLE_BIBLE_TSX = TEMPLATE / 'design' / 'styleBible.tsx'
SCHEMA_TS = ROOT / 'studio' / 'src' / 'schemas' / 'showcase-v1.ts'
EXAMPLES = ROOT / 'pipeline' / 'examples'

#: Production `.tsx` that can render a scene. Two exclusions, both earned:
#:
#:  * `*.check.ts` — a check file is full of text patterns on purpose, and a
#:    guard that reads its own sibling's assertions is how this project produced
#:    a green suite over a red renderer once already (see
#:    `test_undeclared_field_reads.py`).
#:  * `design/styleBible.tsx` — this is the one the first version of this file
#:    got wrong, and it is worth recording why. The resolver *defines* every
#:    export, so it names all nine of them, and counting it as a consumer made
#:    every key reachable the moment it was bound. The key would have looked
#:    consumed on the strength of the very code being measured. A resolver is
#:    not a consumer of itself.
SCENE_SOURCES: tuple[Path, ...] = tuple(
    sorted(p for p in TEMPLATE.rglob('*.tsx')
           if not p.name.endswith('.check.ts')
           and p.resolve() != STYLE_BIBLE_TSX.resolve())
)


def _strip_comments(text: str) -> str:
    """Drop `//` line comments and `/* */` blocks, preserving line count.

    Comments are where this codebase *explains* its own dead fields — the
    `CameraRig.tsx` note about `cameraLanguage` being "a declaration nothing
    read" is prose describing the defect, not a consumer. A sweep that cannot
    tell prose from code keeps reporting those as live.
    """
    out = re.sub(r'/\*[\s\S]*?\*/', lambda m: '\n' * m.group(0).count('\n'), text)
    return re.sub(r'//[^\n]*', '', out)


# ── link 1: what survives the parser ───────────────────────────────────────

def declared_style_bible_keys() -> set[str]:
    """Keys `StyleBibleSchema` names, parsed out of the zod literal.

    Read from source rather than by running node, for the reason
    `test_undeclared_field_reads.py` gives: a guard that needs a node runtime
    cannot fail when node is missing, and this suite must stay runnable with
    nothing but pytest.

    THE BODY IS MATCHED NON-GREEDILY, and that is load-bearing. Attaching
    `.strict()` means `z.object({` is no longer on the same line as the
    `export const`, so the body used to be matched from `z.object({` with a
    greedy `.*?` — which runs to the LAST `});` in the file, SceneSchema's, and
    sweeps Motion/Camera/Transition keys into this set. The result is not a
    wrong answer, it is a wrong QUESTION: every caller believes it is asking
    about StyleBible. Twelve tests went red on the day `.strict()` landed
    because of it, and every one of them went red in `assert`, which is the
    worst possible shape for a refactor to present as.

    The opening is therefore `z\\s*\\n?\\s*\\.object\\(\\{` — accepting both the
    one-line and the wrapped spelling — and the body is non-greedy, so it stops
    at the first `}` at the object's own indentation. This is the same trap
    `test_motion_ease_is_not_a_claim.py` had to solve for `_ts_motion_keys`,
    and it is solved the same way.

    KEY INDENTATION IS MATCHED AS `^[ \\t]+`, NOT AS A FIXED COUNT. A fixed
    width looks harmless and is not: when P12 wrapped this object to attach
    `.strict()`, the keys moved from two spaces to four, and a mutation in
    `test_style_bible_merges_only_declared.py` that deletes the `spacing` line
    by its two-space anchor then deleted only TWO of the four leading spaces.
    The next key was left at six, the fixed-width pattern stopped matching it,
    and `radius` was reported as an UNDECLARED section that had never been
    removed — a mutation test failing on a phantom produced by its own parser.
    Indentation is a formatting fact; the declaration is not.
    """
    src = SCHEMA_TS.read_text(encoding='utf-8')
    m = re.search(
        r'export const StyleBibleSchema\s*=\s*z\s*\n?\s*\.object\(\{\s*\n(.*?)\n\s*\}\)',
        src, re.S)
    assert m, ('could not find StyleBibleSchema in showcase-v1.ts; if it was '
               'reshaped, update this parser rather than reading the failure as '
               'a schema problem.')
    return set(re.findall(r'^[ \t]+(\w+):', m.group(1), re.M))


def style_bible_is_strict() -> bool:
    """Whether `StyleBibleSchema` rejects undeclared keys.

    False means an undeclared key is STRIPPED rather than rejected: the graph
    validates clean and the value vanishes before any renderer sees it. That is
    the structural reason link 1 of the chain exists at all.

    IMPORTANT: this is a TEXT predicate and it is NOT what the P12 strictness
    guard uses. `tests/test_style_bible_schema_is_strict.py` calls `safeParse`
    and asserts the returned value, because a substring test cannot tell a
    `.strict()` in code from a `.strict()` in this repository's own prose. This
    helper survives only because
    `test_style_bible_no_dumb_declarations.py` still needs a runtime-free
    premise anchor -- and that file's own docstring says so. If you are adding a
    strictness check, add it there, not here.
    """
    src = SCHEMA_TS.read_text(encoding='utf-8')
    m = re.search(r'export const StyleBibleSchema\s*=\s*z\s*\n?\s*\.object\(\{'
                  r'.*?\}\s*\)(\.\w+\([^()]*\))*;', src, re.S)
    assert m, 'could not locate the StyleBibleSchema declaration'
    return '.strict()' in m.group(0)


# ── links 2 and 3: the resolver and the context export ──────────────────────

def resolver_bindings() -> dict[str, str]:
    """style_bible key -> the `StyleBible` field the resolver writes it into.

    Both spellings the resolver uses are covered, because it uses two: `b.<key>`
    inside `resolveInvariant`, and `section('<key>')` for the theme-merged
    sections. Derived rather than listed so that renaming a binding in
    `styleBible.tsx` breaks the chain loudly instead of silently keeping a
    stale key marked reachable.
    """
    src = _strip_comments(STYLE_BIBLE_TSX.read_text(encoding='utf-8'))
    bindings: dict[str, str] = {}
    for m in re.finditer(r'(\w+):\s*merge\w*\((?:[^;]*?)b\.(\w+)', src, re.S):
        bindings[m.group(2)] = m.group(1)
    for m in re.finditer(r"""(\w+):\s*merge\w*\((?:[^;]*?)section\('(\w+)'\)""", src, re.S):
        bindings[m.group(2)] = m.group(1)
    return bindings


def design_exports() -> dict[str, str]:
    """`StyleBible` field -> the name `useDesign()` publishes it under."""
    src = _strip_comments(STYLE_BIBLE_TSX.read_text(encoding='utf-8'))
    return {m.group(2): m.group(1)
            for m in re.finditer(r'(\w+):\s*s\.(\w+)', src)}


# ── link 4: a scene names the export ───────────────────────────────────────

def _first_use(body: str, name: str) -> int:
    """1-based line where `name` appears in comment-stripped `body`, else 0."""
    pat = re.compile(r'\b%s\b' % re.escape(name))
    for i, line in enumerate(body.split('\n'), 1):
        if pat.search(line):
            return i
    return 0


def destructured_exports() -> dict[str, list[str]]:
    """`useDesign()` export -> every `file:line` that destructures it.

    The retrieval-path index the consumer link is judged against. Kept
    separate from `consumers_of` so a test can assert on the two independently.
    """
    index: dict[str, list[str]] = {}
    for src in SCENE_SOURCES:
        body = _strip_comments(src.read_text(encoding='utf-8'))
        for m in re.finditer(r'const\s*\{([^}]*)\}\s*=\s*useDesign\(\)', body):
            line = body[: m.start()].count('\n') + 1
            rel = '%s:%d' % (src.relative_to(ROOT).as_posix(), line)
            for n in m.group(1).split(','):
                name = n.strip().split(':')[0].strip()
                if name:
                    index.setdefault(name, []).append(rel)
    return index


def consumers_of(export: str) -> list[str]:
    """`file:line` for every production scene that pulls `export` off `useDesign()`.

    A bare word match is too loose, and this is the second version of this file
    to learn that the hard way. `camera` is both the name `useDesign()` publishes
    the camera defaults under AND the name of the `camera` PROP every scene
    passes to `<CameraRig camera={scene.camera} .../>`. Matching the word made
    `cameraLanguage` look consumed by six files when the only real read is
    `CameraRig.tsx:149` — the graph could set `cameraLanguage.perspective` and
    four scenes would still have matched on a prop they were already passing.

    So the consumer link is scoped to the actual retrieval path: the export name
    must be destructured FROM `useDesign()`. A scene that imports a value
    directly from `tokens.ts` instead is not consuming the bible and must not
    count — that was the original P4 defect this whole mechanism exists for.
    """
    hits: list[str] = []
    for src in SCENE_SOURCES:
        body = _strip_comments(src.read_text(encoding='utf-8'))
        for m in re.finditer(r'const\s*\{([^}]*)\}\s*=\s*useDesign\(\)', body):
            names = {n.strip().split(':')[0].strip()
                     for n in m.group(1).split(',') if n.strip()}
            if export in names:
                line = body[: m.start()].count('\n') + 1
                hits.append('%s:%d' % (src.relative_to(ROOT).as_posix(), line))
    return hits


# ── the chain ──────────────────────────────────────────────────────────────

def reachability(key: str) -> tuple[str, list[str]]:
    """Where the chain for `key` stops.

    Returns `(state, evidence)`:

      * `reachable` — all four links hold; a graph setting this key changes
        the film.
      * `no-declaration` — zod strips the key, so nothing can ever arrive.
      * `no-resolver-binding` — it survives parsing, the resolver never reads
        it, so it dies at link 2.
      * `bound-but-not-exported` — the resolver merges it but `useDesign()`
        does not republish the field it lands in.
      * `resolver-bound-but-unused` — it reaches the context and no scene
        names the export.

    The last three are all "the graph can say this and nothing happens", and the
    distinction matters to whoever acts on it, so they are not collapsed.
    """
    evidence: list[str] = []
    if key not in declared_style_bible_keys():
        return 'no-declaration', evidence

    bindings = resolver_bindings()
    if key not in bindings:
        return 'no-resolver-binding', evidence
    field = bindings[key]
    evidence.append('b.%s -> StyleBible.%s' % (key, field))

    exports = design_exports()
    if field not in exports:
        return 'bound-but-not-exported', evidence
    name = exports[field]
    evidence.append('useDesign().%s' % name)

    sites = consumers_of(name)
    if not sites:
        return 'resolver-bound-but-unused', evidence
    evidence.append('named by %s' % ', '.join(sites))
    return 'reachable', evidence


def reachability_report() -> dict[str, tuple[str, list[str]]]:
    """state + evidence for every key `StyleBibleSchema` declares."""
    return {key: reachability(key) for key in sorted(declared_style_bible_keys())}


def unreachable_declared_keys() -> dict[str, str]:
    """Declared keys that no graph can actually make the renderer see."""
    return {k: s for k, s in
            ((k, v[0]) for k, v in reachability_report().items())
            if s != 'reachable'}


def resolver_sections_outside_the_schema() -> dict[str, str]:
    """Sections `styleBible.tsx` merges that no declared key can populate.

    These are the strongest form of dumb declaration found so far and they are
    invisible from the data side: the resolver genuinely reads them, scenes
    genuinely read the result, and the parser deletes the input on the way past.
    """
    declared = declared_style_bible_keys()
    return {k: v for k, v in sorted(resolver_bindings().items())
            if k not in declared}


def keys_in_graphs() -> dict[str, list[str]]:
    """Every style_bible key that appears in a delivered graph.

    Walks the film-level and per-scene `style_bible` alike, because
    `FinanceShowcaseWide.tsx:170` feeds `doc.style_bible` and
    `scene.style_bible` into the same provider, so a per-scene override is just
    as capable of being a dumb declaration.

    Only tracked graphs under `pipeline/examples` are read.
    `studio/public/jobs/**` is a gitignored staging copy that renders from
    whichever graph was staged last; treating it as "the delivered graph" would
    make this guard's verdict depend on local scratch state.
    """
    keys: dict[str, list[str]] = {}
    for graph_path in sorted(EXAMPLES.glob('*.json')):
        doc = json.loads(graph_path.read_text(encoding='utf-8-sig'))

        def walk(node: object, trail: str) -> None:
            if isinstance(node, dict):
                for k, v in node.items():
                    if k == 'style_bible' and isinstance(v, dict):
                        for sk in v:
                            keys.setdefault(sk, []).append(
                                f'{graph_path.name}{trail}')
                    walk(v, f'{trail}.{k}')
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f'{trail}[{i}]')

        walk(doc, '')
    return keys


if __name__ == '__main__':
    print('strict                 :', style_bible_is_strict())
    for key, (state, ev) in reachability_report().items():
        print('  %-16s %-26s %s' % (key, state, '; '.join(ev)))
    print('resolver-only sections :', resolver_sections_outside_the_schema())
    print('keys in delivered graph:', keys_in_graphs())
