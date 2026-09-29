// drama-vertical 样式集 —— 自 ceo_mindread_ep01/scripts/burn_subtitles_v2.py STYLES 逐字段移植。
// 设计稿 1080×1920。样式改动必须双端同步（qa_final.py 引用 PIL 侧同源数值）。

import type {StyleSet} from '../common/styleSet';

export const DRAMA_STYLES: StyleSet = {
  designWidth: 1080,
  designHeight: 1920,
  defaultStyle: 'normal',
  priority: ['special', 'opening', 'ending', 'normal', 'inner_special', 'inner'],
  styles: {
    normal:        {fontSize: 56, color: '#FFFFFF', strokeColor: '#000000', strokePx: 3, yPx: 1620, maxWidthPx: 1000, movable: true},
    inner:         {fontSize: 52, color: '#FFEB64', strokeColor: '#000000', strokePx: 3, yPx: 1620, maxWidthPx: 1000, movable: true},
    opening:       {fontSize: 72, color: '#FFFFFF', strokeColor: '#000000', strokePx: 4, yPx: 400,  maxWidthPx: 1000, movable: true},
    special:       {fontSize: 76, color: '#FF3232', strokeColor: '#FFFFFF', strokePx: 4, yPx: 1620, maxWidthPx: 1000, movable: true},
    inner_special: {fontSize: 64, color: '#FFEB64', strokeColor: '#000000', strokePx: 4, yPx: 1620, maxWidthPx: 1000, movable: true},
    ending:        {fontSize: 72, color: '#FFFFFF', strokeColor: '#000000', strokePx: 4, yPx: 1560, maxWidthPx: 1000, movable: true},
  },
};
