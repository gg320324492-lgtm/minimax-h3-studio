# P52 — `rule_font_size` measured the frame and then decided on the caller's argument

> Execution record for `docs/WORKORDER_P52_FONT_SIZE_VERDICT.md`.
> Every number here was measured in this task; the probe that measured it is
> named beside it. Where a number is inherited rather than measured, that is
> said.

## 1. The defect, re-measured on the fixture P22 uses

`visual_qa.py:665` decided on

```python
absolute_short = declared_px < MIN_TYPE_PX
verdict = FAIL if absolute_short else PASS
```

while `median` — measured off the pixels two lines above — entered only the
ratio. Measured by calling `rule_font_size` on the exact frame
`tests/test_p22_contrast_is_not_a_per_frame_gate.py::_clean_frame` builds:

```
trusted True   worst 0.0   bands [20]   median 20.0
declared=20       verdict=PASS         value=1.0
declared=5        verdict=FAIL         value=4.0
declared=11.25    verdict=FAIL         value=1.7778
declared=12       verdict=PASS         value=1.6667
declared=1000     verdict=PASS         value=0.02
declared=None     verdict=UNVERIFIABLE
```

One frame, 389 identical pixels, five verdicts. The gate moves when a number on
the command line moves.

## 2. The obvious fix was measured and rejected, not argued away

Replacing `declared_px` with the measured `median` is what the work order warned
against, and the warning is right. Measured over all 333 frames of
`out/p13_probe` (`e:/tmp_p52/measure_font_bands.py`, the same corpus P22 used):

```
trusted+measured 298   untrusted 12   trusted-but-no-bands 23

  bands per frame        min 1   median 3   max 6
  band heights     min 1.0   median 51.0   max 411.0
  share of bands below 12px per frame   min 0.0000  median 0.2500  max 1.0000

FIRE RATE over the 298 measured frames
  median  < 12                    52   17.4%
  p25     < 12                    84   28.2%
  p10     < 12                   131   43.9%
  min     < 12                   199   66.8%   <- two thirds of the corpus
  n_below_12 >= 3                 15    5.0%
```

Three measurements kill it, and none of them is a preference.

**(a) The bands are not type.** `out/p13_probe/f760_a.png` is a calendar scene
whose only type is a 45px "2026-09" title. Its bands are

```
rows 324..368  h= 45   x 856..1063    <- the title
rows 422..703  h=282   x 716..1203    <- the day tiles
rows 706..769  h= 64   x 736.. 850    <- the last tile row
```

`median` is 64px: the tiles, not the type. Two of the three bands are not text.

**(b) There is no median to be robust.** A frame carries 1..6 bands (median 3).
Measured (`e:/tmp_p52/measure_hijack.py`, over the 283 frames with ≥ 2 bands):

```
dropping the single LARGEST band flips the verdict   58 of 283  (20.5%)
dropping the single SMALLEST band flips the verdict  42 of 283
mean |median shift| from dropping one band          68.7px     max 199.5px
adding ONE 2px band flips PASS -> FAIL               58 frames
```

The cleanest case is a real corpus frame. `out/p13_probe/full_a/0002.png`
measures bands `[6, 201]`, median 103.5px; add one 2px accent rule and it
measures `[2, 6, 201]`, median 6.0px — **PASS becomes FAIL on a one-pixel design
change.** That frame is also the one
`tests/test_p24_per_job_baseline.py:384` requires to exit 0.

**(c) There is no valley at the bar.** 199 of 298 frames carry a sub-12px band,
so "any ink below 12px" is red on two thirds of the corpus; 204 of 298 have a
median ≥ 24px, so "the median is below 12px" is decided by whichever single band
happens to be the median. Real frames sit exactly on the cut —
`fr_a/0016.png` measures `[9, 12, 17]`, median 12.0, and 21 frames sit within 2px
of the bar.

This is P22 §5.1's finding in a different instrument: a cut with nothing for it
to sit in between. And it is `docs/P16_REFERENCE_BENCHMARK.md` §3 row 8, which
reached this verdict for this dimension before the rule was written — telling
type from the marks around it needs glyph recognition, and this project has
none.

