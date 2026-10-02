import React, {useMemo} from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {ShowcaseSchema, resolveScenes, describeIssues, type Scene, type Showcase} from '../../schemas/showcase-v1';
import {resolveShowcaseMeta} from '../../schemas/showcaseMeta';
import {KpiHero} from './scenes/KpiHero';
import {BrowserStack} from './scenes/BrowserStack';
import {CalendarGrid, DataColumns} from './scenes/DataColumns';
import {ChartScene} from './charts/Chart';
import {PALETTE} from './design/tokens';
import {StyleBibleProvider, useDesign} from './design/styleBible';
import {SceneEnter} from './common/primitives';
import {EnsureFonts} from '../common/EnsureFonts';

/**
 * FinanceShowcaseWide — premium product-film template (P4).
 *
 * Renders a showcase-v1 scene graph. Distinct from ReportVertical by design:
 * that one is energetic (short-form data hooks, shake/flash/RGB split); this
 * one is premium — fewer effects, longer eases, spatial movement, restrained
 * typography. They share no motion vocabulary on purpose.
 *
 * P8 requirement honoured here: width/height/fps come from the graph through
 * calculateMetadata, never from the Composition registration.
 *
 *
 * ── Why this film has NO background music layer (P11 defect 1) ──────────────
 *
 * This component used to read a top-level `doc.audio` and render
 * `<Audio src={staticFile(audio.src)} volume={audio.volume ?? 0.9} />`. That
 * branch was DEAD, and it was dead in the expensive way: `ShowcaseSchema` never
 * declared `audio` and has no `.passthrough()`, so zod stripped the key on every
 * parse. Measured, not inferred — a graph carrying
 * `"audio": {"src": "audio/bgm_main.m4a", "volume": 0.4}` gave
 * `safeParse success: true`, keys `version,project,format,bpm,scenes`, and
 * `audio survived?: false`. An author could write a film with a music bed,
 * watch it validate clean, and get silence out. No error, anywhere.
 *
 * The repair was chosen to DELETE, not to wire, and the reason is not that
 * wiring is hard — it is that wiring would be wrong. Four measured facts:
 *
 *   1. NO PRODUCER. Of the 17 tracked .json files, exactly one has a top-level
 *      `audio`, and it is `piyao_2026/09_final/delivery_manifest.json`, where
 *      `audio` is the free-text string `"AAC 48kHz stereo, loudnorm -14 LUFS"`.
 *      Not a graph, not a `src`. Neither delivered showcase graph sets it.
 *   2. THE PYTHON MIRROR FORBIDS IT. `pipeline/schemas/showcase-v1.schema.json`
 *      carries `additionalProperties: false` and lists
 *      `bpm/format/project/scenes/style_bible/version` — no `audio`. Declaring
 *      it in zod alone would make the two sides disagree, which is the one thing
 *      `tests/test_showcase_schema_parity.py` exists to prevent. The Python
 *      mirror is the authoring side; zod is the rendering side.
 *   3. IT WOULD CONTRADICT A GUARDED DESIGN DECISION. `beat/sfxProfile.check.ts`
 *      asserts "no mapped sound is a bgm — a table of event sounds must not map
 *      to a background track", and `beat/beatGrid.ts` derives the beat grid
 *      *from* `public/audio/bgm_beats.json`. For THIS template the track is a
 *      TIMING REFERENCE. Its sound design is per-event SFX. Wiring `audio`
 *      reachable would put a music bed under every film that set the field,
 *      contradicting a decision the project has already made and tested.
 *   4. THE DEFAULT WAS WRONG ANYWAY. `volume ?? 0.9` is a near-full-scale bed.
 *      A field whose out-of-the-box value is an unasked-for 0.9 mix is not a
 *      capability anyone designed; it is a number that happened to be typed.
 *
 * Deleting also removes a hazard that wiring would have kept: `staticFile()` on
 * a graph-supplied path means the graph chooses what gets decoded. The SFX table
 * resolves names against the audio directory in `sfxProfile.check.ts` — a typo
 * fails there, at a check, instead of becoming a 404 inside `<Audio>` at render
 * time, which is silence rather than an error.
 *
 * If a music bed is genuinely wanted here, that is a DESIGN change and it is not
 * a one-line repair: decide the mix alongside `EVENT_SFX`, declare `audio` on
 * BOTH schema sides so the parity test stays meaningful, and give it a sane
 * default. `tests/test_undeclared_field_reads.py` is written to go red the day
 * this comes back — so a reintroduction cannot be quiet.
 */

const SCENE_RENDERERS: Record<string, React.FC<{scene: Scene}>> = {
  'kpi-hero': KpiHero,
  'browser-stack': BrowserStack,
  dashboard: DataColumns,
  calendar: CalendarGrid,
  // P7.1. These seven were declared in showcase-v1 from P3 and had NO renderer,
  // so a graph asking for a bar chart got a frame that said "not implemented in
  // P4" — the schema promising a capability nothing delivered. They all route
  // to the chart engine, which dispatches on the graph's own chart.type.
  'bar-chart': ChartScene,
  'line-chart': ChartScene,
  'area-chart': ChartScene,
  'bubble-chart': ChartScene,
  'rank-chart': ChartScene,
  'slope-chart': ChartScene,
  heatmap: ChartScene,
  'volume-chart': ChartScene,
  'sparkline-chart': ChartScene,
};

