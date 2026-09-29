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
                        fallback_newest: bool = True) -> Path | None:
    """The file this prompt produced, or None.

    Only if the history carries no usable entry do we fall back to the old
    newest-mtime guess, and the caller is expected to warn when that happens.
    """
    for p in outputs_from_history(rec, output_dir):
        if p.exists():
            return p
    if not fallback_newest:
        return None
    base = output_dir or COMFY_OUTPUT
    files = list(base.glob('MiniMax_H3*.mp4')) or list(base.rglob('*.mp4'))
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]