## 3. Adjudication: C, in P22's shape

**A** is dead by §2. **B** is unavailable for a reason worth stating separately:
`declared_px` arrives only through `--declared-px`. The graph does not carry a
declared type size — `studio/src/schemas/showcase-v1.ts:227` types it
`z.record(z.string(), z.unknown()).optional()`, an opaque record with no `size`
field and no key anyone agreed on. So the declaration's only home is the
caller's argument, and any gate built on it is a gate the caller operates.

So the same move P22 made for `contrast`:

* `rule_font_size` still **measures the frame** and still reports it — the band
  list, its median, the declared size and the ratio all travel in `extra` as
  data a machine can read (the P23 convention).
* It reports **UNAVAILABLE**, which in this file's vocabulary means the
  instrument for this question was never built. (UNVERIFIABLE — "an instrument
  ran and could not decide" — would exit 1 and make `--frame` permanently
  non-zero, which is the mistake P22 fixed next door.)
* `value` is `None` and `trusted` is `False`, matching `rule_contrast_frame`.
  A number on a finding whose instrument does not exist gets consumed as a
  measurement.
* `declared_px` is **still read** — it is the denominator of a real ratio — and
  it can no longer move a verdict, because there is no verdict left to move.

**Why it is decidable.** It is not a measurement dressed as a verdict, which is
the point: the question "is the type on this frame below 12px" has an
instrument-shaped answer available only as bands, and §2 measures that no cut
through the bands separates the two populations. UNAVAILABLE is the true
reading, not a shrug.

### The positive/negative classes, and why there are none

A frame carrying one 7px band and a frame carrying one 201px band are about as
opposite as this instrument can make them. **They get the same verdict**, and
that is the finding rather than a gap in one: a criterion that separated them
would be applying the readability bar to marks. `test_frames_whose_type_differs_do_not_produce_a_verdict`
pins it, and mutation 2 below shows it going red the moment someone adds the
cut.

### False positives and false negatives

There are none, because there is no verdict. The costs are elsewhere and are
real:

* **Coverage.** `--frame` no longer reports anything that can catch unreadable
  type. It says so instead of implying otherwise, which is the P21 defect class
  P22's guard was written for.
* **The measurements are not gated.** A reader who wants "did the render honour
  the declared size" now has to read `extra['measured_over_declared']` and
  supply the tolerance themselves. Before, the tool supplied one and it was
  `declared_px < 12`, which answered a different question.

## 4. ⚠️ "Is the declared size too small" still caught? — the required answer

**No, and this is a stated loss. Here is the measurement that says the loss is
of a fiction rather than of a capability.**

The defect the docstring names is the chart value labels being declared
`20 * s`, which is 11.25px at `s = 0.5625`. For the rule to catch that, a caller
has to pass 11.25. Pass the design token instead. Measured by loading the
**pre-P52** rule from its byte snapshot and handing it a frame whose type
renders at 11.25px (an 11px band, pixels being integers):

```
PRE-P52 rule, on a frame whose type renders at 11.25px
  measured bands: [11]   median 11.0
  --declared-px 20.0   ->  PASS   (ratio 0.550)
  --declared-px 11.25  ->  FAIL   (ratio 0.978)
```

⚠️ The `20` is what the graph actually declares, and the `11.25` is a number the
caller computed by hand. **The rule caught the defect only when the caller
volunteered the offending value, and sailed past it on the spelling the graph
really uses.** Before this change it was not a gate against unreadable type; it
was a gate against a caller who disagreed with the 12px bar.

So the honest accounting is: this change removes a FAIL that a caller controlled
and restores nothing in its place. **What would restore it**, so the next reader
does not have to guess, and neither of which is a font change:

