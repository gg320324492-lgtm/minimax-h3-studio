"""showcase-v1 loader + validator (P3).

The scene graph is the centre of the new architecture: agents author scene JSON,
not TSX. This module is the Python-side entry point — it validates, resolves the
timeline (start frames, beat snapping), and answers the questions the renderer
and the QA gates ask.

Schema: pipeline/schemas/showcase-v1.schema.json
Mirror:  studio/src/schemas/showcase-v1.ts (kept in sync by
         tests/test_showcase_schema_parity.py)

WHY THIS FILE NOW VALIDATES AGAINST `SCHEMA_PATH` INSTEAD OF A HAND-WRITTEN LIST.

For most of the project's life this module declared the schema path above and
never used it. Its validation was `_validate()`, a second, hand-maintained
spelling of the same contract, and the two had drifted apart in BOTH
directions. Measured on 35 probe graphs (`tests/test_pipeline_validates_the_schema.py`
runs them; the table is in that file's docstring):

  * Python accepted 8 graphs the JSON Schema REJECTED — including every case
    the last three commits were written for. `motion.ease`, a top-level
    `audio`, and a misspelled scene key all passed `scene_graph.load()`.
    Those are exactly the "the graph claims something nothing honours" defects,
    and the producer — the side that WRITES graphs — was the one not checking.
  * Python rejected 2 graphs the JSON Schema ACCEPTED: a duplicate scene id,
    and `camera.perspective: 0`.

The asymmetry is the bug. The pipeline is where graphs are authored, so a
permissive producer validator means a typo leaves the pipeline looking valid and
fails only at render time. So the schema is now the authority here too: this
file runs the schema at `SCHEMA_PATH` and reports what it says.

WHICH SIDE IS THE AUTHORITY, WHEN THE TWO MIRRORS THEMSELVES DISAGREE.

Wiring this file to `SCHEMA_PATH` created a question it could not answer on its
own: zod and the JSON Schema were not always in agreement, so "defer to the
schema" silently picks a side. The answer is zod, always, and the reason is
which one is ENFORCED. `ShowcaseSchema.safeParse` is what the renderer calls;
the JSON Schema file is a declaration that for most of this project's life did
not compile in any validator. A declaration nobody runs is a wish, not a
contract. `camera.perspective: 0` and `format.width: 8` are the two places this
mattered; both were fixed in the schema, toward zod, and both are pinned by
`tests/test_showcase_mirrors_agree_on_values.py`.

WHY THE SCHEMA IS RUN BY CODE IN THIS FILE RATHER THAN BY `import jsonschema`.

`jsonschema` is installed on Python 3.10 (4.26.0) and NOT on 3.12 — and 3.12 is
the only interpreter the test suite runs on, by the project's own documented
setup. `requirements-dev.txt` carries `pytest` and nothing else, with an
explicit comment that production dependencies "all live in ComfyUI's venv and
are not duplicated here because two declarations drift". So `import jsonschema`
would make the pipeline's validator unavailable on the machine the tests run on,
which is precisely the silent-skip failure this change exists to remove.

Instead `_Schema` below implements the exact draft-07 keyword subset the schema
uses, driven entirely by the parsed schema file — nothing is hardcoded about
showcase-v1's fields. `test_pipeline_validates_the_schema.py` checks that
subset against a real validator (Ajv, via the repo's own node) so the subset
cannot silently rot into a weaker language.

THE RULES THAT SURVIVED ARE THE ONES JSON SCHEMA CANNOT EXPRESS.

Two checks stay in `_validate` because no draft-07 keyword can state them, and
each has a consumer that breaks when it is dropped:

  * DUPLICATE SCENE ID — `FinanceShowcaseWide.tsx:156` resolves each resolved
    scene with `doc.scenes.find(x => x.id === r.id)`, so two scenes sharing an id
    both render the FIRST one's content and the second never renders at all.
    `uniqueItems` cannot express this either: it compares whole objects, so two
    scenes that differ only in `durationInFrames` are "distinct" while sharing an
    id. This is the one probe where Python was RIGHT and the schema was silent,
    and it is the one place this file is deliberately stricter than its authority.
    `tests/test_pipeline_validates_the_schema.py` pins the disagreement as a
    known, intended one rather than letting it drift back to silent.
  * `scenes` must be a non-empty LIST OF OBJECTS — `additionalProperties` applies
    only to objects, so `{"scenes": {"a": 1}}` satisfies `items` vacuously, and
    the per-scene loop below would then be iterating a dict.

THE `camera.perspective: 0` DISAGREEMENT WAS RESOLVED TOWARD ZOD, NOT HERE.

This file originally recorded that disagreement the other way round, and the
recording was wrong — or rather, it applied the tie-breaker from the wrong side.
At the time, the two MIRRORS already disagreed: zod said `z.number().positive()`
(rejects 0), the JSON Schema said `minimum: 0` (accepts it), and the old
hand-written `_validate` also rejected it. Facing two sides that disagreed, it
deferred to "the schema is the authority the renderer enforces" and let
`perspective: 0` through.

But zod is the side the renderer actually enforces. `ShowcaseSchema.safeParse`
is what `FinanceShowcaseWide.tsx` and `showcaseMeta.ts` run, and the JSON Schema
was only ever a declaration — one that, for most of this project's life, could
not even compile. So "the schema is the authority" was never a reason to prefer
it over zod; it was a reason to stop looking. The schema now says
`exclusiveMinimum: 0` and rejects 0, like zod, and this file follows the file.

The same sweep that found it found a second instance of the identical shape:
`format.width`/`height` carried `minimum: 16` in the JSON Schema while zod says
`.int().positive()`. Both are now `minimum: 1`. `perspective: 0` is not merely
meaningless in a perspective projection — it is a division by zero on the way to
the screen. No delivered graph sets it: all ten in `charts_demo` use 1600.

WHAT WAS DELETED, AND WHY IT WAS SAFE TO DELETE.

`_is_track()`, the camera-track shape check, the scene-type check, the
`motion.preset` check, and every hand-copied numeric range are gone. Each was
measured against the schema on the probe set and every one of them is covered by
a real schema keyword (`oneOf` + `minItems`/`maxItems` on `Track`, `enum` on
`Scene.type` and `Motion.preset`, `minimum`/`maximum` elsewhere). Keeping a
second copy of a rule that the schema already states is how this file drifted in
the first place: `_is_track` accepted `[1, 2, 3]`-shaped tracks and the schema
rejects them, and nobody noticed for a year.

WHAT WAS DELIBERATELY NOT ADDED: TOLERANCE FOR UNKNOWN KEYS.

There is an obvious temptation here, and it is the wrong one. The schema already
declares `_note` on both mirrors as a `string`, so the meta convention keeps
working with zero special-casing in this file — the schema file is where that
decision belongs, and duplicating it here would be a third place for it to drift
out of. Adding an "ignore unknown keys" pass on top of `additionalProperties:
false` would re-open exactly the hole commit 55a1d90 closed in the other two
mirrors: an unknown key is precisely how `motion.ease` and `audio` entered this
project, and tolerating them here makes the producer permissive again while the
renderer stays strict. An unknown key is a hard error, on all three mirrors.

Usage:
  python pipeline/scene_graph.py --file showcase.json [--resolve] [--beat-snap]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).resolve().parent / 'schemas' / 'showcase-v1.schema.json'

#: Draft-07 keywords this file's `_Schema` implements. `_check_supported()`
#: refuses to run against a schema that uses anything else, so an unsupported
#: keyword can never be silently ignored — it stops the pipeline loudly, which is
#: the opposite of the silent-skip failure this change exists to remove.
#:
#: `exclusiveMinimum` is here because `Camera.perspective` needs it. draft-07 has
#: two spellings of "greater than 0" — `exclusiveMinimum: 0` and, in draft-06,
#: `minimum: 1` — and the mirror uses the first because that is what zod's own
#: `toJSONSchema` emits for `.positive()`. Spelled it the draft-06 way it would be
#: indistinguishable from `Scene.durationInFrames`'s `minimum: 1`, and the two
#: would then differ only in a number nobody re-reads. `exclusiveMaximum` is
#: deliberately NOT here: nothing uses it, and
#: `test_an_unsupported_keyword_stops_the_pipeline_rather_than_being_ignored`
#: relies on it staying unsupported.
SUPPORTED_KEYWORDS = frozenset({
    '$schema', '$ref', 'title', 'description', 'default', 'definitions',
    'type', 'properties', 'required', 'additionalProperties',
    'items', 'enum', 'const',
    'minimum', 'exclusiveMinimum', 'maximum', 'minLength', 'minItems', 'maxItems',
    'pattern', 'oneOf',
})

#: JSON Schema `type` values this file distinguishes.
_TYPE_CHECKS = {
    'object': dict, 'array': list, 'string': str,
    'boolean': bool, 'null': type(None),
}

SCENE_TYPES = (
    'video', 'kpi-hero', 'browser-window', 'browser-stack', 'dashboard',
    'stat-card', 'card-grid', 'calendar', 'bar-chart', 'line-chart',
    'area-chart', 'bubble-chart', 'rank-chart', 'slope-chart', 'heatmap',
    'volume-chart', 'sparkline-chart',
    'data-table', 'quote', 'data-plane-3d', 'logo', 'outro',
)

# Scenes that come from H3 rather than the motion engine (P3 asset routing).
GENERATIVE_TYPES = {'video', 'data-plane-3d'}

CAMERA_TRACKS = ('translateX', 'translateY', 'translateZ',
                 'rotateX', 'rotateY', 'rotateZ', 'scale', 'focus')


class ShowcaseError(ValueError):
    pass


@dataclass
class ResolvedScene:
    id: str
    type: str
    startFrame: int
    durationInFrames: int
    raw: dict[str, Any] = field(default_factory=dict)
    #: what the graph asked for; in beat mode the resolved duration is authoritative
    requested_frames: int = 0

    @property
    def endFrame(self) -> int:
        return self.startFrame + self.durationInFrames

    @property
    def adjusted(self) -> bool:
        """True when beat quantisation changed the requested length."""
        return self.requested_frames != self.durationInFrames

    @property
    def generative(self) -> bool:
        """True when this scene needs H3 rather than the Remotion motion engine."""
        return self.type in GENERATIVE_TYPES


@dataclass
class Showcase:
    project: str
    width: int
    height: int
    fps: int
    bpm: float
    scenes: list[dict[str, Any]]
    style_bible: dict[str, Any] = field(default_factory=dict)

    @property
    def totalFrames(self) -> int:
        return sum(int(s['durationInFrames']) for s in self.scenes)

    def resolve(self, beat_snap: bool = False) -> list[ResolvedScene]:
        """Assign start frames.

        Without beat_snap this is a plain back-to-back timeline.

        With beat_snap, timing lives in BEAT space and is converted to frames
        exactly once per boundary. Both boundaries of a scene come from the
        same rounding of the same beat grid, so:

          * continuity is structural — start[i+1] == end[i] by construction,
            so neither an overlap nor a gap can be expressed;
          * drift is bounded by half a frame per boundary and never
            accumulates, because the beat cursor is an exact count.

        Three earlier versions failed, and the pattern is worth keeping in
        mind: picking start-rounding and duration-rounding independently gives
        round(a) + round(b) != round(a + b), so every combination leaves a
        one-frame defect on one side or the other — snapping starts iteratively
        overlapped (0.43 frames per scene, 3.86 over ten), and flooring the
        duration instead turned that overlap into a gap. The fix is not a
        better rounding mode; it is deriving each scene's end from the next
        scene's start instead of computing both.

        `durationInFrames` in the input is therefore a REQUEST. The resolved
        duration is authoritative and may differ by up to half a beat; ask for
        whole-beat durations to keep the difference predictable.
        """
        beat_frames = (60.0 / self.bpm) * self.fps
        out: list[ResolvedScene] = []
        beat_cursor = 0.0
        frame_cursor = 0
        for s in self.scenes:
            requested = int(s['durationInFrames'])
            if beat_snap:
                beats = float(max(1, round(requested / beat_frames)))
                start = int(round(beat_cursor * beat_frames))
                end = int(round((beat_cursor + beats) * beat_frames))
                beat_cursor += beats
            else:
                start = frame_cursor
                end = frame_cursor + requested
            out.append(ResolvedScene(id=s['id'], type=s['type'], startFrame=start,
                                     durationInFrames=end - start, raw=s,
                                     requested_frames=requested))
            frame_cursor = end
        return out

    def beat_distance_frames(self, frame: int) -> float:
        """Distance from `frame` to the nearest beat boundary, in frames."""
        beat_frames = (60.0 / self.bpm) * self.fps
        off = frame % beat_frames
        return min(off, beat_frames - off)

    def on_beat(self, frame: int) -> bool:
        """Within HALF A FRAME of a beat.

        That is the tightest bound integer frames allow when snapping is on
        (each start is rounded once from its exact beat position). Half a BEAT
        only applies when beat_snap is off — it is a loose bound and, used as an
        assertion, cannot catch sub-beat drift at all.
        """
        return self.beat_distance_frames(frame) <= 0.5 + 1e-6

    def generative_scenes(self) -> list[ResolvedScene]:
        return [s for s in self.resolve() if s.generative]


class _Schema:
    """A draft-07 validator for the keyword subset in `SUPPORTED_KEYWORDS`.

    Deliberately small and deliberately strict about its own limits. It knows
    nothing about showcase-v1 — every rule comes from the parsed schema file —
    so it cannot go stale the way a hand-written field list did. And
    `_check_supported()` makes an unknown keyword a loud error rather than a
    silently-skipped constraint, which is the same class of failure as a
    validator that quietly does nothing when its schema file is missing.
    """

    def __init__(self, schema: dict, source: str = '<schema>') -> None:
        self._root = schema
        self._source = source
        self._patterns: dict[str, re.Pattern[str]] = {}
        self._check_supported(schema, '')
        self._resolve_every_ref(schema, '')

    # ── construction ────────────────────────────────────────────────────────

    def _check_supported(self, node: Any, at: str) -> None:
        """Refuse to run against a schema using a keyword we do not implement."""
        if isinstance(node, dict):
            for key, value in node.items():
                if key == 'properties':
                    for name, sub in value.items():
                        self._check_supported(sub, f'{at}/properties/{name}')
                    continue
                if key == 'definitions':
                    for name, sub in value.items():
                        self._check_supported(sub, f'{at}/definitions/{name}')
                    continue
                if key not in SUPPORTED_KEYWORDS:
                    raise ShowcaseError(
                        f'{self._source}: unsupported JSON Schema keyword '
                        f'{key!r} at {at or "(document root)"}. Add it to '
                        f'SUPPORTED_KEYWORDS and implement it in _Schema, or the '
                        f'pipeline would validate against a weaker schema than '
                        f'the renderer does.')
                self._check_supported(value, f'{at}/{key}')
        elif isinstance(node, list):
            for i, item in enumerate(node):
                self._check_supported(item, f'{at}/{i}')

    def _resolve_every_ref(self, node: Any, at: str) -> None:
        """Resolve EVERY `$ref` up front, exactly as a compiling validator does.

        This is not tidiness. Resolving lazily, at validation time, means a
        dangling reference is only noticed when some document happens to reach
        that branch -- so the graph being validated has to contain a camera
        before a broken camera schema is detected. That is precisely the
        `definitions/Track` failure of 55a1d90 reproduced in a new place: the
        schema is broken, and the pipeline validates against it anyway, quietly,
        until the day a graph uses the broken part. Ajv rejects it at COMPILE
        time; so does this, which is what keeps the two agreeing about what a
        broken schema means rather than about which documents happen to trip
        over it.
        """
        if isinstance(node, dict):
            for key, value in node.items():
                if key == '$ref' and isinstance(value, str):
                    self._resolve(value)
                    continue
                self._resolve_every_ref(value, f'{at}/{key}')
        elif isinstance(node, list):
            for i, item in enumerate(node):
                self._resolve_every_ref(item, f'{at}/{i}')

    def _pattern(self, expr: str) -> re.Pattern[str]:
        """Compiled patterns are cached — ECMA and Python regex syntax differ
        only where this schema never goes, and a divergence would raise rather
        than silently pass."""
        compiled = self._patterns.get(expr)
        if compiled is None:
            try:
                compiled = re.compile(expr)
            except re.error as exc:  # pragma: no cover - defensive
                raise ShowcaseError(
                    f'{self._source}: pattern {expr!r} did not compile: {exc}') from exc
            self._patterns[expr] = compiled
        return compiled

    def _resolve(self, ref: str) -> dict:
        if not ref.startswith('#/'):
            raise ShowcaseError(f'{self._source}: only local $ref is supported, got {ref!r}')
        node: Any = self._root
        for step in ref[2:].split('/'):
            step = step.replace('~1', '/').replace('~0', '~')
            if not isinstance(node, dict) or step not in node:
                raise ShowcaseError(
                    f'{self._source}: $ref {ref!r} does not resolve. A schema that '
                    f'cannot resolve its own references cannot be compiled by any '
                    f'validator, so it can never agree with the renderer — it just '
                    f'never answers.')
            node = node[step]
        if not isinstance(node, dict):
            raise ShowcaseError(f'{self._source}: $ref {ref!r} does not point at a schema')
        return node

    # ── validation ──────────────────────────────────────────────────────────

    def iter_errors(self, doc: Any) -> list[str]:
        """Every violation, as `path: message` — an author can act on that."""
        out: list[str] = []
        self._check(self._root, doc, '', out)
        return out

    def _check(self, schema: dict, value: Any, at: str, out: list[str]) -> None:
        if '$ref' in schema:
            self._check(self._resolve(schema['$ref']), value, at, out)
            # draft-07: a $ref object ignores its sibling keywords.
            return

        if 'const' in schema and value != schema['const']:
            out.append(f'{at or "(document root)"}: must be {schema["const"]!r}, got {value!r}')
        if 'enum' in schema and value not in schema['enum']:
            out.append(f'{at or "(document root)"}: must be one of {schema["enum"]!r}, got {value!r}')
        if 'oneOf' in schema and not self._matches_one(schema['oneOf'], value):
            out.append(f'{at or "(document root)"}: does not match any of the '
                       f'{len(schema["oneOf"])} allowed forms, got {value!r}')

        types = schema.get('type')
        if types is not None:
            wanted = [types] if isinstance(types, str) else list(types)
            if not any(_is_type(value, t) for t in wanted):
                out.append(f'{at or "(document root)"}: must be '
                           f'{" or ".join(wanted)}, got {_describe(value)}')
                return

        if isinstance(value, str):
            if 'minLength' in schema and len(value) < schema['minLength']:
                out.append(f'{at}: must be at least {schema["minLength"]} characters')
            if 'pattern' in schema and not self._pattern(schema['pattern']).search(value):
                out.append(f'{at}: {value!r} does not match {schema["pattern"]!r}')
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            # draft-06+: booleans are NOT numbers, and `True` is an int in Python.
            if 'minimum' in schema and value < schema['minimum']:
                out.append(f'{at}: must be >= {schema["minimum"]}, got {value!r}')
            if 'exclusiveMinimum' in schema and value <= schema['exclusiveMinimum']:
                out.append(f'{at}: must be > {schema["exclusiveMinimum"]}, got {value!r}')
            if 'maximum' in schema and value > schema['maximum']:
                out.append(f'{at}: must be <= {schema["maximum"]}, got {value!r}')
        elif isinstance(value, list):
            if 'minItems' in schema and len(value) < schema['minItems']:
                out.append(f'{at}: must have at least {schema["minItems"]} items')
            if 'maxItems' in schema and len(value) > schema['maxItems']:
                out.append(f'{at}: must have at most {schema["maxItems"]} items')
            item_schema = schema.get('items')
            if isinstance(item_schema, dict):
                for i, item in enumerate(value):
                    self._check(item_schema, item, f'{at}[{i}]', out)
        elif isinstance(value, dict):
            for key in schema.get('required', ()):
                if key not in value:
                    out.append(f'{at or "(document root)"}: missing required key {key!r}')
            props = schema.get('properties') or {}
            for key, sub in props.items():
                if key in value:
                    self._check(sub, value[key], f'{at}.{key}' if at else key, out)
            if schema.get('additionalProperties') is False:
                extra = sorted(set(value) - set(props))
                if extra:
                    out.append(f'{at or "(document root)"}: unknown key(s) '
                               f'{extra}; this graph\'s vocabulary is closed, and '
                               f'an unknown key is either a typo or a field no '
                               f'renderer reads')

    @staticmethod
    def _matches_one(branches: list[dict], value: Any) -> bool:
        """`oneOf` means exactly one branch may match (not "at least one")."""
        hits = 0
        for branch in branches:
            probe: list[str] = []
            _Schema(branch, '<oneOf>')._check(branch, value, '', probe)
            if not probe:
                hits += 1
        return hits == 1


def _is_type(value: Any, name: str) -> bool:
    if name == 'integer':
        return isinstance(value, int) and not isinstance(value, bool)
    if name == 'number':
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == 'boolean':
        return isinstance(value, bool)
    py = _TYPE_CHECKS.get(name)
    if py is None:
        raise ShowcaseError(f'unsupported JSON Schema type {name!r}')
    # An `object` in JSON is never a `string` in Python even though str is iterable.
    return isinstance(value, py) and not (name != 'boolean' and isinstance(value, bool))


def _describe(value: Any) -> str:
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return f'boolean {value}'
    return f'{type(value).__name__} {value!r}'


@lru_cache(maxsize=1)
def schema() -> _Schema:
    """The compiled schema at `SCHEMA_PATH`. Loaded ONCE, and loudly.

    A missing, unreadable, or unsupported schema is a hard `ShowcaseError`, not
    a skip. The failure this change removes began with a validator that quietly
    did nothing; a validator that quietly does nothing when its file is absent
    is the same defect wearing a different hat. Raising here means a caller sees
    "the schema is missing" instead of "this graph validated", which is the
    difference between a bug you can fix and one you have to reproduce.
    """
    try:
        raw = SCHEMA_PATH.read_bytes()
    except OSError as exc:
        raise ShowcaseError(
            f'cannot read the showcase schema at {SCHEMA_PATH}: {exc}. The pipeline '
            f'will NOT validate without it -- a skipped schema check is exactly the '
            f'permissive-validator defect this replaced.') from exc
    try:
        doc = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ShowcaseError(
            f'{SCHEMA_PATH} is not valid JSON: {exc}') from exc
    if not isinstance(doc, dict):
        raise ShowcaseError(f'{SCHEMA_PATH} must contain a JSON object at the root')
    return _Schema(doc, source=str(SCHEMA_PATH))


def _validate(doc: dict) -> list[str]:
    """Validate a graph: the schema first, then the rules JSON Schema cannot state.

    The schema is the authority -- it is the same file the renderer validates
    against -- so its errors come first and are not softened by anything here.
    The extra checks that follow are narrow and each one is documented below with
    the consumer that breaks without it.
    """
    problems = schema().iter_errors(doc)

    # `scenes` must be a non-empty list OF OBJECTS. `additionalProperties` applies
    # only to objects, so `{"scenes": {"a": 1}}` satisfies `items` vacuously and
    # the per-scene rules below would then be checking a dict.
    scenes = doc.get('scenes')
    if not isinstance(scenes, list) or not scenes:
        # The schema already said so when it is empty; only add the shape claim.
        if not any('scenes' in p for p in problems):
            problems.append('scenes must be a non-empty array')
        return problems
    if not all(isinstance(s, dict) for s in scenes):
        problems.append('scenes must be an array of objects')
        return problems

    # DUPLICATE SCENE ID -- kept, and it is the only probe where Python was right
    # and the schema was silent. `FinanceShowcaseWide.tsx:156` resolves a scene
    # with `doc.scenes.find(x => x.id === r.id)`, so two scenes sharing an id
    # both render the FIRST one's content and the second silently vanishes.
    # JSON Schema cannot express uniqueness inside an array without `uniqueItems`
    # on a whole-object comparison, so it can never be covered by the schema.
    seen: set[str] = set()
    for i, s in enumerate(scenes):
        sid = s.get('id', f'#{i}')
        if sid in seen:
            problems.append(f'scenes[{i}]: duplicate scene id {sid!r} '
                            f'(the renderer looks scenes up by id, so the first '
                            f'one wins and this one never renders)')
        seen.add(sid)

    return problems


def beat_aligned_durations(doc: dict) -> list[str]:
    """Report beat drift, measured from the ACTUAL resolved timeline.

    Two earlier versions of this check were wrong in instructive ways:

    * It compared each scene's DURATION in isolation and reported "aligned" on
      a graph that drifted to 3.9 frames over 10 scenes. Per-scene duration
      says nothing about where the STARTS land.
    * It then re-implemented the beat arithmetic itself, so it silently
      disagreed with Showcase.resolve(). It now measures resolve()'s output.

    A beat is 28.5714 frames at 60 fps / 126 BPM, so integer frames can only
    approximate the grid. Half a frame is the achievable bound once timing is
    accumulated in beat space and rounded once (see Showcase.resolve).
    """
    fmt = doc.get('format') or {}
    fps = fmt.get('fps')
    if not isinstance(fps, int) or fps <= 0 or not doc.get('scenes'):
        return []
    sc = Showcase(project=doc.get('project', '?'), width=fmt.get('width', 0),
                  height=fmt.get('height', 0), fps=fps,
                  bpm=float(doc.get('bpm', 126)), scenes=doc['scenes'])
    out: list[str] = []
    for r in sc.resolve(beat_snap=True):
        drift = sc.beat_distance_frames(r.startFrame)
        if drift > 0.5 + 1e-6:
            out.append(f'{r.id}: start {r.startFrame} is {drift:.3f} frames off the '
                       f'beat — cumulative drift')
    return out


def load(path: Path) -> Showcase:
    doc = json.loads(Path(path).read_text(encoding='utf-8'))
    problems = _validate(doc)
    if problems:
        raise ShowcaseError('; '.join(problems))
    fmt = doc['format']
    return Showcase(
        project=doc['project'],
        width=fmt['width'], height=fmt['height'], fps=fmt['fps'],
        bpm=float(doc.get('bpm', 126)),
        scenes=doc['scenes'],
        style_bible=doc.get('style_bible') or {},
    )


def load_or_report(path: Path) -> tuple[Showcase | None, list[str]]:
    doc = json.loads(Path(path).read_text(encoding='utf-8'))
    problems = _validate(doc)
    if problems:
        return None, problems
    fmt = doc['format']
    return Showcase(project=doc['project'], width=fmt['width'], height=fmt['height'],
                    fps=fmt['fps'], bpm=float(doc.get('bpm', 126)),
                    scenes=doc['scenes'],
                    style_bible=doc.get('style_bible') or {}), []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', required=True, type=Path)
    ap.add_argument('--resolve', action='store_true', help='print the resolved timeline')
    ap.add_argument('--beat-snap', action='store_true', help='snap starts to the beat grid')
    args = ap.parse_args()

    sc, problems = load_or_report(args.file)
    if sc is None:
        print(f'{len(problems)} problem(s):')
        for p in problems:
            print(f'  ! {p}')
        return 1

    print(f'project={sc.project} {sc.width}x{sc.height}@{sc.fps} '
          f'bpm={sc.bpm} scenes={len(sc.scenes)} total={sc.totalFrames}f '
          f'({sc.totalFrames / sc.fps:.2f}s)')
    gen = sc.generative_scenes()
    if gen:
        print(f'generative (H3) scenes: {[(g.id, g.type) for g in gen]}')
    else:
        print('generative (H3) scenes: none — fully programmatic')
    if args.resolve:
        print()
        for s in sc.resolve(beat_snap=args.beat_snap):
            mark = ' *' if s.adjusted else '  '
            print(f'  {s.id:22s} {s.type:16s} {s.startFrame:5d} +{s.durationInFrames:4d} '
                  f'[{s.startFrame / sc.fps:6.2f}s]{mark}')
        if args.beat_snap:
            res = sc.resolve(beat_snap=True)
            adj = [s for s in res if s.adjusted]
            print(f'\n  * = beat quantisation adjusted the length '
                  f'({len(adj)}/{len(res)} scenes); declared total '
                  f'{sc.totalFrames}f -> resolved {res[-1].endFrame}f')
    return 0


if __name__ == '__main__':
    sys.exit(main())
