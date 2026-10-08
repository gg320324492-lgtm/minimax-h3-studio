import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Scene} from '../../../schemas/showcase-v1';
import {CameraRig} from '../common/CameraRig';
// Fonts and scaling are NOT theme-scoped, so importing them is correct.
// Everything that IS theme-scoped (palette, type, spacing, shadow) must come
// from useDesign() — see tests/test_design_system.py.
import {FONT_SANS, scaleFor} from '../design/tokens';
import {useDesign} from '../design/styleBible';
import {SpecularSweep} from '../common/primitives';

/**
 * Scene — Logo lockup + Outro / CTA (reference film: "金色 Logo Lockup、CTA 结尾").
 *
 * ── THE `logo` TYPE AND `LOCKED_SCENE_TYPES` ─────────────────────────────────
 *
 * `studio/scripts/locked_fields.py` carries `LOCKED_SCENE_TYPES = frozenset(
 * {'logo'})`, and its comment says why: "`logo` is a scene TYPE in
 * showcase-v1.ts:36, so the brand mark is a scene, not a field. Locking the
 * type is what stops a repair from rerouting it to a chart to make it fit."
 *
 * WHAT THAT LOCK ACTUALLY WAS. Until P26 it guarded a type that had NO renderer:
 * a repair loop protecting `logo` from being rerouted protected a scene that
 * would have rendered `MissingScene` ("not implemented in P4") either way. That
 * did not make the lock wrong — 11.2's point (a repair may not reroute a brand
 * scene) is independent of whether the scene draws — but it made the lock
 * UNFALSIFIABLE: no rendering path existed on which rerouting `logo` could be
 * observed to change a frame. Registering a renderer gives the lock an artefact.
 * The lock itself is untouched; `tests/test_locked_fields.py` still pins it.
 *
 * ── WHAT THIS RENDERS, AND WHY IT IS DESIGN RATHER THAN A CONTENT PRINT ──────
 *
 * A lockup is a grammar: a MARK (a procedural glyph, drawn from the accent, not
 * an image asset the repo does not have), a WORDMARK (the brand line from
 * `content`), optionally a TAGLINE, and the settle that brings them on. The
 * graph owns the words; the grammar — gold, spacing, the mark, the reveal — is
 * the design system's, the same split as `KpiHero`.
 *
 * The brand mark is PROCEDURAL on purpose. There is no brand asset in the
 * repository, and inventing one would be the C failure ("做了就是编"). A
 * geometric mark derived from the tokens is a lockup grammar the graph can fill,
 * which is exactly what "Lockup" means — it is not a claim to a real brand.
 */

const MARK_BOX = 96;

/** The procedural mark: a gold ring with an inset bar — brand motion, not a logo file. */
const LockupMark: React.FC<{s: number; enter: number}> = ({s, enter}) => {
  const {PALETTE} = useDesign();
  const size = MARK_BOX * s;
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.28,
        border: `${5 * s}px solid ${PALETTE.accent}`,
        boxSizing: 'border-box',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transform: `scale(${0.7 + 0.3 * enter}) rotate(${(1 - enter) * -18}deg)`,
        opacity: enter,
      }}
    >
      <div style={{width: size * 0.34, height: size * 0.34, background: PALETTE.accent, borderRadius: size * 0.08}} />
    </div>
  );
};

/** Shared lockup: mark + wordmark (+ tagline). Both scenes draw the same brand. */
const Lockup: React.FC<{name: string; tagline: string; s: number; enter: number; scale?: number}> = ({
  name,
  tagline,
  s,
  enter,
  scale = 1,
}) => {
  const {PALETTE, SPACE, TYPE} = useDesign();
  return (
    <div style={{display: 'flex', alignItems: 'center', gap: SPACE.lg * s, transform: `scale(${scale})`, opacity: enter}}>
      <LockupMark s={s} enter={enter} />
      <div style={{display: 'flex', flexDirection: 'column'}}>
        <div
          style={{
            fontFamily: FONT_SANS,
            fontSize: TYPE.heading.size * s,
            fontWeight: 700,
            letterSpacing: '-0.02em',
            color: PALETTE.ink,
          }}
        >
          {name}
        </div>
        {tagline ? (
          <div
            style={{
              fontFamily: FONT_SANS,
              fontSize: TYPE.annotation.size * 1.1 * s,
              letterSpacing: TYPE.annotation.tracking,
              textTransform: 'uppercase',
              color: PALETTE.accent,
              marginTop: 6 * s,
            }}
          >
            {tagline}
          </div>
        ) : null}
      </div>
    </div>
  );
};

