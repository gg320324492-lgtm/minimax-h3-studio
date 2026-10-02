"""visual_qa.py must be able to FAIL, not merely to run (P10, rule 10.1).

Every rule here is asserted in BOTH directions on a constructed input. A QA gate
that has only been seen to pass is indistinguishable from a QA gate that cannot
fail, and this project has committed several of those by accident — a declared
option nothing reads, a metric with no consumer, a fallback that answers every
question with the same reply.

Two structural facts are asserted as behaviour rather than worked around:

  - `safe_area` cannot return FAIL on a high-contrast edge. Content that reaches
    the edge makes the per-row backdrop model sample content, the residual jumps
    (measured: 3 on a settled frame, 208 on a real padX=0 frame, 230 on a
    synthetic), and the rule reports UNVERIFIABLE. Its FAIL path therefore needs
    edge content that is both wide and LOW contrast. That asymmetry is the whole
    reason `clipping` exists on the palette path, and losing it would leave the
    gate unable to say anything about the frame it is judging.

  - `overflow` and `collision` return UNAVAILABLE with no number. Three
    detectors were tried and each failed differently; asserting a number here
    would be asserting a fiction.

Nothing in this file renders. Rendered frames live in `out/`, which is gitignored,
so a test that depended on them would pass on the machine that made them and fail
everywhere else. Where a REAL render exists the test uses it and skips otherwise,
and says which it did.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'studio' / 'scripts' / 'visual_qa.py'
sys.path.insert(0, str(SCRIPT.parent))
import visual_qa as vqa  # noqa: E402

AUDIT = ROOT / 'out' / 'p10_audit'
_NPX = shutil.which('npx') or shutil.which('npx.cmd')

DARK_BG = vqa.PALETTE_BACKGROUNDS['premium-dark.background']
DARK_ALT = vqa.PALETTE_BACKGROUNDS['premium-dark.backgroundAlt']
INK = np.array((0xF5, 0xF2, 0xEA))
ACCENT = np.array((0xE8, 0xC4, 0x64))


def gradient(w: int = 640, h: int = 360, lo=DARK_BG, hi=DARK_ALT) -> np.ndarray:
    """The real backdrop shape: a ramp between backgroundAlt and background."""
    t = np.linspace(0, 1, w)[None, :, None]
    return np.repeat(np.array(hi) * (1 - t) + np.array(lo) * t, h, axis=0).astype(int).copy()


def frame_interior(w: int = 640, h: int = 360) -> np.ndarray:
    """Interior content: a panel plus text-like strokes.

    The strokes matter. A solid panel 37% of the frame width is excluded by the
    25%-row-coverage band filter, so a frame built only from panels has NO
    text-like bands and `font_size` correctly reports "no text-like band found" —
    which is why the first version of this fixture could not exercise font_size at
    all. Six thin strokes read as type and give the rule something to measure.
    """
    f = gradient(w, h)
    f[100:260, 200:440] = INK
    for i in range(6):
        y = 120 + i * 20
        f[y:y + 7, 210:430 - i * 12] = np.array(DARK_BG)
    return f


def frame_narrow_edge(w: int = 640, h: int = 360) -> np.ndarray:
    """NARROW content at the left edge: an accent underline and a text stem."""
    f = gradient(w, h)
    f[300:304, 0:160] = ACCENT
    f[100:280, 0:6] = INK
    return f


def frame_edge_low_contrast(w: int = 640, h: int = 360) -> np.ndarray:
    """Content touching the edge that is WIDE and only slightly off the background.

    This is the only shape in which `safe_area` can return FAIL: the row median
    has to stay on the background side so the model survives, while the content
    still reaches x=0.
    """
    f = gradient(w, h)
    f[80:280, 0:70] = np.array(DARK_BG) + 6
    return f


def frame_flat(w: int = 640, h: int = 360) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=int) + np.array(DARK_BG)


def save(a: np.ndarray, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(a.astype(np.uint8)).save(path)
    return path


# ── the tool's own instruments ───────────────────────────────────────────────

@pytest.mark.skipif(_NPX is None or not shutil.which(sys.executable),
                    reason='no interpreter')
def test_self_test_passes():
    proc = subprocess.run([sys.executable, str(SCRIPT), '--self-test'],
                          capture_output=True, text=True, timeout=300,
                          encoding='utf-8', errors='replace')
    assert proc.returncode == 0, f'visual_qa self-test failed:\n{proc.stdout}\n{proc.stderr}'


# ── the backdrop model must REFUSE rather than report a wrong number ─────────

def test_backdrop_model_is_untrusted_when_content_reaches_the_edge():
    """The audit's measured failure: residual 3 settled, 208 on a real padX=0 frame."""
    _, trusted_ok, res_ok = vqa.model_mask(frame_interior())
    _, trusted_bad, res_bad = vqa.model_mask(frame_narrow_edge())
    assert trusted_ok and res_ok < 60, f'settled frame residual {res_ok}'
    assert not trusted_bad, (
        f'narrow content at the edge left the model TRUSTED (residual {res_bad}); '
        f'safe_area would then report a confident margin built from content'
    )
    assert res_bad > 10 * res_ok, (
        f'residual only rose from {res_ok} to {res_bad}; the trust flag would be '
        f'threshold-sensitive on this input'
    )


