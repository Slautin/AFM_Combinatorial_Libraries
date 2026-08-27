# src/afm_lib/nodes/sync_status_node.py
from afm_lib.instrument.session import call
from afm_lib.schemas.instrument import to_instrument_state
from afm_lib.schemas.scanner_calibrations import calibration_is_fresh
from afm_lib.states.measurement_state import MeasurementState


async def sync_status_node(state: MeasurementState) -> MeasurementState:
    """Refresh InstrumentState. Runs once at init and after every acquisition —
    the post-acquisition call is what gives each ExperimentalRecord a system's truthful
    snapshot (probe position included, which is the loop's actual location)."""
    cal = state.get("scanner_calibrations")
    if cal is None:
        raise RuntimeError(
            "sync_status requires a scanner calibration — probe position cannot be "
            "expressed in frame coordinates without it (to_instrument_state would "
            "build ProbePosition(x_m=None) and fail pydantic validation).")

    raw = await call("pfm_get_experiment_status")

    if not calibration_is_fresh(cal, raw):
        raise RuntimeError(
            "Scanner calibration is STALE — LVDT sensitivity changed since calibration "
            f"(cal {cal.x_lvdt_sens_m_per_v:.6e}/{cal.y_lvdt_sens_m_per_v:.6e}, "
            f"live {raw['x_lvdt_sens_m_per_v']:.6e}/{raw['y_lvdt_sens_m_per_v']:.6e}). "
            "Re-calibrate: any direct move_tip would land silently wrong.")

    return {"instrument_state": to_instrument_state(raw, scanner_calibrations=cal)}