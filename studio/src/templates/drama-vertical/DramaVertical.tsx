import React from 'react';
import {TimelineV2Schema} from '../../schemas/timeline-v2';
import {TimelinePlayer} from '../common/TimelinePlayer';
import {DRAMA_STYLES} from './styles';

// drama-vertical = TimelinePlayer × 1080×1920 × EP01 样式集
export const DramaVertical: React.FC<Record<string, unknown>> = (rawProps) => {
  const tl = TimelineV2Schema.parse(rawProps);
  return <TimelinePlayer tl={tl} styleSet={DRAMA_STYLES} />;
};