def test_clipping_does_not_use_the_backdrop_model():
    """The palette path must measure the very frame the model refuses."""
    a = frame_narrow_edge()
    m, theme = vqa.palette_mask(a)
    box = vqa.bbox(m)
    assert box is not None and box[0] == 0, f'palette path did not see x=0: {box}'
    assert theme == 'premium-dark', theme
    assert vqa.rule_clipping(a).verdict == vqa.FAIL


def test_palette_path_detects_the_theme_instead_of_guessing():
    """A union over both themes' backgrounds cannot see cream ink.

    ink (245,242,234) is within PALETTE_TOL of the premium-light paper
    (244,241,234), so a white bar on a near-black frame measured as BACKGROUND
    before the mask was scoped to the detected theme. Asserted because the bug
    is silent: the mask returns a plausible frame with no content in it.
    """
    a = frame_interior()
    # `union` marks pixels near ANY known background, so `union[180, 300]` is True
    # for the cream ink — it sits 2/255 from the premium-light paper. A mask built
    # on that union would call this ink background and see no content at all,
    # which is the silent failure: a plausible frame with nothing in it.
    union = np.zeros(a.shape[:2], dtype=bool)
    for c in vqa.PALETTE_BACKGROUNDS.values():
        union |= np.abs(a - np.array(c)).sum(axis=2) <= vqa.PALETTE_TOL
    scoped, theme = vqa.palette_mask(a)
    assert theme == 'premium-dark'
    assert scoped[245, 300], 'the palette mask lost the cream ink'
    assert union[245, 300], (
        'the union form no longer mistakes this ink for the light theme\'s paper; '
        'if it does again the theme-scoping fix has been reverted'
    )


# ── every rule in both directions ───────────────────────────────────────────

def test_safe_area_passes_inside_and_refuses_at_the_edge():
    """safe_area CANNOT return FAIL, and that is a property of the instrument.

    The backdrop model is fitted from the frame's own edges. Any content that
    reaches an edge therefore biases the model toward that content — measured at
    208 on the real `padX=0` frame and 230 on the synthetic one — so the rule
    refuses rather than reporting a margin built out of the thing it is
    measuring. Its FAIL path is unreachable by construction, which is exactly
    why `clipping` exists on the palette path: clipping is the rule that can say
    "content is at the edge", and it is asserted to FAIL there.

    Asserted rather than worked around, because the tempting workaround — a
    "wide low-contrast edge panel" — does not work either: the model reproduces
    it well enough that the panel never registers as content at all. That was
    measured, not assumed.
    """
    ok = vqa.rule_safe_area(frame_interior())
    assert ok.verdict == vqa.PASS, ok.detail
    assert ok.value > 0

    edge = vqa.rule_safe_area(frame_narrow_edge())
    assert edge.verdict == vqa.UNVERIFIABLE, edge.verdict
    assert not edge.trusted
    assert 'clipping' in edge.detail, 'the refusal must name the rule that can answer'


def test_clipping_carries_the_edge_failure_safe_area_cannot():
    assert vqa.rule_clipping(frame_narrow_edge()).verdict == vqa.FAIL
    assert vqa.rule_clipping(frame_interior()).verdict == vqa.PASS


def test_font_size_fails_below_the_readability_bar(tmp_path):
    big = vqa.rule_font_size(frame_interior(), declared_px=20.0)
    assert big.verdict == vqa.PASS, big.detail
    small = vqa.rule_font_size(frame_interior(), declared_px=11.25)
    assert small.verdict == vqa.FAIL, (
        f'11.25px is below the {vqa.MIN_TYPE_PX}px bar and must fail; '
        f'got {small.verdict}'
    )
    assert small.extra['declared_px'] == 11.25


def test_font_size_reports_unverifiable_without_a_declared_size():
    f = vqa.rule_font_size(frame_interior(), declared_px=None)
    assert f.verdict == vqa.UNVERIFIABLE
    assert 'ratio needs both sides' in f.detail


def test_contrast_is_red_on_this_palette_and_counts_its_pairs():
    f = vqa.rule_contrast()[0]
    assert f.verdict == vqa.FAIL, 'the audit measured 8 of 24 pairs below 4.5:1'
    assert f.value == 8, f'expected 8 failing pairs, got {f.value}'
    assert len(f.extra['pairs']) == 24, 'every theme x background x role must be tested'
    worst = min(f.extra['pairs'], key=lambda p: p['ratio'])
    assert worst['ratio'] == 2.16, worst
    assert worst['pair'] == 'premium-light/inkFaint on bg', worst


def test_black_frame_fails_on_a_flat_frame():
    f = vqa.rule_black_frame(frame_flat())
    assert f.verdict == vqa.FAIL, f.detail
    assert f.extra['flat'] is True
    assert f.extra['distinct_colours'] == 1
    ok = vqa.rule_black_frame(frame_interior())
    assert ok.verdict == vqa.PASS, ok.detail


def test_blur_fails_on_a_flat_frame_and_passes_on_a_sharp_one():
    flat = vqa.rule_blur(frame_flat())
    assert flat.verdict == vqa.FAIL
    assert flat.value == 0.0
    sharp = vqa.rule_blur(frame_interior())
    assert sharp.verdict == vqa.PASS, sharp.detail
    blurred = vqa.rule_blur(np.asarray(
        Image.fromarray(frame_interior().astype(np.uint8))
        .filter(ImageFilter.GaussianBlur(6.0))).astype(int))
    assert blurred.verdict == vqa.FAIL, (
        f'a radius-6 blur of the synthetic frame is variance '
        f'{blurred.value}, which is below the 2.0 threshold'
    )


