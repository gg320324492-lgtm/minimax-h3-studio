import React, {useMemo} from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {ShowcaseSchema, resolveScenes, type Scene, type Showcase} from '../../schemas/showcase-v1';
import {KpiHero} from './scenes/KpiHero';
import {BrowserStack} from './scenes/BrowserStack';
import {CalendarGrid, DataColumns} from './scenes/DataColumns';
import {PALETTE, scaleFrom} from './design/tokens';
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
  const light = theme === 'premium-light';
  return (
    <AbsoluteFill
      style={{
        background: light
          ? `radial-gradient(120% 90% at 20% 0%, ${PALETTE.lightBackground} 0%, ${PALETTE.lightSurface} 100%)`
          : `radial-gradient(120% 90% at 20% 0%, ${PALETTE.backgroundAlt} 0%, ${PALETTE.background} 100%)`,
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
              <Backdrop theme={scene.theme} />
              <SceneRenderer scene={scene} />
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