# P41 — a VLM criterion: what to look FOR, not how to judge

> Ledger item **1.3 / 10.2**. Replaces the "多维评分" design in 10.2, which P17
> already ruled undecidable. This document records what was measured, what was
> rejected, and what the guard holds. It is NOT a quality judgement of the film
> and it makes none: P17 ruled `premium product film` undecidable (no
> instrument, no corpus, no positive class) and nothing here reopens that.

---

## 1. What 10.2 asked for, and why it was not built

10.2 asked for *每 scene 抽 5 帧，多维评分 + problems + repair_suggestions*.

"多维评分" is a score with no instrument and no positive class. This repo has
now refused that shape three separate times:

| refusal | what was missing |
|---|---|
| `collision` | a detector exists (`chart_geometry.py`), no threshold |
| `flicker` (P23) | no positive class |
| `rule_contrast_frame` (P22) | population does not separate (97.8% of pixels in one band) |

Building the score would have been a fourth refusal, this time in code, and the
score would have read green while measuring nothing.

## 2. The criterion that was built instead

One question, with an answer derivable from the graph:

> **the graph says this scene's chart prints `48.2M` — is that text on the frame?**

### Why it is decidable

- **An instrument.** `qwen2.5vl:7b` (5.97 GB) over a local ollama. Measured
  below, on frames decoded from the delivered `out/charts_demo.mp4`.
- **An expected value, not a taste.** The string comes from the graph by way of
  a port of the renderer's own `formatValue` (`scale.ts`), pinned to the
  shipped implementation by a test that runs both sides over a 192-row corpus.
- **No threshold.** The answer is a string identity: present or not. Nothing is
  invented, so nothing can be mis-cut. This is the property that makes P21's
  `graph_scene_renderable` worth having, and it is why this rule has a verdict
  where `collision` still does not.

### Why this question and not "is the frame good"

`locked_fields.py` already asks this shape of question about a JSON document:
*did the repair move a number the graph declared?* This asks it about a
**rendered picture**, where the claim has been through a formatter, a layout, a
font stack and a video codec before anyone looks at it. That distance is the
entire reason a second instrument earns its place.

### False positives and false negatives — stated, not hoped for

- **False positive (the dangerous one):** the expectation is wrong, so a correct
  frame FAILs. Two real sources, both now guarded: (a) the Python formatter
  drifting from `scale.ts` — pinned by `test_the_python_formatter_matches_the_
  renderer_it_mirrors`, which compares 192 rows row-by-row; (b) asking for a
  value the renderer never drew — which is exactly what happened, below.
- **False negative:** the model says YES about a string that is not really
  legible. Measured at 0/44 on the positive probes, including 18 two-digit
  heatmap cell values.
- **Both are bounded by a negative control.** The model was asked about a blank
  frame and a 1px-flattened frame, where no text exists at all: 8/8 correct NO.
  A reader answering without looking could not produce that.

## 3. The open question was measured and REJECTED

The obvious richer form is "list every number in this image", scored against a
Python port of `formatValue`. It was built and measured:

```
f0075 c01_bar  hit 5/5   missing=[]                 extra=[]
f0225 c02_line hit 0/12  missing=[22,31,28,...,108]  extra=[0,10,...,100]
f0375 c03_area hit 1/8   missing=[12,19,16,...]      extra=[20,30,42,50]
```

**The 0/12 is not a VLM failure. The VLM was right.** `c02_line` declares
`showValues: false`, so its data values are never printed — only axis ticks are,
which is precisely what the model listed. Scoring an open question requires a
Python reproduction of every renderer decision (ticks, `showValues`,
`showCellValues`, end labels, per-type branches); that mirror is a new source of
false positives, and a criterion that can be wrong about a correct artefact is
worse than no criterion. **So the closed question is the shipped one**, and
`expected_strings` carries the graph's declaration rather than a reconstruction
of everything the renderer chose to draw.

> **Correction to the record:** the three `f0075` lines above were scored
> against a frame I had mis-read by eye as a slope chart. It is `c01_bar`
> (confirmed by cropping). The model was right and my annotation was wrong, in
> the same direction as the `c02_line` result — which is why the open form is
> rejected for two independent reasons rather than one.

