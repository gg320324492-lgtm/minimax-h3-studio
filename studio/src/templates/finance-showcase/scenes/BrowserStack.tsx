import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Scene} from '../../../schemas/showcase-v1';
import {CameraRig} from '../common/CameraRig';
import {FONT_NUM, FONT_SANS, scaleFrom} from '../design/tokens';
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
              background: i === values.length - 1 ? PALETTE.accent : 'rgba(245,242,234,0.32)',
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
  z: number;
  width: number;
  height: number;
  rotateY: number;
}> = ({win, s, progress, z, width, height, rotateY}) => {
  const {PALETTE, RADIUS, SHADOW} = useDesign();
  return (
  <div
    style={{
      position: 'absolute',
      width,
      height,
      transform: `translateZ(${z}px) rotateY(${rotateY}deg)`,
      transformStyle: 'preserve-3d',
      background: PALETTE.surface,
      border: `1px solid ${PALETTE.hairline}`,
      borderRadius: RADIUS.window * s,
      boxShadow: SHADOW.floating,
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
      {['#FF5F57', '#FEBC2E', '#28C840'].map((c) => (
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
  const {MOTION, PALETTE, RADIUS, SHADOW} = useDesign();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = scaleFrom(comp.height);
  const layout = (scene.layout ?? {}) as Record<string, unknown>;
  const motion = scene.motion;
  const stagger = Number(motion?.stagger ?? MOTION.staggerDefault);

  const windows = ((scene.content ?? {}).windows ?? []) as Win[];

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
          const z = (i - 1) * 180 * s;
          const rot = (1 - i) * 7;
          const winW = Number(layout.width ?? 560) * s;
          const winH = Number(layout.height ?? 400) * s;
          return (
            <div
              key={w.title}
              style={{
                position: 'absolute',
                left: '50%',
                top: '50%',
                // centre the plane; without this the windows hang off the
                // right edge because left:50% is the window's own origin
                transform: `translate(-50%, -50%) translateZ(${(i - (windows.length - 1) / 2) * 150 * s}px) translateX(${(i - (windows.length - 1) / 2) * 330 * s}px)`,
                transformStyle: 'preserve-3d',
              }}
            >
              <BrowserWindow
                win={w}
                s={s}
                progress={enter}
                z={0}
                width={winW}
                height={winH}
                rotateY={rot}
              />
            </div>
          );
        })}
      </div>
    </CameraRig>
  );
};