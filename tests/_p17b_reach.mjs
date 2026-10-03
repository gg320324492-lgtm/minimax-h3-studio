// Does render.mjs's real top-level code actually reach the props gate?
//
// WHY THIS FILE EXISTS. A dynamic answer to a static question. The first two
// attempts were both wrong and are recorded here so the next person does not
// retry them:
//
//   1. A hand-written JS lexer inside the Python test. It swallowed every
//      template literal and everything after it, lost the ONE real call to
//      `runGates` because that call lives inside a `${…}` hole, and reported
//      the file's last (perfectly closed) template as unterminated.
//   2. Node's own parser — but Node does not expose one to user code without
//      acorn, which this repository does not depend on and must not be made to
//      depend on for a test.
//
// So the question is settled empirically instead: run the module's own
// top-level code and WATCH whether it spawns the gate.
//
//   * `if (false) { spawnSync(...) }`   -> nothing is spawned. reachable false.
//   * the branch deleted                -> nothing is spawned. false.
//   * `--gate-props` not in argv        -> nothing is spawned. false.
//   * the real wiring                   -> one spawn, carrying `--props`.
//
// Nothing here rewrites the gate or relaxes a check: `spawnSync` is replaced by
// a recorder and the filesystem and renderer are stubbed, then what the program
// actually did is reported. This is an OBSERVATION of render.mjs.
//
// CONTRACT. One JSON object on stdout. `ok` is false when the module could not
// be observed at all, and a caller must treat that as a FAILURE — never as
// "unreachable" and never as "reachable".
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const file = process.argv[2];
const withFlag = process.argv[3] !== 'off';
const src = readFileSync(file, 'utf8');

const record = {argv: [], exits: []};

// ── the module's imports, as data ──
// Parsed by regex rather than guessed at, and every id used must have a stub
// below; an unknown id throws, so a new import in render.mjs fails loudly
// instead of silently answering "not reachable".
// ANCHORED TO THE START OF A LINE, deliberately. An unanchored `import` scan
// matches prose: render.mjs's gate comment contains the words "import exit 1",
// and three revisions of this probe tried to require a module named `p` — a
// fragment of an English sentence. Anchoring is the whole fix.
//
// The NAMED shape is tried FIRST, because `import {a, b} from 'm'` also matches
// the default shape's `import (\w+) from` only if the brace were a word — it is
// not, so ordering matters only for the mixed form and costs nothing.
const IMPORTS = [
  [/^[ \t]*import\s+\{([^}]*)\}\s+from\s+['"]([^'"]+)['"]/gm,
   (g) => ({names: g[0].split(',').map((s) => s.trim()), mod: g[1],
           kind: 'named'})],
  [/^[ \t]*import\s+([\w$]+)\s*,\s*\{([^}]*)\}\s+from\s+['"]([^'"]+)['"]/gm,
   (g) => ({name: g[0], names: g[1].split(',').map((s) => s.trim()),
           mod: g[2], kind: 'mixed'})],
  [/^[ \t]*import\s+([\w$]+)\s+from\s+['"]([^'"]+)['"]/gm,
   (g) => ({name: g[0], mod: g[1], kind: 'default'})],
  [/^[ \t]*import\s+\*\s+as\s+([\w$]+)\s+from\s+['"]([^'"]+)['"]/gm,
   (g) => ({name: g[0], mod: g[1], kind: 'namespace'})],
];

const stubs = {
  'node:fs': {
    mkdirSync() {}, mkdtempSync() { return 'probe-bundle'; },
    rmSync() {}, writeFileSync() {},
    readFileSync() {
      return JSON.stringify({
        version: 1, project: 'p17',
        format: {width: 1920, height: 1080, fps: 60},
        scenes: [{id: 's1', type: 'kpi-hero', durationInFrames: 1,
                  content: {value: 1, label: 'x'}}],
      });
    },
  },
  'node:path': {
    join: (...a) => a.join('/'),
    resolve: (...a) => a.join('/'),
    dirname: (p) => String(p).replace(/\/[^/]*$/, ''),
  },
  'node:child_process': {
    spawnSync: (...args) => {
      // the WHOLE tuple, so a spread argument stays an array instead of being
      // flattened into something that string-matches nothing
      record.argv.push(args);
      return {status: 0, stdout: '', stderr: ''};
    },
  },
  'node:url': {
    fileURLToPath: (u) => String(u && u.href ? u.href : u),
  },
  '@remotion/bundler': {bundle: () => 'serve-url'},
  '@remotion/renderer': {
    renderMedia: () => undefined,
    selectComposition: () => ({
      width: 1920, height: 1080, fps: 60, durationInFrames: 1,
    }),
  },
};

let body = src
  // COMMENTS ARE STRIPPED FIRST. render.mjs's gate comment contains the word
  // `import`, so an import scan that ran before stripping asked for a stub for
  // a module named after a word in an English sentence.
  //
  // Block comments become whitespace of the same length so every subsequent
  // OFFSET still points where it did — the line numbers in this probe's report
  // are read from the rewritten body.
  .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));

