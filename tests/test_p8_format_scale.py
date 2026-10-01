"""The render scale, the camera ramp and the metadata fallback (P8 guards).

Three defects that a successful render cannot show, so the assertions are about
arithmetic and about which errors are raised — not about a picture:

  1. The scale read the frame's HEIGHT only. Nothing in the template had a width
     to read, so 1080x1920 scaled by 1.7778 and kept a 1920-wide design frame's
     geometry inside a 1080-wide one: 18 columns authored, 12 visible, ~357px cut
     off each edge.
  2. The camera ramp was a fraction of the scene that depended on fps, so frame
     N rendered a different camera position at 30 and 60 fps.
  3. `calculateMetadata` answered every invalid graph with `1920x1080@60 1
     frames`, so a string where a number belonged surfaced as a complaint about
     the requested FRAME NUMBER.

Each has an executable check next to the code it covers — the same arrangement
`test_perspective_math.py` uses for the projection maths, for the same reason:
a re-implementation in Python would be just as wrong as the TypeScript, and
reading the source does not reveal a fraction that is the right way round.

Where node is unavailable the behavioural tests SKIP rather than fail. A geometry
check must not be the reason the suite is red on a machine that cannot run it,
and a skip that nobody reads is still better than a suite that is red for the
wrong reason.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase'
SCHEMAS = ROOT / 'studio' / 'src' / 'schemas'

CHECKS = (
    TEMPLATE / 'design' / 'scale.check.ts',
    SCHEMAS / 'showcaseMeta.check.ts',
)

#: Every PRODUCTION TypeScript file in the wide template. The source-level
#: guards below sweep these rather than naming files, because the defect they
#: guard against is a pattern and a named-file check only ever covers the file
#: someone remembered.
#:
#: `*.check.ts` is excluded on purpose. These guards look for text patterns, and a
#: check file is full of them deliberately — `scale.check.ts` asserts that
#: `1920 / 1080` is NOT the scale, which is the very string the sweep forbids.
#: The first version of this file swept everything and failed on that assertion.
SOURCES = sorted(
    src
    for src in (*TEMPLATE.rglob('*.ts'), *TEMPLATE.rglob('*.tsx'))
    if not src.name.endswith('.check.ts')
)

_NPX = shutil.which('npx') or shutil.which('npx.cmd')


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
@pytest.mark.parametrize('check', CHECKS, ids=lambda p: p.stem)
def test_check_passes(check: Path):
    proc = subprocess.run(
        [_NPX, 'tsx', str(check)],
        cwd=ROOT / 'studio',
        capture_output=True,
        text=True,
        timeout=300,
        # utf-8, not the gbk locale default: see test_chart_math's note —
        # locale-decoded capture eats the message exactly when it is needed
        encoding='utf-8',
        errors='replace',
    )
    assert proc.returncode == 0, f'{check.name} failed:\n{proc.stdout}\n{proc.stderr}'


def test_no_height_only_scaler_survives():
    """`scaleFrom` is gone, and nothing divides by the design height directly.

    The behavioural check proves `scaleFor` behaves; this proves nothing else
    computes a scale of its own. Those are different failures — a fifth scene
    that reaches for `comp.height / 1080` would pass every assertion in
    scale.check.ts and still crop on a portrait frame, because the check only
    covers the function it imports.
    """
    offenders = []
    for src in SOURCES:
        text = src.read_text(encoding='utf-8')
        if 'scaleFrom' in text:
            offenders.append(f'{src.name}: still references scaleFrom')
        for line in text.splitlines():
            if line.lstrip().startswith(('*', '//')):
                continue  # prose about the old behaviour is not the old behaviour
            if '/ 1080' in line or '/DESIGN_HEIGHT' in line:
                offenders.append(f'{src.name}: {line.strip()}')
    assert not offenders, 'height-only scaling is back:\n  ' + '\n  '.join(offenders)


def test_scale_is_asked_for_both_axes():
    """A caller of the scaler has to hand it both dimensions.

    `scaleFor(comp.width, comp.height)` and `scaleFor(comp.height, comp.width)`
    are both a number and only one is right, so the argument order is pinned in
    source. This is the same class of guard as the projection's fraction: a
    transposition compiles and returns a plausible value.
    """
    token = (TEMPLATE / 'design' / 'tokens.ts').read_text(encoding='utf-8')
    assert 'export const scaleFor = (width: number, height: number)' in token, (
        'scaleFor must take (width, height) — reversing the pair still type-checks'
    )
    assert 'Math.min(width / DESIGN_WIDTH, height / DESIGN_HEIGHT)' in token, (
        'the scale must be the MIN of the two ratios; a max or a single axis '
        'overruns the narrower edge'
    )

    callers = [src for src in SOURCES if 'scaleFor(' in src.read_text(encoding='utf-8')]
    assert callers, 'nothing calls scaleFor — has the scaler been bypassed?'
    for src in callers:
        text = src.read_text(encoding='utf-8')
        if src.name == 'tokens.ts':
            continue  # the declaration itself
        for line in text.splitlines():
            if 'scaleFor(' not in line:
                continue
            assert 'width' in line and 'height' in line, (
                f'{src.name}: {line.strip()} — pass both axes'
            )


def test_camera_ramp_is_not_a_fraction_of_the_scene():
    """The ramp must not be divided by the scene's length.

    `seconds * fps / sceneFrames` looks like a duration and behaves like a
    fraction, which is how the fps dependence survived: halving fps halved the
    camera's share of the scene. The guard is on the absence of the division,
    because the property tests in scale.check.ts cannot tell the two apart when
    only one fps is exercised per case.
    """
    token = (TEMPLATE / 'design' / 'tokens.ts').read_text(encoding='utf-8')
    start = token.index('export const cameraMoveFrames')
    body = token[start:token.index('\n};', start)]

    # `minimal` legitimately uses the scene length — the move IS the scene — so
    # the guard is on what happens AFTER that branch's statement, not on the word
    # itself. The old form was `(seconds * fps) / Math.max(dur, 1)`: a
    # duration-shaped expression on the left and a scene-shaped one on the right,
    # which is why it read as a frame count and behaved as a fraction of the scene.
    marker = "'minimal'"
    assert marker in body, 'the minimal branch must still be there to be excluded'
    head, _, tail = body.partition(marker)
    after_minimal = tail[tail.index(';') + 1:]  # past the minimal early return
    assert 'sceneFrames' not in after_minimal, (
        'the scene length must not influence the move length for any other preset'
    )
    assert 'seconds * fps' in after_minimal, (
        'the move must be seconds * fps, converted through fps like every other '
        'duration in the template'
    )

    rig = (TEMPLATE / 'common' / 'CameraRig.tsx').read_text(encoding='utf-8')
    assert 'rampOf' not in rig, (
        'CameraRig must not carry its own ramp — one implementation, imported'
    )
    assert 'cameraMoveFrames' in rig, 'CameraRig should take the move length from tokens'


def test_invalid_graph_metadata_is_not_silently_defaulted():
    """Source-level counterpart to the behavioural check, for when node is absent.

    The tell of the old code was a fallback object literal in the metadata path.
    A default still has to exist — Remotion calls calculateMetadata before props
    arrive — so this does not forbid one; it forbids the fallback being reachable
    from a document that declares graph fields, which is the branch that was wrong.
    """
    meta = (SCHEMAS / 'showcaseMeta.ts').read_text(encoding='utf-8')
    assert 'if (isAbsent(raw)) return {...FALLBACK};' in meta, (
        'the absent-props branch must come first and be the only silent path'
    )
    assert 'throw new Error' in meta, 'an invalid graph must be rejected, not defaulted'
    assert 'safeParse' in meta, 'the metadata must validate rather than assume'
    # and the guard must not be so loose that a real graph is treated as absent
    assert 'GRAPH_KEYS' in meta, (
        'the absent test must key on declared graph fields, not on one of them'
    )


def test_the_chart_plot_box_is_the_design_box_scaled_not_the_frame():
    """The frame's height is not a design quantity, and reading it as one held.

    `scaleFor` had already been fixed to take both axes, and every chart still
    sized its plot box from `comp.height - padY`. That is the same number as
    `DESIGN_HEIGHT * s - padY` on every same-aspect format, which is why a
    1920x1080 render and a 3840x2160 render both looked right and the bug was
    invisible. On 1080x1920 the two expressions part company: s = 0.5625, so the
    design height is 607.5 while the frame is 1920, and the chart was STRETCHED
    rather than scaled -- five bars measured 1223/1012/1331/943/1557 px tall
    against 319/285/345/260/406 for the scaled design box, 3.4x too tall, with
    the baseline at y=1824 instead of 532.

    So this asserts the shape of the expression rather than a value: the plot
    box may not be derived from the frame. Every same-aspect format renders
    identically either way, so only a format with a different aspect ratio can
    tell them apart -- which is the same reason the defect survived from P7.1.
    """
    frame = (TEMPLATE / 'charts' / 'ChartFrame.tsx').read_text(encoding='utf-8')
    assert 'DESIGN_WIDTH * s' in frame and 'DESIGN_HEIGHT * s' in frame, (
        'the plot box must be the DESIGN box scaled by s'
    )
    for line in frame.splitlines():
        stripped = line.strip()
        if stripped.startswith(('const W =', 'const H =')):
            assert 'comp.width' not in stripped and 'comp.height' not in stripped, (
                f'plot box derived from the frame, which is not a design quantity: {stripped}'
            )
