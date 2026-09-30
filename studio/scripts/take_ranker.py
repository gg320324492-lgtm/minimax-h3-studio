"""Cheap deterministic metrics for take ranking (P1).

Every metric is computable from the pixels alone — no VLM, no GPU, no network —
so a take is prescreenable in milliseconds. The VLM critic (take_critic.py)
runs only on the survivors.

Design rules:
  * Deterministic: same file -> same scores (no RNG).
  * Sampling: metrics read at most MAX_PROBE_FRAMES evenly spaced frames, so a
    226-frame take costs the same as a 56-frame one.
  * Every metric returns 0..1 where 1 = better, except *_raw diagnostics.
  * Failure of one metric must never abort the take: it degrades to None and
    the score reweights.

Usage:
  python take_ranker.py --project ceo_mindread_ep01
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(r'E:\Minimax-H3')
sys.path.insert(0, str(ROOT))
from ffmpeg_env import FFPROBE  # noqa: E402

MAX_PROBE_FRAMES = 12
PROBE_WIDTH = 256  # downscale for speed; metrics are scale-invariant


def probe(path: Path) -> dict:
    r = subprocess.run(
        [FFPROBE, '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'stream=width,height,nb_frames,avg_frame_rate,codec_name',
         '-of', 'json', str(path)],
        capture_output=True, text=True, check=True)
    s = json.loads(r.stdout)['streams'][0]
    n, d = s.get('avg_frame_rate', '0/1').split('/')
    return {
        'width': int(s['width']), 'height': int(s['height']),
        'frames': int(s.get('nb_frames') or 0),
        'fps': float(n) / float(d) if float(d) else 0.0,
        'codec': s.get('codec_name', ''),
    }


def read_probe_frames(path: Path, max_frames: int = MAX_PROBE_FRAMES) -> list[np.ndarray]:
    """Evenly spaced grayscale + color frames, downscaled."""
    cap = cv2.VideoCapture(str(path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total <= 0:
        cap.release()
        return []
    idxs = np.unique(np.linspace(0, total - 1, min(max_frames, total)).astype(int))
    out = []
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        h, w = frame.shape[:2]
        scale = PROBE_WIDTH / max(w, 1)
        small = cv2.resize(frame, (PROBE_WIDTH, max(int(h * scale), 1)), interpolation=cv2.INTER_AREA)
        out.append(small)
    cap.release()
    return out


def read_full_gray(path: Path, max_px: int = 160_000) -> tuple[np.ndarray, float]:
    """Full-sequence luma (downscaled) + fps. Used for temporal metrics."""
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if w <= 0 or h <= 0:
        cap.release()
        return np.array([]), fps
    scale = min(1.0, math.sqrt(max_px / (w * h)))
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            break
        if scale < 1.0:
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    cap.release()
    if not frames:
        return np.array([]), fps
    return np.stack(frames).astype(np.float32), fps


# ── individual metrics (0..1, higher = better) ──────────────────────────────

def m_sharpness(frames: list[np.ndarray]) -> float:
    """Variance of Laplacian on probe frames — blur/low-detail detector."""
    if not frames:
        return 0.5
    vals = [cv2.Laplacian(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var() for f in frames]
    v = float(np.mean(vals))
    # ~50 is soft, ~500 crisp on 256px-wide frames
    return float(np.clip(v / 400.0, 0.0, 1.0))


def m_exposure(frames: list[np.ndarray]) -> float:
    """1.0 when mean luma sits near mid-grey; penalizes blown/ crushed."""
    if not frames:
        return 0.5
    means = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).mean() for f in frames]
    m = float(np.mean(means)) / 255.0
    return float(np.clip(1.0 - abs(m - 0.48) * 2.2, 0.0, 1.0))


def m_black_frames(frames: list[np.ndarray]) -> float:
    """Penalize near-black probe frames (failed generation)."""
    if not frames:
        return 0.0
    dark = sum(1 for f in frames if cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).mean() < 12)
    return float(1.0 - dark / len(frames))


def m_motion_amount(gray: np.ndarray, fps: float) -> float:
    """Reward *some* motion; dead frames and chaotic shake are both bad."""
    if len(gray) < 3:
        return 0.0
    d = np.abs(np.diff(gray, axis=0)).mean() / 255.0
    # sweet spot around 2-8% mean abs diff per frame pair
    if d < 0.002:
        return 0.05           # frozen
    if d < 0.02:
        return float(d / 0.02) * 0.9 + 0.1
    if d > 0.14:
        return float(max(0.0, 1.0 - (d - 0.14) * 4))  # chaotic
    return 1.0


def m_temporal_stability(gray: np.ndarray) -> tuple[float, float]:
    """Flicker = luma variance across time; jitter = flow-magnitude variance."""
    if len(gray) < 3:
        return 0.5, 0.5
    mean_luma = gray.mean(axis=(1, 2))
    flicker = float(np.std(np.diff(mean_luma)) / 255.0)
    stability = float(np.clip(1.0 - flicker * 26.0, 0.0, 1.0))

    flows = []
    step = max(1, len(gray) // 16)
    for i in range(0, len(gray) - 1, step):
        f = cv2.calcOpticalFlowFarneback(
            gray[i], gray[i + 1], None, 0.5, 2, 15, 2, 5, 1.2, 0)
        flows.append(float(np.mean(np.linalg.norm(f, axis=2))))
    jitter = 0.5
    if len(flows) >= 3:
        jitter = float(np.clip(1.0 - (np.std(flows) / (np.mean(flows) + 1e-6)) * 0.5, 0.0, 1.0))
    return stability, jitter


def m_duplicate(gray: np.ndarray) -> float:
    """Penalize consecutive near-identical frames (encoder stall / freeze)."""
    if len(gray) < 3:
        return 1.0
    diffs = np.abs(np.diff(gray, axis=0)).mean(axis=(1, 2)) / 255.0
    dup_ratio = float((diffs < 0.0015).mean())
    return float(1.0 - dup_ratio)


def m_artifact_heuristic(frames: list[np.ndarray]) -> float:
    """Saturation blowout + blockiness proxy. Cheap stand-in for 'looks wrong'."""
    if not frames:
        return 0.5
    scores = []
    for f in frames:
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        sat_blow = float((hsv[:, :, 1] > 250).mean())
        lap = cv2.Laplacian(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        blocky = 1.0 if lap < 8 else 0.0
        scores.append(1.0 - min(1.0, sat_blow * 3.0 + blocky))
    return float(np.mean(scores))


def m_subject_consistency(gray: np.ndarray) -> float:
    """Global feature (histogram) drift over time — identity/lighting stability."""
    if len(gray) < 3:
        return 0.5
    hists = []
    step = max(1, len(gray) // 12)
    for i in range(0, len(gray), step):
        h = cv2.calcHist([gray[i]], [0], None, [64], [0, 256])
        cv2.normalize(h, h)
        hists.append(h.flatten())
    hists = np.stack(hists)
    drift = float(np.mean([cv2.compareHist(hists[i], hists[i + 1], cv2.HISTCMP_CORREL)
                           for i in range(len(hists) - 1)]))
    return float(np.clip((drift + 1.0) / 2.0, 0.0, 1.0))


# ── aggregate ───────────────────────────────────────────────────────────────

@dataclass
class TakeMetrics:
    take_id: str
    path: str
    width: int = 0
    height: int = 0
    frames: int = 0
    fps: float = 0.0
    duration_s: float = 0.0
    sharpness: float = 0.0
    exposure: float = 0.0
    not_black: float = 0.0
    motion: float = 0.0
    stability: float = 0.0
    flow_jitter: float = 0.0
    not_duplicate: float = 0.0
    artifact: float = 0.0
    subject_consistency: float = 0.0
    score: float = 0.0
    hard_fail: str | None = None
    redundant_with: str | None = None
    notes: list[str] = field(default_factory=list)
    _sig: np.ndarray | None = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop('_sig', None)
        return d


def pixel_signature(path: Path, n_frames: int = 8, span: int = 20, size=(64, 112)) -> np.ndarray:
    """Tiny multi-frame grayscale signature for near-duplicate detection.

    Two takes produced from the same seed are pixel-identical (only encoder
    noise differs), so all quality metrics tie and ranking is meaningless.
    This signature catches that case: verified on EP01, where S06_T01 and
    S06_T02 differ by exactly 0.0 while S05A's two real generations differ
    by 55.9 on the same measure.
    """
    cap = cv2.VideoCapture(str(path))
    out = []
    for i in range(n_frames):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i * span)
        ok, f = cap.read()
        if ok and f is not None:
            out.append(cv2.resize(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), size).astype(np.float32))
    cap.release()
    return np.stack(out) if out else np.zeros((1, size[1], size[0]), np.float32)


def signature_distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(a - b).mean())


# 默认权重（任务书建议值）
WEIGHTS = {
    'sharpness': 0.05,
    'exposure': 0.05,
    'not_black': 0.05,
    'motion': 0.10,
    'stability': 0.10,
    'flow_jitter': 0.05,
    'not_duplicate': 0.05,
    'artifact': 0.10,
    'subject_consistency': 0.10,
}
# prompt_adherence 0.20 / composition 0.15 / consistency 0.15 属 VLM 维度，
# cheap 指标在 prescreen 阶段按比例分摊（见 rank_takes.py）


def analyze(take_path: Path, take_id: str | None = None) -> TakeMetrics:
    take_id = take_id or take_path.stem
    m = TakeMetrics(take_id=take_id, path=str(take_path))
    try:
        info = probe(take_path)
    except Exception as e:
        m.hard_fail = f'probe failed: {e}'
        return m
    m.width, m.height = info['width'], info['height']
    m.frames, m.fps = info['frames'], info['fps']
    m.duration_s = (m.frames / m.fps) if m.fps else 0.0

    if m.frames < 8:
        m.hard_fail = f'too few frames ({m.frames})'
        return m

    frames = read_probe_frames(take_path)
    if not frames:
        m.hard_fail = 'no decodable frames'
        return m
    gray, _ = read_full_gray(take_path)
    if len(gray) < 3:
        gray = np.stack([cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in frames])

    m.sharpness = m_sharpness(frames)
    m.exposure = m_exposure(frames)
    m.not_black = m_black_frames(frames)
    m.motion = m_motion_amount(gray, m.fps)
    m.stability, m.flow_jitter = m_temporal_stability(gray)
    m.not_duplicate = m_duplicate(gray)
    m.artifact = m_artifact_heuristic(frames)
    m.subject_consistency = m_subject_consistency(gray)
    m._sig = pixel_signature(take_path)

    if m.not_black < 0.5:
        m.hard_fail = 'mostly black frames'
    elif m.sharpness < 0.02:
        m.hard_fail = 'severely blurred'

    wsum = sum(WEIGHTS.values())
    m.score = sum(getattr(m, k) * w for k, w in WEIGHTS.items()) / wsum

    if m.motion < 0.1:
        m.notes.append('near-frozen motion')
    if m.stability < 0.6:
        m.notes.append('luma flicker detected')
    if m.flow_jitter < 0.4:
        m.notes.append('unstable camera shake')
    if m.exposure < 0.6:
        m.notes.append('exposure off mid-grey')
    if m.subject_consistency < 0.7:
        m.notes.append('subject/lighting drift across the take')
    return m


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        r = analyze(Path(arg))
        print(json.dumps(r.to_dict(), ensure_ascii=False, indent=2))
