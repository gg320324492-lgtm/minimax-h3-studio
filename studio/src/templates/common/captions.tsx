import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import type {SubtitleEvent} from '../../schemas/timeline-v2';
import {CAPTION_FONT, estimateLines, webkitStrokeWidth, type StyleSet, type SubtitleToken} from './styleSet';

type Placed = {
  event: SubtitleEvent;
  token: SubtitleToken;
  yPx: number; // 已按设计稿→成片缩放
  scale: number;
};

const bandOf = (token: SubtitleToken, text: string, scale: number): [number, number] => {
  const lines = estimateLines(text, token);
  const top = token.yPx * scale;
  return [top, top + lines * token.fontSize * scale * 1.25];
};

const overlaps = (a: [number, number], b: [number, number]): boolean =>
  a[0] < b[1] && b[0] < a[1];

/**
 * 碰撞感知的字幕布局：
 * - 不可移动样式（msg/step/corner/title 等屏幕固定元素）先占位；
 * - 可移动字幕按模板优先级（同优先级按出现时间）占用各自 yPx，
 *   与已占用竖向带冲突时向上让位，直到无冲突或到达画面上 1/3 下限。
 * 解决 EP01 结尾 ending+special+inner 三事件同屏叠字问题（v2 既有缺陷）。
 */
export const layoutCaptions = (
  visible: SubtitleEvent[],
  styleSet: StyleSet,
  scale: number
): Placed[] => {
  const tokenOf = (ev: SubtitleEvent): SubtitleToken =>
    styleSet.styles[ev.style] ?? styleSet.styles[styleSet.defaultStyle];

  const occupied: Array<[number, number]> = [];
  const immovable = visible.filter((ev) => !tokenOf(ev).movable);
  for (const ev of immovable) {
    occupied.push(bandOf(tokenOf(ev), ev.text, scale));
  }

  const prioOf = (ev: SubtitleEvent): number => {
    const idx = styleSet.priority.indexOf(ev.style);
    return idx === -1 ? styleSet.priority.length : idx;
  };
  const movable = visible
    .filter((ev) => tokenOf(ev).movable)
    .sort((a, b) => prioOf(a) - prioOf(b) || a.start - b.start);

  const placed: Placed[] = [];
  for (const ev of movable) {
    const token = tokenOf(ev);
    const band = bandOf(token, ev.text, scale);
    const bandH = band[1] - band[0];
    let y = token.yPx * scale;
    const minY = styleSet.designHeight * scale * 0.3;
    let guard = 0;
    while (
      guard < 24 &&
      occupied.some((b) => overlaps(b, [y, y + bandH]))
    ) {
      y -= token.fontSize * scale * 0.55;
      guard += 1;
      if (y < minY) {
        y = minY;
        break;
      }
    }
    occupied.push([y, y + bandH]);
    placed.push({event: ev, token, yPx: y, scale});
  }
  for (const ev of immovable) {
    const token = tokenOf(ev);
    placed.push({event: ev, token, yPx: token.yPx * scale, scale});
  }
  return placed;
};

const KaraokeText: React.FC<{p: Placed; time: number}> = ({p, time}) => {
  const {token, event, scale} = p;
  const words = event.words!;
  const spans = words.map((w, i) => {
    const start = Math.max(w.t, event.start);
    const end = Math.max(w.t + w.d, start + 0.01);
    const state = time >= end ? 'done' : time >= start ? 'active' : 'future';
    return (
      <span
        key={i}
        style={{
          display: 'inline-block',
          whiteSpace: 'pre',
          opacity: state === 'future' ? 0.4 : 1,
          transform: state === 'active' ? 'scale(1.18)' : 'none',
          transformOrigin: 'center bottom',
        }}
      >
        {w.w}
      </span>
    );
  });
  return (
    <div
      style={{
        maxWidth: token.maxWidthPx * scale,
        fontFamily: CAPTION_FONT,
        fontWeight: token.fontWeight ?? 400,
        fontSize: token.fontSize * scale,
        lineHeight: 1.25,
        color: token.color,
        textAlign: 'center',
        ...(token.strokeColor
          ? {
              WebkitTextStrokeWidth: webkitStrokeWidth(token.strokePx ?? 0) * scale,
              WebkitTextStrokeColor: token.strokeColor,
              paintOrder: 'stroke fill' as const,
            }
          : {}),
      }}
    >
      {spans}
    </div>
  );
};

