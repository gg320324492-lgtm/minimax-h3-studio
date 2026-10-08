import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Scene} from '../../../schemas/showcase-v1';
import {CameraRig} from '../common/CameraRig';
// Fonts and scaling are NOT theme-scoped, so importing them is correct.
// Everything that IS theme-scoped (palette, type, spacing, shadow) must come
// from useDesign() — see tests/test_design_system.py.
import {FONT_NUM, FONT_SANS, scaleFor} from '../design/tokens';
import {useDesign} from '../design/styleBible';

/**
 * Scene — Stat Card / Card Grid (reference film: "日历/数据卡/表格矩阵").
 *
 * WHY THESE TWO EXIST AND WHY THEY ARE ONE FILE. The master plan's visual target
 * names "数据卡" (data cards) and the responsibility split puts "Card" on the
 * Remotion side — "文字、数字、表格、UI 绝不交给 H3 生成，必须程序化渲染". Until P26
 * neither `stat-card` nor `card-grid` had a renderer, so a graph asking for a
 * card got the `MissingScene` placeholder instead.
 *
 * The two are one file for the same reason `DataColumns.tsx` carries both
 * `DataColumns` and `CalendarGrid`: a grid of cards IS a card, repeated, and the
 * card is the design. Splitting them would put the card's chrome in one file and
 * its only other consumer in another, which is how two spellings of "a card"
 * appear.
 *
 * WHAT MAKES THIS A RENDERER RATHER THAN A `content` PRINTER. The card is a
 * designed surface — a token-driven panel (`PALETTE.surface`, `RADIUS.card`,
 * `SHADOW.medium`), a label in the annotation role, a number in the NUMERIC
 * table role, a signed delta in the positive/negative role, and a tiny
 * sparkline mark whose shape comes from the data. The graph supplies the values;
 * the LANGUAGE (roles, spacing, motion, the sign-colour rule) is the design
 * system's, exactly as `KpiHero` takes a number and decides how a KPI looks.
 * A renderer that echoed `content` would have no roles and no marks.
 */

/** A deterministic little series from a seed, so two renders cannot differ. */
const seededSeries = (seed: number, n: number, lo = 0, hi = 1): number[] => {
  const out: number[] = [];
  for (let i = 0; i < n; i += 1) {
    const x = Math.sin(seed * 9301 + i * 49297 + 0.5) * 233280;
    const f = x - Math.floor(x);
    out.push(lo + f * (hi - lo));
  }
  return out;
};

type CardContent = {
  label?: unknown;
  value?: unknown;
  prefix?: unknown;
  suffix?: unknown;
  delta?: unknown;
  note?: unknown;
  /** per-card seed — a card may carry a mark, and its shape must be stable */
  seed?: unknown;
  /** explicit little series; falls back to a seeded one */
  series?: unknown;
  /** the emphasised card, in a grid, draws its number in the accent */
  accent?: unknown;
};

const numOr = (v: unknown, fallback: number): number => {
  const n = typeof v === 'number' ? v : parseFloat(String(v ?? ''));
  return Number.isFinite(n) ? n : fallback;
};

/** A small signed trend line. One path, no axes — the premium mark grammar. */
const Spark: React.FC<{values: number[]; width: number; height: number; color: string; draw: number}> = ({
  values,
  width,
  height,
  color,
  draw,
}) => {
  if (values.length < 2) return null;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = Math.max(max - min, 1e-6);
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * 100;
    const y = 100 - ((v - min) / span) * 100;
    return `${x},${y}`;
  });
  const d = `M ${pts.join(' L ')}`;
  const len = 320;
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{width, height}}>
      <path
        d={d}
        fill="none"
        stroke={color}
        strokeWidth={2.6}
        vectorEffect="non-scaling-stroke"
        strokeLinecap="round"
        strokeDasharray={len}
        strokeDashoffset={len * (1 - draw)}
      />
    </svg>
  );
};

/**
 * The card surface itself. Exported because the grid and the single-card scene
 * must draw the SAME card — a second copy is how the two drift apart.
 *
 * `progress` carries the entrance (0..1), supplied by whichever scene owns the
 * stagger, so the card never invents its own timing.
 */
