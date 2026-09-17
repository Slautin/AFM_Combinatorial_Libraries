from math import isclose

from pydantic import BaseModel, Field

from afm_lib.config import SCAN_BOUNDS, SCAN_SIZES_PX, SCANNER_CENTER_LIMIT_M
from afm_lib.schemas.instrument import InstrumentState, ScanSettings

_FIELDS = ("x_scan_center_m", "y_scan_center_m", "scan_size_m", "pixels", "scan_rate_hz")


class ScanPlan(BaseModel, frozen=True):
    """Target frame for the next scan. Same idea as LoopPlan: the diff against
    the live state becomes the tool calls (centre -> set_scan_center,
    size/pixels/rate -> the scan tool). Centre here is ABSOLUTE."""
    diagnosis: str = Field(description="1-3 sentences on acquisition quality, not the sample")
    scan_settings: ScanSettings = Field(description="Target frame; restate every field")
    reasoning: str = Field(description="Why each changed value follows from the diagnosis")


def scan_plan_diff(plan: ScanPlan, live: InstrumentState,
                   rel_tol: float = 1e-6) -> dict[str, float | int]:
    """Frame fields that differ from the live state, by schema field name."""
    ss, lss = plan.scan_settings, live.scan_settings
    return {f: getattr(ss, f) for f in _FIELDS
            if not isclose(getattr(ss, f), getattr(lss, f), rel_tol=rel_tol, abs_tol=1e-12)}


def validate_scan_plan(plan: ScanPlan, live: InstrumentState,
                       rel_tol: float = 1e-6) -> list[str]:
    """Deterministic gate before anything reaches the instrument.
    Bounds constrain what the plan CHANGES; the scanner-range check is absolute."""
    errors: list[str] = []
    ss = plan.scan_settings
    changed = scan_plan_diff(plan, live, rel_tol)

    for f, (lo, hi) in SCAN_BOUNDS.items():
        if f in changed and not (lo <= changed[f] <= hi):
            errors.append(f"{f}={changed[f]:.6g} outside [{lo:.6g}, {hi:.6g}]")

    if "pixels" in changed and ss.pixels not in SCAN_SIZES_PX:
        errors.append(f"pixels must be one of {SCAN_SIZES_PX}, got {ss.pixels}")

    half = ss.scan_size_m / 2
    for axis, c in (("x", ss.x_scan_center_m), ("y", ss.y_scan_center_m)):
        if abs(c) + half >= SCANNER_CENTER_LIMIT_M:
            errors.append(f"frame leaves the {axis} scanner range: |{c:.3g}| + {half:.3g} m")

    return errors