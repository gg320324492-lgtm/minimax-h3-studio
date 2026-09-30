import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Scene} from '../../../schemas/showcase-v1';
import {CameraRig} from '../common/CameraRig';
import {FONT_NUM, FONT_SANS, scaleFrom} from '../design/tokens';
import {useDesign} from '../design/styleBible';
import {Reveal, Stagger} from '../common/primitives';

/**
 * Scene 3 — Big Number + Column Field (reference film ~32s)
 * A headline figure with a field of vertical columns receding behind it.
 *
 * The columns are DOM, not Three.js: at this count (a few dozen) CSS 3D beats a
 * WebGL canvas on render cost and text stays crisp. Deterministic heights from
 * a seed — the same graph always renders the same picture.
 */

const seeded = (seed: number, i: number) => {
  const x = Math.sin(seed * 9301 + i * 49297) * 233280;
  return x - Math.floor(x);
};

export const DataColumns: React.FC<{scene: Scene}> = ({scene}) => {
  const {MOTION, PALETTE, SHADOW, SPACE, TYPE} = useDesign();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = scaleFrom(comp.height);
  const c = (scene.content ?? {}) as Record<string, unknown>;

  const headline = String(c.headline ?? '');
  const unit = c.unit ? String(c.unit) : '';
  const count = Number(c.columns ?? 24);
  const seed = Number(c.columnSeed ?? 42);
  const layout = (scene.layout ?? {}) as Record<string, unknown>;
  const fieldHeight = Number(layout.fieldHeight ?? 420) * s;
  const columnWidth = Number(layout.columnWidth ?? 44) * s;
  const columnGap = Number(layout.columnGap ?? 10) * s;

  const valueIn = spring({
    frame,
    fps: comp.fps,
    config: MOTION.springs.hero,
    durationInFrames: Math.round(0.9 * comp.fps),
  });

  return (
    <CameraRig camera={scene.camera} motion={scene.motion} durationInFrames={scene.durationInFrames}>
      {/*
        Headline ABOVE, field BELOW, in normal flow — deliberately.

        The two were both absolutely positioned and centred on `top: 50%`, with
        the field 520px tall, so the field's top edge sat at y=323 while the
        caption under the headline ended at y=398. The caption was therefore
        always inside the column band, and whether it looked broken depended on
        the column seed: with a short column under the caption it read as depth,
        with a tall one the text was struck through by bars. That is a layout
        that can only be right by luck.

        In flow the browser guarantees the order and the spacing, so the
        collision is not representable. The trade is that the columns no longer
        pass behind the number — which is the right loss, since the reference
        beats keep the figure in clear space and the P4 brief rules out using
        clutter to fake depth.
      */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div
          style={{
            textAlign: 'center',
            transform: `scale(${0.94 + 0.06 * valueIn})`,
            zIndex: 2,
            opacity: valueIn,
          }}
        >
          <div
            style={{
              fontFamily: FONT_NUM,
              fontVariantNumeric: 'tabular-nums',
              fontSize: TYPE.displayXL.size * s * 1.5,
              fontWeight: TYPE.displayXL.weight,
              letterSpacing: TYPE.displayXL.tracking,
              color: PALETTE.ink,
              lineHeight: 1,
              textShadow: '0 20px 60px rgba(0,0,0,0.55)',
            }}
          >
            {headline}
          </div>
          {unit ? (
            <div
              style={{
                fontFamily: FONT_SANS,
                fontSize: TYPE.subheading.size * s,
                color: PALETTE.inkMuted,
                marginTop: SPACE.md * s,
                letterSpacing: TYPE.annotation.tracking,
              }}
            >
              {unit}
            </div>
          ) : null}
        </div>

        <div
          style={{
            marginTop: SPACE.xl * s,
            display: 'flex',
            alignItems: 'flex-end',
            gap: columnGap,
            height: fieldHeight,
            transformStyle: 'preserve-3d',
          }}
        >
          {Array.from({length: count}, (_, i) => {
            const h = 0.25 + seeded(seed, i) * 0.75;
            const at = i * 0.9;
            const grow = spring({
              frame: frame - at * 3,
              fps: comp.fps,
              config: MOTION.springs.land,
            });
            const isTall = i % 5 === 0;
            return (
              <div
                key={i}
                style={{
                  width: columnWidth,
                  height: `${h * 100 * grow}%`,
                  background: isTall ? PALETTE.accent : PALETTE.column,
                  borderRadius: `${4 * s}px ${4 * s}px 0 0`,
                  boxShadow: isTall ? SHADOW.glowAccent : 'none',
                }}
              />
            );
          })}
        </div>
      </div>
    </CameraRig>
  );
};

/**
 * Scene 4 — Calendar / Data Grid (reference film ~34-38s)
 * A month grid whose cells carry deterministic values; the highlight cells
 * arrive last so the eye is led to them.
 */

export const CalendarGrid: React.FC<{scene: Scene}> = ({scene}) => {
  const {MOTION, PALETTE, SHADOW, SPACE, TYPE} = useDesign();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = scaleFrom(comp.height);
  const layout = (scene.layout ?? {}) as Record<string, unknown>;
  const motion = scene.motion;
  const c = (scene.content ?? {}) as Record<string, unknown>;

  const seed = Number(c.seed ?? 7);
  const month = String(c.month ?? '');
  const highlight = (c.highlight ?? []) as number[];
  const cell = Number(layout.cell ?? 34) * s * 1.9;
  const gap = Number(layout.gap ?? 6) * s;

  const days = 30;
  const cols = 7;
  const stagger = Number(motion?.stagger ?? 0.012);

  const monthIn = spring({
    frame,
    fps: comp.fps,
    config: MOTION.springs.settle,
    durationInFrames: Math.round(MOTION.enterSeconds * comp.fps),
  });

  return (
    <CameraRig camera={scene.camera} motion={motion} durationInFrames={scene.durationInFrames}>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          opacity: monthIn,
        }}
      >
        <div
          style={{
            fontFamily: FONT_NUM,
            fontVariantNumeric: 'tabular-nums',
            fontSize: TYPE.heading.size * s,
            fontWeight: 700,
            color: PALETTE.ink,
            marginBottom: SPACE.lg * s,
            letterSpacing: '-0.01em',
          }}
        >
          {month}
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${cols}, ${cell}px)`,
            gap,
          }}
        >
          {Array.from({length: days}, (_, i) => {
            const v = seeded(seed, i);
            const hl = highlight.includes(i + 1);
            const local = spring({
              frame: frame - i * stagger * comp.fps,
              fps: comp.fps,
              config: MOTION.springs.reveal,
            });
            const alpha = 0.05 + v * 0.16;
            return (
              <div
                key={i}
                style={{
                  width: cell,
                  height: cell,
                  borderRadius: 6 * s,
                  background: hl ? PALETTE.accent : `rgba(245,242,234,${alpha})`,
                  transform: `scale(${hl ? 1 : 0.55 + 0.45 * local})`,
                  opacity: hl ? 1 : local,
                  boxShadow: hl ? SHADOW.glowAccent : 'none',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontFamily: FONT_NUM,
                  fontVariantNumeric: 'tabular-nums',
                  fontSize: 15 * s,
                  color: hl ? '#14140F' : PALETTE.inkFaint,
                }}
              >
                {i + 1}
              </div>
            );
          })}
        </div>
      </div>
    </CameraRig>
  );
};