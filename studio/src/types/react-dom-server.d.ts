/**
 * Ambient types for `react-dom/server`.
 *
 * `@types/react-dom` is not a dependency of this project, and adding it for one
 * call to `renderToStaticMarkup` would mean a lockfile change for a test
 * harness. Only the two entry points this repo uses are declared, and both are
 * typed as narrowly as the real package types them:
 *
 *   renderToStaticMarkup(element)  -> the markup as a string
 *   renderToString(element)        -> the markup as a string
 *
 * This exists for `design/depthCue.check.ts`, which server-renders the real
 * `BrowserStack` to read back the `box-shadow` React actually emitted. That is
 * the measurement the P6.8 depth-cue guard is built on; see that file for why a
 * CSS declaration and not a flattened PNG is what decides the defect.
 *
 * Deliberately minimal: an untyped `any` import would silence the same error and
 * also silence every real mistake made against it later.
 */
declare module 'react-dom/server' {
  import type {ReactElement} from 'react';

  export function renderToStaticMarkup(element: ReactElement): string;
  export function renderToString(element: ReactElement): string;
}