## 4. Measured accuracy — 44/44 hand-verified probes

Truth was established by reading the frames, not by asking the model.

| probe set | correct |
|---|---|
| 18 two-digit heatmap cell values (printed) | 18/18 |
| 6 near-misses, ±1 off a printed value | 6/6 NO |
| 4 absent values on that frame | 4/4 NO |
| 6 values from a DIFFERENT scene of the same film | 6/6 NO |
| 2 nonsense strings (`12345678`, `QWERTY`) | 2/2 NO |
| 8 on a blank frame / a 1px-flattened frame | 8/8 NO |
| **total** | **44/44** |

An earlier run of 20 probes on mixed frames scored 17/20. All three misses were
the `f0075` annotation error above, where the truth was mislabelled — the model
answered correctly for the frame it was actually shown. The 44/44 above is the
post-correction, hand-verified figure and the only one quoted.

**Reproducibility is measured, not assumed.** Same question, same frame, twice,
at `temperature: 0`, `top_k: 1`, `seed: 42`: **7/7 byte-identical answers**.
The seed and greedy options are what buy this, and
`test_reproducibility_is_asserted_not_assumed` asserts the options have not been
loosened.

**Cost — measured, not extrapolated.** Cold load 66.7 s (first call of a
session). With the model resident, 42 sequential probes: **4.5 s wall, 0.106 s
per probe** (min 0.12, max 0.19). The work order forbids extrapolating these
numbers; the 42-probe figure was run end to end. The two single-frame timings
quoted in the command window (64.2 s cold, ~0 s resident) are consistent with
it, but were not used to produce it.

## 5. What this module refuses to do

- It does not score beauty, rank takes, or say a frame is good. A frame that is
  well-composed and prints every declared number PASSES; a frame that is hideous
  and prints them all also PASSES. That narrowness is the point — it is the
  narrowness `rule_aspect` has.
- It is not in `FRAME_SCOPED_RULES`. It needs a model and a graph; registering
  it as a pixel rule would make every `--frame` run on a machine without ollama
  report a verdict it cannot support.
- It does not download, install or vendor a model. `qwen2.5vl:7b` was already
  on this machine.

## 6. UNAVAILABLE is a verdict, never a fallback

`ollama` is an external process and is simply not running on CI, or on the next
machine, or after a reboot. Every gate in this repo that failed that way
reported green: `visual_qa` silently skipping, `render.mjs` ignoring a flag, the
props gate idling.

So `unavailable_reason()` returns a **reason and never a verdict** — there is
no branch of it that returns PASS — and it checks the model list rather than
just the port, because a 200 from an ollama with no model pulled is a health
check that passes on an empty room. Any unanswered probe makes the whole rule
UNAVAILABLE with the reason in `detail` and in `extra['unanswered']`, and
`main()` exits 1 on UNAVAILABLE as well as on FAIL.

The finding carries its reason in the return value, not in a log line — the
shape P36's `unapplied` established.

Measured against the live model, not only against the transport double:

```
$ python studio/scripts/vlm_critic.py f0825.png --expect 88 --expect 95 --expect 34
  [PASS] frame_shows_expected_text  value=0        EXIT=0

$ python studio/scripts/vlm_critic.py f0825.png --expect 88 --expect 777
  [FAIL] frame_shows_expected_text  value=1
         ... 1 expected string(s) are NOT on the frame: d0825.png/777
                                                 EXIT=1

$ python studio/scripts/vlm_critic.py f0825.png --expect 88 --host http://127.0.0.1:1
  [UNAVAILABLE] ... [UNTRUSTED INSTRUMENT]
         First reason: no ollama at http://127.0.0.1:1 ...; a VLM judgement is
         UNAVAILABLE, never a pass        EXIT=1

$ python studio/scripts/vlm_critic.py f0825.png --expect 88 --model no-such-model:1b
  [UNAVAILABLE] ... ollama is running but has no model named 'no-such-model:1b'
                                                 EXIT=1
```

## 7. The guard

`tests/test_p41_vlm_critic.py` calls the criterion with the model replaced at
the `transport=` seam. **No test opens a socket, loads a model, or needs a
GPU**, because a guard that needs 6 GB of weights is a guard that is red on CI
for a reason unrelated to the code.

