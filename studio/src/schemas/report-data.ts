// report-data —— 模式 B（纯程序化数据视频）的 props 契约。
// 与 timeline-v2 并行的第二类输入：无 AI 片段、无 GPU，全部视觉由数据驱动生成。
// 修改后运行 `pnpm exec tsx bin/export-schema.ts`（同时导出两份 schema）。

import {z} from 'zod';

export const StatSchema = z.object({
  label: z.string(),
  value: z.string(), // 已格式化的展示值，如 "48.2亿"
  delta: z.string().optional(), // 如 "+12%"（正绿负红由模板按符号判断）
  note: z.string().optional(),
});

export const ChartItemSchema = z.object({
  label: z.string(),
  value: z.number().nonnegative(),
  note: z.string().optional(),
});

export const ChartSchema = z.object({
  title: z.string().optional(),
  type: z.enum(['bar', 'rank']).default('bar'),
  unit: z.string().optional(),
  items: z.array(ChartItemSchema).min(1),
});

export const ReportNarrationSchema = z.object({
  src: z.string(), // public/ 相对路径（jobs/<job>/...）
  volume: z.number().min(0).max(1).default(0.25),
  /** 离线预计算的每帧低频能量（make_audio_assets.py 产出）——有它渲染端零 FFT 成本 */
  pumpEnvelope: z
    .object({
      fps: z.number().int().positive(),
      values: z.array(z.number()).min(1),
    })
    .optional(),
  subtitles: z
    .array(
      z.object({
        text: z.string(),
        start: z.number().nonnegative(),
        end: z.number().positive(),
      })
    )
    .default([]),
});

export const ReportDataSchema = z.object({
  version: z.literal(2),
  project: z.string().min(1),
  template: z.literal('report-vertical'),
  format: z.object({
    width: z.number().int().positive(),
    height: z.number().int().positive(),
    fps: z.number().int().positive(),
  }),
  title: z.string().min(1),
  subtitle: z.string().optional(),
  badge: z.string().optional(),
  accentColor: z.string().default('#FFD866'),
  /** 卡点：分段起点量化到该 BPM 的拍边界（配合合成的 bgm_tech_126 用 126） */
  bpm: z.number().min(60).max(200).default(126),
  /** 自动音效：分段边界铺设 whoosh（提前量）+ impact（落点），要点段 ding，outro 前 riser */
  sfxAuto: z.boolean().default(true),
  stats: z.array(StatSchema).default([]),
  chart: ChartSchema.optional(),
  takeaways: z.array(z.string()).default([]),
  outro: z
    .object({
      slogan: z.string(),
      sub: z.string().optional(),
    })
    .optional(),
  narration: ReportNarrationSchema.optional(),
});

export type Stat = z.infer<typeof StatSchema>;
export type ChartSpec = z.infer<typeof ChartSchema>;
export type ReportData = z.infer<typeof ReportDataSchema>;

// 自动时间轴（秒）：title 3 → 每条 stat 2.4 → chart 5+0.9×条目 → 每条 takeaway 2.4 → outro 3
export const reportSections = (d: ReportData) => {
  const sections: Array<{kind: string; start: number; end: number; index?: number}> = [];
  let t = 0;
  sections.push({kind: 'title', start: t, end: (t += 3)});
  d.stats.forEach((_, i) => {
    sections.push({kind: 'stat', start: t, end: (t += 2.4), index: i});
  });
  if (d.chart) {
    sections.push({kind: 'chart', start: t, end: (t += 5 + d.chart.items.length * 0.9)});
  }
  d.takeaways.forEach((_, i) => {
    sections.push({kind: 'takeaway', start: t, end: (t += 2.4), index: i});
  });
  if (d.outro) {
    sections.push({kind: 'outro', start: t, end: (t += 3)});
  }
  // 无任何分段时至少给标题 3s
  return sections.length > 1 ? sections : [{kind: 'title', start: 0, end: 3}];
};

export const reportDurationSeconds = (d: ReportData): number => {
  const s = reportSections(d);
  return s[s.length - 1].end;
};
