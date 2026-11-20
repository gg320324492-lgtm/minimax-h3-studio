import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Scene} from '../../../schemas/showcase-v1';
import {CameraRig, useCameraState} from '../common/CameraRig';
import {cssXForScreenX, screenScaleFor} from '../common/projection';
// Fonts and scaling are NOT theme-scoped, so importing them is correct.
// Everything that IS theme-scoped (palette, type, spacing, shadow) must come
// from useDesign() — see tests/test_showcase_schema_parity.py::test_scenes_do_not_import_design_values_directly
import {FONT_NUM, FONT_SANS, TRAFFIC_LIGHTS, scaleFor} from '../design/tokens';
import {useDesign} from '../design/styleBible';
import {Stagger} from '../common/primitives';

/**
 * Scene 2 — Browser Stack (reference film ~26-30s)
 * Several dashboard windows at different depths, the camera flying through them.
 *
 * The depth is CSS 3D: each window sits on its own translateZ plane, the rig
 * supplies perspective and the camera move. Windows enter staggered with a
 * long ease so the stack assembles rather than pops — the reference film never
 * snaps anything into place.
 */

/**
 * The depth cue for window `i`, and what happens past the end of the ramp.
 *
 * This replaces `DEPTH_CUE[Math.min(i, DEPTH_CUE.length - 1)]`, which was the
 * clamp that made every window from the fourth onward share the third window's
 * shadow. Measured, not inferred: rendering this scene with six windows and
 * reading back what React actually emitted gave
 *
 *     w0 0 14px  40px   w1 0 30px  84px   w2 0 46px 132px
 *     w3 0 46px 132px   w4 0 46px 132px   w5 0 46px 132px
 *
 * Exported because the behaviour past the last layer is a DESIGN decision and
 * not an indexing detail, and a decision deserves to be named and checked
 * rather than written as a `Math.min` nobody reads:
 *
 *  - clamp at the LAST layer (what this does). The ramp runs five deep (see
 *    themes.ts for how those five were derived), so a six-window stack repeats
 *    the deepest cue. That under-claims depth rather than lying about it.
 *  - WRAP (`i % length`). Rejected, and the reason is specific: it makes
 *    window 5 render as window 0 - the FAR plane - behind a window carrying
 *    the deepest shadow. The stack would read as nearer-behind-further, which
 *    is a depth lie the viewer can see, and it would cost nothing to ship.
 *  - EXTRAPOLATE the ramp's own progression past layer five. Also rejected,
 *    and this one is arithmetic: the dark ramp's alpha multiplies by 1.240 per
 *    layer and reaches 0.95 at five, so layer six would need alpha 1.18. Not a
 *    colour. The ramp saturates on near-black before its geometry does.
 *
 * `undefined` for an empty ramp rather than a throw, so a graph that overrides
 * `depthCue` with an empty list falls through to the scene's own `SHADOW.floating`
 * at the call site.
 */
export const depthCueAt = (cue: readonly string[], i: number): string | undefined => {
  if (cue.length === 0) return undefined;
  return cue[i < cue.length ? i : cue.length - 1];
};

type Win = {
  title: string;
  metric: string;
  bars?: number[];
  spark?: number[];
  flat?: boolean;
};

const MiniBars: React.FC<{values: number[]; s: number; progress: number}> = ({
  values,
  s,
  progress,
}) => {
  const {MOTION, PALETTE, RADIUS, SHADOW} = useDesign();
  const max = Math.max(...values, 1);
  return (
    <div style={{display: 'flex', alignItems: 'flex-end', gap: 6 * s, height: 72 * s}}>
      {values.map((v, i) => {
        const local = interpolate(progress, [i * 0.12, i * 0.12 + 0.5], [0, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
        return (
          <div
            key={i}
            style={{
              width: 16 * s,
              height: `${(v / max) * 100 * local}%`,
              background: i === values.length - 1 ? PALETTE.accent : PALETTE.columnBright,
              borderRadius: 3 * s,
            }}
          />
        );
      })}
    </div>
  );
};

const Spark: React.FC<{values: number[]; s: number; progress: number}> = ({
  values,
  s,
  progress,
}) => {
  const {MOTION, PALETTE, RADIUS, SHADOW} = useDesign();
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * 100;
    const y = 100 - ((v - min) / Math.max(max - min, 1e-6)) * 100;
    return `${x},${y}`;
  });
  const d = `M ${pts.join(' L ')}`;
  const len = 400;
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{width: '100%', height: 72 * s}}>
      <path
        d={d}
        fill="none"
        stroke={PALETTE.accent}
        strokeWidth={2.4}
        vectorEffect="non-scaling-stroke"
        strokeDasharray={len}
        strokeDashoffset={len * (1 - progress)}
        strokeLinecap="round"
      />
    </svg>
  );
};

