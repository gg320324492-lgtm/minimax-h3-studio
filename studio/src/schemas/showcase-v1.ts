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
//
// UNKNOWN KEYS ARE REJECTED, NOT SWALLOWED (P11, defect 3 — measured).
//
// Read this before adding `.passthrough()` anywhere below, because the two
// mirrors used to return opposite verdicts on the same bytes:
//
//   * these `z.object(...)` calls had no `.strict()`, so zod silently STRIPPED
//     any key it did not declare, and `safeParse` still returned `success: true`;
//   * the document root and the `Scene` / `Camera` / `Motion` / `Transition`
//     definitions all carried `additionalProperties: false` in the JSON Schema
//     mirror, so the same graph was REJECTED there.
//
// Measured on the two delivered graphs, full strictness, at every depth: the only
// key either mirror would reject is `showcase_demo.json`'s top-level `_note`.
// `charts_demo.json` has none. So the disagreement was not theoretical — the
// shipped showcase demo passed zod and failed the JSON Schema, and no test ran
// the JSON Schema at all, because it could not even be compiled (see
// `definitions/Track` in the mirror).
//
// That is the defect class the last three commits removed (`motion.ease`,
// top-level `audio`, `chart.baseline`): a field the graph can set, that nothing
// reads, that reports success anyway. Stripping is the worst variant, because it
// is invisible in both directions — the author sees a clean parse, and the field
// vanishes before any renderer could honour it.
//
// THE TRADE-OFF ACCEPTED: full strictness makes an unknown key a HARD ERROR. That
// is a real cost — a graph authored against a slightly different draft now fails
// to load instead of loading with a field quietly ignored — and it is paid
// deliberately, because the alternative is a failure that is invisible and
// therefore unfixable from the outside. It is not a bare `ZodError`:
// `describeIssues` names the path (`scenes[0].motion: Unrecognized key: "ease"`),
// and both `FinanceShowcaseWide.tsx` and `showcaseMeta.ts` report issues that way.
//
// `Track` carries NO modifier, and that is a measured equivalence rather than an
// oversight. It is a shared leaf VALUE type, not a bag of author-supplied data,
// and zod 4 gives a `z.tuple()` no `.strict()` at all: `z.tuple([a, b])` already
// rejects `[a, b, c]`, `[[a], b]` and `{a: 1}`. Measured on zod 4.5.4 — `Track` is
// therefore exactly as strict as a strict version of it would have been. An
// earlier draft of this comment claimed a `.passthrough()` exception was needed
// here; it was not, and the parity guard asserts the equivalence instead of
// documenting a divergence that does not exist.
//
// The object-valued bags (`layout`, `content`, `audioEvents`, every
// `StyleBible` section) are `z.record(...)` and stay open. Strictness applies to
// the graph's OWN vocabulary — where a typo is most likely and most expensive —
// not to the free-form payload the scene components interpret.

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

export const CameraSchema = z
  .object({
    perspective: z.number().positive().max(20000).optional(),
    translateX: Track.optional(),
    translateY: Track.optional(),
    translateZ: Track.optional(),
    rotateX: Track.optional(),
    rotateY: Track.optional(),
    rotateZ: Track.optional(),
    scale: Track.optional(),
    focus: Track.optional(),
  })
  .strict();

