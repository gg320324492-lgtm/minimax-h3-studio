import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {EnsureFonts} from './common/EnsureFonts';

// Phase 0 探针合成：验证 headless 渲染 + 中文字体（自托管 vs 系统）+ 基础动效。
// 用 `npx remotion still Phase0Probe out/probe.png --frame=60` 出单帧目检。

export const Phase0Probe: React.FC = () => {
  const frame = useCurrentFrame();
  const {durationInFrames, height} = useVideoConfig();
  const progress = frame / durationInFrames;

  const titleY = interpolate(frame, [0, 30], [80, 0], {
    extrapolateRight: 'clamp',
  });

  return (
    <EnsureFonts>
      <AbsoluteFill
        style={{
          background: `linear-gradient(${140 + frame * 0.5}deg, #0b1026, #241b3a ${40 + progress * 20}%, #4a2b4d)`,
          justifyContent: 'center',
          alignItems: 'center',
        }}
      >
        <div
          style={{
            transform: `translateY(${titleY}px)`,
            textAlign: 'center',
          }}
        >
          <div style={{fontFamily: 'SimHeiLocal, serif', fontSize: 96, color: '#FFD866', marginBottom: 40}}>
            Remotion × MiniMax-H3
          </div>
          <div style={{fontFamily: '"Microsoft YaHei", sans-serif', fontSize: 72, color: '#FFFFFF', marginBottom: 28}}>
            系统字体：总裁听见了实习生的心声
          </div>
          <div style={{fontFamily: 'SimHeiLocal, sans-serif', fontSize: 72, color: '#7FE3FF', marginBottom: 28}}>
            自托管黑体：【心声】他还有七秒就要死了。
          </div>
          <div style={{fontFamily: 'SimHeiLocal, sans-serif', fontSize: 56, color: '#B48CFF'}}>
            基准帧 {frame} / {durationInFrames}
          </div>
        </div>
        <div
          style={{
            position: 'absolute',
            bottom: height * 0.08,
            width: 800,
            height: 10,
            background: 'rgba(255,255,255,0.15)',
            borderRadius: 5,
            overflow: 'hidden',
          }}
        >
          <div style={{width: `${progress * 100}%`, height: '100%', background: '#FFD866'}} />
        </div>
      </AbsoluteFill>
    </EnsureFonts>
  );
};
