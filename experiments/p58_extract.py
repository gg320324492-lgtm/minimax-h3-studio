"""P58 stage 1: extract control signals from REAL material.

Runs the built-in SDPose (wholebody + RT-DETR person boxes, exactly the
official template's subgraph recipe) and Depth Anything 3 (base, mono mode)
over the real clip `p58_real.mp4` (864x480x124 @ 24fps, cut from
water_renewal/07_edit/WaterRenewal_1080p.mp4 t=169.0s).

The prompt is written directly in API form (the extraction graph has no
subgraph wrapper to expand). VRAM is sampled once per second while the job
runs, like p57_runner.py did for generation, so the report can state the
extraction stage's own peak and time — the work order asks for both routes'
extraction cost before any generation runs.

Usage: python p58_extract.py <pose|depth>
Writes out/p58/extract_<route>.json (run record) and moves the produced
control video to out/p58/controls/p58_<route>_real.mp4, then copies it into
E:\\ComfyUI\\input\\ for the generation stage.
"""
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bench import api  # noqa: E402

OUT = Path(r"E:\Minimax-H3\out\p58")
COMFY_OUTPUT = Path(r"E:\ComfyUI\output")
COMFY_INPUT = Path(r"E:\ComfyUI\input")
CLIP = "p58_real.mp4"

POSE_PROMPT = {
    "1": {"class_type": "LoadVideo", "inputs": {"file": CLIP}},
    "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
    "3": {"class_type": "CheckpointLoaderSimple",
          "inputs": {"ckpt_name": "sdpose_wholebody_fp16.safetensors"}},
    "4": {"class_type": "UNETLoader",
          "inputs": {"unet_name": "rt_detr_v4-x-hgnet_fp16.safetensors",
                     "weight_dtype": "default"}},
    # template subgraph values: threshold 0.5, class 'person', max 2
    "5": {"class_type": "RTDETR_detect",
          "inputs": {"model": ["4", 0], "image": ["2", 0], "threshold": 0.5,
                     "class_name": "person", "max_detections": 2}},
    "6": {"class_type": "SDPoseKeypointExtractor",
          "inputs": {"model": ["3", 0], "vae": ["3", 2], "image": ["2", 0],
                     "batch_size": 16, "bboxes": ["5", 0]}},
    # template subgraph values: body/hands/face/feet on, stick 4, face pt 2,
    # score_threshold 0.5, draw_head on
    "7": {"class_type": "SDPoseDrawKeypoints",
          "inputs": {"keypoints": ["6", 0], "draw_body": True,
                     "draw_hands": True, "draw_face": True, "draw_feet": True,
                     "stick_width": 4, "face_point_size": 2,
                     "score_threshold": 0.5, "draw_head": True}},
    "8": {"class_type": "CreateVideo", "inputs": {"images": ["7", 0], "fps": 24}},
    "9": {"class_type": "SaveVideo",
          "inputs": {"video": ["8", 0], "filename_prefix": "p58/pose_real",
                     "format": "auto", "format.codec": "auto", "codec": "auto"}},
}

DEPTH_PROMPT = {
    "1": {"class_type": "LoadVideo", "inputs": {"file": CLIP}},
    "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
    "3": {"class_type": "LoadDA3Model",
          "inputs": {"model_name": "depth_anything_3_base.safetensors",
                     "weight_dtype": "default"}},
    # mono mode, node default resolution 504 (longest side, multiple of 14),
    # v2_style normalisation = the node's own default
    "4": {"class_type": "DA3Inference",
          "inputs": {"da3_model": ["3", 0], "image": ["2", 0],
                     "resolution": 504, "resize_method": "upper_bound_resize",
                     "mode": "mono"}},
    "5": {"class_type": "DA3Render",
          "inputs": {"da3_geometry": ["4", 0], "output": "depth",
                     "output.normalization": "v2_style",
                     "output.apply_sky_clip": False}},
    "6": {"class_type": "CreateVideo", "inputs": {"images": ["5", 0], "fps": 24}},
    "7": {"class_type": "SaveVideo",
          "inputs": {"video": ["6", 0], "filename_prefix": "p58/depth_real",
                     "format": "auto", "format.codec": "auto", "codec": "auto"}},
}


class Vram:
    def __init__(self, interval=1.0):
        self.interval = interval
        self.stop = threading.Event()
        self.samples = []
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def _query(self):
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.used,utilization.gpu",
                 "--format=csv,noheader,nounits"], text=True, timeout=10)
            mem, util = out.strip().splitlines()[0].split(", ")
            return int(mem), int(util)
        except Exception:
            return None, None

    def _loop(self):
        while not self.stop.is_set():
            m, u = self._query()
            if m is not None:
                self.samples.append((round(time.time(), 1), m, u))
            time.sleep(self.interval)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *a):
        self.stop.set()
        self.thread.join(timeout=5)


def run(route):
    prompt = POSE_PROMPT if route == "pose" else DEPTH_PROMPT
    base = Vram()._query()
    print(f"[p58] route={route} idle baseline: {base[0]} MiB used, {base[1]}% util")

    t0 = time.time()
    result = api("/prompt", "POST", {"prompt": prompt})
    prompt_id = result.get("prompt_id")
    print(f"[p58] prompt_id={prompt_id}")

    status, rec = "running", None
    v = Vram()
    with v:
        while True:
            h = api(f"/history/{prompt_id}")
            if prompt_id in h:
                rec = h[prompt_id]
                st = rec.get("status", {})
                if st.get("completed") or st.get("status_str") in ("error", "failed"):
                    status = st
                    break
            if time.time() - t0 > 3600:
                status = {"status_str": "timeout"}
                break
            time.sleep(2)
    elapsed = time.time() - t0
    peak = max((m for _, m, _ in v.samples), default=base[0])

    produced = []
    if rec:
        for nid, o in (rec.get("outputs") or {}).items():
            for key in ("videos", "images"):
                for f in (o.get(key) or []):
                    if f.get("type") == "output":
                        produced.append(f)
    print(f"[p58] status={status} elapsed={elapsed:.1f}s peak={peak} MiB "
          f"(over baseline {peak - base[0]} MiB) files={produced}")

    record = {"route": route, "prompt_id": prompt_id, "status": status,
              "elapsed_s": round(elapsed, 1),
              "vram_idle_baseline_mib": base[0], "vram_peak_mib": peak,
              "vram_peak_over_baseline_mib": peak - base[0],
              "vram_samples": v.samples, "produced": produced,
              "api_prompt": prompt}
    (OUT / f"extract_{route}.json").write_bytes(
        json.dumps(record, indent=1, ensure_ascii=False).encode("utf-8"))

    # move the produced control video out of ComfyUI's output dir
    dest_dir = OUT / "controls"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for f in produced:
        src = COMFY_OUTPUT / f.get("subfolder", "") / f["filename"]
        if src.exists():
            dest = dest_dir / f"p58_{route}_real_{f['filename']}"
            shutil.copy2(src, dest)
            # the generation stage loads it from ComfyUI's input dir
            shutil.copy2(src, COMFY_INPUT / dest.name)
            print(f"[p58] control -> {dest}")
    return 0 if status == "success" or (isinstance(status, dict) and status.get("completed")) else 1


if __name__ == "__main__":
    sys.exit(run(sys.argv[1]))
