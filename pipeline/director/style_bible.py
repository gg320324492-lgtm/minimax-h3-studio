"""Brief -> depth plan -> style bible section -> scene graph (P12.1).

This is the FIRST producer in the pipeline
`Brief -> StyleBible -> Storyboard -> SceneGraph -> AssetPlan`. Everything
downstream of it already existed -- `pipeline/scene_graph.py` validates, and
`design/styleBible.tsx` resolves and publishes -- and nothing fed them. This
module is the piece that was missing.

IT GENERATES ONE KEY OUT OF TEN, ON PURPOSE.

P12 ruled that a Director auto-generating the style bible "would generate mostly
dumb declarations by default", because two of the declared keys
(`chartLanguage`, `audioLanguage`) have no consumer at all. That ruling is
correct and is not contradicted here; see `REFUSED` for what this module does
instead, and docs/P12_1_GENERATION.md for the per-key verdicts and the reasoning.

THE CHAIN IS REAL, AND THAT IS THE POINT.

`generate_graph` does not accept a style bible and hand it back. It takes a
brief that has NO style bible in it -- a project, a format, and scenes -- and
returns a document that `scene_graph.load()` accepts. Everything between those
two ends is computed: the depth layers come from the window count in the brief,
and the section is assembled from the plan rather than from the caller's
intentions. A pass-through would be indistinguishable from this module by
inspecting one graph; it is distinguishable by asking for six windows, which
produces five layers and a refusal, and by asking for three, which produces
three.

WHAT COMES BACK.

`GeneratedGraph` carries the document, the plan that shaped it, and the list of
things the generator declined to do. The refusals are part of the return value
rather than a log line, because P12's whole finding is that a dropped intent is
invisible: nine times this project shipped something that was declared and
nothing more. An intent this generator cannot honour is returned to the caller
to be reported, not swallowed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .depth_plan import MEASURED_RAMPS, DepthPlan, plan_depth

#: The keys of the style bible that `StyleBibleSchema` declares.
STYLE_BIBLE_KEYS: frozenset[str] = frozenset({
    'palette', 'typography', 'spacing', 'radius', 'shadow', 'depthCue',
    'cameraLanguage', 'motionLanguage', 'chartLanguage', 'audioLanguage',
})

#: The keys this generator emits, and the measured reason it emits them.
#:
#: `depthCue` has a consumer (`BrowserStack.tsx` reads it through `depthCueAt`)
#: AND a measured rule that says how long it should be. Every other key has at
#: most one of those two, which is why this is a one-entry list rather than a
#: loop over `STYLE_BIBLE_KEYS`.
EMITS: frozenset[str] = frozenset({'depthCue'})

#: The nine keys this generator refuses, each with the measured reason.
#:
#: The reasons are the ones recorded in docs/P12_1_GENERATION.md; they are kept
#: HERE, next to the code that acts on them, so a reader who asks "why is this
#: not generated" gets an answer from the module rather than from a document
#: they have to know to open.
REFUSED: dict[str, str] = {
    'chartLanguage': (
        'zero consumers: declared by both schemas, bound by no line of the '
        'resolver, read by no scene. Generating it would be a declaration that '
        'cannot change a frame.'),
    'audioLanguage': (
        'zero consumers, same measurement. Note this is the OPPOSITE defect '
        'direction from P11/P12 radius-shadow-depthCue: nothing reads it, '
        'rather than something reads a value that cannot arrive.'),
    'palette': (
        'has 22 consumer sites but no derivation. Its values are brand hex, '
        'and P16 ruled the colour dimension undecidable without a reference '
        'film that is not on this machine. Any hex emitted here would be '
        'invented, not generated.'),
    'typography': (
        'has 12 consumer sites and is the only key any delivered graph has ever '
        'set -- but its one delivered value is authored judgement (a tracking '
        'of -0.055em against a default -0.04em), not the continuation of a '
        'measured curve. There is nothing to continue.'),
    'spacing': (
        'has 12 consumer sites but generating it would fight an invariant: the '
        'scale is 8x Fibonacci, pinned by tests/test_space_scale.py, and three '
        'of its steps (xs, xxl, hero) are MEASURED dead. A generator emitting '
        'spacing values is emitting values nothing reads, against a rule.'),
    'radius': (
        'has 10 consumer sites, but the four values are shape idioms rather '
        'than a scale: chip:999 is the pill trick, not a rung. No progression '
        'to continue.'),
    'shadow': (
        'has 8 consumer sites; four named roles (near/medium/floating/'
        'glowAccent) that are a theme surface, not a curve. No rule maps an '
        'intent onto them.'),
    'cameraLanguage': (
        'has ONE consumer and it reads ONE sub-key (CameraRig.tsx reads '
        'cameraDefaults.perspective). durationSeconds is declared, merged and '
        'read by nobody -- generating it would repeat, at sub-key granularity, '
        'exactly the defect P12 identified and nobody has guarded yet.'),
    'motionLanguage': (
        'has 15 consumer sites but mergeSection is a SHALLOW type-checked '
        'merge, and its value tables are nested objects. Measured on the real '
        'resolver: a graph setting motionLanguage.profiles.premium leaves '
        'ONLY that profile -- the other three are replaced, not merged -- and '
        'profileOf then silently falls back. Generating a nested motion '
        'section would be generating a value that can delete three others.'),
}


@dataclass(frozen=True)
class GeneratedGraph:
    """The document, the plan behind it, and everything that was not done."""

    graph: dict[str, Any]
    plan: DepthPlan
    unapplied: tuple[str, ...] = field(default=())

    @property
    def style_bible(self) -> dict[str, Any]:
        return dict(self.graph.get('style_bible') or {})

    @property
    def emitted_keys(self) -> frozenset[str]:
        return frozenset(self.style_bible)


def _browser_stack_windows(brief: dict[str, Any]) -> int:
    """The deepest stack the brief asks for.

    Only `browser-stack` scenes consume the depth cue, so only they are counted.
    Counting every scene's `content.windows` would inflate the number with bags
    that no depth-reading scene will ever index.
    """
    deepest = 0
    for scene in brief.get('scenes') or []:
        if not isinstance(scene, dict) or scene.get('type') != 'browser-stack':
            continue
        content = scene.get('content')
        windows = content.get('windows') if isinstance(content, dict) else None
        if isinstance(windows, list):
            deepest = max(deepest, len(windows))
    return deepest


def _scene_theme(brief: dict[str, Any], scene: dict[str, Any]) -> str:
    """The theme a scene resolves against: its own, else the brief's default."""
    for source in (scene, brief):
        theme = source.get('theme')
        if isinstance(theme, str) and theme in MEASURED_RAMPS:
            return theme
    return 'premium-dark'