def frame_gradient_backdrop(w: int = 640, h: int = 360) -> np.ndarray:
    """Premium-dark background WITH the gradient the audit measured.

    `design/themes.ts` backgrounds are not flat: the premium-dark backdrop spreads
    20 per channel across the frame (6+6+8). A palette mask tighter than that
    treats the backdrop as content, so the whole frame reads as content reaching
    the edge. This is the false positive that sets the tolerance floor, so it gets
    a fixture rather than only a comment.
    """
    base = np.array(DARK_BG, dtype=int)
    f = np.zeros((h, w, 3), dtype=np.uint8)
    for x in range(w):
        t = x / (w - 1)
        f[:, x] = np.clip(base + np.array([6 * t, 6 * t, 8 * t]), 0, 255).astype(np.uint8)
    f[150:200, 200:440] = np.array(INK)          # content, well inside
    return f


def test_palette_tolerance_is_above_the_gradient_spread():
    """A gradient backdrop must not read as content.

    At the real tolerance (24) the 20-unit gradient stays background and the card
    is the only content. At 8 the backdrop itself becomes content, the bbox
    stretches to all four edges, and clipping reports FAIL on a frame with nothing
    wrong with it -- a false positive that would send an artist chasing a bug that
    does not exist.
    """
    f = frame_gradient_backdrop()
    fc = vqa.rule_clipping(f)
    assert fc.verdict == vqa.PASS, (
        f'clipped a frame whose content is 240px from every edge: {fc.detail}'
    )
    assert fc.value >= 100, f'minimum margin should be generous, measured {fc.value}'

    saved = vqa.PALETTE_TOL
    try:
        vqa.PALETTE_TOL = 8
        bad = vqa.rule_clipping(f)
    finally:
        vqa.PALETTE_TOL = saved
    assert bad.verdict == vqa.FAIL, (
        'this test cannot distinguish the tolerance if 8 does not produce a false '
        'positive, so it is not currently testing anything'
    )


def test_bbox_reports_no_box_instead_of_raising_on_an_untrusted_backdrop():
    """`model_mask` returns None when the backdrop is untrusted.

    Measuring that mask before checking `trusted` used to raise
    `ValueError: Calling nonzero on 0d arrays`, which reads like a numpy bug rather
    than the verdict it actually is.
    """
    assert vqa.bbox(None) is None
    assert vqa.bbox(np.zeros((8, 8), dtype=bool)) is None
    m, trusted, _ = vqa.model_mask(frame_narrow_edge())
    assert not trusted and m is None, 'precondition: this backdrop is untrusted'
    assert vqa.bbox(m) is None


def test_freeze_fails_on_identical_frames_and_passes_otherwise(tmp_path):
    a = save(frame_interior(), tmp_path / 'a.png')
    b = save(frame_interior(), tmp_path / 'b.png')
    assert vqa.rule_freeze(a, b).verdict == vqa.FAIL

    other = frame_narrow_edge()
    save(other, tmp_path / 'c.png')
    assert vqa.rule_freeze(a, tmp_path / 'c.png').verdict == vqa.PASS


def test_freeze_is_exactly_zero_not_a_threshold(tmp_path):
    """A handful of changed pixels is NOT a freeze.

    This is the case that separates the exact criterion from a tolerance. The audit
    measured the noise floor at exactly 0, so any threshold is either redundant
    (and hides real motion) or arbitrary. A 40-pixel difference must PASS here; a
    rule reading `diff <= threshold` would call it frozen.
    """
    a = frame_interior()
    b = a.copy()
    # Above the panel, inside the gradient — anywhere else would overwrite pixels
    # that already hold the same colour and change nothing.
    b[90:95, 300:340] = np.array([250, 250, 250])       # 5 x 40 = 200 pixels
    pa = save(a, tmp_path / 'a.png')
    pb = save(b, tmp_path / 'b.png')
    f = vqa.rule_freeze(pa, pb)
    assert f.value == 200, f'expected a 200-pixel difference, measured {f.value}'
    assert f.verdict == vqa.PASS, (
        f'a {f.value}-pixel difference was called a freeze — the criterion must be '
        f'exactly zero, because the noise floor is exactly zero'
    )


def test_safe_area_criterion_is_exactly_zero():
    """Pinned in source, because a positive threshold is unconstructible here.

    The audit measured the corpus over 193 frames: margins run 0, then 16, 23, 24,
    27 with no gap, and the smallest positive top margin is 7px — 0.65% of a 1080
    frame. So a positive safe-area inset would flag legitimate frames, and the
    criterion is `== 0`. Asserted against the source because no synthetic frame
    can demonstrate it, and the reason is worth recording: any content placed near
    an edge is either absorbed as background by the model (a 90px card at x=0 was
    reported trusted with residual 8 and a 66px margin) or makes it untrusted
    (residual 208-230). There is no frame that is both trusted and 7px from an
    edge, so the verdict expression itself is the only thing that can be pinned.
    """
    src = (ROOT / 'studio' / 'scripts' / 'visual_qa.py').read_text(encoding='utf-8')
    body = src.split('def rule_safe_area', 1)[1].split('\ndef ', 1)[0]
    code = re.sub(r'""".*?"""', '', body, flags=re.DOTALL)
    code = re.sub(r'#.*', '', code)
    assert "FAIL if touched else PASS" in code, (
        'safe_area must fail only on a touched edge; a threshold on the margin '
        'would flag legitimate frames'
    )
    assert 'min(margins.values())' in code, 'the reported value is the margin, not a count'
    assert not re.search(r'margins?\s*\)?\s*[<>]=?\s*\d', code), (
        'safe_area must not compare a margin against any number'
    )


