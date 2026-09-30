import React from 'react';
import {interpolate, spring as remotionSpring, useCurrentFrame, useVideoConfig} from 'remotion';
import {MOTION, profileOf, scaleFor, type MotionProfile, type SpringName} from '../design/tokens';
import {cubicBezierEase} from './CameraRig';

/**
 * Motion primitives (P5).
 *
 * Every animated thing in a showcase scene goes through this file. The point is
 * not tidiness: it is that two entrances which SHOULD feel identical do, because
 * both ask for springName="settle" rather than each picking damping numbers.
 * Before P5, `damping: 200` was written three times across three scenes by hand.
 *
 * NOTE: the spring NAME is `springName`, never `spring` — a prop called `spring`
 * shadows remotion's spring() and turns `spring({...})` into calling a string.
 */

const cfgFor = (name: SpringName) => MOTION.springs[name] ?? MOTION.springs.settle;

export type RevealProps = {
  /** frame offset so siblings can stagger without separate components */
  delay?: number;
  springName?: SpringName;
  /** seconds; defaults to the profile's standard duration */
  durationSeconds?: number;
  /** extra travel in design px */
  rise?: number;
  fade?: boolean;
  children: React.ReactNode;
  style?: React.CSSProperties;
};

/** The standard entrance: rise + fade on a named spring. */
export const Reveal: React.FC<RevealProps> = ({
  delay = 0,
  springName = 'settle',
  durationSeconds,
  rise = 28,
  fade = true,
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const secs = durationSeconds ?? MOTION.durations.standard;
  const p = remotionSpring({
    frame: frame - delay,
    fps: comp.fps,
    config: cfgFor(springName),
    durationInFrames: Math.max(1, Math.round(secs * comp.fps)),
  });
  const s = scaleFor(comp.width, comp.height);
  return (
    <div
      style={{
        opacity: fade ? Math.min(Math.max(p, 0), 1) : 1,
        transform: `translateY(${(1 - p) * rise * s}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

/** Staggered children — each revealed in turn with the profile's stagger. */
export const Stagger: React.FC<{
  children: React.ReactNode;
  profile?: MotionProfile;
  index?: number;
  stagger?: number;
  springName?: SpringName;
  rise?: number;
}> = ({children, profile = 'premium', index = 0, stagger, springName, rise}) => {
  const comp = useVideoConfig();
  const p = profileOf(profile);
  const step = Math.round((stagger ?? p.stagger) * comp.fps);
  return (
    <>
      {React.Children.map(children, (child, i) => (
        <Reveal
          key={i}
          delay={(index + i) * step}
          springName={springName ?? (p.spring as SpringName)}
          rise={rise}
        >
          {child}
        </Reveal>
      ))}
    </>
  );
};

/** Mask reveal: content slides up from behind a fixed mask. */
export const MaskReveal: React.FC<{
  delay?: number;
  durationSeconds?: number;
  springName?: SpringName;
  children: React.ReactNode;
}> = ({delay = 0, durationSeconds, springName = 'settle', children}) => {
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = scaleFor(comp.width, comp.height);
  const p = remotionSpring({
    frame: frame - delay,
    fps: comp.fps,
    config: cfgFor(springName),
    durationInFrames: Math.max(1, Math.round((durationSeconds ?? MOTION.durations.standard) * comp.fps)),
  });
  return (
    <div style={{overflow: 'hidden'}}>
      <div style={{transform: `translateY(${(1 - p) * 110 * s}%)`}}>{children}</div>
    </div>
  );
};

/** A light sweep across a surface, once. Premium scenes use it sparingly. */
export const SpecularSweep: React.FC<{delayFrames?: number; durationFrames?: number}> = ({
  delayFrames = 12,
  durationFrames = 26,
}) => {
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const t = interpolate(frame, [delayFrames, delayFrames + durationFrames], [-40, 140], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  if (frame < delayFrames || frame > delayFrames + durationFrames) return null;
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: 'none',
        background: `linear-gradient(105deg, transparent ${t - 12}%, rgba(255,255,255,0.10) ${t}%, transparent ${t + 12}%)`,
      }}
    />
  );
};

/** Vignette that tightens briefly — an emphasis cue, not a decoration. */
export const VignettePulse: React.FC<{atFrames?: number; strength?: number}> = ({
  atFrames = 0,
  strength = 0.45,
}) => {
  const frame = useCurrentFrame();
  if (frame < atFrames || frame > atFrames + 8) return null;
  const k = 1 - Math.abs(frame - atFrames - 4) / 4;
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: 'none',
        background: 'radial-gradient(ellipse at center, transparent 52%, rgba(0,0,0,0.9) 100%)',
        opacity: Math.max(k, 0) * strength,
      }}
    />
  );
};

/**
 * Scene transitions (P5) — implements the `transitionIn` field the showcase
 * schema has always declared.
 *
 * These are FRAME-LOCAL: they animate inside the scene's own frames and never
 * change when a scene starts or ends. That constraint is inherited from the
 * ffmpeg-era pipeline — a transition that consumed time from either neighbour
 * would move every downstream subtitle, audio cue and beat off its absolute
 * second. depth-push, mask-wipe and dissolve all satisfy it.
 */
export const SceneEnter: React.FC<{
  kind?: string;
  durationInFrames?: number;
  children: React.ReactNode;
}> = ({kind = 'none', durationInFrames = 18, children}) => {
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = scaleFor(comp.width, comp.height);
  const d = Math.max(1, durationInFrames);
  if (kind === 'none' || frame >= d) return <>{children}</>;

  const p = cubicBezierEase(0.16, 1, 0.3, 1)(Math.min(frame / d, 1));
  const style: React.CSSProperties = {};
  switch (kind) {
    case 'fade':
      style.opacity = p;
      break;
    case 'mask-wipe':
      style.opacity = Math.min(p * 1.4, 1);
      style.clipPath = `inset(${(1 - p) * 100}% 0 0 0)`;
      break;
    case 'depth-push':
      style.opacity = Math.min(p * 1.6, 1);
      style.transform = `perspective(${1400 * s}px) translateZ(${(1 - p) * -160 * s}px) scale(${0.94 + 0.06 * p})`;
      break;
    case 'dissolve':
      style.opacity = p;
      style.filter = `blur(${(1 - p) * 8 * s}px)`;
      break;
    default:
      style.opacity = p;
  }
  return <div style={style}>{children}</div>;
};