const MissingScene: React.FC<{scene: Scene}> = ({scene}) => (
  <div
    style={{
      position: 'absolute',
      inset: 0,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: PALETTE.inkMuted,
      fontFamily: 'sans-serif',
    }}
  >
    <div style={{textAlign: 'center'}}>
      <div style={{fontSize: 48, color: PALETTE.ink}}>{scene.type}</div>
      <div style={{fontSize: 22, marginTop: 8}}>not implemented in P4</div>
    </div>
  </div>
);

const SceneRenderer: React.FC<{scene: Scene}> = ({scene}) => {
  const C = SCENE_RENDERERS[scene.type];
  return C ? <C scene={scene} /> : <MissingScene scene={scene} />;
};

/** Scene-local background so cuts feel deliberate rather than abrupt. */
const Backdrop: React.FC<{theme?: string}> = ({theme}) => {
  const {PALETTE} = useDesign();
  // No branch on the theme name: the resolved palette already carries this
  // scene's backgroundAlt and background, so the same expression is correct on
  // both surfaces. Branching here is how the two languages drift apart.
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(120% 90% at 20% 0%, ${PALETTE.backgroundAlt} 0%, ${PALETTE.background} 100%)`,
      }}
    />
  );
};

export const FinanceShowcaseWide: React.FC<Record<string, unknown>> = (rawProps) => {
  // `.parse`, not `safeParse`: this component cannot render a graph it does not
  // understand, so the failure has to be loud. What was wrong before was not the
  // throw — it was that the throw reached Remotion as a bare `ZodError` with no
  // message, no path and no offending value, so the only thing an operator saw
  // was a stack trace through the component. The issues are named here.
  const parsed = ShowcaseSchema.safeParse(rawProps);
  if (!parsed.success) {
    throw new Error(`showcase-v1: the graph does not match the schema.\n${describeIssues(parsed.error)}`);
  }
  const doc = parsed.data as Showcase;

  const resolved = useMemo(() => resolveScenes(doc, false), [doc]);

  return (
    <EnsureFonts>
      {/* The ground behind the sequences. Every scene paints a full-frame
          Backdrop inside its own provider, so this is only ever seen in the
          gap between two sequences — the default theme is the right guess and
          nothing depends on it being themed. */}
      <AbsoluteFill style={{background: PALETTE.background}}>
        {resolved.map((r) => {
          const scene = doc.scenes.find((x) => x.id === r.id);
          if (!scene) return null;
          return (
            <Sequence
              key={r.id}
              from={r.startFrame}
              durationInFrames={r.durationInFrames}
              name={`${r.id}:${r.type}`}
            >
              {/* The provider is PER SCENE, not per film. It used to wrap the
                  whole composition, which meant `theme` could only ever change
                  the Backdrop while every scene kept reading premium-dark
                  tokens — a light scene came out as black windows on paper.
                  Resolution has to happen where the theme is declared. */}
              <StyleBibleProvider bible={doc.style_bible} override={scene.style_bible} theme={scene.theme}>
                <SceneEnter
                  kind={scene.transitionIn?.in}
                  durationInFrames={scene.transitionIn?.durationInFrames ?? 18}
                >
                  <Backdrop theme={scene.theme} />
                  <SceneRenderer scene={scene} />
                </SceneEnter>
              </StyleBibleProvider>
            </Sequence>
          );
        })}
      </AbsoluteFill>
    </EnsureFonts>
  );
};

/**
 * P8: the graph owns the format.
 *
 * Two things worth recording here:
 *  - Remotion passes calculateMetadata an ARGUMENT OBJECT
 *    ({props, defaultProps, abortSignal, compositionId, isRendering}), not the
 *    props themselves. Destructuring `props` out of it is mandatory; passing
 *    the object straight into a schema silently fails every time.
 *  - It also runs once with defaultProps before real props arrive, so this must
 *    not throw on an empty document. That constraint is real, and it is also
 *    exactly what the previous version used to excuse the fallback below.
 *
 * The fallback returned `{width: 1920, height: 1080, fps: 60, durationInFrames: 1}`
 * for ANY unparseable graph, which turned every possible authoring mistake into
 * one indistinguishable answer. Measured, with four different defects —
 * `format.width` as a string, a scene id that fails the id regex, a scene type
 * outside the enum, `fps` over the schema cap — all four produced exactly
 * `1920x1080@60 1 frames` and no mention of the cause.
 *
 * That is worse than an error, because the error it replaced was addressed to the
 * wrong thing. The caller saw `RangeError: Cannot use frame 515: Duration of
 * composition is 1` — a complaint about the FRAME NUMBER, on a graph whose
 * actual fault was a string where a number belonged. Two steps in, asking for a
 * legal frame, the render failed again with a bare `ZodError` carrying a stack
 * and no message.
 *
 * So: no props yet is a legitimate question with a default answer, and props
 * that are present and wrong are a defect that must be named. `resolveShowcaseMeta`
 * is the decision, kept out of this file so a check can reach it without
 * react or remotion in the way.
 */
type MetaArgs = {props?: unknown; defaultProps?: unknown};

export const showcaseMeta = (args: MetaArgs) =>
  resolveShowcaseMeta(args && typeof args === 'object' && 'props' in args ? args.props : args);

/** A valid starter graph so the Studio opens on something renderable. */
export const SHOWCASE_DEFAULTS = {
  version: 1 as const,
  project: 'showcase',
  format: {width: 1920, height: 1080, fps: 60},
  bpm: 126,
  scenes: [
    {
      id: 's01',
      type: 'kpi-hero' as const,
      durationInFrames: 240,
      layout: {eyebrow: 'TOTAL VOLUME'},
      content: {value: 7263, prefix: '$', suffix: 'M', delta: '+18.4%'},
    },
  ],
};