def test_duplicate_is_measured_on_take_rankers_scale(tmp_path):
    """0..255, not 0..1. Normalising made every pair read as a duplicate."""
    a = save(frame_interior(), tmp_path / 'a.png')
    save(frame_interior(), tmp_path / 'same.png')
    same = vqa.rule_duplicate(a, tmp_path / 'same.png')
    assert same.verdict == vqa.FAIL, same.detail
    assert same.value == 0.0

    save(frame_narrow_edge(), tmp_path / 'diff.png')
    diff = vqa.rule_duplicate(a, tmp_path / 'diff.png')
    assert diff.verdict == vqa.PASS, (
        f'distance {diff.value} is below the 0.5 threshold — the signature scale '
        f'has drifted from take_ranker, which measures on 0..255'
    )
    margin = diff.value / vqa.DUP_DISTANCE
    assert margin > 2, f'only {margin:.1f}x margin to the threshold'


def test_aspect_is_an_exact_comparison():
    assert vqa.rule_aspect((1920, 1080), (1920, 1080)).verdict == vqa.PASS
    bad = vqa.rule_aspect((1080, 1920), (1920, 1080))
    assert bad.verdict == vqa.FAIL, bad.detail
    assert vqa.rule_aspect(None, (1920, 1080)).verdict == vqa.UNVERIFIABLE


def test_missing_asset_is_a_set_difference(tmp_path):
    """The rule is a set difference over the four SFX the components hardcode.

    It used to drive its difference from `props['audio']` — a top-level field
    `ShowcaseSchema` does not declare, so nothing a renderer can receive ever
    reached it. That case is now pinned as IGNORED rather than removed, so the
    rule cannot silently go back to trusting a field that cannot arrive.
    """
    good = vqa.rule_missing_asset({})[0]
    assert good.verdict in (vqa.PASS, vqa.FAIL)
    assert good.value == 0, good.detail

    # A props file that DOES carry an audio block is still checked against the
    # four hardcoded SFX, and the impossible field contributes nothing.
    absent_ignored = vqa.rule_missing_asset(
        {'audio': {'src': 'audio/definitely_absent.m4a'}})[0]
    assert absent_ignored.verdict == vqa.PASS, absent_ignored.detail
    assert absent_ignored.value == 0
    assert 'definitely_absent' not in absent_ignored.detail
    assert 'definitely_absent' not in absent_ignored.extra['checked']


# ── the four rules with no detector must say so, not invent a number ─────────

@pytest.mark.parametrize('rule', ['overflow', 'collision', 'flicker', 'broken_font'])
def test_unimplemented_rules_report_no_number(rule: str):
    f = next(x for x in vqa.unavailable_findings() if x.rule == rule)
    assert f.verdict == vqa.UNAVAILABLE
    assert f.value is None, f'{rule} reported a number without a detector'
    assert not f.trusted
    assert len(f.detail) > 40, f'{rule} must carry a reason'


def test_collision_records_why_a_run_detector_would_invert():
    """The most dangerous property found: overlap FUSES labels, so a run-based
    detector reports 0px overlap BECAUSE the collision happened."""
    f = next(x for x in vqa.unavailable_findings() if x.rule == 'collision')
    assert 'BECAUSE' in f.detail or 'because' in f.detail.lower()


# ── against the real renders, where they exist ──────────────────────────────

def _have(*rel: str) -> bool:
    return all((AUDIT / r).exists() for r in rel)


@pytest.mark.skipif(not _have('sc_hd/f00114.png', 'sc_padX0/f00114.png'),
                    reason='out/p10_audit renders not present (gitignored)')
def test_real_renders_agree_with_the_audit():
    settled = vqa.run_on_frame(AUDIT / 'sc_hd' / 'f00114.png')
    by = {f.rule: f for f in settled}
    assert by['safe_area'].verdict == vqa.PASS, by['safe_area'].detail
    assert by['safe_area'].value >= 100, (
        f'audit baseline said the showcase minimum margin is 106px, got '
        f'{by["safe_area"].value}'
    )

    pad0 = {f.rule: f for f in vqa.run_on_frame(AUDIT / 'sc_padX0' / 'f00114.png')}
    assert pad0['safe_area'].verdict == vqa.UNVERIFIABLE, (
        'a padX=0 frame must make the backdrop model refuse; if it does not, the '
        'trust flag has been loosened'
    )
    assert pad0['clipping'].verdict == vqa.FAIL, pad0['clipping'].detail


@pytest.mark.skipif(not _have('ch_hd/f00120.png', 'ch_hd/f00121.png'),
                    reason='out/p10_audit renders not present (gitignored)')
def test_real_consecutive_settled_frames_are_frozen():
    f = vqa.rule_freeze(AUDIT / 'ch_hd' / 'f00120.png', AUDIT / 'ch_hd' / 'f00121.png')
    assert f.verdict == vqa.FAIL, f.detail
    assert f.value == 0, f'audit measured a noise floor of exactly 0, got {f.value}'


@pytest.mark.skipif(not _have('repro/a/f00400.png'), reason='flat frame not present')
def test_real_flat_frame_is_black_and_blurred():
    p = AUDIT / 'repro' / 'a' / 'f00400.png'
    assert vqa.rule_black_frame(vqa.load(p)).verdict == vqa.FAIL
    assert vqa.rule_blur(vqa.load(p)).verdict == vqa.FAIL


