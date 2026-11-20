import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Scene} from '../../../schemas/showcase-v1';
import {CameraRig} from '../common/CameraRig';
// Fonts and scaling are NOT theme-scoped, so importing them is correct.
// Everything that IS theme-scoped (palette, type, spacing, shadow) must come
// from useDesign() — see tests/test_showcase_schema_parity.py::test_scenes_do_not_import_design_values_directly
import {FONT_NUM, FONT_SANS, TRAFFIC_LIGHTS, scaleFor} from '../design/tokens';
import {useDesign} from '../design/styleBible';

/**
 * Scene — a single Browser Window (the reference's "Dashboard 多窗口透视景深",
 * one window rather than a stack).
 *
 * WHY THIS IS ITS OWN COMPOSITION AND NOT `BrowserStack` WITH ONE ENTRY. The
 * stack authors its windows at screen scale and fans them on the z axis, then
 * solves each window's x so the CLUSTER is centred (see BrowserStack's centring
 * note). A single window has none of that: it is one large window held on the
 * optical axis, filling most of the frame, read as a product screenshot rather
 * than as a wall. Feeding one window through the stack produces a small window
 * adrift in a wide empty frame — a correct render of the wrong composition.
 *
 * So the window CHROME is drawn here in the same vocabulary (the macOS traffic
 * lights are the shared `TRAFFIC_LIGHTS` token — "a red dot is still a red dot"
 * whichever theme is up), and the marks reuse the design system rather than a
 * second copy of the stack's internals. `BrowserStack.tsx` is deliberately NOT
 * touched: it is guarded by `test_p4_9_ledger_numbers_resolve.py`, which reads
 * its `spreadX`/`spreadZ` defaults by line, so extracting its window would move
 * numbers a false ledgers' guard is pinned to.
 *
 * The graph supplies the window's title and its metric; the chrome, the roles,
 * the mark and the entrance are the design system's.
 */

const MiniBars: React.FC<{values: number[]; s: number; progress: number}> = ({values, s, progress}) => {
  const {PALETTE} = useDesign();
  const max = Math.max(...values, 1);
  return (
    <div style={{display: 'flex', alignItems: 'flex-end', gap: 10 * s, height: 160 * s}}>
      {values.map((v, i) => {
        const local = interpolate(progress, [i * 0.1, i * 0.1 + 0.55], [0, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
        return (
          <div
            key={i}
            style={{
              width: 26 * s,
              height: `${(v / max) * 100 * local}%`,
              background: i === values.length - 1 ? PALETTE.accent : PALETTE.column,
              borderRadius: 4 * s,
            }}
          />
        );
      })}
    </div>
  );
};

const Spark: React.FC<{values: number[]; s: number; progress: number}> = ({values, s, progress}) => {
  const {PALETTE} = useDesign();
  if (values.length < 2) return null;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = Math.max(max - min, 1e-6);
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * 100;
    const y = 100 - ((v - min) / span) * 100;
    return `${x},${y}`;
  });
  const len = 400;
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{width: '100%', height: 160 * s}}>
      <path
        d={`M ${pts.join(' L ')}`}
        fill="none"
        stroke={PALETTE.accent}
        strokeWidth={2.6}
        vectorEffect="non-scaling-stroke"
        strokeLinecap="round"
        strokeDasharray={len}
        strokeDashoffset={len * (1 - progress)}
      />
    </svg>
  );
};

export const BrowserWindow: React.FC<{scene: Scene}> = ({scene}) => {
  const {MOTION, PALETTE, RADIUS, SHADOW, SPACE, TYPE} = useDesign();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = scaleFor(comp.width, comp.height);
  const c = (scene.content ?? {}) as Record<string, unknown>;
  const layout = (scene.layout ?? {}) as Record<string, unknown>;

  const title = c.title !== undefined ? String(c.title) : '';
  const metric = c.metric !== undefined ? String(c.metric) : '';
  const caption = c.caption !== undefined ? String(c.caption) : '';
  const bars = Array.isArray(c.bars) ? (c.bars as unknown[]).map((n) => Number(n)) : [];
  const spark = Array.isArray(c.spark) ? (c.spark as unknown[]).map((n) => Number(n)) : [];

  const winW = Number(layout.windowWidth ?? 1400) * s;
  const winH = Number(layout.windowHeight ?? 800) * s;

  const enter = spring({
    frame,
    fps: comp.fps,
    config: MOTION.springs.settle,
    durationInFrames: Math.round(MOTION.enterSeconds * comp.fps),
  });
  const draw = interpolate(
    frame,
    [Math.round(MOTION.enterSeconds * comp.fps), Math.round((MOTION.enterSeconds + 1.0) * comp.fps)],
    [0, 1],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );

  return (
    <CameraRig camera={scene.camera} motion={scene.motion} durationInFrames={scene.durationInFrames}>
      <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
        <div
          style={{
            width: winW,
            height: winH,
            background: PALETTE.surface,
            border: `1px solid ${PALETTE.hairline}`,
            borderRadius: RADIUS.window * s,
            boxShadow: SHADOW.floating,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            opacity: Math.min(Math.max(enter, 0), 1),
            transform: `scale(${0.96 + 0.04 * Math.max(Math.min(enter, 1), 0)})`,
          }}
        >
          {/* chrome */}
          <div
            style={{
              height: 56 * s,
              display: 'flex',
              alignItems: 'center',
              gap: 10 * s,
              padding: `0 ${20 * s}px`,
              borderBottom: `1px solid ${PALETTE.hairline}`,
              background: PALETTE.surfaceElevated,
            }}
          >
            {TRAFFIC_LIGHTS.map((col) => (
              <div key={col} style={{width: 13 * s, height: 13 * s, borderRadius: '50%', background: col, opacity: 0.65}} />
            ))}
            <div style={{marginLeft: 16 * s, fontFamily: FONT_SANS, fontSize: 20 * s, color: PALETTE.inkMuted, letterSpacing: '0.02em'}}>
              {title}
            </div>
          </div>

          {/* body */}
          <div style={{flex: 1, display: 'flex', flexDirection: 'column', padding: `${SPACE.lg * s}px ${SPACE.xl * s}px`}}>
            <div style={{fontFamily: FONT_SANS, fontSize: TYPE.annotation.size * s, letterSpacing: TYPE.annotation.tracking, textTransform: 'uppercase', color: PALETTE.inkMuted}}>
              {caption}
            </div>
            <div
              style={{
                fontFamily: FONT_NUM,
                fontVariantNumeric: 'tabular-nums',
                fontSize: TYPE.displayXL.size * 0.9 * s,
                fontWeight: TYPE.displayXL.weight,
                letterSpacing: TYPE.displayXL.tracking,
                color: PALETTE.ink,
                marginTop: SPACE.sm * s,
              }}
            >
              {metric}
            </div>
            <div style={{flex: 1, display: 'flex', alignItems: 'flex-end', marginTop: SPACE.lg * s}}>
              {bars.length ? <MiniBars values={bars} s={s} progress={draw} /> : null}
              {spark.length ? <Spark values={spark} s={s} progress={draw} /> : null}
            </div>
          </div>
        </div>
      </div>
    </CameraRig>
  );
};
