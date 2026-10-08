import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Scene} from '../../../schemas/showcase-v1';
import {CameraRig} from '../common/CameraRig';
// Fonts and scaling are NOT theme-scoped, so importing them is correct.
// Everything that IS theme-scoped (palette, type, spacing, shadow) must come
// from useDesign() — see tests/test_design_system.py.
import {FONT_SANS, scaleFor} from '../design/tokens';
import {useDesign} from '../design/styleBible';
import {MaskReveal} from '../common/primitives';

/**
 * Scene — Quote card (reference film: "黑卡 Quote + 极大留白").
 *
 * THE MOST IMPORTANT WORD IN THAT LINE IS 留白 — WHITESPACE. A quote scene is
 * where the film breathes between data beats, so the renderer's whole job is to
 * put a sentence in a large, nearly empty frame and get out of the way. That
 * makes "rendered correctly" definable in a way that is easy to betray: if the
 * frame is busy, it is WRONG, however correct the text is.
 *
 * So the design is: a dark card just off-frame-centre, the sentence at display
 * scale on it, an attribution beneath on a short accent rule, everything else
 * empty. Nothing animates except the entrance, and that is a masked reveal —
 * the premium grammar (`MaskReveal`, `MOTION.springs.settle`), not a pop.
 *
 * A `content` printer would be a bare `<div>{text}</div>`. This decides the
 * card, the measure, the attribution rule, the off-centre composition and the
 * reveal; the graph decides only the words.
 */
export const Quote: React.FC<{scene: Scene}> = ({scene}) => {
  const {MOTION, PALETTE, SHADOW, SPACE, TYPE, RADIUS} = useDesign();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = scaleFor(comp.width, comp.height);
  const c = (scene.content ?? {}) as Record<string, unknown>;
  const layout = (scene.layout ?? {}) as Record<string, unknown>;

  const text = c.text !== undefined ? String(c.text) : '';
  const attribution = c.attribution !== undefined ? String(c.attribution) : '';
  const role = c.role !== undefined ? String(c.role) : '';
  const cardW = Number(layout.cardWidth ?? 1280) * s;
  const markSize = TYPE.displayL.size;

  const enter = spring({
    frame,
    fps: comp.fps,
    config: MOTION.springs.settle,
    durationInFrames: Math.round(MOTION.enterSeconds * comp.fps),
  });
  const rule = interpolate(frame, [Math.round(0.5 * comp.fps), Math.round(1.4 * comp.fps)], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <CameraRig camera={scene.camera} motion={scene.motion} durationInFrames={scene.durationInFrames}>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div
          style={{
            position: 'relative',
            width: cardW,
            boxSizing: 'border-box',
            padding: `${SPACE.xl * 2 * s}px ${(SPACE.xl * 2 - SPACE.sm) * s}px ${SPACE.xl * s}px`,
            background: PALETTE.surfaceElevated,
            border: `1px solid ${PALETTE.hairline}`,
            borderRadius: RADIUS.panel * s,
            boxShadow: SHADOW.floating,
            opacity: Math.min(Math.max(enter, 0), 1),
            transform: `translateY(${(1 - Math.max(Math.min(enter, 1), 0)) * 24 * s}px)`,
          }}
        >
          {/* an oversized opening mark, in the accent, hung in the margin —
              a typographic cue, not a character of the sentence */}
          <div
            style={{
              position: 'absolute',
              top: SPACE.lg * s,
              left: SPACE.lg * s,
              fontFamily: FONT_SANS,
              fontSize: markSize * 1.4 * s,
              lineHeight: 1,
              color: PALETTE.accent,
              opacity: 0.5,
            }}
          >
            {String.fromCharCode(0x201C)}
          </div>

          <MaskReveal durationSeconds={MOTION.durations.settle} springName="settle">
            <div
              style={{
                fontFamily: FONT_SANS,
                fontSize: TYPE.heading.size * s,
                fontWeight: 600,
                lineHeight: 1.28,
                letterSpacing: '-0.01em',
                color: PALETTE.ink,
              }}
            >
              {text}
            </div>
          </MaskReveal>

          {attribution || role ? (
            <div style={{marginTop: SPACE.xl * s, display: 'flex', alignItems: 'center', gap: SPACE.md * s}}>
              <div
                style={{
                  width: interpolate(rule, [0, 1], [0, 72]) * s,
                  height: 3 * s,
                  background: PALETTE.accent,
                }}
              />
              <div style={{fontFamily: FONT_SANS, fontSize: TYPE.caption.size * s, color: PALETTE.inkMuted, opacity: rule}}>
                {attribution}
                {attribution && role ? ' · ' : ''}
                {role ? <span style={{color: PALETTE.accent}}>{role}</span> : null}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </CameraRig>
  );
};
