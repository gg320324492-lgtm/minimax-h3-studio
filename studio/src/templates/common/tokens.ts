// 字幕样式令牌 —— 自 ceo_mindread_ep01/scripts/burn_subtitles_v2.py 的 STYLES 字典
// 逐字段精确移植（2026-09-29 版本）。样式改动必须双端同步，qa_final.py 的字幕宽度
// 检查引用 PIL 侧同源数值。
// 坐标系：1080×1920 设计稿（y 为 PIL draw.text 的 top 像素）。

export type SubtitleToken = {
  fontSize: number;
  color: string;
  strokeColor: string;
  strokePx: number;
  /** 1080×1920 设计稿中的 top 像素 */
  yPx: number;
  maxWidthPx: number;
};

export const SUBTITLE_STYLES: Record<string, SubtitleToken> = {
  normal:        {fontSize: 56, color: '#FFFFFF', strokeColor: '#000000', strokePx: 3, yPx: 1620, maxWidthPx: 1000},
  inner:         {fontSize: 52, color: '#FFEB64', strokeColor: '#000000', strokePx: 3, yPx: 1620, maxWidthPx: 1000},
  opening:       {fontSize: 72, color: '#FFFFFF', strokeColor: '#000000', strokePx: 4, yPx: 400,  maxWidthPx: 1000},
  special:       {fontSize: 76, color: '#FF3232', strokeColor: '#FFFFFF', strokePx: 4, yPx: 1620, maxWidthPx: 1000},
  inner_special: {fontSize: 64, color: '#FFEB64', strokeColor: '#000000', strokePx: 4, yPx: 1620, maxWidthPx: 1000},
  ending:        {fontSize: 72, color: '#FFFFFF', strokeColor: '#000000', strokePx: 4, yPx: 1560, maxWidthPx: 1000},
};

export const FALLBACK_STYLE: SubtitleToken = SUBTITLE_STYLES.normal;

// PIL 的 stroke 画在字形轮廓外侧 sw 像素；-webkit-text-stroke 以轮廓为中心，
// 宽度乘 2 补差（外露 ≈ sw px）。fill 在 stroke 之上（paintOrder）保持字面完整。
export const webkitStrokeWidth = (sw: number): number => sw * 2;

// PIL 主字体是 msyh.ttc（微软雅黑），与 headless Chrome 的系统 "Microsoft YaHei"
// 同字形；自托管 SimHeiLocal 仅作兜底（跨机可移植）。
export const CAPTION_FONT = '"Microsoft YaHei", SimHeiLocal, sans-serif';
