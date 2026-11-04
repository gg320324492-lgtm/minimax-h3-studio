"""P58 measurement: the three comparison groups, per route.

All readings are pixel-based (the work order's ruling: P57 measured the VLM
to be unreliable, so effectiveness is judged by pixel difference + eyeball;
VLM is at most a labelled side note).

Pairs (same seed 1086599926715797, same prompt, same 864x480x124, same
20 steps — the only variable is marked):

  1. effectiveness   : <route>_real_s1 vs <route>_real_s0   (strength 1.0/0.0)
  2. real vs synthetic: <route>_real_s1 vs P57 <route>_s1   (control source)
  3. quality baseline : <route>_real_s1 vs <route>_real_s0  (s0 == no control,
     proven at nodes_minimax_h3.py:605 — strength 0 returns the model
     UNPATCHED — and cross-checked here by byte-comparing the s0 outputs
     against P57's pose_s0.mp4, which used a DIFFERENT control video but the
     same seed: identical bytes would confirm both determinism and the
     no-op claim on the real chain)
  4. e2e vs two-stage : <route>_e2e_s1 vs <route>_real_s1   (mp4 roundtrip)

For every pair: per-frame MAD and PSNR over the full 124 frames, plus the
3 gate frames (f30/f62/f93) written to out/p58/compare/ as side-by-side
strips for the human ruling.
"""
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(r"E:\Minimax-H3")
P58 = ROOT / "out" / "p58"
P57 = ROOT / "out" / "p57"
CMP = P58 / "compare"
W, H = 864, 480
FRAME_IDX = [30, 62, 93]

RUNS = {}
for p in (P58 / "runs").glob("*.mp4"):
    RUNS[p.stem] = p
SYN = {"pose_synth": P57 / "runs" / "pose_s1.mp4",
       "depth_synth": P57 / "runs" / "depth_s1.mp4",
       "p57_pose_s0": P57 / "runs" / "pose_s0.mp4"}


def decode(video: Path) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-"], check=True, capture_output=True).stdout
    arr = np.frombuffer(raw, dtype=np.uint8)
    per = H * W * 3
    n = len(arr) // per
    return arr[:n * per].reshape(n, H, W, 3)


def mad_psnr(a: np.ndarray, b: np.ndarray):
    mads, psnrs = [], []
    n = min(a.shape[0], b.shape[0])
    for i in range(n):
        d = np.abs(a[i].astype(np.float32) - b[i].astype(np.float32))
        mad = float(d.mean())
        mse = float((d * d).mean())
        mads.append(mad)
        psnrs.append(float("inf") if mse == 0 else 10 * np.log10(255.0 * 255.0 / mse))
    return mads, psnrs


def strip(tag, a_frame, b_frame):
    pair = np.concatenate([a_frame, np.full((H, 4, 3), 255, np.uint8), b_frame], axis=1)
    (CMP / f"{tag}.png").write_bytes(_png(pair))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    CMP.mkdir(parents=True, exist_ok=True)
    out = {"pairs": {}, "byte_checks": {}, "specs": {}}

    def spec(p: Path):
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_name,width,height,r_frame_rate,nb_frames:format=duration",
             "-of", "csv=p=0", str(p)], capture_output=True, text=True)
        return r.stdout.strip().replace("\n", " | ")

    pairs = [
        ("pose_effectiveness", "pose_real_s1", "pose_real_s0", None),
        ("depth_effectiveness", "depth_real_s1", "depth_real_s0", None),
        ("pose_real_vs_synth", "pose_real_s1", None, "pose_synth"),
        ("depth_real_vs_synth", "depth_real_s1", None, "depth_synth"),
        ("pose_e2e_vs_two_stage", "pose_e2e_s1", "pose_real_s1", None),
        ("depth_e2e_vs_two_stage", "depth_e2e_s1", "depth_real_s1", None),
    ]
    cache = {}

    def load(key):
        if key not in cache:
            p = RUNS.get(key) or SYN.get(key)
            if p is None or not p.exists():
                return None
            cache[key] = decode(p)
        return cache.get(key)

    for name, ka, kb, kc in pairs:
        a = load(ka)
        b = load(kb) if kb else load(kc)
        if a is None or b is None:
            out["pairs"][name] = {"error": f"missing input ({ka} / {kb or kc})"}
            continue
        mads, psnrs = mad_psnr(a, b)
        finite = [p for p in psnrs if p != float("inf")]
        out["pairs"][name] = {
            "a": ka, "b": kb or kc,
            "frames_compared": len(mads),
            "mad_mean": round(float(np.mean(mads)), 3),
            "mad_min": round(float(np.min(mads)), 3),
            "mad_max": round(float(np.max(mads)), 3),
            "psnr_mean_db": round(float(np.mean(finite)), 2) if finite else None,
            "psnr_min_db": round(float(np.min(finite)), 2) if finite else None,
            "psnr_max_db": round(float(np.max(finite)), 2) if finite else None,
            "identical_frame_count": sum(1 for p in psnrs if p == float("inf")),
        }
        for i in FRAME_IDX:
            strip(f"{name}_f{i:03d}", a[min(i, a.shape[0]-1)], b[min(i, b.shape[0]-1)])

    # byte-level identity checks for the no-op / determinism claim
    checks = {
        "pose_real_s0_vs_p57_pose_s0": ("pose_real_s0", "p57_pose_s0"),
        "pose_real_s0_vs_depth_real_s0": ("pose_real_s0", "depth_real_s0"),
    }
    for name, (ka, kb) in checks.items():
        pa, pb = RUNS.get(ka) or SYN.get(ka), RUNS.get(kb) or SYN.get(kb)
        if pa and pb and pa.exists() and pb.exists():
            out["byte_checks"][name] = {"sha_a": sha(pa)[:16], "sha_b": sha(pb)[:16],
                                        "identical": sha(pa) == sha(pb)}
        else:
            out["byte_checks"][name] = {"error": "file missing"}

    for k, p in {**RUNS, **SYN}.items():
        if p.exists():
            out["specs"][k] = spec(p)

    (P58 / "compare_metrics.json").write_bytes(
        json.dumps(out, indent=1, ensure_ascii=False).encode("utf-8"))
    print(json.dumps(out["pairs"], indent=1)[:1500])
    print("BYTE:", json.dumps(out["byte_checks"], indent=1))


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
