// 样式集类型 —— 每个模板一套（从各项目 burn_subtitles 的 STYLES 字典移植）。
// 坐标系：designWidth × designHeight 设计稿内的像素（y 为 PIL draw.text 的 top）。

export type SubtitleToken = {
  fontSize: number;
  color: string;
  strokeColor?: string;
  /** 无描边的样式（box 底板类）省略，按 0 处理 */
  strokePx?: number;
  yPx: number;
  maxWidthPx: number;
  /** 默认 center；left 时用 xPx */
  align?: 'center' | 'left';
  xPx?: number;
  /** 底板（PIL box：圆角矩形垫在文字后） */
  bg?: {color: string; padX: number; padY: number; radius: number};
  /** 400/700 —— liaozhai 用雅黑粗体（msyhbd） */
  fontWeight?: number;
  /** 可参与碰撞错行的"字幕类"样式（msg/step/corner 等屏幕固定元素不可动） */
  movable: boolean;
};

export type StyleSet = {
  designWidth: number;
  designHeight: number;
  styles: Record<string, SubtitleToken>;
  /** 碰撞时优先占用原位的样式名（高 → 低）；不在表内的样式排最后 */
  priority: string[];
  defaultStyle: string;
};

export const rgba = (r: number, g: number, b: number, a: number): string =>
  `rgba(${r},${g},${b},${(a / 255).toFixed(3)})`;

// PIL stroke 画在轮廓外侧 sw px；-webkit-text-stroke 以轮廓为中心，×2 补差
export const webkitStrokeWidth = (sw: number): number => sw * 2;

export const CAPTION_FONT = '"Microsoft YaHei", SimHeiLocal, sans-serif';

/** CJK 估行数：全角字符宽 ≈ fontSize */
export const estimateLines = (text: string, token: SubtitleToken): number => {
  const effLen = [...text].reduce((n, ch) => n + (ch.charCodeAt(0) > 0x2e80 ? 1 : 0.55), 0);
  return Math.max(1, Math.ceil((effLen * token.fontSize) / token.maxWidthPx));
};