export const Card: React.FC<{
  c: CardContent;
  s: number;
  progress: number;
  width?: number;
  height?: number;
  /** draw its number in the accent and lift it slightly — the grid's one point */
  emphasised?: boolean;
  sparkDraw?: number;
}> = ({c, s, progress, width, height, emphasised = false, sparkDraw = 1}) => {
  const {PALETTE, RADIUS, SHADOW, SPACE, TYPE, MOTION} = useDesign();

  const label = c.label !== undefined ? String(c.label) : '';
  const value = c.value !== undefined ? String(c.value) : '';
  const prefix = c.prefix !== undefined ? String(c.prefix) : '';
  const suffix = c.suffix !== undefined ? String(c.suffix) : '';
  const delta = c.delta !== undefined ? String(c.delta) : '';
  const note = c.note !== undefined ? String(c.note) : '';
  const positive = !delta.trim().startsWith('-');
  const series = Array.isArray(c.series)
    ? (c.series as unknown[]).map((x) => numOr(x, 0))
    : seededSeries(numOr(c.seed, 7), 12);

  return (
    <div
      style={{
        position: 'relative',
        width,
        height,
        boxSizing: 'border-box',
        padding: `${SPACE.lg * s}px ${SPACE.lg * s}px`,
        background: PALETTE.surface,
        border: `1px solid ${emphasised ? PALETTE.accent + '55' : PALETTE.hairline}`,
        borderRadius: RADIUS.card * s,
        boxShadow: emphasised ? SHADOW.glowAccent : SHADOW.medium,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        overflow: 'hidden',
        opacity: Math.min(Math.max(progress, 0), 1),
        transform: `translateY(${(1 - Math.max(Math.min(progress, 1), 0)) * 28 * s}px)`,
      }}
    >
      {label ? (
        <div
          style={{
            fontFamily: FONT_SANS,
            fontSize: TYPE.annotation.size * s,
            fontWeight: 500,
            letterSpacing: TYPE.annotation.tracking,
            textTransform: 'uppercase',
            color: emphasised ? PALETTE.accent : PALETTE.inkMuted,
          }}
        >
          {label}
        </div>
      ) : null}

      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          fontFamily: FONT_NUM,
          fontVariantNumeric: 'tabular-nums',
          color: emphasised ? PALETTE.accent : PALETTE.ink,
          lineHeight: TYPE.numericTable.leading,
        }}
      >
        {prefix ? (
          <span style={{fontSize: TYPE.numericTable.size * 0.5 * s, color: PALETTE.inkMuted, marginRight: 4 * s}}>
            {prefix}
          </span>
        ) : null}
        <span style={{fontSize: TYPE.numericTable.size * s, fontWeight: TYPE.numericTable.weight, letterSpacing: TYPE.numericTable.tracking}}>
          {value}
        </span>
        {suffix ? (
          <span style={{fontSize: TYPE.numericTable.size * 0.44 * s, color: PALETTE.accent, marginLeft: 8 * s}}>
            {suffix}
          </span>
        ) : null}
      </div>

      <div style={{display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: SPACE.md * s}}>
        <div style={{display: 'flex', flexDirection: 'column', gap: 6 * s}}>
          {delta ? (
            <span
              style={{
                alignSelf: 'flex-start',
                fontFamily: FONT_NUM,
                fontVariantNumeric: 'tabular-nums',
                fontSize: TYPE.annotation.size * 1.1 * s,
                fontWeight: 700,
                color: positive ? PALETTE.positive : PALETTE.negative,
                background: (positive ? PALETTE.positive : PALETTE.negative) + '1F',
                borderRadius: RADIUS.chip,
                padding: `${3 * s}px ${12 * s}px`,
              }}
            >
              {delta}
            </span>
          ) : null}
          {note ? (
            <span style={{fontFamily: FONT_SANS, fontSize: TYPE.caption.size * 0.8 * s, color: PALETTE.inkMuted}}>
              {note}
            </span>
          ) : null}
        </div>
        <Spark
          values={series}
          width={120 * s}
          height={44 * s}
          color={emphasised ? PALETTE.accent : PALETTE.columnBright}
          draw={sparkDraw}
        />
      </div>
    </div>
  );
};