/**
 * Per-scene motion overrides. `preset` and `stagger` are READ; `ease` was
 * removed in P11 and is deliberately not coming back (see below).
 *
 * WHY THERE IS NO `ease` (P11, defect 2 — measured, not inferred):
 *
 * The delivered graph set `"ease": "expo-out"` on s01_kpi and s03_columns, and
 * the field was declared here — but nothing in the render path ever read
 * it. Every `motion.*` read in production is exactly three lines, and `ease`
 * is in none of them:
 *
 *   CameraRig.tsx:98     motion?.preset   -> cameraMoveFrames(...)
 *   BrowserStack.tsx:189 motion?.stagger
 *   DataColumns.tsx:176  motion?.stagger
 *
 * So the graph told an author `expo-out` was shaping those two scenes. It was
 * not: the only easing in the render path is the hardcoded bezier at
 * `primitives.tsx:183`, `cubicBezierEase(0.16, 1, 0.3, 1)`.
 *
 * DELIBERATELY CLEANED, NOT WIRED. Wiring was rejected on evidence, not taste:
 *
 *  * That bezier takes FOUR NUMBERS. So does the built-in table
 *    (`MOTION.profiles[x].ease`, a `[n,n,n,n]` tuple). The shipped value is the
 *    NAME `expo-out` — and NO name’curve resolver exists anywhere in
 *    studio/src, studio/scripts or pipeline (the only two `expo-out` hits are a
 *    comment in CameraRig.tsx and a hand-rolled quartic in KpiHero.tsx).
 *    Honouring the field would mean INVENTING that table — deciding alone
 *    that `expo-out` means [0.16, 1, 0.3, 1] — a design decision, not a bug fix.
 *  * The alternative — retype the field as a 4-number bezier — would
 *    REJECT every graph shipped today. Breaking a delivered artefact is worse
 *    than the lie it replaces.
 *  * The "read it, fail to resolve it, fall back to the hardcoded bezier" variant
 *    is the one this project has already paid for: it trades a lie you can read
 *    in the graph for a lie the code performs, and it makes the guard unfalsifiable.
 *
 * Removing the declaration (not just the graph values) is what makes the fix
 *  stick: BOTH mirrors now REJECT a re-added `ease` — the JSON Schema via
 * `additionalProperties: false`, zod via `.strict()`. Before P11 defect 3 the two
 * disagreed here, which is why the runtime test could assert a STRIP as though it
 * were the contract. If the
 * so a re-added `ease` is REJECTED, while here zod would silently STRIP it. If the
 * declaration came back without a reader, the graph would be claiming an effect
 * again while validation reported success — defect one, one level
 * down. `tests/test_motion_ease_is_not_a_claim.py` guards both halves.
 */
export const MotionSchema = z
  .object({
    preset: z.enum(['premium', 'energetic', 'cinematic', 'minimal']).optional(),
    stagger: z.number().min(0).max(2).optional(),
  })
  .strict();

export const TransitionSchema = z
  .object({
    in: z.string().optional(),
    out: z.string().optional(),
    durationInFrames: z.number().int().nonnegative().optional(),
  })
  .strict();

/**
 * STRICT (P12, third deliverable). `.strict()` was added here to close the root
 * of the "silently stripped" family, and the addition was MEASURED first: an
 * undeclared key is now a hard error instead of a value that vanishes, so the
 * question is not "is this safe" but "what does it cost", and the answer is
 * below.
 *
 * THE COST, MEASURED, NOT ASSUMED. Every JSON in the repository was swept for a
 * `style_bible` carrying a key this schema does not declare: 563 files parsed,
 * 3 carried a `style_bible`, and every key in them is declared. So `.strict()`
 * breaks nothing that exists TODAY. That is NOT the same claim as "breaks
 * nothing", and the difference is the entire reason the change is worth making:
 *
 *   * "breaks nothing today"  — a snapshot. True until the first graph ships a
 *                               section nobody declared.
 *   * "cannot break later"     — the actual point. Before this, a typo or a
 *                               not-yet-implemented section was a clean parse
 *                               plus a silently ignored field. The author got a
 *                               success and a render that ignored them, and
 *                               nothing in the toolchain could tell them apart
 *                               from a section that worked.
 *
 * The failure it removes is not hypothetical — it is the one P12 just closed at
 * the instance level. `radius` / `shadow` / `depthCue` were merged by the
 * resolver, read by real scenes, and deleted by zod on the way past: `success:
 * true`, a fully populated `StyleBible` on the renderer side, defaults only on
 * screen. `test_style_bible_merges_only_declared.py` guards "merged but not
 * declared"; it structurally CANNOT catch "declared by an intermediate layer
 * and stripped before the schema sees it", because by then the evidence is
 * gone. Only strictness at the parser catches that.
 *
 * WHAT `.strict()` DOES NOT CLOSE. It governs the TOP-LEVEL keys of the style
 * bible only, and nothing about the bag VALUES:
 *
 *  * `palette.card`, `spacing.gutter` and any other sub-key remain free-form.
 *    Verified by running it: `safeParse({palette: {nope: 1}})` succeeds. This is
 *    load-bearing, not an oversight — `mergeSection` filters incoming values
 *    against the default's own keys and type-checks each one, so an unknown
 *    sub-key inside a section is dropped by the merge with the rest, and the
 *    two cross-mirror tests that pin this openness
 *    (`test_pipeline_validates_the_schema.py`'s "style_bible open bag" and
 *    `test_showcase_mirrors_agree_on_values.py`'s "unknown key in style_bible
 *    section") would go red if it closed.
 *  * `depthCue` stays a `string[]`, not a bag. `mergeList` is all-or-nothing,
 *    because a partial ramp would mis-index: a 3-element ramp asked for depth 4
 *    would render the depth-1 shadow. Typing it as an open record would let that
 *    shape through the schema and reject it at the merge instead.
 *  * `radius` / `shadow` value types stay loose, for the same reason: pinning
 *    `radius` to numbers would reject a value the merge would have dropped
 *    anyway, turning a no-op into a hard error.
 *
 * `depth` remains deliberately ABSENT — zero consumers, and an absent key is now
 * a loud error rather than a silent strip. See
 * docs/STYLE_BIBLE_STRIPPED_SECTIONS.md for the ruling and the measurement.
 */
