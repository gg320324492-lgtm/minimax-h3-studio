"""qa_layers.py — which QA layer each rule belongs to, as DATA rather than prose.

WHY THIS FILE EXISTS

`docs/UPGRADE_MASTER_PLAN.md` lists P18 as "Technical / Layout / Motion / Visual
four-layer gates". Those four words have never been defined: nothing in the repo
says which rule belongs to which layer. This file is the first such statement,
and it is deliberately NOT a gate — it reports. Whether a "four-layer gate"
should be built is a judgement recorded in `docs/P18_QA_LAYERS.md`, not a
decision this module makes.

THE THINGS THIS FILE WILL NOT DO

1. It does not implement a gate. There is no exit code, no threshold, no
   blocking. `LAYER_OF` answers "which layer", never "should this pass".
2. It does not change any rule's decision logic. It imports the real functions
   and calls them on real inputs to derive the layer's behaviour from what the
   code does, so the classification cannot drift away from the implementation.
3. It does not merge `visual_qa.py` with `qa_report.py`. Those gate two
   different pipelines — see `PIPELINES` below — and merging them would lose
   the fact that one of them has a caller and the other does not.

THE TEST-ABILITY DESIGN, WHICH IS THE POINT

`build_report()` returns a plain dict. Nothing here re-implements a rule, and
nothing here reads `visual_qa.py` as TEXT to decide membership. Every field is
derived by CALLING the rule:

  * `behaves_like_static` — the rule returns the same verdict on a frame with
    content and on a frame with none. A rule that cannot tell those apart is
    not reading its input.
  * `reads_graph` �� the rule's verdict differs when the graph it was handed
    differs. This is what separates a real graph-reading rule from a function
    that merely takes a `props` argument.
  * `requires_pair` — the signature needs two paths, so running the rule needs
    two rendered frames. This is the cost axis.

Deriving these by execution is what makes the classification testable at all. A
classification written as `assert 'rule_freeze' in motion_source` is the shape
of guard this project has been fooled by six times: it cannot tell a rule from
a comment about a rule, or a rule from a substring of another rule's name. Here,
changing a layer or moving a rule changes what `build_report()` computes, so a
test can watch it change.

`LAYER_OF` IS THE ONE PLACE A LAYER IS DECLARED. It maps the name a rule EMITS
(a `Finding.rule` string) to exactly one layer. Emitted names are used rather
than Python function names because a report shows emitted names, and because
one function here emits a name that is not its own (see `EMITTED_BY`).
"""

