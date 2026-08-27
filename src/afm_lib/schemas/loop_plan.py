from math import isclose

from pydantic import BaseModel, Field
from typing import Literal

from afm_lib.config import LOOP_BOUNDS
from afm_lib.schemas.instrument import InstrumentState, LoopSettings

_FIELDS = ("v_dc_max_v", "frequency_hz", "var0_phase", "var1_pulsetime_s", "n_cycles")

class LoopPlan(BaseModel, frozen=True):
    """Target switching waveform for the next hysteresis loop. Reuses the instrument
    read-model: the diff against the live state becomes the tool call.
    The measurement LOCATION is not here — it is picked deterministically."""

    diagnosis: str = Field(
        description="1-3 sentences: what the previous loops on this scan showed about "
                    "the waveform — saturation, noise, switching — not about the sample")
    loop_settings: LoopSettings = Field(
        description="Target waveform. Restate every field; copy unchanged what you do "
                    "not intend to move")
    reasoning: str = Field(
        description="2-3 sentences: why each changed value follows from the diagnosis")

def loop_plan_diff(plan: LoopPlan, live: InstrumentState,
                   rel_tol: float = 1e-6) -> dict[str, float]:
    """Waveform fields that differ from the live state, by schema field name."""
    ls, lls = plan.loop_settings, live.loop_settings
    return {f: getattr(ls, f) for f in _FIELDS
            if not isclose(getattr(ls, f), getattr(lls, f), rel_tol=rel_tol,
                           abs_tol=1e-12)}

def validate_loop_plan(plan: LoopPlan, live: InstrumentState,
                       rel_tol: float = 1e-6) -> list[str]:
    """Deterministic gate before anything reaches the instrument.
    Bounds constrain what the plan CHANGES; a value already set is admissible."""
    errors: list[str] = []
    changed = loop_plan_diff(plan, live, rel_tol)

    for f, v in changed.items():
        lo, hi = LOOP_BOUNDS[f]
        if not (lo <= v <= hi):
            errors.append(f"{f}={v:.6g} outside [{lo:.6g}, {hi:.6g}]")

    return errors