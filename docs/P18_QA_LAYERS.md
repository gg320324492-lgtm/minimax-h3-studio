# P18 — How many QA layers are there, actually

> Status: **analysis only.** No four-layer gate was built, no rule's decision
> logic was changed, and no new threshold was invented. The classification is
> now written down as data (`studio/scripts/qa_layers.py`) and guarded
> (`tests/test_p18_qa_layer_partition.py`). Whether to build a gate is left to
> the commander; §3 says what I measured and what I would and would not build.

**Verdict up front: B, with the real gap named in §3.2.** Building a "four-layer
gate" as a grouping would be building a table with a column header. The gate's
one load-bearing element — "everything passes or nothing ships" — already
exists, already exits non-zero, and is already misfiring on a rule that cannot
be otherwise.

---

## 1. What each rule is, measured

Membership is taken from the `Finding.rule` name each function **emits**, found
by calling all eleven rules — not from function names, and not by reading source
text. That distinction is load-bearing here: `rule_duplicate_check_props`
**emits the rule name `missing_asset`**, which is not its own name (measured,
`qa_layers._emitted_names()`). Partitioning by function name would have given
`missing_asset` two owners and missed the collision entirely.

| # | Rule (emitted name) | Layer | Input shape | Why this layer |
|---|---|---|---|---|
| 1 | `black_frame` | **Technical** | pixel array | Asks whether the frame is a flat single colour — container fidelity, not composition. |
| 2 | `aspect` | **Technical** | size tuple | Declared format vs measured pixels. A lookup; reads the graph, not taste. |
| 3 | `missing_asset` | **Technical** | props dict *(unused)* | Declared assets vs disk. Existence question. See the caveat below — this one does not read its argument. |
| 4 | `safe_area` | **Layout** | pixel array | Content bbox vs frame edge: does it fit. |
| 5 | `clipping` | **Layout** | pixel array | Content crossing the edge: does it get cut. |
| 6 | `font_size` | **Layout** | pixel array + declared | Rendered type against declared size; readability bar. |
| 7 | `freeze` | **Motion** | **two paths** | Did consecutive frames change. Pure time dimension. |
| 8 | `duplicate` | **Motion** | **two paths** | Did the sequence advance. See §1.2 — arguable. |
| 9 | `blur` | **Visual** | pixel array | Sharpness. Aesthetic quality. See §1.1 — arguable. |
| 10 | `contrast` | **Visual** | **none** | WCAG palette lookup. See §1.3 — the reason Visual is effectively one rule. |

