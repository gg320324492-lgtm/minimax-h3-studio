import React from 'react';
import {AbsoluteFill, Audio, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {noise2D} from '@remotion/noise';
import {useAudioData, visualizeAudio} from '@remotion/media-utils';
import {
  ReportDataSchema,
  reportDurationSeconds,
  reportSections,
  type ChartSpec,
  type ReportData,
  type Stat,
} from '../../schemas/report-data';
import {EnsureFonts} from '../common/EnsureFonts';

/**
 * report-vertical v2 —— 高张力数据视频（抖音动效语法，参数来自 Phase 5 调研）：
 * - 数字滚动 count-up（45-60f 缓出三次曲线 + tabular-nums 防抖动）
 * - ImpactWrap：punch-in 变焦（1.10×）+ 白闪 3f + 指数衰减震动（±9px/6f）
 * - 逐字 slam 标题（1 帧错峰，scale 1.4→1 back.out）
 * - 卡点量化：分段起点吸附 BPM 拍边界（与合成 BGM 的拍网格零误差对齐）
 * - 柱状图 spring（damping 20 / stiffness 100）+ 7 帧错峰，冠军条金色
 * - 速度线（集中线）+ 暗角冲击 + 标题光扫
 * - 自动音效：分段边界 whoosh(提前 0.18s)+impact，要点 ding，outro 前 riser
 */

const FONT = '"Microsoft YaHei", SimHeiLocal, sans-serif';
const NUM_FONT = '"Bahnschrift", "Segoe UI", "Microsoft YaHei", sans-serif'; // 数字用窄体 + tabular-nums

// ---------- 动效原语 ----------

/** count-up：解析 value 前导数字（如 "48.2亿"→48.2+"亿"），缓出三次曲线 50f */
const AnimatedNumber: React.FC<{value: string; s: number; durationFrames?: number}> = ({
  value,
  s,
  durationFrames = 50,
}) => {
  const frame = useCurrentFrame();
  const m = value.match(/^([\d.,]+)(.*)$/s);
  if (!m) {
    return <span>{value}</span>;
  }
  const target = parseFloat(m[1].replace(/,/g, ''));
  const suffix = m[2] ?? '';
  const decimals = m[1].includes('.') ? m[1].split('.')[1].replace(/,/g, '').length : 0;
  const t = Math.min(frame / durationFrames, 1);
  const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
  const current = target * eased;
  const shown = current.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return (
    <span style={{fontVariantNumeric: 'tabular-nums'}}>
      {shown}
      <span style={{fontSize: 0.55 * s}}>{suffix}</span>
    </span>
  );
};

/** ImpactWrap：punch-in + 白闪 + noise 衰减震动（调研定稿参数） */
const ImpactWrap: React.FC<{children: React.ReactNode; s: number; fps: number}> = ({children, s, fps}) => {
  const frame = useCurrentFrame();
  const punch = spring({frame, fps, config: {damping: 12, stiffness: 160}});
  const scale = 1.1 - 0.1 * punch; // 1.10 → 1.0
  const shakeAmp = 9 * s * Math.exp(-frame / 6); // 指数衰减 6f 常数
  const sx = noise2D('shake-x', frame / 2.5, 0) * shakeAmp; // simplex 噪声：比正弦更"脏"更自然
  const sy = noise2D('shake-y', frame / 2.5, 100) * shakeAmp * 0.6;
  const flash = frame < 3 ? (1 - frame / 3) * 0.85 : 0;
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{transform: `scale(${scale}) translate(${sx}px, ${sy}px)`}}>
        {children}
      </AbsoluteFill>
      <AbsoluteFill style={{background: '#FFF', opacity: flash, pointerEvents: 'none'}} />
      {/* 暗角冲击 */}
      <AbsoluteFill
        style={{
          background: 'radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.85) 100%)',
          opacity: frame < 6 ? (1 - frame / 6) * 0.5 : 0,
          pointerEvents: 'none',
        }}
      />
    </AbsoluteFill>
  );
};

