# `StyleBibleSchema` is strict — and why "breaks nothing today" is not the argument

P12, third deliverable. Follows `docs/STYLE_BIBLE_STRIPPED_SECTIONS.md`.

## What changed

| side | before | after |
|---|---|---|
| `studio/src/schemas/showcase-v1.ts` | `z.object({...})` — open | `z.object({...}).strict()` |
| `pipeline/schemas/showcase-v1.schema.json` | no `additionalProperties` on `definitions/StyleBible` | `"additionalProperties": false` |

Both mirrors, in the same commit. They had been disagreeing: zod stripped an
undeclared key and returned `success: true`, while the JSON Schema — had it been
asked — would have rejected it. That disagreement is the P11 defect-3 shape, and
one-sided strictness would have widened it rather than closed it.

## The measurement, and what it does not say

Before touching anything, every JSON in the repository was swept for a
`style_bible` carrying a key the schema does not declare:

```
scanned JSON files            : 563
files carrying a style_bible  : 3
undeclared keys that would become hard errors under .strict(): (none)
```

563 files, not the 19 originally quoted — the wider sweep includes
`studio/public/**`, `pipeline/**`, `tests/**` (no fixture graphs there; they are
built in-memory), `studio/bin/**` (no JSON), and every other JSON in the tree
outside `node_modules`. Keys actually found in delivered graphs:
`palette`, `typography`, `cameraLanguage`, `motionLanguage` — all declared.

**So `.strict()` breaks nothing that exists today.**

That sentence is true and it is not sufficient, and the difference is the whole
reason the change was made:

- *"breaks nothing today"* is a **snapshot**. It holds until the first graph
  ships a section nobody declared. At that moment a legitimate new feature
  becomes a load-time crash — visible, attributable, one line of fix.
- *"cannot break later"* is the **property** worth having. Before this change,
  that same graph would have validated clean, rendered, and silently ignored the
  new section.

The trade is being loud at authoring time instead of silent forever. That is the
same trade `SceneSchema` / `ShowcaseSchema` already made in P11, recorded at the
top of `showcase-v1.ts` under "THE TRADE-OFF ACCEPTED".

## What `.strict()` closes, and what it does not

Closed: an undeclared **top-level** style_bible key. Measured before and after on
the same input (`ghostKey` alongside a valid `typography`):

| state | `safeParse` result | keys |
|---|---|---|
| before (open) | `success: true` | `['typography']` — silently gone |
| `.passthrough()` | `success: true` | `['typography', 'ghostKey']` — kept, unvalidated |
| after (`.strict()`) | `success: false` | `error.issues`: `style_bible: Unrecognized key: "ghostKey"` |

**Not** closed — all of this is deliberate and pinned by tests:

