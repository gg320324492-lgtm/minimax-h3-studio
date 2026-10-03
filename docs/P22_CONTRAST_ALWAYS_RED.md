# P22 — the contrast rule was a constant being reported as a per-frame measurement

> Execution record for `docs/WORKORDER_P22_CONTRAST_ALWAYS_RED.md`.
> Every number here was measured in this task; the measuring code is named beside it.

## 1. The defect

`rule_contrast()` took **no arguments**. It read `THEMES` — constants in
`design/themes.ts` — and returned the same 24-pair table whatever frame it was
handed. It was emitted into every `--frame` report, so `visual_qa.py --frame`
exited 1 on all 333 corpus frames for a fact no frame could have caused.

Measured before the change (`out/p22_probe/before_frame.txt`):

```
11 findings: 1 FAIL, 2 UNVERIFIABLE, 4 UNAVAILABLE
  [FAIL        ] contrast        value=8
```

and the FAIL is `theme_contrast`-shaped: 6 of the 8 failing pairs belong to
`premium-light`.

## 2. What the three roles are actually used for

The work order asked for this before any adjudication, and warned that a word
count is not an answer — this project has mis-read a same-named decoy four times
(`focus`, `ease`, `sizes`/`sizeBy`/`showArea`). So every consumer was read.

Measured with `out/p22_probe/measure_contrast.py` (M2), which greps the render
source and prints the line, not a count:

| role | sites | text sites | what the text sites are |
|---|---|---|---|
| `inkFaint` | 10 | **10** | Y tick labels `ChartFrame.tsx:320`, axis title `:339`, X category labels `:379`, PathMark value labels `types.tsx:244`, Slope end label `:344` and series name `:350`, Bubble category label `:429`, Heatmap cell value `:499` and its column/row labels `:523,:530`, DataColumns cell rank number `DataColumns.tsx:244` |
| `accent` | 8 | 3 | KpiHero eyebrow `KpiHero.tsx:84` (20px/500), KpiHero value suffix `:118` (78.88px), "chart: no values" `Chart.tsx:196` (34px). The other 5 are mark fills/strokes. |
| `positive` | 2 | **2** | KpiHero delta chip `KpiHero.tsx:139` (44px/700), RankTable row delta `types.tsx:593` (20px) |

**`inkFaint` is not a decorative shade.** All ten of its consumers are text
labels or data numbers. The decorative roles in this palette are named
differently — `grid`, `hairline`, `column`, `columnBright` — and **none of those
is among the six roles `rule_contrast` measures**. The reading the work order
flagged as possible ("it's the faintest ink, so 4.5:1 does not apply") is
falsified for this template.

`accent` is genuinely mixed: three text sites and five marks. `positive` is
text at both sites.

## 3. Why 4.5:1 is the right bar, and why that does not rescue `inkFaint`

WCAG SC 1.4.3's bar depends on **rendered** size, and
`s = scaleFor(w, h) = min(w/1920, h/1080)` (`design/tokens.ts:263`). Measured
across the three formats the delivered graphs actually declare
(`out/p22_probe/measure_perframe_fire.py`, Q0):

```
site                     role     declared    w  |      1920x1080 |      1080x1920 |      2560x1440 |  dark  vs 3.0  vs 4.5
ChartFrame.tsx:320       inkFaint   20.00px  400  |  20.00px text  |  11.25px text  |  26.67px LARGE |   2.83    FAIL    FAIL
types.tsx:499            inkFaint   20.00px  400  |  20.00px text  |  11.25px text  |  26.67px LARGE |   2.83    FAIL    FAIL
DataColumns.tsx:244      inkFaint   15.00px  400  |  15.00px text  |   8.44px text  |  20.00px text  |   2.83    FAIL    FAIL
KpiHero.tsx:84           accent     20.00px  500  |  20.00px text  |  11.25px text  |  26.67px LARGE |  11.78    PASS    PASS
KpiHero.tsx:139          positive   44.00px  700  |  44.00px LARGE |  24.75px LARGE |  58.67px LARGE |  10.86    PASS    PASS
```

Two things fall out, and they point in opposite directions:

* At `s=0.5625` — the format **6 of the 9 delivered graphs declare** — every
  `inkFaint` site renders 8.4–12.4px, so 4.5:1 is unambiguously the right bar
  and they fail it.
* At `s=1.333` they become 20–29px, i.e. large text, where the bar drops to
  3:1. **They still fail**: 2.83 (dark) and 2.16 (light) are below 3.0 too.

