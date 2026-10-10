/**
 * Does a generated graph's style bible actually reach the pixels? (P12.1)
 *
 * Run:  npx tsx scripts/p12_1_depth_cue_probe.ts <graph.json>
 *
 * WHY A RENDER AND NOT AN ASSERTION ON A DICT.
 *
 * The P12.1 work order's hardest requirement is that the guard must catch
 * "generated but nobody uses" — which is precisely the failure P12 spent a
 * whole work order documenting. A test that asserts
 * `generate_graph(...)['style_bible']['depthCue']` is a list proves the
 * generator returned a list. It cannot tell a wired section from an inert one,
 * because those two are the same object on the Python side and different
 * objects on screen.
 *
 * So this drives the real path end to end and reports what came out:
 *
 *   generated graph
 *     -> ShowcaseSchema.parse          (the real zod, `.strict()` and all)
 *     -> resolveStyleBible             (the real merge, over the real theme)
 *     -> StyleBibleProvider            (the real context)
 *     -> renderToStaticMarkup(BrowserStack)   (the real scene)
 *     -> read the emitted box-shadow per window back off the HTML
 *
 * The last step reads React's OUTPUT rather than recomputing the lookup, for
 * the reason `design/depthCue.check.ts` gives: the clamp lives in the scene's
 * map callback, and a probe that reimplemented it would be testing itself
 * against the very defect it exists to catch.
 *
 * It also reports the resolved DEPTH_CUE separately from the per-window
 * shadows, so a caller can tell "the section arrived but every window drew the
 * same thing" from "the section never arrived" — two failures with one
 * symptom on screen.
 *
 * Prints one JSON object on stdout. Exits non-zero if the graph cannot be read
 * or parsed, so a broken probe cannot be mistaken for a broken renderer.
 */

import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import fs from 'node:fs';
import path from 'node:path';
import {useVideoConfig} from 'remotion';
import {BrowserStack} from '../src/templates/finance-showcase/scenes/BrowserStack';
import {resolveStyleBible, StyleBibleProvider} from '../src/templates/finance-showcase/design/styleBible';
import {ShowcaseSchema, type Scene} from '../src/schemas/showcase-v1';

const REMOTION_CJS = path.resolve(process.cwd(), 'node_modules/remotion/dist/cjs');

/**
 * `TimelineContextProvider` seeds its `useState` from `localStorage`, which does
 * not exist under node. `frameState` below overrides its internal store on
 * every render, so a stub reporting "nothing stored" is exactly equivalent to a
 * browser with no saved position — not a change to what is measured. Carried
 * from `design/depthCue.check.ts`, which measured this rather than assumed it.
 */
(globalThis as unknown as {localStorage?: unknown}).localStorage ??= {
  getItem: () => null,
  setItem: () => undefined,
  removeItem: () => undefined,
};

/** Remotion's hook contexts are unexported subpaths; `require` the dist files. */
const remotionModule = (file: string): Record<string, unknown> => {
  const resolved = path.join(REMOTION_CJS, `${file}.js`);
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  return require(resolved);
};

const {CompositionManager} = remotionModule('CompositionManagerContext');
const {TimelineContextProvider} = remotionModule('TimelineContext');
const {CanUseRemotionHooksProvider} = remotionModule('CanUseRemotionHooks');
const {SequenceContext} = remotionModule('SequenceContext');
const {RenderAssetManager} = remotionModule('RenderAssetManager');
const {ResolveCompositionContext, resolveCompositionsRef} =
  remotionModule('ResolveCompositionConfig');
const {SequenceManager, SequenceManagerRefContext} = remotionModule('SequenceManager');
const {BufferingContextReact} = remotionModule('buffering');
const {LogLevelContext} = remotionModule('log-level-context');
const {PreloadContext} = remotionModule('prefetch-state');

const CompositionManagerDefault = (CompositionManager as unknown as Record<string, unknown>)
  ._currentValue;
const SequenceContextDefault = (SequenceContext as unknown as Record<string, unknown>)._currentValue;
const SequenceManagerDefault = (SequenceManager as unknown as Record<string, unknown>)._currentValue;
const SequenceManagerRefDefault = (SequenceManagerRefContext as unknown as Record<string, unknown>)
  ._currentValue;
const BufferingDefault = (BufferingContextReact as unknown as Record<string, unknown>)._currentValue;
const LogLevelDefault = (LogLevelContext as unknown as Record<string, unknown>)._currentValue;
const PreloadDefault = (PreloadContext as unknown as Record<string, unknown>)._currentValue;
const RenderAssetManagerDefault = (RenderAssetManager as unknown as Record<string, unknown>)
  ._currentValue;

