// psa-wide 样式集 —— 自 piyao_2026/scripts/burn_subtitles.py STYLES 逐字段移植。
// 设计稿 1920×1080（MAX_TEXT_WIDTH=1700）。msg/step/card/title/corner 为屏幕固定元素
//（手机弹窗/步骤条/角标），不可参与碰撞错行；end_ai 为浅色药丸底板（radius 999）。

import type {StyleSet} from '../common/styleSet';
import {rgba} from '../common/styleSet';

export const PSA_STYLES: StyleSet = {
  designWidth: 1920,
  designHeight: 1080,
  defaultStyle: 'narr',
  priority: ['slogan', 'hook', 'narr', 'end_slogan', 'end_theme', 'end_title', 'end_ai', 'end_note'],
  styles: {
    narr:       {fontSize: 54, color: '#FFFFFF', strokeColor: '#000000', strokePx: 3, yPx: 962,  maxWidthPx: 1700, movable: true},
    hook:       {fontSize: 64, color: rgba(255, 235, 120, 255), strokeColor: '#000000', strokePx: 3, yPx: 900, maxWidthPx: 1700, movable: true},
    slogan:     {fontSize: 68, color: rgba(255, 210, 77, 255), strokeColor: '#000000', strokePx: 4, yPx: 890, maxWidthPx: 1700, movable: true},
    msg:        {fontSize: 46, color: '#FFFFFF', yPx: 150, maxWidthPx: 900, movable: false,
                 bg: {color: rgba(18, 22, 32, 215), padX: 46, padY: 26, radius: 22}},
    step:       {fontSize: 76, color: '#FFFFFF', yPx: 170, maxWidthPx: 1100, movable: false,
                 bg: {color: rgba(24, 58, 118, 200), padX: 60, padY: 30, radius: 26}},
    card:       {fontSize: 58, color: rgba(255, 235, 120, 255), yPx: 820, maxWidthPx: 1100, movable: false,
                 bg: {color: rgba(10, 12, 18, 200), padX: 50, padY: 26, radius: 20}},
    title:      {fontSize: 44, color: rgba(255, 255, 255, 235), strokeColor: rgba(0, 0, 0, 200), strokePx: 2, yPx: 96, maxWidthPx: 1700, movable: false},
    corner:     {fontSize: 27, color: rgba(215, 215, 215, 185), strokeColor: rgba(0, 0, 0, 140), strokePx: 2, yPx: 1032, maxWidthPx: 600, align: 'left', xPx: 40, movable: false},
    end_slogan: {fontSize: 96, color: '#FFFFFF', strokeColor: '#000000', strokePx: 4, yPx: 380, maxWidthPx: 1700, movable: true},
    end_theme:  {fontSize: 60, color: rgba(255, 210, 77, 255), strokeColor: rgba(0, 0, 0, 220), strokePx: 3, yPx: 548, maxWidthPx: 1700, movable: true},
    end_title:  {fontSize: 34, color: rgba(205, 214, 228, 255), yPx: 688, maxWidthPx: 1700, movable: true},
    end_ai:     {fontSize: 40, color: rgba(16, 22, 34, 255), yPx: 790, maxWidthPx: 900, movable: true,
                 bg: {color: rgba(240, 243, 248, 235), padX: 36, padY: 18, radius: 999}},
    end_note:   {fontSize: 28, color: rgba(150, 160, 176, 220), yPx: 920, maxWidthPx: 1700, movable: true},
  },
};
