"""P57: build the measurement variants of the official
video_minimax_h3_fun_controlnet_union template.

The official copy (untouched apart from nothing) lives at
workflows/video_minimax_h3_fun_controlnet_union.json; this script derives
per-run UI workflows from it, applying ONLY these documented changes:

  1. ModelPatchLoader  -> the Union 2.0 bf16 pack we downloaded for P57
     (the template ships pointing at the legacy int8 name).
  2. Video VAELoader   -> minimax_h3_video_vae_fp16.safetensors (int8_convrot
     is not on this machine; fp16 is the P55/P56 production choice).
  3. Control side      -> LoadVideo(p57_<route>.mp4) -> Video Slice ->
     GetVideoComponents -> Apply.control_video. The SDPose extractor subgraph
     is dropped because its two model files (sdpose_wholebody, rt_detr) are
     not on disk; the work order explicitly allows feeding preprocessed
     control frames ("the control video is input, not output; a drawn stick
     figure is fine"). Canny/Depth/HED/MLSD were never wired in the template
     anyway (its own note: swap the preprocessor only).
  4. strength          -> per variant (the control-effectiveness pair is
     1.0 vs 0.0, everything else identical).
  5. RandomNoise seed  -> pinned by the runner (single SEED for all variants).
  6. SaveVideo prefix  -> p57/<label>.

Everything else (prompt, 0.4MP 16:9 -> 864x480, 5s -> 124 frames, 20 steps,
res_multistep + simple sigmas, Lightning-LoRA switch OFF, guidance baked by
the distilled model, audio VAE + mux) is the template's own defaults.

Writes workflows/video_p57_<label>.json (gitignored dir, like every workflow
in this repo) and prints a per-file summary of the widget diffs.
"""
import copy
import json
from pathlib import Path

ROOT = Path(r"E:\Minimax-H3")
WF = ROOT / "workflows"
TEMPLATE = WF / "video_minimax_h3_fun_controlnet_union.json"

UNION2 = "minimax_h3_fun_controlnet_union_2.0_pruned_bf16.safetensors"
UNION2_URL = ("https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/"
              "model_patches/" + UNION2)
VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"


def _fix_model_meta(node, new_name, new_url=None):
    """The frontend keeps a `properties.models[]` download descriptor carrying
    the shipped recipe's filename. Rewrite the name to the pack we actually
    load (and the url only when we have a verified one) so the saved UI is
    honest about which file will be fetched/run."""
    for m in (node.get("properties", {}).get("models") or []):
        m["name"] = new_name
        if new_url:
            m["url"] = new_url
        else:
            m.pop("url", None)  # file is already on disk; don't leave a stale fetch url

ROUTES = ["pose", "canny", "depth", "hed", "mlsd"]

VARIANTS = (
    # (label, route, strength)  - pose runs BOTH strengths as the pair
    [("pose_s1", "pose", 1.0), ("pose_s0", "pose", 0.0)]
    + [(f"{r}_s1", r, 1.0) for r in ("canny", "depth", "hed", "mlsd")]
)

DROP_NODES = {700, 704, 710}  # SDPose wrapper, PreviewImage, dead GetImageSize
DROP_LINKS = {1761, 1762, 1768}  # control-side links replaced by 1770->apply
# MarkdownNote doc nodes also carry the shipped-recipe names (legacy int8 pack,
# sdpose models) — they are stripped here so the variant UI file is honest
# about what it will actually run. to_prompt would skip them anyway.
DROP_TYPES = {"MarkdownNote"}


def _widget(node, key, value):
    """Set a widget by name in BOTH serializations the frontend keeps.

    The template stores every editable widget in widgets_values_named and also
    positionally in widgets_values (index 0 is the widget we retarget on each
    of these nodes). to_prompt reads named first, but keeping the positional
    array in sync means the saved UI file is honest to a human who opens it."""
    if node.get("widgets_values_named") is not None and key in node["widgets_values_named"]:
        node["widgets_values_named"][key] = value
    names = node.get("widgets_names") or []
    vals = node.get("widgets_values")
    if vals is not None:
        if key in names:
            vals[names.index(key)] = value
        else:
            vals[0] = value  # each node below exposes this as its first widget


def build_variant(template, label, route, strength):
    wf = copy.deepcopy(template)
    nodes = {n["id"]: n for n in wf["nodes"]}

    # 1/2: model retargets (widget AND the frontend download descriptor)
    _widget(nodes[173], "name", UNION2)
    _fix_model_meta(nodes[173], UNION2, UNION2_URL)
    _widget(nodes[119], "vae_name", VIDEO_VAE)
    _fix_model_meta(nodes[119], VIDEO_VAE)  # already on disk, no url

    # 3: control side -> our preprocessed route video
    _widget(nodes[174], "file", f"p57_{route}.mp4")

    # 4: strength
    _widget(nodes[172], "strength", strength)

    # 6: output prefix
    _widget(nodes[707], "filename_prefix", f"p57/{label}")

    # drop the SDPose chain and rewire GetVideoComponents -> Apply.control_video
    drop_ids = set(DROP_NODES) | {n["id"] for n in wf["nodes"] if n["type"] in DROP_TYPES}
    wf["nodes"] = [n for n in wf["nodes"] if n["id"] not in drop_ids]
    wf["links"] = [l for l in wf["links"]
                   if l[0] not in DROP_LINKS and l[1] not in drop_ids and l[3] not in drop_ids]
    apply_node = [n for n in wf["nodes"] if n["id"] == 172][0]
    for inp in apply_node["inputs"]:
        if inp["name"] == "control_video":
            inp["link"] = 1768  # rebuilt below: GetVideoComponents.images (IMAGE)
    gvc = [n for n in wf["nodes"] if n["id"] == 709][0]
    wf["links"].append([1768, 709, 0, 172, 3, "IMAGE"])
    for out in gvc["outputs"]:
        if out["name"] == "images":
            out["links"] = [1768]

    wf["definitions"] = {"subgraphs": [], "node_defs": {}}
    wf["last_node_id"] = max(n["id"] for n in wf["nodes"])
    return wf


def main():
    template = json.loads(TEMPLATE.read_bytes().decode("utf-8"))
    summary = []
    for label, route, strength in VARIANTS:
        wf = build_variant(template, label, route, strength)
        # sanity: no reference to the legacy pack / int8 vae / SDPose anywhere
        blob = json.dumps(wf)
        assert "legacy" not in blob
        for forbidden in ("sdpose_wholebody", "rt_detr", "dancer_field_pose",
                         "minimax_h3_fun_controlnet_union_pruned_int8",
                         "minimax_h3_video_vae_int8"):
            assert forbidden not in blob, forbidden
        assert UNION2 in blob and VIDEO_VAE in blob and f"p57_{route}.mp4" in blob
        out = WF / f"video_p57_{label}.json"
        out.write_bytes(json.dumps(wf, ensure_ascii=False).encode("utf-8"))
        n_apply = [n for n in wf["nodes"] if n["id"] == 172][0]
        summary.append((str(out), len(wf["nodes"]), route,
                        n_apply["widgets_values_named"]["strength"],
                        [n for n in wf["nodes"] if n["id"] == 707][0]["widgets_values_named"]["filename_prefix"]))
    for s in summary:
        print(s)


if __name__ == "__main__":
    main()
