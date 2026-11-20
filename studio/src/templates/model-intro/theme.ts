/**
 * model-intro —— 视觉令牌。
 * 纯代码渲染（无生成模型）的自我介绍片：深色工程仪表风，冷青主色 + 紫色次级色。
 */

export const COLORS = {
  bg: '#05070C',
  ink: '#EAF2FA',
  dim: '#7C8DA3',
  /** 对底色约 4.6:1，达 WCAG AA；原先 #3E4B5C 只有 2.27:1，HUD/页脚几乎看不见。 */
  faint: '#5A6B80',
  accent: '#5CE1FF',
  accent2: '#A78BFA',
  ok: '#6EE7A8',
  panel: 'rgba(148, 200, 255, 0.045)',
  panelSolid: '#0A0F18',
  border: 'rgba(140, 200, 255, 0.14)',
  borderStrong: 'rgba(92, 225, 255, 0.42)',
} as const;

export const FONTS = {
  sans: '"Microsoft YaHei", "PingFang SC", SimHeiLocal, sans-serif',
  mono: '"Cascadia Mono", Consolas, "Courier New", monospace',
} as const;

/** 画面安全边距（1920×1080 基准）。 */
export const PAD = 96;

export const EASE = {
  out: [0.16, 1, 0.3, 1] as [number, number, number, number],
};