1. a **declared type size in the graph** — a typed `size` under
   `style_bible.typography`, so the number being judged is read from the graph
   and not from argv (P48's own test said this: *"needs the declared size from
   the graph rather than from argv"*); and
2. a **scale the frame itself supplies** — `scaleFor(w, h)` is computed from the
   frame's own size, so `declared * scaleFor(measured)` is decidable with the
   frame as one side, exactly the `rule_aspect` shape. With both, the defect
   above FAILs at `--declared-px 20` on a 1080x1920 frame, for the right reason.

Neither is in this commit. `typography` being `record<string, unknown>` means
building (1) now would be inventing a contract — which is the
`chart.sizes` / `sizes` shape P48 refused, and which the queue already holds.

## 5. The P22 test: it was **not** red, and why

The work order expected `tests/test_p22_contrast_is_not_a_per_frame_gate.py:103`
to go red, because it passes `--declared-px 20`. **It does not go red, and the
reason is a measurement, not luck:**

`_clean_frame` draws two bars at rows 50..69, so its measured median band is
**exactly 20** — the same number it declares (§1 above). Any criterion keyed on
the measured median would also return PASS there. Both P22 tests that pass
`--declared-px 20` (lines 103 and 185-187) therefore keep exiting 0, and the
third, at line 131, asserts `code == 1` because `aspect` is UNVERIFIABLE
without `--props` — `font_size` leaving UNVERIFIABLE does not change that.

Measured, not inferred:

```
test_a_clean_frame_no_longer_fails_on_the_palette ... PASSED
test_the_frame_path_reports_the_contrast_hole_... PASSED
test_the_theme_flag_does_not_change_the_frame_exit_code ... PASSED
```

**No assertion was weakened to achieve this.** The three tests that *did* go
red were the three that pinned the defect itself, and each was replaced with an
assertion of the new contract rather than deleted:

| file | was | now |
|---|---|---|
| `tests/test_visual_qa.py` | `test_font_size_fails_below_the_readability_bar` — one frame, `declared_px` 20 vs 11.25, assert PASS then FAIL | `test_font_size_reports_the_bands_and_gates_on_neither_side` — asserts the measurement is present, `value is None`, and that the verdict is identical across declared sizes |
| `tests/test_visual_qa.py` | `test_font_size_reports_unverifiable_without_a_declared_size` | `test_font_size_reports_without_a_declared_size` — no declared size no longer blocks the *reporting*, only the ratio is absent |
| `tests/test_p48_reaccept.py` | `test_rule_font_size_verdict_tracks_the_argument_not_the_frame` | `test_rule_font_size_no_longer_decides_on_the_argument`, on the same fixture, per that test's own failure message |

⚠️ **P48's file changed, and the work order's "do not touch" list does not name
it — but its sha256 is on the watch list, so it is reported here.** The old
test's assertion message read: *"If it now measures the frame, delete this
characterisation and replace it with one that asserts the frame decides the
verdict."* It does not measure the frame (§2), so the replacement asserts the
measured truth instead, and says so in its own docstring. Nothing else in
`tests/test_p48_reaccept.py` was touched.

## 6. Guard

`tests/test_p52_font_size_verdict_is_not_the_caller_argument.py`, 9 tests.
Every claim is reached by calling `vqa.main(argv)` or `vqa.rule_font_size(...)`
and reading the verdict, the exit code and the report. Nothing greps the source
and nothing asserts a name merely exists, so no test can pass on a machine that
never ran the probe.

`test_the_rule_still_measures_the_pixels_it_is_handed` is what stops "no
verdict" from being indistinguishable from "not looking": two frames that differ
must report different measurements.

The fixtures that matter, built in the file so no test depends on the gitignored
corpus: `_MIXED` draws the two rectangles that reproduce `full_a/0002.png`'s
`[6, 201]` bands, and `_MIXED_PLUS_RULE` is that frame plus one 2px accent rule,
giving `[2, 6, 201]`. Every test that reads a band asserts the band it expected
first, so a fixture that quietly stopped producing one fails loudly instead of
passing on nothing.

### Mutations

| # | mutation | result | killed on |
|---|---|---|---|
| 1 | reinstate `FAIL if declared_px < MIN_TYPE_PX` | **killed**, 5 failed | the headline test: *"the verdict followed `--declared-px`. It is `['FAIL', 'PASS']` across declared sizes 5, 11.25, 12, 20 and 1000 on ONE frame with no pixel changed"* |
| 2 | `FAIL if median < MIN_TYPE_PX` — the obvious fix | **killed**, 5 failed | *"a single 2px accent rule moved the verdict: PASS -> FAIL"* and *"the bands alone decided the verdict (PASS vs FAIL)"* |
| 3 | the criterion always PASSes | **killed**, 3 failed | `assert 'PASS' == 'UNAVAILABLE'`, three times |

Mutation 1 raw `-rf`:

```
FAILED ::test_the_verdict_is_identical_on_one_frame_at_every_declared_size - A...
FAILED ::test_the_declared_size_moves_the_ratio_and_nothing_else - Assertion...
FAILED ::test_the_finding_carries_no_number_and_claims_no_trust - Assertion...
FAILED ::test_it_is_unavailable_and_not_unverifiable - AssertionError: assert ...
FAILED ::test_every_declared_size_reaches_the_report_with_its_own_ratio - As...
5 failed, 4 passed in 21.68s
```

Mutation 2 raw `-rf`:

```
FAILED ::test_the_finding_carries_no_number_and_claims_no_trust - Assertion...
FAILED ::test_it_is_unavailable_and_not_unverifiable - AssertionError: assert ...
FAILED ::test_one_more_2px_accent_rule_does_not_move_the_verdict - Assertio...
FAILED ::test_frames_whose_type_differs_do_not_produce_a_verdict - Assertion...
FAILED ::test_every_declared_size_reaches_the_report_with_its_own_ratio - A...
5 failed, 4 passed in 20.51s
```

Mutation 3 raw `-rf`:

```
FAILED ::test_the_finding_carries_no_number_and_claims_no_trust - Assertion...
FAILED ::test_it_is_unavailable_and_not_unverifiable - AssertionError: assert ...
FAILED ::test_every_declared_size_reaches_the_report_with_its_own_ratio - As...
3 failed, 6 passed in 22.01s
```

**No mutation survived**, and each was killed on a verdict read off a real call —
not on a string in a source file, and not on an exception escaping a probe.

⚠️ **One honest weakness in mutation 3**: a rule that unconditionally returns
PASS *satisfies* the headline invariance test, because "the same on every call"
is trivially true of a constant. It is the three assertions on the verdict being
UNAVAILABLE and value-less that kill it. The invariance test alone is not
sufficient, and this file should not be read as claiming otherwise.

Every mutation was reverted from a byte snapshot, and the hash was checked after
each one (§9).

## 7. What this does NOT do

* **No threshold moved.** `MIN_TYPE_PX = 12.0` is unchanged and still asserted
  by `tests/test_visual_qa.py`. Nothing was retuned to make a number go green —
  there is no number to move.
* **`--declared-px` was not removed.** It is still a CLI flag, still read, and
  still produces the ratio. It is no longer able to decide anything.
* **The other 13 rules are untouched.** The diff to `visual_qa.py` is
  `rule_font_size` plus one new module constant.
* ⚠️ **`studio/scripts/qa_layers.py:270` is now stale prose** — it says
  `font_size` is "UNVERIFIABLE on all 333 corpus frames when no --declared-px is
  supplied". That is no longer true. The file is outside this work order's
  edit scope and no test asserts on the string, so it was left alone rather than
  edited silently; it is flagged here instead.

### 7.1 ⚠️ An incidental regression this change caused, and the fix

Adding 55 lines above `visual_qa.py:644` moved every line number below it. Two
citations into that file were live, and one of them the guards could not see:

| site | was | now | how it was found |
|---|---|---|---|
| `tests/test_p13_scene_cache_facts.py:257` → `ap.add_argument('--props', …)` | `:1501` | `:1556` | ⚠️ **not caught by any test** — `:1501` now names `ck('backdrop model is UNTRUSTED…')`, which is still code, and the guard only asks "is it code", never "is it the right code". Found by enumerating every `visual_qa.py:NNN` citation in the tree and diffing each target against the byte snapshot. |
| `tests/test_line_refs_land_on_code.py` negative control → a blank line | `:751` | `:137` | caught by `test_the_criterion_can_still_say_no`, because P52 turned `:751` into the closing quote of `rule_contrast`'s docstring and the fixture stopped reproducing the defect it exists to reproduce |

Both are fixed, and the fixture's docstring records that the target was
re-pointed and why, so the next reader is not left with a bare number. `:137` is
inside the verdict-constant block, above every line P52 touched, and was blank
both before and after.

⚠️ The second row is the guard working as designed, and it is worth stating
plainly: a line-number citation is an assertion no test can check, and the one
the guard could check was caught while the one it could not was not.

## 8. Numbers

All runs: serial (no `pytest-xdist`, and this tree carries no pytest config),
`TMPDIR`/`TEMP` pointed at `E:\tmp_p52`, `test_take_selection_behaviour.py`
ignored, and the render scratch checked beforehand — `out/p14_guard_scratch`
absent and no `render-*` directory anywhere under `out/` before the first run
and after the last.

| | value |
|---|---|
| baseline, measured **before any edit** | `772 passed, 4 skipped in 559.41s` |
| after (first attempt) | `1 failed, 780 passed, 4 skipped in 651.46s` |
| — the one failure | `test_line_refs_land_on_code.py::test_the_criterion_can_still_say_no`, §7.1 |
| after (final) | **`781 passed, 4 skipped in 611.78s`** |
| delta vs baseline | **+9** — the new guard file, nothing else |

⚠️ The work order warns that this machine's full suite gives a different failure
set on each of three consecutive runs. **My baseline run was clean and green and
I did not reproduce that instability**; the post-change run reproduced a real
failure of mine, not a flaky one. Stated rather than glossed: my baseline is one
run, and I cannot claim the suite is stable on this machine either way.

## 9. sha256

Recorded before any edit and compared after the last, as the work order asks:

| file | before | after |
|---|---|---|
| `studio/scripts/visual_qa.py` | `1674d5e71e98207c43a4b5b378db5525…` | `62a76c59906c5cb54117d3f8837b62d5…` — changed, by this task |
| `tests/test_p22_contrast_is_not_a_per_frame_gate.py` | `da3ac3beb28eace37c371fbe8f2d00b7…` | `da3ac3beb28eace37c371fbe8f2d00b7…` — **byte-identical** |
| `tests/test_p48_reaccept.py` | `cb234af7cbbd572b918a7494f9fd4002…` | `f7d56a2fa85f5651f2a465e97b35739c…` — changed, per §5 |

`visual_qa.py` line endings were measured before the first edit — **0 CRLF,
1645 LF** — and after the last: **0 CRLF, 1697 LF**. The edits introduced no CRLF,
so a CRLF-count check would not have caught it and it was checked anyway.

## 10. Files changed

| file | what |
|---|---|
| `studio/scripts/visual_qa.py` | `rule_font_size` rewritten; one new module constant `FONT_SIZE_NO_FRAME_CRITERION`. Nothing else. |
| `tests/test_p52_font_size_verdict_is_not_the_caller_argument.py` | **new** — the guard, 9 tests |
| `tests/test_visual_qa.py` | two tests that asserted the defect, replaced per §5 |
| `tests/test_p48_reaccept.py` | one test replaced per its own failure message, per §5 |
| `tests/test_p13_scene_cache_facts.py` | one drifted citation re-pointed, per §7.1 |
| `tests/test_line_refs_land_on_code.py` | one negative-control fixture re-pointed, per §7.1 |
| `docs/P52_FONT_SIZE_VERDICT.md` | **new** — this file |

## 11. Reproducing the measurements

```
py -3.12 e:/tmp_p52/measure_font_bands.py     # band distribution + fire rates
py -3.12 e:/tmp_p52/measure_hijack.py         # one-band flips, knife-edge frames
py -3.12 e:/tmp_p52/mutate_p52.py             # the three mutations, byte-restored
```

The two probes need the gitignored corpus in `out/p13_probe` (333 frames); the
mutation harness needs the byte snapshot it restores from and leaves
`visual_qa.py` byte-identical.