const WIDTH = 1920;
const HEIGHT = 1080;
const FPS = 60;

const compositionManagerValue = {
  ...(CompositionManagerDefault as Record<string, unknown>),
  compositions: [{
    id: 'FinanceShowcaseWide',
    component: () => null,
    durationInFrames: 300,
    fps: FPS,
    width: WIDTH,
    height: HEIGHT,
    defaultProps: {},
  }],
  folders: [],
  canvasContent: {type: 'composition', compositionId: 'FinanceShowcaseWide'},
  currentCompositionMetadata: {
    id: 'FinanceShowcaseWide',
    durationInFrames: 300,
    fps: FPS,
    width: WIDTH,
    height: HEIGHT,
  },
  currentAssetMetadata: null,
};

type Contextual = unknown;

const wrapContext = (context: Contextual, value: unknown, child: React.ReactNode): React.ReactElement =>
  React.createElement((context as {Provider: React.Provider<unknown>}).Provider, {value}, child);

const wrapProvider = (
  Provider: Contextual,
  props: Record<string, unknown>,
  child: React.ReactNode
): React.ReactElement =>
  React.createElement(Provider as React.FC<Record<string, unknown>>, props, child);

const renderSceneAt = (scene: Scene, bible: unknown, theme: unknown, frame: number): string => {
  let tree: React.ReactNode = React.createElement(BrowserStack, {scene});
  tree = wrapProvider(StyleBibleProvider, {bible, theme}, tree);
  tree = wrapProvider(TimelineContextProvider, {frameState: frame}, tree);
  tree = wrapProvider(CanUseRemotionHooksProvider, {value: true}, tree);
  tree = wrapContext(SequenceContext, SequenceContextDefault, tree);
  tree = wrapContext(PreloadContext, PreloadDefault, tree);
  tree = wrapContext(LogLevelContext, LogLevelDefault, tree);
  tree = wrapContext(BufferingContextReact, BufferingDefault, tree);
  tree = wrapContext(SequenceManager, SequenceManagerDefault, tree);
  tree = wrapContext(SequenceManagerRefContext, SequenceManagerRefDefault, tree);
  tree = wrapContext(ResolveCompositionContext, resolveCompositionsRef, tree);
  tree = wrapContext(RenderAssetManager, RenderAssetManagerDefault, tree);
  tree = wrapContext(CompositionManager, compositionManagerValue, tree);
  return renderToStaticMarkup(tree as React.ReactElement);
};

/** One entry per window, in DOM order, read off the emitted markup. */
const shadowsFor = (scene: Scene, bible: unknown, theme: unknown, frame: number): string[] => {
  const html = renderSceneAt(scene, bible, theme, frame);
  const out: string[] = [];
  const re = /box-shadow:([^;"]+)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(html)) !== null) {
    out.push(m[1].trim());
  }
  return out;
};

const main = (): void => {
  const graphPath = process.argv[2];
  if (!graphPath) {
    console.error('usage: p12_1_depth_cue_probe.ts <graph.json>');
    process.exit(2);
  }
  const raw = fs.readFileSync(graphPath, 'utf-8');
  const doc = JSON.parse(raw) as Record<string, unknown>;

  // The REAL zod schema. `.strict()` has been on StyleBibleSchema since P12, so
  // this is where an undeclared key becomes a hard error rather than a silently
  // stripped value — the exact "looks wired, is inert" family this project has
  // been bitten by, and the reason the parse step cannot be skipped.
  const parsed = ShowcaseSchema.safeParse(doc);
  if (!parsed.success) {
    console.error(JSON.stringify({parse_ok: false, issues: parsed.error.issues}, null, 2));
    process.exit(1);
  }

  const data = parsed.data as unknown as {
    style_bible?: Record<string, unknown>;
    scenes: Array<Record<string, unknown>>;
  };
  const scene = data.scenes.find((s) => s.type === 'browser-stack') ?? data.scenes[0];
  if (!scene) {
    console.error('graph has no scenes');
    process.exit(1);
  }

  const bible = resolveStyleBible(data.style_bible, scene.theme);
  const shadows = shadowsFor(scene as unknown as Scene, data.style_bible, scene.theme, 240);

  console.log(JSON.stringify({
    parse_ok: true,
    bible_keys_surviving_parse: Object.keys(data.style_bible ?? {}).sort(),
    resolved_depth_cue: [...bible.depthCue],
    window_count: Array.isArray((scene.content as Record<string, unknown>)?.windows)
      ? ((scene.content as Record<string, unknown>).windows as unknown[]).length
      : 0,
    shadows,
    distinct_shadows: new Set(shadows).size,
  }, null, 2));
};

main();