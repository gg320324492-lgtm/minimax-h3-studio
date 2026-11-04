"""P57 runner: submit a built workflow, measure end-to-end time and VRAM.

Reuses p56_runner.to_prompt (expand_subgraphs + flat_nodes_to_prompt, seed
pinned, control_after_generate stripped) — the conversion path P55/P56 proved
against the live 0.43.2 server. While the job runs, samples
`nvidia-smi --query-gpu=memory.used` once per second in a background thread
and records the peak; also records the idle baseline before submitting.

Usage: python p57_runner.py <workflow.json> <label>
Writes E:\\Minimax-H3\\out\\p57\\run_<label>.json and moves the produced MP4
into E:\\Minimax-H3\\out\\p57\\runs\\.
"""
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from p56_runner import to_prompt  # noqa: E402
from bench import api  # noqa: E402

SEED = 1086599926715797  # the template's own RandomNoise value, pinned for every P57 run
OUT = Path(r"E:\Minimax-H3\out\p57")
COMFY_OUTPUT = Path(r"E:\ComfyUI\output")


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


def main():
    wf_path = Path(sys.argv[1])
    label = sys.argv[2]
    workflow = json.loads(wf_path.read_bytes().decode("utf-8"))
    prompt = to_prompt(workflow, SEED)
    seeds = [(k, v["inputs"].get("noise_seed")) for k, v in prompt.items()
             if v["class_type"] == "RandomNoise"]
    print(f"[p57] label={label} nodes={len(prompt)} pinned_seeds={seeds}")

    base = Vram()._query()
    print(f"[p57] idle baseline: {base[0]} MiB used, {base[1]}% util")

    t0 = time.time()
    result = api("/prompt", "POST", {"prompt": prompt})
    prompt_id = result.get("prompt_id")
    print(f"[p57] prompt_id={prompt_id}")

    status, _, rec = "running", None, None
    v = Vram()
    with v:
        while True:
            h = api(f"/history/{prompt_id}")
            if prompt_id in h:
                rec = h[prompt_id]
                st = rec.get("status", {})
                if st.get("completed") or st.get("status_str") in ("error", "failed") or "outputs" in rec:
                    status = st
                    break
            if time.time() - t0 > 3600:
                status = {"status_str": "timeout"}
                break
            time.sleep(2)
    elapsed = time.time() - t0
    peak = max((m for _, m, _ in v.samples), default=base[0])

    # server's own view of the execution timing (node durations if present)
    # SaveVideo registers its mp4 under history `images` (animated list too),
    # older nodes may use `videos` — collect from either.
    node_times = {}
    if rec:
        for nid, o in (rec.get("outputs") or {}).items():
            files = [f for key in ("videos", "images") if isinstance(o.get(key), list)
                     for f in o[key]
                     if str(f.get("filename", "")).lower().endswith(".mp4")]
            if files:
                node_times[nid] = [str(Path(f.get("subfolder", "")) / f["filename"])
                                   for f in files]

    record = {
        "label": label, "workflow": str(wf_path), "seed": SEED,
        "prompt_id": prompt_id, "status": status.get("status_str"),
        "elapsed_s": round(elapsed, 1),
        "vram_idle_baseline_mib": base[0],
        "vram_peak_mib": peak,
        "vram_peak_over_baseline_mib": peak - base[0],
        "vram_samples": v.samples,
        "output_videos": node_times,
        "history_outputs": (rec or {}).get("outputs", {}),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"run_{label}.json").write_bytes(
        json.dumps(record, ensure_ascii=False, indent=1).encode("utf-8"))
    print(f"[p57] status={record['status']} elapsed={elapsed:.1f}s "
          f"peak={peak} MiB (over baseline {peak - base[0]} MiB)")

    # pull produced files into the project evidence folder
    runs = OUT / "runs"
    runs.mkdir(exist_ok=True)
    for nid, files in node_times.items():
        for fn in files:
            src = COMFY_OUTPUT / fn
            if src.exists():
                dst = runs / f"{label}{src.suffix}"
                shutil.copyfile(src, dst)
                print(f"[p57] copied {src} -> {dst}")
    if status.get("status_str") not in ("success", None):
        print(f"[p57] STATUS: {json.dumps(status, ensure_ascii=False)[:2000]}")
        sys.exit(2)


if __name__ == "__main__":
    main()
