"""P58 runner: submit a generation job (UI workflow or API prompt file),
measure end-to-end time and VRAM peak.

Same harness p57_runner.py used (bench.api + a 1 Hz nvidia-smi sampler in a
background thread, idle baseline recorded before submit), with two additions:
  * the input may be an API-format prompt file (out/p58/api_*.json) as well
    as a UI workflow (converted through p56_runner.to_prompt, the path P55/P56
    proved against the live 0.43.2 server);
  * outputs move to E:\\Minimax-H3\\out\\p58\\runs\\<label>.mp4 and the record
    to E:\\Minimax-H3\\out\\p58\\run_<label>.json.

Usage: python p58_runner.py <file.json> <label>
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

SEED = 1086599926715797  # template's own RandomNoise value, pinned for every run
OUT = Path(r"E:\Minimax-H3\out\p58")
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


def load_prompt(path: Path):
    raw = json.loads(path.read_bytes().decode("utf-8"))
    if "nodes" in raw:  # UI workflow
        prompt = to_prompt(raw, SEED)
    else:               # API prompt file (e2e graphs) — seed already pinned
        prompt = raw
    seeds = [(k, v["inputs"].get("noise_seed")) for k, v in prompt.items()
             if v["class_type"] == "RandomNoise"]
    return prompt, seeds


def main():
    src = Path(sys.argv[1])
    label = sys.argv[2]
    prompt, seeds = load_prompt(src)
    print(f"[p58] label={label} nodes={len(prompt)} pinned_seeds={seeds}")

    base = Vram()._query()
    print(f"[p58] idle baseline: {base[0]} MiB used, {base[1]}% util")

    t0 = time.time()
    result = api("/prompt", "POST", {"prompt": prompt})
    prompt_id = result.get("prompt_id")
    print(f"[p58] prompt_id={prompt_id}")

    status, _, rec = "running", None, None
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

    moved = []
    runs = OUT / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    for f in produced:
        srcf = COMFY_OUTPUT / f.get("subfolder", "") / f["filename"]
        if srcf.exists() and srcf.suffix.lower() == ".mp4":
            dst = runs / f"{label}.mp4"
            shutil.copy2(srcf, dst)
            moved.append(str(dst))

    record = {"label": label, "source": str(src), "seed": SEED,
              "prompt_id": prompt_id, "status": status,
              "elapsed_s": round(elapsed, 1),
              "vram_idle_baseline_mib": base[0], "vram_peak_mib": peak,
              "vram_peak_over_baseline_mib": peak - base[0],
              "vram_samples": v.samples, "produced": produced, "moved": moved}
    (OUT / f"run_{label}.json").write_bytes(
        json.dumps(record, indent=1, ensure_ascii=False).encode("utf-8"))
    ok = isinstance(status, dict) and status.get("completed")
    print(f"[p58] status={status} elapsed={elapsed:.1f}s peak={peak} MiB "
          f"(over baseline {peak - base[0]} MiB) moved={moved}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
