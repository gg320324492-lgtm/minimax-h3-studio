/**
 * The chart lifecycle — one timeline, shared by all nine marks (P7.2).
 *
 * Before this, every mark invented its own entrance. `Bar` grew on a `land`
 * spring, `PathMark` drew itself on with a dash offset, `Slope` extended its
 * lines from the left, `Heatmap` scaled its cells in — and each read the same
 * two options differently. Nine charts in one film therefore did not feel like
 * one film: the same "arrive" happened nine ways.
 *
 * A lifecycle fixes that by being a pure function of (frame, duration, count,
 * options). Every mark asks the same questions — how far into the entrance am
 * I, how much attention does this mark get, is anything leaving — and gets the
 * same answer, so consistency is structural rather than nine implementations
 * happening to agree.
 *
 * The five phases, and why each exists:
 *
 *   intro     the marks assemble, staggered. Long, eased, no overshoot: a chart
 *             that bounces in looks like a chart that wants attention.
 *   settle    the stagger completes and the emphasised mark arrives. The chart
 *             stops introducing itself and starts being read.
 *   highlight the emphasised mark is held at full attention. Not animated —
 *             held. A premium chart says one thing by doing nothing to it.
 *   focus     the reading moment. Nothing moves; the value labels and the
 *             emphasised mark are simply the brightest things on screen.
 *   exit      the marks leave, faster than they came in. A chart that fades out
 *             over as long as it faded in has no ending.
 *
 * Phases are FRACTIONS of the scene, not fixed frame counts, so a 90-frame chart
 * and a 600-frame chart both read correctly. The exception is the entrance
 * itself: a spring needs frames to be a spring, so `enterFrames` and
 * `staggerFrames` still cap it, and the intro is the shorter of "the scene's
 * share" and "how long the marks actually take". Without that cap a 40-frame
 * scene would still be arriving when it cuts.
 */

import type {ChartOptions} from './options';

export type Phase = 'intro' | 'settle' | 'highlight' | 'focus' | 'exit';

export const PHASES: readonly Phase[] = ['intro', 'settle', 'highlight', 'focus', 'exit'];

/** How the scene's frames are divided, before the entrance cap is applied. */
export const WEIGHTS = {
  intro: 0.34,
  settle: 0.12,
  highlight: 0.18,
  focus: 0.36,
} as const;

/** The exit takes what is left over, and is never zero-length. */
const EXIT_SHARE = 0.08;
const EXIT_MIN = 6;

export type Lifecycle = {
  phase: Phase;
  /** clamped scene frame, so callers never have to bounds-check */
  frameInScene: number;
  /** 0..1 through the whole scene */
  t: number;
  /** 0..1 through the current phase */
  phaseT: number;
  /** how long the shared entrance lasts, after the cap */
  entranceFrames: number;
  /** 0..1 for the FIRST mark; a staggered mark adds its own delay */
  enter: number;
  /** 0..1 attention for the emphasised mark; equals a plain curve when none */
  emphasis: number;
  /** 0..1 for the leaving transition; 0 until the exit begins */
  exit: number;
  /** 1 while present, easing to 0 through the exit */
  presence: number;
  /** true only during `focus`, when nothing should move */
  reading: boolean;
};

export type LifecycleInput = {
  frame: number;
  durationInFrames: number;
  /** how many marks are staggered; 1 for a single-mark chart */
  count?: number;
  emphasisIndex?: number;
  opts?: Pick<ChartOptions, 'enterFrames' | 'staggerFrames'> | null;
};

/**
 * An ease-out with no overshoot.
 *
 * Deliberately not a spring. A chart that bounces has asked to be looked at
 * twice, and the reference language is a chart that states a number once.
 */
export const easeOut = (x: number): number => {
  const t = x < 0 ? 0 : x > 1 ? 1 : x;
  return 1 - (1 - t) ** 3;
};

