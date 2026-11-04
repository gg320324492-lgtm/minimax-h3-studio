"""P58 extraction quality gate — numbers + frames, before any generation.

Decodes the two extracted control videos (pose skeletons, DA3 depth) and the
real clip itself, frame by frame, and measures:

  pose   : per-frame skeleton pixel count (non-black), person blob count
           (connected components, >= 200 px), frames with zero detection.
  depth  : per-frame luminance mean/std, Sobel gradient magnitude (mean and
           p95), temporal mean-absolute-difference between consecutive frames
           — reported next to the SAME metric on the real RGB clip, because a
           depth map that tracks the scene's motion should have temporal MAD
           of the same order as the footage; a frozen or noisy map will not.

Writes out/p58/extract_metrics.json and the 3 gate frames (f30/f62/f93) for
each route into out/p58/extract/, plus a source-vs-control side-by-side per
frame for the eyeball half of the gate.
"""
import json
import subprocess
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(r"E:\Minimax-H3")
OUT = ROOT / "out" / "p58"
EXTRACT = OUT / "extract"
W, H, N = 864, 480, 124
FRAME_IDX = [30, 62, 93]

SRC = Path(r"E:\ComfyUI\input\p58_real.mp4")
CTRL = {
    "pose": OUT / "controls" / "p58_pose_real_pose_real_00001_.mp4",
    "depth": OUT / "controls" / "p58_depth_real_depth_real_00001_.mp4",
}


def decode(video: Path) -> np.ndarray:
    """(N, H, W, 3) uint8 via ffmpeg rawvideo."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-"],
        check=True, capture_output=True).stdout
    arr = np.frombuffer(raw, dtype=np.uint8)
    per = H * W * 3
    n = len(arr) // per
    return arr[:n * per].reshape(n, H, W, 3)


def lum(img: np.ndarray) -> np.ndarray:
    return img.astype(np.float32) @ np.array([0.2126, 0.7152, 0.0722], np.float32)


def sobel_mag(g: np.ndarray) -> np.ndarray:
    gx = np.zeros_like(g)
    gy = np.zeros_like(g)
    gx[:, 1:-1] = g[:, 2:] - g[:, :-2]
    gy[1:-1, :] = g[2:, :] - g[:-2, :]
    return np.hypot(gx, gy)


def temporal_mad(stack: np.ndarray) -> float:
    a = stack[..., :3].astype(np.float32)
    return float(np.abs(a[1:] - a[:-1]).mean())


def main():
    EXTRACT.mkdir(parents=True, exist_ok=True)
    src = decode(SRC)
    rgb_tm = temporal_mad(src)
    results = {"source_temporal_mad": rgb_tm, "routes": {}}

    # ---- pose ----
    pose = decode(CTRL["pose"])
    nonblack = (pose.max(axis=3) > 16)          # any channel lit = drawn ink
    px_counts = nonblack.reshape(N if N <= pose.shape[0] else pose.shape[0], -1).sum(axis=1)
    blobs, blob_sizes = [], []
    for i in range(pose.shape[0]):
        lab, k = ndimage.label(nonblack[i])
        if k:
            sizes = ndimage.sum(nonblack[i], lab, range(1, k + 1))
            big = sizes[sizes >= 200]
            blobs.append(len(big))
            blob_sizes.append(sorted(big.tolist(), reverse=True))
        else:
            blobs.append(0)
            blob_sizes.append([])
    results["routes"]["pose"] = {
        "frames": int(pose.shape[0]),
        "skeleton_px_per_frame": {
            "mean": float(px_counts.mean()), "min": int(px_counts.min()),
            "max": int(px_counts.max())},
        "frames_with_zero_skeleton": int((px_counts == 0).sum()),
        "person_blobs_per_frame": {
            "mean": float(np.mean(blobs)), "min": int(min(blobs)),
            "max": int(max(blobs)),
            "histogram": {str(k): blobs.count(k) for k in sorted(set(blobs))}},
        "blob_sizes_px_examples": blob_sizes[:3] + blob_sizes[-3:],
    }

    # ---- depth ----
    dep = decode(CTRL["depth"])
    dl = np.stack([lum(f) for f in dep])
    sm = np.stack([sobel_mag(l) for l in dl])
    results["routes"]["depth"] = {
        "frames": int(dep.shape[0]),
        "luminance_mean": float(dl.mean()), "luminance_std": float(dl.std()),
        "per_frame_lum_std_min": float(dl.reshape(dl.shape[0], -1).std(axis=1).min()),
        "per_frame_lum_std_max": float(dl.reshape(dl.shape[0], -1).std(axis=1).max()),
        "sobel_mean": float(sm.mean()), "sobel_p95": float(np.percentile(sm, 95)),
        "depth_temporal_mad": temporal_mad(dep),
        "source_rgb_temporal_mad": rgb_tm,
    }

    # ---- gate frames ----
    for route, stack in (("pose", pose), ("depth", dep)):
        for i in FRAME_IDX:
            f = min(i, stack.shape[0] - 1)
            (EXTRACT / f"{route}_f{f:03d}.png").write_bytes(
                _png(stack[f]))
            pair = np.concatenate([src[f], np.full((H, 4, 3), 255, np.uint8), stack[f]], axis=1)
            (EXTRACT / f"{route}_f{f:03d}_pair.png").write_bytes(_png(pair))

    (OUT / "extract_metrics.json").write_bytes(
        json.dumps(results, indent=1, ensure_ascii=False).encode("utf-8"))
    print(json.dumps(results, indent=1, ensure_ascii=False)[:2000])


def _png(img: np.ndarray) -> bytes:
    import zlib

    def chunk(tag, data):
        c = tag + data
        return (len(data)).to_bytes(4, "big") + c + \
            (zlib.crc32(c) & 0xFFFFFFFF).to_bytes(4, "big")
    h, w, _ = img.shape
    raw = b"".join(b"\x00" + img[y].tobytes() for y in range(h))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", w.to_bytes(4, "big") + h.to_bytes(4, "big")
                    + bytes([8, 2, 0, 0, 0]))
            + chunk(b"IDAT", zlib.compress(raw, 6))
            + chunk(b"IEND", b""))


if __name__ == "__main__":
    main()