So `inkFaint` fails **both bars in both themes**. No size argument rescues it.
This is the fact that makes adjudication B unavailable here: there is no
WCAG-scope argument that would lower the bar for `inkFaint` without lowering it
below the one SC 1.4.3 sets for every other case as well.

`positive` is the opposite: it fails only in `premium-light`, only against the
text bar, and at every delivered format it renders large — where the applicable
bar is 3.0 and it passes at 3.71.

## 4. A finding that changes the picture: the corpus is all one theme

Measured over all 333 corpus frames (`out/p22_probe/measure_perframe_fire.py`,
Q1), by calling `detect_theme` on each:

```
corpus themes: {'premium-dark': 333}
```

**Six of the eight failing pairs belong to `premium-light`, and not one
`premium-light` frame has ever been rendered in this corpus.** The permanent
red was therefore asserting failures about a theme nothing in `out/` exercises,
while the two pairs that *are* exercised (`premium-dark/inkFaint`) fail for a
reason that has nothing to do with any frame either.

This is worth stating on its own: it is a coverage fact, and it is not the
defect — but it means "the gate has been red 333 times" never once meant "333
things are wrong".

## 5. Adjudication: A, and what it cost

**A — split it.** Not B: see §3, no WCAG-scope argument exists that helps
`inkFaint`, and the only way to get a green gate would have been to move the
number, which is the forbidden move. Not C: the red is real, but C requires the
per-frame gate to "know" it is known, and there is no way to encode that without
either an exemption list or a third verdict state — both of which leave a
constant able to fail a frame gate.

The split:

* `rule_contrast()` now **emits `theme_contrast`**, is reported by a new
  `--theme-contrast` flag, and is not emitted on the frame path at all. Its
  verdict is computed against both bars (4 pairs below 3.0, of which 8 below
  4.5 — the 4.5 count is still reported under its own key, so neither number
  can be quietly changed to flatter the other).
* `rule_contrast_frame()` **emits `contrast_frame`**, takes the frame, and
  reports **UNAVAILABLE** with the reason attached.

### 5.1 Why the per-frame half is UNAVAILABLE and not implemented

The work order's preferred answer was "split it up AND add a real per-frame
check", so this was measured rather than assumed. It cannot be built honestly.

Measured over 531,100,800 corpus pixels
(`out/p22_probe/measure_perframe_fire.py`, Q1/Q2):

```
percentiles of EVERY rendered pixel against its frame background:
  p1 1.026   p25 1.034   p50 1.046   p75 1.052   p95 1.070   p99 11.219

histogram, share of ALL pixels:
  [ 1.0, 2.0)  98.647%      [ 2.0, 3.0)   0.095%     [ 4.5, 6.0)   0.044%
  [ 3.0, 4.0)   0.042%      [ 6.0,10.0)   0.104%     [10.0,25.0)   1.054%

Q2. the naive per-frame rule — "any pixel below 3:1":
  frames where >=1% of pixels are below 3:1: 333 of 333
  frames where >=50% of pixels are below 3:1: 333 of 333
  per-frame share below 3:1: min 0.9621  median 0.9895  max 1.0000
  => PERMANENTLY RED on every frame
```

Two independent reasons, and both are measurements rather than arguments:

1. **The naive rule is a second permanently-red gate.** 333 of 333 frames, with
   ≥96% of pixels below 3:1 on every one.
2. **The population has no valley.** It runs 1.0→1.5 (97.765%), 1.5→2.0
   (0.882%), 2.0→3.0 (0.095%), 3.0→4.5 (0.056%), 4.5→6.0 (0.044%), 6.0→10.0
   (0.104%), 10.0→25.0 (1.054%). There is nothing for a cut to sit in between
   "the gridline this design intends" and "the label a reader must be able to
   read".

And the reason neither can be fixed by choosing a better instrument:

> Contrast is a property of a (foreground, background) **pair**, and a frame's
> pixels carry no foreground/background **role**. A glyph stem, a hairline and
> the backdrop ramp are all just a pixel. Separating them needs the mark layout
> from the chart options — the same missing input `overflow` names.

That is why it is UNAVAILABLE (the instrument was never built) rather than
UNVERIFIABLE (an instrument ran and could not decide). The distinction is this
file's whole vocabulary.

