# P24 — a per-job baseline, and what it compares when renders are not reproducible

> Work order: `docs/WORKORDER_P24_PER_JOB_BASELINE.md`. This file records what was
> measured, what was concluded, and what was deliberately NOT built.

---

## 1. The blocking question: if every render differs, what does a baseline compare?

**The work order asked this first, and it is the right question.** The answer is:
**it compares the VERDICT, not the number** — and that is not a compromise, it is
the only choice the measurements allow.

### 1.1 P13's fact, confirmed

`out/p13_probe/demo1.mp4`, `demo2.mp4`, `demo3.mp4` are three renders of one graph.
Their sizes are **711054 / 710851 / 712303** bytes, exactly as quoted.

Byte size is not the only difference. Decoding all three to 801 PNG frames each and
comparing pixels:

| pair | identical frames | changed px (median) | changed px (max) | max channel delta |
|---|---|---|---|---|
| demo1 / demo2 | 581 / 801 | 0 | 97729 | 76 |
| demo1 / demo3 | 589 / 801 | 0 | 95851 | 82 |
| demo2 / demo3 | 590 / 801 | 0 | 96604 | 77 |

So **~220 of 801 frames differ pixel-wise between runs of one render**. Renders are
not reproducible, confirmed beyond the byte count.

### 1.2 What that does to the numbers the gate emits

The corpus holds six real rerun pairs — `(full_a,full_b)`, `(full_a,full_r2)`,
`(full_b,full_r2)`, `(fr_a,fr_b)`, `(xc1a,xc1b)`, `(s1,s2)` — 226 frame-comparisons
per rule. Asking "does the rule agree with ITSELF on two runs of one render?":

| rule | measured | value differs | **verdict differs** | max relative spread |
|---|---|---|---|---|
| black_frame | 226 | 86 | **0** | 0.4250% |
| blur | 226 | 91 | **0** | 16.1488% |
| clipping | 226 | 18 | **0** | 1.6667% |
| contrast_frame | 226 | 0 | **0** | — |
| font_size | 226 | 37 | **0** | 96.8750% |
| safe_area | 226 | 9 | **0** | 3.2967% |

**VERDICT reproducibility: 1356/1356 identical (100.00%).** Independently
re-derived with different code over the five pixel rules: **1130/1130 = 100.00%**.

A second measurement, decoding the three demo mp4s to 81 frames each (243
measurements), found the same split: **0/243 verdicts varied, values varied on
`font_size` by up to 98.97%**.

### 1.3 Therefore

- A baseline over **numbers** would be **noise**. `font_size` moves ~97% between
  two runs of an unchanged render, so a numeric baseline would fire constantly on
  reruns of the same artefact — which is the "red for a constant" defect P22
  removed, pointed the other way.
- A baseline over **verdicts** compares the one thing measured to be stable.

**This is the difference from the four UNAVAILABLE predecessors.** They each lacked
a *judgement* (no threshold, no bimodality, no positive class). A baseline needs no
threshold at all: it compares a verdict word to the word recorded last time. The
work order's expectation that this item "很可能真的能建成" is correct, and the
reason is precisely this.

---

## 2. P18's three gaps, re-measured today

P18 said the diagnosis was "no baseline". The work order notes that P18's *measured*
bottleneck — "rules that do not read the artefact pass anyway" — was fixed by P21.
Re-measured, not quoted:

| P18 gap | status today | how it was re-measured |
|---|---|---|
| Rules that do not read the artefact pass anyway | **CLOSED (P21)** | `rule_graph_scene_renderable` returns FAIL for a graph asking `video` / `data-table` (declared, no renderer) and PASS for `kpi-hero` (declared and rendered). `rule_duplicate_check_props` returns UNVERIFIABLE for a missing props path. The rule discriminates. |
| The permanently-red gate | **CLOSED (P22)** | `FRAME_SCOPED_RULES` holds exactly 9 rules; `theme_contrast` is not among them; `UNIMPLEMENTED` holds exactly the 4 placeholders. `--frame out/p13_probe/fr_a/0020.png` reproduces the command window's result exactly: **EXIT=1, 11 findings: 0 FAIL, 2 UNVERIFIABLE, 5 UNAVAILABLE**. |
| No baseline | **STILL TRUE** | This document's subject. |

