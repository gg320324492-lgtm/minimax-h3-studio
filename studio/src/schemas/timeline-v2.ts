// timeline-v2 —— Python 管线 ↔ Remotion 渲染层的唯一契约。
// 修改本文件后必须运行 `pnpm exec tsx bin/export-schema.ts` 重新导出 JSON Schema，
// Python 侧（stage_assets.py）以导出的 timeline-v2.schema.json 校验 props。
// 行级字段语义与 timeline v1 完全兼容（秒、样式名、文件路径）。

import {z} from 'zod';

export const TemplateName = z.enum(['drama-vertical', 'psa-wide', 'story-animation']);

export const SubtitleStyleName = z.string().min(1); // 样式名由各模板的样式集解释

export const ShotSchema = z.object({
  id: z.string().min(1),
  /** 项目相对路径（build_timeline 产出），staging 后改写为 jobs/<job>/... */
  file: z.string().min(1),
  /** 源片段起始帧（帧级裁剪，生成长度≠呈现长度时使用） */
  trimBefore: z.number().int().nonnegative().default(0),
  durationInFrames: z.number().int().positive(),
  /** 入场转场（帧内动画，不改变时间轴——对白/音效的绝对秒不受影响） */
  transitionIn: z
    .object({
      type: z.enum(['none', 'fade', 'flash']).default('none'),
      durationInFrames: z.number().int().nonnegative().default(0),
    })
    .default({type: 'none', durationInFrames: 0}),
});

export const SubtitleEventSchema = z.object({
  id: z.string().min(1),
  text: z.string(),
  style: SubtitleStyleName,
  /** 绝对秒（与 v1 语义一致） */
  start: z.number().nonnegative(),
  end: z.number().positive(),
  /** 词级时间戳（卡拉OK渲染；w 为 ASR 词面，t/d 秒。由 word_timestamps.py 注入） */
  words: z
    .array(
      z.object({
        w: z.string().min(1),
        t: z.number().nonnegative(),
        d: z.number().positive(),
      })
    )
    .optional(),
});

export const OverlaySchema = z.discriminatedUnion('kind', [
  z.object({
    kind: z.literal('text'),
    text: z.string(),
    style: SubtitleStyleName,
    start: z.number(),
    end: z.number(),
    /** 入场动画：pop=弹入（默认），rise=上浮，none */
    anim: z.enum(['pop', 'rise', 'none']).default('pop'),
  }),
  z.object({
    kind: z.literal('progress'),
    start: z.number(),
    end: z.number(),
  }),
  z.object({
    kind: z.literal('lower-third'),
    title: z.string(),
    sub: z.string().optional(),
    start: z.number(),
    end: z.number(),
  }),
]);

/** 片头卡：位于全部 shots 之前（liaozhai 模式，timeline 的 shot 从卡后起算） */
export const TitleCardSchema = z.object({
  durationInFrames: z.number().int().positive(),
  lines: z
    .array(
      z.object({
        text: z.string(),
        style: SubtitleStyleName,
      })
    )
    .default([]),
  background: z.enum(['black', 'gradient']).default('black'),
});

/** 结束卡：位于全部 shots 之后（piyao/liaozhai 的 endcard 段） */
export const EndCardSchema = z.object({
  durationInFrames: z.number().int().positive(),
  lines: z
    .array(
      z.object({
        text: z.string(),
        style: SubtitleStyleName,
      })
    )
    .default([]),
  background: z.enum(['black', 'gradient']).default('black'),
});

export const TimelineV2Schema = z.object({
  version: z.literal(2),
  project: z.string().min(1),
  template: TemplateName,
  format: z.object({
    width: z.number().int().positive(),
    height: z.number().int().positive(),
    fps: z.number().int().positive(),
  }),
  totalDuration: z.number().nonnegative(),
  /** 片段适配：fill=拉伸（与超分链几何一致），cover=裁切填满 */
  fit: z.enum(['cover', 'fill']).default('fill'),
  shots: z.array(ShotSchema).min(1),
  /** mix_audio 产出的成品混音轨（单轨进渲染，响度工程留在 Python 侧） */
  audioBus: z.object({
    premixed: z.string().min(1),
  }),
  subtitles: z.array(SubtitleEventSchema).default([]),
  overlays: z.array(OverlaySchema).default([]),
  titlecard: TitleCardSchema.optional(),
  endcard: EndCardSchema.optional(),
});

export type Shot = z.infer<typeof ShotSchema>;
export type SubtitleEvent = z.infer<typeof SubtitleEventSchema>;
export type Overlay = z.infer<typeof OverlaySchema>;
export type TitleCard = z.infer<typeof TitleCardSchema>;
export type EndCard = z.infer<typeof EndCardSchema>;
export type TimelineV2 = z.infer<typeof TimelineV2Schema>;
