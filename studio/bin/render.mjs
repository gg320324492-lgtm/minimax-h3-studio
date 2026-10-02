#!/usr/bin/env node
// 渲染桥：Python 管线 → 本脚本 → Remotion 渲染。
// 用法：
//   node bin/render.mjs --comp DramaVertical --props <props.json> --out <out.mp4>
//       [--codec h264] [--crf 18] [--bitrate 8M|14000K] [--hw disable|if-possible|required]
//       [--concurrency 8] [--pixelfmt yuv420p] [--imageformat jpeg] [--colorspace bt709]
// bundle 在单次进程内复用；批量产能升级为常驻服务是 Phase 4 事项。

import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';

const argv = process.argv.slice(2);
const get = (key, fallback) => {
  const i = argv.indexOf(`--${key}`);
  if (i >= 0 && i + 1 < argv.length) {
    return argv[i + 1];
  }
  return fallback;
};
const requireArg = (key) => {
  const v = get(key);
  if (!v) {
    console.error(`Missing required --${key}`);
    process.exit(2);
  }
  return v;
};
// Hand-rolled flag parsing is why `--frames 10` where `--frame` was meant used
// to render the whole film and exit 0. still.mjs got this check first and says
// why in its own comment; render.mjs did not, and the two entry points then
// disagreed about the same mistake. A typo here that lands on a flag WITH a
// default cannot be caught by requireArg at all — `--cosdec vp9` (codec)
// leaves h264 in place, renders, and exits 0, so the caller sees a perfectly
// plausible file. Unknown flags are now an error, for the same reason still.mjs
// makes them one: a typo that silently selects different settings produces a
// wrong film rather than a failure.
//
// The known set is every `--name` this file reads, by hand, because `get()`
// hides them: the three required, the six read at the top, and the three read
// inline inside renderMedia() (pixelfmt / imageformat / colorspace). Those last
// three are the ones a list derived from the parsing helpers would miss, and
// they are documented only by the usage comment above until this file landed.
//
// There are NO boolean flags: nothing here is consumed as `argv.includes(...)`,
// so every flag takes a value. still.mjs has `--clean` precisely because it
// reads one; render.mjs has nothing of the kind. Reject `--clean` here like
// any other unknown, rather than quietly accepting a flag that does nothing.
const VALUE_FLAGS = new Set([
  'comp', 'props', 'out',            // required
  'codec', 'crf', 'bitrate', 'hw', 'concurrency',   // read at the top
  'pixelfmt', 'imageformat', 'colorspace',         // read inline in renderMedia()
]);
for (const a of argv) {
  if (!a.startsWith('--')) continue;
  const name = a.slice(2);
  if (!VALUE_FLAGS.has(name)) {
    console.error(
      `Unknown flag --${name}. Known value flags: ` +
        `${[...VALUE_FLAGS].map((f) => '--' + f).join(', ')}`
    );
    process.exit(2);
  }
}

const comp = requireArg('comp');
const propsPath = requireArg('props');
const out = requireArg('out');
const codec = get('codec', 'h264');
const crf = get('crf') ? Number(get('crf')) : undefined;
const bitrate = get('bitrate'); // 字符串，形如 "8M" / "14000K"
const hw = get('hw', 'disable');
const concurrency = get('concurrency') ? Number(get('concurrency')) : undefined;

const entryPoint = fileURLToPath(new URL('../src/index.ts', import.meta.url));

// The bundle is ~800 MB and it is scratch: it exists only while this process
// runs. Left to itself `bundle()` writes it to os.tmpdir() via mkdtemp and
// NEVER deletes it (prepareOutDir in @remotion/bundler), so every render leaks
// one copy of studio/public onto the system drive — 118 of them filled a C:
// TEMP to 46 GB. Passing an explicit outDir only MOVES the leak, so the
// directory has to be ours and it has to be removed in a finally, including
// when the render throws.
//
// mkdtemp under a repo-local .remotion/ (already gitignored): the scratch goes
// on the drive the repo lives on rather than on C:, and a per-run name keeps
// two concurrent renders from sharing one directory.
const scratchRoot = process.env.REMOTION_SCRATCH_DIR
  ?? path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '.remotion', 'bundle');
fs.mkdirSync(scratchRoot, {recursive: true});
const bundleDir = fs.mkdtempSync(path.join(scratchRoot, 'render-'));

// A failure below must not leave an 800 MB directory behind, and neither must a
// Ctrl-C: the exit handler runs on SIGINT, the finally does not.
let cleanedUp = false;
const cleanUp = () => {
  if (cleanedUp) return;
  cleanedUp = true;
  fs.rmSync(bundleDir, {recursive: true, force: true});
};
process.on('exit', cleanUp);
for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => {
    cleanUp();
    process.exit(130);
  });
}

try {
  const t0 = Date.now();
  console.log(`[render.mjs] bundling…`);
  const serveUrl = await bundle({
    entryPoint,
    outDir: bundleDir,
    onProgress: (p) => {
      if (p % 25 === 0) {
        console.log(`[render.mjs] bundle ${p}%`);
      }
    },
  });
  console.log(`[render.mjs] bundle done in ${((Date.now() - t0) / 1000).toFixed(1)}s`);

  const inputProps = JSON.parse(fs.readFileSync(path.resolve(propsPath), 'utf8'));

  const t1 = Date.now();
  const composition = await selectComposition({serveUrl, id: comp, inputProps});
  console.log(
    `[render.mjs] composition ${composition.width}x${composition.height}@${composition.fps} ` +
      `${composition.durationInFrames}f, metadata in ${((Date.now() - t1) / 1000).toFixed(1)}s`
  );

  await renderMedia({
    composition,
    serveUrl,
    codec,
    inputProps,
    outputLocation: path.resolve(out),
    // Node API 不读 remotion.config.ts（仅 CLI 生效），必须显式传：
    // jpeg 截帧默认产出 yuvj420p（full range），qa_final.py 要求 yuv420p。
    pixelFormat: get('pixelfmt', 'yuv420p'),
    imageFormat: get('imageformat', 'jpeg'),
    // bt709 是 Phase 0 实测定稿：jpeg 截帧下把输出转为 yuv420p/tv range（否则 yuvj420p 挂 QA），
    // 速度无损耗。基准数据见 BENCHMARK_20260929.md。
    colorSpace: get('colorspace', 'bt709'),
    ...(crf !== undefined ? {crf} : {}),
    ...(bitrate !== undefined ? {videoBitrate: bitrate} : {}),
    hardwareAcceleration: hw,
    ...(concurrency !== undefined ? {concurrency} : {}),
    onProgress: ({progress}) => {
      const pct = Math.floor(progress * 100);
      if (pct % 10 === 0) {
        console.log(`[render.mjs] render ${pct}%`);
      }
    },
  });

  console.log(`[render.mjs] DONE ${out} in ${((Date.now() - t0) / 1000).toFixed(1)}s total`);
} finally {
  cleanUp();
}