### 2.1 A correction to the work order's premise

The work order states: *"the problem is not 'red', it is that **no path reaches
exit 0**"*. **Measured, that is false for the ordinary case.**

Two arguments were simply never supplied by the caller:

- `--declared-px` — without it `font_size` is UNVERIFIABLE on **333/333**, because
  a ratio needs both sides;
- a props file declaring the format — without it `aspect` is UNVERIFIABLE on
  **333/333**, for the same reason.

With both supplied, on a real corpus frame:

```
$ py -3.12 studio/scripts/visual_qa.py --frame out/p13_probe/full_a/0002.png \
      --declared-px 20 --props <props with format 1920x1080@60>
EXIT=0
13 findings: 0 FAIL, 0 UNVERIFIABLE, 5 UNAVAILABLE
```

Over the whole 333-frame corpus, **291 of 333 reach exit 0**. The remaining 42 are
blocked by real measurements: 23 `black_frame` FAIL (flat/black frames), 30 `blur`
FAIL, and UNVERIFIABLEs where the backdrop model is untrusted.

⚠️ **An earlier measurement in this work said 227/333. That figure was an artifact of
my own assumption** — I declared 1920x1080 for every frame, but the corpus holds two
sizes (251 frames at 1920x1080, 82 at 480x270), so 82 frames FAILED `aspect` for a
reason I had invented. Declaring each frame's own size gives 291/333. The corrected
figure is the one reported here.

So the gate is **not stuck**. It is a gate that goes green when the caller tells it
what was asked for. This does not weaken the case for a baseline — it changes what a
baseline is for: not "make the gate reachable" but "notice that a reachable gate
changed shape".

---

## 3. Ruling: **A — it can be built**

| criterion | how it is satisfied |
|---|---|
| **1. Stable** | 1356/1356 verdicts identical across six real rerun pairs; 1130/1130 re-derived independently; 0/243 on a second corpus. Pinned as a value in the guard, and re-measured from the corpus at a stated sample (85 measurements) so the claim is checkable rather than asserted. |
| **2. Can catch something** | On a **real** pair already in the repo — `out/dark3/f00440.png` vs `out/debug/f00440.png`, two renders of the same job at the same frame — the rules disagree (`safe_area` PASS/UNVERIFIABLE, `clipping` PASS/FAIL). A baseline recorded from one is DEVIATED by the other. **No contrived input was constructed.** The guard runs the real rules over both real files, so a rule that stopped reading the frame would fail the guard rather than keep demonstrating nothing. |
| **3. Comparison object is explicit** | It compares **verdicts**, because that is what was measured stable, and it compares them for **equality** — there is no tolerance and no distance, so there is no number to tune. `Deviation` carries the two words (`PASS -> FAIL`), never a delta, because a delta would be a number and numbers are what this refuses. |

### 3.1 What was NOT built, and why

- **No exit code is changed.** `main()`'s `return 1 if hard or unver` is untouched.
  UNVERIFIABLE still exits non-zero — that is `6e86b46`'s rule, and "cannot measure
  means pass" is the failure this project has already paid for once.
- **No threshold is created.** There is nothing to tune; that is the whole point.
- **No `rule_*` function was added.** `qa_layers._rule_functions()` reads every
  `rule_*` off the AST and `tests/test_p18_qa_layer_partition.py` pins the result in
  `PINNED_LAYERS`. A new rule function would have required editing a partition P18
  owns and this work order does not authorise. A baseline is also not a rule: it
  reports no verdict of its own about an artefact, it compares two reports. Keeping
  it out of the AST namespace leaves P18's partition untouched and testable as-is.
- **`visual_qa.py` and `qa_layers.py` were not modified at all** — both sha256 values
  are byte-identical to `e372fe2` (see §6).

---

## 4. "If someone deleted the baseline file tomorrow"

**The answer is a definite failure, not a silent rebuild.**

