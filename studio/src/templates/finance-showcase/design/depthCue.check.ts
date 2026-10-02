/**
 * MEASURE, then fix: is the 4th window's depth cue really the 3rd's?
 *
 * Run:  npx tsx src/templates/finance-showcase/design/depthCue.check.ts
 *
 * The question this file answers is empirical and was answered wrongly in
 * both directions before it was measured. `BrowserStack.tsx` read
 *
 *     const depth = DEPTH_CUE[Math.min(i, DEPTH_CUE.length - 1)] ?? SHADOW.floating;
 *
 * with a `depthCue` of exactly three entries, so `Math.min` clamps every window
 * from the fourth onward onto the third entry. That is a defect only if the
 * fourth window is genuinely reachable AND genuinely undifferentiated — a
 * source read proves neither, and every graph ever delivered carries exactly
 * three windows, so no shipped frame has ever shown it.
 *
 * So this file renders the REAL scene through the REAL Remotion contexts and
 * reads the box-shadow React actually emitted, per window, at a chosen frame.
 * It is deliberately not a re-implementation of the clamp: the whole class of
 * bug it is looking for is a clamp written slightly differently in a test than
 * in the scene.
 *
 * Why server-rendering rather than `visual_qa.py` on a PNG: a box-shadow is a
 * CSS declaration. `visual_qa.py` measures pixels, and a shadow's contribution
 * to pixels is a function of what it falls on, the window's opacity, the
 * spread of the stack behind it and the camera's position — so "layer 4 and
 * layer 3 have the same shadow" is not recoverable from a flattened frame,
 * while "layer 4 and layer 3 were handed the same box-shadow string" is exactly
 * what decides it. Both facts are recorded below; the CSS one is the defect.
 *
 * No headless Chrome, no render, no fixture: it runs in milliseconds and
 * cannot fail for a reason unrelated to depth.
 */

import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import path from 'node:path';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {BrowserStack, depthCueAt} from '../scenes/BrowserStack';
import {StyleBibleProvider} from './styleBible';
import {THEMES, type ThemeName} from './themes';
import type {Scene} from '../../../schemas/showcase-v1';

const REMOTION_CJS = path.resolve(process.cwd(), 'node_modules/remotion/dist/cjs');

/**
 * `TimelineContextProvider` seeds its `useState` from `localStorage`, a browser
 * global that does not exist under node. It is the INITIAL frame of the
 * provider's internal store, and `frameState` overrides it on every render
 * below, so a stub that reports "nothing stored" is exactly equivalent to a
 * browser with no saved position — not a change to what is measured.
 */
(globalThis as unknown as {localStorage?: unknown}).localStorage ??= {
  getItem: () => null,
  setItem: () => undefined,
  removeItem: () => undefined,
};

/**
 * Remotion's hook contexts, assembled by hand.
 *
 * `RemotionContextProvider` takes a prebuilt `contexts` bag that the renderer
 * constructs internally, so it is not usable from here. Each provider below is
 * the real one out of remotion's own dist, with the real default value from the
 * real context object — so `useCurrentFrame` and `useVideoConfig` read what a
 * render would give them, and nothing about the scene is stubbed.
 *
 * The `require` of a computed path is what the package's own exports map forces:
 * `remotion/internals` is not an exported subpath, so these modules are not
 * reachable by name. Every path below is asserted to exist before use, so a
 * Remotion upgrade that moves one turns this into a loud failure rather than a
 * quietly different measurement.
 */
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
const {
  ResolveCompositionContext,
  resolveCompositionsRef,
} = remotionModule('ResolveCompositionConfig');
const {SequenceManager, SequenceManagerRefContext} = remotionModule('SequenceManager');
const {BufferingContextReact} = remotionModule('buffering');
const {LogLevelContext} = remotionModule('log-level-context');
const {PreloadContext} = remotionModule('prefetch-state');

const CompositionManagerDefault = (
  CompositionManager as unknown as {_currentValue: unknown}
)._currentValue;
const SequenceContextDefault = (SequenceContext as unknown as {_currentValue: unknown})
  ._currentValue;