export const StyleBibleSchema = z
  .object({
    palette: z.record(z.string(), z.unknown()).optional(),
    typography: z.record(z.string(), z.unknown()).optional(),
    spacing: z.record(z.string(), z.unknown()).optional(),
    radius: z.record(z.string(), z.unknown()).optional(),
    /** one CSS shadow per depth step, far plane first; all-or-nothing */
    depthCue: z.array(z.string()).optional(),
    shadow: z.record(z.string(), z.unknown()).optional(),
    cameraLanguage: z.record(z.string(), z.unknown()).optional(),
    motionLanguage: z.record(z.string(), z.unknown()).optional(),
    chartLanguage: z.record(z.string(), z.unknown()).optional(),
    audioLanguage: z.record(z.string(), z.unknown()).optional(),
  })
  .strict();

export const SceneSchema = z
  .object({
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
  })
  .strict();

export const ShowcaseSchema = z
  .object({
    version: z.literal(1),
    project: z.string().min(1),
    /**
     * Provenance comment for humans, accepted and DISCARDED. Declared here and
     * in the JSON Schema mirror rather than smuggled through a hole: the
     * leading-underscore prefix is this project's convention for meta and
     * annotation, so it gets a named, typed home instead of riding on the
     * difference between the two mirrors' unknown-key handling.
     *
     * It exists on exactly ONE graph — `showcase_demo.json`, whose value is a
     * 53-character Chinese sentence about the reference film's 24-40s visual
     * structure. Removing it instead of declaring it was the other option and
     * was rejected: it is real authorship information, and two of the three
     * graph writers in `pipeline/` (`prompt_compiler.py`,
     * `migrate_shotspecs.py`) already emit `_note` under the same convention.
     * Dropping one producer's note to satisfy a validator would have been the
     * schema dictating to the authors what they are allowed to write down.
     *
     * Nothing reads it: it is stripped before the renderer sees the document, so
     * declaring it cannot make an unread field look supported — the defect class
     * this whole change is about is a field a graph can set AND that something
     * might honour. A field nothing can read is a comment, and comments are
     * allowed.
     */
    _note: z.string().optional(),
    style_bible: StyleBibleSchema.optional(),
    format: z
      .object({
        width: z.number().int().positive(),
        height: z.number().int().positive(),
        fps: z.number().int().min(1).max(120),
      })
      .strict(),
    bpm: z.number().min(40).max(240).default(126),
    scenes: z.array(SceneSchema).min(1),
  })
  .strict();

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

/**
 * Render a schema failure as something an author can act on.
 *
 * A raw `ZodError` is the worst possible report for a graph-authoring mistake:
 * its `.message` is a JSON blob and Remotion prints only the stack, so what
 * reached the operator was `ZodError` and a call trace through the component.
 * Each issue becomes `path: message` — `format.width: Invalid input: expected
 * number, received string` — which names the field and what it got.
 */
export const describeIssues = (error: {
  issues: ReadonlyArray<{path: ReadonlyArray<PropertyKey>; message: string}>;
}): string =>
  error.issues
    .map((i) => {
      const at = i.path.length ? i.path.map(String).join('.') : '(document root)';
      return `  ${at}: ${i.message}`;
    })
    .join('\n');