A third measurement points the same way
(`out/p22_probe/measure_frame_ink.py`): restricting the population to pixels
that are clearly a MARK rather than the ramp — contrast ≥ 2.0 against the
frame's own background — **32 of the 333 frames have fewer than 0.1% such
pixels**, i.e. no type at all. A rule of the form "how much of this frame is
readable ink" therefore has no defined value on a tenth of the corpus, quite
apart from not separating ink from gridline where type does exist.

**What would make it available**, so the next reader does not have to guess: the
renderer knows each role's rendered px (`size * scaleFor(...)`), so a decidable
per-frame contrast rule has to come from the graph and the declared format —
which is a `--props` question, the shape `rule_graph_scene_renderable` already
has.

## 6. How the gate knows "this red is not about this frame"

It does not need to know. **On the frame path the finding is not emitted**, so
there is nothing to misread. The fact exists, is still reported, and is reported
by the path whose subject it describes.

This is **separation by scope, not an exemption by name**:

* `FRAME_SCOPED_RULES` states which rules describe an artefact. It is a scope
  table, not a deny-list: anything not in it is reported on every path, so a new
  rule cannot be silently dropped from the frame report.
* The guard re-derives that set **by calling** every rule and inspecting its
  signature (`test_frame_scoped_rules_is_exactly_the_rules_that_take_a_frame`),
  so a rule that stops reading a frame fails the guard rather than inheriting an
  exemption nobody chose.
* `--frame --theme-contrast` together is allowed and prints both, but the exit
  code is the **frame's**, and the summary says so in words:
  `(of which 1 theme-level FAIL, NOT counted in this exit code: it describes
  design/themes.ts, not the frame)`.

## 7. Which of this project's four precedent shapes this is

The work order listed four accepted dispositions. This is the **second** one —
*"a threshold is mismatched to the question, so change the question it asks"* —
the same shape as `rule_duplicate`, which P19 moved off a cross-render 0.5 onto
the identity question its own entry point could be asked.

It is **not** "instrument good, criterion missing" (`collision`, still
UNAVAILABLE) — although the per-frame half *does* end at UNAVAILABLE, because
that half genuinely has no instrument. And it is not "the claimed property does
not exist" (fix the docstring), because the property was real: the palette does
fail 8 pairs, and that measurement is preserved exactly.

**Why it says the truth rather than turning red green:** no threshold moved
(`WCAG_TEXT` is still 4.5, `WCAG_LARGE` is still 3.0, both asserted as values),
and no palette value moved (`design/themes.ts` is byte-identical, sha256
`6cf58d0f…`). The palette is exactly as red as it was. What changed is which
path reports it — and the frame path lost a FAIL it was never entitled to,
while the theme path gained one it previously could not produce on demand.

## 8. Guard

`tests/test_p22_contrast_is_not_a_per_frame_gate.py`, 15 tests. Every claim is
reached by **running `vqa.main(argv)`** and reading the exit code and the
report. Nothing asserts that a string is in a source file, and nothing asserts
that a constant is merely *named* — `test_neither_wcag_threshold_moved` asserts
the value, so redefining `WCAG_TEXT = 2.0` while keeping the name fails.

It answers the work order's question directly:

> "If the palette were fixed tomorrow, would this gate go green?"

For the **frame** path the answer is *no, and it must not* — that path never
measured the palette, so fixing the palette cannot change it. For the
**theme** path the answer is *yes*, and `test_the_theme_path_still_reports_the_palette_finding_and_still_exits_one`
asserts the table can still go red, so a future change that made it permanently
green would be caught rather than inherited.

### Mutations (§3 of the work order)

Each was proven in the file *before* the tests were read, per protocol §5.1.

| # | mutation | landed check | result |
|---|---|---|---|
| 1 | `WCAG_TEXT = 4.5` → `2.0` | runtime read: `WCAG_TEXT = 2.0`, `failing_text_bar = []` | **killed**, 5 failed |
| 2 | `rule_contrast_frame` returns `FAIL` instead of `UNAVAILABLE` | runtime read: `verdict = FAIL, trusted = True` | **killed**, 7 failed |
| 3 | re-attach `theme_contrast` to the frame path | CLI run showed `1 theme-level` on a `--frame` report | **killed**, 4 failed |

Mutation 1 raw `-rf`:

```
FAILED ::test_the_theme_finding_still_names_the_eight_pairs_and_the_worst - A...
FAILED ::test_neither_wcag_threshold_moved - AssertionError: WCAG_TEXT moved....
FAILED ::test_self_test_passes - AssertionError: visual_qa self-test failed:
FAILED ::test_contrast_is_red_on_this_palette_and_counts_its_pairs - Assertio...
FAILED ::test_thresholds_match_the_measured_distributions - assert (2.0 == 4.5)
5 failed, 70 passed, 1 skipped in 8.64s
```

