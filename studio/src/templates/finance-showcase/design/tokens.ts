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

/** Motion presets. Premium = long, eased, spatial; energetic = short and punchy. */
export type MotionProfile = 'premium' | 'energetic' | 'cinematic' | 'minimal';

export const MOTION = {
  /** standard entrances share these so nothing feels hand-tuned differently */
  enterSeconds: 0.72,
  enterEase: [0.16, 1, 0.3, 1] as [number, number, number, number],
  settleSeconds: 1.15,
  staggerDefault: 0.035,
  premiumCameraSeconds: 2.6,
  energeticCameraSeconds: 0.55,
} as const;

/** Design height the type scale is authored against. */
export const DESIGN_HEIGHT = 1080;

export const scaleFrom = (height: number) => height / DESIGN_HEIGHT;
