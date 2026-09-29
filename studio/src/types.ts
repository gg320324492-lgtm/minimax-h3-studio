// Phase 0 的 props 类型是轻量 TS 类型；Phase 1 升级为 zod schema（唯一契约）。

export type VideoFormat = {
  width: number;
  height: number;
  fps: number;
};

export type Shot = {
  id: string;
  file: string; // public/ 下的相对路径，如 jobs/phase0/S01.mp4
  durationInFrames: number;
  trimBefore?: number; // 源片段起始帧（帧级裁剪）
};

export type SubtitleEvent = {
  id: string;
  text: string;
  style: string; // normal | inner | opening | special | inner_special | ending
  start: number; // 秒（与 timeline v1 语义一致）
  end: number;
};

export type DramaProps = {
  version: number;
  project: string;
  format: VideoFormat;
  shots: Shot[];
  audioBus: {
    premixed: string; // mix_audio 产出的成品混音轨（含音轨的 mp4/m4a 均可）
  };
  subtitles: SubtitleEvent[];
};
