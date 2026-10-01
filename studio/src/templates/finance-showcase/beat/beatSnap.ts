/**
 * What turning on `beat_snap` would do to a timeline, stated as a number.
 *
 * The situation this exists for. `FinanceShowcaseWide` calls
 * `resolveScenes(doc, false)` — so the beat maths in `showcase-v1` and in
 * `scene_graph.py`, both present since P3, has never run in a delivered render.
 * The graph's `bpm` was read by nothing on the render path at all. That is the
 * same shape as the committed-but-unread `bgm_beats.json`: a capability with no
 * caller.
 *
 * Leaving it that way is a legitimate choice — flipping it would move delivered
 * frames — but an unexercised branch that nobody has measured is a branch nobody
 * can say anything about. So this reports what it WOULD do, and the check beside
 * it pins the numbers so that a future change to `resolveScenes` shows up here
 * rather than in a delivered film.
 *
 * Pure and dependency-free: it takes the resolved timelines as arguments and does
 * arithmetic on them. The caller is responsible for producing those with the real
 * `resolveScenes`, so this cannot disagree with it about what the timeline IS —
 * only report on what was handed in.
 */

import {resolveScenes} from '../../../schemas/showcase-v1';

export type SceneTiming = {
  id: string;
  startFrame: number;
  durationInFrames: number;
  requestedFrames?: number;
};

export type SnapDelta = {
  id: string;
  requested: number;
  /** the shipped path: back-to-back, frame-cumulative */
  shippedStart: number;
  /** what beat_snap=true would produce */
  snappedStart: number;
  shippedDuration: number;
  snappedDuration: number;
  /** snappedStart - shippedStart; positive means beat_snap pushes the scene later */
  startDelta: number;
  durationDelta: number;
  moved: boolean;
  /** True when beat quantisation changed the requested LENGTH, as ResolvedScene.adjusted does */
  lengthAdjusted: boolean;
};

export type SnapComparison = {
  rows: SnapDelta[];
  maxStartDelta: number;
  maxDurationDelta: number;
  movedCount: number;
  /** total frames either way, which beat_snap does NOT change here */
  shippedTotal: number;
  snappedTotal: number;
};export const compareBeatSnap = (
  shipped: readonly SceneTiming[],
  snapped: readonly SceneTiming[]
): SnapComparison => {
  if (shipped.length !== snapped.length) {
    throw new Error(
      `compareBeatSnap got ${shipped.length} shipped scenes and ${snapped.length} snapped; ` +
        'the two timelines are not the same film'
    );
  }
  const rows: SnapDelta[] = shipped.map((s, i) => {
    const n = snapped[i];
    if (s.id !== n.id) {
      throw new Error(
        `scene ${i} is "${s.id}" on the shipped path and "${n.id}" when snapped — ` +
          'comparing two different films'
      );
    }
    const requested = s.requestedFrames ?? s.durationInFrames;
    return {
      id: s.id,
      requested,
      shippedStart: s.startFrame,
      snappedStart: n.startFrame,
      shippedDuration: s.durationInFrames,
      snappedDuration: n.durationInFrames,
      startDelta: n.startFrame - s.startFrame,
      durationDelta: n.durationInFrames - s.durationInFrames,
      moved: n.startFrame !== s.startFrame || n.durationInFrames !== s.durationInFrames,
      lengthAdjusted: requested !== n.durationInFrames,
    };
  });
  const shippedTotal = shipped.reduce((sum, s) => sum + s.durationInFrames, 0);
  const snappedTotal = snapped.reduce((sum, s) => sum + s.durationInFrames, 0);
  return {
    rows,
    maxStartDelta: rows.reduce((m, r) => Math.max(m, Math.abs(r.startDelta)), 0),
    maxDurationDelta: rows.reduce((m, r) => Math.max(m, Math.abs(r.durationDelta)), 0),
    movedCount: rows.filter((r) => r.moved).length,
    shippedTotal,
    snappedTotal,
  };
};

export type SnapCostInput = {
  bpm: number;
  fps: number;
  scenes: {id: string; durationInFrames: number}[];
};

export type SnapCostScene = {
  id: string;
  /** what the graph asked for */
  req: number;
  shippedStart: number;
  shippedDuration: number;
  snappedStart: number;
  snappedDuration: number;
  /** snappedStart - shippedStart */
  delta: number;
  /**
   * req - snappedDuration: the frames this scene loses to beat quantisation,
   * POSITIVE when shortened and NEGATIVE when lengthened. This is the quantity
   * that is bounded by half a beat; the film-level total is not.
   */
  deficit: number;
};

