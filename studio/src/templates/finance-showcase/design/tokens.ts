/**
 * Premium design tokens (P4) — the shared brand language.
 *
 * Two rules make this a system rather than a pile of per-scene constants:
 *   1. One place decides what "premium" looks like. A scene never invents a
 *      colour or a font size; it asks for a role.
 *   2. Everything scales from the design FRAME, so a 1080p and a 4K render of
 *      the same graph are the same picture. The scale is `scaleFor` below and
 *      reads both axes — see the note there for why the height alone is not
 *      enough.
 *
 * The reference language (premium fintech product film): near-black, warm
 * off-white ink, one gold accent, and colour used only where it carries
 * meaning. Less than 3 hues per screen.
 */

/**
 * The default theme's palette and shadows.
 *
 * These are NOT the definition — `themes.ts` is, because a theme has to be
 * able to change them. They stay exported under the old names so existing call
 * sites resolve, but a SCENE must read them through the style bible, never by
 * importing here: importing here is exactly what made a graph's `theme` field
 * decorative when only the backdrop honoured it.
 */
import {THEMES} from './themes';

export const PALETTE = THEMES['premium-dark'].palette;
export const SHADOW = THEMES['premium-dark'].shadow;
export const DEPTH_CUE = THEMES['premium-dark'].depthCue;

/**
 * Typography roles. Sizes are at design height 1080 and scale from there.
 *
 * Numeric roles are separate from the display roles on purpose. A headline
 * figure and a figure in a table are the same NUMBER but different typography:
 * the headline wants tight tracking and a heavy weight, a table wants a size
 * where digits are the same width as each other and nothing shifts as it counts.
 * Before these existed, KpiHero reached for kpiXL — a display role — to set a
 * number that animates, which is why it had to set tabular figures by hand to
 * stop the digits jittering.
 */
export const TYPE = {
  displayXL: {size: 148, weight: 800, tracking: '-0.03em', leading: 1.02},
  displayL: {size: 112, weight: 800, tracking: '-0.025em', leading: 1.05},
  kpiXL: {size: 232, weight: 700, tracking: '-0.04em', leading: 0.94},
  kpiL: {size: 148, weight: 700, tracking: '-0.035em', leading: 0.98},
  heading: {size: 64, weight: 700, tracking: '-0.015em', leading: 1.15},
  subheading: {size: 44, weight: 600, tracking: '0', leading: 1.2},
  body: {size: 32, weight: 400, tracking: '0', leading: 1.4},
  caption: {size: 26, weight: 400, tracking: '0.01em', leading: 1.35},
  annotation: {size: 20, weight: 500, tracking: '0.08em', leading: 1.2},
  /** the hero figure: display scale, but a NUMERIC face and tabular figures */
  numericDisplay: {
    size: 232, weight: 700, tracking: '-0.04em', leading: 0.94, tabular: true,
  },
  /** a figure in a table or a stat row: fits a column, never reflows */
  numericTable: {size: 52, weight: 700, tracking: '-0.02em', leading: 1.1, tabular: true},
  /** tabular figures — non-negotiable for any number that animates */
  numeric: {size: 72, weight: 600, tracking: '-0.01em', leading: 1.1, tabular: true},
} as const;

export type TypeRole = keyof typeof TYPE;

export const FONT_SANS =
  '"Microsoft YaHei", "PingFang SC", "Noto Sans SC", system-ui, sans-serif';
/** Numerals get a tighter, more technical face when one is present. */
export const FONT_NUM =
  '"Bahnschrift", "DIN Alternate", "Segoe UI", var(--font-sans), sans-serif';

/**
 * The macOS window controls.
 *
 * Deliberately NOT theme-scoped, and that is the point: these three dots are a
 * UI convention, and a "light theme" version of a red dot is still a red dot.
 * Recolouring them to match a paper background would stop them reading as
 * window controls at all. They live in tokens rather than inline in the scene
 * so the exemption is a named value instead of a hex literal nobody can find.
 */