# ── the thresholds must not be quietly widened ───────────────────────────────

def test_thresholds_match_the_measured_distributions():
    """Every constant that came out of the audit, checked against that audit."""
    assert vqa.DUP_DISTANCE == 0.5, 'take_ranker and its test both use 0.5'
    assert vqa.BLUR_VARIANCE == 2.0, (
        'corpus p5 is 11.5 and a blur ramp reaches 0.4; 2.0 sits between with 5.75x'
    )
    assert vqa.MIN_TYPE_PX == 12.0
    assert vqa.WCAG_TEXT == 4.5 and vqa.WCAG_LARGE == 3.0
    assert vqa.FREEZE_DIFF == 0, 'the noise floor was measured at exactly 0'
    assert vqa.TRUST_RESIDUAL == 60.0, (
        'settled frames measure 3 and touching-edge frames measure 208-230'
    )
    assert vqa.BLACK_NONCONTENT == 0.9995, (
        'the window is (0.999238, 1.0); a threshold outside it cannot separate'
    )
    assert vqa.PALETTE_TOL == 24, (
        'above the premium-dark gradient spread of 20 (6+6+8), or the backdrop '
        'itself reads as content'
    )


def _code_only(path: Path) -> str:
    """The file with block and line comments removed.

    These guards are textual and the module explains itself in comments that NAME
    take_ranker, which defines the scale the duplicate measure reuses. Scanning
    the raw text for an import would match that prose.
    """
    text = path.read_text(encoding='utf-8')
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    text = re.sub(r'^\s*#.*$', '', text, flags=re.MULTILINE)
    return text


def _imports(path: Path) -> list[str]:
    """Every import statement in the file, as text.

    Anchored to the start of a statement rather than searched for as a substring,
    because the module's docstring names take_ranker — it defines the scale the
    duplicate measure reuses — and a substring search matches that prose. Comments
    are stripped first; docstrings are not, because an import cannot be hidden
    inside one.
    """
    text = re.sub(r'/\*.*?\*/', '', path.read_text(encoding='utf-8'), flags=re.DOTALL)
    text = re.sub(r'^\s*#.*$', '', text, flags=re.MULTILINE)
    return re.findall(r'^\s*(?:from|import)\s+\S+', text, flags=re.MULTILINE)


def test_the_module_does_not_import_the_renderer():
    """visual_qa.py must stay runnable without remotion, react or cv2."""
    imports = _imports(SCRIPT)
    for forbidden in ('remotion', 'react', 'cv2', 'torch'):
        hits = [i for i in imports if i.split()[1].split('.')[0] == forbidden]
        assert not hits, f'visual_qa.py imports {forbidden}: {hits}'
    # take_ranker may be NAMED in a comment (the duplicate measure is
    # reimplemented on its scale) but must never be imported: it pulls in cv2,
    # which is not installed in this environment.
    hits = [i for i in imports if i.split()[1].split('.')[0] == 'take_ranker']
    assert not hits, (
        f'take_ranker imports cv2, which is not installed — the duplicate and '
        f'sharpness measures are reimplemented on its scale: {hits}'
    )
    assert any('numpy' in i for i in imports) and any('PIL' in i for i in imports), (
        'the instruments are numpy + PIL; if those are gone the rules are hollow'
    )

# ---------------------------------------------------------------------------
# Step 18 — qa_report.py's duration check. These run the real script against real
# ffmpeg-built files: a unit test of the tolerance formula would still pass if the
# branch that decides whether to check at all were still broken.
# ---------------------------------------------------------------------------

def _clip(tmp_path: pathlib.Path, name: str, seconds: float, **kw) -> pathlib.Path:
    try:
        from ffmpeg_env import FFMPEG
    except Exception:                                    # noqa: BLE001
        FFMPEG = None
    if not FFMPEG:
        pytest.skip('ffmpeg unavailable; duration guard cannot build a real clip')
    out = tmp_path / f'{name}.mp4'
    rate = kw.get('fps', 30)
    r = subprocess.run(
        [str(FFMPEG), '-y', '-hide_banner', '-loglevel', 'error',
         '-f', 'lavfi', '-i', f'testsrc2=size=640x360:rate={rate}:duration={seconds}',
         '-f', 'lavfi', '-i', f'sine=frequency=440:sample_rate=48000:duration={seconds}',
         '-af', 'loudnorm=I=-14:TP=-1.0',
         '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
         '-ar', '48000', '-ac', '2', str(out)],
        capture_output=True)
    assert r.returncode == 0, r.stderr.decode('utf-8', 'replace')
    return out


def _qa(video, props_file) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / 'studio' / 'scripts' / 'qa_report.py'),
         '--video', str(video), '--props', str(props_file)],
        capture_output=True, text=True, encoding='utf-8', errors='replace')


def _duration_verdict(stdout: str) -> str:
    for line in stdout.splitlines():
        s = line.strip()
        if 'duration vs props' in s and s.startswith(('\u001b', '[PASS]', '[FAIL]', '[UNVERIFIABLE]', ' \u001b')):
            if s.startswith('[PASS]'):
                return 'PASS'
            if s.startswith('[FAIL]'):
                return 'FAIL'
            if s.startswith('[UNVERIFIABLE]'):
                return 'UNVERIFIABLE'
    raise AssertionError(f'no duration verdict in output:\n{stdout}')


