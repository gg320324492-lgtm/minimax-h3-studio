# P19 — `rule_duplicate` measured two different things with one ruler

> Findings behind the fix. Every number below was measured on this machine
> during this task; the measurement commands and the corpus are named in each
> section, and anything not measured is marked as not measured. Work order:
> `docs/WORKORDER_P18_DUPLICATE_MISMATCH.md`.

---

## 1. THE QUESTION THAT HAD TO BE ANSWERED FIRST

> Does a "duplicate threshold" exist in `take_ranker.py`? If yes, is it 0.5?

**It does not exist.** `take_ranker.py` contains no 0.5 duplicate threshold.

The 0.5s that are in that file are jitter and optical-flow parameters, exactly
as the work order suspected:

| line | what it is |
|---|---|
| `take_ranker.py:106` | `m_sharpness` fallback on an empty frame list |
| `take_ranker.py:116` | `m_exposure` fallback on an empty frame list |
| `take_ranker.py:148` | `m_temporal_stability` fallback for `(stability, jitter)` |
| `take_ranker.py:157` | `calcOpticalFlowFarneback(pyr_scale=0.5)` — a cv2 parameter |
| `take_ranker.py:159`, `:161` | the jitter score's neutral value and its scaling |

What the file *does* have is `m_duplicate` (`:165-171`), and it is a different
instrument answering a different question:

```
diff  = mean abs diff of consecutive full-resolution frames / 255   # 0..1 scale
cut   = 0.0015                                                       # ~0.006 grey levels
```

`0.0015 × 255 = 0.3825` grey levels — 0.0015 is a different number, on a
different scale, answering "is this take frozen".

The 0.5 the docstring cited lives in **`studio/scripts/rank_takes.py:44`**,
`DUP_THRESHOLD`, applied at `:68` to `signature_distance(a._sig, b._sig)` over
whole-take signatures. `rank_takes.py:35-38` states P1's measurement
({0.000} ∪ [34.5, 67.2]) in a comment that is accurate for that comparison.

**So the number was real and it was real somewhere else. The reuse never
existed.** That is verdict **B**, and it takes precedence over A.

### 1a. A fourth number, and a third value

The "same" rule is also applied at `ceo_mindread_ep01/scripts/select_takes.py:90`
with **`< 1.0`**, not 0.5. And `rank_takes.py:40-43` already carried a KNOWN
LIMIT that contradicted the reuse it was being cited for:

> this catches *exact* duplicates only. A rerun with a non-deterministic sampler
> would land at a small-but-nonzero distance and slip through.

So three call sites, three numbers, one of which (`take_ranker.m_duplicate`)
answers a different question entirely. **Recorded, not fixed** — this work
order is scoped to `rule_duplicate`.

---

## 2. THE MEASUREMENT

Corpus: `out/p13_probe`, 329 PNGs across 9 frame directories (P18's corpus;
read-only, nothing written into `out/`). All distances are
`visual_qa.signature_distance` on the 0..255 scale the rule actually uses.

### 2.1 The two populations

| population | n | below 0.5 | median | max |
|---|---|---|---|---|
| **consecutive** frames of one scene | 320 | **152** | 0.506487 | 13.382255 |
| **cross-scene** pairs (two renders) | 47796 | 2580 | 5.775949 | 16.801340 |

152 of 320 consecutive pairs failing at the rule's cut is the defect. P18
reported 20 of 40 per group; across all nine groups it is 152 of 320.

Consecutive-pair distances are not a cluster near zero — they run the whole
range:

```
offset  1: n=320  min=0.000000  p50=0.506487  p95=7.176339  max=13.382255
offset  2: n=311  min=0.000000  p50=1.181362  p95=12.997140
offset  3: n=302  min=0.000279  p50=2.972098  p95=13.179255
offset  5: n=284  min=0.141741  p50=5.620675
offset 10: n=239  min=0.843471  p50=6.243722
```

A cut cannot be placed to fire on genuinely-different renders and not on
adjacent frames, because the adjacent frames are not a tight cluster around
zero — they are a continuum reaching 13.38.

### 2.2 Do the populations separate at all?

Scoring every candidate cut on the merged distribution — consecutive pairs
*should* PASS, rerun pairs *should* FAIL:

```
BEST possible cut: above 0.000000 -> TPR 0.9969  FPR 0.0000  balance 0.9969
```

The best cut sits above **exactly zero** and is carried by a **single** real
rerun pair. `out/p13_probe` contains exactly four rerun pairs (`fr_a`/`fr_b`,
`full_a`/`full_b`, `full_b`/`full_r2`, `s1`/`s2`, `xc1a`/`xc1b` — these
directories are two runs of one render, and `rank_takes.py:35-38` says so).

**The two populations do not separate on this measure.** Every cut strictly
between 0 and the next consecutive value fires on pairs drawn from the wrong
population. This is the `collision` situation — an instrument with no
defensible threshold — and it is why **A (pick a better number) was not taken**.

