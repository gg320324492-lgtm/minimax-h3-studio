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

/**
 * The camera's full state at a given frame, in SCALED px/deg.
 *
 * This is exported because layout has to know where the camera is, not just what
 * transform string to hand CSS. Browser Stack needs the camera's translateZ to
 * work out each window's absolute depth: whether a window is magnified depends
 * on its distance from the EYE, which is the rig's z plus the window's own z.
 * Recomputing the camera move inside a scene would be a second copy of the
 * ramp/easing maths, and the two copies would drift — which is the same class
 * of bug as a scene re-deriving the style bible instead of reading it.
 */
/**
 * CSS perspective projects about the centre of the perspective element: a point
 * at (x, z) appears on screen at `x * P / (P - z)`. Two consequences scenes
 * depend on:
 *
 *  - depth is measured from the EYE, so z must be ABSOLUTE — the object's own
 *    plane plus the camera rig's. Using the object's own z alone is wrong for
 *    any moving camera.
 *  - a nearer object is magnified. A row of objects at increasing depth is
 *    therefore NOT symmetric on screen even if its authored x positions are:
 *    the near end spreads out and the far end pulls in. That is the defect P6
 *    recorded as "optical centre right of frame centre".
 *
 * The maths now lives in ./projection so it can be imported by a test with no
 * React or Remotion in the way; this module owns the camera's MOTION only, so
 * there is exactly one implementation of each concern.
 */
export type CameraState = {
  perspective: number;
  translateX: number;
  translateY: number;
  translateZ: number;
  rotateX: number;
  rotateY: number;
  rotateZ: number;
  scale: number;
  /** normalised time through the camera move, 0..1 */
  t: number;
};

const rampOf = (preset: string, dur: number, fps: number) => {
  const seconds =
    preset === 'energetic'
      ? MOTION.energeticCameraSeconds
      : preset === 'minimal'
        ? 0
        : MOTION.premiumCameraSeconds;
  return Math.max(1, (seconds * fps) / Math.max(dur, 1));
};

/**
 * Evaluate the camera at `frame`. Pure: CameraRig and any scene that needs the
 * camera's position both call this with the same arguments and cannot disagree.
 */
export const cameraStateAt = (
  camera: Camera | undefined,
  motion: Motion | undefined,
  frame: number,
  height: number,
  durationInFrames: number,
  fps: number
): CameraState => {
  const s = height / 1080;
  const dur = durationInFrames > 1 ? durationInFrames : 1;
  const t = Math.min(frame / (dur - 1), 1);
  // the move is authored as if it continues past the scene, so the ramp can
  // exceed the scene length — that is what makes it feel like a real move
  const ramp = rampOf(motion?.preset ?? 'premium', dur, fps);
  const ct = Math.min(t / ramp, 1);
  return {
    perspective: (camera?.perspective ?? 0) * s,
    translateX: track(camera?.translateX, ct, 0) * s,
    translateY: track(camera?.translateY, ct, 0) * s,
    translateZ: track(camera?.translateZ, ct, 0) * s,
    rotateX: track(camera?.rotateX, ct, 0),
    rotateY: track(camera?.rotateY, ct, 0),
    rotateZ: track(camera?.rotateZ, ct, 0),
    scale: track(camera?.scale, ct, 1),
    t: ct,
  };
};

/** Hook form, for components that must agree with the rig they sit inside. */
export const useCameraState = (
  camera?: Camera,
  motion?: Motion,
  durationInFrames?: number
): CameraState => {
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  return cameraStateAt(
    camera,
    motion,
    frame,
    comp.height,
    durationInFrames ?? comp.durationInFrames,
    comp.fps
  );
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
  const cam = useCameraState(camera, motion, durationInFrames);

  const transform = useMemo(() => {
    const px = (v: number) => `${v}px`;
    const deg = (v: number) => `${v}deg`;
    const parts: string[] = [];
    if (cam.perspective) parts.push(`perspective(${px(cam.perspective)})`);
    const {translateX: tx, translateY: ty, translateZ: tz} = cam;
    if (ty || tx) parts.push(`translate3d(${px(tx)}, ${px(ty)}, ${px(tz)})`);
    else if (tz) parts.push(`translateZ(${px(tz)})`);
    if (cam.rotateX) parts.push(`rotateX(${deg(cam.rotateX)})`);
    if (cam.rotateY) parts.push(`rotateY(${deg(cam.rotateY)})`);
    if (cam.rotateZ) parts.push(`rotateZ(${deg(cam.rotateZ)})`);
    if (cam.scale !== 1) parts.push(`scale(${cam.scale})`);
    return parts.length ? parts.join(' ') : 'none';
  }, [cam]);

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