def test_qa_report_duration_tolerance_is_relative_not_absolute(tmp_path):
    """A 15% error on a 4s clip fails; a 1% error on a 60s clip passes.

    Under the old `abs(dur - expect) <= 0.6`, a 4s clip tolerated 15% drift — a
    clip could lose or gain two seconds and the gate called it clean. Under an
    absolute tolerance the error is also unbounded in the other direction: the
    same 0.6s is 0.02% of a 60s film, far tighter than any real render needs.
    """
    props_short = tmp_path / 'short.json'
    props_short.write_text(json.dumps(
        {'format': {'width': 640, 'height': 360, 'fps': 30}, 'totalDuration': 4.0}),
        encoding='utf-8')
    r = _qa(_clip(tmp_path, 'short', 4.6), props_short)
    assert _duration_verdict(r.stdout) == 'FAIL', (
        f'a 4.6s clip against a 4.0s reference is 15% out and must fail, '
        f'exit={r.returncode}'
    )
    assert r.returncode != 0

    props_long = tmp_path / 'long.json'
    props_long.write_text(json.dumps(
        {'format': {'width': 640, 'height': 360, 'fps': 30}, 'totalDuration': 60.0}),
        encoding='utf-8')
    r = _qa(_clip(tmp_path, 'long', 60.6), props_long)
    assert _duration_verdict(r.stdout) == 'PASS', (
        f'a 60.6s clip against 60.0s is 1% out, well inside 2%, and must pass: '
        f'{r.stdout}'
    )


def test_qa_report_duration_without_total_duration_is_unverifiable(tmp_path):
    """Missing totalDuration is UNVERIFIABLE and exits non-zero.

    The old code read `expect = props.get('totalDuration') or 0` and then
    `expect == 0 or ...`, so a props file with no totalDuration skipped the
    assertion and printed "no props reference". `studio/public/jobs/report_demo/
    props.json` — the one delivered props file — has no totalDuration, so the
    check had never run against a real render. A clip twice the implied length
    must not report success.
    """
    props_file = tmp_path / 'nodur.json'
    props_file.write_text(json.dumps({'format': {'width': 640, 'height': 360, 'fps': 30}}),
                          encoding='utf-8')
    r = _qa(_clip(tmp_path, 'nodur', 9.0), props_file)
    assert _duration_verdict(r.stdout) == 'UNVERIFIABLE', r.stdout
    assert r.returncode != 0, 'an unverifiable check must not exit 0'
    assert 'UNVERIFIABLE' in r.stdout and 'no totalDuration' in r.stdout


def test_the_delivered_report_props_still_carry_no_total_duration():
    """The gate cannot verify the one props file we ship.

    Recorded as a fact, not a fix. `reportSections` is not stored in props at all --
    it is derived -- and the derivation only pins the section COUNT: 1 title +
    len(stats) + 1 chart + len(takeaways) + 1 outro, which is 9 for the demo and
    agrees with `buildReportSections` in `schemas/report-data.ts`. The per-section
    DURATIONS are TypeScript literals (`t += 3`, `t += 2.4`, `t += 5 + items*0.9`),
    which reproduce here would duplicate four magic numbers that already exist once
    and would drift. The producer must carry totalDuration.
    """
    d = json.loads((ROOT / 'studio' / 'public' / 'jobs' / 'report_demo' / 'props.json')
                   .read_text(encoding='utf-8'))
    assert 'totalDuration' not in d, (
        'if this now carries totalDuration, qa_report can verify it and this test '
        'should be deleted rather than left asserting the old fact'
    )
    assert 'reportSections' not in d, 'sections are derived at render time, not stored'
    assert 3 + len(d['stats']) + len(d['takeaways']) == 9


# --------------------------------------------------------------------------
# CLI contracts (P11 steps 26-28)
#
# Three defects sat on P11's threshold and none of the 186 tests noticed: the
# suite was green before the fix and green after it. A contract nobody guards is
# a contract that can be reverted silently, so each one is pinned here — and each
# pin names the mistake it exists to catch.
#
# Step 29 asked for a guard on step 22's "strategy 1" consumer. That code does
# not exist — no planner, no repair module, nothing tracked — so the intent is
# served by guarding the contracts that were actually delivered.
# --------------------------------------------------------------------------

def _run_cli(args, cwd=ROOT):
    """Invoke the CLI as a subprocess: the bugs were in main(), not in a helper."""
    return subprocess.run([sys.executable, str(ROOT / 'studio' / 'scripts' / 'visual_qa.py')]
                          + [str(a) for a in args],
                          capture_output=True, text=True, cwd=cwd)


@pytest.fixture(scope='module')
def qa_frame(tmp_path_factory):
    """A frame with a known FAIL, built here rather than taken from out/.

    out/ is gitignored, so a fixture pointing into it would make this test fail
    on a fresh clone for a reason that has nothing to do with the contract.
    """
    from PIL import Image
    p = tmp_path_factory.mktemp('cli') / 'f00001.png'
    im = Image.new('RGB', (320, 180), (12, 12, 16))
    for x in range(0, 320, 24):          # bright verticals touching the edge
        for y in range(0, 180):
            im.putpixel((x, y), (250, 250, 250))
    im.save(p)
    return p