const SequenceManagerDefault = (SequenceManager as unknown as {_currentValue: unknown})
  ._currentValue;
const RenderAssetManagerDefault = (RenderAssetManager as unknown as {_currentValue: unknown})
  ._currentValue;
const BufferingDefault = (BufferingContextReact as unknown as {_currentValue: unknown})
  ._currentValue;
const LogLevelDefault = (LogLevelContext as unknown as {_currentValue: unknown})._currentValue;
const PreloadDefault = (PreloadContext as unknown as {_currentValue: unknown})._currentValue;
const SequenceManagerRefDefault = (SequenceManagerRefContext as unknown as {_currentValue: unknown})
  ._currentValue;

/**
 * A composition Remotion will resolve to the geometry this harness asks for.
 *
 * `useVideoConfig` resolves through the CompositionManager, so the size and
 * frame rate the scene computes `scaleFor` and its spring from have to come
 * from here — a scene rendered against the wrong frame is measuring a different
 * scene. 1920x1080@60 is the shipped composition's own geometry.
 */
const COMPOSITION_ID = 'FinanceShowcaseWide';
const WIDTH = 1920;
const HEIGHT = 1080;
const FPS = 60;
const DURATION = 300;

const compositionEntry = {
  id: COMPOSITION_ID,
  component: () => null,
  durationInFrames: DURATION,
  fps: FPS,
  width: WIDTH,
  height: HEIGHT,
  defaultProps: {},
};

const compositionManagerValue = {
  ...(CompositionManagerDefault as Record<string, unknown>),
  compositions: [compositionEntry],
  folders: [],
  canvasContent: {type: 'composition', compositionId: COMPOSITION_ID},
  currentCompositionMetadata: {
    id: COMPOSITION_ID,
    durationInFrames: DURATION,
    fps: FPS,
    width: WIDTH,
    height: HEIGHT,
  },
  currentAssetMetadata: null,
};

/**
 * Nest one provider inside another, by name, without naming its type.
 *
 * Remotion's contexts are reached through its unexported dist modules, so they
 * arrive here as `unknown` and each one needs a cast. Doing that per provider
 * turned this function into a 50-line staircase of `as unknown as
 * React.Provider<unknown>` casts, which is unreadable and — worse — made the
 * ORDER of the providers the only readable statement of what the scene needs.
 * One `wrap` keeps the tree below it readable as the list it is.
 *
 * The provider's real default value is passed in alongside it, because the value
 * is what the render reads: passing `undefined` here would make every hook fall
 * back to its own error path rather than to what a render supplies.
 */
type Contextual = unknown;

/**
 * Wrap `child` in a Remotion context provider carrying `value`.
 *
 * Two shapes are called out separately below, because conflating them is
 * exactly what breaks this: a CONTEXT (`SequenceContext`, `PreloadContext`,
 * ...) is an object whose `.Provider` takes `{value}`, while a PROVIDER
 * FUNCTION (`TimelineContextProvider`, `CanUseRemotionHooksProvider`,
 * `StyleBibleProvider`) takes its props directly and has no `.Provider` to
 * index. Passing one where the other is expected yields either
 * "Element type is invalid ... got: undefined" or a silently ignored value, so
 * they get separate helpers rather than one `wrap` that has to guess.
 */
type ContextProviderLike = {Provider: React.Provider<unknown>};
type PropsComponent = React.FC<Record<string, unknown>>;

const wrapContext = (
  context: Contextual,
  value: unknown,
  child: React.ReactNode
): React.ReactElement =>
  React.createElement((context as ContextProviderLike).Provider, {value}, child);

/** Wrap `child` in a provider FUNCTION that takes its props directly. */
const wrapProvider = (
  Provider: Contextual,
  props: Record<string, unknown>,
  child: React.ReactNode
): React.ReactElement =>
  React.createElement(Provider as PropsComponent, props, child);

