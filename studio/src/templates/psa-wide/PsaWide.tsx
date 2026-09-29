import React from 'react';
import {TimelineV2Schema} from '../../schemas/timeline-v2';
import {TimelinePlayer} from '../common/TimelinePlayer';
import {PSA_STYLES} from './styles';

// psa-wide = TimelinePlayer × 1920×1080 × piyao 样式集
export const PsaWide: React.FC<Record<string, unknown>> = (rawProps) => {
  const tl = TimelineV2Schema.parse(rawProps);
  return <TimelinePlayer tl={tl} styleSet={PSA_STYLES} />;
};
