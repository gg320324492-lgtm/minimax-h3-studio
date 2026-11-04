"""P57 control-effectiveness measurement: pose strength 1.0 vs 0.0.

Same prompt, same seed, same 864x480x124, the ONLY difference is the
MiniMaxH3FunControlNetApply `strength` (1.0 = control skip added, 0.0 = branch
still runs but `add_(skip, alpha=0)` is a no-op -> equivalent to no control,
per nodes_minimax_h3.py:515). So this A/B isolates the control contribution.

Two independent readings, as the work order requires:
  1. PIXEL: per-frame mean absolute difference and PSNR between the two videos.
     "If they are nearly identical, control did NOT take effect" -> low pixel
     diff here means control is doing nothing, which the order calls more
     serious than an OOM.
  2. VLM: qwen2.5vl:7b reads the same frame from each video and answers what
     the humanoid is doing / where its arms are. Different answers on the two
     sides = the control changed the content, not just the pixels.

Frames for both videos are extracted at the same indices into out/p57/compare/.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, r"E:\Minimax-H3\studio\scripts")
from vlm_critic import ask_vlm  # noqa: E402

ROOT = Path(r"E:\Minimax-H3")
RUNS = ROOT / "out" / "p57" / "runs"
CMP = ROOT / "out" / "p57" / "compare"
FRAME_IDX = [30, 62, 93]  # ~1.25s, ~2.6s, ~3.9s into the 124-frame clip


def extract(video: Path, tag: str):
    CMP.mkdir(parents=True, exist_ok=True)
    out = []
    for i in FRAME_IDX:
        png = CMP / f"{tag}_f{i:03d}.png"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(video), "-vf", f"select=eq(n\\,{i})",
             "-frames:v", "1", str(png)],
            check=True, capture_output=True)
        out.append((i, png))
    return out


def load_frame(path: Path):
    p = subprocess.run(["ffmpeg", "-i", str(path), "-f", "rawvideo",
                        "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    w, h = 864, 480
    arr = np.frombuffer(p.stdout, dtype=np.uint8).reshape(h, w, 3)
    return arr.astype(np.float32)


def pixel_metrics(a, b):
    mad = float(np.mean(np.abs(a - b)))
    mse = float(np.mean((a - b) ** 2))
    psnr = float("inf") if mse < 1e-9 else 10.0 * np.log10(255.0 ** 2 / mse)
    return {"mean_abs_diff": round(mad, 3), "mse": round(mse, 2), "psnr_db": round(psnr, 2)}


VLM_Q = ("Look at the humanoid figure ONLY. Answer two facts about it, "
         "nothing else, in exactly this form: "
         "body_orientation=<facing-camera | back-to-camera | sideways>, "
         "arms=<extended out to the sides | raised in front of chest | "
         "behind back | lowered at sides>")


def vlm_read(png: Path):
    ans, why = ask_vlm(png, VLM_Q)
    return {"answer": (ans or "").strip(), "unavailable": why or None}


def main():
    a_path = RUNS / "pose_s1.mp4"
    b_path = RUNS / "pose_s0.mp4"
    if not (a_path.exists() and b_path.exists()):
        print(f"missing video(s): a={a_path.exists()} b={b_path.exists()}")
        sys.exit(2)

    fa = extract(a_path, "pose_scale1")
    fb = extract(b_path, "pose_scale0")

    result = {"frame_indices": FRAME_IDX, "frames": []}
    for (i, pa), (_, pb) in zip(fa, fb):
        pm = pixel_metrics(load_frame(pa), load_frame(pb))
        result["frames"].append({
            "n": i,
            "pixel": pm,
            "vlm_scale1": vlm_read(pa),
            "vlm_scale0": vlm_read(pb),
        })

    out = ROOT / "out" / "p57" / "control_effectiveness.json"
    out.write_bytes(json.dumps(result, ensure_ascii=False, indent=1).encode("utf-8"))
    for f in result["frames"]:
        print(f"frame {f['n']:3d}: MAD={f['pixel']['mean_abs_diff']:6.2f} "
              f"PSNR={f['pixel']['psnr_db']:6.2f} dB")
        print(f"    scale1 VLM: {f['vlm_scale1']['answer'] or f['vlm_scale1']['unavailable']}")
        print(f"    scale0 VLM: {f['vlm_scale0']['answer'] or f['vlm_scale0']['unavailable']}")


if __name__ == "__main__":
    main()
