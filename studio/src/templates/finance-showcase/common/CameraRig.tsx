import React, {useMemo} from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Camera, Motion} from '../../../schemas/showcase-v1';
import {MOTION} from '../design/tokens';

/**
 * CameraRig — the 2.5D camera every showcase scene renders inside.
 *
 * The reference film gets its depth from perspective plus layered parallax, not
 * from effects: several planes at different translateZ, one camera transform
 * applied to all of them. This component is that camera.
 *
 * Camera motion is separate from component motion on purpose: the camera is
 * slow and eased (premium: 2.6s, expo-out), while components pop on their own
 * timing. Driving both from one clock is what makes motion feel amateur.
 *
 * All channels accept a number (constant) or [from, to] (interpolated over the
 * scene). Values are px/deg at design height 1080 and scale with the format.
 */

const track = (
  v: number | [number, number] | undefined,
  t: number,
  fallback: number
): number => {
  if (v === undefined) return fallback;
  if (typeof v === 'number') return v;
  return interpolate(t, [0, 1], [v[0], v[1]], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
};

export type CameraRigProps = {
  camera?: Camera;
  motion?: Motion;
  /** durationInFrames of the enclosing scene; defaults to the composition */
  durationInFrames?: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
};

export const CameraRig: React.FC<CameraRigProps> = ({
  camera,
  motion,
  durationInFrames,
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const dur = durationInFrames ?? comp.durationInFrames;
  const t = dur > 1 ? Math.min(frame / (dur - 1), 1) : 1;

  const preset = motion?.preset ?? 'premium';
  const seconds = preset === 'energetic'
    ? MOTION.energeticCameraSeconds
    : preset === 'minimal'
    ? 0
    : MOTION.premiumCameraSeconds;
  // frames over which the camera move completes (may exceed the scene: the move
  // is authored as if it continues, which is what makes it feel like a real move
  // rather than a tween that starts and stops)
  const ramp = Math.max(1, (seconds * comp.fps) / Math.max(dur, 1));
  const ct = Math.min(t / ramp, 1);

  const ease = (x: number) =>
    MOTION.enterEase.length === 4
      ? cubicBezier(MOTION.enterEase[0], MOTION.enterEase[1], MOTION.enterEase[2], MOTION.enterEase[3])(x)
      : x;

  const transform = useMemo(() => {
    const s = scaleOf(comp.height);
    const px = (v: number) => `${v * s}px`;
    const deg = (v: number) => `${v}deg`;
    const parts: string[] = [];
    const persp = camera?.perspective;
    if (persp) parts.push(`perspective(${persp * s}px)`);
    const tx = track(camera?.translateX, ct, 0);
    const ty = track(camera?.translateY, ct, 0);
    const tz = track(camera?.translateZ, ct, 0);
    const rx = track(camera?.rotateX, ct, 0);
    const ry = track(camera?.rotateY, ct, 0);
    const rz = track(camera?.rotateZ, ct, 0);
    const sc = track(camera?.scale, ct, 1);
    if (ty || tx) parts.push(`translate3d(${px(tx)}, ${px(ty)}, ${px(tz)})`);
    else if (tz) parts.push(`translateZ(${px(tz)})`);
    if (rx) parts.push(`rotateX(${deg(rx)})`);
    if (ry) parts.push(`rotateY(${deg(ry)})`);
    if (rz) parts.push(`rotateZ(${deg(rz)})`);
    if (sc !== 1) parts.push(`scale(${sc})`);
    return parts.length ? parts.join(' ') : 'none';
  }, [camera, ct, comp.height]);

  return (
    <AbsoluteFill
      style={{
        transform,
        transformStyle: 'preserve-3d',
        willChange: 'transform',
        ...style,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

const scaleOf = (height: number) => height / 1080;

/** Minimal cubic-bezier solver — avoids a dependency for one curve. */
const cubicBezier =
  (x1: number, y1: number, x2: number, y2: number) =>
  (x: number): number => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let t = x;
    for (let i = 0; i < 6; i += 1) {
      const cx = 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t ** 2 * x2 + t ** 3;
      const dx =
        3 * (1 - t) ** 2 * x1 + 6 * (1 - t) * t * (x2 - x1) + 3 * t ** 2 * (1 - x2);
      if (Math.abs(cx - x) < 1e-4) break;
      if (Math.abs(dx) < 1e-6) break;
      t -= (cx - x) / dx;
    }
    const y =
      3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t ** 2 * y2 + t ** 3;
    return y;
  };

export const cubicBezierEase = cubicBezier;