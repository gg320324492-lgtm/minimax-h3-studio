/**
 * Executable check of the render scale and the camera ramp (P8 regression guard).
 *
 * Run:  npx tsx src/templates/finance-showcase/design/scale.check.ts
 *
 * Two defects are pinned here, and both were invisible to a render that
 * succeeded.
 *
 * 1. The scale read only the frame's HEIGHT. Nothing in the template had a width
 *    to read, so a 1080x1920 render of a wide graph was scaled by 1920/1080 =
 *    1.7778 and kept a 1920-wide design frame's geometry inside a 1080-wide
 *    frame. Measured on the demo graph's dashboard scene: 18 columns authored,
 *    12 visible, ~357px cut off each edge. A render that completes and produces
 *    a file is exactly what this defect looks like, so the assertion has to be
 *    about the arithmetic rather than about the picture.
 *
 * 2. The camera ramp was `Math.max(1, seconds * fps / sceneFrames)` used against
 *    normalised scene time. The `Math.max` raises the ramp UP to 1, so for any
 *    scene longer than the nominal camera duration — 229 frames against 2.6s at
 *    60fps — the ramp was exactly 1 and the camera move spanned the WHOLE scene.
 *    `premiumCameraSeconds` and `energeticCameraSeconds` were therefore dead in
 *    every shipped scene: the number was computed and then discarded. The fps
 *    dependence that produced was real but narrow, and only bit scenes shorter
 *    than the nominal duration.
 *
 *    The fix makes the token live, so it CHANGES existing 16:9 renders: a
 *    premium camera move now completes at frame 156 of a 229-frame scene instead
 *    of drifting to the last frame. That is the point — the alternative was to
 *    leave a declared duration inert — but it is a change to the motion language
 *    of a delivered template and it is recorded here rather than discovered later.
 *    Measured effect on the demo graph at frame 343: 2.49% of the browser stack's
 *    on-screen width, because the camera is 46% further along at that frame
 *    (t 0.500 -> 0.731).
 *
 * Dependency-free (tokens.ts imports only ./themes) so it runs in a millisecond
 * and cannot fail for reasons unrelated to the maths.
 */

import {DESIGN_HEIGHT, DESIGN_WIDTH, MOTION, cameraMoveFrames, scaleFor} from './tokens';

let failures = 0;

const check = (name: string, ok: boolean, detail = ''): void => {
  if (ok) {
    console.log(`  ok   ${name}`);
  } else {
    failures += 1;
    console.log(`  FAIL ${name}${detail ? ` — ${detail}` : ''}`);
  }
};

const near = (a: number, b: number, eps = 1e-9): boolean => Math.abs(a - b) <= eps;

console.log('scaleFor: the design frame is 1920x1080 and every 16:9 render is exact');
check('1920x1080 scales by exactly 1', near(scaleFor(1920, 1080), 1), String(scaleFor(1920, 1080)));
check('3840x2160 scales by exactly 2', near(scaleFor(3840, 2160), 2), String(scaleFor(3840, 2160)));
check(
  '1920x1080 and 3840x2160 are the SAME picture, not two similar ones',
  near(scaleFor(1920, 1080) * 2, scaleFor(3840, 2160))
);

console.log('\nscaleFor: a frame that is proportionally taller is bounded by its WIDTH');
// The defect itself, stated as an assertion: the height-only scale was 1.7778 and
// the contain scale is 0.5625. If this ever passes again the bug is back.
check(
  '1080x1920 is 0.5625 (fit to width), not 1.7778 (fit to height)',
  near(scaleFor(1080, 1920), 1080 / 1920),
  String(scaleFor(1080, 1920))
);
check(
  '1080x1920 does NOT take the height-only scale',
  !near(scaleFor(1080, 1920), 1920 / 1080)
);