const BrowserWindow: React.FC<{
  win: Win;
  s: number;
  progress: number;
  width: number;
  height: number;
  rotateY: number;
  /** depth-cued shadow; see SHADOW.byDepth */
  shadow: string;
}> = ({win, s, progress, width, height, rotateY, shadow}) => {
  const {PALETTE, RADIUS} = useDesign();
  return (
  <div
    style={{
      // MUST stay in flow. The wrapper is what `translate(-50%, -50%)` measures,
      // so if the window inside it is absolutely positioned the wrapper collapses
      // to 0x0, the percentage resolves to zero, and every window hangs from the
      // frame centre by its TOP-LEFT corner instead of its middle. That bug put
      // the whole cluster in the bottom-right quadrant and is invisible to a
      // source read — the transform looks right, it just does nothing. The
      // wrapper therefore carries the window's size explicitly.
      position: 'relative',
      width,
      height,
      // depth belongs to the wrapper that positions the window — it owns both
      // the plane and the solved x, and a second translateZ here would move
      // the window off the axis the centring maths just placed it on
      transform: `rotateY(${rotateY}deg)`,
      transformStyle: 'preserve-3d',
      background: PALETTE.surface,
      border: `1px solid ${PALETTE.hairline}`,
      borderRadius: RADIUS.window * s,
      boxShadow: shadow,
      overflow: 'hidden',
      opacity: progress,
      display: 'flex',
      flexDirection: 'column',
    }}
  >
    <div
      style={{
        height: 38 * s,
        display: 'flex',
        alignItems: 'center',
        gap: 7 * s,
        padding: `0 ${14 * s}px`,
        borderBottom: `1px solid ${PALETTE.hairline}`,
        background: PALETTE.surfaceElevated,
      }}
    >
      {TRAFFIC_LIGHTS.map((c) => (
        <div key={c} style={{width: 9 * s, height: 9 * s, borderRadius: '50%', background: c, opacity: 0.65}} />
      ))}
      <div
        style={{
          marginLeft: 12 * s,
          fontFamily: FONT_SANS,
          fontSize: 17 * s,
          color: PALETTE.inkMuted,
          letterSpacing: '0.02em',
        }}
      >
        {win.title}
      </div>
    </div>
    <div style={{padding: `${20 * s}px ${22 * s}px`, flex: 1, display: 'flex', flexDirection: 'column'}}>
      <div
        style={{
          fontFamily: FONT_NUM,
          fontVariantNumeric: 'tabular-nums',
          fontSize: 52 * s,
          fontWeight: 700,
          letterSpacing: '-0.02em',
          color: PALETTE.ink,
        }}
      >
        {win.metric}
      </div>
      <div style={{flex: 1, display: 'flex', alignItems: 'flex-end', marginTop: 12 * s}}>
        {win.bars ? <MiniBars values={win.bars} s={s} progress={progress} /> : null}
        {win.spark ? <Spark values={win.spark} s={s} progress={progress} /> : null}
        {win.flat ? (
          <div style={{width: '100%', height: 3 * s, background: PALETTE.hairline, borderRadius: 2}} />
        ) : null}
      </div>
    </div>
  </div>
  );
};

