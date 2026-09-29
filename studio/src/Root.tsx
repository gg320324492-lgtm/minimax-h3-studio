import React from 'react';
import {Composition} from 'remotion';
import {DramaVertical} from './templates/drama-vertical/DramaVertical';
import {PsaWide} from './templates/psa-wide/PsaWide';
import {StoryAnimation} from './templates/story-animation/StoryAnimation';
import {CoverCard} from './templates/cover/CoverCard';
import {ReportVertical, reportTotalFrames} from './templates/report/ReportVertical';
import {Phase0Probe} from './templates/Phase0Probe';
import {timelineTotalFrames} from './templates/common/TimelinePlayer';
import type {TimelineV2} from './schemas/timeline-v2';
import type {ReportData} from './schemas/report-data';

// 三个时间线模板共用 calculateMetadata 逻辑；props 契约校验在各组件内（parse）。
const timelineMeta = ({props}: {props: unknown}) => ({
  durationInFrames: Math.max(1, timelineTotalFrames(props as TimelineV2)),
});
const reportMeta = ({props}: {props: unknown}) => ({
  durationInFrames: Math.max(1, reportTotalFrames(props as ReportData)),
});

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="DramaVertical"
        component={DramaVertical}
        width={1080}
        height={1920}
        fps={24}
        durationInFrames={1}
        defaultProps={{}}
        calculateMetadata={timelineMeta}
      />
      <Composition
        id="PsaWide"
        component={PsaWide}
        width={1920}
        height={1080}
        fps={24}
        durationInFrames={1}
        defaultProps={{}}
        calculateMetadata={timelineMeta}
      />
      <Composition
        id="StoryAnimation"
        component={StoryAnimation}
        width={2560}
        height={1440}
        fps={24}
        durationInFrames={1}
        defaultProps={{}}
        calculateMetadata={timelineMeta}
      />
      <Composition
        id="ReportVertical"
        component={ReportVertical}
        width={1080}
        height={1920}
        fps={24}
        durationInFrames={1}
        defaultProps={{}}
        calculateMetadata={reportMeta}
      />
      <Composition
        id="CoverCard"
        component={CoverCard}
        width={1080}
        height={1920}
        fps={24}
        durationInFrames={1}
        defaultProps={{}}
      />
      <Composition
        id="Phase0Probe"
        component={Phase0Probe}
        width={1080}
        height={1920}
        fps={24}
        durationInFrames={150}
      />
    </>
  );
};
