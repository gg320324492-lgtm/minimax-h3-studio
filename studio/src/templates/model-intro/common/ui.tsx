import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {Audio} from '@remotion/media';
import {COLORS, EASE, FONTS, PAD} from '../theme';

/** 统一的淡入淡出包：场景切换时前后各留 14 帧呼吸，避免生硬。 */
export const Fade: React.FC<{
  children: React.ReactNode;
  inFrames?: number;
  outFrames?: number;
  /** 场景帧数（等于所在 Sequence 的时长）；显式传入，方便换算叠化窗口。 */
  durationFrames: number;
}> = ({children, inFrames = 14, outFrames = 14, durationFrames}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(
    frame,
    [0, inFrames, Math.max(inFrames + 1, durationFrames - outFrames), durationFrames],
    [0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.linear},
  );
  return <AbsoluteFill style={{opacity}}>{children}</AbsoluteFill>;
};

/** 逐字显现的打字机。中文按字，英文按字符，速度由 framesPerChar 控制。 */
export const Typewriter: React.FC<{
  text: string;
  framesPerChar?: number;
  startFrame?: number;
  cursor?: boolean;
  style?: React.CSSProperties;
}> = ({text, framesPerChar = 2, startFrame = 0, cursor = false, style}) => {
  const frame = useCurrentFrame();
  const shown = Math.max(0, Math.floor((frame - startFrame) / framesPerChar));
  const visible = text.slice(0, Math.min(text.length, shown));
  const done = shown >= text.length;
  const blink = Math.floor(frame / 12) % 2 === 0;
  return (
    <span style={style}>
      {visible}
      {cursor && frame >= startFrame && !done && blink ? <span style={{opacity: 0.85}}>▍</span> : null}
    </span>
  );
};

/** 背景层：网格 + 双色光晕 + 噪点 + 暗角。所有场景共用。 */
export const Backdrop: React.FC<{intensity?: number}> = ({intensity = 1}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const breathe = 0.82 + 0.18 * Math.sin(frame / 42);
  const sweep = interpolate(frame % (durationInFrames / 2), [0, durationInFrames / 2], [-30, 130]);
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.bg}}>
      <AbsoluteFill
        style={{
          backgroundImage: `linear-gradient(${sweep}deg, transparent 42%, rgba(92,225,255,0.05) 50%, transparent 58%)`,
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage: `
            radial-gradient(760px 520px at 22% 18%, rgba(92,225,255,0.13), transparent 70%),
            radial-gradient(680px 520px at 84% 82%, rgba(167,139,250,0.12), transparent 72%)
          `,
          opacity: intensity * breathe,
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.028) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.028) 1px, transparent 1px)`,
          backgroundSize: '64px 64px',
          maskImage: 'radial-gradient(120% 100% at 50% 45%, #000 30%, transparent 88%)',
          WebkitMaskImage: 'radial-gradient(120% 100% at 50% 45%, #000 30%, transparent 88%)',
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage: `url("data:image/svg+xml;utf8,${encodeURIComponent(
            '<svg xmlns="http://www.w3.org/2000/svg" width="220" height="220"><filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="3"/></filter><rect width="220" height="220" filter="url(#n)" opacity="0.42"/></svg>',
          )}")`,
          opacity: 0.05,
          mixBlendMode: 'overlay',
        }}
      />
      <AbsoluteFill
        style={{
          background: 'radial-gradient(115% 88% at 50% 45%, transparent 52%, rgba(2,4,10,0.82) 100%)',
        }}
      />
    </AbsoluteFill>
  );
};

