# P15 — SR Router: the routing signal has no consumer, and nothing shipped needs one

> Measured on this machine at `59f2cc3`, node v24.16.0, py 3.12.
> Guard: `tests/test_generative_signal_has_no_consumer.py` (6 tests).
> This file records measurements. It does not implement anything.

## Verdict: B — not worth building, and the input signal is inert

P15 asked whether to build an SR router. It did not, because the two things a
router needs are both absent: **nothing routes on the flag, and nothing shipped
would route anyway.**

| Router requirement | Measured |
|---|---|
| A consumer for the routing signal | **None.** `generative` is produced and never read. |
| Delivered content that needs SR | **None.** 0 of 14 delivered scenes are generative. |
| P15 implementation in the repo | **None.** `sr_pipeline`/`flashvsr`/`real-esrgan` hit 8 markdown files, 0 code files. |

Ledger 15.1 / 15.2 stay empty. Consistent with P12/P13/P14, which were also
decided on measurement rather than built to show progress.

## 1. `generative` has no consumer — and the reason is a type, not a search

The obvious check is a text search, and it returns two hits, both in
`studio/src/schemas/showcase-v1.ts`: the declaration at :316 and the assignment
at :373. That is the commander window's finding, and it is correct.

**But a text search alone would have been wrong here, and this project has been
burned by that six times.** The reason `generative` cannot reach a component is
structural, and the structural evidence is stronger than the search:

```
GENERATIVE_SCENE_TYPES            showcase-v1.ts:87    ← the set
ResolvedScene.generative          showcase-v1.ts:316   ← declaration
resolveScenes() populates it     showcase-v1.ts:373   ← production
        │
        └──> resolveScenes() IS called in production:
             FinanceShowcaseWide.tsx:146  useMemo(() => resolveScenes(doc, false))
        │
        └──> ...and the result is mapped at :155
             resolved.map((r) => { ... r.id, r.startFrame, r.durationInFrames, r.type ... })
             <SceneRenderer scene={scene} />   ← `scene`, looked back up out of raw `doc` by id
```

**`SceneRenderer` is typed `React.FC<{scene: Scene}>` (FinanceShowcaseWide.tsx:114),
and `Scene` is `z.infer<typeof SceneSchema>` — which has no `generative` key at all.**
`SceneSchema` is `.strict()`; `generative` exists only on the *derived*
`ResolvedScene`. The flag is computed, returned, and then dropped at the exact
point where the code switches from `r` (resolved) back to `scene` (raw).

So this is not "declared and never called" — the usual smell, which the flag
does have a smell for. `resolveScenes` is called every render. The flag is inert
because **the type that carries it stops one function call short of the
components it would have to reach.**

### Indirect-consumption paths, each closed with evidence

The work order flagged that `sizes`/`sizeBy`/`showArea` were wrongly reported
inert. Those were consumed via `useDesign()`, props spreads, or runtime strings.
Each such path was checked here rather than assumed closed:

| Indirect path | Result | Evidence |
|---|---|---|
| Props spread of a resolved scene | **Closed** | Only spread is `bindings.check.ts:164` (`{...s}` on chart scenes, a check file). No `...r` / `...resolved` anywhere. |
| `useDesign()` / design context | **Closed** | No scene component reads a `generative` field; the flag is not on any context value. |
| Runtime string / bracket access | **Closed** | `\[\s*['"]generative['"]\s*\]` matches nothing outside the schema file. |
| Serialization (`JSON.stringify` of a resolved scene) | **Closed** | The only two stringify calls near scenes are in `depthCue.check.ts` on a locally-built object. |
| `Object.keys/entries` over a scene | **Closed** | All `Object.keys` calls are over `DEFAULT_CHART_OPTIONS`, `EVENT_SFX`, `THEMES`, or style-bible literals — none over a `ResolvedScene`. |
| Import of the exported constant | **Closed** | `GENERATIVE_SCENE_TYPES` is exported and imported by **nobody**. |

The Python side has a mirror that *is* consumed — `scene_graph.py:179`
`GENERATIVE_TYPES`, with `ResolvedScene.generative` (:209) and
`generative_scenes()` (:291) — but that is the Python planner reading its own
model, not the TS renderer reading the prop. `tests/test_showcase_schema_parity.py`
pins the two sets against each other. That mirror is real; it is not a consumer
of the TS flag.

## 2. How it got here: introduced by P3 as a declaration, never finished

```
a707d31  P3: showcase-v1 scene graph (the new centre of the architecture)
```

The commit message says: *"Generative routing is declared, not guessed: only
`video` and `data-plane-3d` go to H3; everything else is the Remotion motion
engine."*

**There was never a consumer — not then, not at any point since.** P3 shipped
`showcase-v1.ts`, `scene_graph.py`, the JSON Schema and the parity test; the TS
side of P3 had no `FinanceShowcaseWide` at all (it arrived in `3cd20ff`, P4, which
read `r.id`/`r.startFrame`/`r.durationInFrames`/`r.type` and never added a fifth).

