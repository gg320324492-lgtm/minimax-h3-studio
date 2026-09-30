/**
 * CSS 3D perspective projection, as pure functions.
 *
 * Split out of CameraRig with no imports at all, for one reason: this is the
 * maths that decides where every pixel of a 3D scene lands, and P6.2 shipped a
 * bug in it that a source read could not see. Keeping it dependency-free means
 * a test can import the real functions and check the actual numbers.
 *
 * The two facts everything else follows from:
 *
 *  - CSS perspective projects about the centre of the perspective element. A
 *    point at (x, z) appears on screen at `x * P / (P - z)`.
 *  - depth is measured from the EYE, so z is ABSOLUTE — the object's own plane
 *    plus the camera rig's. Using an object's own z alone is wrong the moment
 *    the camera moves, which is why a stack that looked centred at the start of
 *    a camera move drifted as the move progressed.
 */

export const projectX = (cssX: number, absoluteZ: number, perspective: number): number =>
  perspective > 0 && absoluteZ < perspective
    ? (cssX * perspective) / (perspective - absoluteZ)
    : cssX;

/**
 * The exact inverse of {@link projectX}: the CSS x that lands a point at
 * `screenX`.
 *
 * Authoring a layout in screen space and solving back to CSS makes "centred" a
 * structural property of the layout instead of a number someone tuned until one
 * render looked right.
 */
export const cssXForScreenX = (
  screenX: number,
  absoluteZ: number,
  perspective: number
): number =>
  perspective > 0 && absoluteZ < perspective
    ? (screenX * (perspective - absoluteZ)) / perspective
    : screenX;

/**
 * Counter-scale for an object that must keep a chosen size ON SCREEN: the
 * inverse of the projection at its own plane, `(P - z) / P`.
 *
 * It must be the INVERSE. Returning `P / (P - z)` — the magnification — looks
 * plausible and is exactly backwards: it makes near objects bigger and far ones
 * smaller, which is the asymmetry this function exists to remove. That mistake
 * shipped once and measured +33px of drift on a 1920 frame; `projection.check.ts`
 * pins the round-trip so it cannot come back.
 *
 * Note the deliberate difference from {@link cssXForScreenX}: position is solved
 * against ABSOLUTE depth, so the stack stays on the axis even while the camera
 * moves, but scale is solved against the object's OWN plane. Freezing scale too
 * would magnify the stack rigidly and the camera move would stop reading as
 * depth at all.
 */
export const screenScaleFor = (planeZ: number, perspective: number): number =>
  perspective > 0 && planeZ < perspective ? (perspective - planeZ) / perspective : 1;
