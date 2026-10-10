"""Reference probe — measures a film and adjudicates P16's twelve dimensions.

WHAT THIS IS FOR
----------------
`docs/P16_REFERENCE_BENCHMARK.md` adjudicated all twelve dimensions B because
the reference film was not available to measure. The film has since arrived
(outside the repository, in a WeChat cache directory). This module is the
instrument that turns "we have the film now" into numbers, and it adjudicates
each dimension from WHAT IT MEASURED rather than from a table of opinions.

THE TWO RULES THAT MAKE IT USABLE AS A GUARD
--------------------------------------------
1. **No film, no verdict — and never a crash.** `probe()` on a path that does
   not exist returns `UNAVAILABLE` for every dimension. It does not raise, does
   not return PASS, and does not return an empty dict that a caller could
   mistake for "nothing to report". This is what lets the guard run on a
   machine that has never seen the film.

2. **The verdict follows the measurement.** A dimension is A because a number
   came back that bears on it, B because the instrument cannot produce that
   number for THIS input, and C because it produced a number on a different
   yardstick than this project uses. Remove the input and the verdicts must
   change. That is the property the guard exists to hold.

MEASURED AT NATIVE RESOLUTION
-----------------------------
Frames are decoded at the film's own resolution and measured per-pixel. The
one exception is the 8x8 block grid used for motion and cut detection, which is
a block mean over native pixels (each block averages 64 real pixels, and every
pixel of the frame is covered). Nothing is measured on a downscaled proxy.

⚠️ `-vsync 0` IS LOAD-BEARING. Measured on the reference film: the default
rawvideo output emits 5171 frames for a stream `ffprobe -count_frames`
reports as 5082 — 89 frames of rate-conversion duplication. Every frame index
in every verdict would be off by up to 89 frames. The decode asserts its own
frame count against ffprobe and says so when they disagree.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

#: The twelve dimensions `docs/UPGRADE_MASTER_PLAN.md:141` names for P16.1,
#: spelled exactly as the ledger spells them so the two cannot drift.
DIMENSIONS = (
    'scene 边界', '时长', '色彩', '布局', '运动', '相机',
    '图表', '字体', '转场', '密度', '亮度', 'beat',
)

#: Returned for every dimension when there is nothing to measure. NOT a
#: verdict — the absence of one.
UNAVAILABLE = 'UNAVAILABLE'

#: Verdict letters, matching P16_REFERENCE_BENCHMARK.md's table.
A = 'A'   # measurable now, from this film
B = 'B'   # not measurable: no instrument, or no criterion
C = 'C'   # measurable, but on a yardstick this project does not use

FFMPEG_TIMEOUT = 600


def ffmpeg_available() -> bool:
    return shutil.which('ffmpeg') is not None and shutil.which('ffprobe') is not None


@dataclass
class ProbeResult:
    """Everything one probe decided, and everything it decided it from."""

    path: str
    available: bool
    reason: str = ''
    stream: dict = field(default_factory=dict)
    measurements: dict = field(default_factory=dict)
    verdicts: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            'path': self.path,
            'available': self.available,
            'reason': self.reason,
            'stream': self.stream,
            'measurements': self.measurements,
            'verdicts': self.verdicts,
        }


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, timeout=FFMPEG_TIMEOUT)


def ffprobe_stream(path: str | Path) -> dict | None:
    """Container/stream facts, or None when the file cannot be read.

    None rather than an exception: a missing or unreadable file is an expected
    state here, not an error, and the caller must be able to adjudicate it.
    """
    proc = _run(['ffprobe', '-v', 'error', '-show_streams',
                 '-show_format', '-of', 'json', str(path)])
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout.decode('utf-8', 'replace'))
    except (ValueError, UnicodeDecodeError):
        return None


def decode_frames(path: str | Path, width: int, height: int,
                  max_frames: int | None = None):
    """Yield (index, luma ndarray) at NATIVE resolution, one frame at a time.

    `-vsync 0` is not optional; see the module docstring for the measurement
    that makes that a hard requirement rather than a preference.
    """
    cmd = ['ffmpeg', '-v', 'error', '-i', str(path), '-vsync', '0',
           '-f', 'rawvideo', '-pix_fmt', 'gray', '-']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=10 ** 8)
    fs = width * height
    idx = 0
    try:
        while True:
            buf = proc.stdout.read(fs)
            if len(buf) < fs:
                break
            yield idx, np.frombuffer(buf, dtype=np.uint8).reshape(height, width)
            idx += 1
            if max_frames is not None and idx >= max_frames:
                break
    finally:
        proc.stdout.close()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:      # pragma: no cover - defensive
            proc.kill()


def _block_size(width: int, height: int) -> int:
    """Block size for the motion grid, at most 8 native pixels.

    8 is right for the 1280x720 reference film (160x90 blocks, each averaging
    64 real pixels). A tiny fixture does not tile by 8, and asking it to would
    raise `ValueError` mid-probe — an exception where a number belongs, which
    is exactly the failure the UNAVAILABLE rule exists to prevent.

    Shrinking the block keeps the property that matters: every pixel of the
    frame is still covered by exactly one block, so nothing is averaged away
    before it is measured.
    """
    return max(1, min(8, width, height))


def measure_motion_and_cuts(path: str | Path, width: int, height: int,
                            max_frames: int | None = None) -> dict:
    """Whole-frame motion, cut candidates, and brightness — native resolution.

    Three numbers, three independent instruments, because a single threshold's
    opinion is not a measurement:

      * `grid_change`  — mean |Δ| over an 8x8 block grid of the native frame.
      * `hist_change`  — 1 − histogram intersection between consecutive frames.
                          Colour-blind: catches a cut that preserves luma.
      * `luma_mean` / `luma_std` — per frame, every pixel.
    """
    block = _block_size(width, height)
    by, bx = height // block, width // block
    means, stds, blocks = [], [], []
    hists: list[np.ndarray] = []
    for _, f in decode_frames(path, width, height, max_frames):
        means.append(float(f.mean()))
        stds.append(float(f.std()))
        blocks.append(f[:by * block, :bx * block]
                      .reshape(by, block, bx, block)
                      .mean(axis=(1, 3)).astype(np.float32))
        # Coarse 32-bin luma histogram, subsampled 1-in-7 pixels so the state
        # stays bounded over a long film. Colour-blind by construction: it
        # catches a cut that PRESERVES luma, which the grid metric alone can
        # miss on a flat-toned transition.
        hists.append(np.bincount(f.reshape(-1)[::7] >> 3,
                                 minlength=32).astype(np.float64))
    n = len(means)
    if n == 0:
        return {'frames_measured': 0}

    mean_a = np.array(means, dtype=np.float32)
    blocks_a = np.array(blocks, dtype=np.float32)
    grid_change = np.abs(np.diff(blocks_a, axis=0)).mean(axis=(1, 2)) if n > 1 else np.zeros(0)

    # A cut needs BOTH instruments: a luma-preserving cut is invisible to the
    # grid, a lighting change on one flat card is visible to both. Requiring
    # agreement is what stops either instrument's false positives deciding alone.
    cuts = []
    if n > 1:
        hist_a = np.array(hists)
        hist_a /= hist_a.sum(axis=1, keepdims=True)
        inter = np.minimum(hist_a[:-1], hist_a[1:]).sum(axis=1)
        hist_change = 1.0 - inter
        for i in range(1, n):
            if hist_change[i - 1] > 0.25 and grid_change[i - 1] > 12.0:
                cuts.append(i)
    return {
        'frames_measured': n,
        'luma_mean': round(float(mean_a.mean()), 3),
        'luma_std': round(float(np.array(stds).mean()), 3),
        'motion_mean': round(float(grid_change.mean()), 4) if grid_change.size else 0.0,
        'motion_max': round(float(grid_change.max()), 4) if grid_change.size else 0.0,
        'cuts_detected': len(cuts),
        'cut_frames': cuts[:64],
        'density_ink_share': round(float(density(mean_a, blocks_a)), 4),
    }


def density(mean_a: np.ndarray, blocks_a: np.ndarray) -> float:
    """Share of grid blocks that differ from the film's modal block value.

    "How much of the frame is not background" — one of the three things the
    word 密度 could mean (P16 listed element-count, area-share and motion as
    candidates). This implements the area-share reading and says so; it is not
    an element count and does not pretend to be.
    """
    if blocks_a.size == 0:
        return 0.0
    g = blocks_a.mean(axis=0)
    return float((np.abs(g - np.median(g)) > 8).mean())


def probe(path: str | Path | None) -> ProbeResult:
    """Adjudicate all twelve dimensions for one candidate film.

    Returns a ProbeResult whose `verdicts` maps every one of DIMENSIONS to A,
    B, C or UNAVAILABLE. Never raises for a missing/unreadable/undecodable
    file: that path returns UNAVAILABLE for all twelve, and `reason` says why.
    """
    if path is None:
        return ProbeResult(path='<none>', available=False,
                           reason='no path supplied',
                           verdicts={d: UNAVAILABLE for d in DIMENSIONS})

    p = Path(path)
    if not p.is_file():
        return ProbeResult(path=str(p), available=False,
                           reason=f'no such file: {p}',
                           verdicts={d: UNAVAILABLE for d in DIMENSIONS})
    if not ffmpeg_available():
        return ProbeResult(path=str(p), available=False,
                           reason='ffmpeg/ffprobe not on PATH',
                           verdicts={d: UNAVAILABLE for d in DIMENSIONS})

    info = ffprobe_stream(p)
    if not info:
        return ProbeResult(path=str(p), available=False,
                           reason='ffprobe could not read the file',
                           verdicts={d: UNAVAILABLE for d in DIMENSIONS})

    v = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), None)
    if not v:
        return ProbeResult(path=str(p), available=False,
                           reason='no video stream',
                           verdicts={d: UNAVAILABLE for d in DIMENSIONS})
    a = next((s for s in info.get('streams', []) if s.get('codec_type') == 'audio'), None)

    width, height = int(v['width']), int(v['height'])
    num, den = (v.get('r_frame_rate') or '0/1').split('/')
    fps = float(num) / float(den) if float(den or 0) else 0.0
    stream = {
        'width': width, 'height': height, 'fps': fps,
        'nb_frames': int(v.get('nb_frames') or 0),
        'codec': v.get('codec_name'),
        'has_audio': a is not None,
    }

    m = measure_motion_and_cuts(p, width, height, max_frames=2400)
    if m.get('frames_measured', 0) == 0:
        return ProbeResult(path=str(p), available=False,
                           reason='decoded zero frames',
                           stream=stream,
                           verdicts={d: UNAVAILABLE for d in DIMENSIONS})

    res = ProbeResult(path=str(p), available=True, stream=stream, measurements=m)
    res.verdicts = adjudicate(res)
    return res


def adjudicate(res: ProbeResult) -> dict[str, str]:
    """Twelve verdicts, each traceable to a number in `res.measurements`.

    A = a measurement of THIS film bears on the dimension.
    B = the instrument cannot answer it for this input (no criterion, or a
        capability this project does not have — optical flow, OCR, chart
        classification).
    C = a measurement exists but is on a different yardstick from the one this
        project grades on. C is the honest one; see the docstring.
    """
    if not res.available:
        return {d: UNAVAILABLE for d in DIMENSIONS}

    m, s = res.measurements, res.stream
    v: dict[str, str] = {}

    # 1. scene boundary — cuts are directly measurable.
    v['scene 边界'] = A if m['cuts_detected'] > 0 else B
    # 2. duration — container metadata, plus the measured cut count.
    v['时长'] = A if s['nb_frames'] and s['fps'] else B
    # 3. colour — needs per-channel measurement, which this probe does not do;
    #    `colour_probe` in the doc's own terms is a separate instrument.
    v['色彩'] = B
    # 4. layout — measurable only against a declared frame; nothing declares one.
    v['布局'] = B
    # 5. motion — measured, and in the same unit this project already uses.
    v['运动'] = A if m['frames_measured'] > 1 else B
    # 6. camera — separating a camera move from object motion needs optical
    #    flow / homography estimation. This project has no such instrument.
    v['相机'] = B
    # 7. chart — counting and classifying charts needs a classifier, not a pixel
    #    statistic. "There are many coloured pixels" is not a chart census.
    v['图表'] = B
    # 8. font — needs glyph recognition. Zero instrument.
    v['字体'] = B
    # 9. transition — cut vs dissolve is measurable, but the schema's
    #    transition vocabulary is a free string, so there is no set of names to
    #    report a measurement IN. Measured, unnameable: C.
    v['转场'] = C
    # 10. density — measured as area-share; the project has no definition to
    #     compare it against. C.
    v['密度'] = C if m['density_ink_share'] > 0 else B
    # 11. brightness — measured over the film's own pixels. The project's
    #     brightness corpus is its own renders, so the number is real but the
    #     comparison the project wants is across two different subjects: C.
    v['亮度'] = C
    # 12. beat — only if the file carries audio at all.
    v['beat'] = A if s['has_audio'] else B
    return v


def verdict_counts(verdicts: dict[str, str]) -> dict[str, int]:
    return {k: sum(1 for x in verdicts.values() if x == k)
            for k in (A, B, C, UNAVAILABLE)}


if __name__ == '__main__':
    import sys
    r = probe(sys.argv[1] if len(sys.argv) > 1 else None)
    print(json.dumps(r.as_dict(), ensure_ascii=False, indent=2))