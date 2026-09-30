// showcase-v1 — Scene graph for product-film / data-showcase video (P3).
//
// MIRROR of pipeline/schemas/showcase-v1.schema.json. The two must stay in
// sync — tests/test_showcase_schema_parity.py checks the scene-type list and
// the camera/motion keys. Python authors the graph; TypeScript renders it.
//
// Design rules encoded here:
//  * the unit is a SCENE, not a shot (a scene may be pure motion graphics)
//  * camera motion is separate from component motion
//  * format is metadata-driven (P8): nothing hardcodes 1080p/24fps

import {z} from 'zod';

export const SceneType = z.enum([
  'video',
  'kpi-hero',
  'browser-window',
  'browser-stack',
  'dashboard',
  'stat-card',
  'card-grid',
  'calendar',
  'bar-chart',
  'line-chart',
  'area-chart',
  'bubble-chart',
  'rank-chart',
  'slope-chart',
  'heatmap',

  'volume-chart',
  'sparkline-chart',
  'data-table',
  'quote',
  'data-plane-3d',
  'logo',
  'outro',
]);

/** Scenes that need H3 rather than the Remotion motion engine. */
export const GENERATIVE_SCENE_TYPES = new Set<z.infer<typeof SceneType>>([
  'video',
  'data-plane-3d',
]);

/** A camera channel: constant, or [from, to] interpolated over the scene. */
const Track = z.union([z.number(), z.tuple([z.number(), z.number()])]);

export const CameraSchema = z.object({
  perspective: z.number().positive().max(20000).optional(),
  translateX: Track.optional(),
  translateY: Track.optional(),
  translateZ: Track.optional(),
  rotateX: Track.optional(),
  rotateY: Track.optional(),
  rotateZ: Track.optional(),
  scale: Track.optional(),
  focus: Track.optional(),
});

export const MotionSchema = z.object({
  preset: z.enum(['premium', 'energetic', 'cinematic', 'minimal']).optional(),
  stagger: z.number().min(0).max(2).optional(),
  ease: z.string().optional(),
});

export const TransitionSchema = z.object({
  in: z.string().optional(),
  out: z.string().optional(),
  durationInFrames: z.number().int().nonnegative().optional(),
});

export const StyleBibleSchema = z.object({
  palette: z.record(z.string(), z.unknown()).optional(),
  typography: z.record(z.string(), z.unknown()).optional(),
  spacing: z.record(z.string(), z.unknown()).optional(),
  cameraLanguage: z.record(z.string(), z.unknown()).optional(),
  motionLanguage: z.record(z.string(), z.unknown()).optional(),
  chartLanguage: z.record(z.string(), z.unknown()).optional(),
  audioLanguage: z.record(z.string(), z.unknown()).optional(),
});

export const SceneSchema = z.object({
  id: z.string().regex(/^[a-z0-9_]+$/),
  type: SceneType,
  durationInFrames: z.number().int().positive(),
  theme: z.string().optional(),
  /**
   * Per-scene overrides, merged over the document's style_bible AFTER the
   * scene's theme is applied. This is the escape hatch for "one scene nudges one
   * colour" without restating a palette — and it is why the provider moved
   * inside the scene loop: resolution has to happen where the theme is declared.
   */
  style_bible: StyleBibleSchema.optional(),
  layout: z.record(z.string(), z.unknown()).optional(),
  camera: CameraSchema.optional(),
  motion: MotionSchema.optional(),
  content: z.record(z.string(), z.unknown()).optional(),
  transitionIn: TransitionSchema.optional(),
  transitionOut: TransitionSchema.optional(),
  audioEvents: z.array(z.record(z.string(), z.unknown())).optional(),
  notes: z.string().optional(),
});

export const ShowcaseSchema = z.object({
  version: z.literal(1),
  project: z.string().min(1),
  style_bible: StyleBibleSchema.optional(),
  format: z.object({
    width: z.number().int().positive(),
    height: z.number().int().positive(),
    fps: z.number().int().min(1).max(120),
  }),
  bpm: z.number().min(40).max(240).default(126),
  scenes: z.array(SceneSchema).min(1),
});

export type SceneType = z.infer<typeof SceneType>;
export type Camera = z.infer<typeof CameraSchema>;
export type Motion = z.infer<typeof MotionSchema>;
export type Scene = z.infer<typeof SceneSchema>;
export type Showcase = z.infer<typeof ShowcaseSchema>;

/** Assigned start frames for every scene. */
export type ResolvedScene = {
  id: string;
  type: SceneType;
  startFrame: number;
  durationInFrames: number;
  generative: boolean;
};

export const beatFrames = (doc: Showcase): number => (60 / doc.bpm) * doc.format.fps;

/**
 * Distance from a frame to the nearest beat boundary, in frames.
 * At 60 fps a 126 BPM beat is 28.5714 frames — no integer frame lands exactly on
 * a beat — so callers should treat <= 0.5 frames as "on the beat" once
 * beatSnap is used. Half a BEAT only applies without snapping.
 */
export const beatDistanceFrames = (doc: Showcase, frame: number): number => {
  const b = beatFrames(doc);
  const off = frame % b;
  return Math.min(off, b - off);
};

export const onBeat = (doc: Showcase, frame: number): boolean =>
  beatDistanceFrames(doc, frame) <= 0.5 + 1e-6;

/**
 * With beatSnap, timing lives in BEAT space and is converted to frames exactly
 * once per boundary. Both boundaries of a scene come from the same rounding of
 * the same grid, so `start[i+1] === end[i]` by construction — neither an
 * overlap nor a gap can be expressed — and drift stays under half a frame
 * without accumulating.
 *
 * Choosing start-rounding and duration-rounding independently does not work:
 * round(a) + round(b) !== round(a + b), so every pairing leaves a one-frame
 * defect on one side. Deriving each end from the next start is what makes the
 * error unrepresentable.
 *
 * `durationInFrames` in the input is a REQUEST; the resolved duration is
 * authoritative and may differ by up to half a beat.
 */
export const resolveScenes = (doc: Showcase, beatSnap = false): ResolvedScene[] => {
  const b = beatFrames(doc);
  const out: ResolvedScene[] = [];
  let beatCursor = 0;
  let frameCursor = 0;
  for (const s of doc.scenes) {
    let start: number;
    let end: number;
    if (beatSnap) {
      const beats = Math.max(1, Math.round(s.durationInFrames / b));
      start = Math.round(beatCursor * b);
      end = Math.round((beatCursor + beats) * b);
      beatCursor += beats;
    } else {
      start = frameCursor;
      end = frameCursor + s.durationInFrames;
    }
    out.push({
      id: s.id,
      type: s.type,
      startFrame: start,
      durationInFrames: end - start,
      generative: GENERATIVE_SCENE_TYPES.has(s.type),
    });
    frameCursor = end;
  }
  return out;
};

export const totalFrames = (doc: Showcase): number =>
  doc.scenes.reduce((sum, s) => sum + s.durationInFrames, 0);
