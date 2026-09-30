"""Central path/config layer (P0.4).

Replaces the 200+ hardcoded `E:\\Minimax-H3` / `E:\\ComfyUI` / `C:\\Users\\...`
strings with one resolvable source. Precedence:

    1. environment variable (H3_ROOT / COMFY_ROOT / H3_PYTHON)
    2. config/local.yaml (gitignored, machine-specific)
    3. config/local.example.yaml (committed template)
    4. built-in default (the current machine layout)

Usage:
    from config.paths import ROOT, COMFY_ROOT, PYTHON, ffmpeg_bin
    # or
    from config import paths; paths.ROOT

Nothing here imports the rest of the project, so it is safe to import from
any script (including ffmpeg_env.py).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CONFIG_DIR = _HERE


def _from_yaml(path: Path) -> dict:
    """Minimal YAML subset loader (flat `key: value` pairs only).

    A full YAML parser is not worth a dependency here: local.yaml holds ~6
    scalar paths. Anything more complex belongs in code, not config.
    """
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line or ':' not in line:
            continue
        k, v = line.split(':', 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


_YAML = {**_from_yaml(_CONFIG_DIR / 'local.example.yaml'),
         **_from_yaml(_CONFIG_DIR / 'local.yaml')}


def _resolve(key: str, env: str, default: Path) -> Path:
    if os.environ.get(env):
        return Path(os.environ[env]).expanduser()
    if _YAML.get(key):
        return Path(_YAML[key]).expanduser()
    return default


#: Repository root (this project)
ROOT = _resolve('root', 'H3_ROOT', _HERE.parent)

#: ComfyUI checkout
COMFY_ROOT = _resolve('comfy_root', 'COMFY_ROOT', Path(r'E:\ComfyUI'))

#: Python interpreter that owns torch/kokoro/librosa (never use system python here)
PYTHON = _resolve('python', 'H3_PYTHON', COMFY_ROOT / 'venv' / 'Scripts' / 'python.exe')

#: Bundled ffmpeg (gitignored; may be absent on a fresh clone)
FFMPEG_DIR = _resolve('ffmpeg_dir', 'H3_FFMPEG_DIR',
                      ROOT / 'tools' / 'ffmpeg-7.1.1-full_build' / 'bin')

FFMPEG = FFMPEG_DIR / 'ffmpeg.exe'
FFPROBE = FFMPEG_DIR / 'ffprobe.exe'

COMFY_OUTPUT = COMFY_ROOT / 'output'
COMFY_INPUT = COMFY_ROOT / 'input'
COMFY_WORKFLOWS = COMFY_ROOT / 'user' / 'default' / 'workflows'
COMFY_SERVER = os.environ.get('H3_COMFY_SERVER', 'http://127.0.0.1:8188')

#: Production projects
PROJECTS_DIR = ROOT

#: Remotion workspace
STUDIO = ROOT / 'studio'
STUDIO_PUBLIC = STUDIO / 'public'
STUDIO_JOBS = STUDIO_PUBLIC / 'jobs'

#: Local-only content (never committed; backup at E:/H3_local_private/)
LOCAL_PRIVATE_BACKUP = _resolve('local_private_backup', 'H3_LOCAL_BACKUP',
                                Path(r'E:\H3_local_private'))


def ffmpeg_available() -> bool:
    return FFMPEG.exists()


def ensure_scripts_on_path() -> None:
    """Make sibling scripts importable (comfy_utils, ffmpeg_env, ...)."""
    for p in (ROOT, ROOT / 'ceo_mindread_ep01' / 'scripts', _CONFIG_DIR):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)


def describe() -> str:
    return '\n'.join([
        f'ROOT         = {ROOT}',
        f'COMFY_ROOT   = {COMFY_ROOT}',
        f'PYTHON       = {PYTHON} (exists={PYTHON.exists()})',
        f'FFMPEG       = {FFMPEG} (exists={ffmpeg_available()})',
        f'COMFY_SERVER = {COMFY_SERVER}',
        f'config source= {"local.yaml" if (_CONFIG_DIR / "local.yaml").exists() else "local.example.yaml / defaults"}',
    ])


if __name__ == '__main__':
    print(describe())
