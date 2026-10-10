"""Director: the generating side of the pipeline (P12.1).

Only the depth cue is generated. The other nine `StyleBible` keys are refused
with a measured reason each -- see `style_bible.REFUSED` and
docs/P12_1_GENERATION.md. Nothing in this package imports from `tests/`; the
guard in `tests/test_p12_1_depth_cue_generation.py` is what checks that every
key emitted here has a consumer, so production code does not have to trust a
list it wrote itself.
"""

from .depth_plan import MEASURED_RAMPS, DepthPlan, plan_depth, ramp_ceiling
from .style_bible import (
    EMITS,
    REFUSED,
    STYLE_BIBLE_KEYS,
    GeneratedGraph,
    generate_graph,
)

__all__ = [
    'DepthPlan',
    'EMITS',
    'GeneratedGraph',
    'MEASURED_RAMPS',
    'REFUSED',
    'STYLE_BIBLE_KEYS',
    'generate_graph',
    'plan_depth',
    'ramp_ceiling',
]