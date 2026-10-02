import React, {createContext, useContext, useMemo} from 'react';
import {useVideoConfig} from 'remotion';
import {TYPE, MOTION, SPACE, RADIUS, FONT_NUM, FONT_SANS, scaleFor} from './tokens';
import {THEMES, themeNamed, type ThemeName} from './themes';

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
  /** which theme resolved this bible; scenes read the palette, not the name */
  theme: ThemeName;
  palette: Record<string, string>;
  typography: Record<string, {size: number; weight: number; tracking: string; leading: number; tabular?: boolean}>;
  spacing: Record<string, number>;
  radius: Record<string, number>;
  shadow: Record<string, string>;
  /** one shadow per depth step, far plane first */
  depthCue: readonly string[];
  motion: typeof MOTION;
  camera: {perspective: number; durationSeconds: number};
};

/** A list token is all-or-nothing: a partial ramp would silently mis-index. */
const mergeList = (base: readonly string[], over: unknown): readonly string[] =>
  Array.isArray(over) && over.length > 0 && over.every((v) => typeof v === 'string')
    ? (over as string[])
    : base;

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

/**
 * The parts of the bible that do NOT vary by theme.
 *
 * Type scale, spacing, radius, motion and camera are the brand; the palette and
 * shadows are the surface. Keeping that split explicit is what stops "add a
 * light theme" from quietly becoming a redesign — and it means a scene cannot
 * end up with light-theme ink on the dark theme's type scale, which is the
 * failure mode when the two get mixed section by section.
 */
const resolveInvariant = (b: Record<string, unknown>) => ({
  typography: mergeSection({...TYPE} as Record<string, unknown>, b.typography),
  spacing: mergeSection({...SPACE} as Record<string, unknown>, b.spacing),
  radius: mergeSection({...RADIUS} as Record<string, unknown>, b.radius),
  // `depth` USED to be merged here, from the same `b.depth`, and was deleted in
  // P12: zero consumers (measured three ways) and an input that could not exist,
  // because `StyleBibleSchema` never declared it and zod therefore stripped it on
  // every parse. The `DEPTH` table itself is untouched in tokens.ts — removing a
  // token is a larger call than removing a graph-facing binding.
  motion: mergeSection({...MOTION} as unknown as Record<string, unknown>, b.motionLanguage),
  camera: mergeSection(
    {perspective: 1400, durationSeconds: MOTION.premiumCameraSeconds} as Record<string, unknown>,
    b.cameraLanguage
  ),
});

/**
 * Resolve a graph's style bible against a named theme.
 *
 * `theme` is the per-scene one, not a film-level flag: a showcase that moves
 * from a dark act to a light data section switches theme scene by scene, and
 * that only works if resolution happens per scene. A scene's explicit
 * `style_bible` still overrides the theme, so a graph can nudge one colour in
 * one scene without restating the whole palette.
 */
export const resolveStyleBible = (input?: unknown, themeName?: unknown): StyleBible => {
  const b = (input ?? {}) as Record<string, unknown>;
  const theme = THEMES[themeNamed(themeName)];
  const section = (name: string): Record<string, unknown> =>
    (b[name] ?? {}) as Record<string, unknown>;
  return {
    theme: themeNamed(themeName),
    palette: mergeSection({...theme.palette}, section('palette')),
    // Every section merged here MUST also be declared in StyleBibleSchema, or zod
    // strips the graph's value before it arrives and `section()` returns the theme
    // default while still reporting success. `radius` / `shadow` / `depthCue` sat in
    // exactly that state from P4 until P12. tests/test_style_bible_merges_only_declared.py
    // is the guard; do not add a section here without adding it to the schema.
    shadow: mergeSection({...theme.shadow}, section('shadow')),
    depthCue: mergeList(theme.depthCue, section('depthCue')),
    ...(resolveInvariant(b) as unknown as Omit<StyleBible, 'theme' | 'palette' | 'shadow' | 'depthCue'>),
  };
};

/**
 * Combine the film-level bible with a scene's, so a document-wide palette
 * still applies to every scene and a scene may nudge one token on top.
 *
 * Merged per SECTION, shallowly, before resolution — not by resolving twice and
 * combining, because resolution is where the theme is applied and doing it
 * twice would let the scene's raw value land on the wrong theme's defaults.
 */
export const combineBibles = (film?: unknown, scene?: unknown): Record<string, unknown> => {
  const f = (film ?? {}) as Record<string, unknown>;
  const s = (scene ?? {}) as Record<string, unknown>;
  const out: Record<string, unknown> = {...f};
  for (const key of Object.keys(s)) {
    const fv = f[key];
    const sv = s[key];
    out[key] =
      fv && sv && typeof fv === 'object' && typeof sv === 'object' && !Array.isArray(fv)
        ? {...(fv as Record<string, unknown>), ...(sv as Record<string, unknown>)}
        : sv;
  }
  return out;
};

const StyleBibleContext = createContext<StyleBible>(resolveStyleBible());

export const StyleBibleProvider: React.FC<{
  /** the film-level style bible */
  bible?: unknown;
  /** this scene's overrides, layered over `bible` */
  override?: unknown;
  theme?: unknown;
  children: React.ReactNode;
}> = ({bible, override, theme, children}) => {
  const resolved = useMemo(
    () => resolveStyleBible(combineBibles(bible, override), theme),
    [bible, override, theme]
  );
  return <StyleBibleContext.Provider value={resolved}>{children}</StyleBibleContext.Provider>;
};

/** Every scene reads design through this. There is deliberately no other path. */
export const useStyle = (): StyleBible => useContext(StyleBibleContext);

/**
 * The one scale for the render frame.
 *
 * Reads BOTH axes, via `scaleFor`. This hook used to read the height alone, and
 * it was the second place (after the scenes) where a portrait frame got a scale
 * that filled its height and overran its width.
 */
export const useScale = (): number => {
  const {width, height} = useVideoConfig();
  return scaleFor(width, height);
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
    DEPTH_CUE: s.depthCue,
    camera: s.camera,
    FONT_NUM,
    FONT_SANS,
    scaleFor,
  };
};
