// story-animation 样式集 —— 自 liaozhai_demo/scripts/burn_subtitles.py STYLES 逐字段移植。
// 设计稿 1920×1080（成片超分到 2560×1440，样式坐标随设计稿等比缩放）。
// 该项目字体偏好 msyhbd（雅黑粗体）→ 全样式 fontWeight 700。
// title_*/end_*/corner 为片头卡/结束卡/角标固定元素，不可移动。

import type {StyleSet} from '../common/styleSet';
import {rgba} from '../common/styleSet';

const GOLD = rgba(232, 196, 96, 255);
const PAPER = rgba(238, 232, 220, 255);
const GREY = rgba(178, 182, 192, 225);

export const STORY_STYLES: StyleSet = {
  designWidth: 1920,
  designHeight: 1080,
  defaultStyle: 'narr',
  priority: ['narr', 'title_main', 'title_sub', 'title_sub2', 'title_warn', 'end_main', 'end_title', 'end_ai', 'end_note'],
  styles: {
    narr:       {fontSize: 58, color: '#FFFFFF', strokeColor: '#000000', strokePx: 3, yPx: 952,  maxWidthPx: 1700, movable: true, fontWeight: 700},
    title_main: {fontSize: 138, color: GOLD, strokeColor: '#000000', strokePx: 5, yPx: 400, maxWidthPx: 1700, movable: false, fontWeight: 700},
    title_sub:  {fontSize: 46, color: PAPER, strokeColor: rgba(0, 0, 0, 200), strokePx: 2, yPx: 590, maxWidthPx: 1700, movable: false, fontWeight: 700},
    title_sub2: {fontSize: 38, color: GREY, yPx: 680, maxWidthPx: 1700, movable: false, fontWeight: 700},
    title_warn: {fontSize: 34, color: rgba(210, 205, 195, 235), yPx: 950, maxWidthPx: 1700, movable: false, fontWeight: 700},
    corner:     {fontSize: 27, color: rgba(215, 215, 215, 185), strokeColor: rgba(0, 0, 0, 140), strokePx: 2, yPx: 1032, maxWidthPx: 600, align: 'left', xPx: 40, movable: false, fontWeight: 700},
    end_main:   {fontSize: 88, color: PAPER, strokeColor: '#000000', strokePx: 4, yPx: 430, maxWidthPx: 1700, movable: false, fontWeight: 700},
    end_title:  {fontSize: 38, color: GREY, yPx: 580, maxWidthPx: 1700, movable: false, fontWeight: 700},
    end_ai:     {fontSize: 40, color: rgba(16, 22, 34, 255), yPx: 740, maxWidthPx: 900, movable: false,
                 bg: {color: rgba(240, 243, 248, 235), padX: 36, padY: 18, radius: 999}, fontWeight: 700},
    end_note:   {fontSize: 28, color: rgba(150, 158, 172, 220), yPx: 920, maxWidthPx: 1700, movable: false, fontWeight: 700},
  },
};
