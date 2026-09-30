import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Scene} from '../../../schemas/showcase-v1';
import {CameraRig} from '../common/CameraRig';
import {FONT_NUM, FONT_SANS, scaleFrom} from '../design/tokens';
import {useDesign} from '../design/styleBible';

/**
 * Scene 1 — KPI Hero (reference film ~24s)
 * A number so large it is the composition, on a near-empty ground.
 * Premium grammar: slow masked reveal, tabular count-up, then a settle that
 * lets the viewer read it. No shake, no flash, no RGB split.
 */

const countUp = (frame: number, fps: number, target: number, seconds = 1.6) => {
  const p = Math.min(frame / (seconds * fps), 1);
  return target * (1 - (1 - p) ** 4); // expo-out
};

const fmt = (n: number, decimals: number) =>
  n.toLocaleString('en-US', {minimumFractionDigits: decimals, maximumFractionDigits: decimals});

export const KpiHero: React.FC<{scene: Scene}> = ({scene}) => {
  const {MOTION, PALETTE, RADIUS, SPACE, TYPE} = useDesign();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = scaleFrom(comp.height);
  const c = (scene.content ?? {}) as Record<string, unknown>;
  const layout = (scene.layout ?? {}) as Record<string, unknown>;

  const rawValue = c.value;
  const target = typeof rawValue === 'number' ? rawValue : parseFloat(String(rawValue ?? 0));
  const decimals = /\./.test(String(rawValue)) ? String(rawValue).split('.')[1].length : 0;
  const prefix = String(c.prefix ?? '');
  const suffix = String(c.suffix ?? '');
  const delta = c.delta ? String(c.delta) : '';
  const caption = c.caption ? String(c.caption) : '';
  const eyebrow = String(layout.eyebrow ?? '');
  const padX = Number(layout.padX ?? 120) * s;

  // entrance: the whole block rises and settles, the number counts up behind it
  const enter = spring({
    frame,
    fps: comp.fps,
    config: {damping: 200},
    durationInFrames: Math.round(MOTION.enterSeconds * comp.fps),
  });
  const mask = interpolate(enter, [0, 1], [102, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const value = countUp(frame, comp.fps, target, 1.6);
  const deltaIn = interpolate(frame, [Math.round(1.5 * comp.fps), Math.round(2.1 * comp.fps)],
    [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  const positive = !delta.trim().startsWith('-');

  return (
    <CameraRig camera={scene.camera} motion={scene.motion} durationInFrames={scene.durationInFrames}>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          paddingLeft: padX,
          paddingRight: padX,
          opacity: enter,
          transform: `translateY(${enter * 0 - (1 - enter) * 40 * s}px)`,
        }}
      >
        {eyebrow ? (
          <div
            style={{
              fontFamily: FONT_SANS,
              fontSize: TYPE.annotation.size * s,
              fontWeight: 500,
              letterSpacing: TYPE.annotation.tracking,
              color: PALETTE.accent,
              textTransform: 'uppercase',
              marginBottom: SPACE.lg * s,
              overflow: 'hidden',
              height: TYPE.annotation.size * s * 1.4,
            }}
          >
            <div style={{transform: `translateY(${mask * 100}%)`}}>{eyebrow}</div>
          </div>
        ) : null}

        <div
          style={{
            display: 'flex',
            alignItems: 'baseline',
            fontFamily: FONT_NUM,
            fontVariantNumeric: 'tabular-nums',
            color: PALETTE.ink,
            lineHeight: TYPE.kpiXL.leading,
            overflow: 'hidden',
          }}
        >
          {prefix ? (
            <span style={{fontSize: TYPE.kpiXL.size * 0.5 * s, color: PALETTE.inkMuted, marginRight: 6 * s}}>
              {prefix}
            </span>
          ) : null}
          <span style={{fontSize: TYPE.kpiXL.size * s, fontWeight: TYPE.kpiXL.weight, letterSpacing: TYPE.kpiXL.tracking}}>
            {fmt(value, decimals)}
          </span>
          {suffix ? (
            <span
              style={{
                fontSize: TYPE.kpiXL.size * 0.34 * s,
                color: PALETTE.accent,
                marginLeft: 18 * s,
                // sit the suffix on the baseline rather than inline, so it can
                // never overlap the last digit
                position: 'relative',
                top: 0,
              }}
            >
              {suffix}
            </span>
          ) : null}
        </div>

        <div style={{display: 'flex', alignItems: 'center', gap: SPACE.md * s, marginTop: SPACE.lg * s}}>
          {delta ? (
            <span
              style={{
                fontFamily: FONT_NUM,
                fontVariantNumeric: 'tabular-nums',
                fontSize: TYPE.subheading.size * s,
                fontWeight: 700,
                color: positive ? PALETTE.positive : PALETTE.negative,
                opacity: deltaIn,
                transform: `translateY(${(1 - deltaIn) * 12 * s}px)`,
                background: (positive ? PALETTE.positive : PALETTE.negative) + '1F',
                borderRadius: RADIUS.chip,
                padding: `${6 * s}px ${16 * s}px`,
              }}
            >
              {delta}
            </span>
          ) : null}
          {caption ? (
            <span
              style={{
                fontFamily: FONT_SANS,
                fontSize: TYPE.body.size * s,
                color: PALETTE.inkMuted,
                opacity: deltaIn,
              }}
            >
              {caption}
            </span>
          ) : null}
        </div>

        <div
          style={{
            marginTop: SPACE.xl * s,
            width: 160 * s,
            height: 4 * s,
            background: PALETTE.accent,
            transformOrigin: 'left center',
            transform: `scaleX(${enter})`,
          }}
        />
      </div>
    </CameraRig>
  );
};