Mutation 2 raw `-rf`:

```
FAILED ::test_a_clean_frame_no_longer_fails_on_the_palette - AssertionError: ...
FAILED ::test_the_frame_path_reports_the_contrast_hole_rather_than_hiding_it
FAILED ::test_the_theme_flag_does_not_change_the_frame_exit_code - Assertio...
FAILED ::test_contrast_frame_is_the_same_verdict_on_frames_that_differ - Asse...
FAILED ::test_json_mode_keeps_the_separation - AssertionError: assert 'FAIL' ...
FAILED ::test_self_test_passes - AssertionError: visual_qa self-test failed:
FAILED ::test_contrast_really_takes_no_input_and_really_fails - AssertionErro...
7 failed, 68 passed, 1 skipped in 9.10s
```

Mutation 3 raw `-rf`:

```
FAILED ::test_a_clean_frame_no_longer_fails_on_the_palette - AssertionError: ...
FAILED ::test_json_mode_keeps_the_separation - AssertionError: assert ('contr...
FAILED ::test_the_cli_does_not_emit_the_unavailable_findings_twice - Assertio...
FAILED ::test_json_output_is_byte_level_parseable - AssertionError: the human...
4 failed, 71 passed, 1 skipped in 8.76s
```

**No mutation survived.** Each was killed on a verdict or an exit code, not on a
text match: mutation 1 on `WCAG_TEXT == 4.5` and on the eight-pair count,
mutation 2 on `UNAVAILABLE` vs `FAIL` read off a real call, mutation 3 on the
headline guard asserting a clean frame exits 0. Mutation 3 is the one worth
keeping — it is the original defect wearing the new code's name, and the guard
that caught it is the work order's own question.

## 9. Numbers

| | value |
|---|---|
| baseline suite | `443 passed, 3 skipped` |
| after | `458 passed, 3 skipped` |
| delta | +15 (the new guard file), 0 regressions |

Baseline was measured before any edit, not taken from the work order.

## 10. What this does NOT do

* **No palette value changed.** `design/themes.ts` is byte-identical
  (`6cf58d0f52104c6a0f6883d5513f79f0351c376b7670a416aec059a05c99df5f`).
  `inkFaint` really is below both WCAG bars in both themes and
  `premium-light/accent` is 3.23 against a 4.5 text bar. **Recolouring is a
  design decision and is out of scope; this is the recommendation, not the
  implementation.**
* **No threshold moved.** `WCAG_TEXT = 4.5`, `WCAG_LARGE = 3.0`.
* `collision` and the other three `UNIMPLEMENTED` placeholders are untouched.
* P19's `SIGNATURE_EQUAL`, P20's `DUP_THRESHOLD`, P21's
  `graph_scene_renderable` are untouched.

## 11. Two things this changed that a reader should know

* **Visual went from 2 rules to 3, and its `THIN_LAYERS` entry was DELETED.** The
  entry went away because the thin set is defined by count (`<= 2`) and Visual
  now holds 3 — but Visual holds 3 rules of which **exactly one** (`blur`) can
  currently say anything about a frame. The count stopped being a proxy for
  coverage. Leaving the entry would have been the same mistake as the one this
  task fixes, one level up, so `qa_layers.py` says so in the comment where the
  entry used to be rather than claiming "Visual: 3 rules, fine".
* **`test_the_two_qa_scripts_are_byte_identical_to_head` no longer pins
  `visual_qa.py`.** It is not re-baselined to the new hash. A re-baselined hash
  records a hash and no argument, and the next reader could not tell this
  deliberate decision change from a rule quietly retuned. `qa_report.py` keeps
  its pin (untouched here), and `visual_qa.py` is instead held by four
  behavioural guards — no threshold moved, no palette moved, the rule still
  reads no frame, and every other rule's layer is unchanged.

## 12. Reproducing the measurements

```
py -3.12 out/p22_probe/measure_contrast.py         # 24-pair table + consumption sites
py -3.12 out/p22_probe/measure_perframe_fire.py     # sizes, histogram, naive-rule firing rate
```

Both require the gitignored corpus in `out/p13_probe` (333 frames). The vectorised
contrast path asserts itself against `vqa.contrast_ratio` on 4000 random pixels
per theme/background pair before it is used, so the fast path cannot silently
become a different function than the rule's.