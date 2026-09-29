import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';

/**
 * 帧内转场：动画只发生在镜头自己的前 N 帧（fade 从黑起 / flash 闪白起），
 * 绝不改变时间轴——对白、音效、字幕的绝对秒完全不受影响。
 * （不用 <TransitionSeries> 的重叠式转场：那会挪动后续镜头的时间位置。）
 */
export const ShotFrame: React.FC<{
  transitionIn: {type: 'none' | 'fade' | 'flash'; durationInFrames: number};
  children: React.ReactNode;
}> = ({transitionIn, children}) => {
  const frame = useCurrentFrame(); // Sequence 内局部帧
  const dur = transitionIn.durationInFrames;
  const progress = dur > 0 ? Math.min(frame / dur, 1) : 1;

  if (transitionIn.type === 'none' || progress >= 1) {
    return <>{children}</>;
  }
  return (
    <AbsoluteFill>
      {children}
      <AbsoluteFill
        style={{
          background: transitionIn.type === 'fade' ? '#000' : '#FFF',
          opacity: 1 - progress,
        }}
      />
    </AbsoluteFill>
  );
};