That claim was tested rather than asserted. Running the guard with the host
deliberately broken (`VLM_CRITIC_HOST=http://127.0.0.1:1`) turned **three**
tests red — the reachability check ran before the transport seam, so a replaced
judge was still asked whether a server was alive. A guard that can be broken by
an environment variable it never intended to read is a guard that would go red
on CI, which is the failure the guard exists to avoid. `unavailable_reason` now
short-circuits when a transport is supplied, on the grounds that **a judge that
has been replaced cannot be absent**. Both settings now give `19 passed`:

```
$ python -m pytest tests/test_p41_vlm_critic.py -q
19 passed
$ VLM_CRITIC_HOST=http://127.0.0.1:1 python -m pytest tests/test_p41_vlm_critic.py -q
19 passed
```

**The test that pins this was itself a dead test twice, and only a mutation
found it either time.** The first version set `VLM_CRITIC_HOST` *after* import,
but `DEFAULT_HOST` is bound by `os.environ.get(...)` at module scope, so
nothing changed and the assertion ran against a live ollama. The second patched
the module attribute and still called without `host=`, because `probe_text`'s
`host` is a default argument evaluated at def-time — so it too reached the live
host. Both versions **passed with the fix deleted**. The third passes
`host=DEAD_HOST` at the call site and fails with the fix deleted:

```
E  AssertionError: with the host unreachable and the judge replaced, the rule
   reported UNAVAILABLE. The guard must not depend on a model being present.
```

Which is the argument for proving a mutation is dead before believing anything
else: two of the three versions of the test written specifically to stop a guard
depending on a model were themselves depending on one.

Nothing in it asserts that `qwen` appears in the source or that a field is named
correctly — this project has been fooled by text-existence assertions eleven
times, and a module can name the model and be reached by nobody.

Three mutations, each **proved to have landed before the result was read**,
each reverted from a sha256 snapshot, each red for the stated reason rather
than for a `NameError`:

| # | mutation | where it landed | guard |
|---|---|---|---|
| 1 | absent judge reports `PASS` | `rule_frame_shows_text`, `if absent:` branch — `UNAVAILABLE` → `PASS` | **4 red** |
| 2 | criterion always passes | `missing` forced to `[]`, so the `FAIL` arm is unreachable | **2 red** |
| 3 | criterion ignores the expectation | every answer forced to `True` before it is recorded | **2 red** |

Mutation 1 turns **four** tests red rather than one, because an absent judge
has to be caught four ways that all have to hold: a missing frame file, a dead
host, a judge that raises / answers something unparseable / answers nothing at
all, and the host-independence test (which replaces the judge and therefore
must never see a reachability error).

Two further checks, because this project has shipped guards that asserted
nothing:

- **the guard's own FAIL assertion was neutered** (`assert True or (...)`, the
  P21 mutation that leaves the message and the line in place): caught by this
  file's own `test_this_file_contains_no_neutered_assertion`.
- **the formatter mirror was wrong and the guard said so.** The first run
  reported `formatValue(0.5, 'int')`: TypeScript `1`, Python `0` — Python
  rounds half to even, JavaScript rounds half up. Fixing that exposed a second
  divergence on `-0`, where JavaScript keeps a negative zero that
  `toLocaleString('en-US')` renders as the string `"-0"`. Both were found by
  running the corpus, not by reasoning about it, and both are invisible in
  these graphs (no value is ever exactly n.5). The mirror comparison asserts
  192 rows and requires the corpus to contain `48.2M`, so it cannot pass by
  agreeing about small numbers.

## 8. Reproducing the measurements

The model is not required for the guard, only for these numbers:

```
curl -s http://127.0.0.1:11434/api/tags          # qwen2.5vl:7b present
ffmpeg -i out/charts_demo.mp4 -vf "trim=start_frame=825:end_frame=826,\
setpts=PTS-STARTPTS" -vsync 0 -frames:v 1 f0825.png
python studio/scripts/vlm_critic.py f0825.png --expect 88
```

Frames are decoded from the delivered film into a temp directory. **No frame
was copied into the repository** — this project does not track media.