`git log -S generative -- studio/` returns exactly one commit: `a707d31`. No
later commit has ever added, removed or read the field. It is not a regression
from a working version that got broken; **it is a contract that was written down
and never implemented.** The parity test that ships alongside it asserts the two
*declarations* agree — which is a real and useful guard, and is also why the
field has stayed green and unquestioned ever since.

## 3. Nothing shipped would route anyway

Measured from the graphs, not the source (`pipeline/examples/*.json`):

| File | Scenes | Types |
|---|---|---|
| `charts_demo.json` | 10 | bar-chart ×2, line-chart, area-chart, slope-chart, bubble-chart, heatmap, rank-chart, volume-chart, sparkline-chart |
| `showcase_demo.json` | 4 | kpi-hero, browser-stack, dashboard, calendar |

**14 scenes, 0 of them `video` or `data-plane-3d`.** Every delivered scene is a
programmatic chart or dashboard, which is the case the design says should go
**native and skip SR entirely.**

⚠️ **Correction to the work order:** it says 13 scenes. The measured count is
**14** (`bar-chart` appears twice in `charts_demo.json`). The conclusion is
unchanged — `video` and `data-plane-3d` appear zero times either way — but the
number was wrong.

So even if the flag were fully wired tomorrow, today's output would be
byte-identical: 14/14 scenes route native, 0 through SR.

## 4. What to do with the dead signal — recommendation only, not implemented

**Recommend: annotate, do not delete, do not wire.**

The work order asks this directly, and the choice is not free — each option has
a failure mode this project has already paid for somewhere:

- **Delete `generative`.** Rejected. The Python mirror (`scene_graph.py:179`)
  *is* consumed, and `test_showcase_schema_parity.py:100` asserts the TS and
  Python sets are equal. Deleting the TS half breaks a live guard to remove an
  inert half, and P3's design decision ("declared, not guessed") is real
  documentation of intent. Deleting the *field* would also break the parity
  contract that the ledger treats as an architectural invariant.
- **Wire a consumer now.** Rejected, and explicitly out of scope: the
  conclusion is not adjudicated, and a router built on a signal with zero
  content needing it would be building to show progress — the thing P12/P13/P14
  each declined to do.
- **Annotate.** `ResolvedScene.generative` carries a docstring saying it is
  computed and currently read by nothing, and pointing at this file. The
  `GENERATIVE_SCENE_TYPES` docstring already says what the flag *means*; what
  is missing is a line saying it is not yet *consumed*, so the next person
  reads "declared" as "working".