export const BrowserStack: React.FC<{scene: Scene}> = ({scene}) => {
  const {MOTION, PALETTE, RADIUS, SHADOW, DEPTH_CUE} = useDesign();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = scaleFor(comp.width, comp.height);
  const layout = (scene.layout ?? {}) as Record<string, unknown>;
  const motion = scene.motion;
  const stagger = Number(motion?.stagger ?? MOTION.staggerDefault);

  const windows = ((scene.content ?? {}).windows ?? []) as Win[];

  // composition lives in the graph (P6): every value has a default so an
  // older graph still renders, but a new graph can retune it without TS edits
  const spreadX = Number(layout.spreadX ?? 250) * s;
  const spreadZ = Number(layout.spreadZ ?? 110) * s;
  const perWindowRot = Number(layout.perWindowRotateY ?? 7);
  const winW = Number(layout.windowWidth ?? layout.width ?? 520) * s;
  const winH = Number(layout.windowHeight ?? layout.height ?? 400) * s;
  /**
   * Two coherent ways to draw a stack in perspective, and they are NOT both
   * available at once — so the graph picks, rather than the component guessing:
   *
   *  equalOnScreen: true (default) — every window is counter-scaled to the size
   *    the graph asked for ON SCREEN. The silhouette is exactly symmetric, so
   *    the cluster is centred to the pixel at any spreadZ or rotation. The cost
   *    is real: a near window is no longer drawn bigger than a far one, so the
   *    depth has to come from the fan, the shadows and the camera move.
   *
   *  equalOnScreen: false — no counter-scale, so a near window IS drawn larger.
   *    That reads as depth immediately, but perspective then makes the cluster
   *    genuinely asymmetric: measured +16.8px on a 1920 frame with the demo
   *    graph's 1400px perspective, about 0.9% of frame width.
   *
   * Both are correct renderings of a decision. Neither is a bug; the important
   * thing is that the choice is visible in the graph rather than emergent.
   */
  const equalOnScreen = layout.equalOnScreen !== false;

  // the camera's own z, read from the SAME evaluation the rig renders with, so
  // the layout below cannot disagree with the camera actually on screen
  const cam = useCameraState(scene.camera, motion, scene.durationInFrames);
  const c = (windows.length - 1) / 2;

  return (
    <CameraRig camera={scene.camera} motion={motion} durationInFrames={scene.durationInFrames}>
      <div style={{position: 'absolute', inset: 0, transformStyle: 'preserve-3d'}}>
        {windows.map((w, i) => {
          const at = i * stagger * comp.fps;
          const enter = spring({
            frame: frame - at,
            fps: comp.fps,
            config: MOTION.springs.settle,
            durationInFrames: Math.round(MOTION.enterSeconds * comp.fps),
          });
          // depth plane + a slight counter-rotation so the stack reads as
          // three dimensional rather than as a flat row
          const planeZ = (i - c) * spreadZ;
          const rot = (1 - i) * perWindowRot;
          // THE CENTRING FIX (P6.2). The stack is authored in SCREEN space —
          // even spacing about the frame's centre line, one chosen size on
          // screen — and this solves for the CSS that survives the projection.
          //
          // Authoring CSS x directly, which is what this did before, put the
          // near window closer to the eye, so perspective magnified it more
          // than it shrank the far one. The cluster's optical centre drifted
          // right of the frame centre, and the drift grew as the camera's own
          // translateZ changed every window's depth. Solving per frame against
          // absolute depth puts the stack on the axis at EVERY frame, and the
          // counter-scale makes the silhouette symmetric too — so "centred" is
          // now a property of the layout, not a value someone tuned until the
          // numbers looked right in one render.
          const cssX = cssXForScreenX((i - c) * spreadX, planeZ + cam.translateZ, cam.perspective);
          const k = equalOnScreen ? screenScaleFor(planeZ, cam.perspective) : 1;
          // depth read now that the windows are equal size at rest: a nearer
          // window carries a deeper shadow and a stronger turn
          const depth = depthCueAt(DEPTH_CUE, i) ?? SHADOW.floating;
          return (
            <div
              key={w.title}
              style={{
                position: 'absolute',
                left: '50%',
                top: '50%',
                // the wrapper must carry the window's size, or the -50% below
                // is a no-op (see BrowserWindow's comment)
                width: winW,
                height: winH,
                // centring: left/top put the box's top-LEFT on the frame centre,
                // -50%,-50% moves that to its middle. The scale is applied to
                // the element's own points first (a CSS transform list applies
                // right to left), so it magnifies the window about the very
                // centre this establishes.
                transform:
                  `translate(-50%, -50%) translateZ(${planeZ}px) ` +
                  `translateX(${cssX}px) scale(${k})`,
                transformStyle: 'preserve-3d',
              }}
            >
              <BrowserWindow
                win={w}
                s={s}
                progress={enter}
                width={winW}
                height={winH}
                rotateY={rot}
                shadow={depth}
              />
            </div>
          );
        })}
      </div>
    </CameraRig>
  );
};