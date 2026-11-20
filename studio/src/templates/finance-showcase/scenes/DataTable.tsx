import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Scene} from '../../../schemas/showcase-v1';
import {CameraRig} from '../common/CameraRig';
// Fonts and scaling are NOT theme-scoped, so importing them is correct.
// Everything that IS theme-scoped (palette, type, spacing, shadow) must come
// from useDesign() — see tests/test_showcase_schema_parity.py::test_scenes_do_not_import_design_values_directly
import {FONT_NUM, FONT_SANS, scaleFor} from '../design/tokens';
import {useDesign} from '../design/styleBible';

/**
 * Scene — Data Table (reference film: "表格矩阵").
 *
 * The master plan puts "表格" (tables) on the Remotion side explicitly —
 * "文字、数字、表格、UI 绝不交给 H3 生成，必须程序化渲染" — and the type has been
 * declared since P3 with no renderer. Before P26 a graph asking for a table got
 * `MissingScene` ("not implemented in P4") for its whole duration.
 *
 * A TABLE IS NOT A CHART. `DataColumns` and the chart engine draw MARKS whose
 * position encodes magnitude; a table draws ALIGNED TEXT whose COLUMN does. That
 * is why this is its own renderer and not a chart type: the moment a bar is
 * asked to align a column of numbers, one of the two jobs wins and the other is
 * wrong. The reference language for it is "colour carries meaning only" plus
 * direct labelling, so:
 *
 *   - the header is a row of annotations, separated by a hairline, not a band;
 *   - the number column is right-aligned in the NUMERIC table role, so digits
 *     line up and a value changing under a repair cannot reflow the column —
 *     this is the role `tokens.ts` says exists precisely because "a headline
 *     figure and a figure in a table are the same NUMBER but different
 *     typography";
 *   - rows arrive on a stagger, which is the only motion a table wants.
 *
 * The graph supplies columns and rows; the roles, the hairlines and the stagger
 * are the design system's. A renderer that printed `content` would have none of
 * them.
 */

type Column = {
  key?: unknown;
  label?: unknown;
  /** 'num' right-aligns and uses the numeric face; anything else is left/sans */
  align?: unknown;
  /** 'text' | 'num' | 'delta' — delta colours by sign */
  kind?: unknown;
};

type Row = Record<string, unknown> & {label?: unknown; _accent?: unknown};

const isNumericKind = (col: Column): boolean =>
  col.kind === 'num' || col.kind === 'delta' || col.align === 'right';

const signed = (v: unknown): boolean => !String(v ?? '').trim().startsWith('-');