/**
 * Scene — Stat Card. ONE card, centred, on the near-empty ground.
 *
 * The composition is deliberately the KPI hero's cousin rather than a copy: the
 * hero makes the number the whole frame, and a stat card puts the same number on
 * a surface with a label and a mark — the "data card" the reference names. The
 * card also counts up its number, because a static card beside a count-up hero
 * would read as a different film.
 */
export const StatCard: React.FC<{scene: Scene}> = ({scene}) => {
  const {MOTION} = useDesign();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = scaleFor(comp.width, comp.height);
  const c = (scene.content ?? {}) as Record<string, unknown>;
  const layout = (scene.layout ?? {}) as Record<string, unknown>;

  const cardW = numOr(layout.cardWidth, 720) * s;
  const cardH = numOr(layout.cardHeight, 420) * s;

  const enter = spring({
    frame,
    fps: comp.fps,
    config: MOTION.springs.settle,
    durationInFrames: Math.round(MOTION.enterSeconds * comp.fps),
  });
  const draw = interpolate(
    frame,
    [Math.round(MOTION.enterSeconds * comp.fps), Math.round((MOTION.enterSeconds + 0.9) * comp.fps)],
    [0, 1],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );

  return (
    <CameraRig camera={scene.camera} motion={scene.motion} durationInFrames={scene.durationInFrames}>
      <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
        <Card c={c as CardContent} s={s} progress={enter} width={cardW} height={cardH} sparkDraw={draw} />
      </div>
    </CameraRig>
  );
};

/**
 * Scene — Card Grid. N cards in a matrix — the reference's "窗口墙" / card wall.
 *
 * The grid is the composition and the stagger is the motion: cards arrive in
 * reading order on the profile's stagger, so the wall assembles rather than
 * pops. One card may be emphasised (`accent: true` in its content), and it is
 * the only accent on screen — "colour carries meaning only" (options.ts).
 *
 * The layout comes from the graph (`layout.columns`) with a default, so a
 * 6-card wall and a 16-card wall are the same renderer.
 */
export const CardGrid: React.FC<{scene: Scene}> = ({scene}) => {
  const {MOTION, SPACE} = useDesign();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = scaleFor(comp.width, comp.height);
  const c = (scene.content ?? {}) as Record<string, unknown>;
  const layout = (scene.layout ?? {}) as Record<string, unknown>;
  const motion = scene.motion;

  const cards = (Array.isArray(c.cards) ? c.cards : []) as CardContent[];
  const columns = Math.max(1, Math.round(numOr(layout.columns, Math.min(cards.length, 3) || 1)));
  // Card width: the graph may pin it; otherwise it is the width that fits
  // `columns` cards inside the frame's own margins, so the wall is centred by
  // construction rather than by a number someone tuned. `SPACE.xl` (64) is the
  // frame margin — the ladder's top READ rung, deliberately, so this renderer
  // neither consumes a reserved rung nor invents a spacing number.
  const cardW = layout.cardWidth !== undefined
    ? numOr(layout.cardWidth, 360) * s
    : Math.min(520 * s, (comp.width - 2 * SPACE.xl * s - (columns - 1) * SPACE.lg * s) / columns);
  const cardH = numOr(layout.cardHeight, 240) * s;
  const stagger = Number(motion?.stagger ?? MOTION.staggerDefault);
  const gap = SPACE.lg * s;

  return (
    <CameraRig camera={scene.camera} motion={motion} durationInFrames={scene.durationInFrames}>
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
            display: 'grid',
            gridTemplateColumns: `repeat(${columns}, ${cardW}px)`,
            gap,
          }}
        >
          {cards.map((card, i) => {
            const enter = spring({
              frame: frame - i * stagger * comp.fps,
              fps: comp.fps,
              config: MOTION.springs.reveal,
            });
            const draw = interpolate(
              frame - i * stagger * comp.fps,
              [Math.round(0.4 * comp.fps), Math.round(1.3 * comp.fps)],
              [0, 1],
              {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
            );
            return (
              <Card
                key={i}
                c={card}
                s={s}
                progress={enter}
                width={cardW}
                height={cardH}
                emphasised={card.accent === true}
                sparkDraw={draw}
              />
            );
          })}
        </div>
      </div>
    </CameraRig>
  );
};
