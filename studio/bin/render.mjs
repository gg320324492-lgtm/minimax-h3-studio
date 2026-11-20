#!/usr/bin/env node
// 渲染桥：Python 管线 → 本脚本 → Remotion 渲染。
// 用法：
//   node bin/render.mjs --comp DramaVertical --props <props.json> --out <out.mp4>
//       [--codec h264] [--crf 18] [--bitrate 8M|14000K] [--hw disable|if-possible|required]
//       [--concurrency 8] [--pixelfmt yuv420p] [--imageformat jpeg] [--colorspace bt709]
//       [--gate-props] [--py <python>]
// bundle 在单次进程内复用；批量产能升级为常驻服务是 Phase 4 事项。
//
// --gate-props: 渲染前跑 studio/scripts/visual_qa.py --props，红则不渲（P25）。
// 默认关，因为 --props 也吃非图谱的 timeline/report props，那类图谱会被报
// UNVERIFIABLE 而非零退出（6e86b46 立的规矩，本项不动它）。

import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
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
// `gate-props` and `py` are here for the same reason `pixelfmt` is: they are
// read INSIDE the gate call below, not by `get()` at the top, so a list derived
// from the parsing helpers still would not find them. `py` exists because the
// gate needs an interpreter and the renderer's Python is not on PATH by default
// — measured here, where `python` resolves to a 3.10 build and `py -3.12` is
// what the test suite runs on.
//
// There are NO boolean flags other than the one named below, and it is the only
// one: nothing here is consumed as `argv.includes(...)` for anything else, so
// every other flag takes a value. still.mjs has `--clean` precisely because it
// reads one; render.mjs has nothing of the kind. Reject `--clean` here like
// any other unknown, rather than quietly accepting a flag that does nothing.
const VALUE_FLAGS = new Set([
  'comp', 'props', 'out',            // required
  'codec', 'crf', 'bitrate', 'hw', 'concurrency',   // read at the top
  'pixelfmt', 'imageformat', 'colorspace',         // read inline in renderMedia()
  'py',                                               // read inside runGates()
]);
// The ONE boolean flag, and it is the only one — see the comment above. It lives
// in BOOL_FLAGS only, NOT in VALUE_FLAGS: a flag in both sets would be reported
// twice, and `tests/test_p14_render_entry_points.py` parses this message to build
// its own copy of the surface. One flag, one set.
const BOOL_FLAGS = new Set(['gate-props']);
for (const a of argv) {
  if (!a.startsWith('--')) continue;
  const name = a.slice(2);
  if (!VALUE_FLAGS.has(name) && !BOOL_FLAGS.has(name)) {
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
const qaScript = fileURLToPath(new URL('../scripts/visual_qa.py', import.meta.url));

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

// P25 — 把 props 质量闸接进渲染路径。之前这里没有任何 QA 调用：一份 graph
// 指向没有渲染器的 scene 类型（渲染出来是 "not implemented in P4" 占位帧），
// 整片照渲、照产出、照退出 0，CI 里看不出任何东西。
//
// 位置在 bundle 之前 —— 实测这件事的顺序就是成本：闸读的是 props，红的时候
// 1.5 秒就有结果，渲染要 20 秒，而 bundle 本身还要 1.2 秒 + 800 MB 磁盘。
// 所以「QA 红了片子已经产出」这个问题在这个接点上不存在：被拒的图谱一个
// mp4 都不会留下，bundle 目录也已经建好但由上面同一个 cleanUp 覆盖。
//
// 为什么只接 props、不接逐帧：实测（E:/Minimax-H3，同 commit）：
//   整片渲染             19.6–22.5 s
//   整片解码成 801 张 PNG  1.324 s      —— 解码不是瓶颈，1.3 秒
//   单帧 run_on_frame    中位 1.61 s    —— 其中 rule_black_frame 占 1.18 s
//                             （np.unique 扫 1920x1080x3 是仪器本身，不是帧）
//   逐帧跑完整片         1.61 × 801 ≈ 21.5 min —— 渲染的 57–69 倍
// 逐帧闸不是接不起，是接了以后每次渲染要多等二十来分钟，而它能抓的那几条
// （safe_area / clipping / black_frame / blur）在 props 这一层一条都看不见。
// 所以本项接 props 闸；逐帧闸要先有便宜的仪器，那是另一次裁定。
//
// ⚠️ 没有放宽任何判定：这里只读 visual_qa.py 的退出码并原样转报。
// UNVERIFIABLE 仍然非零（6e86b46），FAIL 仍然非零，UNAVAILABLE 仍然不计入。
// 本文件不改 visual_qa.py 的四态语义，也不改任何阈值。
const runGates = () => `${get('py', 'py -3.12')} ${qaScript} --props ${propsPath}`;

if (argv.includes('--gate-props')) {
  const pyArgs = get('py', 'py -3.12').split(' ').filter(Boolean);
  console.log(`[render.mjs] QA GATE (props): ${runGates()}`);
  const gateStart = Date.now();
  const gate = spawnSync(pyArgs[0], [...pyArgs.slice(1), qaScript,
    '--props', propsPath], {
    cwd: path.dirname(fileURLToPath(import.meta.url)) + '/..',
    encoding: 'utf8',
    // 报告里有 CJK。不设它，GBK stdout 会在第一个非 ASCII 字符上抛
    // UnicodeEncodeError，闸看起来像崩了而不是像红了。
    env: {...process.env, PYTHONIOENCODING: 'utf-8'},
  });
  if (gate.stdout) process.stdout.write(gate.stdout);
  if (gate.stderr) process.stderr.write(gate.stderr);
  const gateCode = gate.status === null ? -1 : gate.status;
  console.log(
    `[render.mjs] QA GATE (props): exit ${gateCode} in ` +
      `${((Date.now() - gateStart) / 1000).toFixed(1)}s — ` +
      (gateCode === 0
        ? 'graph accepted'
        : `graph REJECTED, nothing was rendered and ${out} was not written`)
  );
  if (gateCode !== 0) {
    // 退出码就是闸的退出码，原样转报 —— 这样 CI 看到的红和直接跑
    // `visual_qa.py --props` 看到的红是同一个码。不改它、不吞它、不折中。
    // spawnSync 拿不到 status 时（信号杀死、ENOENT）报 3，因为 1 是「图谱有问题」
    // 的含义，拿一个「闸根本没跑起来」去冒充它会把工具故障说成质量问题。
    process.exit(gateCode === -1 ? 3 : gateCode);
  }
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