- **The bag interior.** `palette.card`, `spacing.gutter`, and any other sub-key
  stay free-form: `safeParse({palette: {nope: 1}})` still succeeds.
  `mergeSection` filters by the default's own keys and type-checks each value,
  so an unknown sub-key is dropped there with the rest. Two pre-existing
  cross-mirror tests pin this openness
  (`test_pipeline_validates_the_schema.py` "style_bible open bag",
  `test_showcase_mirrors_agree_on_values.py` "unknown key in style_bible
  section") and would have gone red had strictness deepened.
- **`Scene.layout` / `Scene.content`**, the other two free-form bags, are
  untouched. `definitions/StyleBible` was removed from that file's `OPEN_BAGS`
  list, with the reason written down rather than left as a silent edit.
- **`depthCue`'s shape** stays `string[]`. `mergeList` is all-or-nothing; a
  3-element ramp asked for depth 4 would otherwise render the depth-1 shadow.

## The defect family this closes the root of

Three defects, one bed. They are not three unrelated bugs:

| | shape | detectable by |
|---|---|---|
| P11 `audio` | declared, merged by nothing, read by nothing | data-side reachability sweep |
| `836f532` `radius`/`shadow`/`depthCue` | merged and read by real scenes, never declared | data-side reachability sweep |
| **this** | parser open ⇒ *either* of the above can happen invisibly | `safeParse` behaviour |

The middle one is the one strictness was actually load-bearing for. Its author
saw a clean parse; its renderer saw a fully populated `StyleBible`; nothing
between them ever observed the value disappear. `836f532` fixed those three
sections and **left the bed in place** — `merge a section → a graph sets it →
it is stripped → a consumer reads a default` could run again with a fourth key.

`test_style_bible_merges_only_declared.py` cannot catch that class: by the time
it looks, the evidence is gone, and it only sees resolver bindings against
declared keys. Only strictness at the parser catches it.

## The guard

`tests/test_style_bible_schema_is_strict.py`. It calls `safeParse` and asserts
the **returned value** — never that a `.strict()` string appears in the source,
which would be satisfied by this file's own 60-line comment explaining that it
is strict. (This project has been fooled by text-presence assertions five times;
the list is in the guard's docstring.)

Two mutations, both proved landed on disk before reading results:

| mutation | outcome | keys |
|---|---|---|
| remove `.strict()` | guard red (6 tests) | `[]` — stripped |
| add `.passthrough()` | guard red (3 tests) | `['typography', 'zzUndeclaredSection']` — kept |

**Both are caught, by the same assertion** — `success is False`. That is the
point worth recording: the two ways to be non-strict produce *opposite* outputs,
so a guard written as "the unknown key is absent" catches stripping and misses
passthrough completely, and one written as "every declared key survived" misses
both. Only the rejection verdict distinguishes "rejects unknown keys" from both
ways of not doing it.

The guard also asserts the error **names the offending key**. Strictness nobody
can act on is not a fix: `describeIssues` renders `style_bible: Unrecognized
key: "ghostKey"`, and an author seeing that knows which key and where.

## What changed in the existing guards

`StyleBibleSchema` being open was the stated premise of two existing guards, so
adding strictness is a breaking change to them by construction. Three groups:

1. **`style_bible_consumption.declared_style_bible_keys()`** — its regex was
   anchored on `z.object({` with a greedy `.*?`, and it read keys at exactly two
   spaces. Attaching `.strict()` wraps the object (keys → 4 spaces) and the
   greedy match ran to `SceneSchema`'s closing `});`, sweeping Camera/Motion/
   Transition keys in. **12 tests went red on the day this landed, every one in
   an `assert`.** Fixed by a non-greedy body plus `[ \t]+` indentation. The
   second half of that fix is not cosmetic: with a fixed 4-space pattern, an
   existing mutation that deletes the `spacing` line by its old 2-space anchor
   deleted only two of four spaces, and `radius` was then reported as an
   undeclared section that had never been removed. That mutation's anchor is now
   indentation-agnostic.
2. **`test_showcase_schema_mirrors_agree.OPEN_BAGS`** — dropped
   `definitions/StyleBible`, with the distinction from `Scene.layout` /
   `Scene.content` (enumerated and bound by name vs. interpreted by components)
   written into the constant.
3. **`test_style_bible_no_dumb_declarations`** — its premise test asserted the
   schema was *open* and said "re-derive this file if someone adds `.strict()`".
   Someone did; the file is re-derived, the premise now asserts the opposite with
   the reason, and its runtime probe test is inverted from "the key is stripped"
   to "the key is rejected and named".

**Residue that strictness does NOT reach:** `chartLanguage` and `audioLanguage`
are declared on both mirrors and bound by nothing. There is no undeclared key in
that chain, so validation is perfectly happy — it is the P11 direction, and its
repair (delete the declaration, or wire the consumer) is a different decision
and deliberately out of this change's scope.

## Line endings

Measured per file at the byte level before and after, not assumed:
`showcase-v1.ts` 400 CRLF / 0 bare LF (was 371 before this change — the
comment grew), `showcase-v1.schema.json` CRLF, `styleBible.tsx` CRLF,
`tokens.ts` LF. (The work order's "339 CRLF" for `showcase-v1.ts` was stale; the
*classification* was right, the count was not.)

## Validation note

The JSON Schema was compiled with **Ajv 8 using the draft-07 class selected from
the file's own `$schema`**, because Python's `jsonschema` was used once on this
file and failed to resolve `$ref` — producing the opposite verdict. `additional-
Properties: false` on `StyleBible` is only reachable through
`#/definitions/StyleBible`, so a run that does not resolve `$ref` silently never
tests it.