**Three input shapes, confirmed by introspection not by reading:** 5 take a
single `np.ndarray`; 3 take pairs or tuples (`font_size` a+declared,
`aspect` measured+declared, `freeze`/`duplicate` two `Path`s — that's 4);
`contrast` takes **no arguments at all**; `missing_asset` and
`rule_duplicate_check_props` take a dict / a path.

### 1.1 `blur` is Visual, but Technical is a defensible reading

I classified it **Visual**: the instrument is Laplacian variance, the same
measure `take_ranker` uses for `m_sharpness`, which is an aesthetic quantity.
The counter-reading is that a defocused frame is a capture defect, and
`black_frame` — also frame fidelity — is Technical. Both readings are recorded;
one layer is chosen. Recorded in `qa_layers.AMBIGUOUS`.

### 1.2 `duplicate` is Motion, and the measurement complicates it

The question is time-domain, so Motion. But measured on this repo's own corpus
(all 53,956 frame pairs under `out/p13_probe`): 3,042 pairs fall below
`DUP_DISTANCE=0.5` and 50,914 above, landing at 0.498465 and 0.500140. The cut
is real. What it separates, though, is **scene, not time** — and restricted to
its actual input (consecutive frames of one scene), **20 of 40 pairs FAIL in
every group measured**. It reports DUPLICATE about half the time on frames that
are visibly moving, because the threshold was measured for two *renders* of one
graph and the rule is fed two *frames* of one render.

This is a finding, not a fix. **I did not change the rule's threshold or logic** —
that is a decision for the commander, and §6 lists it as the highest-value
open item.

### 1.3 `contrast` classifies the theme file, not the artefact

`rule_contrast()` takes **no arguments** and returns the same 24-pair table every
time. It is FAIL on all 333 corpus frames. It is the only rule in the table
whose verdict does not describe the thing being inspected — which is why
**Visual is 2 rules but effectively 1 rule that reads its input.**

### 1.4 `missing_asset` doesn't read its `props` argument

Verified two ways, because either alone is weak. Behaviourally: three unrelated
dicts produce byte-identical `Finding`s. Structurally: the function body with
its docstring removed, unparsed from the AST, never contains the token `props`.
The four checked paths are hardcoded SFX. **It is a repository check wearing a
props argument.** It is still Technical — it is an existence question — but it
is not a graph-reading rule, and it cannot be one without new work.

### 1.5 Which layers are empty or thin

**No layer is empty.** But the distribution is **3 / 3 / 2 / 2** —
Technical 3, Layout 3, Motion 2, Visual 2 — and that is the headline. "Four
layers" in the master plan reads like four comparable buckets. It is two of
three and two of two.

The work order predicted Motion would hold one rule. **It holds two** —
`duplicate` shares `freeze`'s input shape, and a `--frame` run reaches neither.
Motion is also the most expensive layer per rule: both its rules need two
rendered frames.

**Motion is the layer with almost nothing in it.** It has 2 rules out of 10,
both requiring the most expensive input in the tool, and one of the two
(`duplicate`) has a mismatched threshold (§1.2). Any four-layer gate would be
gatekeeping a **quarter** of the rule set, half of it on a pair-input basis,
one member of which currently misfires.

---

## 2. Does "全过才算过" exist? Yes. Does it work? Measured.

The commander's suspicion was that `visual_qa.py` reports findings rather than
blocking. **That is no longer true** — `visual_qa.py:855` returns
`1 if hard or unver else 0`, and `6e86b46` made UNVERIFIABLE non-zero too. I
verified the gate is real and that it **does** block. Measured exit codes (no
pipes — this window was nearly misled by one earlier):

| Invocation | Exit | Reading |
|---|---|---|
| `--frame <any png>` | **1** | `contrast` always FAILs, so this can never pass |
| `--frame-pair` (two frames of one scene) | **1** | `duplicate` FAILs — see §1.2 |
| `--frame-pair` (frames from different scenes) | **0** | the only green path found |
| `--props <real>` | **0** | runs `missing_asset` only; 5 findings, 1 rule |
| `--props <nonexistent>` | **1** | P13's fix holds |
| `--self-test` | **0** | |

**So the total gate exists and is armed. The problem is elsewhere: a gate that is
permanently red is indistinguishable from no gate at all.**

### 2.1 The P15 question, answered with a measurement

The commander's prompt was: *think about P15's `generative` — the QA report was
byte-identical and the exit code was identical. What can it block?*

I ran the experiment. Poisoning **every string in the props graph** to
`POISONED_XXXX…` and re-running:

```
EXITCODE_propsonly=0   →   EXITCODE_poisoned=0
diff report_original report_poisoned  →  IDENTICAL: byte-for-byte the same report
```

Also identical: `scenes` emptied, `scenes` removed entirely, and `format` set to
7×13. **The props path reports the same bytes and the same exit code for a
correct graph, an empty graph and a destroyed one.**

Why: `rule_missing_asset` is the only rule on that path, and §1.4 established it
never reads the props. So `visual_qa.py --props` is a repository check wearing a
gate costume.

**The generalisation the commander's prompt points at:** *a gate's power is
exactly the set of defects that move its output.* P15's `generative` flag and
P18's props-only path are the same defect — a signal that dies before it
reaches the measuring instrument — and both produce a clean, green, meaningless
report.

### 2.2 The blind spot nobody would have predicted

The gate has **no baseline**, so it cannot pass by accident, and **no way to
distinguish "checked and clean" from "checked nothing but the four UNAVAILABLE
rules always fire."**

Look at what a green run actually executes:

```
$ python visual_qa.py --props studio/public/jobs/showcase_demo/props.json
5 findings: 0 FAIL, 0 UNVERIFIABLE, 4 UNAVAILABLE
EXITCODE=0
```

**4 of the 5 findings are the UNAVAILABLE placeholders.** The fifth is
`missing_asset`, which doesn't read its input (§1.4). So the green props-only
path executes **zero rules that examine anything about the deliverable**. This is
P13's "a rule that silently never runs reports the same 0 FAIL as a clean frame,"
one level up: here a rule *does* run, and reports PASS, about the repository
rather than the render.

`flicker` — the rule that would need a luminance time-series — is in that
UNAVAILABLE set. **`flicker` is a Motion rule, and the only Motion-layer rule
that is absent from the layer partition is precisely the one the master plan's
"Motion" layer implies should exist.**

---

## 3. What is the real gap?

### 3.1 Ruling out two candidates

- **Not the rules.** Ten rules exist and are partitioned. Adding rules is a
  project decision, not a prerequisite for a gate, and inventing one now is
  exactly the "measurement is not a verdict" error the codebase documents at
  length (`collision` is deliberately UNAVAILABLE for this reason).
- **Not the layer split.** The partition is exhaustive, mutually exclusive, and
  each entry carries a measurement. A gate does not need four layers; it needs a
  total verdict.

### 3.2 The real gap, in order of severity

1. **Rules that pass without reading the artefact** (§1.4 `missing_asset`; §1.3
   `contrast`). Two of ten rules describe the repo or the theme file. A gate
   built on top of these inherits their blindness.
2. **A permanently-red gate** (§2). `--frame` can never pass. A gate that is
   always red is not enforced; it is noise, and noise is what gets ignored.
3. **No baseline.** `--frame-pair` between different scenes exits 0 — that is
   the nearest thing to a real pass in this tool, and it happens by accident of
   which two PNGs you name, not by any comparison against an expected state.

### 3.3 Verdict: **B — don't build a four-layer gate**

It would be a fourth column header on a table that already has a verdict. The
architecture question it poses was already answered correctly by `6e86b46`
(`FAIL` and `UNVERIFIABLE` both exit non-zero). What a four-layer gate would
*add* is a grouping with no consumer, and the layer thinness means the grouping
would be arbitrary where it matters most (Motion: 2 rules, both pair-input, one
misfiring).

**If a gate is wanted later**, the minimum design — *not implemented* — is: a
**baseline file** per job recording the expected verdict of each rule, and a
comparison gate that flags **any deviation**, not any absolute FAIL. That
directly fixes gap 3: it makes a props edit visible (§2.1 shows it currently is
invisible), it makes "checked nothing" distinguishable from "checked and clean",
and it turns the permanently-red rules into *stable red* — which a baseline
tolerates — rather than noise. Nothing about that requires four layers.

---

## 4. What was added

| File | What it is |
|---|---|
| `studio/scripts/qa_layers.py` | The partition as data. Derives layer behaviour by **calling** the rules. No gate, no exit code, no threshold. |
| `tests/test_p18_qa_layer_partition.py` | 20 guards: exhaustiveness, exclusivity, the layer pin, the behavioural claims, and two integrity guards. |
| `docs/P18_QA_LAYERS.md` | This file. |

Nothing else was touched. `visual_qa.py` and `qa_report.py` are **byte-identical
to HEAD** (sha256 verified, §7).

---

## 5. Mutation results

Protocol: inject → **assert the mutation is in the file** → run → restore from
snapshot → verify sha256. Every mutation below was proven on disk before the
test ran.

### Mutation 1 — move `blur` from Visual to Technical → **KILLED** (after a fix)

**First attempt SURVIVED: `16 passed`.** This is the finding worth recording.
`build_report()` originally held a module-level `LAYER_OF` dict and *derived*
the per-layer groupings from it — so every structural assertion read a structure
derived from the thing it was guarding. Moving a rule moved the grouping, the
counts and the thinness set together, and all sixteen guards stayed green.

That is the exact shape of the six text-assertion failures this project has
already paid for, arriving through a different door: **not a wrong guard, but a
guard derived from the thing it guarded.** A partition derived from itself cannot
be asserted against.

Fixed by inverting the direction — the grouping is now authored in
`build_report()` and `layer_of` is derived from it — and adding `PINNED_LAYERS`,
an independent copy in the test file. Re-run:

```
FAILED tests/test_p18_qa_layer_partition.py::test_the_layer_assignment_is_exactly_what_was_delivered
E   AssertionError: the layer partition changed. If this re-classification is intended, update PINNED_LAYERS in the same commit and say so in docs/P18_QA_LAYERS.md — a rule that changes layer silently is exactly what this project has been bitten by.
E   assert {'Technical':... 'contrast'], ...} == {'Technical':..., 'contrast'}
E     Differing items:
E     {'Visual': ['contrast']} != {'Visual': ['blur', 'contrast']}
E     {'Technical': ['aspect', 'black_frame', 'blur', 'missing_asset']} != {'Technical': ['aspect', 'black_frame', 'missing_asset']}
1 failed, 17 passed in 0.37s
```

### Mutation 2 — put `freeze` in Motion *and* Layout → **KILLED**

```
FAILED …::test_the_layer_assignment_is_exactly_what_was_delivered
FAILED …::test_a_rule_cannot_be_listed_in_two_layers
E   AssertionError: rules assigned to more than one layer: {'freeze': ['Layout', 'Motion']}
FAILED …::test_each_layer_grouping_agrees_with_the_flat_assignment
E   AssertionError: freeze is listed under Layout but LAYER_OF says 'Motion'
FAILED …::test_layer_sizes_are_reported_not_merely_implied
E   AssertionError: assert 11 == 10   # counts no longer close over the dict
4 failed, 14 passed in 0.36s
```

Note `LAYER_OF` is a dict and cannot hold a duplicate key — so the exclusivity
mutation had to be written into the **groupings**, which is exactly why the
guard is written against the groupings too.

### Mutation 3 — give `flicker` (an UNAVAILABLE rule) a layer → **KILLED**

Aimed at the property that a layer is a thing a gate can run:

```
FAILED …::test_the_layer_assignment_is_exactly_what_was_delivered
FAILED …::test_no_rule_is_classified_but_absent_from_the_code
E   AssertionError: layer entries for rules the code never emits: ['flicker']
FAILED …::test_the_unimplemented_rules_report_no_number_and_have_no_layer
E   AssertionError: UNAVAILABLE rules were given a layer: ['flicker']
FAILED …::test_thin_layers_are_declared_thin_not_left_for_the_reader
FAILED …::test_every_entry_carries_its_justification
E   AssertionError: flicker is in Visual with no MEASURED_NOTE
5 failed, 13 passed in 0.40s
```

**Survivors: none.** No mutation was judged an invalid variant; all three were
live and all three died on an assertion about the property they broke.

### 5.1 A mutation I could not kill, and did not fake

`flicker` and the other UNAVAILABLE rules **can** be placed in a layer if
`PINNED_LAYERS` is updated in the same edit — because a pin, by construction, can
be moved. The guard makes it *visible*; it cannot make it *impossible*. I did not
try to close this with a contrived input. It is the correct limit of a pin, and
it is why `PINNED_LAYERS` lives in the test file rather than beside the
implementation: the diff that moves a rule must touch the guard too.

---

## 6. Open items for the commander

1. **`duplicate`'s threshold is mismatched to its input** (§1.2) — 20/40
   consecutive-frame pairs report DUPLICATE. Highest-value finding. **Not fixed
   here**: changing a threshold is a judgement call and the rule's logic was out
   of scope.
2. **`contrast` fails permanently** (§2). A theme-level defect reported as a
   per-frame gate failure.
3. **`--props` runs no rule that examines the deliverable** (§1.4, §2.1).
4. **`flicker` is a Motion rule that does not exist** (§2.2). If Motion is ever
   to be a real layer, this is the rule it is missing.
5. **The master plan's "四层" row is now written down** and its distribution is
   3/3/2/2 as measured at P18. Two of its three open items have since been closed and the distribution has moved twice: P21 added a rule that examines the deliverable (4/3/2/2), and P22 split contrast so the palette lookup no longer gates any frame and added an UNAVAILABLE per-frame rule in its place (4/3/2/3). Item 3 below is therefore closed; item 1 (per-job baseline) and item 4 (flicker) are not.

---

## 7. Integrity

| File | sha256 at start | sha256 at end |
|---|---|---|
| `studio/scripts/visual_qa.py` | `9db0198e8db21bef696ead30114b1e242833cf2b39205880638fbded78565db3` | *unchanged* |
| `studio/scripts/qa_report.py` | `9e7e4725fcfcbe201caa14cdfe8f5cb6ea4a51bf3ea3b6bfe831b99c79b41f38` | *unchanged* |

No rendering was performed. `out/p13_probe/` was read only. Both QA scripts were
opened read-only. Nothing under `studio/public/jobs/` or `out/` was written.

**Test suite:** baseline **395 passed, 2 skipped**; after this change
**415 passed, 2 skipped** (20 new guards, no existing test modified).
`tests/test_p13_scene_cache_facts.py` was not modified and is green
(56 passed / 1 skipped across the three QA-adjacent files).

---

## 8. Mistakes I made, since a clean result is worth less than an honest one

1. **I wrote a vacuous measurement and it looked like a result.** The first
   `behaves_like_static` probe used an 80×120 frame with content at columns
   20..89, inside `visual_qa.EDGE=40`, so the backdrop model rejected every probe
   frame and `safe_area` answered UNVERIFIABLE on both inputs. `static: True`
   for a rule that read identical verdicts on two different frames — which looks
   exactly like "this rule ignores its input", and was in fact "this probe could
   not have detected anything". Fixed by moving the content clear of EDGE, and
   by adding `probe_is_sensitive()`, which asserts the pair really does drive
   rules apart. A second geometry mistake (inside `RING=24`, the top row band)
   had the same shape and was caught the same way.

2. **My first mutation survived, and I had built the reason for it into the
   design.** `build_report()` derived the layer groupings from `LAYER_OF`, so
   every structural assertion read a structure derived from the thing it
   guarded. Sixteen green tests, one silently re-classified rule. Full write-up
   in §5.1; the fix inverted the direction of derivation and added an
   independent `PINNED_LAYERS` copy.

3. **I shipped a line-ending change across a whole file and did not notice for
   several operations.** `qa_layers.py` was written as LF, then rewritten
   through several `python -c` `Path.write_text` calls, and came back **459 CRLF
   lines in a repository where every existing file is bare LF**. A one-line edit
   would have shown as a 459-line diff. Caught only when I measured endings rather
   than trusting them. Both new source files are now LF, and there is a guard.

4. **I asserted a number in a docstring that measurement contradicted.** I wrote
   that `duplicate` "reports FAIL on consecutive pairs" without qualifying it,
   then measured: 20 of 40 such pairs FAIL, not all of them — the rest reach
   13.29. I had also written a range, "0.28 to 0.69", that I had never measured.
   The final note states the measured figures (53,956 pairs; sides at 0.498465
   and 0.500140; 20/40 per group).

5. **Two process slips worth recording.** I piped a long-running probe into
   `tail`, so for ten minutes I was reading `tail`'s buffer and would have
   reported an empty result as "nothing found" — the exact misjudgement this
   window has already made once. And I ran a 333-`subprocess` sweep rather than
   in-process, which did not finish in 15 minutes. Both were avoidable; the
   in-process rewrite finished in about a minute.

**What I did not do:** render anything, change a threshold, change a rule's
decision logic, merge the two QA scripts, modify
`tests/test_p13_scene_cache_facts.py`, or touch `out/` or
`studio/public/jobs/`.