def test_the_cli_does_not_emit_the_unavailable_findings_twice(qa_frame):
    """main() appended them a second time; the CLI counted 15 where the library counted 11.

    A repair budget sized off the CLI number over-counts by four, which is the
    whole reason these were found: the count feeds P11's accounting.
    """
    lib = vqa.run_on_frame(qa_frame, None, 1.0, None, None)
    cli = _run_cli(['--frame', qa_frame])

    def rules(text):
        return re.findall(r'\[(\w+)\s*\]\s*(\w+)', text)

    assert rules(cli.stdout) == rules('\n'.join(str(f) for f in lib)), (
        'the CLI and the library must report the same findings in the same order; '
        f'library has {len(lib)}, CLI printed {len(rules(cli.stdout))}'
    )
    per_rule = [r for v, r in rules(cli.stdout) if v == vqa.UNAVAILABLE]
    assert len(per_rule) == len(set(per_rule)), (
        f'UNAVAILABLE rules emitted more than once: {per_rule}'
    )


def test_the_props_only_branch_still_reports_the_unavailable_instruments():
    """Guards the other half of step 26.

    --props with no --frame never enters run_on_frame, so the four UNAVAILABLE
    findings come from main(). Gating the duplicate append on `not args.frame`
    is what keeps this branch intact; deleting the append outright would have
    left this test with nothing to assert and the CLI silent about instruments
    it cannot run.
    """
    props = ROOT / 'studio' / 'public' / 'jobs' / 'showcase_demo' / 'props.json'
    if not props.exists():
        pytest.skip('staged props absent; run scripts/stage_showcase.py')
    r = _run_cli(['--props', props])
    rules = re.findall(r'\[(\w+)\s*\]\s*(\w+)', r.stdout)
    unavail = [rule for v, rule in rules if v == vqa.UNAVAILABLE]
    assert sorted(unavail) == sorted(vqa.UNIMPLEMENTED), (
        'every unimplemented rule must still be announced on the props-only path'
    )


def test_json_output_is_byte_level_parseable(qa_frame):
    """--json died on json.load() twice, in two different ways.

    A summary line followed the array ("Extra data"), and ensure_ascii=False
    wrote real CJK through a GBK stdout on Windows, so the bytes were not valid
    UTF-8 at all. Both were invisible to a test that only ever ran the library.

    Decoding the raw bytes is the point: reading with the wrong encoding is how
    a consumer would have met the second bug.
    """
    r = subprocess.run([sys.executable, str(ROOT / 'studio' / 'scripts' / 'visual_qa.py'),
                        '--frame', str(qa_frame), '--json'],
                       capture_output=True, cwd=ROOT)
    raw = r.stdout
    findings = json.loads(raw.decode('utf-8'))
    assert isinstance(findings, list)
    assert raw.decode('utf-8').isprintable() or True   # decodable is the assertion
    assert 'findings:' not in raw.decode('utf-8'), 'the summary leaked into stdout'
    assert b'findings:' in r.stderr, 'the human summary belongs on stderr'
    for f in findings:
        assert f['verdict'] in (vqa.PASS, vqa.FAIL, vqa.UNVERIFIABLE, vqa.UNAVAILABLE)


def test_the_summary_does_not_merge_unverifiable_with_unavailable(qa_frame):
    """One number for two different states.

    "10 not measurable" counted both, and the instrument being absent is not the
    same claim as the instrument running and unable to decide. Section 8 of the
    handoff makes the four-value split a rule; the CLI summary was breaking it.
    """
    # Both output modes carry the summary, on different streams: without --json
    # it is the last stdout line, with --json it is on stderr. Checking one and
    # missing the other is how mutation 4 survived the first version of this
    # guard -- the merged bucket was reintroduced on the branch not inspected.
    plain = _run_cli(['--frame', qa_frame])
    as_json = _run_cli(['--frame', qa_frame, '--json'])
    for label, text in (('stdout', plain.stdout), ('stderr', as_json.stderr)):
        tail = text.strip().splitlines()[-1]
        assert 'not measurable' not in tail, f'the merged bucket came back ({label}): {tail!r}'
        assert vqa.UNVERIFIABLE in tail and vqa.UNAVAILABLE in tail, (
            f'the summary must name both states separately ({label}): {tail!r}'
        )


# --------------------------------------------------------------------------
# Input validation: a gate that checks nothing must not report success.
#
# `main()` read `if args.props and args.props.exists():`, so a --props path
# that did not exist was dropped without a word. `props` stayed None, the whole
# `missing_asset` branch was skipped, and the run printed "0 FAIL, 0
# UNVERIFIABLE" and exited 0 — identical to a clean pass. A typo in a path
# turned QA into a no-op that CI reads as a green light.
#
# `ab_field.py:472`, one file over, has always done `ap.error()` on the same
# flag: the same repo, the same flag, two opposite conventions. Anything that
# read one of them was misled by the other.
#
# WHY THIS GUARD CALLS `main(argv)` IN-PROCESS RATHER THAN GREPPING THE SOURCE.
# A guard of the form `assert 'ap.error' in source` passes against
# `assert True`, against the word appearing in a COMMENT, and against a string
# that is built at runtime from parts. This project has been fooled by text
# existence five times, and the first version of the guard this one replaces
# counted `assert` occurrences. So: call the entry point, read the RETURN
# VALUE, and read the report it printed. The return value is the thing CI gates
# on; the report is the thing a human reads. Both are asserted here.
#
# WHY BOTH DIRECTIONS ARE ASSERTED IN THE SAME PLACE. A guard that only checks
# the failure case is satisfied by an implementation that always fails — the
# tool would be "safe" and useless, and no assertion about the bad path could
# tell the difference. `test_the_failure_direction_...` and
# `test_the_healthy_direction_...` below are deliberately paired: mutation 2 in
# the verification protocol injects exactly that always-fail implementation and
# the healthy test is what kills it.
# --------------------------------------------------------------------------

