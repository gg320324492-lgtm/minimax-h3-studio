import React, {createContext, useContext, useMemo} from 'react';
import {useVideoConfig} from 'remotion';
import {PALETTE, TYPE, MOTION, SPACE, RADIUS, DEPTH, SHADOW, DESIGN_HEIGHT, FONT_NUM, FONT_SANS, scaleFrom} from './tokens';

/**
 * Style Bible resolution (P4 review finding).
 *
 * The graph declared palette / typography / motionLanguage / cameraLanguage and
 * the renderer ignored all of it — every scene imported the static TS tokens.
 * That split brain would have hardened in P5, where motion tokens were about to
 * be centralised.
 *
 * The fix is structural: the graph's style bible is resolved here, merged over
 * the built-in defaults, and published through context. A scene asks for a
 * role (`palette.accent`, `type.kpiXL`); it never imports a colour, so a graph
 * that sets a different accent actually changes the film. Reading a raw import
 * instead of context is the mistake this file makes hard to repeat.
 */

export type StyleBible = {
  palette: Record<string, string>;
  typography: Record<string, {size: number; weight: number; tracking: string; leading: number; tabular?: boolean}>;
  spacing: Record<string, number>;
  radius: Record<string, number>;
  shadow: Record<string, string>;
  depth: Record<string, string>;
  motion: typeof MOTION;
  camera: {perspective: number; durationSeconds: number};
};

const DEFAULT_BIBLE: StyleBible = {
  palette: {...PALETTE},
  typography: {...TYPE} as StyleBible['typography'],
  spacing: {...SPACE},
  radius: {...RADIUS},
  shadow: {...SHADOW},
  depth: {...DEPTH},
  motion: {...MOTION},
  camera: {perspective: 1400, durationSeconds: MOTION.premiumCameraSeconds},
};

/**
 * Merge a graph-provided section over the defaults, ignoring keys the defaults
 * do not define. Filtering by the DEFAULT's own keys (rather than spreading a
 * Partial<T>) keeps the result type exact and means a typo in the graph cannot
 * widen or blank a token — it is simply not applied.
 */
const mergeSection = <T extends Record<string, unknown>>(base: T, over: unknown): T => {
  const src = (over ?? {}) as Record<string, unknown>;
  const out: Record<string, unknown> = {...base};
  for (const key of Object.keys(base)) {
    const v = src[key];
    if (v !== undefined && v !== null && typeof v === typeof base[key]) {
      out[key] = v;
    }
  }
  return out as T;
};

/** Shallow-merge each section so a graph may override one colour, not all. */
export const resolveStyleBible = (input?: unknown): StyleBible => {
  const b = (input ?? {}) as Record<string, unknown>;
  const section = (name: string): Record<string, unknown> =>
    (b[name] ?? {}) as Record<string, unknown>;
  return {
    palette: mergeSection(DEFAULT_BIBLE.palette, section('palette')),
    typography: mergeSection(DEFAULT_BIBLE.typography, section('typography')),
    spacing: mergeSection(DEFAULT_BIBLE.spacing, section('spacing')),
    radius: mergeSection(DEFAULT_BIBLE.radius, section('radius')),
    shadow: mergeSection(DEFAULT_BIBLE.shadow, section('shadow')),
    depth: mergeSection(DEFAULT_BIBLE.depth, section('depth')),
    motion: mergeSection(DEFAULT_BIBLE.motion, section('motionLanguage')),
    camera: mergeSection(DEFAULT_BIBLE.camera, section('cameraLanguage')),
  };
};

const StyleBibleContext = createContext<StyleBible>(DEFAULT_BIBLE);

export const StyleBibleProvider: React.FC<{bible?: unknown; children: React.ReactNode}> = ({
  bible,
  children,
}) => {
  const resolved = useMemo(() => resolveStyleBible(bible), [bible]);
  return <StyleBibleContext.Provider value={resolved}>{children}</StyleBibleContext.Provider>;
};

/** Every scene reads design through this. There is deliberately no other path. */
export const useStyle = (): StyleBible => useContext(StyleBibleContext);

/** Design-height scaling. */
export const useScale = (): number => {
  const {height} = useVideoConfig();
  return height / DESIGN_HEIGHT;
};
/**
 * One hook per component, names aliased the way scenes already used them, so
 * the migration is a single destructure per component. Scenes must not import
 * design values directly: that is what made the graph's style bible decorative.
 */
export const useDesign = () => {
  const s = useStyle();
  return {
    PALETTE: s.palette,
    TYPE: s.typography,
    MOTION: s.motion,
    SPACE: s.spacing,
    RADIUS: s.radius,
    SHADOW: s.shadow,
    DEPTH: s.depth,
    camera: s.camera,
    FONT_NUM,
    FONT_SANS,
    scaleFrom,
  };
};