/** 逐字 slam（1 帧错峰） */
const KineticChars: React.FC<{text: string; s: number; fps: number; charSize: number; color: string; startDelay?: number}> = ({
  text,
  s,
  fps,
  charSize,
  color,
  startDelay = 0,
}) => {
  const frame = useCurrentFrame();
  return (
    <span>
      {[...text].map((ch, i) => {
        const local = frame - startDelay - i;
        const p = spring({frame: local, fps, config: {damping: 13, stiffness: 170}});
        // 入场前 3 帧的 RGB 分离闪光（抖音冲击感）
        const glitch = local >= 0 && local < 3
          ? '-3px 0 rgba(255,0,90,0.75), 3px 0 rgba(0,229,255,0.75)'
          : 'none';
        return (
          <span
            key={i}
            style={{
              display: 'inline-block',
              whiteSpace: 'pre',
              opacity: Math.max(p, 0),
              transform: `scale(${1.45 - 0.45 * p}) translateY(${(1 - p) * 0.12 * charSize}px)`,
              textShadow: glitch,
            }}
          >
            {ch}
          </span>
        );
      })}
      <span style={{fontSize: charSize * 0 + 1, color}} aria-hidden>
        {}
      </span>
    </span>
  );
};

/** 速度线（集中线）：从中心放射的 12 条线，快速入场后淡出 */
const SpeedLines: React.FC<{s: number}> = ({s}) => {
  const frame = useCurrentFrame();
  const grow = interpolate(frame, [0, 7], [0.4, 1], {extrapolateRight: 'clamp'});
  const fade = interpolate(frame, [10, 22], [0.32, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const lines = Array.from({length: 12}, (_, i) => i * 30 + 7);
  return (
    <AbsoluteFill style={{opacity: fade, pointerEvents: 'none'}}>
      {lines.map((deg) => (
        <div
          key={deg}
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            width: 3 * s,
            height: 620 * s * grow,
            background: 'linear-gradient(to bottom, rgba(255,255,255,0.85), transparent)',
            transformOrigin: 'top center',
            transform: `translate(-50%, 0) rotate(${deg}deg)`,
            borderRadius: 2,
          }}
        />
      ))}
    </AbsoluteFill>
  );
};

// ---------- 分段卡片 ----------

const TitleCard: React.FC<{d: ReportData; s: number; fps: number}> = ({d, s, fps}) => {
  const frame = useCurrentFrame();
  // 光扫：一条 45° 白色渐变带从左扫到右（12-30f 一次）
  const sweep = interpolate(frame, [12, 32], [-30, 130], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
      {d.badge ? (
        <div style={{
          position: 'absolute', top: 300 * s,
          background: d.accentColor, color: '#1a1206', fontWeight: 700,
          fontFamily: FONT, fontSize: 40 * s, padding: `${10 * s}px ${28 * s}px`, borderRadius: 999,
          transform: `scale(${spring({frame, fps, config: {damping: 12, stiffness: 150}})})`,
        }}>{d.badge}</div>
      ) : null}
      <div style={{textAlign: 'center', padding: `0 ${100 * s}px`, position: 'relative', overflow: 'hidden'}}>
        <div style={{fontFamily: FONT, fontWeight: 700, fontSize: 96 * s, lineHeight: 1.2, color: '#FFFFFF', whiteSpace: 'pre-line'}}>
          <KineticChars text={d.title} s={s} fps={fps} charSize={96 * s} color={d.accentColor} startDelay={3} />
        </div>
        {d.subtitle ? (
          <div style={{
            fontFamily: FONT, fontSize: 44 * s, color: d.accentColor, marginTop: 26 * s,
            opacity: interpolate(frame, [16, 26], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
          }}>
            {d.subtitle}
          </div>
        ) : null}
        <div style={{width: 160 * s, height: 8 * s, background: d.accentColor, borderRadius: 4, margin: `${44 * s}px auto 0`, transformOrigin: 'center', transform: `scaleX(${interpolate(frame, [20, 34], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})})`}} />
        {/* 光扫层 */}
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          background: `linear-gradient(115deg, transparent ${sweep - 12}%, rgba(255,255,255,0.75) ${sweep}%, transparent ${sweep + 12}%)`,
          mixBlendMode: 'overlay',
        }} />
      </div>
    </AbsoluteFill>
  );
};

