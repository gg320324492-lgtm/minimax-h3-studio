import React, {useMemo} from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {ShowcaseSchema, resolveScenes, type Scene, type Showcase} from '../../schemas/showcase-v1';
import {KpiHero} from './scenes/KpiHero';
import {BrowserStack} from './scenes/BrowserStack';
import {CalendarGrid, DataColumns} from './scenes/DataColumns';
import {ChartScene} from './charts/Chart';
import {PALETTE, scaleFrom} from './design/tokens';
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
  const doc = ShowcaseSchema.parse(rawProps) as Showcase;
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = scaleFrom(comp.height);

  const resolved = useMemo(() => resolveScenes(doc, false), [doc]);

  const audio = (doc as unknown as { audio?: { src: string; volume?: number } }).audio;

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
        {audio ? <Audio src={staticFile(audio.src)} volume={audio.volume ?? 0.9} /> : null}
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
 *  - It also runs once with defaultProps before real props arrive, so this
 *    must not throw on an empty or partial document.
 */
type MetaArgs = {props?: unknown; defaultProps?: unknown};

export const showcaseMeta = (args: MetaArgs) => {
  const raw = (args && typeof args === 'object' && 'props' in args ? args.props : args);
  const parsed = ShowcaseSchema.safeParse(raw);
  if (!parsed.success) {
    return {width: 1920, height: 1080, fps: 60, durationInFrames: 1};
  }
  const doc = parsed.data as Showcase;
  const total = doc.scenes.reduce((sum, sc) => sum + sc.durationInFrames, 0);
  return {
    width: doc.format.width,
    height: doc.format.height,
    fps: doc.format.fps,
    durationInFrames: Math.max(1, total),
  };
};

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