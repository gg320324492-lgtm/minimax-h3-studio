/**
 * Event bindings — P9 step 13. The six events 9.2 wants to bind to the beat grid,
 * and which of them can be asked about at all.
 *
 * The audit that produced this list (P9, step 5) found that the six events split
 * three ways, and the split is the whole content of this file:
 *
 *   QUERYABLE (2). `camera settle` and `chart finish` each have a pure function
 *   that answers "when". `cameraStateAt().t` is 0..1 progress through the camera
 *   move, so the move's end is derivable; `lifecycleAt()` returns the chart's
 *   phase for any frame, so the start of `focus` is derivable.
 *
 *   INPUT-ONLY (2). `cut` and `card arrival` have the DATA a binding would need —
 *   `transitionIn` names the wipe and its length, `Reveal`/`Stagger` know the
 *   spring — but no function exports the frame. Both are consumed inside a
 *   component: `SceneEnter` reads `transitionIn` and applies a transform, `Reveal`
 *   computes `Math.round(secs * comp.fps)` locally and never returns it. So a
 *   caller cannot ask "when does this cut land" without reimplementing the answer,
 *   and reimplementing it is how two copies drift.
 *
 *   ABSENT (2). `number finish` and `hit` have nothing. `countUp`'s 1.6s is a
 *   default parameter AND its call site passes the literal again, so it is not
 *   even a token — there is no value to read. `hit` does not exist anywhere in the
 *   template: no downbeat, no accent beat. (`onAccent` is a palette colour for text
 *   set on the accent, which is a different thing entirely and matches only by
 *   name.) And the measured reason `hit` cannot be faked is in `beatGrid.ts`: a
 *   permutation test over the analysed track's bass values finds NO index modulus
 *   that predicts loudness, so `i % 4` would be wrong.
 *
 * The four unavailable ones carry a `source` explaining exactly that, in the code,
 * because "not available" with no reason is indistinguishable from "not looked at".
 * The guards in `bindings.check.ts` reject a short or empty `source` for precisely
 * that reason: `''` and `'n/a'` both pass a truthiness test and both tell a later
 * reader nothing.
 *
 * Zero react, zero remotion. Two of the six answers come from real functions —
 * `cameraMoveFrames` and `lifecycleAt` — and importing them is the point: the
 * bindings cannot disagree with the motion system about when a camera settles,
 * because they ask it rather than recompute it.
 */

import {cameraMoveFrames} from '../design/tokens';
import {lifecycleAt} from '../charts/lifecycle';

export const BINDING_EVENTS = [
  'camera-settle',
  'chart-finish',
  'cut',
  'card-arrival',
  'number-finish',
  'hit',
] as const;

export type BindingEvent = (typeof BINDING_EVENTS)[number];

export type BindingScene = {
  id: string;
  type: string;
  durationInFrames: number;
  /** start frame on the shipped timeline */
  startFrame: number;
};

export type BindingDoc = {
  fps: number;
  scenes: BindingScene[];
};

export type Binding = {
  /** is there a queryable surface for this event at all */
  available: boolean;
  /**
   * The event's frame, or null when unavailable.
   *
   * SCENE-RELATIVE, not film-absolute. Both available events are per-scene
   * properties — the camera belongs to the scene it is inside, and the chart
   * lifecycle is bounded by the scene's duration — so a film-absolute frame would
   * be a number nobody can compare against the function that produced it. Callers
   * add `scene.startFrame` if they want the film's timeline.
   */
  frame: number | null;
  /** what answered, or why nothing could */
  source: string;
};

/**
 * Which scene a frame belongs to. Used to scope the two per-scene events, so the
 * caller's `frame` argument does real work instead of being ignored.
 */
export const sceneAt = (doc: BindingDoc, frame: number): BindingScene | null => {
  if (!doc.scenes.length) return null;
  for (const s of doc.scenes) {
    if (frame >= s.startFrame && frame < s.startFrame + s.durationInFrames) return s;
  }
  // past the end: the last scene, so a query at the film's tail still answers
  return doc.scenes[doc.scenes.length - 1];
};

