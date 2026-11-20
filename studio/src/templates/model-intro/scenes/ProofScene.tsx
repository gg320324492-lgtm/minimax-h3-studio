import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import {COLORS, EASE, FONTS, PAD} from '../theme';
import {Panel, Tag, Typewriter} from '../common/ui';

const CODE: {text: string; kind: 'kw' | 'str' | 'plain' | 'comment'}[] = [
  {text: 'import {useCurrentFrame, interpolate} from \'remotion\';', kind: 'plain'},
  {text: '', kind: 'plain'},
  {text: '<AbsoluteFill style={{background: \'#05070C\'}}>', kind: 'plain'},
  {text: '  <Sequence from={s.start} durationInFrames={s.dur}>', kind: 'plain'},
  {text: '    <Scene />', kind: 'kw'},
  {text: '  </Sequence>', kind: 'plain'},
  {text: '</AbsoluteFill>', kind: 'plain'},
  {text: '', kind: 'plain'},
  {text: '// 每一帧都由 frame 算出来，没有一张是"生成"出来的', kind: 'comment'},
  {text: 'const t = interpolate(frame, [0, 24], [0, 1],', kind: 'plain'},
  {text: '  {extrapolateRight: \'clamp\',', kind: 'plain'},
  {text: '   easing: Easing.bezier(0.16, 1, 0.3, 1)});', kind: 'plain'},
];

const CODE_COLOR: Record<string, string> = {
  kw: COLORS.accent2,
  str: COLORS.ok,
  plain: COLORS.ink,
  comment: COLORS.faint,
};

/** 场景 6 —— 证据：左边是我写的代码，右边是它渲染出来的画面。 */
export const ProofScene: React.FC<{totalFrames: number}> = ({totalFrames}) => {
  const frame = useCurrentFrame();

  const panel = interpolate(frame, [0, 22], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(...EASE.out),
  });
  // 扫描线走三角波往返，不做取模硬跳。
  const scanPhase = (frame % 90) / 90;
  const scan = scanPhase < 0.5 ? scanPhase * 2 : 2 - scanPhase * 2;

  const facts = [
    {k: '本片调用视频生成模型', v: '0', unit: '次', color: COLORS.ok},
    {k: '画面来源', v: '100%', unit: '代码', color: COLORS.accent},
    {k: '成片帧数', v: String(totalFrames), unit: '帧', color: COLORS.accent2},
  ];

  return (
    <AbsoluteFill style={{padding: PAD, justifyContent: 'center'}}>
      <div style={{display: 'flex', gap: 40, opacity: panel}}>
        {/* 代码 */}
        <Panel style={{flex: 1.18, padding: 0, overflow: 'hidden'}}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '13px 22px',
              borderBottom: `1px solid ${COLORS.border}`,
              background: 'rgba(255,255,255,0.022)',
            }}
          >
            <span style={{fontFamily: FONTS.mono, fontSize: 18, color: COLORS.dim, letterSpacing: 1}}>
              ModelIntro.tsx
            </span>
            <span style={{fontFamily: FONTS.mono, fontSize: 15, letterSpacing: 3, color: COLORS.faint}}>
              written by me
            </span>
          </div>
          <div style={{padding: '24px 26px', display: 'flex', flexDirection: 'column', gap: 9}}>
            {CODE.map((line, i) => {
              const start = 14 + i * 11;
              const base: React.CSSProperties = {
                fontFamily: FONTS.mono,
                fontSize: 20,
                lineHeight: 1.4,
                color: CODE_COLOR[line.kind],
                whiteSpace: 'pre',
                letterSpacing: 0.2,
              };
              // 中文注释逐字打会被截成半行，看着像 bug —— 改成整行淡入。
              if (line.kind === 'comment') {
                const t = interpolate(frame, [start, start + 16], [0, 1], {
                  extrapolateLeft: 'clamp',
                  extrapolateRight: 'clamp',
                  easing: Easing.bezier(...EASE.out),
                });
                return (
                  <div key={i} style={{...base, opacity: t}}>
                    {line.text}
                  </div>
                );
              }
              return (
                <div key={i} style={base}>
                  <Typewriter text={line.text} framesPerChar={0.55} startFrame={start} />
                </div>
              );
            })}
          </div>
        </Panel>

        {/* 渲染结果 */}
        <div style={{flex: 0.82, display: 'flex', flexDirection: 'column', gap: 22}}>
          <Tag>OUTPUT</Tag>
          <Panel style={{padding: 0, overflow: 'hidden', position: 'relative', height: 330}}>
            <div
              style={{
                position: 'absolute',
                inset: 0,
                background: `radial-gradient(560px 320px at 30% 26%, rgba(92,225,255,0.16), transparent 70%), radial-gradient(460px 300px at 76% 80%, rgba(167,139,250,0.15), transparent 72%)`,
              }}
            />
            <div
              style={{
                position: 'absolute',
                inset: 0,
                backgroundImage: `linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px)`,
                backgroundSize: '40px 40px',
              }}
            />
            <div
              style={{
                position: 'absolute',
                left: 0,
                right: 0,
                top: `${scan * 100}%`,
                height: 2,
                background: `linear-gradient(90deg, transparent, ${COLORS.accent}, transparent)`,
                boxShadow: `0 0 16px ${COLORS.accent}`,
              }}
            />
            <div
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 10,
              }}
            >
              <div style={{fontFamily: FONTS.mono, fontSize: 46, fontWeight: 700, color: COLORS.accent, letterSpacing: 8}}>
                M3.1
              </div>
              <div style={{fontFamily: FONTS.mono, fontSize: 16, letterSpacing: 3, color: COLORS.dim}}>
                RENDERED BY CODE
              </div>
            </div>
          </Panel>

          <div style={{display: 'flex', flexDirection: 'column', gap: 14}}>
            {facts.map((f, i) => {
              const start = 52 + i * 12;
              const t = interpolate(frame, [start, start + 24], [0, 1], {
                extrapolateLeft: 'clamp',
                extrapolateRight: 'clamp',
                easing: Easing.bezier(...EASE.out),
              });
              return (
                <Panel
                  key={f.k}
                  style={{
                    padding: '16px 24px',
                    display: 'flex',
                    alignItems: 'baseline',
                    justifyContent: 'space-between',
                    opacity: t,
                  }}
                >
                  <span style={{fontFamily: FONTS.sans, fontSize: 24, color: COLORS.dim, letterSpacing: 1}}>
                    {f.k}
                  </span>
                  <span style={{fontFamily: FONTS.mono, fontSize: 46, fontWeight: 700, color: f.color}}>
                    {f.v}
                    <span style={{fontSize: 22, color: COLORS.faint, marginLeft: 6}}>{f.unit}</span>
                  </span>
                </Panel>
              );
            })}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