### 2.3 How wide is the "wrong" zone?

Consecutive pairs strictly between 0 and 0.5: **137**. Pairs at exactly 0.0:
**15**. So the old cut discarded 137 pairs of moving frames and caught 15 pairs
of genuinely identical ones. The 15 remaining FAILs are the **entire** correctly
-flagged population — nothing was lost by moving the cut.

Values bracketing the old cut, both populations merged:

```
below: 0.494978 ... 0.498465  (x8, then x4)
above: 0.500140 (x3) 0.501535 (x3) 0.502232 0.503209 (x4)
```

The old cut sat in the densest part of the distribution. It was not near a
margin; it was in the crowd.

---

## 3. VERDICT: B, then the question the entry point can actually ask

### B — the docstring claimed a property the code did not have

`rule_duplicate`'s docstring said:

> Same measure and **SAME threshold as `take_ranker`** … Reusing the number
> rather than inventing one is the point: a second threshold for the same
> question is a second answer.

`take_ranker` holds no such threshold (§1). `rank_takes.py` holds it, and holds
it correctly, for a different comparison. Fixed: the Finding now names
`rank_takes.py` as where the 0.5 lives, and puts it in `extra['reference_cut']`
rather than in `extra['threshold']`, so a consumer can tell which number decided
the verdict.

### The threshold A would have needed does not exist

§2.2 shows it cannot be derived. So A was not available, and inventing one would
have violated the work order's explicit instruction.

**What `--frame-pair` actually supplies.** Grepped the whole repo: no CI
consumer, no script, no test calls `--frame-pair`. Every corpus measured here is
two consecutive frames of one scene, because that is the only way anyone has
ever used it (P18 established this; re-confirmed).

**What the rule now measures.** Whether the two inputs are the *same frame* —
distance exactly 0. The rule is the identity question, and it is the question
whose answer must be unambiguous for a pair run to proceed. The continuous
question ("did the sequence advance?") is not lost: `rule_freeze` runs in the
same pair run on the same two files, asks it directly on the pixels, and answers
for every interval regardless of size. P18's measurement that `freeze` sees
`difference == 0` and a pair run of one scene exits 1 because of it is
unchanged and is not re-litigated here.

The cut is therefore exact, and its warrant is stated rather than assumed:
two PNGs of the same array measure `0.0` exactly (asserted in the new guard, and
`rule_freeze`'s noise floor is measured at exactly 0 on the same principle).

**C was considered and is recorded as rejected.** It does not apply: the rule is
reachable, it does answer a question the entry point can be asked, and deleting
it would remove a report line without fixing the misattribution. It is not
deleted.

### What was NOT changed, and why

- `PINNED_LAYERS` — `duplicate` stays in `Motion`. The layer depends on the
  input (two rendered frames), not on the cut. Unchanged, asserted by the
  existing partition test.
- `rank_takes.py`, `take_ranker.py`, `select_takes.py` — the three-value
  duplication in §1a is recorded here and left for a separate decision.
- The four open items P18 listed — out of scope by instruction.

---

## 4. THE INSTRUMENT'S REAL LIMIT (measured, pinned in the guard)

A signature is a **mean absolute difference**, so pictures that differ by the
same amount in different places read the same. Measured on the constructed
backdrop:

| pair | distance |
|---|---|
| same array, re-encoded | 0.000000 |
| 300×60 ink bar moved **1 px** | **0.151228** |
| 300×60 bar moved 2 px | 0.297154 |
| 300×60 bar moved 3 px | 0.442104 |
| 300×60 bar vs 150×60 bar (same place, half the ink) | 9.157506 |
| 300×60 bar vs four shifted text rows | 18.548967 |

The old cut of 0.5 called a **one-pixel move** a duplicate on a 640-wide frame —
0.151228 is below it. That is the tightest collision on this backdrop. Note what
it does *not* show: the old cut was one pixel short on this fixture, not wildly
wrong. The pairs it actually got wrong are the 137 real consecutive corpus pairs
sitting strictly inside (0, 0.5), up to 0.494978, against only 15 pairs at
exactly 0.0.

Two claims were tried first and are **false**, recorded so they are not
re-asserted: two flat frames 1 luma apart measure **1.0**, not 0.0 (a flat
frame's signature *is* that luma); and a bar against a shifted word measures
**18.548967**, not the 0.040597 that a same-area pair reads.

---

## 5. WHAT A FUTURE CHANGE HAS TO RE-DERIVE

`tests/test_p19_duplicate_population.py` is behavioural: it calls the rule and
asserts verdicts, and never searches the source for a constant. Two claims are
checked structurally from the AST instead — that `take_ranker.m_duplicate` holds
no 0.5 (cv2 is not importable under 3.12, so the module cannot be imported here,
and a text search for "0.5" would also hit a docstring, which is the kind of
claim that was wrong to begin with).

If the signature is ever made richer — per-pixel, or block-wise — the two
populations may separate, and this task's conclusion stops holding. That is a
deliberate re-measurement, not a regression.
