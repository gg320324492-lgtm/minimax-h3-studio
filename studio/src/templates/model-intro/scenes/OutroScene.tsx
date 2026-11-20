import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import {COLORS, EASE, FONTS, PAD} from '../theme';
import {Panel, Tag} from '../common/ui';

/** 场景 7 —— 收尾：这句话就是这支片子的全部意义。 */
export const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();

  const line1 = interpolate(frame, [8, 44], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(...EASE.out),
  });
  const line2 = interpolate(frame, [40, 76], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(...EASE.out),
  });
  const sign = interpolate(frame, [72, 96], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(...EASE.out),
  });
  const rule = interpolate(frame, [68, 92], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(...EASE.out),
  });

  return (
    <AbsoluteFill style={{padding: PAD, justifyContent: 'center', alignItems: 'center'}}>
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18}}>
        <div
          style={{
            fontFamily: FONTS.sans,
            fontSize: 82,
            fontWeight: 600,
            letterSpacing: 6,
            color: COLORS.ink,
            opacity: line1,
            translate: `0 ${interpolate(line1, [0, 1], [26, 0])}px`,
          }}
        >
          画面不是我画出来的，
        </div>
        <div
          style={{
            fontFamily: FONTS.sans,
            fontSize: 82,
            fontWeight: 700,
            letterSpacing: 6,
            color: COLORS.ink,
            opacity: line2,
            translate: `0 ${interpolate(line2, [0, 1], [26, 0])}px`,
          }}
        >
          是<span style={{color: COLORS.accent, textShadow: '0 0 38px rgba(92,225,255,0.4)'}}>代码</span>画出来的。
        </div>

        <div
          style={{
            width: 560 * rule,
            height: 1,
            marginTop: 26,
            background: `linear-gradient(90deg, transparent, ${COLORS.borderStrong}, transparent)`,
          }}
        />

        <div style={{opacity: sign, marginTop: 16}}>
          <Panel style={{padding: '20px 40px', display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'center'}}>
            <div style={{fontFamily: FONTS.mono, fontSize: 30, letterSpacing: 6, color: COLORS.accent}}>
              MiniMax M3.1
            </div>
            <div style={{fontFamily: FONTS.sans, fontSize: 24, letterSpacing: 3, color: COLORS.ink}}>
              本地运行 · 纯模型能力
            </div>
          </Panel>
        </div>

        <div
          style={{
            marginTop: 22,
            fontFamily: FONTS.mono,
            fontSize: 17,
            letterSpacing: 3,
            color: COLORS.faint,
            opacity: sign,
          }}
        >
          E:\Minimax-H3 · 由 Remotion 渲染 · 本片调用视频生成模型 0 次
        </div>
      </div>

      <div
        style={{
          position: 'absolute',
          bottom: PAD * 0.55,
          right: PAD * 0.5,
          opacity: sign * 0.85,
        }}
      >
        <Tag color={COLORS.faint}>07 / 07</Tag>
      </div>
    </AbsoluteFill>
  );
};
