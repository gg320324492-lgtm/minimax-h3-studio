/**
 * Themes — a complete surface language, not a colour swap (P6.5).
 *
 * The graph could already say `theme: 'premium-light'` and Backdrop would
 * lighten the background, but the scenes kept reading premium-dark tokens: you
 * got a pale backdrop behind black windows. Half-wired is worse than absent,
 * because the field looked like it worked.
 *
 * A theme therefore carries everything that changes with the surface, and a
 * scene never assembles a theme by mixing tokens from two of them:
 *
 *   palette — ink, surfaces, accent
 *   shadow  — a shadow tuned for a near-black ground is invisible on paper, and
 *             a shadow tuned for paper is a bruise on near-black. So the whole
 *             ramp, including DEPTH_CUE, is per-theme.
 *
 * What does NOT change: type scale, spacing, radius, motion, camera. Those are
 * the brand; the surface is the skin. Keeping them out of the theme is what
 * stops "add a theme" from turning into "redesign the design system".
 */

export type ThemeName = 'premium-dark' | 'premium-light';

export type Theme = {
  palette: Record<string, string>;
  shadow: Record<string, string>;
  /** one shadow per depth step, far plane first */
  depthCue: readonly string[];
};

const darkPalette = {
  background: '#0A0A0C',
  backgroundAlt: '#101014',
  surface: '#141418',
  surfaceElevated: '#1C1C22',
  ink: '#F5F2EA',
  inkMuted: 'rgba(245, 242, 234, 0.62)',
  inkFaint: 'rgba(245, 242, 234, 0.34)',
  accent: '#E8C464',
  accentDim: 'rgba(232, 196, 100, 0.16)',
  /** readable as text on the gold accent — used for a highlighted grid cell */
  onAccent: '#14140F',
  positive: '#5AD878',
  negative: '#FF6B6B',
  grid: 'rgba(245, 242, 234, 0.07)',
  hairline: 'rgba(245, 242, 234, 0.12)',
  /**
   * Data marks. These were inline rgba() literals in three scenes, at two
   * different alphas, so the same "a column" was one colour in DataColumns and
   * another in BrowserStack. A mark's weight is a design decision, so it gets
   * a name.
   */
  column: 'rgba(245, 242, 234, 0.16)',
  columnBright: 'rgba(245, 242, 234, 0.32)',
} as const;

const lightPalette = {
  background: '#F4F1EA',
  backgroundAlt: '#FFFFFF',
  surface: '#FFFFFF',
  surfaceElevated: '#FBFAF6',
  ink: '#14140F',
  inkMuted: 'rgba(20, 20, 15, 0.62)',
  inkFaint: 'rgba(20, 20, 15, 0.34)',
  // a deeper gold: the dark theme's #E8C464 has too little contrast on paper
  // to carry a headline, and gold that disappears is worse than gold that
  // reads as ochre
  accent: '#A8801F',
  accentDim: 'rgba(168, 128, 31, 0.14)',
  onAccent: '#FFFFFF',
  positive: '#1E8E4A',
  negative: '#C0392B',
  grid: 'rgba(20, 20, 15, 0.07)',
  hairline: 'rgba(20, 20, 15, 0.12)',
  column: 'rgba(20, 20, 15, 0.16)',
  columnBright: 'rgba(20, 20, 15, 0.32)',
} as const;

export const THEMES: Record<ThemeName, Theme> = {
  'premium-dark': {
    palette: darkPalette,
    shadow: {
      near: '0 2px 12px rgba(0,0,0,0.35)',
      medium: '0 18px 48px rgba(0,0,0,0.45)',
      floating: '0 40px 120px rgba(0,0,0,0.55)',
      glowAccent: '0 0 64px rgba(232, 196, 100, 0.28)',
    },
    depthCue: [
      '0 14px 40px rgba(0,0,0,0.40)',
      '0 30px 84px rgba(0,0,0,0.50)',
      '0 46px 132px rgba(0,0,0,0.62)',
    ],
  },
  'premium-light': {
    palette: lightPalette,
    // same shapes, much lower alpha: on paper a 0.55 black shadow reads as a
    // smudge, and the point of the light theme is that it looks like paper
    shadow: {
      near: '0 1px 4px rgba(20,20,15,0.10)',
      medium: '0 10px 28px rgba(20,20,15,0.13)',
      floating: '0 26px 70px rgba(20,20,15,0.17)',
      glowAccent: '0 0 40px rgba(168, 128, 31, 0.24)',
    },
    depthCue: [
      '0 8px 22px rgba(20,20,15,0.10)',
      '0 18px 48px rgba(20,20,15,0.14)',
      '0 30px 80px rgba(20,20,15,0.19)',
    ],
  },
};

export const DEFAULT_THEME: ThemeName = 'premium-dark';

/** Unknown theme names fall back rather than throw — a typo must not black out a render. */
export const themeNamed = (name: unknown): ThemeName =>
  typeof name === 'string' && name in THEMES ? (name as ThemeName) : DEFAULT_THEME;
