#!/usr/bin/env node
// 抽帧工具：只渲指定的单帧，不渲整片。
//
// 为什么需要它：验收构图必须落到像素上。渲整片再 ffmpeg 抽帧要几分钟，
// 而且一旦改一个数就得重跑一遍。这里 bundle 一次，直接从 Remotion 取帧，
// 改一个数到看到结果是一轮 bundle 而已。
//
// 用法：
//   node bin/still.mjs --comp FinanceShowcaseWide --props <props.json> \
//       --out <dir> --frames 260,300,400,455

import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';

const argv = process.argv.slice(2);
const get = (key, fallback) => {
  const i = argv.indexOf(`--${key}`);
  return i >= 0 && i + 1 < argv.length ? argv[i + 1] : fallback;
};
const requireArg = (key) => {
  const v = get(key);
  if (!v) {
    console.error(`Missing required --${key}`);
    process.exit(2);
  }
  return v;
};

const comp = requireArg('comp');
const propsPath = requireArg('props');
const outDir = requireArg('out');
const frames = requireArg('frames')
  .split(',')
  .map((s) => Number(s.trim()))
  .filter((n) => Number.isFinite(n));
if (!frames.length) {
  console.error('--frames must be a comma-separated list of integers');
  process.exit(2);
}

const entryPoint = fileURLToPath(new URL('../src/index.ts', import.meta.url));
const inputProps = JSON.parse(fs.readFileSync(path.resolve(propsPath), 'utf8'));

const t0 = Date.now();
const serveUrl = await bundle({entryPoint, onProgress: undefined});
console.log(`[still] bundle ${((Date.now() - t0) / 1000).toFixed(1)}s`);

const composition = await selectComposition({serveUrl, id: comp, inputProps});
console.log(
  `[still] ${composition.id} ${composition.width}x${composition.height}@${composition.fps} ` +
    `${composition.durationInFrames} frames`
);

fs.mkdirSync(path.resolve(outDir), {recursive: true});
for (const frame of frames) {
  const output = path.resolve(outDir, `f${String(frame).padStart(5, '0')}.png`);
  await renderStill({composition, serveUrl, output, frame, inputProps, imageFormat: 'png'});
  console.log(`[still] frame ${frame} -> ${output}`);
}