/** 顶部/左侧的工程仪表：进度线 + 当前段落名 + 帧计数。 */
export const Hud: React.FC<{label: string; totalFrames: number}> = ({label, totalFrames}) => {
  const frame = useCurrentFrame();
  const progress = totalFrames > 0 ? frame / totalFrames : 0;
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          height: 2,
          width: '100%',
          background: 'rgba(255,255,255,0.05)',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${Math.min(100, progress * 100)}%`,
            background: `linear-gradient(90deg, ${COLORS.accent}, ${COLORS.accent2})`,
            boxShadow: `0 0 14px ${COLORS.accent}`,
          }}
        />
      </div>
      <div
        style={{
          position: 'absolute',
          top: PAD * 0.42,
          right: PAD * 0.5,
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          fontFamily: FONTS.mono,
          fontSize: 17,
          letterSpacing: 2,
          color: COLORS.faint,
        }}
      >
        <span style={{color: COLORS.accent}}>M3.1</span>
        <span>·</span>
        <span>LOCAL</span>
        <span>·</span>
        <span>NO-VIDEO-GEN</span>
      </div>
      <div
        style={{
          position: 'absolute',
          left: PAD * 0.5,
          top: PAD * 0.42,
          fontFamily: FONTS.mono,
          fontSize: 17,
          letterSpacing: 3,
          color: COLORS.faint,
        }}
      >
        {label}
      </div>
    </AbsoluteFill>
  );
};

/**
 * 底部字幕条：跟随当前旁白段落。
 * 由顶层 Sequence 承载（useCurrentFrame 是本场相对帧），前 10 帧淡入，
 * fadeOut 为真时在段末 8 帧淡出，叠化窗口里不会同时出现两条字幕。
 */
export const CaptionBar: React.FC<{text: string; fadeOut?: boolean}> = ({text, fadeOut = false}) => {
  const frame = useCurrentFrame();
  // Sequence 内 useVideoConfig() 拿到的是本 Sequence 的时长，正好是字幕窗口长度。
  const {durationInFrames} = useVideoConfig();
  const fadeIn = interpolate(frame, [0, 10], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(...EASE.out),
  });
  const fadeOutT = fadeOut
    ? interpolate(frame, [Math.max(0, durationInFrames - 8), durationInFrames], [1, 0], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.linear,
      })
    : 1;
  const opacity = Math.min(fadeIn, fadeOutT);
  const translate = interpolate(frame, [0, 10], [14, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(...EASE.out),
  });
  if (!text) {
    return null;
  }
  return (
    <div
      style={{
        position: 'absolute',
        bottom: 58,
        left: '50%',
        translate: `-50% ${translate}px`,
        opacity,
        // left:50% + 绝对定位下，宽度默认被右侧可用空间（960px）卡住，
        // 长字幕会折成两行、末行只剩几个字。改用 max-content 让字幕单行铺开。
        width: 'max-content',
        maxWidth: 1420,
        padding: '16px 30px',
        borderRadius: 14,
        background: 'rgba(4,7,14,0.62)',
        border: `1px solid ${COLORS.border}`,
        backdropFilter: 'blur(9px)',
        fontFamily: FONTS.sans,
        fontSize: 31,
        lineHeight: 1.45,
        letterSpacing: 0.6,
        color: COLORS.ink,
        textAlign: 'center',
        whiteSpace: 'pre-wrap',
      }}
    >
      {text}
    </div>
  );
};

/**
 * 转场闪白：叠化窗口里新旧两场的文字会短暂同时在场（看着像重影）。
 * 用一记极淡的冷白脉冲盖住那一瞬，读起来就是一次快闪切换。
 */
export const TransitionFlash: React.FC<{peak?: number}> = ({peak = 0.16}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 3, 9], [0, peak, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.linear,
  });
  return (
    <AbsoluteFill style={{background: `rgba(226, 245, 255, ${opacity})`, pointerEvents: 'none'}} />
  );
};

/** 半透明面板：技术图纸质感。 */
export const Panel: React.FC<{
  children: React.ReactNode;
  style?: React.CSSProperties;
  accent?: string;
}> = ({children, style, accent}) => (
  <div
    style={{
      background: COLORS.panel,
      border: `1px solid ${COLORS.border}`,
      borderRadius: 18,
      boxShadow: '0 24px 70px rgba(0,0,0,0.45)',
      ...style,
      borderTopColor: accent ?? COLORS.border,
    }}
  >
    {children}
  </div>
);

/** 小标签（等宽小字 + 左侧竖线）。 */
export const Tag: React.FC<{children: React.ReactNode; color?: string}> = ({children, color}) => (
  <span
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 8,
      fontFamily: FONTS.mono,
      fontSize: 18,
      letterSpacing: 2,
      color: color ?? COLORS.dim,
    }}
  >
    <span style={{width: 3, height: 16, background: color ?? COLORS.accent, display: 'inline-block'}} />
    {children}
  </span>
);

/**
 * 转场音效：场景切换的一记轻 whoosh。
 * 包络约 30 帧 —— 原来的 44 帧（1.8 秒）会拖到下一段语音前面；
 * 素材本身只有 0.55 秒（13 帧），所以实际出声长度由素材决定。
 */
export const Whoosh: React.FC<{volume?: number}> = ({volume = 0.16}) => (
  <Audio
    src={staticFile('audio/_whoosh.m4a')}
    volume={(f) => {
      const v = interpolate(f, [0, 5, 14, 30], [0, 1, 0.3, 0], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      });
      return v * volume;
    }}
  />
);
