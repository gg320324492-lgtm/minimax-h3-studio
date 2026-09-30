"""ShotSpec schema (P2) — the structured description of one atomic shot.

A ShotSpec is what a director (human or agent) authors. It never contains
prompt prose: the prompt is *derived* from the spec by prompt_compiler.py, so
two shots with the same spec always compile to the same prompt, and prompt
tuning never means editing a string blob in a Python file.

Why this matters (P0 review R1 class of risk): EP01's prompts used to live as
literals inside gen_keyframes_v3.py. They are now data (00_project/h3_generation.json,
gitignored). A compiler that reads and writes that data keeps production logic
in git while the IP stays local.

Atomic-shot rule (master plan §P2): ONE H3 generation == ONE atomic shot.
Multi-beat descriptions ("two-shot: wide then close-up") belong in the edit,
not in a generation. `validate_atomic()` enforces it.

Schema doc: docs/UPGRADE_MASTER_PLAN.md (P2)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any, Literal

VERSION = 1

# Patterns that indicate a generation was asked to contain more than one shot.
# H3 (like every video model) handles multi-beat prompts far worse than it
# handles one well-described atomic shot, and the editor cannot re-time what it
# cannot re-take.
#
# Tuned against EP01's real prompts (2026-09-30). A bare "then" is NOT a signal:
# four prompts contained "then" inside a single continuous performance
# ("hands over the report, then his eyes shift") and those are perfectly atomic.
# Only explicit editorial language counts.
MULTI_BEAT_PATTERNS = [
    r'\bcut\s+to\b',
    r'\bthen\s+(?:cut|we\s+(?:see|watch)|the\s+(?:camera|shot|scene)\b)',
    r'\bfollowed\s+by\s+(?:a|an|the)?\s*(?:shot|scene|cut|close-?up|wide|angle)\b',
    r'\b\d\s*-\s*shot\b',
    r'\b(?:two|three|2|3)[\s-]*shot\s*[:：]',
    r'\bmulti[\s-]*shot\b',
    r'\bthe\s+camera\s+cuts?\b',
    r'镜头切',
    r'切到',
    r'然后画面切',
]
MULTI_BEAT_RE = re.compile('|'.join(MULTI_BEAT_PATTERNS), re.IGNORECASE)


@dataclass
class ShotSpec:
    """One atomic shot. `id` matches the take-generation id (S01, S03A, ...)."""

    id: str
    purpose: str = ''                 # establishing | insert | reaction | b-roll | transition
    duration_target_s: float = 0.0    # what the edit wants (may be < generation)
    generation_frames: int = 0        # H3 frame count; must satisfy 17k+5
    seed_base: int = 0
    takes: int = 1                    # how many candidates to generate (P1 ranks them)

    subject: str = ''                 # who/what is on screen
    action: str = ''                  # what they do — ONE beat
    environment: str = ''             # where
    camera: str = ''                  # shot size + movement, e.g. "medium close-up, slow push in"
    lighting: str = ''
    style: str = ''
    references: list[str] = field(default_factory=list)   # <Picture N> tokens in order
    negative_constraints: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)  # escape hatch, stays structured

    def validate(self) -> list[str]:
        """Returns a list of problems; empty means valid."""
        problems: list[str] = []
        if not re.fullmatch(r'S\d+[A-Z]?', self.id or ''):
            problems.append(f'{self.id}: id must look like S01 / S03A')
        if self.generation_frames and (self.generation_frames - 5) % 17 != 0:
            problems.append(
                f'{self.id}: generation_frames={self.generation_frames} violates the '
                f'H3 17k+5 grid (5, 22, 39, 56, ..., 124, 141, ..., 226)')
        if self.takes < 1:
            problems.append(f'{self.id}: takes must be >= 1')
        if self.duration_target_s and self.generation_frames and \
                self.duration_target_s > self.generation_frames / 24.0 + 1e-6:
            problems.append(
                f'{self.id}: duration_target_s={self.duration_target_s} exceeds the '
                f'generated length ({self.generation_frames / 24.0:.2f}s)')
        beats = validate_atomic(f'{self.action} {self.camera} {self.extra.get("beats", "")}')
        problems += [f'{self.id}: {b}' for b in beats]
        return problems


def validate_atomic(text: str) -> list[str]:
    """One generation must describe ONE shot."""
    if not text:
        return []
    hits = sorted({m.group(0).lower() for m in MULTI_BEAT_RE.finditer(text)})
    if hits:
        return [
            'non-atomic description (multi-beat prompt detected: '
            f'{", ".join(hits)}). Split into separate ShotSpecs and cut in the edit — '
            'the editor can re-time and re-take a shot, the generator cannot.'
        ]
    return []


def to_dict(s: ShotSpec) -> dict:
    return asdict(s)


def from_dict(d: dict) -> ShotSpec:
    known = {f for f in ShotSpec.__dataclass_fields__}  # type: ignore[attr-defined]
    kwargs = {k: v for k, v in d.items() if k in known and k != 'extra'}
    extra = {k: v for k, v in d.items() if k not in known}
    spec = ShotSpec(**kwargs)
    if extra:
        spec.extra.update(extra)
    return spec
