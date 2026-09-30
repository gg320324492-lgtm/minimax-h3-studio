"""Shared ComfyUI helpers for the EP01 scripts.

Why this exists
---------------
`find_latest_video()` was copy-pasted into five scripts (gen_keyframes,
gen_office, gen_references, gen_reference_sheets, _archive/gen_keyframes). It
picks the newest .mp4 in ComfyUI/output by modification time, which silently
returns the WRONG clip when any other job writes to that directory -- a
concurrent prompt, a manual test, a rerun in another window. No error, just the
wrong shot in the shot folder.

ComfyUI's /history/<prompt_id> already carries the exact filename each SaveVideo
node wrote, so there is no reason to guess. Use `outputs_from_history()`.
"""

from __future__ import annotations

# --- ffmpeg binary resolution -------------------------------------------------
# PATH `ffmpeg` on this machine is GNU Octave's bundled 4.2.11, not a normal
# install, so every encode silently depended on a third-party app. Resolve via
# ffmpeg_env (repo-bundled 7.1.1 by default; MINIMAX_FFMPEG_LEGACY=1 to pin the
# legacy PATH binary for byte-comparable re-runs).
# NOTE: this block must stay AFTER `from __future__ import annotations`.
import sys as _sys, os as _os  # noqa: E402
if r'E:\Minimax-H3' not in _sys.path:
    _sys.path.insert(0, r'E:\Minimax-H3')
from ffmpeg_env import prepend_to_path as _prepend_ffmpeg  # noqa: E402
_prepend_ffmpeg()
# -----------------------------------------------------------------------------

from pathlib import Path

COMFY_OUTPUT = Path(r'E:\ComfyUI\output')


def outputs_from_history(rec, output_dir: Path | None = None) -> list[Path]:
    """Every file the given history record says it saved, as absolute paths.

    rec is the dict from GET /history/<prompt_id>, i.e. h[prompt_id].
    """
    base = output_dir or COMFY_OUTPUT
    found: list[Path] = []
    for node_out in (rec.get('outputs') or {}).values():
        if not isinstance(node_out, dict):
            continue
        for key in ('images', 'videos', 'gifs', 'audio'):
            for item in (node_out.get(key) or []):
                if isinstance(item, dict) and item.get('filename'):
                    sub = item.get('subfolder') or ''
                    found.append(base / sub / item['filename'])
    return found


def resolve_output_file(rec, output_dir: Path | None = None,
                        fallback_newest: bool = False) -> Path | None:
    """The file this prompt produced, or None.

    PRODUCTION DEFAULT IS STRICT: if the history record carries no usable
    entry, this returns None and the caller must fail. Guessing "newest mp4"
    is only safe when you are the only job writing to that output dir.

    Rationale (P0 audit R3): the original default was True, and all three
    callers relied on it silently — which is exactly the bug this module was
    created to eliminate (wrong take silently shipped into the edit).

    Opt in explicitly for interactive/experimental use:
        resolve_output_file(rec, fallback_newest=True)   # warns loudly
    """
    for p in outputs_from_history(rec, output_dir):
        if p.exists():
            return p
    if not fallback_newest:
        return None
    import sys as _sys
    print('[WARN] history has no output entry — falling back to newest-mtime '
          'guess (UNSAFE in concurrent production; wrong take may be shipped)',
          file=_sys.stderr, flush=True)
    base = output_dir or COMFY_OUTPUT
    files = list(base.glob('MiniMax_H3*.mp4')) or list(base.rglob('*.mp4'))
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


# --- P0.3: bounded polling (R3: ComfyUI hang used to block forever) ---

DEFAULT_DEADLINE_S = 3600


def wait_for_prompt(api, pid, deadline_s: int = DEFAULT_DEADLINE_S,
                    log=print, sleep_s: float = 5.0):
    """Poll /history/<pid> until the job completes, fails, or the deadline hits.

    Returns the history record on success, None on job failure or timeout.
    Replaces the bare `while True: ... time.sleep(5)` loops, which hung
    forever whenever the ComfyUI queue stalled or the service restarted.
    The deadline pattern already existed in experiments/bench.py (1800s) and
    flashvsr_upscale.py (7200s) — production just never adopted it.
    """
    import time as _time
    t0 = _time.time()
    last_log = 0.0
    while True:
        try:
            h = api(f'/history/{pid}')
        except Exception as e:  # service restart / transient network
            if _time.time() - t0 > deadline_s:
                log(f'TIMEOUT after {deadline_s}s (last error: {e})')
                return None
            _time.sleep(sleep_s)
            continue
        if pid in h:
            rec = h[pid]
            if rec.get('status', {}).get('completed') or 'outputs' in rec:
                log(f'DONE in {_time.time() - t0:.1f}s')
                return rec
            st = rec.get('status', {}).get('status_str')
            if st in ('error', 'failed'):
                log(f'FAILED: {st}')
                return None
        now = _time.time()
        if now - t0 > deadline_s:
            log(f'TIMEOUT after {deadline_s}s waiting for prompt {pid}')
            return None
        if now - last_log > 60:
            log(f'  ...waiting {int(now - t0)}s')
            last_log = now
        _time.sleep(sleep_s)