export const TRAFFIC_LIGHTS = ['#FF5F57', '#FEBC2E', '#28C840'] as const;

export const SPACE = {xs: 8, sm: 16, md: 24, lg: 40, xl: 64, xxl: 104, hero: 168} as const;

export const RADIUS = {chip: 999, card: 20, window: 14, panel: 28} as const;

/**
 * Depth planes, as CSS transform strings.
 *
 * Note the honest state of this table: no scene uses it. Every scene computes
 * its own z from the graph's spread values, because a scene's depth is a
 * function of its composition rather than a fixed step. It stays exported for
 * scenes that DO want a fixed plane (a floating card over a page), but P6.8
 * should not be recorded as done on the strength of this table existing.
 */
export const DEPTH = {
  z0: 'translateZ(0)',
  z1: 'translateZ(60px)',
  z2: 'translateZ(140px)',
  z3: 'translateZ(240px)',
  zHero: 'translateZ(380px)',
} as const;

/**
 * Motion presets (P5).
 *
 * Named by INTENT, not by physics. A scene asks for "settle" or "reveal"; it
 * never picks damping and stiffness itself. That is the whole point: before this
 * table, `damping: 200` appeared three times and `20/100` twice across three
 * scenes, each hand-tuned, and two entrances that should have felt identical
 * did not.
 *
 * Profiles sit on top of the same primitives, so `premium` and `energetic` are a
 * duration/easing choice rather than a different vocabulary.
 */
export type MotionProfile = 'premium' | 'energetic' | 'cinematic' | 'minimal';

export const SPRINGS = {
  /** deliberate, no overshoot — the default for anything that must feel calm */
  settle: {damping: 200, stiffness: 120},
  /** small confident pop (badges, chips, icons) */
  pop: {damping: 14, stiffness: 200},
  /** a large object arriving: lands and sits down, tiny overshoot */
  land: {damping: 20, stiffness: 100},
  /** data marks appearing in sequence — quick, unobtrusive */
  reveal: {damping: 22, stiffness: 160},
  /** expressive settle for hero moments (used sparingly) */
  hero: {damping: 16, stiffness: 120},
  /** scale/position hand-off, no spring character at all */
  linear: {damping: 200, stiffness: 200},
} as const;

export type SpringName = keyof typeof SPRINGS;

export const MOTION = {
  springs: SPRINGS,

  /** durations in seconds, at 24fps-equivalent authoring */
  durations: {
    micro: 0.28,
    standard: 0.52,
    enter: 0.72,
    settle: 1.15,
    reveal: 0.9,
    hero: 1.4,
    cameraSlow: 2.6,
    cameraFast: 0.55,
  },

  /**
   * Per-profile overrides. Premium spends frames and never bounces; energetic
   * is short and pops once. This is what makes the two templates feel like
   * different languages without two vocabularies.
   */
  profiles: {
    premium: {stagger: 0.035, spring: 'settle', ease: [0.16, 1, 0.3, 1] as [number, number, number, number]},
    energetic: {stagger: 0.02, spring: 'pop', ease: [0.34, 1.56, 0.64, 1] as [number, number, number, number]},
    cinematic: {stagger: 0.06, spring: 'hero', ease: [0.65, 0, 0.35, 1] as [number, number, number, number]},
    minimal: {stagger: 0.05, spring: 'linear', ease: [0.25, 1, 0.5, 1] as [number, number, number, number]},
  },

  /** legacy fields kept so older call sites still resolve */
  enterSeconds: 0.72,
  enterEase: [0.16, 1, 0.3, 1] as [number, number, number, number],
  settleSeconds: 1.15,
  staggerDefault: 0.035,
  premiumCameraSeconds: 2.6,
  energeticCameraSeconds: 0.55,
} as const;

export const profileOf = (name: MotionProfile = 'premium') =>
  MOTION.profiles[name] ?? MOTION.profiles.premium;

