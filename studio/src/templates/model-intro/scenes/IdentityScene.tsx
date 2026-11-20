import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import {COLORS, EASE, FONTS, PAD} from '../theme';
import {Panel, Tag} from '../common/ui';

/** 场景 2 —— 我是什么：没有身体，只有文本进出。 */
export const IdentityScene: React.FC = () => {
  const frame = useCurrentFrame();

  const reveal = interpolate(frame, [8, 62], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(...EASE.out),
  });
  const facts = [
    {k: '没有摄像头', v: 'NO CAMERA'},
    {k: '没有身体', v: 'NO BODY'},
    {k: '只有文本进出', v: 'TEXT IN / TEXT OUT'},
  ];
  const flow = interpolate(frame, [54, 76], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(...EASE.out),
  });
  const pulse = 0.5 + 0.5 * Math.sin(frame / 7);

  return (
    <AbsoluteFill style={{padding: PAD, justifyContent: 'center'}}>
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 44}}>
        {/* 被逐笔点亮的型号名 */}
        <div style={{position: 'relative', height: 210, display: 'flex', alignItems: 'center'}}>
          <div
            style={{
              position: 'absolute',
              fontFamily: FONTS.mono,
              fontSize: 186,
              fontWeight: 700,
              letterSpacing: 16,
              color: 'transparent',
              WebkitTextStroke: `1.5px ${COLORS.dim}`,
              whiteSpace: 'nowrap',
            }}
          >
            M3.1
          </div>
          <div
            style={{
              position: 'absolute',
              fontFamily: FONTS.mono,
              fontSize: 186,
              fontWeight: 700,
              letterSpacing: 16,
              color: COLORS.accent,
              whiteSpace: 'nowrap',
              clipPath: `inset(0 ${100 - reveal * 100}% 0 0)`,
              textShadow: `0 0 46px rgba(92,225,255,0.42)`,
            }}
          >
            M3.1
          </div>
        </div>

        <div style={{display: 'flex', gap: 22}}>
          {facts.map((f, i) => {
            const t = interpolate(frame, [24 + i * 11, 48 + i * 11], [0, 1], {
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
              easing: Easing.bezier(...EASE.out),
            });
            return (
              <div
                key={f.v}
                style={{
                  opacity: t,
                  translate: `0 ${interpolate(t, [0, 1], [18, 0])}px`,
                }}
              >
                <Panel style={{padding: '18px 26px', minWidth: 300}}>
                  <div style={{fontFamily: FONTS.sans, fontSize: 27, color: COLORS.ink, letterSpacing: 2}}>
                    {f.k}
                  </div>
                  <div
                    style={{
                      marginTop: 8,
                      fontFamily: FONTS.mono,
                      fontSize: 15,
                      letterSpacing: 2,
                      color: COLORS.dim,
                    }}
                  >
                    {f.v}
                  </div>
                </Panel>
              </div>
            );
          })}
        </div>

        {/* 数据流示意：文本进 → 模型 → 文本出 */}
        <div style={{opacity: flow, display: 'flex', alignItems: 'center', gap: 26, marginTop: 6}}>
          <Tag>INPUT</Tag>
          <div
            style={{
              width: 190,
              height: 3,
              background: `linear-gradient(90deg, ${COLORS.faint}, ${COLORS.accent})`,
            }}
          />
          <div
            style={{
              width: 92,
              height: 92,
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontFamily: FONTS.mono,
              fontSize: 19,
              letterSpacing: 1,
              color: COLORS.accent,
              background: `radial-gradient(circle, rgba(92,225,255,${0.1 + pulse * 0.14}) 0%, transparent 72%)`,
              border: `1px solid ${COLORS.borderStrong}`,
              boxShadow: `0 0 ${18 + pulse * 26}px rgba(92,225,255,${0.16 + pulse * 0.22})`,
            }}
          >
            M3.1
          </div>
          <div
            style={{
              width: 190,
              height: 3,
              background: `linear-gradient(90deg, ${COLORS.accent}, ${COLORS.faint})`,
            }}
          />
          <Tag color={COLORS.accent2}>OUTPUT</Tag>
        </div>
      </div>
    </AbsoluteFill>
  );
};