/** Scene — Logo lockup on the near-empty ground, with one specular sweep. */
export const Logo: React.FC<{scene: Scene}> = ({scene}) => {
  const {MOTION} = useDesign();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = scaleFor(comp.width, comp.height);
  const c = (scene.content ?? {}) as Record<string, unknown>;

  const name = c.name !== undefined ? String(c.name) : '';
  const tagline = c.tagline !== undefined ? String(c.tagline) : '';

  const enter = spring({
    frame,
    fps: comp.fps,
    config: MOTION.springs.settle,
    durationInFrames: Math.round(MOTION.enterSeconds * comp.fps),
  });

  return (
    <CameraRig camera={scene.camera} motion={scene.motion} durationInFrames={scene.durationInFrames}>
      <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
        <Lockup name={name} tagline={tagline} s={s} enter={Math.min(Math.max(enter, 0), 1)} />
        <SpecularSweep delayFrames={Math.round(MOTION.enterSeconds * comp.fps)} />
      </div>
    </CameraRig>
  );
};

/**
 * Scene — Outro / CTA. The lockup held small, a call to action at display scale,
 * and a settle. The CTA text is the graph's; the composition is the closing
 * beat the reference names ("CTA 结尾").
 */
export const Outro: React.FC<{scene: Scene}> = ({scene}) => {
  const {MOTION, PALETTE, SPACE, TYPE} = useDesign();
  const frame = useCurrentFrame();
  const comp = useVideoConfig();
  const s = scaleFor(comp.width, comp.height);
  const c = (scene.content ?? {}) as Record<string, unknown>;

  const cta = c.cta !== undefined ? String(c.cta) : c.text !== undefined ? String(c.text) : '';
  const sub = c.sub !== undefined ? String(c.sub) : '';
  const name = c.name !== undefined ? String(c.name) : '';
  const tagline = c.tagline !== undefined ? String(c.tagline) : '';

  const lockupIn = spring({
    frame,
    fps: comp.fps,
    config: MOTION.springs.settle,
    durationInFrames: Math.round(MOTION.enterSeconds * comp.fps),
  });
  const ctaIn = spring({
    frame: frame - Math.round(0.3 * comp.fps),
    fps: comp.fps,
    config: MOTION.springs.hero,
    durationInFrames: Math.round(0.9 * comp.fps),
  });

  return (
    <CameraRig camera={scene.camera} motion={scene.motion} durationInFrames={scene.durationInFrames}>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: SPACE.xl * s,
        }}
      >
        {name ? <Lockup name={name} tagline={tagline} s={s} enter={Math.min(Math.max(lockupIn, 0), 1)} scale={0.72} /> : null}

        <div
          style={{
            textAlign: 'center',
            opacity: Math.min(Math.max(ctaIn, 0), 1),
            transform: `translateY(${(1 - Math.max(Math.min(ctaIn, 1), 0)) * 24 * s}px)`,
          }}
        >
          <div
            style={{
              fontFamily: FONT_SANS,
              fontSize: TYPE.displayL.size * 0.62 * s,
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: PALETTE.ink,
              lineHeight: 1.15,
            }}
          >
            {cta}
          </div>
          {sub ? (
            <div style={{fontFamily: FONT_SANS, fontSize: TYPE.subheading.size * s, color: PALETTE.inkMuted, marginTop: SPACE.md * s}}>
              {sub}
            </div>
          ) : null}
        </div>

        <div
          style={{
            width: interpolate(ctaIn, [0, 1], [0, 200]) * s,
            height: 4 * s,
            background: PALETTE.accent,
          }}
        />
      </div>
    </CameraRig>
  );
};