console.log('\nscaleFor: the scale is min of both ratios, over a sweep of frames');
const frames: [number, number][] = [
  [1920, 1080], [3840, 2160], [1080, 1920], [1080, 1080], [1440, 1080],
  [2560, 1440], [720, 1280], [2160, 3840], [1920, 800], [800, 1920], [1, 1],
];
for (const [w, h] of frames) {
  const want = Math.min(w / DESIGN_WIDTH, h / DESIGN_HEIGHT);
  check(
    `${w}x${h} -> ${want.toFixed(4)}`,
    near(scaleFor(w, h), want),
    `got ${scaleFor(w, h).toFixed(4)}`
  );
  // The property the defect broke: the design frame, mapped through the scale,
  // must fit INSIDE the render frame on both axes. This is the containment
  // guarantee restated as pixels, so it is checked in pixels.
  check(
    `${w}x${h} contains the design frame`,
    DESIGN_WIDTH * scaleFor(w, h) <= w + 1e-9 && DESIGN_HEIGHT * scaleFor(w, h) <= h + 1e-9,
    `scaled design frame is ${(DESIGN_WIDTH * scaleFor(w, h)).toFixed(1)}x` +
      `${(DESIGN_HEIGHT * scaleFor(w, h)).toFixed(1)}`
  );
}

console.log('\ncameraMoveFrames: a duration is wall-clock, so it scales WITH fps');
check(
  'premium 60fps is 2.6s = 156 frames',
  near(cameraMoveFrames('premium', 229, 60), MOTION.premiumCameraSeconds * 60),
  String(cameraMoveFrames('premium', 229, 60))
);
check(
  'premium 30fps is half the frames',
  cameraMoveFrames('premium', 229, 60) === 2 * cameraMoveFrames('premium', 229, 30),
  `${cameraMoveFrames('premium', 229, 60)} vs ${cameraMoveFrames('premium', 229, 30)}`
);
check(
  'energetic 30fps is half the frames',
  cameraMoveFrames('energetic', 229, 60) === 2 * cameraMoveFrames('energetic', 229, 30)
);
check(
  'minimal is the scene, in any fps',
  cameraMoveFrames('minimal', 229, 60) === 229 && cameraMoveFrames('minimal', 229, 30) === 229,
  `${cameraMoveFrames('minimal', 229, 60)} / ${cameraMoveFrames('minimal', 229, 30)}`
);
check(
  'the camera move does not depend on the scene length',
  cameraMoveFrames('premium', 60, 60) === cameraMoveFrames('premium', 900, 60),
  'premium moved when only the scene length changed'
);

console.log('\ncameraMoveFrames: the token is live, not clamped away');
// The regression is an ARITHMETIC one, so it is asserted as arithmetic. The old
// form was `Math.max(1, seconds * fps / sceneFrames)`: for a 229-frame scene at
// 60fps that is max(1, 0.681) = 1, so the camera move ran the length of the scene
// and the 2.6s token decided nothing. A clamp that raises a value can only ever
// make a duration longer than it asked for, which is how the token died without
// any test noticing — `rampOf` was correct as written and still meant nothing.
const longScene = 229;
const nominal = MOTION.premiumCameraSeconds * 60;
const oldRamp = Math.max(1, nominal / longScene);
check(
  'the old ramp really was clamped to 1 — this is why the token was inert',
  oldRamp === 1,
  `old ramp was ${oldRamp}, so the defect this guards is not the one above`
);
check(
  `the move is the nominal 2.6s (${nominal} frames), not the scene's ${longScene}`,
  cameraMoveFrames('premium', longScene, 60) === nominal,
  String(cameraMoveFrames('premium', longScene, 60))
);
check(
  'the move is shorter than the scene it moves through',
  cameraMoveFrames('premium', longScene, 60) < longScene,
  'the camera would run the length of the scene again'
);
check(
  'a scene shorter than the move does not finish it',
  cameraMoveFrames('premium', 100, 60) > 100,
  'a short scene would drag the move out to its own length'
);
check(
  'energetic is its own token, not the scene',
  cameraMoveFrames('energetic', longScene, 60) === MOTION.energeticCameraSeconds * 60 &&
    cameraMoveFrames('energetic', longScene, 60) < cameraMoveFrames('premium', longScene, 60)
);

if (failures) {
  console.log(`\n${failures} check(s) failed`);
  process.exit(1);
}
console.log('\nall scale and ramp checks passed');
