import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import {COLORS, EASE, FONTS, PAD} from '../theme';
import {Panel, Tag, Typewriter} from '../common/ui';

// 画面里的数字全部取自真实仓库状态（拍摄本片时的实测值）：
// studio/src 下 82 个 .ts/.tsx 共 12,763 行；本片新写 11 个文件共 1,596 行；tsc 零报错。
const TERMINAL_LINES: {text: string; dim?: boolean; accent?: boolean}[] = [
  {text: 'PS E:\\Minimax-H3\\studio\\src> ls'},
  {text: '  schemas/   templates/   types/   water-renewal/', dim: true},
  {text: 'PS E:\\Minimax-H3\\studio\\src> read("**/*.tsx")'},
  {text: '  → 82 个源文件 · 12,763 行 · 已扫描', accent: true},
  {text: 'PS E:\\Minimax-H3\\studio\\src> write("templates/model-intro/")'},
  {text: '  → 11 个新文件 · 1,596 行 · tsc 通过', accent: true},
  {text: 'PS E:\\Minimax-H3\\studio\\src> render("ModelIntro")'},
  {text: '  → 1,198 帧 · h264 · 49.9 秒', accent: true},
];

/** 数字滚动（tabular-nums 防抖动）。 */
const CountUp: React.FC<{value: number; start: number; suffix?: string}> = ({value, start, suffix}) => {
  const frame = useCurrentFrame();
  const t = Math.min(1, Math.max(0, (frame - start) / 40));
  const eased = 1 - Math.pow(1 - t, 3);
  const shown = Math.round(value * eased).toLocaleString('en-US');
  return (
    <span style={{fontVariantNumeric: 'tabular-nums'}}>
      {shown}
      {suffix ?? ''}
    </span>
  );
};

/** 场景 3 —— 我住在哪：终端窗口里的一次真实工作。 */
export const RepoScene: React.FC = () => {
  const frame = useCurrentFrame();

  const win = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(...EASE.out),
  });
  const translate = interpolate(frame, [0, 20], [26, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(...EASE.out),
  });

  const stats = [
    {label: '源文件', value: 82, suffix: ' 个'},
    {label: '代码', value: 12763, suffix: ' 行'},
    {label: '本片新写', value: 11, suffix: ' 个'},
    {label: '渲染', value: 1198, suffix: ' 帧'},
  ];

  return (
    <AbsoluteFill style={{padding: PAD, justifyContent: 'center'}}>
      <div
        style={{
          display: 'flex',
          gap: 44,
          alignItems: 'stretch',
          opacity: win,
          translate: `0 ${translate}px`,
        }}
      >
        {/* 终端 */}
        <Panel style={{flex: 1, padding: 0, overflow: 'hidden'}}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '14px 20px',
              borderBottom: `1px solid ${COLORS.border}`,
              background: 'rgba(255,255,255,0.022)',
            }}
          >
            {['#FF5F57', '#FEBC2E', '#28C840'].map((c) => (
              <span key={c} style={{width: 12, height: 12, borderRadius: '50%', background: c, opacity: 0.75}} />
            ))}
            <span
              style={{
                marginLeft: 12,
                fontFamily: FONTS.mono,
                fontSize: 18,
                letterSpacing: 1,
                color: COLORS.dim,
              }}
            >
              powershell — E:\Minimax-H3
            </span>
          </div>
          <div style={{padding: '30px 34px', display: 'flex', flexDirection: 'column', gap: 13}}>
            {TERMINAL_LINES.map((line, i) => (
              <div
                key={line.text}
                style={{
                  fontFamily: FONTS.mono,
                  fontSize: 25,
                  letterSpacing: 0.6,
                  lineHeight: 1.35,
                  color: line.accent ? COLORS.ok : line.dim ? COLORS.dim : COLORS.ink,
                  whiteSpace: 'pre',
                }}
              >
                <Typewriter
                  text={line.text}
                  framesPerChar={0.85}
                  startFrame={16 + i * 18}
                  cursor={i === TERMINAL_LINES.length - 1}
                />
              </div>
            ))}
          </div>
        </Panel>

        {/* 统计 */}
        <div style={{width: 452, display: 'flex', flexDirection: 'column', gap: 18}}>
          <Tag>REPOSITORY</Tag>
          {stats.map((s, i) => {
            const start = 22 + i * 10;
            const t = interpolate(frame, [start, start + 24], [0, 1], {
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
              easing: Easing.bezier(...EASE.out),
            });
            return (
              <div key={s.label} style={{opacity: t, translate: `0 ${interpolate(t, [0, 1], [16, 0])}px`}}>
                <Panel
                  style={{padding: '20px 26px', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between'}}
                  accent={COLORS.border}
                >
                  <span style={{fontFamily: FONTS.sans, fontSize: 25, color: COLORS.dim, letterSpacing: 1}}>
                    {s.label}
                  </span>
                  <span
                    style={{
                      fontFamily: FONTS.mono,
                      fontSize: 40,
                      fontWeight: 700,
                      color: COLORS.accent,
                    }}
                  >
                    <CountUp value={s.value} start={start} suffix={s.suffix} />
                  </span>
                </Panel>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