const StatCard: React.FC<{stat: Stat; accent: string; s: number; fps: number}> = ({stat, accent, s, fps}) => {
  const frame = useCurrentFrame();
  const pop = spring({frame, fps, config: {damping: 20, stiffness: 100}});
  const deltaColor = stat.delta
    ? stat.delta.trim().startsWith('-')
      ? '#FF6B6B'
      : '#5AD878'
    : 'transparent';
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
      <SpeedLines s={s} />
      <div style={{
        transform: `scale(${0.8 + 0.2 * pop})`,
        opacity: Math.max(pop, 0),
        textAlign: 'center',
        background: 'rgba(255,255,255,0.05)', border: '2px solid rgba(255,255,255,0.09)',
        borderRadius: 36 * s, padding: `${80 * s}px ${110 * s}px`,
        boxShadow: `0 0 ${90 * s}px rgba(255,216,102,0.07)`,
      }}>
        <div style={{fontFamily: FONT, fontSize: 44 * s, color: 'rgba(255,255,255,0.72)'}}>{stat.label}</div>
        <div style={{fontFamily: NUM_FONT, fontWeight: 700, fontSize: 158 * s, color: accent, margin: `${18 * s}px 0`, fontVariantNumeric: 'tabular-nums'}}>
          <AnimatedNumber value={stat.value} s={s} />
        </div>
        {stat.delta ? (
          <div style={{
            fontFamily: FONT, fontWeight: 700, fontSize: 56 * s, color: deltaColor,
            opacity: interpolate(frame, [30, 38], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
          }}>{stat.delta}</div>
        ) : null}
        {stat.note ? (
          <div style={{fontFamily: FONT, fontSize: 30 * s, color: 'rgba(255,255,255,0.5)', marginTop: 20 * s}}>{stat.note}</div>
        ) : null}
        <div style={{width: 90 * s, height: 6 * s, background: accent, borderRadius: 3, margin: `${36 * s}px auto 0`}} />
      </div>
    </AbsoluteFill>
  );
};