/**
 * The frame at which the chart lifecycle enters `focus` — the reading moment, and
 * the natural "the chart has finished" signal: after it, nothing moves.
 *
 * Found by asking `lifecycleAt` rather than by recomputing `WEIGHTS` and
 * `EXIT_SHARE`. Those are exported and a second copy of the arithmetic would be
 * one edit away from disagreeing with the chart it describes; phase is monotone in
 * frame, so a binary search over the real function is both cheap and incapable of
 * drifting. ~8 calls for a 150-frame scene.
 *
 * Returns the SCENE's duration when `focus` never begins, which is the honest
 * answer for a scene too short to hold a reading phase rather than a guess.
 */
export const focusStartFrame = (durationInFrames: number, count = 1): number => {
  const dur = Math.max(1, Math.floor(durationInFrames));
  const at = (f: number): boolean => lifecycleAt({frame: f, durationInFrames: dur, count}).phase === 'focus';
  if (at(0)) return 0;
  let lo = 0;
  let hi = dur;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (at(mid)) hi = mid;
    else lo = mid + 1;
  }
  return lo;
};

const SOURCES = {
  'camera-settle':
    'cameraMoveFrames(preset, durationInFrames, fps) in design/tokens.ts, via cameraStateAt().t. ' +
    'Wall-clock anchored since P8: seconds * fps, not a fraction of the scene.',
  'chart-finish':
    'focus phase start from charts/lifecycle.ts lifecycleAt(), located by binary search ' +
    'rather than recomputed from WEIGHTS so the binding cannot drift from the chart.',
  cut:
    'No queryable surface. transitionIn exists in showcase-v1.ts and SceneEnter consumes it ' +
    'internally (common/primitives.tsx), applying opacity/clipPath/translateZ without ever ' +
    'exposing the frame it lands on. A binding would have to reimplement SceneEnter.',
  'card-arrival':
    'No queryable surface. Reveal and Stagger (common/primitives.tsx) compute the spring length ' +
    'locally as Math.round(secs * comp.fps) and return only the rendered element; the value ' +
    'never leaves the component.',
  'number-finish':
    'No input and no query surface. countUp in scenes/KpiHero.tsx takes seconds = 1.6 as a ' +
    'default parameter AND its call site passes the literal 1.6 again, so the duration is not ' +
    'a token and cannot be read by anything. The value is also interpolated separately at ' +
    'lines 57 for the delta, so there is no single "finished" instant to name.',
  hit:
    'Does not exist. No downbeat, accent beat or hit concept anywhere in the template; ' +
    "onAccent is a palette colour for text on the accent, unrelated to metre. It also must " +
    'not be faked as i % 4: a permutation test over the analysed track finds no index modulus ' +
    'that predicts bass (mod 4 spread 0.032 against a shuffled-null 95th percentile of 0.070). ' +
    'Accent is available from beatGrid.ts grid().accent instead, measured from the audio.',
} as const;

export const bindingFor = (
  event: BindingEvent,
  doc: BindingDoc,
  frame: number
): Binding => {
  const scene = sceneAt(doc, frame);
  switch (event) {
    case 'camera-settle': {
      if (!scene) return {available: false, frame: null, source: 'no scene contains the frame'};
      const preset = 'premium';
      return {
        available: true,
        frame: Math.ceil(cameraMoveFrames(preset, scene.durationInFrames, doc.fps)),
        source: SOURCES['camera-settle'],
      };
    }
    case 'chart-finish': {
      if (!scene) return {available: false, frame: null, source: 'no scene contains the frame'};
      return {
        available: true,
        frame: focusStartFrame(scene.durationInFrames),
        source: SOURCES['chart-finish'],
      };
    }
    case 'cut':
      return {available: false, frame: null, source: SOURCES.cut};
    case 'card-arrival':
      return {available: false, frame: null, source: SOURCES['card-arrival']};
    case 'number-finish':
      return {available: false, frame: null, source: SOURCES['number-finish']};
    case 'hit':
      return {available: false, frame: null, source: SOURCES.hit};
    default: {
      // Unreachable for a well-typed caller, and deliberately not a silent null:
      // an unknown event name is a bug in the caller, and returning "unavailable"
      // for it would put it in the same bucket as the four that genuinely have no
      // surface.
      const never: never = event;
      throw new Error(`unknown binding event ${String(never)}`);
    }
  }
};

/** Which events have a queryable surface, in `BINDING_EVENTS` order. */
export const availableEvents = (doc: BindingDoc, frame: number): BindingEvent[] =>
  BINDING_EVENTS.filter((e) => bindingFor(e, doc, frame).available);