def generate_graph(brief: dict[str, Any]) -> GeneratedGraph:
    """Turn a brief that carries no style bible into one that does.

    `brief` is what an author asks for: `project`, `format`, and `scenes`. It is
    NOT a graph with a style bible already in it -- supplying one would make
    this module a pass-through dressed as a generator, which is the failure the
    P12.1 work order names first.

    The returned graph validates against `showcase-v1` via
    `pipeline.scene_graph.load`, which the guard exercises rather than assumes.
    """
    if not isinstance(brief, dict):
        raise TypeError(f'brief must be a dict, got {type(brief).__name__}')

    scenes = brief.get('scenes')
    if not isinstance(scenes, list) or not scenes:
        raise ValueError('brief must carry a non-empty "scenes" list')

    theme = _scene_theme(brief, next((s for s in scenes
                                      if isinstance(s, dict) and s.get('type') == 'browser-stack'),
                                     scenes[0] if isinstance(scenes[0], dict) else {}))
    plan = plan_depth(theme, _browser_stack_windows(brief))

    graph: dict[str, Any] = {
        'version': 1,
        'project': brief.get('project') or 'generated',
        'format': brief.get('format') or {'width': 1920, 'height': 1080, 'fps': 60},
        'scenes': scenes,
    }
    if plan.ramp:
        graph['style_bible'] = {'depthCue': list(plan.ramp)}
    for extra in ('bpm', '_note'):
        if extra in brief:
            graph[extra] = brief[extra]

    # The keys this generator did not emit are reported, never silently absent:
    # a caller who asked for a palette needs to be told there isn't one.
    unapplied = list(plan.refusals)
    for key in sorted(STYLE_BIBLE_KEYS - EMITS):
        unapplied.append(f'{key}: not generated -- {REFUSED[key]}')

    return GeneratedGraph(graph=graph, plan=plan, unapplied=tuple(unapplied))