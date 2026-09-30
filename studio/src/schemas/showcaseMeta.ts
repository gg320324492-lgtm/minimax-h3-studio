// showcase-v1 -> composition metadata. P8.
//
// Deliberately free of react and remotion so the decision it makes can be
// executed by a check. `FinanceShowcaseWide.showcaseMeta` is a two-line wrapper
// around this; when the question was "what happens when the graph is wrong",
// the answer lived inside a React component and could not be asked without
// rendering a frame to ask it.

import {ShowcaseSchema, describeIssues, type Showcase} from './showcase-v1';

export type ShowcaseMeta = {
  width: number;
  height: number;
  fps: number;
  durationInFrames: number;
};

/** The registration defaults, used only when there is nothing to read. */
const FALLBACK: ShowcaseMeta = {width: 1920, height: 1080, fps: 60, durationInFrames: 1};

/**
 * No graph at all is a real state, not a defect: Remotion runs
 * `calculateMetadata` once with `defaultProps` before real props arrive, and a
 * Studio opened with no graph selected passes an empty document. Both mean
 * "tell me what you would render", and the registration default answers that.
 *
 * Anything that declares a field of the graph is an ATTEMPT at a graph, and an
 * attempt has to validate. The discriminator is deliberately "does it declare
 * any of showcase-v1's top-level fields", not "does it have a scenes array":
 * a document carrying `format` and no `scenes` is a graph with a missing
 * required field, and it must be told so rather than quietly rendered as
 * something else. That distinction was itself a defect in the first version of
 * this rule, found by the check below.
 */
const GRAPH_KEYS = ['version', 'project', 'scenes', 'format', 'bpm', 'style_bible'] as const;

const isAbsent = (raw: unknown): boolean => {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) return true;
  const doc = raw as Record<string, unknown>;
  return !GRAPH_KEYS.some((k) => k in doc);
};

/**
 * Read the render format off the graph.
 *
 * Throws, with the offending field named, when a document that IS a graph fails
 * the schema. It used to return `1920x1080@60 1 frames` instead, for every
 * possible defect at once — see the long note on `showcaseMeta` for what that
 * cost, which was an error message about the wrong field.
 */
export const resolveShowcaseMeta = (raw: unknown): ShowcaseMeta => {
  if (isAbsent(raw)) return {...FALLBACK};
  const parsed = ShowcaseSchema.safeParse(raw);
  if (!parsed.success) {
    throw new Error(
      `showcase-v1: this graph does not match the schema, so its render format ` +
        `cannot be trusted.\n${describeIssues(parsed.error)}`
    );
  }
  const doc = parsed.data as Showcase;
  const total = doc.scenes.reduce((sum, sc) => sum + sc.durationInFrames, 0);
  return {
    width: doc.format.width,
    height: doc.format.height,
    fps: doc.format.fps,
    durationInFrames: Math.max(1, total),
  };
};
