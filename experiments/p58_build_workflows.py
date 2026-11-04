"""P58 stage 2: build the generation workflows for the real-extraction chain.

Two families, both derived from the P57 variants with ONLY the documented
edits (prompt, seed, 864x480x124, 20 steps, res_multistep + simple sigmas,
Lightning-LoRA off, Union 2.0 pack, fp16 video VAE — all unchanged):

  A. two-stage UI variants (workflows/video_p58_<label>.json)
     from video_p57_<route>_s1/s0.json:
       1. LoadVideo(174) file -> the extracted real control video
          (p58_<route>_real_*.mp4, already copied into ComfyUI/input)
       2. SaveVideo(707) filename_prefix -> p58/<label>
     Arms: <route>_real_s1 (strength 1.0) and <route>_real_s0 (0.0).
     Source note: nodes_minimax_h3.py:605 — strength == 0 returns the model
     UNPATCHED, so the s0 arm is also the "pure H3, no control branch"
     baseline the work order asks for (verified, not assumed: the s0 outputs
     are byte-compared against P57's pose_s0.mp4 in p58_measure.py).

  B. end-to-end API prompts (out/p58/api_p58_<route>_e2e_s1.json)
     the same converted P57 prompt, but the control side is replaced by the
     live extraction chain (LoadVideo p58_real.mp4 -> GetVideoComponents ->
     SDPose(+RT-DETR) / DA3 -> Apply.control_video), no intermediate mp4.
     This is the production-shape graph: it measures whether the extractor
     models and the H3 sampler fit in 32 GB when they live in ONE graph.

Usage: python p58_build_workflows.py
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(r"E:\Minimax-H3")
sys.path.insert(0, str(ROOT / "experiments"))
from p56_runner import to_prompt  # noqa: E402

WF = ROOT / "workflows"
OUT = ROOT / "out" / "p58"

SEED = 1086599926715797

CTRL_FILE = {
    "pose": "p58_pose_real_pose_real_00001_.mp4",
    "depth": "p58_depth_real_depth_real_00001_.mp4",
}


def _set_widget(node, key, value):
    """Set a widget in both serializations the frontend keeps (same helper
    P57's builder used)."""
    named = node.get("widgets_values_named")
    if named is not None and key in named:
        named[key] = value
    names = node.get("widgets_values")
    if names is None:
        return
    # positional: find index by the node's declared widget order
    order = node.get("widgets_values_order") or []
    if key in order:
        names[order.index(key)] = value
    elif named is not None:
        # fall back: replace the first positional slot matching the old value
        for i, v in enumerate(names):
            if v == named.get(key):
                names[i] = value
                break


def build_two_stage():
    for route in ("pose", "depth"):
        src1 = WF / f"video_p57_{route}_s1.json"
        for strength, tag in ((1.0, "s1"), (0.0, "s0")):
            wf = json.loads(src1.read_bytes().decode("utf-8"))
            for n in wf["nodes"]:
                if n["type"] == "LoadVideo":
                    _set_widget(n, "file", CTRL_FILE[route])
                elif n["type"] == "MiniMaxH3FunControlNetApply":
                    _set_widget(n, "strength", strength)
                elif n["type"] == "SaveVideo":
                    label = f"{route}_real_{tag}"
                    _set_widget(n, "filename_prefix", f"p58/{label}")
            label = f"{route}_real_{tag}"
            dst = WF / f"video_p58_{label}.json"
            dst.write_bytes(json.dumps(wf, ensure_ascii=False).encode("utf-8"))
            print(f"[p58] wrote {dst.name}")


POSE_EXTRACT_NODES = {
    "900": {"class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "sdpose_wholebody_fp16.safetensors"}},
    "901": {"class_type": "UNETLoader",
            "inputs": {"unet_name": "rt_detr_v4-x-hgnet_fp16.safetensors",
                       "weight_dtype": "default"}},
    "902": {"class_type": "RTDETR_detect",
            "inputs": {"model": ["901", 0], "image": ["903", 0],
                       "threshold": 0.5, "class_name": "person",
                       "max_detections": 2}},
    "903": {"class_type": "ResizeImageMaskNode",
            "inputs": {"input": ["709", 0], "resize_type": "scale longer dimension",
                       "resize_type.longer_size": 1024, "scale_method": "lanczos"}},
    "904": {"class_type": "SDPoseKeypointExtractor",
            "inputs": {"model": ["900", 0], "vae": ["900", 2],
                       "image": ["903", 0], "batch_size": 16,
                       "bboxes": ["902", 0]}},
    "905": {"class_type": "SDPoseDrawKeypoints",
            "inputs": {"keypoints": ["904", 0], "draw_body": True,
                       "draw_hands": True, "draw_face": True, "draw_feet": True,
                       "stick_width": 4, "face_point_size": 2,
                       "score_threshold": 0.5, "draw_head": True}},
}
POSE_CTRL_SOURCE = ["905", 0]

DEPTH_EXTRACT_NODES = {
    "910": {"class_type": "LoadDA3Model",
            "inputs": {"model_name": "depth_anything_3_base.safetensors",
                       "weight_dtype": "default"}},
    "911": {"class_type": "DA3Inference",
            "inputs": {"da3_model": ["910", 0], "image": ["709", 0],
                       "resolution": 504, "resize_method": "upper_bound_resize",
                       "mode": "mono"}},
    "912": {"class_type": "DA3Render",
            "inputs": {"da3_geometry": ["911", 0], "output": "depth",
                       "output.normalization": "v2_style",
                       "output.apply_sky_clip": False}},
}
DEPTH_CTRL_SOURCE = ["912", 0]


def build_e2e():
    for route in ("pose", "depth"):
        wf = json.loads((WF / f"video_p57_{route}_s1.json").read_bytes().decode("utf-8"))
        prompt = to_prompt(wf, SEED)
        # swap the control source: real clip instead of the synthetic control
        prompt["174"]["inputs"]["file"] = "p58_real.mp4"
        # drop the mp4 roundtrip: wire the extractor straight into Apply
        prompt["172"]["inputs"]["control_video"] = (
            POSE_CTRL_SOURCE if route == "pose" else DEPTH_CTRL_SOURCE)
        extract = POSE_EXTRACT_NODES if route == "pose" else DEPTH_EXTRACT_NODES
        for nid, node in copy.deepcopy(extract).items():
            prompt[nid] = node
        # SaveVideo prefix honest
        for nid, node in prompt.items():
            if node["class_type"] == "SaveVideo":
                node["inputs"]["filename_prefix"] = f"p58/{route}_e2e_s1"
        dst = OUT / f"api_p58_{route}_e2e_s1.json"
        dst.write_bytes(json.dumps(prompt, indent=1, ensure_ascii=False).encode("utf-8"))
        print(f"[p58] wrote {dst.name} ({len(prompt)} nodes)")


if __name__ == "__main__":
    build_two_stage()
    build_e2e()
