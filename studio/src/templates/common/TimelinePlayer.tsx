import React, {useMemo} from 'react';
import {AbsoluteFill, Audio, OffthreadVideo, Sequence, staticFile, useVideoConfig} from 'remotion';
import type {Shot, TimelineV2} from '../../schemas/timeline-v2';
import {EnsureFonts} from './EnsureFonts';
import {CaptionLayer} from './captions';
import {OverlayLayer} from './overlays';
import type {StyleSet} from './styleSet';
import {ShotFrame} from './transitions';

/**
 * 时间线播放核心：titlecard? → shots → endcard? 的确定性装配。
 * 三个模板（drama-vertical / psa-wide / story-animation）= 本核心 × 各自格式与样式集。
 * 字幕/overlay 时间为绝对秒（titlecard 在时间轴最前，shots 从卡后起算——与 liaozhai v1 语义一致）。
 */

const CardBackdrop: React.FC<{background: 'black' | 'gradient'}> = ({background}) => (
  <AbsoluteFill
    style={
      background === 'black'
        ? {background: '#000'}
        : {background: 'linear-gradient(160deg, #0b1026 0%, #241b3a 55%, #4a2b4d 100%)'}
    }
  />
);

const CardLines: React.FC<{
  lines: Array<{text: string; style: string}>;
  styleSet: StyleSet;
}> = ({lines, styleSet}) => {
  const {height} = useVideoConfig();
  const scale = height / styleSet.designHeight;
  return (
    <>
      {lines.map((line, i) => {
        const token = styleSet.styles[line.style] ?? styleSet.styles[styleSet.defaultStyle];
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              top: token.yPx * scale,
              left: 0,
              right: 0,
              display: 'flex',
              justifyContent: token.align === 'left' ? 'flex-start' : 'center',
              paddingLeft: token.align === 'left' ? (token.xPx ?? 0) * scale : 0,
            }}
          >
            <div
              style={{
                fontFamily: '"Microsoft YaHei", SimHeiLocal, sans-serif',
                fontWeight: token.fontWeight ?? 400,
                fontSize: token.fontSize * scale,
                lineHeight: 1.25,
                color: token.color,
                textAlign: token.align === 'left' ? 'left' : 'center',
                ...(token.strokeColor
                  ? {
                      WebkitTextStrokeWidth: (token.strokePx ?? 0) * 2 * scale,
                      WebkitTextStrokeColor: token.strokeColor,
                      paintOrder: 'stroke fill' as const,
                    }
                  : {}),
              }}
            >
              {line.text}
            </div>
          </div>
        );
      })}
    </>
  );
};

export const TimelinePlayer: React.FC<{tl: TimelineV2; styleSet: StyleSet}> = ({tl, styleSet}) => {
  const {fps} = useVideoConfig();

  const sequences = useMemo(() => {
    const out: React.ReactNode[] = [];
    let cursor = 0;

    if (tl.titlecard) {
      const from = cursor;
      cursor += tl.titlecard.durationInFrames;
      out.push(
        <Sequence key="titlecard" from={from} durationInFrames={tl.titlecard.durationInFrames} name="TitleCard">
          <CardBackdrop background={tl.titlecard.background} />
          <CardLines lines={tl.titlecard.lines} styleSet={styleSet} />
        </Sequence>
      );
    }

    for (const shot of tl.shots) {
      const from = cursor;
      cursor += shot.durationInFrames;
      out.push(
        <Sequence key={shot.id} from={from} durationInFrames={shot.durationInFrames} name={shot.id}>
          <ShotFrame transitionIn={shot.transitionIn}>
            <OffthreadVideo
              src={staticFile(shot.file)}
              trimBefore={shot.trimBefore}
              style={{width: '100%', height: '100%', objectFit: tl.fit}}
            />
          </ShotFrame>
        </Sequence>
      );
    }

    if (tl.endcard) {
      const from = cursor;
      cursor += tl.endcard.durationInFrames;
      out.push(
        <Sequence key="endcard" from={from} durationInFrames={tl.endcard.durationInFrames} name="EndCard">
          <CardBackdrop background={tl.endcard.background} />
          <CardLines lines={tl.endcard.lines} styleSet={styleSet} />
        </Sequence>
      );
    }

    return out;
  }, [tl, styleSet]);

  return (
    <EnsureFonts>
      <AbsoluteFill style={{background: '#000'}}>
        {sequences}
        {/* text 类花字并入字幕碰撞布局（同屏自动错行）；progress/lower-third 独立渲染 */}
        <CaptionLayer
          events={[
            ...tl.subtitles,
            ...tl.overlays
              .filter((o): o is Extract<typeof o, {kind: 'text'}> => o.kind === 'text')
              .map((o, i) => ({
                id: `overlay-text-${i}`,
                text: o.text,
                style: o.style,
                start: o.start,
                end: o.end,
              })),
          ]}
          styleSet={styleSet}
        />
        <OverlayLayer
          overlays={tl.overlays.filter((o) => o.kind !== 'text')}
          styleSet={styleSet}
        />
        <Audio src={staticFile(tl.audioBus.premixed)} />
      </AbsoluteFill>
    </EnsureFonts>
  );
};

export const timelineTotalFrames = (tl: TimelineV2): number =>
  (tl.titlecard?.durationInFrames ?? 0) +
  tl.shots.reduce((sum, s: Shot) => sum + s.durationInFrames, 0) +
  (tl.endcard?.durationInFrames ?? 0);
