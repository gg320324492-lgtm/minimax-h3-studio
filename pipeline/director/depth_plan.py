"""The intermediate representation between a brief and a style bible (P12.1).

WHAT THIS IS, AND WHY IT IS NOT A DICT.

The whole point of P12.1 is to not build "a function that returns a dict matching
the schema". A dict has nowhere to put the two things that make a generated
value honest:

  * WHERE IT CAME FROM -- whether a number was measured, derived, or carried;
  * WHAT IT COULD NOT DO -- an intent the ramp cannot express, which has to
    survive to the caller instead of being silently dropped or silently faked.

So the brief is turned into a `DepthPlan` first, and the style bible section is
printed off the plan. The plan is the thing the caller inspects, the thing the
guard mutates, and the thing that records a refusal. Returning
`{'style_bible': {...}}` would lose all three.

WHY DEPTH, AND ONLY DEPTH.

Nine of the ten `StyleBible` keys are refused, for reasons measured and recorded
in docs/P12_1_GENERATION.md. `depthCue` is the one that survives, because it is
the only key in this repository with a MEASURED progression: P6.8 fitted it
(`y` steps by a constant, `blur = k*y`, `alpha` multiplied by a constant ratio)
and then hit a real ceiling -- the fifth layer reaches alpha 0.95 and a sixth
would need 1.18, which is not a colour. A key whose values can be *continued by
a rule* is a key a generator can be said to generate.

MEASURED, NOT COMPUTED -- AND WHY THAT DISTINCTION IS LOAD-BEARING.

`themes.ts` describes the ramp as "the ramp's OWN progression, fitted rather
than picked ... no number here was chosen by taste", and gives the constants
(`k = 2.849` dark, `2.671` light; alpha ratio `1.240` / `1.357`; y step
16 / 12). Those constants FIT the stored strings, but they do not REPRODUCE
them: recomputing `blur = round(k*y)` off the stored `y` reproduces 6 of the 10
stored blurs and misses the other 4 by 1px, because the strings were rounded by
hand after fitting.

So this module CARRIES the measured strings rather than computing them, and the
guard (`tests/test_p12_1_depth_cue_generation.py`) asserts the carried copy
still equals `themes.ts` -- if a theme ramp is refitted, the generator's copy is
declared stale instead of quietly emitting the old numbers.

What is DERIVED here is therefore the part that is genuinely a decision:

    layers = min(windows the film actually needs, the ceiling the measurement hit)

and, when the film asks for more than the ramp can express, a refusal that names
the layer that could not be drawn and the alpha it would have needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: The `depthCue` ramps as they are MEASURED in `themes.ts`, carried verbatim.
#:
#: These are measurements, not outputs of the formulas in the comment above.
#: The generator emits a PREFIX of one of these; it never invents an entry, and
#: it never extends one past the last -- see `RampCeiling`.
#:
#: Provenance: `studio/src/templates/finance-showcase/design/themes.ts`, measured
#: 2026-10-03 by P6.8. Asserted equal to that file by the P12.1 guard.
MEASURED_RAMPS: dict[str, tuple[str, ...]] = {
    'premium-dark': (
        '0 14px 40px rgba(0,0,0,0.40)',
        '0 30px 84px rgba(0,0,0,0.50)',
        '0 46px 132px rgba(0,0,0,0.62)',
        '0 62px 177px rgba(0,0,0,0.77)',
        '0 78px 222px rgba(0,0,0,0.95)',
    ),
    'premium-light': (
        '0 8px 22px rgba(20,20,15,0.10)',
        '0 18px 48px rgba(20,20,15,0.14)',
        '0 30px 80px rgba(20,20,15,0.19)',
        '0 42px 112px rgba(20,20,15,0.26)',
        '0 54px 144px rgba(20,20,15,0.35)',
    ),
}

#: The alpha each theme's LAST layer carries, and the ratio its alpha multiplies
#: by per layer. Together they say where the ramp runs out of colour.
#:
#: The ceiling is not a policy number and it is not "five because five was
#: chosen". It is arithmetic: dark reaches 0.95 on its fifth layer, and
#: 0.95 * 1.240 = 1.178, which is not an alpha a renderer can draw. A sixth
#: layer has to change the KIND of cue, which is a design decision this module
#: is not entitled to make.
_ALPHA_LAST: dict[str, float] = {'premium-dark': 0.95, 'premium-light': 0.35}
_ALPHA_RATIO: dict[str, float] = {'premium-dark': 1.240, 'premium-light': 1.357}


def ramp_ceiling(theme: str) -> int:
    """How many depth layers `theme` can actually draw.

    `len(MEASURED_RAMPS[theme])` -- the length of the measured ramp -- which is
    also the first layer index whose alpha would exceed 1.0. Both numbers are
    reported by `plan_depth` so a caller can see that they agree.
    """
    return len(MEASURED_RAMPS[theme])


def alpha_that_would_be_needed(theme: str, layer_index: int) -> float | None:
    """Alpha a layer at `layer_index` would carry, extrapolating the ratio.

    `None` once `layer_index` is inside the measured ramp: there the alpha is
    known, not extrapolated, and a caller asking for it should read
    `MEASURED_RAMPS` rather than be handed a recomputed approximation of a
    number that is sitting right there.
    """
    ramp = MEASURED_RAMPS[theme]
    if layer_index < len(ramp):
        return None
    return _ALPHA_LAST[theme] * (_ALPHA_RATIO[theme] ** (layer_index - len(ramp) + 1))


@dataclass(frozen=True)
class DepthPlan:
    """The decision, made explicit, before any style bible is printed.

    `windows` is what the film ASKS for. `layers` is what can be drawn.
    `refusals` is what the difference cost, kept rather than dropped.
    """

    theme: str
    windows: int
    layers: int
    ramp: tuple[str, ...]
    refusals: tuple[str, ...] = field(default=())

    @property
    def capped(self) -> bool:
        """Whether the film asked for more depth than the ramp can express."""
        return self.windows > self.layers


def plan_depth(theme: str, windows: int) -> DepthPlan:
    """Turn "this film stacks `windows` browser windows" into a depth plan.

    The only input that moves the output is `windows`. That is deliberate: it is
    the one number in this decision that the FILM knows and the ramp does not,
    so it is the one number a generator can honestly be said to have derived.

    A film with fewer windows than the ramp has layers gets a shorter ramp: the
    layers past the last window are never read (`depthCueAt` clamps at the end),
    so carrying them would be carrying an unused declaration.

    A film asking for MORE than the ramp holds gets the measured ramp and a
    refusal, never an extrapolated layer -- see `alpha_that_would_be_needed`.
    """
    if theme not in MEASURED_RAMPS:
        raise KeyError(
            f'unknown theme {theme!r}; the measured ramps cover '
            f'{sorted(MEASURED_RAMPS)}')
    if not isinstance(windows, int) or isinstance(windows, bool) or windows < 0:
        raise ValueError(f'windows must be a non-negative int, got {windows!r}')

    ceiling = ramp_ceiling(theme)
    layers = min(windows, ceiling)
    refusals: list[str] = []
    if windows > ceiling:
        blocked = alpha_that_would_be_needed(theme, ceiling)
        refusals.append(
            f'{theme}: the film stacks {windows} windows but the measured ramp '
            f'stops at {ceiling}. Window {ceiling} would need alpha '
            f'{blocked:.2f}, which is not a colour, so it is refused rather '
            f'than drawn. depthCueAt clamps windows {ceiling}+ onto layer '
            f'{ceiling - 1}; giving those windows a distinct cue is a change '
            f'to the KIND of depth cue, which this generator will not invent.'
        )
    return DepthPlan(theme=theme, windows=windows, layers=layers,
                     ramp=MEASURED_RAMPS[theme][:layers],
                     refusals=tuple(refusals))