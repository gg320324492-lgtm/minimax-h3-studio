/**
 * SFX profile — P9 step 14. Which sound marks which beat event.
 *
 * 9.3 is written as "replace the per-screen whoosh+impact+flash", so this file is
 * the specification of the replacement: a table from event to sound, and nothing
 * else. It is not wired to anything. Wiring it would change what a delivered film
 * sounds like, and the point of writing the table first is that the table can be
 * argued about as data.
 *
 * WHY THE TABLE LOOKS LIKE THIS, measured from the report template's actual
 * behaviour (`ReportVertical.tsx:373-383`) on the shipped props:
 *
 *   9 sections, 8 of them sounding. Every one of those 8 gets whoosh AND impact —
 *   8 of 8 screens carry both. 18 events in 29.9s, 2.25 per screen, mix
 *   {whoosh: 8, impact: 8, ding: 1, riser: 1}. Only `ding` (once, on the first
 *   takeaway) and `riser` (once, on the outro) are conditional; everything else is
 *   indiscriminate. Two transients 0.18s apart on every screen is the habit being
 *   replaced, and it is why the table has one sound per event rather than a pair.
 *
 * THE RULE THE TABLE ENCODES. Two of the six events are the ones with a queryable
 * frame (`bindings.ts`), so they are the two that could be timed against the grid
 * at all. `camera-settle` is a camera arriving and wants the soft one; `chart-finish`
 * is a number becoming readable and wants the accent. That leaves four events with
 * no frame, and an event with no frame cannot be placed on a beat.
 *
 * `cut` is the interesting one, and the reason coverage is 3 rather than 2. It has
 * an input (`transitionIn`, including an optional `out`) and no queryable frame, and
 * it is the event whose current behaviour is most worth preserving while everything
 * else is reconsidered: eight whooshes in a row is the thing being cut down, and
 * `whoosh` is a transition sound by construction. So it is mapped — on the stated
 * condition that the binding is wired to a frame before it is wired to a sound, which
 * is why `bindings.ts` still reports it unavailable.
 *
 * Three of six mapped, so coverage is 3/6 = 50%. The three holes are exactly the three
 * events with neither a frame nor an input: `card-arrival`, `number-finish`, `hit`.
 * That number is asserted rather than described, because a coverage figure nobody
 * checks drifts the moment a row is added without a file.
 *
 * Zero react, zero remotion: a table of strings.
 */

import type {BindingEvent} from './bindings';

/**
 * Event -> audio filename, or null when the event has no frame to place.
 *
 * Filenames, not paths. The check resolves them against `studio/public/audio/`, so
 * a typo fails there rather than at render time — where it would be a 404 inside an
 * `<Audio>` and, depending on the renderer, silence rather than an error.
 */
export const EVENT_SFX: Record<BindingEvent, string | null> = {
  'camera-settle': 'sfx_whoosh.m4a',
  'chart-finish': 'sfx_impact.m4a',
  // conditional: only while `cut` still has no queryable frame. See the header.
  cut: 'sfx_whoosh.m4a',
  'card-arrival': null,
  'number-finish': null,
  hit: null,
};

/** Events with a mapped sound, in BindingEvent order. */
export const MAPPED_EVENTS = (Object.keys(EVENT_SFX) as BindingEvent[]).filter(
  (e) => EVENT_SFX[e] !== null
);

export const SFX_COVERAGE = MAPPED_EVENTS.length / (Object.keys(EVENT_SFX).length);

/**
 * The measured report baseline this table is a reaction to. Exported so the check
 * and the ledger quote one number rather than each keeping their own.
 */
export const REPORT_BASELINE = {
  sections: 9,
  soundingScreens: 8,
  screensWithBothWhooshAndImpact: 8,
  totalEvents: 18,
  seconds: 29.9,
  mix: {whoosh: 8, impact: 8, ding: 1, riser: 1},
} as const;
