import React from 'react';
import {spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Overlay} from '../../schemas/timeline-v2';
import type {StyleSet} from './styleSet';

/**
 * overlays 体系：progress 进度条、lower-third 人名条。
 * （text 花字在 TimelinePlayer 中并入字幕碰撞布局——独立渲染会与字幕同屏叠字。）
 */

const ProgressOverlay: React.FC<{start: number; end: number}> = ({start, end}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t0 = Math.round(start * fps);
  const t1 = Math.round(end * fps);
  const progress = Math.min(Math.max((frame - t0) / Math.max(t1 - t0, 1), 0), 1);
  return (
    <div
      style={{
        position: 'absolute',
        bottom: height * 0.03,
        left: width * 0.1,
        right: width * 0.1,
        height: Math.max(4, height * 0.004),
        background: 'rgba(255,255,255,0.18)',
        borderRadius: 999,
        overflow: 'hidden',
      }}
    >
      <div style={{width: `${progress * 100}%`, height: '100%', background: '#FFD866'}} />
    </div>
  );
};

const LowerThird: React.FC<{
  ov: Extract<Overlay, {kind: 'lower-third'}>;
  styleSet: StyleSet;
}> = ({ov, styleSet}) => {
  const {height, width} = useVideoConfig();
  const scale = height / styleSet.designHeight;
  return (
    <div
      style={{
        position: 'absolute',
        bottom: height * 0.12,
        left: width * 0.05,
        background: 'rgba(10,12,18,0.78)',
        borderRadius: 14 * scale,
        padding: `${18 * scale}px ${30 * scale}px`,
      }}
    >
      <div
        style={{
          fontFamily: '"Microsoft YaHei", SimHeiLocal, sans-serif',
          fontWeight: 700,
          fontSize: 44 * scale,
          color: '#FFFFFF',
        }}
      >
        {ov.title}
      </div>
      {ov.sub ? (
        <div
          style={{
            fontFamily: '"Microsoft YaHei", SimHeiLocal, sans-serif',
            fontSize: 28 * scale,
            color: 'rgba(255,255,255,0.75)',
            marginTop: 6 * scale,
          }}
        >
          {ov.sub}
        </div>
      ) : null}
    </div>
  );
};

type NonTextOverlay = Exclude<Overlay, {kind: 'text'}>;

export const OverlayLayer: React.FC<{overlays: NonTextOverlay[]; styleSet: StyleSet}> = ({
  overlays,
  styleSet,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <>
      {overlays.map((ov, i) => {
        const visible = frame >= Math.round(ov.start * fps) && frame < Math.round(ov.end * fps);
        if (!visible) {
          return null;
        }
        if (ov.kind === 'progress') {
          return <ProgressOverlay key={`ov${i}`} start={ov.start} end={ov.end} />;
        }
        return <LowerThird key={`ov${i}`} ov={ov} styleSet={styleSet} />;
      })}
    </>
  );
};