/**
 * The design frame the token scale is authored against.
 *
 * Both numbers exist because the scale depends on BOTH, and the missing half is
 * what produced the P8 defect: `DESIGN_HEIGHT` was here alone, so the only
 * scaler available was `height / 1080` and nothing in the template could ask
 * how wide the frame is. At 1080x1920 that returns 1.7778 and the layout keeps
 * a 1920-wide design frame's worth of horizontal geometry inside a 1080-wide
 * one — measured, not suspected: on the demo graph's dashboard scene it put 18
 * columns where 12 fit and cut ~357px off each edge.
 */
export const DESIGN_HEIGHT = 1080;
export const DESIGN_WIDTH = 1920;

/**
 * The single scaler: fit the design frame into the render frame.
 *
 * `min` of the two ratios, i.e. CONTAIN. Type and spacing are authored at the
 * design frame, so a frame that is proportionally larger on one axis gets the
 * scale that keeps the other axis inside it — never the scale that fills the
 * taller axis and overruns the narrower one.
 *
 * Note what this deliberately does NOT do: adapt the layout to the new aspect
 * ratio. A 1080x1920 render of a wide graph is a wide composition letterboxed
 * into a portrait frame, with the design frame's own proportions intact and its
 * content centred, rather than a portrait composition. Reflowing the layout is
 * a different and much larger decision (per-scene horizontal geometry), and
 * getting it wrong is how a vertical render ends up cropped instead of small.
 *
 * 1920x1080 -> 1 and 3840x2160 -> 2, both exactly, which is why this change is
 * invisible to every existing 16:9 render.
 */
export const scaleFor = (width: number, height: number): number =>
  Math.min(width / DESIGN_WIDTH, height / DESIGN_HEIGHT);

/**
 * How many frames the camera move takes, for a given scene and fps.
 *
 * A motion DURATION is a wall-clock quantity, so it converts through fps the
 * way every other duration in this template does (`secs * comp.fps`). The form
 * it replaces was `Math.max(1, seconds * fps / sceneFrames)`, used as a ramp
 * against normalised scene time — and the `Math.max` is the whole story.
 *
 * That clamp can only raise the ramp, and it raised it to exactly 1 for every
 * scene longer than the nominal move: 2.6s is 156 frames at 60fps, and the demo
 * graph's scenes are 229. So the ramp was 1, the camera moved across the WHOLE
 * scene, and `premiumCameraSeconds` was multiplied out and then discarded. The
 * function was correct as written and meant nothing, which is the same shape of
 * failure as a declared chart option nothing reads.
 *
 * The fps dependence that hid inside it was real but narrow — it only bit scenes
 * shorter than the nominal duration, where the ramp could exceed 1 and the move
 * overran the scene by an amount that moved when fps moved.
 *
 * Making the token live CHANGES existing 16:9 renders, and deliberately: a
 * premium move now completes at frame 156 of a 229-frame scene instead of
 * drifting to the last one, which is what `premiumCameraSeconds: 2.6` and the two
 * comments in CameraRig have always said the camera did.
 *
 * `minimal` is the one profile expressed in scene time rather than seconds — it
 * means "the move lasts the whole scene", which is a statement about the scene
 * and so is deliberately the scene's own length.
 */
export const cameraMoveFrames = (
  preset: string | undefined,
  sceneFrames: number,
  fps: number
): number => {
  if (preset === 'minimal') return Math.max(1, sceneFrames);
  const seconds = preset === 'energetic' ? MOTION.energeticCameraSeconds : MOTION.premiumCameraSeconds;
  // NOT clamped, and NOT rounded.
  //
  // Clamping: `Math.max(1, ...)` is what made the token inert — it turns a
  // fractional frame count into a whole scene. Rounding: this value is a divisor
  // (progress is `frame / moveFrames`), so a half frame costs nothing, while
  // rounding makes the move a frame too long at half the frame rate — energetic
  // is 0.55s, which is 16.5 frames at 30fps, and `Math.round` turns that into 17.
  // Both would reintroduce, in the ramp, the fps-dependence the conversion exists
  // to remove.
  return Math.max(1, seconds * fps);
};