/** 心声打字机：inner/inner_special 且无词级时间戳时，前 35% 时长内逐字显形 */
const TypewriterText: React.FC<{p: Placed; time: number}> = ({p, time}) => {
  const {token, event, scale} = p;
  const dur = event.end - event.start;
  const revealDur = Math.min(0.6, dur * 0.35);
  const chars = [...event.text];
  const shown = Math.min(
    chars.length,
    Math.floor((Math.max(time - event.start, 0) / Math.max(revealDur, 0.01)) * chars.length) + 1
  );
  return (
    <div
      style={{
        maxWidth: token.maxWidthPx * scale,
        fontFamily: CAPTION_FONT,
        fontWeight: token.fontWeight ?? 400,
        fontSize: token.fontSize * scale,
        lineHeight: 1.25,
        color: token.color,
        textAlign: 'center',
        ...(token.strokeColor
          ? {
              WebkitTextStrokeWidth: webkitStrokeWidth(token.strokePx ?? 0) * scale,
              WebkitTextStrokeColor: token.strokeColor,
              paintOrder: 'stroke fill' as const,
            }
          : {}),
      }}
    >
      <span>{chars.slice(0, shown).join('')}</span>
      {shown < chars.length ? (
        <span style={{opacity: 0.18}}>{chars.slice(shown).join('')}</span>
      ) : null}
    </div>
  );
};

const StaticText: React.FC<{p: Placed}> = ({p}) => {
  const {token, scale} = p;
  return (
    <div
      style={{
        maxWidth: token.maxWidthPx * scale,
        fontFamily: CAPTION_FONT,
        fontWeight: token.fontWeight ?? 400,
        fontSize: token.fontSize * scale,
        lineHeight: 1.25,
        color: token.color,
        textAlign: 'center',
        ...(token.strokeColor
          ? {
              WebkitTextStrokeWidth: webkitStrokeWidth(token.strokePx ?? 0) * scale,
              WebkitTextStrokeColor: token.strokeColor,
              paintOrder: 'stroke fill' as const,
            }
          : {}),
      }}
    >
      {p.event.text}
    </div>
  );
};

const Caption: React.FC<{p: Placed; width: number}> = ({p, width}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const time = frame / fps;
  const {token} = p;
  const alignLeft = token.align === 'left';
  const content = p.event.words?.length && token.movable && p.event.style !== 'inner' && p.event.style !== 'inner_special' ? (
    <KaraokeText p={p} time={time} />
  ) : p.event.style === 'inner' || p.event.style === 'inner_special' ? (
    <TypewriterText p={p} time={time} />
  ) : (
    <StaticText p={p} />
  );
  return (
    <div
      style={{
        position: 'absolute',
        top: p.yPx,
        left: alignLeft ? (token.xPx ?? 0) * p.scale : 0,
        right: alignLeft ? undefined : 0,
        display: 'flex',
        justifyContent: alignLeft ? 'flex-start' : 'center',
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          maxWidth: token.maxWidthPx * p.scale,
          ...(token.bg
            ? {
                background: token.bg.color,
                padding: `${token.bg.padY * p.scale}px ${token.bg.padX * p.scale}px`,
                borderRadius: Math.min(token.bg.radius, 999) * p.scale,
              }
            : {}),
        }}
      >
        {content}
      </div>
    </div>
  );
};

export const CaptionLayer: React.FC<{
  events: SubtitleEvent[];
  styleSet: StyleSet;
}> = ({events, styleSet}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const scale = height / styleSet.designHeight;
  const visible = events.filter(
    (ev) => frame >= Math.round(ev.start * fps) && frame < Math.round(ev.end * fps)
  );
  if (visible.length === 0) {
    return null;
  }
  return (
    <>
      {layoutCaptions(visible, styleSet, scale).map((p) => (
        <Caption key={p.event.id} p={p} width={width} />
      ))}
    </>
  );
};