**Basis for preferring annotation over deletion**, from the project's own
precedent: `tests/test_undeclared_field_reads.py:26-28` already names six
declared-but-inert fields (`notes`, `audioEvents`, `transitionOut`, `focus`,
``ease`, `chart.baseline`) and deliberately does **not** delete them, calling
them *"ledger entries, not this file's job"*, with the rule stated as: *"a
declared-but-unread field is inert (a lie in the other direction, tracked
separately)."* `generative` is the same species. The established discipline is
**track it, don't silently remove it** — because an inert field that is deleted
takes its design rationale with it, and an inert field that is *unlabelled*
gets re-litigated from scratch every few phases.

This file plus the guard are that "tracked separately" half. **Implementing the
annotation is left to the commander window**, per the work order's instruction
not to wire or restructure before the verdict is adjudicated.

## 5. The guard

`tests/test_generative_signal_has_no_consumer.py`, 6 tests. Every assertion is
on observable behaviour or on a sweep that is anchored so it cannot pass by
matching nothing — never on file absence.

| Test | What it measures |
|---|---|
| `test_generative_is_produced_on_the_resolved_scene` | Runs the real `resolveScenes` under tsx; asserts the flag is computed **and** pins the set contents `{video, data-plane-3d}`. |
| `test_no_scene_module_can_receive_the_generative_flag` | Reads every delivered scene module's source (comments stripped) and asserts none mentions the flag. |
| `test_no_delivered_graph_contains_a_generative_scene` | Off the graphs: no `video`/`data-plane-3d`. Also asserts `total > 0` so a moved directory cannot make it vacuous. |
| `test_the_read_sweep_finds_a_genuine_read` | **Anchor.** Proves the matcher sees 4 real read shapes before its zero is trusted. |
| `test_no_production_source_reads_the_generative_flag` | Sweep over all of `studio/src`, excluding `.check.ts` and the two *producing* lines by shape (not line number). |
| `test_the_sweep_catches_a_read_added_to_a_scene_module` | Writes a real read into a scene module and requires the sweep to find it. |

The producer exclusion is a **shape** match (`generative: boolean;` /
`generative: GENERATIVE_SCENE_TYPES.has(`), not `line 316`/`line 373` — pinning
line numbers would cry wolf the first time anyone edits the schema above them.

## 6. Mutation results

All three injected at byte level (CRLF preserved on both CRLF files), **verified
present in the file before reading any test output**, then restored from backup
with `git diff` confirmed empty and sha256 re-checked.

### A. Real read added to a scene component (`KpiHero.tsx`) — **KILLED**

Injected: `export const SR_CUE = (r: {generative: boolean}): number => (r.generative ? 1 : 0);`

```
.F..F.                                                                   [100%]
FAILED tests/test_generative_signal_has_no_consumer.py::test_no_scene_module_can_receive_the_generative_flag
FAILED tests/test_generative_signal_has_no_consumer.py::test_no_production_source_reads_the_generative_flag
E   AssertionError: scene modules now mention `generative`: ['KpiHero.tsx']. The routing signal has a consumer; this file must be re-justified or retired.
E   AssertionError: the `generative` routing signal now has a consumer:
E     studio\src\templates\finance-showcase\scenes\KpiHero.tsx:line 178: .generative
2 failed, 4 passed in 1.64s
```

Killed twice, independently — the node-side scene sweep and the Python-side
source sweep. Red for the right reason in both cases.

### B. `'video'` removed from `GENERATIVE_SCENE_TYPES` — **KILLED**

```
FF....                                                                   [100%]
FAILED tests/test_generative_signal_has_no_consumer.py::test_generative_is_produced_on_the_resolved_scene
FAILED tests/test_generative_signal_has_no_consumer.py::test_no_scene_module_can_receive_the_generative_flag
E   AssertionError: {'setMembers': ['data-plane-3d'], 'flags': [['kpi-hero', False], ['video', False]]}
E   assert ['data-plane-3d'] == ['data-plane-3d', 'video']
E   AssertionError: {'flagOnResolved': False, 'filesScanned': 3, 'reads': [], 'exported': []}
2 failed, 4 passed in 1.74s
```

Red on the *routing behaviour*, not on a string: a `video` scene now resolves
to `generative: false`.

### C. Comment-only mention of the flag (`KpiHero.tsx`) — **SURVIVED**

Injected (prose only, no read): `// The generative flag decides whether this scene goes to H3 or stays native.`

```
......                                                                   [100%]
6 passed in 1.58s
```

**Judged an equivalent mutant, not a hole** — and deliberately *not* killed.
This is the `render.mjs` failure mode the work order names: `'Unknown flag' in
source` kept matching the comment explaining the fix it was meant to verify.
A comment is not a consumer; flagging it would push the next person toward a
"guard" that cries wolf on documentation. The scene sweep strips comments before
matching, so a prose mention cannot be mistaken for a read — and mutation A
confirms a real read is still caught on the very next line of the same file.

Confirmed the survival is not a gap in the file's reach: under mutation C the
neighbouring guards `test_showcase_schema_parity.py` and
`test_undeclared_field_reads.py` also stay green (42 passed) — all three treat
prose as prose.

## 7. sha256 — before and after

| File | Before | After |
|---|---|---|
| `studio/src/schemas/showcase-v1.ts` | `3294bd069eb6c44f85b8c6ca6f67d32f8a84f86b67e54f9b49e4c14a109ca278` | *identical* |
| `studio/bin/render.mjs` | `fdf178c7e1abd074f013f1bda633133447407af1a0d130a913c9fd6475624180` | *identical* |

Both production files are byte-for-byte unchanged. `showcase-v1.ts` measured at
**400 CRLF / 0 bare LF** at the start and again at the end (the work order's 400
was correct); `render.mjs` is **LF-only, 162 lines**.

## 8. Side observation: is there a third "entry silently passes"?

The family (`6e86b46` `visual_qa.py`, `306f327` `render.mjs`) is **not
reproduced**. Every entry point with a flag surface now rejects unknown flags
explicitly:

| Entry point | Handling |
|---|---|
| `studio/bin/render.mjs:56-61` | Walks argv, errors on any unknown flag |
| `studio/bin/still.mjs:38-43` | Same, with the known-flag list |
| `studio/scripts/visual_qa.py:766-774` | `argparse` — unknown flags exit non-zero |
| `studio/scripts/stage_showcase.py:92-98` | `argparse` |
| `studio/scripts/qa_report.py`, `rank_takes.py` | `argparse` |
| `studio/scripts/check_contract.py` | Takes **no arguments** — no flag surface to accept silently |

**No third instance found.** Noted only; nothing outside the guard was touched,
per the work order.

## 9. Test numbers

| Run | Result |
|---|---|
| Baseline (`59f2cc3`, before this change) | **389 passed, 2 skipped** in 197.49s |
| After adding the guard | **395 passed, 2 skipped** (389 + 6 new) |

## 10. Reproducing

```bash
cd /e/Minimax-H3 && py -3.12 -m pytest tests/test_generative_signal_has_no_consumer.py -q -rf
```

Node-backed tests skip if `npx` is absent; the sweep, the anchor and the graph
check run anywhere.