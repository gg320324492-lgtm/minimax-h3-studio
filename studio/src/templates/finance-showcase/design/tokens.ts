/**
 * Premium design tokens (P4) — the shared brand language.
 *
 * Two rules make this a system rather than a pile of per-scene constants:
 *   1. One place decides what "premium" looks like. A scene never invents a
 *      colour or a font size; it asks for a role.
 *   2. Everything scales from the design height, so a 1080p and a 4K render of
 *      the same graph are the same picture.
 *
 * The reference language (premium fintech product film): near-black, warm
 * off-white ink, one gold accent, and colour used only where it carries
 * meaning. Less than 3 hues per screen.
 */

export const PALETTE = {
  // premium-dark — the default surface
  background: '#0A0A0C',
  backgroundAlt: '#101014',
  surface: '#141418',
  surfaceElevated: '#1C1C22',
  ink: '#F5F2EA',
  inkMuted: 'rgba(245, 242, 234, 0.62)',
  inkFaint: 'rgba(245, 242, 234, 0.34)',
  accent: '#E8C464',
  accentDim: 'rgba(232, 196, 100, 0.16)',
  positive: '#5AD878',
  negative: '#FF6B6B',
  grid: 'rgba(245, 242, 234, 0.07)',
  hairline: 'rgba(245, 242, 234, 0.12)',
  // premium-light — the counterpoint used for the data-plane / light sections
  lightBackground: '#F4F1EA',
  lightSurface: '#FFFFFF',
  lightInk: '#14140F',
  lightInkMuted: 'rgba(20, 20, 15, 0.58)',
} as const;

/** Typography roles. Sizes are at design height 1080 and scale from there. */
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
  /** tabular figures — non-negotiable for any number that animates */
  numeric: {size: 72, weight: 600, tracking: '-0.01em', leading: 1.1, tabular: true},
} as const;

export type TypeRole = keyof typeof TYPE;

export const FONT_SANS =
  '"Microsoft YaHei", "PingFang SC", "Noto Sans SC", system-ui, sans-serif';
/** Numerals get a tighter, more technical face when one is present. */
export const FONT_NUM =
  '"Bahnschrift", "DIN Alternate", "Segoe UI", var(--font-sans), sans-serif';

export const SPACE = {xs: 8, sm: 16, md: 24, lg: 40, xl: 64, xxl: 104, hero: 168} as const;

export const RADIUS = {chip: 999, card: 20, window: 14, panel: 28} as const;

export const DEPTH = {
  z0: 'translateZ(0)',
  z1: 'translateZ(60px)',
  z2: 'translateZ(140px)',
  z3: 'translateZ(240px)',
  zHero: 'translateZ(380px)',
} as const;

export const SHADOW = {
  near: '0 2px 12px rgba(0,0,0,0.35)',
  medium: '0 18px 48px rgba(0,0,0,0.45)',
  floating: '0 40px 120px rgba(0,0,0,0.55)',
  glowAccent: '0 0 64px rgba(232, 196, 100, 0.28)',
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

/** Design height the type scale is authored against. */
export const DESIGN_HEIGHT = 1080;

export const scaleFrom = (height: number) => height / DESIGN_HEIGHT;
