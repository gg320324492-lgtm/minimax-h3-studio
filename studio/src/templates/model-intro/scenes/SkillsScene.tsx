import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import {COLORS, EASE, FONTS, PAD} from '../theme';
import {Panel, Tag} from '../common/ui';

const SKILLS = [
  {cn: '读代码', en: 'READ', desc: '一次读完整个仓库', icon: 'code'},
  {cn: '写代码', en: 'WRITE', desc: '新功能、重构、修 bug', icon: 'pen'},
  {cn: '查资料', en: 'RESEARCH', desc: '检索、核实、带出处', icon: 'search'},
  {cn: '跑工具', en: 'TOOLS', desc: '终端、MCP、后台任务', icon: 'terminal'},
  {cn: '做推理', en: 'REASON', desc: '分解问题，规划步骤', icon: 'graph'},
  {cn: '出成片', en: 'SHIP', desc: '从一句话到一支视频', icon: 'film'},
];

const Icon: React.FC<{kind: string; color: string}> = ({kind, color}) => {
  const common = {stroke: color, strokeWidth: 2, fill: 'none', strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const};
  if (kind === 'code') {
    return (
      <svg width="42" height="42" viewBox="0 0 34 34">
        <path d="M12 9 L4 17 L12 25" {...common} />
        <path d="M22 9 L30 17 L22 25" {...common} />
        <path d="M19 7 L15 27" {...common} />
      </svg>
    );
  }
  if (kind === 'pen') {
    return (
      <svg width="42" height="42" viewBox="0 0 34 34">
        <path d="M6 28 L9 20 L23 6 L28 11 L14 25 Z" {...common} />
        <path d="M21 8 L26 13" {...common} />
      </svg>
    );
  }
  if (kind === 'search') {
    return (
      <svg width="42" height="42" viewBox="0 0 34 34">
        <circle cx="15" cy="15" r="8" {...common} />
        <path d="M21 21 L29 29" {...common} />
      </svg>
    );
  }
  if (kind === 'terminal') {
    return (
      <svg width="42" height="42" viewBox="0 0 34 34">
        <rect x="4" y="6" width="26" height="22" rx="3" {...common} />
        <path d="M10 14 L15 18 L10 22" {...common} />
        <path d="M19 23 L25 23" {...common} />
      </svg>
    );
  }
  if (kind === 'graph') {
    return (
      <svg width="42" height="42" viewBox="0 0 34 34">
        <circle cx="17" cy="7" r="3.4" {...common} />
        <circle cx="8" cy="26" r="3.4" {...common} />
        <circle cx="26" cy="26" r="3.4" {...common} />
        <path d="M17 10.5 L8.6 22.8 M17 10.5 L25.4 22.8" {...common} />
      </svg>
    );
  }
  return (
    <svg width="42" height="42" viewBox="0 0 34 34">
      <rect x="4" y="7" width="26" height="20" rx="3" {...common} />
      <path d="M4 14 L30 14" {...common} />
      <path d="M11 20 L15 24 L23 18" {...common} />
    </svg>
  );
};

/** 场景 5 —— 我能干什么：六张能力卡。 */
export const SkillsScene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill style={{padding: PAD, justifyContent: 'center'}}>
      <div style={{display: 'flex', flexDirection: 'column', gap: 40}}>
        <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}>
          <Tag>WHAT I DO</Tag>
          <div
            style={{
              fontFamily: FONTS.mono,
              fontSize: 18,
              letterSpacing: 3,
              color: COLORS.faint,
              opacity: interpolate(frame, [10, 34], [0, 1], {
                extrapolateLeft: 'clamp',
                extrapolateRight: 'clamp',
                easing: Easing.bezier(...EASE.out),
              }),
            }}
          >
            SIX VERBS · ONE MODEL
          </div>
        </div>

        <div style={{display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 30}}>
          {SKILLS.map((s, i) => {
            const start = 12 + i * 9;
            const t = interpolate(frame, [start, start + 24], [0, 1], {
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
              easing: Easing.bezier(...EASE.out),
            });
            const hover = 1 + 0.012 * Math.sin((frame - start) / 9);
            return (
              <div key={s.en} style={{opacity: t, translate: `0 ${interpolate(t, [0, 1], [24, 0])}px`}}>
                <Panel
                  style={{
                    padding: '30px 28px',
                    minHeight: 138,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 22,
                    scale: hover,
                  }}
                >
                  <div
                    style={{
                      width: 78,
                      height: 78,
                      borderRadius: 16,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'rgba(92,225,255,0.07)',
                      border: `1px solid ${COLORS.border}`,
                    }}
                  >
                    <Icon kind={s.icon} color={COLORS.accent} />
                  </div>
                  <div style={{display: 'flex', flexDirection: 'column', gap: 5}}>
                    <div style={{display: 'flex', alignItems: 'baseline', gap: 12}}>
                      <span style={{fontFamily: FONTS.sans, fontSize: 34, fontWeight: 600, color: COLORS.ink, letterSpacing: 2}}>
                        {s.cn}
                      </span>
                      <span style={{fontFamily: FONTS.mono, fontSize: 15, letterSpacing: 3, color: COLORS.dim}}>
                        {s.en}
                      </span>
                    </div>
                    <span style={{fontFamily: FONTS.sans, fontSize: 22, color: COLORS.dim, letterSpacing: 1}}>
                      {s.desc}
                    </span>
                  </div>
                </Panel>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