from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(r'E:\Minimax-H3')
if str(ROOT / 'studio' / 'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT / 'studio' / 'scripts'))

import visual_qa as vqa  # noqa: E402

#: The four layer names exactly as the master plan spells them.
LAYERS = ('Technical', 'Layout', 'Motion', 'Visual')

#: Which QA gate serves which pipeline. Measured, not assumed:
#: `qa_report.py` is gated on `props['format']` (resolution/fps) and
#: `props['totalDuration']` — fields only `report-pipeline` props carry, and
#: only `report-data.schema.json` declares. `visual_qa.py` reads
#: `showcase-v1` props (`format`, scenes). They are not two views of one gate.
PIPELINES = {
    'visual_qa.py': 'showcase render',
    'qa_report.py': 'report-pipeline render',
}

#: The layer partition. THIS IS THE DELIVERABLE, and it is asserted — not
#: asserted as an aspiration, but as a measurement re-derived on every call to
#: `build_report()`.
#:
#: Three rules carry a caveat and the caveat is part of the entry, not a note
#: below it:
#:
#:  * `duplicate` is classified Motion. It is genuinely a time-dimension
#:    question — two renders of the same graph must differ — but the measured
#:    note below records that its threshold is the same number take_ranker
#:    reuses, and that the corpus has no positive pair. The honest layer is
#:    recorded and so is the measurement that qualifies it.
#:  * `blur` is classified Visual, against the work order's own table. A
#:    defocused frame is an aesthetic failure, and the instrument (Laplacian
#:    variance) is the same measure take_ranker uses for `m_sharpness`, a
#:    aesthetic quantity. The alternative reading — that a blur is a Technical
#:    defect — is defensible and is recorded in `AMBIGUOUS`, because
#:    "classified once" is not the same claim as "classified correctly".
#:  * `contrast` is classified Visual. It is a palette lookup with no frame
#:    input at all, which makes it the one rule in this table whose verdict
#:    does not describe the artefact under inspection. P22 split it: the palette
#:    half is now `theme_contrast` and is not emitted on the `--frame` path at
#:    all, and the per-frame half is `rule_contrast_frame`, UNAVAILABLE because no
#:    instrument for it exists. Both stay Visual — the layer is about what the
#:    question concerns, and both ask about how the design reads, not about
#:    pixels or layout.
#:
#: THE ASSIGNMENT ITSELF LIVES IN `build_report()`, not here. An earlier version
#: kept `LAYER_OF` as a module constant and built the per-layer groupings by
#: looking each rule up in it -- and the mutation "move `blur` from Visual to
#: Technical" survived all sixteen guards, because every derived structure moved
#: with it. The grouping is now authored, and `layer_of` is derived from it; see
#: the note on `build_report`.
#:
#: The CURRENT assignment is pinned in `tests/test_p18_qa_layer_partition.py` as
#: `PINNED_LAYERS`. That pin is what makes a re-classification a deliberate act:
#: someone has to change the test, in the same commit, to move a rule between
#: layers -- which is the whole point of guarding a classification rather than
#: re-deriving it.

#: Layers holding at most two rules, stated as a measurement.
#:
#: THE HEADLINE FINDING OF P18 is this 3/3/2/2 distribution, not the existence of
#: four layers. Every layer does have rules, so the partition is exhaustive — but
#: "four layers" in the master plan reads like four comparable buckets and it is
#: three of four and two of three. No layer is empty; one is thin.
#:
#: Motion is also the most expensive layer per rule, because both its rules take
#: a PAIR of rendered frames — a single `--frame` run executes neither. That is
#: why the work order's table listed Motion as holding one rule: it listed the
#: rules a one-frame run can reach, and `duplicate` shares `freeze`'s input.
#: It is counted here, so Motion is 2.
#:
#: P22 DROPPED the Visual entry from this table, and that is a finding rather
#: than an omission. Visual held 2 rules, one of which (`contrast`) was a palette
#: lookup identical on every artefact — so the layer COUNTED as full while only
#: `blur` could return a verdict about a frame. Splitting `contrast` into
#: `theme_contrast` (a fact about the theme, reported off the frame path) and
#: `contrast_frame` (the per-frame rule, UNAVAILABLE because the instrument does
#: not exist) took Visual to 3, which pushed it out of the `<= 2` thin set on a
#: COUNT — so the count stopped being a proxy for coverage and the proxy was
#: dropped rather than restated.
#:
#: WHAT THAT HIDES, and why the count is still not the thing to read: Visual now
#: holds 3 rules and exactly ONE of them can say anything about a frame. The
#: layer got fuller and the coverage did not. A "thin layer" note that reported
#: "Visual: 3 rules, fine" would be the same mistake as the one P22 exists to
#: fix, one level up, so Visual is absent from THIN_LAYERS while this paragraph
#: says plainly that it is the least covered layer in the table.
THIN_LAYERS: dict[str, str] = {
    'Motion': ('2 rules, and BOTH take a pair of rendered frames, so this is '
               'the one layer a single --frame run never reaches — and the '
               'most expensive per rule in the tool.'),
}

#: Entries whose layer is defensible both ways, with the reading NOT taken.
#: Recorded so a future reader can overrule rather than rediscover. Nothing is
#: enforced against this table — it is a note, and pretending otherwise would
#: be the same mistake as pretending the partition was derived.
AMBIGUOUS: dict[str, str] = {
    'blur': ("read as Technical too (a defocused frame is a capture defect, and "
             'rule_black_frame — also a frame-fidelity question — is Technical). '
             'Classified Visual because the instrument is the same measure '
             'take_ranker uses for m_sharpness, an aesthetic quantity. '
             'One layer only; the alternative reading is recorded, not adopted.'),
    'duplicate': ("read as Technical too (two runs of one render are a pipeline "
                  'defect, and P19 showed the 0.5 cut that used to sit here WAS '
                  'exactly that question). Classified Motion because the input '
                  'the entry point supplies is time-domain: two consecutive '
                  'frames of one render. See MEASURED_NOTE below.'),
}

#: MEASUREMENTS THAT QUALIFY AN ENTRY. Kept beside the table so a reader does
#: not have to take the layer on faith, and so a guard can assert the layer
#: without the measurement drifting out of the file that states it.
MEASURED_NOTE: dict[str, str] = {
    'black_frame': ('is Technical by instrument, not by subject: it asks whether '
                    'the frame is a flat single colour — a container-fidelity '
                    'question — not whether it is well composed. Its threshold '
                    'window is stated as THIN in the source: 0.999238 against a '
                    '0.9995 cut, a 0.000762 margin, because eight corpus frames '
                    'are exactly 1.0. Measured 23 FAIL of 333 corpus frames, '
                    'which are the flat ones.'),
    'safe_area': ('the one rule whose instrument can be WRONG rather than merely '
                  'absent. backdrop_model is fitted from the frame\'s own edge '
                  'columns, so on a frame whose content reaches the edge the '
                  'samples are content and the residual jumps from 3 to 208 '
                  '(measured). It answers UNVERIFIABLE above TRUST_RESIDUAL=60 '
                  '— measured 35 of 333 corpus frames. Layout by what it asks '
                  '(where does content sit relative to the frame edge), and the '
                  'untrust is a property of its instrument, not of its layer.'),
    'clipping': ('asks the same question as safe_area by a different route, and '
                 'they are MEASURED to disagree on the same frame: on a padX=0 '
                 'frame safe_area says UNVERIFIABLE and clipping says FAIL '
                 '(measured 310 PASS / 23 UNVERIFIABLE of 333). Two rules, one '
                 'layer, different instruments — that is the design, not a '
                 'duplicate. clipping uses the palette path and so is never '
                 'untrusted.'),
    'freeze': ('the only rule in the tool whose criterion is EXACT and total: '
               'difference == 0, because the noise floor was measured at exactly '
               '0 (the same frame rendered twice is array_equal). Costs two '
               'rendered frames — the most expensive input here — and on a '
               'single-frame run it never executes.'),
    'theme_contrast': ('P22. rule_contrast() takes NO arguments and returns the '
                     'same 24-pair table on every invocation — it describes '
                     'design/themes.ts, not an artefact. It used to be emitted '
                     'into every --frame report, which made that path exit 1 on '
                     'all 333 corpus frames for a constant. It is now reported '
                     'by --theme-contrast only, and the per-frame path carries '
                     'rule_contrast_frame instead, which is UNAVAILABLE because the '
                     'instrument does not exist (measured: 97.8% of corpus '
                     'pixels sit in contrast [1.0,1.5) against the gradient '
                     'Backdrop paints, so a pixel-census rule fires on 333/333 '
                     'frames and the population has no valley a cut could sit '
                     'in). The partition keeps both: one is a fact about the '
                     'theme, the other is a hole where a per-frame fact should '
                     'be.'),
    'contrast_frame': ('UNAVAILABLE on every frame, by measurement rather than by '
                       'choice. The question it would answer — "is this frame\'s '
                       'type readable" — needs a foreground/background ROLE per '
                       'pixel, and a frame\'s pixels carry none: a glyph stem, a '
                       'hairline and the backdrop ramp are all just a pixel. '
                       'Measured over 531,100,800 corpus pixels the contrast '
                       'distribution has no valley between gridline and ink, so '
                       'any cut either misses the gridlines or fires on every '
                       'frame. Same missing input `overflow` names: the mark '
                       'layout from the chart options, not pixels.'),
    'blur': ('30 of 333 corpus frames FAIL, not because any render is broken but '
             'because BLUR_VARIANCE = 2.0 sits below every frame this project has '
             'produced: corpus p5 is 11.5, a 5.75x margin ABOVE the threshold. The '
             'threshold is below the floor of the real distribution.'),
    'duplicate': ('STALE-UNTIL-P19 WAS WRONG ON THREE COUNTS AT ONCE, AND IS '
                  'UPDATED HERE; THE LAYER IS NOT. The cut it used was 0.5, cited '
                  'as take_ranker\'s own threshold — take_ranker holds no such '
                  'threshold at all (its m_duplicate works on a different scale, '
                  'mean abs diff / 255, cut at 0.0015); 0.5 lives in '
                  'rank_takes.DUP_THRESHOLD and compares two whole RENDERS. '
                  '`--frame-pair` hands this rule two CONSECUTIVE FRAMES, for '
                  'which "nearly identical" is the correct answer. Measured on '
                  'this repo\'s own corpus (329 frames under out/p13_probe): 152 '
                  'of 320 consecutive pairs FAIL at that cut, and — measured — '
                  'no cut on signature distance separates the two populations, '
                  'the best balance being 0.9969 sitting above exactly 0.0 and '
                  'carried by ONE real rerun pair. P19 therefore moved the rule '
                  'onto an exact identity cut (SIGNATURE_EQUAL = 0.0, the same '
                  'kind of warrant `freeze` has) and left the cross-render '
                  'question to rank_takes.py. It is still the second of the two '
                  'rules that need a PAIR of rendered frames.'),
    'missing_asset': ('rule_missing_asset(props) never reads its `props` argument — '
                      'verified by unparsing the function body with the docstring '
                      'removed and checking "props" does not appear, and by calling '
                      'it with three unrelated dicts and getting an identical '
                      'Finding. The four checked paths are hardcoded. It is a '
                      'repository check wearing a props argument. STILL TRUE after '
                      'P21, which added a rule that genuinely reads the graph '
                      'alongside it rather than changing this one.'),
    'graph_scene_renderable': ('Technical by the same argument as `missing_asset` and '
                              '`aspect`: it asks whether the render pipeline can produce '
                              'what the graph requested — a declared-vs-delivered '
                              'question, not a position, a time or a pixel question. '
                              'Added in P21. Before it, the `--props` path could not '
                              'tell a correct graph from a broken one: poisoning all 49 '
                              'strings of the delivered showcase graph produced a '
                              'byte-identical report and the same exit code as the clean '
                              'graph, and 0 for both. It is the only rule on that path '
                              'whose verdict changes with the graph (measured by '
                              'calling it on two different graphs). MEASURED: 22 scene '
                              'types declared by SceneType, 13 named by '
                              'SCENE_RENDERERS, 9 in between rendering the MissingScene '
                              'placeholder. No threshold — the question is presence or '
                              'absence of a renderer, and a cut point would be a number '
                              'about nothing.'),
    'font_size': ('UNVERIFIABLE on all 333 corpus frames when no --declared-px is '
                  'supplied, because a ratio needs both sides. It is Layout in what '
                  'it MEASURES, and it is dead in this CLI as shipped.'),
    'aspect': ('UNVERIFIABLE on all 333 corpus frames run as --frame, because '
               'declared_format is None unless --props carried a format block.'),
}


def _rule_functions() -> list[str]:
    """Rule functions read from the AST, so a mention in a comment cannot count."""
    tree = ast.parse(vqa.__file__ and Path(vqa.__file__).read_text(encoding='utf-8'))
    return [n.name for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name.startswith('rule_')]


def _emitted_names() -> dict[str, list[str]]:
    """Call every rule on a real input and read back the `Finding.rule` it emits.

    This is the step that keeps the partition honest about identity. A rule can
    be named `rule_duplicate_check_props` and emit the rule name
    `missing_asset` — measured, not hypothetical — so partitioning by function
    name would produce a duplicate key and partitioning by emitted name would
    not. The two are not interchangeable, and only one of them is what a report
    shows.
    """
    out: dict[str, list[str]] = {}
    content = _probe_content()
    # Two PNGs for the pair-taking rules, written to a temp dir and removed.
    # NOT read from out/: that tree is gitignored, so a test that depended on it
    # would pass on the machine that made it and fail on every fresh clone —
    # the reason tests/test_visual_qa.py states this in its own header.
    import tempfile
    from PIL import Image
    with tempfile.TemporaryDirectory(prefix='qa_layers_') as td:
        tdp = Path(td)
        png_a, png_b = tdp / 'a.png', tdp / 'b.png'
        Image.fromarray(content.astype('uint8')).save(png_a)
        shifted = _probe_content(seed=6)
        Image.fromarray(shifted.astype('uint8')).save(png_b)
        props_path = tdp / 'props.json'
        props_path.write_text(json.dumps({'scenes': []}), encoding='utf-8')
        for name in _rule_functions():
            fn = getattr(vqa, name)
            try:
                if name == 'rule_contrast':
                    r = fn()
                elif name == 'rule_contrast_frame':
                    # P22: the per-frame half. Needs a frame, so it is probed
                    # with the same synthetic content every other frame rule
                    # gets. It is UNAVAILABLE and the probe records the emitted
                    # name, which is what the partition is keyed on.
                    r = fn(content)
                elif name in ('rule_freeze', 'rule_duplicate'):
                    r = fn(png_a, png_b)
                elif name == 'rule_aspect':
                    r = fn((PROBE_W, PROBE_H), (PROBE_W, PROBE_H))
                elif name == 'rule_missing_asset':
                    r = fn({})
                elif name == 'rule_graph_scene_renderable':
                    # The ONLY rule here that reads a graph, so it is the one
                    # that has to be handed one. Called with an empty `scenes`
                    # list rather than `{}`: an absent `scenes` is UNVERIFIABLE,
                    # which is a true answer to "what does this rule say with
                    # nothing to say about" and not the answer we want to record
                    # here. The probe is about what the rule EMITS, and both
                    # spellings emit the same name — see the note on
                    # `emitted_names`.
                    r = fn({'scenes': []})
                elif name == 'rule_duplicate_check_props':
                    r = fn(props_path)
                elif name == 'rule_font_size':
                    r = fn(content, 20.0, 1.0)
                else:
                    r = fn(content)
            except Exception as exc:  # noqa: BLE001
                out[name] = [f'<ERROR {type(exc).__name__}: {exc}>']
                continue
            out[name] = sorted({f.rule for f in r}) if isinstance(r, list) else [r.rule]
    return out


#: The probe frames used for the behavioural measurements, and why they are sized
#: the way they are. THIS WAS WRONG TWICE, and the second time is the one worth
#: keeping.
#:
#: Attempt 1 used an 80x120 frame with a content block at columns 20..89.
#: `visual_qa.EDGE` is 40, so `backdrop_model` samples columns 0..39 and 80..119
#: to fit the backdrop — the block overlapped BOTH sample bands and every rule
#: returned UNVERIFIABLE on every frame.
#:
#: Attempt 2 widened it to 220 and moved the block clear of both EDGE bands
#: (cols 60..140). That still failed, and it is the subtler failure: `RING` is 24
#: and `backdrop_model`'s trust check takes the worst residual over a ring that
#: is the union of the top 24 ROWS (all columns), the bottom 24 rows, and the
#: left/right 24 columns. The block sat at rows 8..44, so it was inside the top
#: row band no matter where its columns were, the residual hit 228 against
#: TRUST_RESIDUAL 60, and `safe_area` answered UNVERIFIABLE on BOTH the content
#: and the flat frame. Two different inputs, one verdict — which is exactly what
#: `behaves_like_static` reports, so the column read True, which reads like a
#: measurement and is the absence of one.
#:
#: So the geometry now clears both bands and is stated as arithmetic:
#:   EDGE=40, RING=24, W=320, H=80, bars at cols 70..110 and 140..180, rows 30..50.
#:   columns 70..180 is clear of the EDGE bands 0..39 and 280..319;
#:   rows    30..50  is clear of the RING row bands 0..23 and 56..79.
#: Two bars of 40 px, not three: `text_band_heights` only calls a row band
#: "text-like" at `per_row <= w * 0.25` = 80, and 2 x 40 is exactly 80.
#:
#: And because a differential probe that cannot detect a difference has measured
#: nothing, `probe_is_sensitive()` below asserts that the pair really does drive
#: rules apart — so the next person to resize this frame finds out immediately.
PROBE_W, PROBE_H = 320, 80
PROBE_BARS = ((70, 110), (140, 180))
PROBE_ROWS = (30, 50)


def _probe_content(seed: int = 0):
    import numpy as np
    a = np.zeros((PROBE_H, PROBE_W, 3), dtype=int) + 12
    y0, y1 = PROBE_ROWS
    for x0, x1 in PROBE_BARS:
        a[y0 + seed:y1 + seed, x0:x1] = 240
    return a


def _probe_flat():
    import numpy as np
    return np.zeros((PROBE_H, PROBE_W, 3), dtype=int) + 12


def _verdict_of(fn, *args) -> str:
    r = fn(*args)
    return r[0].verdict if isinstance(r, list) else r.verdict


def probe_is_sensitive() -> bool:
    """Do the content and flat probe frames drive ANY rule to different verdicts?

    A differential probe that returns the same answer for both inputs has
    measured nothing, and every column derived from it is then void. So this is
    a precondition, reported alongside the columns rather than assumed.
    """
    content, flat = _probe_content(), _probe_flat()
    discriminators = (
        lambda: _verdict_of(vqa.rule_clipping, content) != _verdict_of(vqa.rule_clipping, flat),
        lambda: _verdict_of(vqa.rule_black_frame, content) != _verdict_of(vqa.rule_black_frame, flat),
        lambda: _verdict_of(vqa.rule_safe_area, content) != _verdict_of(vqa.rule_safe_area, flat),
        lambda: _verdict_of(vqa.rule_blur, content) != _verdict_of(vqa.rule_blur, flat),
        lambda: _verdict_of(vqa.rule_font_size, content, 20.0)
                != _verdict_of(vqa.rule_font_size, flat, 20.0),
    )
    return any(d() for d in discriminators)


def build_report() -> dict:
    """The partition plus the measurements that justify it. Pure; no rendering.

    Every behavioural field is produced by calling the rule, so a guard can
    assert on behaviour rather than on a word appearing in a source file.

    THE GROUPINGS ARE WRITTEN OUT, NOT GROUPED FROM `LAYER_OF`.
    `report['layers']` is authored literally below, and `LAYER_OF` is DERIVED from
    it. That direction is not a style choice — it is what makes the partition
    testable. The first version did the opposite (grouped the rules by looking up
    each one's layer) and the mutation "move `blur` from Visual to Technical"
    SURVIVED all sixteen guards: the grouping moved with the dict, the thinness
    recomputed to the same answer, and every assertion was satisfied by a
    classification that had silently changed. A table that is derived from itself
    cannot be asserted against; it can only be re-derived. So the assignment is
    stated once, in one place, and everything else reads it.
    """
    layers: dict[str, dict] = {
        'Technical': {'rules': ['black_frame', 'aspect', 'missing_asset',
                                'graph_scene_renderable'], 'notes': {}},
        'Layout': {'rules': ['safe_area', 'clipping', 'font_size'], 'notes': {}},
        'Motion': {'rules': ['freeze', 'duplicate'], 'notes': {}},
        'Visual': {'rules': ['blur', 'contrast_frame', 'theme_contrast'], 'notes': {}},
    }
    content, flat = _probe_content(), _probe_flat()

    behaviour = {
        # Same call twice: a rule with no input cannot differ between calls.
        # P22 renamed this row's subject: `rule_contrast` now emits
        # `theme_contrast` and is not on the per-frame path at all, so the
        # partition records it under the name the report shows.
        'theme_contrast': {
            'behaves_like_static': (_verdict_of(vqa.rule_contrast)
                                    == _verdict_of(vqa.rule_contrast)),
            'reads_graph': False,
            'requires_pair': False,
        },
        # P22. The per-frame half. Measured, not asserted: it is UNAVAILABLE on
        # every frame because the instrument does not exist, and `requires_frame`
        # is true of it while `reads_graph` is false — it reads pixels and the
        # pixels cannot answer the question.
        'contrast_frame': {
            'behaves_like_static': (_verdict_of(vqa.rule_contrast_frame, content)
                                    == _verdict_of(vqa.rule_contrast_frame, flat)),
            'reads_graph': False,
            'requires_pair': False,
        },
        # Two frames, same shape, different content. A rule that returns the
        # same verdict for a frame with a block in it and an empty one is not
        # reading the frame.
        'safe_area': {
            'behaves_like_static': (_verdict_of(vqa.rule_safe_area, content)
                                    == _verdict_of(vqa.rule_safe_area, flat)),
            'requires_pair': False,
        },
        'clipping': {
            'behaves_like_static': (_verdict_of(vqa.rule_clipping, content)
                                    == _verdict_of(vqa.rule_clipping, flat)),
            'requires_pair': False,
        },
        'font_size': {
            'behaves_like_static': (_verdict_of(vqa.rule_font_size, content, 20.0)
                                    == _verdict_of(vqa.rule_font_size, flat, 20.0)),
            'requires_pair': False,
        },
        'black_frame': {
            'behaves_like_static': (_verdict_of(vqa.rule_black_frame, content)
                                    == _verdict_of(vqa.rule_black_frame, flat)),
            'requires_pair': False,
        },
        'blur': {
            'behaves_like_static': (_verdict_of(vqa.rule_blur, content)
                                    == _verdict_of(vqa.rule_blur, flat)),
            'requires_pair': False,
        },
        'aspect': {
            'behaves_like_static': (_verdict_of(vqa.rule_aspect, (120, 80), (120, 80))
                                    == _verdict_of(vqa.rule_aspect, (120, 80), (128, 80))),
            'requires_pair': False,
        },
        'freeze': {'requires_pair': True, 'reads_graph': False},
        'duplicate': {'requires_pair': True, 'reads_graph': False},
        'missing_asset': {
            # The behavioural test for "reads the graph": the same rule, two
            # different graphs, do the verdicts differ? Measured by calling the
            # real function — not by asking whether the body mentions `props`.
            'reads_graph': (vqa.rule_missing_asset({})[0].verdict
                            != vqa.rule_missing_asset(
                                {'scenes': [{'id': 'x'}]})[0].verdict),
            'behaves_like_static': True,
            'requires_pair': False,
        },
        # P21. The same differential, on the rule that DOES read the graph. Two
        # graphs differing only in a scene type: one the renderer map names, one
        # it does not. Measured by calling, for the same reason as the row
        # above — a body that merely MENTIONS `props` reads the same on both.
        #
        # This column is now non-trivial for the first time in the repo. Before
        # P21 every `reads_graph` on the props path was False, which is what
        # `docs/P18_QA_LAYERS.md` §1.4 measured and what P21's own defect report
        # turned on.
        'graph_scene_renderable': {
            'reads_graph': (
                vqa.rule_graph_scene_renderable(
                    {'scenes': [{'id': 'a', 'type': 'kpi-hero'}]}).verdict
                != vqa.rule_graph_scene_renderable(
                    {'scenes': [{'id': 'a', 'type': 'quote'}]}).verdict),
            'behaves_like_static': False,
            'requires_pair': False,
        },
    }

    emitted_by = _emitted_names()

    # Attach the justification to each entry, and DERIVE the flat assignment from
    # the authored groupings. Order matters: `layer_of` must come out of the
    # groupings above, never feed them.
    layer_of: dict[str, str] = {}
    for layer, body in layers.items():
        for rule in body['rules']:
            layer_of[rule] = layer
            body['notes'][rule] = MEASURED_NOTE.get(rule, '')

    return {
        'layers': layers,
        'layer_of': layer_of,
        'emitted_by': emitted_by,
        'ambiguous': dict(AMBIGUOUS),
        'behaviour': behaviour,
        'probe_is_sensitive': probe_is_sensitive(),
        'unimplemented': dict(vqa.UNIMPLEMENTED),
        'pipelines': dict(PIPELINES),
        'counts': {name: len(layers[name]['rules']) for name in LAYERS},
    }


def report_json() -> str:
    return json.dumps(build_report(), indent=1, ensure_ascii=True, sort_keys=True)


if __name__ == '__main__':
    print(report_json())