for (const [pattern, build] of IMPORTS) {
  // `pattern` is a module-level /g regex and String.replace leaves its
  // `lastIndex` where the previous pass ended. Resetting it is not tidiness:
  // with it stale, the scan resumed mid-file and matched the fragment
  // `import p` out of a comment — which is what four revisions of this probe
  // kept hitting. Same class of bug as reusing a /g regex across two searches.
  pattern.lastIndex = 0;
  body = body.replace(pattern, (...args) => {
    // String.replace hands the callback (match, p1..pn, offset, whole) and
    // NOTHING else — there is no groups array. Passing `match` (the whole
    // matched string) to a builder that indexes m[1], m[2] is why the probe
    // reported the module id as `p`: it was reading one of the trailing
    // arguments of the full-argument list. Two revisions of this probe were
    // spent on that, both looking like an import-matching bug.
    const match = args[0];
    const groups = args.slice(1, -2);
    const info = build(groups);
    const mod = stubs[info.mod];
    if (!mod) {
      throw new Error(
        `probe: no stub for import ${info.mod}; add one so the observation `
        + 'cannot silently degrade. matched text: ' + JSON.stringify(match));
    }
    if (info.kind === 'namespace') {
      return `const ${info.name} = require('${info.mod}');`;
    }
    const decls = (info.names || []).filter(Boolean)
      .map((n) => {
        const [orig, alias] = n.split(/\s+as\s+/).map((s) => s && s.trim());
        return alias ? `${orig}: ${alias}` : orig;
      });
    const head = info.name ? `const ${info.name} = ` : '';
    if (info.kind === 'default') {
      return `${head}require('${info.mod}');`;
    }
    if (info.kind === 'mixed') {
      return `${head}{${decls.join(', ')}} = require('${info.mod}');`;
    }
    return `const {${decls.join(', ')}} = require('${info.mod}');`;
  });
}

body = body
  // `import.meta.url` locates the module; this probe does not need the real path.
  .replace(/\bimport\s*\.\s*meta\b/g, '({url: "file:///probe/render.mjs"})')
  // Top-level-await ESM in a CommonJS sandbox: every await in this file wraps
  // the RENDERER, and all of them sit AFTER the gate call. Removing them leaves
  // the control flow being measured exactly as written.
  .replace(/\bawait\s+/g, '');

const sandbox = {
  console: {log() {}, error() {}, warn() {}},
  process: {
    argv: withFlag
      ? ['node', 'render.mjs', '--gate-props',
         '--comp', 'FinanceShowcaseWide',
         // render.mjs's `get()` returns `argv[i + 1]` for a value flag, so
      // every flag it reads needs a value or the parser walks off the end of
         // argv. Missing them made `requireArg('comp')` exit 2 before the gate
         // was ever reached, which is a probe bug that LOOKED like a negative
         // observation.
         '--props', 'pipeline/examples/showcase_demo.json',
         '--out', 'out/probe.mp4']
      : ['node', 'render.mjs',
         '--comp', 'FinanceShowcaseWide',
         '--props', 'pipeline/examples/showcase_demo.json',
         '--out', 'out/probe.mp4'],
    exit(code) { record.exits.push(code); },
    env: {REMOTION_SCRATCH_DIR: '.', PYTHONIOENCODING: 'utf-8'},
    on() { return undefined; },
  },
  require: (id) => {
    const m = stubs[id];
    if (!m) throw new Error(`probe: no stub for module ${id}`);
    return m;
  },
  setTimeout, clearTimeout, Buffer, URL, Date, Math, JSON,
};
sandbox.globalThis = sandbox;

let ran = false;
let runError = null;
try {
  new vm.Script(body, {filename: file}).runInContext(
    vm.createContext(sandbox), {timeout: 20000});
  ran = true;
} catch (e) {
  // A throw AFTER the gate is still a valid observation; it is reported rather
  // than swallowed, and it never turns into "no spawn happened".
  runError = String(e && e.message ? e.message : e);
}

// The argv TUPLE: `[program, ...args]` where `...args` may itself be a single
// spread array. Recording `args` (not `args.slice(1)`) keeps the flatten
// visible: `spawnSync(cmd, [...spread], opts)` arrives as
// `[cmd, [...spread], opts]`, so element 1 is an ARRAY, and stringifying it
// with String() was what collapsed `--props,pipeline/examples/…` into one
// comma-joined string that no `includes('--props')` on an element could match.
const qaSpawns = record.argv.filter((argv) =>
  argv.some((a) => {
    if (Array.isArray(a)) return a.some((x) => /visual_qa\.py/.test(String(x)));
    return /visual_qa\.py/.test(String(a));
  }));
// FLATTENED. render.mjs passes the gate as a SPREAD of two pieces:
// `spawnSync(pyArgs[0], [...pyArgs.slice(1), qaScript, '--props', propsPath],
// opts)`. Recording `args.slice(1)` therefore yields argv[1] = the whole rest of
// the argument list as ONE string, because the spread flattens before the call
// and `args` is the argument tuple. Checking `.includes('--props')` against the
// ORIGINAL array answers false on the CLEAN file — which is how two revisions
// of this probe reported "the gate does not pass --props" about perfectly good
// code. Everything below stringifies, because the props path is `undefined`
// when the caller supplies no --props and a null element is not a string.
const flat = qaSpawns.map((argv) => argv.map((a) =>
  Array.isArray(a) ? a.map((x) => String(x)) : String(a)));

process.stdout.write(JSON.stringify({
  ok: qaSpawns.length > 0 || ran,
  ran,
  runError,
  qaSpawnCount: qaSpawns.length,
  qaSpawnArgv: flat.slice(0, 3),
  passedProps: flat.some((argv) =>
    argv.some((a) => Array.isArray(a) && a.includes('--props'))),
  exits: record.exits,
}));