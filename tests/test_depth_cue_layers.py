"""The depth cue must keep differentiating past the third window (P6.8).

THE DEFECT THIS EXISTS FOR.

`BrowserStack.tsx` read its per-window shadow with

    const depth = DEPTH_CUE[Math.min(i, DEPTH_CUE.length - 1)] ?? SHADOW.floating;

and `themes.ts` declared `depthCue` with exactly three entries. `Math.min` then
clamps every window from the fourth onward onto the third entry, so a stack of
four or more rendered with NO depth difference above the third window. Measured
rather than argued, by rendering the real scene with six windows and reading
back what React emitted:

    w0 0 14px  40px rgba(0,0,0,0.40)
    w1 0 30px  84px rgba(0,0,0,0.50)
    w2 0 46px 132px rgba(0,0,0,0.62)
    w3 0 46px 132px rgba(0,0,0,0.62)     <- same as w2
    w4 0 46px 132px rgba(0,0,0,0.62)     <- same
    w5 0 46px 132px rgba(0,0,0,0.62)     <- same

No delivered frame had ever shown it, which is why it survived: all 46
`browser-stack` scenes in the repository carry exactly three windows, and
`content` is an untyped bag on both schema sides, so a four-window graph was
always legal and always wrong.

WHY THE RENDER AND NOT THE SOURCE.

A `box-shadow` is a CSS declaration, and the defect is that two windows are
handed the same one. That is exactly recoverable from a server render, and NOT
recoverable from a flattened PNG: what a shadow contributes to pixels depends on
what it falls on, the windows' opacity, and what is behind them. So this drives
`design/depthCue.check.ts`, which renders the real component through Remotion's
own context providers and reads the emitted strings back. It deliberately does
not re-implement the clamp — a test that indexed the ramp with its own copy of
`Math.min` would pass against the very defect it was written to catch.

WHERE THE BOUNDARY IS, AND WHY IT IS NOT "ALL WINDOWS DIFFER".

The ramp now names five layers and `depthCueAt` clamps at the last one, so
window 5 in the probe above legitimately repeats window 4. That is the design,
and it is a bounded one: the dark ramp's alpha multiplies by 1.240 per layer and
reaches 0.95 at layer five, so layer six would need alpha 1.18 — not a colour.
The guard therefore asserts two separate things, and the second is the one with
teeth:

  1. windows 0..depthCue.length-1 each differ from the one below;
  2. the first repeat is at EXACTLY depthCue.length — not earlier.

A clamp that fires a layer early repeats inside the named range and fails (1).
A lookup that collapses everything onto one entry fails (1) too. Only a ramp
whose layers are all distinct AND whose clamp starts exactly at its end passes,
which is the whole claim.

Run:
    python -m pytest tests/test_depth_cue_layers.py -q
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / 'studio'
TEMPLATE = STUDIO / 'src' / 'templates' / 'finance-showcase'
DESIGN = TEMPLATE / 'design'
THEMES_TS = DESIGN / 'themes.ts'
TOKENS_TS = DESIGN / 'tokens.ts'
BROWSER_STACK = TEMPLATE / 'scenes' / 'BrowserStack.tsx'
CHECK = DESIGN / 'depthCue.check.ts'
JSON_SCHEMA = ROOT / 'pipeline' / 'schemas' / 'showcase-v1.schema.json'

_NPX = shutil.which('npx') or shutil.which('npx.cmd')


def _depth_cue_lengths() -> dict[str, list[str]]:
    """Every theme's `depthCue`, read out of themes.ts.

    Read from the source rather than restated, for the reason
    test_space_scale.py gives: a guard carrying its own copy of the numbers
    cannot notice them changing. Both themes, because a ramp that only the dark
    theme differentiates is half a fix.
    """
    src = THEMES_TS.read_text(encoding='utf-8')
    out: dict[str, list[str]] = {}
    for name in ('premium-dark', 'premium-light'):
        head = src.find(f"'{name}': {{")
        assert head != -1, f'{name} is missing from themes.ts'
        block = src[head:]
        cue_at = block.find('depthCue:')
        assert cue_at != -1, f'{name} declares no depthCue'
        inner = block[cue_at:]
        inner = inner[inner.find('[') + 1:inner.find(']')]
        out[name] = re.findall(r"'([^']+)'", inner)
    return out


def _shadow_resolutions() -> dict[str, list[float]]:
    """The y-offset / blur / alpha of every layer, parsed from themes.ts.

    Used for the saturation argument below, which is the reason the ramp stops
    at five rather than continuing to whatever number of windows a graph asks
    for. `parse` of the `0 Ypx Bpx rgba(R,G,B,A)` form, which is the only form
    either theme uses.
    """
    out: dict[str, list[float]] = {}
    for name, cues in _depth_cue_lengths().items():
        rows = []
        for cue in cues:
            m = re.match(
                r'0\s+(\d+)px\s+(\d+)px\s+rgba\(([\d.]+),([\d.]+),([\d.]+),([\d.]+)\)', cue
            )
            assert m, f'{name} depthCue entry is not the documented form: {cue!r}'
            rows.append((float(m.group(1)), float(m.group(2)), float(m.group(6))))
        out[name] = rows
    return out


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
def test_depth_cue_keeps_differentiating_past_the_third_window():
    """The real render: window N must differ from window N-1, up to the ramp's end.

    Skipped rather than failed when node is absent, matching
    test_perspective_math.py — a rendering guard must not be the reason the suite
    is red on a machine that cannot run it. The source-level guards below have
    teeth without node.
    """
    proc = subprocess.run(
        [_NPX, 'tsx', str(CHECK)],
        cwd=STUDIO,
        capture_output=True,
        text=True,
        timeout=300,
        encoding='utf-8',
        errors='replace',
    )
    assert proc.returncode == 0, (
        f'depth-cue check failed:\n{proc.stdout}\n{proc.stderr}'
    )
    # The measurement is printed so a run that passes still reports the shadows
    # it compared — a guard whose evidence only exists when it fails is a guard
    # you cannot re-derive a pass from.
    assert 'first repeated shadow is at window' in proc.stdout, (
        f'the check did not report where the repeat starts:\n{proc.stdout}'
    )


def test_every_theme_names_at_least_four_depth_layers():
    """Three layers is the defect. Four is the minimum that makes it unreachable.

    Pinned as a floor rather than as `== 5` so that a future ramp of six or
    seven is an improvement, not a failure, while a return to three — the shape
    that shipped — is caught even if the render guard is skipped for want of node.
    """
    for name, cues in _depth_cue_lengths().items():
        assert len(cues) >= 4, (
            f'{name}.depthCue has {len(cues)} layer(s) ({cues}). BrowserStack '
            'clamped every window past the last one onto it, so a stack deeper '
            'than the ramp rendered with no depth difference above it.'
        )


def test_no_two_layers_of_a_ramp_are_the_same_shadow():
    """A duplicate entry would defeat the ramp even with the index fixed."""
    for name, cues in _depth_cue_lengths().items():
        dupes = {c for c in cues if cues.count(c) > 1}
        assert not dupes, f'{name}.depthCue repeats {dupes}'


def test_layers_increase_geometry_and_opacity_monotonically():
    """Each layer deeper must be offset further, blurrier and less transparent.

    Without this, "every layer differs" is satisfiable by five arbitrary strings,
    and the ramp would differentiate without reading as depth. This is the
    property that makes the extension derived rather than decorative.
    """
    for name, rows in _shadow_resolutions().items():
        for i in range(1, len(rows)):
            (y0, b0, a0), (y1, b1, a1) = rows[i - 1], rows[i]
            assert y1 > y0, f'{name} layer {i}: offset {y1}px does not exceed {y0}px'
            assert b1 > b0, f'{name} layer {i}: blur {b1}px does not exceed {b0}px'
            assert a1 > a0, f'{name} layer {i}: alpha {a1} does not exceed {a0}'


def test_the_dark_ramp_saturates_rather_than_growing_without_limit():
    """Why five, and why the scene clamps rather than extrapolates.

    The dark ramp's alpha rises geometrically (0.40, 0.50, 0.62 — a ratio of
    1.240). Continuing that progression past the last layer reaches alpha 1.18 at
    layer six, which is not a colour. So the ramp's length is bounded by the
    alpha channel, and any future attempt to make it longer has to change the
    KIND of cue rather than its magnitude.

    This is the arithmetic that rules out extrapolating in `depthCueAt`, and it
    is asserted so the reasoning cannot be quietly forgotten when someone asks
    for a six-window stack.
    """
    dark = _shadow_resolutions()['premium-dark']
    alphas = [a for _, _, a in dark]
    ratio = alphas[-1] / alphas[-2]
    assert ratio > 1, f'dark alpha ramp is not increasing: {alphas}'
    projected = alphas[-1] * ratio
    assert projected > 1.0, (
        f'continuing the dark alpha ramp past {len(alphas)} layers gives '
        f'{projected:.3f}, which is still a legal alpha - so the "the ramp '
        'saturates, therefore stop at five" argument does not hold and the '
        'comment above depthCueAt is wrong. Re-measure before extending.'
    )
    assert all(0 < a <= 1 for a in alphas), f'dark ramp has an illegal alpha: {alphas}'


def test_depth_lookup_clamps_at_the_last_layer_and_does_not_wrap():
    """Source-level, so the behaviour survives a missing node.

    Wrapping is the tempting alternative to clamping and it is wrong in a way
    this asserts: `i % length` would render window 5 as window 0 — the FAR
    plane — behind a window carrying the deepest shadow.
    """
    src = BROWSER_STACK.read_text(encoding='utf-8')
    assert 'export const depthCueAt' in src, (
        'BrowserStack no longer exports depthCueAt — this guard has to be taught '
        'the new shape, not left parsing nothing'
    )
    body = src[src.find('export const depthCueAt'):]
    body = body[:body.find('};')]
    assert 'length - 1' in body, (
        'depthCueAt no longer clamps at the last layer; it may now be wrapping '
        f'or unbounded:\n{body}'
    )
    assert '%' not in body, (
        'depthCueAt appears to wrap modulo the ramp length, which would render a '
        'deep window with the FAR plane\'s shadow:\n' + body
    )
    # The scene must go through the helper, not an inline clamp.
    assert 'depthCueAt(DEPTH_CUE, i)' in src, (
        'BrowserStack no longer reads its depth cue through depthCueAt'
    )


def test_the_graph_cannot_set_depth_at_all():
    """Recorded as a fact, because P6.8 was asked to decide about it. P12 closed it.

    `DEPTH` was WIRED — styleBible.tsx imported it, merged `b.depth` over it and
    republished it as `useDesign().DEPTH` — and the graph still could not reach
    it, because `depth` appeared zero times in the JSON Schema.

    P12 ruled on it. Zero consumers, and an input that could not exist, so the
    graph-facing plumbing was deleted: no `b.depth` merge, no `StyleBible.depth`
    field, no `useDesign().DEPTH`. The `DEPTH` TABLE survives in tokens.ts —
    removing a token is a larger call than removing a binding — and the docstring
    above it now records the deletion instead of claiming the merge is live.

    The zero is re-pinned here, DERIVED rather than by substring. The previous
    version of this test was `assert 'depth' not in schema_text`, and it was
    wrong in the most embarrassing way available: P12 added `depthCue` to the
    schema and the substring `depth` inside `depthCue` tripped it. The
    assertion was a fact about TEXT, not about the schema, so it reported a
    breach of a rule the change had not broken. That is the fifth time this
    project has been fooled by a text-presence assertion, and it is why this
    one now parses the key set.

    `depthCue` is deliberately still declared: it is a real consumed section
    (BrowserStack:293) and the graph setting it is legitimate. The two must
    never be confused again, which is the whole point of the derivation.
    """
    import json
    doc = json.loads(JSON_SCHEMA.read_text(encoding='utf-8'))
    keys = set(doc['definitions']['StyleBible']['properties'])

    assert 'depth' not in keys, (
        'the JSON Schema declares `depth` again. If that is a pathway to the '
        'DEPTH table, tokens.ts needs the comment above it updated in the same '
        'change — P12 deleted the merge on the grounds that nothing consumes '
        'it. Declaring the key alone re-creates the stripped-section defect in '
        'reverse: fed, never read.')
    # the neighbouring key is the one that WAS made reachable, and this is the
    # assertion that proves the substring rule above was the bug, not the change
    assert 'depthCue' in keys, (
        'depthCue should be declared — BrowserStack:293 consumes it and P12 '
        'ruled it reachable. If this is red the schema lost a working key.')