export const clamp01 = (x: number): number => (x < 0 ? 0 : x > 1 ? 1 : x);

export const lifecycleAt = (input: LifecycleInput): Lifecycle => {
  const {
    frame, durationInFrames, count = 1, emphasisIndex = -1, opts,
  } = input;
  const dur = Math.max(1, Math.floor(durationInFrames));
  const f = clampFrame(frame, dur);
  const t = f / dur;

  const enterFrames = Math.max(1, Math.round(opts?.enterFrames ?? 34));
  const staggerFrames = Math.max(0, Math.round(opts?.staggerFrames ?? 2));

  // The entrance lasts as long as the marks need and no longer. The 0.4 tail is
  // the settle of the LAST mark, so the intro ends with everything arrived
  // rather than with the final mark still at full growth.
  const needed = enterFrames * 1.4 + staggerFrames * Math.max(count - 1, 0);
  const exitFrames = Math.max(EXIT_MIN, Math.round(dur * EXIT_SHARE));
  const entranceFrames = Math.max(
    1,
    Math.min(Math.round(dur * WEIGHTS.intro), needed, dur - exitFrames)
  );

  const exitStart = dur - exitFrames;
  const bIntro = entranceFrames;
  const bSettle = Math.min(exitStart, bIntro + Math.round(dur * WEIGHTS.settle));
  const bHighlight = Math.min(exitStart, bSettle + Math.round(dur * WEIGHTS.highlight));

  const phase: Phase =
    f >= exitStart ? 'exit'
      : f >= bHighlight ? 'focus'
        : f >= bSettle ? 'highlight'
          : f >= bIntro ? 'settle'
            : 'intro';

  const start =
    phase === 'intro' ? 0
      : phase === 'settle' ? bIntro
        : phase === 'highlight' ? bSettle
          : phase === 'focus' ? bHighlight
            : exitStart;
  const end =
    phase === 'intro' ? bIntro
      : phase === 'settle' ? bSettle
        : phase === 'highlight' ? bHighlight
          : phase === 'focus' ? exitStart
            : dur;
  const phaseT = end > start ? clamp01((f - start) / (end - start)) : 1;

  const enter = easeOut(f / entranceFrames);

  // The emphasised mark's attention is a property of the PHASE, not a second
  // frame-by-frame animation: it rises through the intro, arrives during the
  // settle, and is then simply held. That is what "highlight" means.
  const emphasis = emphasisIndex >= 0
    ? easeOut(phase === 'intro'
      ? 0.45 * phaseT
      : phase === 'settle'
        ? 0.45 + 0.55 * phaseT
        : 1)
    : enter;

  const exit = f >= exitStart ? easeOut((f - exitStart) / exitFrames) : 0;

  return {
    phase, frameInScene: f, t, phaseT, entranceFrames, enter, emphasis,
    exit, presence: 1 - exit,
    reading: phase === 'focus',
  };
};

const clampFrame = (frame: number, dur: number): number => {
  const f = Math.floor(frame);
  return f < 0 ? 0 : f > dur ? dur : f;
};

/**
 * One mark's staggered entrance, derived from the SHARED timeline.
 *
 * This is the only place a mark's own delay is applied. `enterFor` used to exist
 * as a second implementation of the same arithmetic, which is precisely the
 * duplication this module exists to remove — so there is one function, it takes
 * the shared length rather than recomputing it, and a mark cannot drift out of
 * step with the phase it is supposedly in.
 */
export const enterFor = (
  life: Lifecycle,
  index: number,
  staggerFrames: number
): number => {
  const delay = Math.max(0, Math.round(staggerFrames)) * Math.max(index, 0);
  return easeOut((life.frameInScene - delay) / Math.max(life.entranceFrames, 1));
};

/** Where a mark sits in the stagger, 0 for the first and 1 for the last. */
export const staggerPosition = (index: number, count: number): number =>
  count > 1 ? index / (count - 1) : 0;