export type SnapCost = {
  shipped: number;
  snapped: number;
  /** snapped - shipped. Negative shortens the film, positive lengthens it. */
  deltaFrames: number;
  perScene: SnapCostScene[];
  /** round((60 / bpm) * fps) — the whole-frame unit the bound is expressed in */
  oneBeatFrames: number;
  /** (60 / bpm) * fps, unrounded; the per-scene bound is half of THIS plus 1 */
  beatFramesExact: number;
  /**
   * The exact ceiling on any single scene's deficit.
   *
   * Not `oneBeatFrames / 2`, which is wrong by up to a frame. `beats =
   * round(requested / beat_frames)` is wrong by at most half a beat, but the
   * RESOLVED duration is `round((k + beats) * bf) - round(k * bf)` — two boundary
   * roundings — so it carries up to one further frame. The true bound is
   * therefore `beatFramesExact / 2 + 1`.
   *
   * That is not a rounding technicality. At 128.998 bpm and 24fps one beat is
   * 11.158 frames, the half-beat bound is 5.58, and a scene can legitimately land
   * 6 frames from its request — measured, and it is why a half-beat gate is red on
   * a cell where nothing is wrong.
   */
  maxSceneDeficit: number;
  /** the largest absolute per-scene deficit */
  worstSceneDeficit: number;
  scenes: number;
};

/**
 * What beat quantisation COSTS a film, per scene and in total.
 *
 * `resolveScenes(beat_snap=True)` computes `beats = round(requested / beat_frames)`
 * for each scene independently, so every scene loses whatever fraction of a beat
 * its requested duration had. Two consequences this function exists to make
 * measurable rather than argued about:
 *
 *  - The per-scene deficit is bounded by HALF a beat, because that is all a
 *    `round()` can be wrong by. That is the invariant worth guarding: it is what
 *    distinguishes "this is the cost of quantising" from "the maths has a bug".
 *
 *  - The FILM-level total is the SUM of those deficits, so it grows with the scene
 *    count and is not bounded by one beat. Measured over tempo x fps for
 *    showcase_demo: the film-level total exceeds one beat in 6 of 20 cells,
 *    reaching 68 frames at 174 bpm / 120fps, while the worst single scene in any
 *    of those cells is 20. A guard on the film total would therefore be a guard on
 *    the scene count, and it would fail for the wrong reason.
 *
 *  - The sign is not fixed. Quantisation shortens a film when the requests sit
 *    above a whole beat and lengthens it when they sit below: 229 frames is 8.015
 *    beats at 126 bpm (film loses 1 frame) and 8.206 at 128.998 (film loses 20),
 *    but 150 frames is 5.375 beats at 128.998 and the same 150 frames is 5.25 at
 *    126, so charts_demo goes the other way at some tempos. "beat_snap shortens
 *    the film" is not true in general and was not true of every graph.
 */
export const snapCost = (input: SnapCostInput): SnapCost => {
  const {bpm, fps, scenes} = input;
  const doc = {
    bpm,
    format: {fps},
    scenes,
  } as unknown as Parameters<typeof resolveScenes>[0];

  const shippedScenes = resolveScenes(doc, false);
  const snappedScenes = resolveScenes(doc, true);

  const perScene: SnapCostScene[] = scenes.map((s, i) => {
    const flat = shippedScenes[i];
    const snap = snappedScenes[i];
    return {
      id: s.id,
      req: s.durationInFrames,
      shippedStart: flat.startFrame,
      shippedDuration: flat.durationInFrames,
      snappedStart: snap.startFrame,
      snappedDuration: snap.durationInFrames,
      delta: snap.startFrame - flat.startFrame,
      deficit: s.durationInFrames - snap.durationInFrames,
    };
  });

  const shipped = shippedScenes.reduce((sum, s) => sum + s.durationInFrames, 0);
  const snapped = snappedScenes.reduce((sum, s) => sum + s.durationInFrames, 0);
  const beatFramesExact = (60 / bpm) * fps;

  return {
    shipped,
    snapped,
    deltaFrames: snapped - shipped,
    perScene,
    oneBeatFrames: Math.max(1, Math.round(beatFramesExact)),
    beatFramesExact,
    maxSceneDeficit: beatFramesExact / 2 + 1,
    worstSceneDeficit: perScene.reduce((m, r) => Math.max(m, Math.abs(r.deficit)), 0),
    scenes: perScene.length,
  };
};
