import React from 'react';
import {TimelineV2Schema} from '../../schemas/timeline-v2';
import {TimelinePlayer} from '../common/TimelinePlayer';
import {STORY_STYLES} from './styles';

// story-animation = TimelinePlayer × 2560×1440（样式坐标按 1920×1080 设计稿等比 1.333 映射）× liaozhai 样式集
export const StoryAnimation: React.FC<Record<string, unknown>> = (rawProps) => {
  const tl = TimelineV2Schema.parse(rawProps);
  return <TimelinePlayer tl={tl} styleSet={STORY_STYLES} />;
};
