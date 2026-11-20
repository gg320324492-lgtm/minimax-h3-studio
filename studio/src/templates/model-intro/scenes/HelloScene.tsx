import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import {COLORS, EASE, FONTS, PAD} from '../theme';
import {Typewriter} from '../common/ui';

/** 场景 1 —— 自我介绍的开场：一片黑里只有两行字。 */
export const HelloScene: React.FC = () => {
  const frame = useCurrentFrame();

  const intro = interpolate(frame, [0, 26], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(...EASE.out),
  });
  const nameIn = interpolate(frame, [46, 74], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(...EASE.out),
  });
  const metaIn = interpolate(frame, [76, 98], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(...EASE.out),
  });
  const rule = interpolate(frame, [10, 80], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(...EASE.out),
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'center',
        alignItems: 'center',
        opacity: intro,
      }}
    >
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 34}}>
        <div
          style={{
            fontFamily: FONTS.sans,
            fontSize: 118,
            fontWeight: 700,
            letterSpacing: 10,
            color: COLORS.ink,
            lineHeight: 1.1,
          }}
        >
          <Typewriter text="你好。" framesPerChar={4} startFrame={12} cursor style={{whiteSpace: 'pre'}} />
        </div>

        <div
          style={{
            width: 720 * rule,
            height: 1,
            background: `linear-gradient(90deg, transparent, ${COLORS.borderStrong}, transparent)`,
          }}
        />

        <div
          style={{
            fontFamily: FONTS.sans,
            fontSize: 62,
            fontWeight: 300,
            letterSpacing: 6,
            color: COLORS.accent,
            opacity: nameIn,
            translate: `0 ${interpolate(frame, [46, 74], [22, 0], {
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
              easing: Easing.bezier(...EASE.out),
            })}px`,
          }}
        >
          我是 MiniMax M3.1
        </div>

        <div
          style={{
            fontFamily: FONTS.mono,
            fontSize: 22,
            letterSpacing: 4,
            color: COLORS.dim,
            opacity: metaIn,
            marginTop: 8,
          }}
        >
          本地运行 · 无视频生成模型 · E:\Minimax-H3
        </div>
      </div>

      <div
        style={{
          position: 'absolute',
          bottom: PAD * 0.55,
          right: PAD * 0.5,
          fontFamily: FONTS.mono,
          fontSize: 17,
          letterSpacing: 3,
          color: COLORS.faint,
          opacity: metaIn * 0.9,
        }}
      >
        00 / 07
      </div>
    </AbsoluteFill>
  );
};
