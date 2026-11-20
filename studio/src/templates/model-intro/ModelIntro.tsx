import React from 'react';
import {AbsoluteFill, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Audio} from '@remotion/media';
import timelineData from './timeline.json';
import {Backdrop, CaptionBar, Fade, Hud, TransitionFlash, Whoosh} from './common/ui';
import {COLORS, FONTS} from './theme';
import {HelloScene} from './scenes/HelloScene';
import {IdentityScene} from './scenes/IdentityScene';
import {RepoScene} from './scenes/RepoScene';
import {LoopScene} from './scenes/LoopScene';
import {SkillsScene} from './scenes/SkillsScene';
import {ProofScene} from './scenes/ProofScene';
import {OutroScene} from './scenes/OutroScene';

type Timeline = {
  totalSeconds: number;
  /** 场景之间的叠化余量（帧）。 */
  overlapFrames: number;
  scenes: {
    id: string;
    caption: string;
    audio: string;
    start: number;
    duration: number;
    audioInFrame: number;
    captionInFrame: number;
    captionOutFrame: number;
  }[];
};

const timeline = timelineData as Timeline;

const SCENE_LABELS: Record<string, string> = {
  hello: '00 · HELLO',
  identity: '01 · IDENTITY',
  repo: '02 · REPOSITORY',
  loop: '03 · WORKFLOW',
  skills: '04 · CAPABILITIES',
  proof: '05 · PROOF',
  outro: '06 · SIGN-OFF',
};

/**
 * model-intro —— 模型自我介绍片。
 * 全部画面由 React 代码渲染（Remotion），不经过任何视频生成模型；
 * 时间轴由本地 Kokoro 旁白的真实时长驱动（timeline.json）。
 *
 * 画面结构是交叉叠化：每个场景除自身时长外再挂 overlapFrames，
 * 旧场景在叠化窗口内淡出（24 帧），新场景前 12 帧淡入。
 * 字幕与旁白都提到顶层渲染 —— 叠化窗口里若两条字幕同时在画面上就会互相打架。
 */
export const ModelIntro: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const totalFrames = Math.round(timeline.totalSeconds * fps);
  const overlap = timeline.overlapFrames;

  // HUD 场景名：取「最后一个 start <= 当前帧」的场景。
  // 之前用 find(落在区间内) 时，找不到就回落到最后一个场景，片头会闪「06 · SIGN-OFF」。
  const current =
    [...timeline.scenes].reverse().find((s) => Math.round(s.start * fps) <= frame) ??
    timeline.scenes[0];

  return (
    <AbsoluteFill style={{backgroundColor: COLORS.bg, fontFamily: FONTS.sans}}>
      <Backdrop />

      {/* 场景：交叉叠化 */}
      {timeline.scenes.map((scene, index) => {
        const from = Math.round(scene.start * fps);
        const isLast = index === timeline.scenes.length - 1;
        const durationInFrames = Math.round(scene.duration * fps);
        return (
          <Sequence key={scene.id} from={from} durationInFrames={durationInFrames} name={scene.id}>
            <Fade durationFrames={durationInFrames} inFrames={overlap} outFrames={isLast ? 12 : overlap}>
              {scene.id === 'hello' ? <HelloScene /> : null}
              {scene.id === 'identity' ? <IdentityScene /> : null}
              {scene.id === 'repo' ? <RepoScene /> : null}
              {scene.id === 'loop' ? <LoopScene /> : null}
              {scene.id === 'skills' ? <SkillsScene /> : null}
              {scene.id === 'proof' ? <ProofScene totalFrames={totalFrames} /> : null}
              {scene.id === 'outro' ? <OutroScene /> : null}
            </Fade>
          </Sequence>
        );
      })}

      {/* 字幕：提到顶层，一段字幕一条 Sequence，叠化期不交叠 */}
      {timeline.scenes.map((scene) => (
        <Sequence
          key={`caption-${scene.id}`}
          from={Math.round(scene.start * fps) + scene.captionInFrame}
          durationInFrames={scene.captionOutFrame - scene.captionInFrame}
          name={`caption-${scene.id}`}
        >
          <CaptionBar text={scene.caption} fadeOut />
        </Sequence>
      ))}

      {/* 转场闪白：盖住两场之间的空档，读起来像一次快闪切换 */}
      {timeline.scenes.slice(1).map((scene) => (
        <Sequence
          key={`flash-${scene.id}`}
          from={Math.round(scene.start * fps) - overlap}
          durationInFrames={overlap * 2}
          name={`flash-${scene.id}`}
        >
          <TransitionFlash peak={0.16} />
        </Sequence>
      ))}

      {/* 旁白：不写 durationInFrames，让它自然播完 */}
      {timeline.scenes.map((scene) => (
        <Sequence
          key={`audio-${scene.id}`}
          from={Math.round(scene.start * fps) + scene.audioInFrame}
          name={`audio-${scene.id}`}
        >
          <Audio src={staticFile(scene.audio)} />
        </Sequence>
      ))}

      {/* 转场音效：每场转场处一记，起于转场前 10 帧 */}
      {timeline.scenes.slice(1).map((scene) => (
        <Sequence
          key={`whoosh-${scene.id}`}
          from={Math.round(scene.start * fps) - 10}
          name={`whoosh-${scene.id}`}
        >
          <Whoosh volume={0.09} />
        </Sequence>
      ))}

      <Hud label={SCENE_LABELS[current.id] ?? ''} totalFrames={totalFrames} />

      <Audio src={staticFile('audio/bgm_main.m4a')} volume={0.085} />
    </AbsoluteFill>
  );
};

export const modelIntroTotalFrames = (fps: number): number => Math.round(timeline.totalSeconds * fps);