export const DataTable: React.FC<{scene: Scene}> = ({scene}) => {
  const {MOTION, PALETTE, SHADOW, SPACE, TYPE, RADIUS} = useDesign();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = scaleFor(comp.width, comp.height);
  const c = (scene.content ?? {}) as Record<string, unknown>;
  const layout = (scene.layout ?? {}) as Record<string, unknown>;
  const motion = scene.motion;

  const columns: Column[] = Array.isArray(c.columns) ? (c.columns as Column[]) : [];
  const rows: Row[] = Array.isArray(c.rows) ? (c.rows as Row[]) : [];
  const caption = c.caption !== undefined ? String(c.caption) : '';
  const stagger = Number(motion?.stagger ?? MOTION.staggerDefault);
  const rowH = Number(layout.rowHeight ?? 64) * s;
  const padX = Number(layout.padX ?? 44) * s;

  const enter = spring({
    frame,
    fps: comp.fps,
    config: MOTION.springs.settle,
    durationInFrames: Math.round(MOTION.enterSeconds * comp.fps),
  });

  if (!columns.length || !rows.length) {
    // A table with no columns has nothing to draw and must not look like a
    // design choice — say so on the frame, the way the chart engine does.
    return (
      <CameraRig camera={scene.camera} motion={motion} durationInFrames={scene.durationInFrames}>
        <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
          <div style={{fontFamily: FONT_SANS, fontSize: 34 * s, color: PALETTE.accent}}>table: no columns</div>
        </div>
      </CameraRig>
    );
  }

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
          padding: `0 ${SPACE.xl * 2 * s}px`,
          opacity: enter,
        }}
      >
        {caption ? (
          <div
            style={{
              alignSelf: 'flex-start',
              fontFamily: FONT_SANS,
              fontSize: TYPE.subheading.size * s,
              fontWeight: 600,
              color: PALETTE.ink,
              marginBottom: SPACE.lg * s,
              letterSpacing: '-0.01em',
            }}
          >
            {caption}
          </div>
        ) : null}

        <div
          style={{
            width: '100%',
            background: PALETTE.surface,
            border: `1px solid ${PALETTE.hairline}`,
            borderRadius: RADIUS.card * s,
            boxShadow: SHADOW.medium,
            overflow: 'hidden',
            padding: `0 ${padX}px`,
          }}
        >
          {/* header — annotations on a hairline, not a band */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              height: rowH,
              borderBottom: `1px solid ${PALETTE.hairline}`,
            }}
          >
            {columns.map((col, ci) => (
              <div
                key={ci}
                style={{
                  flex: isNumericKind(col) ? '0 0 240px' : 1,
                  textAlign: isNumericKind(col) ? 'right' : 'left',
                  fontFamily: FONT_SANS,
                  fontSize: TYPE.annotation.size * s,
                  fontWeight: 500,
                  letterSpacing: TYPE.annotation.tracking,
                  textTransform: 'uppercase',
                  color: PALETTE.inkMuted,
                  paddingRight: isNumericKind(col) ? 8 * s : 0,
                }}
              >
                {col.label !== undefined ? String(col.label) : ''}
              </div>
            ))}
          </div>

          {/* rows */}
          {rows.map((row, ri) => {
            const local = spring({
              frame: frame - ri * stagger * comp.fps,
              fps: comp.fps,
              config: MOTION.springs.reveal,
            });
            const emphasised = row._accent === true;
            return (
              <div
                key={ri}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  height: rowH,
                  borderBottom: ri === rows.length - 1 ? 'none' : `1px solid ${PALETTE.grid}`,
                  opacity: local,
                  transform: `translateX(${(1 - local) * 20 * s}px)`,
                }}
              >
                {columns.map((col, ci) => {
                  const raw = row[String(col.key ?? '')];
                  const numeric = isNumericKind(col);
                  const isDelta = col.kind === 'delta';
                  const color = emphasised
                    ? PALETTE.accent
                    : isDelta
                      ? signed(raw)
                        ? PALETTE.positive
                        : PALETTE.negative
                      : numeric
                        ? PALETTE.ink
                        : PALETTE.inkMuted;
                  return (
                    <div
                      key={ci}
                      style={{
                        flex: numeric ? '0 0 240px' : 1,
                        textAlign: numeric ? 'right' : 'left',
                        paddingRight: numeric ? 8 * s : 0,
                        fontFamily: numeric ? FONT_NUM : FONT_SANS,
                        fontVariantNumeric: numeric ? 'tabular-nums' : undefined,
                        fontSize: (numeric ? TYPE.numericTable.size * 0.6 : TYPE.body.size * 0.92) * s,
                        fontWeight: numeric ? TYPE.numericTable.weight : ci === 0 ? 600 : 400,
                        letterSpacing: numeric ? TYPE.numericTable.tracking : '0',
                        color: ci === 0 ? (emphasised ? PALETTE.accent : PALETTE.ink) : color,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {raw !== undefined && raw !== null ? String(raw) : ''}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>

        {/* one accent rule under the table — the same emphasis cue KpiHero uses */}
        <div
          style={{
            alignSelf: 'flex-start',
            marginTop: SPACE.xl * s,
            width: interpolate(enter, [0, 1], [0, 160]) * s,
            height: 4 * s,
            background: PALETTE.accent,
          }}
        />
      </div>
    </CameraRig>
  );
};