const renderSceneAt = (scene: Scene, frame: number): string => {
  let tree: React.ReactNode = React.createElement(BrowserStack, {scene});
  tree = wrapProvider(StyleBibleProvider, {}, tree);
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

/**
 * The per-window box-shadow React actually emitted, in DOM order.
 *
 * Read off the rendered markup rather than recomputed: the map callback in
 * BrowserStack is the only place the clamp exists, and a test that re-derived it
 * would be testing itself. `box-shadow` appears on the window element only, so
 * one capture per window is one entry here.
 */
const shadowsFor = (scene: Scene, frame: number): string[] => {
  const html = renderSceneAt(scene, frame);
  const out: string[] = [];
  const re = /box-shadow:([^;"]+)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(html)) !== null) {
    out.push(m[1].trim());
  }
  return out;
};

const window_ = (i: number, extra: Record<string, unknown> = {}): Record<string, unknown> => ({
  title: `w${i}`,
  metric: `${i}M`,
  bars: [3, 5, 4, 6],
  ...extra,
});

/** A browser-stack scene asking for `count` windows, on the demo's own layout. */
const stackScene = (count: number): Scene =>
  ({
    id: 'depth_probe',
    type: 'browser-stack',
    durationInFrames: DURATION,
    layout: {
      spreadX: 300,
      spreadZ: 150,
      perWindowRotateY: 9,
      windowWidth: 520,
      windowHeight: 400,
      equalOnScreen: true,
    },
    camera: {perspective: 1400, translateZ: [0, 0], rotateY: [0, 0], rotateX: [0, 0]},
    motion: {preset: 'premium', stagger: 0.05},
    content: {windows: Array.from({length: count}, (_, i) => window_(i))},
  }) as unknown as Scene;

// --------------------------------------------------------------------------
// The measurement
// --------------------------------------------------------------------------

let failures = 0;
const check = (name: string, ok: boolean, detail = ''): void => {
  if (ok) {
    console.log(`  ok   ${name}`);
  } else {
    failures += 1;
    console.log(`  FAIL ${name}${detail ? `\n         ${detail}` : ''}`);
  }
};

const FRAME = 240; // past every entrance spring, so opacity is 1 on all windows

console.log('depth cue: what each window is actually handed, by render');

const observed = shadowsFor(stackScene(6), FRAME);
console.log(`\n  6 windows at frame ${FRAME} -> ${observed.length} box-shadow declarations`);
observed.forEach((s, i) => console.log(`    window ${i}: ${s}`));
console.log('');

check(
  'the probe found one box-shadow per window',
  observed.length === 6,
  `expected 6, got ${observed.length}`
);

/**
 * The guard proper: every layer the ramp NAMES must differ from the one below.
 *
 * `N` runs to `depthCue.length`, i.e. windows 0..length-1 are all required to
 * be distinct. Window `length` and beyond sit past the end of the ramp and are
 * deliberately clamped — that is the documented `depthCueAt` behaviour, and the
 * reason the darkest layer has to be the one that saturates (see themes.ts). So
 * the boundary the assertion stops at is the ramp's own length, and the check
 * says so in its failure text: a repetition at window `length` is the design,
 * a repetition BELOW it is the defect this file was written to catch.
 *
 * The stack under test is sized `depthCue.length + 1` on purpose. One window
 * past the ramp is what makes the two mistakes distinguishable: a clamp that
 * fires a layer early (the old 3-deep ramp) repeats at window 3, which is
 * inside the named range and turns this red; a correct clamp repeats only at
 * window `length`.
 */
const rampLength = THEMES['premium-dark'].depthCue.length;

// ABSOLUTE floor, before anything relative to `rampLength`.
//
// The two checks below are both phrased in terms of the ramp's own length, so
// on their own they are satisfiable by shrinking the ramp: a three-deep ramp
// repeats at window 3, which is exactly where a correct five-deep ramp clamps,
// and both checks pass. Shrinking depthCue is precisely the mutation this file
// was written to survive, so the floor is asserted FIRST and independently, and
// it is the same floor tests/test_depth_cue_layers.py pins.
check(
  'the ramp is at least four layers deep',
  rampLength >= 4,
  `depthCue has ${rampLength} layer(s); BrowserStack clamps every window past the last one onto it`
);

let firstRepeated = -1;
for (let i = 1; i < observed.length; i += 1) {
  if (observed[i] === observed[i - 1] && firstRepeated === -1) {
    firstRepeated = i;
  }
}
console.log(
  `  depthCue names ${rampLength} layers; the first repeated shadow is at window ${firstRepeated}`
);
console.log('');

check(
  `windows 0..${rampLength - 1} each differ from the one below (window ${rampLength} may repeat)`,
  firstRepeated >= rampLength,
  firstRepeated === -1
    ? ''
    : `window ${firstRepeated} repeats window ${firstRepeated - 1} -- both "${observed[firstRepeated]}". ` +
      `The ramp names ${rampLength} layers, so a repeat at or past window ${rampLength} is the clamp working; ` +
      `a repeat at window ${firstRepeated} is inside the ramp.`
);

check(
  'the clamp starts exactly at the end of the ramp, not before it',
  firstRepeated === rampLength,
  `expected the first repeat at window ${rampLength}, got ${firstRepeated}`
);

check(
  'a 4-window stack gives four distinct shadows',
  new Set(shadowsFor(stackScene(4), FRAME)).size === 4,
  `got ${JSON.stringify(shadowsFor(stackScene(4), FRAME))}`
);

// The window indices the scene hands to the lookup must also land on distinct
// entries, which is the same fact seen from the token side.
const cue = THEMES['premium-dark'].depthCue;
check(
  'the token ramp itself has no duplicate entry',
  new Set(cue).size === cue.length,
  `depthCue = ${JSON.stringify(cue)}`
);

// Both themes: a ramp that only the dark theme differentiates is half a fix.
for (const themeName of Object.keys(THEMES) as Array<ThemeName>) {
  const t = THEMES[themeName];
  check(
    `${themeName} depthCue has no duplicate entry`,
    new Set(t.depthCue).size === t.depthCue.length,
    `depthCue = ${JSON.stringify(t.depthCue)}`
  );
}

// The other half of the theme question: BOTH themes must be the same depth as
// each other, or a graph that switches theme mid-film changes how deep the
// stack reads. Checked as "every layer differentiates", not "same strings" —
// the two ramps are tuned for different grounds and must never match exactly.
for (const themeName of Object.keys(THEMES) as Array<ThemeName>) {
  const t = THEMES[themeName];
  check(
    `${themeName} distinguishes all ${t.depthCue.length} layers`,
    new Set(shadowsFor(stackScene(t.depthCue.length), FRAME)).size === t.depthCue.length,
    `got ${JSON.stringify(shadowsFor(stackScene(t.depthCue.length), FRAME))}`
  );
}

// `depthCueAt` past the end of the ramp, checked directly rather than inferred
// from the render. These three are the behaviours its comment claims, and the
// middle one is the one that was rejected: wrapping would render window 5 as
// window 0, the FAR plane, behind a window carrying the deepest shadow.
check(
  'depthCueAt clamps at the deepest layer, it does not wrap',
  depthCueAt(cue, 99) === cue[cue.length - 1] && depthCueAt(cue, 5) === cue[cue.length - 1],
  `depthCueAt(cue, 99) = ${JSON.stringify(depthCueAt(cue, 99))}, ` +
    `cue[last] = ${JSON.stringify(cue[cue.length - 1])}`
);
check(
  'depthCueAt does not wrap to the far plane',
  depthCueAt(cue, cue.length) !== cue[0],
  `depthCueAt(cue, ${cue.length}) returned the FAR plane ${JSON.stringify(cue[0])}`
);
check(
  'depthCueAt on an empty ramp yields undefined so the call site can fall back',
  depthCueAt([], 3) === undefined,
  `got ${JSON.stringify(depthCueAt([], 3))}`
);

if (failures) {
  console.error(`\n${failures} check(s) FAILED`);
  process.exit(1);
}
console.log('\nall depth-cue checks passed');