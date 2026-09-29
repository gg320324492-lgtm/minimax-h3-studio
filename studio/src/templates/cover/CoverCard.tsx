import React from 'react';
import {AbsoluteFill, Img, staticFile, useVideoConfig} from 'remotion';
import {z} from 'zod';
import {EnsureFonts} from '../common/EnsureFonts';

// 封面模板 —— renderStill 单帧输出（替代 PIL 拼贴封面），与影片共享视觉资产。
// 用法：npx remotion still CoverCard --props=cover.json --output=08_cover/cover.png

export const CoverPropsSchema = z.object({
  backgroundImage: z.string(), // public/ 相对路径（通常为选片抽帧）
  title: z.string(),
  subtitle: z.string().optional(),
  badge: z.string().optional(),
  accentColor: z.string().default('#FFD866'),
});

export const CoverCard: React.FC<Record<string, unknown>> = (rawProps) => {
  const props = CoverPropsSchema.parse(rawProps);
  const {height, width} = useVideoConfig();
  const s = height / 1920; // 封面排版基于 1080×1920 设计稿

  return (
    <EnsureFonts>
      <AbsoluteFill style={{background: '#000'}}>
        <Img
          src={staticFile(props.backgroundImage)}
          style={{width: '100%', height: '100%', objectFit: 'cover'}}
        />
        <AbsoluteFill
          style={{
            background: 'linear-gradient(180deg, rgba(0,0,0,0.05) 40%, rgba(0,0,0,0.82) 100%)',
          }}
        />
        {props.badge ? (
          <div
            style={{
              position: 'absolute',
              top: 120 * s,
              left: 60 * s,
              background: props.accentColor,
              color: '#1a1206',
              fontFamily: '"Microsoft YaHei", SimHeiLocal, sans-serif',
              fontWeight: 700,
              fontSize: 40 * s,
              padding: `${10 * s}px ${28 * s}px`,
              borderRadius: 999,
            }}
          >
            {props.badge}
          </div>
        ) : null}
        <div style={{position: 'absolute', left: 60 * s, right: 60 * s, bottom: 180 * s}}>
          <div
            style={{
              fontFamily: '"Microsoft YaHei", SimHeiLocal, sans-serif',
              fontWeight: 700,
              fontSize: 96 * s,
              lineHeight: 1.18,
              color: '#FFFFFF',
              whiteSpace: 'pre-line',
              textShadow: `0 ${4 * s}px ${18 * s}px rgba(0,0,0,0.65)`,
            }}
          >
            {props.title}
          </div>
          {props.subtitle ? (
            <div
              style={{
                fontFamily: '"Microsoft YaHei", SimHeiLocal, sans-serif',
                fontSize: 44 * s,
                color: props.accentColor,
                marginTop: 22 * s,
                textShadow: `0 ${2 * s}px ${10 * s}px rgba(0,0,0,0.7)`,
              }}
            >
              {props.subtitle}
            </div>
          ) : null}
          <div
            style={{
              marginTop: 40 * s,
              width: 160 * s,
              height: 8 * s,
              background: props.accentColor,
              borderRadius: 4,
            }}
          />
        </div>
        <div
          style={{
            position: 'absolute',
            top: 60 * s,
            right: 60 * s,
            fontFamily: '"Microsoft YaHei", SimHeiLocal, sans-serif',
            fontSize: 24 * s,
            color: 'rgba(255,255,255,0.55)',
          }}
        >
          {width}×{height}
        </div>
      </AbsoluteFill>
    </EnsureFonts>
  );
};