- `read_baseline()` returns `None` for an absent file — and it never writes.
- `compare(..., None)` returns status `NO_BASELINE`, and `Comparison.ok` is **False**.
- A baseline for a different rule set returns `NOT_COMPARABLE`, `ok` **False**.
- A corrupt, empty, non-JSON, wrong-typed or non-dict baseline all read as `None`,
  so they also produce a definite failure rather than a green gate.
- `read_baseline()` is **read-only by construction**: a guard asserts that three
  reads never create the file, because a run that writes its own reference passes on
  first sight of any input.

Recording a baseline is a separate, explicit function (`write_baseline`), so the
"record" path is visible at its call site and never a side effect of a QA run.

---

## 5. Mutations

Every mutation was **asserted present in the file before the test run** (the
project has twice read results from a mutation that never landed).

| # | mutation | result | `-rf` |
|---|---|---|---|
| 1 | `if devs:` → `if False and devs:` (always report 通过) | **KILLED**, 2 failed / 9 passed | `FAILED ::test_a_real_renderer_variant_that_differs_is_reported_as_a_deviation`, `FAILED ::test_a_recorded_baseline_is_read_back_and_agrees` |
| 2 | `if devs:` → `if True or devs:` (always report 偏离) | **KILLED**, 3 failed / 8 passed | the two above plus `FAILED ::test_the_same_verdicts_in_a_different_order_still_agree` |
| 3 | `NO_BASELINE` → `AGREES` on a missing baseline (silent rebuild = pass) | **KILLED**, 2 failed / 9 passed | `FAILED ::test_a_missing_baseline_is_not_a_pass`, `FAILED ::test_a_corrupt_or_empty_baseline_is_not_a_pass` |

Mutation 2 is worth noting: the always-deviating implementation produced
`DEVIATES` with **"0 of 3 verdicts moved"** — a degenerate report. The guard caught it
on the agreement assertions rather than letting a rule that can never pass stand.

**No mutation survived.** Had one survived it would have been judged a real hole or
an invalid mutation and recorded as such; none needed that judgement.

---

## 6. Integrity

| file | sha256 | changed? |
|---|---|---|
| `studio/scripts/visual_qa.py` | `7e7d586a747c9fb13eb5b23628156e19649b1d696fa85fbff281207416d35ded` | **no** (identical to `e372fe2`) |
| `studio/scripts/qa_layers.py` | `ba519e9e9169aa916d143075cb06ac97d518143848fc5660d6112682e33abdf1` | **no** (identical to `e372fe2`) |

Both new files are LF-only (0 CRLF) and end with a newline. `out/**` was read only.

| file | purpose |
|---|---|
| `studio/scripts/frame_baseline.py` | the comparison (new) |
| `tests/test_p24_per_job_baseline.py` | the guard, 11 tests (new) |
| `docs/P24_PER_JOB_BASELINE.md` | this document (new) |

---

## 7. Mistakes made in this work, recorded because they changed results

1. **`NameError: name 'vqa' is not defined`** — the new guard's imports all bound
   `vq` (copied from the P22 guard) while one call site used `vqa.main`. It passed in
   isolation and only failed in a full run, and it is precisely the failure the work
   order names as a recurrence. Found by reading the pytest source excerpt, not by
   guessing.
2. **A wrong headline number: 227/333 instead of 291/333** — caused by declaring
   1920x1080 for every corpus frame when 82 of them are 480x270. Corrected above.
3. **A wrong asserted sample size: 142 / 710** — guessed before measuring. Computed
   first, then corrected to **33 / 165** (stride 8) and finally **17 / 85** (stride 16,
   the version shipped).
4. **A wrong scene type name `kpiHero`** used while re-verifying P18 gap 1, which made
   a correctly-behaving rule look like it FAILed a rendered type. The real value is
   `kpi-hero`. The rule was right; my probe input was not.
5. **A guard that took 11 minutes** (the full 1130-measurement sweep), longer than the
   rest of the suite combined. Reduced to a stated, asserted sample of 85
   measurements (~50s). The full-population figure was measured separately and is
   quoted in §1.2.
