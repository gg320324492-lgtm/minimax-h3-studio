"""P57: consolidate every run's measurements into one table.

Reads out/p57/run_<label>.json (written by p57_runner) and ffprobes the moved
video at out/p57/runs/<label>.mp4. Prints a Markdown-ready table with the
three numbers the report needs per run: status, end-to-end seconds, VRAM peak
MiB, and the ffprobe spec (17k+5 frames / 24fps / audio track).
"""
import json
import subprocess
from pathlib import Path

OUT = Path(r"E:\Minimax-H3\out\p57")
LABELS = ["pose_s1", "pose_s0", "canny_s1", "depth_s1", "hed_s1", "mlsd_s1"]


def probe(p: Path):
    d = json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(p)],
        text=True, encoding="utf-8"))
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), {})
    return {
        "v_codec": v.get("codec_name"),
        "size": f"{v.get('width')}x{v.get('height')}",
        "fps": v.get("r_frame_rate"),
        "nb_frames": int(v.get("nb_frames") or 0),
        "grid_17k5": int(v.get("nb_frames") or 0) % 17 == 5,
        "a_codec": a.get("codec_name"),
    }


def main():
    rows = []
    for lbl in LABELS:
        run = OUT / f"run_{lbl}.json"
        if not run.exists():
            rows.append({"label": lbl, "status": "NOT RUN"})
            continue
        rec = json.loads(run.read_bytes().decode("utf-8"))
        vid = OUT / "runs" / f"{lbl}.mp4"
        spec = probe(vid) if vid.exists() else {"note": "video missing"}
        rows.append({
            "label": lbl,
            "status": rec.get("status"),
            "elapsed_s": rec.get("elapsed_s"),
            "peak_mib": rec.get("vram_peak_mib"),
            "over_baseline_mib": rec.get("vram_peak_over_baseline_mib"),
            "spec": spec,
        })
    (OUT / "summary.json").write_bytes(
        json.dumps(rows, ensure_ascii=False, indent=1).encode("utf-8"))
    print(f"| 运行 | 状态 | 用时(s) | 显存峰值MiB | 高于基线 | 规格 |")
    print(f"|---|---|---|---|---|---|")
    for r in rows:
        if r.get("status") == "NOT RUN":
            print(f"| {r['label']} | NOT RUN | - | - | - | - |")
            continue
        s = r["spec"]
        spec_str = (f"{s.get('size')} {s.get('fps')} {s.get('nb_frames')}帧 "
                    f"17k+5={s.get('grid_17k5')} 音频={s.get('a_codec')}") if "size" in s else "缺片"
        print(f"| {r['label']} | {r['status']} | {r['elapsed_s']} | {r['peak_mib']} | "
              f"{r['over_baseline_mib']} | {spec_str} |")


if __name__ == "__main__":
    main()