const ChartCard: React.FC<{chart: ChartSpec; accent: string; s: number; fps: number}> = ({chart, accent, s, fps}) => {
  const frame = useCurrentFrame();
  const max = Math.max(...chart.items.map((it) => it.value), 1e-9);
  const ranked = [...chart.items].sort((a, b) => b.value - a.value);
  const shown = chart.type === 'rank' ? ranked : chart.items;
  const labelW = 260 * s;
  return (
    <AbsoluteFill style={{justifyContent: 'center', padding: `0 ${110 * s}px`}}>
      {chart.title ? (
        <div style={{fontFamily: FONT, fontWeight: 700, fontSize: 56 * s, color: '#FFFFFF', marginBottom: 50 * s}}>
          {chart.title}
          {chart.unit ? (
            <span style={{fontSize: 30 * s, color: 'rgba(255,255,255,0.5)', marginLeft: 16 * s, whiteSpace: 'nowrap'}}>单位：{chart.unit}</span>
          ) : null}
        </div>
      ) : null}
      {shown.map((it, i) => {
        const appear = Math.round(i * 7); // 7f 错峰（半拍 @126BPM）
        const grow = spring({frame: frame - appear, fps, config: {damping: 20, stiffness: 100}});
        const isLeader = chart.type === 'rank' && i === 0;
        return (
          <div key={it.label} style={{display: 'flex', alignItems: 'center', marginBottom: 30 * s, opacity: Math.max(Math.min(grow * 2, 1), 0.01)}}>
            <div style={{width: labelW, fontFamily: FONT, fontSize: 34 * s, color: isLeader ? '#FFFFFF' : 'rgba(255,255,255,0.7)', textAlign: 'right', paddingRight: 22 * s, fontWeight: isLeader ? 700 : 400}}>
              {it.label}
            </div>
            <div style={{flex: 1, height: 54 * s, background: 'rgba(255,255,255,0.07)', borderRadius: 10 * s, overflow: 'hidden'}}>
              <div style={{
                width: `${Math.max((it.value / max) * 100 * Math.max(grow, 0), 0)}%`, height: '100%',
                background: isLeader ? accent : 'rgba(255,255,255,0.55)', borderRadius: 10 * s,
                boxShadow: isLeader && grow > 0.6 ? `0 0 ${34 * s}px rgba(255,216,102,0.45)` : 'none',
              }} />
            </div>
            <div style={{width: 220 * s, fontFamily: NUM_FONT, fontWeight: 700, fontSize: 38 * s, color: isLeader ? accent : '#FFFFFF', paddingLeft: 20 * s, fontVariantNumeric: 'tabular-nums'}}>
              {(it.value * Math.max(grow, 0)).toLocaleString('en-US', {maximumFractionDigits: 1})}
              {it.note ? <span style={{fontSize: 24 * s, color: 'rgba(255,255,255,0.45)', fontWeight: 400}}> {it.note}</span> : null}
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

const Takeaway: React.FC<{text: string; index: number; accent: string; s: number; fps: number}> = ({text, index, accent, s, fps}) => {
  const frame = useCurrentFrame();
  const slide = spring({frame, fps, config: {damping: 200}});
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
      <div style={{
        transform: `translateX(${(1 - slide) * 60 * s}px)`,
        display: 'flex', alignItems: 'flex-start', gap: 26 * s, padding: `0 ${90 * s}px`,
      }}>
        <div style={{
          minWidth: 72 * s, height: 72 * s, borderRadius: 999, background: accent,
          color: '#1a1206', fontFamily: NUM_FONT, fontWeight: 700, fontSize: 40 * s,
          display: 'flex', justifyContent: 'center', alignItems: 'center',
          transform: `scale(${spring({frame: frame - 4, fps, config: {damping: 12, stiffness: 160}})})`,
        }}>{index + 1}</div>
        <div style={{fontFamily: FONT, fontWeight: 700, fontSize: 62 * s, lineHeight: 1.35, color: '#FFFFFF', textAlign: 'left'}}>
          <KineticChars text={text} s={s} fps={fps} charSize={62 * s} color={accent} startDelay={2} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

const OutroCard: React.FC<{d: ReportData; s: number; fps: number}> = ({d, s, fps}) => {
  const frame = useCurrentFrame();
  const pop = spring({frame, fps, config: {damping: 14, stiffness: 120}});
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
      <div style={{transform: `scale(${0.85 + 0.15 * pop})`, opacity: pop, textAlign: 'center', padding: `0 ${100 * s}px`}}>
        <div style={{fontFamily: FONT, fontWeight: 700, fontSize: 76 * s, lineHeight: 1.3, color: d.accentColor}}>
          {d.outro!.slogan}
        </div>
        {d.outro!.sub ? (
          <div style={{fontFamily: FONT, fontSize: 36 * s, color: 'rgba(255,255,255,0.65)', marginTop: 30 * s}}>
            {d.outro!.sub}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

/** BGM 低频呼吸：visualizeAudio 低频能量（前 2 个 bin）→ 全屏 ≤2.8% 缩放脉冲 */
const BassPump: React.FC<{src: string; fps: number; children: React.ReactNode}> = ({src, fps, children}) => {
  const frame = useCurrentFrame();
  const audioData = useAudioData(src);
  const bass = audioData
    ? (() => {
        const a = visualizeAudio({audioData, frame, fps, numberOfSamples: 8, optimizeFor: 'speed'});
        return (a[0] + a[1]) / 2;
      })()
    : 0;
  const scale = 1 + interpolate(bass, [0, 0.8], [0, 0.028], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{transform: `scale(${scale})`, transformOrigin: 'center center'}}>
      {children}
    </AbsoluteFill>
  );
};

/** BGM 低频呼吸（离线包络版，Phase 6.2）：查表渲染，零 FFT 成本（渲染时间回到 v2 水平） */
const BassPumpEnvelope: React.FC<{
  env: {fps: number; values: number[]};
  children: React.ReactNode;
}> = ({env, children}) => {
  const frame = useCurrentFrame();
  const v = env.values[Math.min(frame, env.values.length - 1)] ?? 0;
  const scale = 1 + interpolate(v, [0, 1], [0, 0.028], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{transform: `scale(${scale})`, transformOrigin: 'center center'}}>
      {children}
    </AbsoluteFill>
  );
};

// ---------- 主组件 ----------

export const ReportVertical: React.FC<Record<string, unknown>> = (rawProps) => {
  const d = ReportDataSchema.parse(rawProps);
  const rawSections = reportSections(d);
  const frame = useCurrentFrame();
  const {fps, height} = useVideoConfig();
  const s = height / 1920;
  const totalFrames = Math.round(reportDurationSeconds(d) * fps);

  // 卡点量化：分段起点吸附到拍边界（beat = 60/bpm 秒）
  const beatFrames = (60 / d.bpm) * fps;
  const sections = rawSections.map((sec, i) => {
    if (i === 0) return sec;
    const snapped = Math.round(sec.start * fps / beatFrames) * beatFrames;
    return {...sec, start: snapped / fps};
  });

  // 自动音效：whoosh 在分段起点前 0.18s，impact 在起点，takeaway 加 ding，outro 前 riser(1.2s)
  const sfxEvents: Array<{src: string; t: number; volume: number}> = [];
  if (d.sfxAuto) {
    sections.forEach((sec, i) => {
      if (i === 0) return;
      sfxEvents.push({src: 'audio/sfx_whoosh.m4a', t: Math.max(0.01, sec.start - 0.18), volume: 0.55});
      sfxEvents.push({src: 'audio/sfx_impact.m4a', t: sec.start, volume: 0.85});
      if (sec.kind === 'takeaway' && sec.index === 0) {
        sfxEvents.push({src: 'audio/sfx_ding.m4a', t: sec.start + 0.24, volume: 0.5});
      }
      if (sec.kind === 'outro') {
        sfxEvents.push({src: 'audio/sfx_riser.m4a', t: Math.max(0.01, sec.start - 1.2), volume: 0.5});
      }
    });
  }

  const backgrounds = (
    <>
      <div style={{
        position: 'absolute', width: 1100 * s, height: 1100 * s, borderRadius: '50%',
        background: 'radial-gradient(closest-side, rgba(64,98,255,0.28), transparent)',
        left: -260 * s + Math.sin(frame / 105) * 70 * s, top: -240 * s + Math.cos(frame / 130) * 50 * s,
      }} />
        <div style={{
          position: 'absolute', width: 1000 * s, height: 1000 * s, borderRadius: '50%',
          background: 'radial-gradient(closest-side, rgba(255,216,102,0.14), transparent)',
          right: -300 * s + Math.sin(frame / 85 + 2) * 60 * s, bottom: -260 * s + Math.cos(frame / 115) * 45 * s,
        }} />
        <div style={{
          position: 'absolute', inset: 0, opacity: 0.05,
          backgroundImage: 'linear-gradient(rgba(255,255,255,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.6) 1px, transparent 1px)',
          backgroundSize: `${80 * s}px ${80 * s}px`,
        }} />
    </>
  );

  // 低频呼吸只作用于内容层：全屏缩放会逼 headless Chrome 每帧重光栅化背景（渲染时间 ×2.5）
  const sectionLayer = (
    <>
      {sections.map((sec, i) => {
          const from = Math.round(sec.start * fps);
          const dur = Math.max(1, Math.round((sec.end - sec.start) * fps));
          const active = frame >= from && frame < from + dur;
          if (!active) {
            return null;
          }
          const local = frame - from;
          const IN = Math.min(10, Math.floor(dur / 3));
          const OUT = Math.min(8, Math.floor(dur / 3));
          const opacity = Math.min(local / Math.max(IN, 1), 1) * Math.min((dur - local) / Math.max(OUT, 1), 1);
          const rise = (1 - Math.min(local / Math.max(IN, 1), 1)) * 34 * s;
          const inner = (() => {
            switch (sec.kind) {
              case 'title': return <TitleCard d={d} s={s} fps={fps} />;
              case 'stat': return <StatCard stat={d.stats[sec.index!]} accent={d.accentColor} s={s} fps={fps} />;
              case 'chart': return d.chart ? <ChartCard chart={d.chart} accent={d.accentColor} s={s} fps={fps} /> : null;
              case 'takeaway': return <Takeaway text={d.takeaways[sec.index!]} index={sec.index!} accent={d.accentColor} s={s} fps={fps} />;
              case 'outro': return d.outro ? <OutroCard d={d} s={s} fps={fps} /> : null;
              default: return null;
            }
          })();
          return (
            <AbsoluteFill key={`${sec.kind}-${i}`} style={{opacity, transform: `translateY(${rise}px)`}}>
              <ImpactWrap s={s} fps={fps}>{inner}</ImpactWrap>
            </AbsoluteFill>
          );
        })}
      </>
    );

  const pumpedSections =
    d.narration && d.narration.pumpEnvelope ? (
      <BassPumpEnvelope env={d.narration.pumpEnvelope}>{sectionLayer}</BassPumpEnvelope>
    ) : d.narration ? (
      <BassPump src={staticFile(d.narration.src)} fps={fps}>{sectionLayer}</BassPump>
    ) : (
      sectionLayer
    );

  const content = (
    <>
      {backgrounds}
      {pumpedSections}
      {/* 全程进度条 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0,
        width: `${(frame / totalFrames) * 100}%`, height: 6 * s,
        background: d.accentColor, opacity: 0.85,
      }} />
    </>
  );

  const bgmSrc = d.narration ? staticFile(d.narration.src) : null;

  return (
    <EnsureFonts>
      <AbsoluteFill style={{background: 'linear-gradient(165deg, #0b1026 0%, #141b33 55%, #1d1430 100%)'}}>
        {content}
        {d.narration ? <Audio src={bgmSrc ?? undefined} volume={d.narration.volume} /> : null}
        {/* 音效：<Sequence> 对齐起点（whoosh 带 0.18s 提前量） */}
        {sfxEvents.map((e, i) => {
          const from = Math.round(e.t * fps);
          return (
            <Sequence key={`sfx${i}`} from={from}>
              <Audio src={staticFile(e.src)} volume={e.volume} />
            </Sequence>
          );
        })}
      </AbsoluteFill>
    </EnsureFonts>
  );
};

export const reportTotalFrames = (d: ReportData): number =>
  Math.round(reportDurationSeconds(d) * d.format.fps);
