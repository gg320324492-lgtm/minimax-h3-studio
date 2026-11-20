import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import {COLORS, EASE, FONTS, PAD} from '../theme';
import {Panel, Tag} from '../common/ui';

const STEPS = [
  {cn: '理解', en: 'READ', desc: '把上下文整个读进来：仓库、报错、文档、历史。'},
  {cn: '计划', en: 'PLAN', desc: '拆成可验证的小步，先想清楚再动手。'},
  {cn: '验证', en: 'VERIFY', desc: '跑一遍、测一遍、看输出，不合格就改到合格。'},
];

/** 场景 4 —— 我怎么做事：理解 → 计划 → 验证。 */
export const LoopScene: React.FC = () => {
  const frame = useCurrentFrame();

  const line = interpolate(frame, [6, 70], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(...EASE.out),
  });
  const dot = (frame % 46) / 46;

  return (
    <AbsoluteFill style={{padding: PAD, justifyContent: 'center'}}>
      <div style={{display: 'flex', flexDirection: 'column', gap: 68}}>
        <Tag>HOW I WORK</Tag>

        <div style={{display: 'flex', alignItems: 'stretch', gap: 0, position: 'relative'}}>
          {/* 连接轨道：三列等宽 576，列宽一半即圆心 288；圆高 118，圆心在 59 */}
          <div
            style={{
              position: 'absolute',
              top: 58,
              left: 288,
              right: 288,
              height: 2,
              background: `linear-gradient(90deg, ${COLORS.border}, ${COLORS.border})`,
            }}
          >
            <div
              style={{
                width: `${line * 100}%`,
                height: '100%',
                background: `linear-gradient(90deg, ${COLORS.accent}, ${COLORS.accent2})`,
                boxShadow: `0 0 12px ${COLORS.accent}`,
              }}
            />
            {line > 0.02 ? (
              <div
                style={{
                  position: 'absolute',
                  left: `${dot * 100}%`,
                  top: -4,
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  background: '#FFFFFF',
                  boxShadow: `0 0 18px 3px ${COLORS.accent}`,
                }}
              />
            ) : null}
          </div>

          {STEPS.map((s, i) => {
            const start = 10 + i * 22;
            const t = interpolate(frame, [start, start + 26], [0, 1], {
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
              easing: Easing.bezier(...EASE.out),
            });
            const scale = interpolate(t, [0, 1], [0.86, 1]);
            const active = frame >= start && frame < start + 22;
            const ring = active ? 0.55 + 0.45 * Math.sin(frame / 5) : 0.35;
            return (
              <div
                key={s.en}
                style={{
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 26,
                  opacity: t,
                }}
              >
                <div
                  style={{
                    width: 118,
                    height: 118,
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontFamily: FONTS.mono,
                    fontSize: 32,
                    fontWeight: 700,
                    letterSpacing: 2,
                    color: COLORS.ink,
                    background: COLORS.panelSolid,
                    border: `1.5px solid ${COLORS.borderStrong}`,
                    boxShadow: `0 0 ${16 + ring * 30}px rgba(92,225,255,${0.1 + ring * 0.25})`,
                    scale,
                  }}
                >
                  {i + 1}
                </div>
                <div style={{textAlign: 'center'}}>
                  <div
                    style={{
                      fontFamily: FONTS.sans,
                      fontSize: 46,
                      fontWeight: 600,
                      letterSpacing: 8,
                      color: COLORS.ink,
                    }}
                  >
                    {s.cn}
                  </div>
                  <div
                    style={{
                      marginTop: 6,
                      fontFamily: FONTS.mono,
                      fontSize: 18,
                      letterSpacing: 5,
                      color: COLORS.accent,
                    }}
                  >
                    {s.en}
                  </div>
                </div>
                <Panel style={{padding: '16px 22px', maxWidth: 380}}>
                  <div
                    style={{
                      fontFamily: FONTS.sans,
                      fontSize: 23,
                      lineHeight: 1.6,
                      color: COLORS.dim,
                      letterSpacing: 1,
                    }}
                  >
                    {s.desc}
                  </div>
                </Panel>
              </div>
            );
          })}
        </div>

        <div
          style={{
            fontFamily: FONTS.sans,
            fontSize: 27,
            color: COLORS.dim,
            letterSpacing: 3,
            opacity: interpolate(frame, [86, 104], [0, 1], {
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
              easing: Easing.bezier(...EASE.out),
            }),
          }}
        >
          循环往复，直到结果站得住。
        </div>
      </div>
    </AbsoluteFill>
  );
};