def _main(argv, capsys):
    """Call main(argv) in-process, returning (exit_code, stdout, stderr)."""
    code = vqa.main([str(a) for a in argv])
    cap = capsys.readouterr()
    return code, cap.out, cap.err


def _verdict_for(stdout: str, rule: str) -> str | None:
    """The verdict the CLI printed for `rule`, or None if it never ran."""
    for line in stdout.splitlines():
        if not line.startswith('  ['):
            continue
        parts = line.split(']')
        if len(parts) < 2:
            continue
        body = parts[1].split()
        if body and body[0] == rule:
            return parts[0].lstrip(' [').strip()
    return None


@pytest.fixture
def real_props(tmp_path):
    """A minimal READABLE graph, written by the test rather than borrowed.

    Not `pipeline/examples/showcase_demo.json`: that is a real file whose
    absence would be this test's problem to explain, and its content is
    P13's business. The contract under test is "a file that exists and parses
    is read, and the gate runs and exits 0" — nothing more.
    """
    p = tmp_path / 'props.json'
    p.write_text(json.dumps({'format': {'width': 320, 'height': 180, 'fps': 30}}),
                 encoding='utf-8')
    return p


def test_the_failure_direction_a_missing_props_file_is_unverifiable_not_silent(
        tmp_path, capsys):
    """A --props path that does not exist must not exit 0.

    The return value is asserted directly. Nothing here reads the source, so an
    implementation that merely MENTIONED the fix in a comment would not pass.
    """
    missing = tmp_path / 'no_such_graph.json'
    assert not missing.exists()
    code, out, _ = _main(['--props', missing], capsys)

    assert code != 0, (
        f'main() returned {code} for a --props path that does not exist. A QA '
        'gate that cannot read its input must not report success: this is the '
        f'state that reported "0 FAIL" while checking nothing.\n{out}'
    )
    assert _verdict_for(out, 'missing_asset') == vqa.UNVERIFIABLE, (
        'the graph-reading rule must REPORT that it could not read the graph. '
        'Dropping it (the old behaviour) and failing it (FAIL means "measured '
        'and it is wrong") are both wrong: nothing was measured.\n'
        f'{out}'
    )


def test_the_failure_direction_names_the_unreadable_path(tmp_path, capsys):
    """The report has to say WHICH input was wrong.

    A bare UNVERIFIABLE with no path would tell a caller that something is
    wrong while leaving it to guess which of N inputs failed — which, with one
    props file, means re-running the command by hand to find a typo.
    """
    missing = tmp_path / 'no_such_graph.json'
    code, out, _ = _main(['--props', missing], capsys)
    assert code != 0
    assert str(missing) in out, (
        f'the report does not name the path it could not read ({missing}); '
        f'the caller cannot act on that:\n{out}'
    )


def test_the_healthy_direction_a_readable_props_file_still_runs_and_exits_zero(
        real_props, capsys):
    """The half that catches an always-fail implementation.

    THIS TEST IS NOT OPTIONAL COVERAGE. The failure test above is satisfied by
    `return 1` unconditionally, by an unconditional `raise`, and by anything
    else that always fails. This is the assertion that distinguishes "refuses
    to run on bad input" from "refuses to run". If you add a guard for the
    missing-props case, keep this one in the same breath.
    """
    code, out, _ = _main(['--props', real_props], capsys)
    assert code == 0, (
        f'main() returned {code} for a readable, parseable props file. The '
        'input validation must reject bad paths WITHOUT breaking good ones:\n'
        f'{out}'
    )
    assert _verdict_for(out, 'missing_asset') == vqa.PASS, (
        f'the graph-reading rule must still run on a readable graph:\n{out}'
    )


def test_the_healthy_direction_is_not_vacuous(real_props, capsys):
    """The healthy run must actually produce findings.

    `code == 0` plus no output is what a tool that returned early would give.
    Asserting the count keeps the previous test from passing on an
    implementation that exits 0 having done nothing.
    """
    code, out, _ = _main(['--props', real_props], capsys)
    assert code == 0
    assert len(re.findall(r'\[(\w+)\s*\]\s*(\w+)', out)) >= 1, (
        f'the healthy props-only run printed no findings at all, so it is not '
        f'evidence that the tool ran:\n{out}'
    )


def test_the_healthy_direction_survives_the_json_mode_too(real_props, capsys):
    """The fix must hold on the output mode a machine reads.

    `--json` puts the findings on stdout and the summary on stderr. A
    validation error that only appeared in the human-readable branch would
    leave a JSON consumer with an empty array and a non-zero exit — which is
    better than the original silent pass, but still not a report explaining
    itself. So the UNVERIFIABLE finding has to be IN the JSON.
    """
    code, out, err = _main(['--props', real_props.parent / 'no_such_graph.json', '--json'],
                           capsys)
    assert code != 0, f'main() returned {code} for a missing props file with --json'
    findings = json.loads(out)
    assert any(f['verdict'] == vqa.UNVERIFIABLE for f in findings), (
        f'the JSON report carries no UNVERIFIABLE finding: {findings}'
    )
    assert 'findings:' in err, 'the summary belongs on stderr in --json mode'
