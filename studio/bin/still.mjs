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
// Hand-rolled flag parsing is why `--frames` where `--frame` was meant used to
// fall through to a default instead of complaining. Unknown flags are now an
// error, because a typo that silently selects a different frame produces a
// well-formed number describing the wrong picture — the exact failure the A/B
// guard exists to prevent, one level up.
const VALUE_FLAGS = new Set(['comp', 'props', 'out', 'frames', 'public-dir']);
const BOOL_FLAGS = new Set(['clean']);
for (const a of argv) {
  if (!a.startsWith('--')) continue;
  const name = a.slice(2);
  if (!VALUE_FLAGS.has(name) && !BOOL_FLAGS.has(name)) {
    console.error(
      `Unknown flag --${name}. Known value flags: ${[...VALUE_FLAGS].map((f) => '--' + f).join(', ')}; ` +
        `boolean flags: ${[...BOOL_FLAGS].map((f) => '--' + f).join(', ')}`
    );
    process.exit(2);
  }
}
const args = {clean: argv.includes('--clean')};

const comp = requireArg('comp');
const propsPath = requireArg('props');
const outArg = requireArg('out');
const frames = requireArg('frames')
  .split(',')
  .map((s) => Number(s.trim()))
  .filter((n) => Number.isFinite(n));
if (!frames.length) {
  console.error('--frames must be a comma-separated list of integers');
  process.exit(2);
}

/**
 * --out is a DIRECTORY, and a caller who passes a file path gets a directory
 * named after it — or a PermissionError, depending on what is already there.
 * Both were hit during review, each time silently enough to look like a render
 * bug. So: recognise a .png and honour it, otherwise say plainly that the value
 * is being used as a directory.
 */
const asFile = /\.png$/i.test(outArg);
const outDir = path.resolve(asFile ? path.dirname(outArg) : outArg);
const oneFile = asFile && frames.length === 1;
if (asFile && frames.length > 1) {
  console.error('--out names a .png but --frames lists more than one frame; pass a directory');
  process.exit(2);
}

if (args.clean && fs.existsSync(outDir)) {
  fs.rmSync(outDir, {recursive: true, force: true});
  console.log(`[still] --clean: emptied ${outDir}`);
}
if (!oneFile) {
  console.log(`[still] output directory: ${outDir}`);
  // Say what is already in there. A stale frame from an earlier run sitting
  // beside this run's frames is how a comparison tool ends up diffing two
  // different frames and reporting the difference as a result.
  if (fs.existsSync(outDir)) {
    const existing = fs.readdirSync(outDir).filter((f) => f.toLowerCase().endsWith('.png'));
    if (existing.length) {
      console.log(`[still] note: ${existing.length} pre-existing PNG(s) in that directory`);
      for (const f of existing) {
        console.log(`[still]   - ${f}${frames.includes(Number(f.slice(1, 6))) ? ' (will be overwritten)' : ' (kept)'}`);
      }
    }
  }
}

const entryPoint = fileURLToPath(new URL('../src/index.ts', import.meta.url));
const inputProps = JSON.parse(fs.readFileSync(path.resolve(propsPath), 'utf8'));

/**
 * Where the bundler copies the static files from.
 *
 * The default is studio/public, and studio/public holds 773 MB of staged job
 * props including EP01's mp4s — so every render copied 773 MB into a temp
 * directory. 125 of those had piled up to 58 GB and filled the system drive.
 * The static files a graph actually needs are the ones it references by name;
 * a graph that references none (no `audio.src`) needs an empty directory, and
 * saying so out loud beats silently shipping half a gigabyte per render.
 */
const publicDir = args.publicDir
  ? path.resolve(args.publicDir)
  : fileURLToPath(new URL('../public', import.meta.url));
if (!fs.existsSync(publicDir)) fs.mkdirSync(publicDir, {recursive: true});
const needsStatic = JSON.stringify(inputProps).includes('"src"');
if (args.publicDir && needsStatic) {
  console.error('--public-dir was given but the graph references a static file; ' +
    'staticFile() lookups will 404. Omit the flag for graphs that reference assets.');
  process.exit(2);
}

const t0 = Date.now();
const serveUrl = await bundle({entryPoint, publicDir, onProgress: undefined});
console.log(`[still] bundle ${((Date.now() - t0) / 1000).toFixed(1)}s`);

const composition = await selectComposition({serveUrl, id: comp, inputProps});
console.log(
  `[still] ${composition.id} ${composition.width}x${composition.height}@${composition.fps} ` +
    `${composition.durationInFrames} frames`
);

fs.mkdirSync(outDir, {recursive: true});
const written = [];
for (const frame of frames) {
  const name = `f${String(frame).padStart(5, '0')}.png`;
  const output = oneFile ? path.resolve(outArg) : path.join(outDir, name);
  await renderStill({composition, serveUrl, output, frame, inputProps, imageFormat: 'png'});
  written.push(output);
  console.log(`[still] frame ${frame} -> ${output}`);
}
console.log(`[still] wrote ${written.length} file(s) to ${outDir}`);
