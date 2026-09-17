from math import hypot

from afm_lib.config import TIP_TOL_M
from afm_lib.instrument.session import call
from afm_lib.nodes.sync_status_node import sync_status_node
from afm_lib.states.measurement_state import MeasurementState
from afm_lib.utils.geometry import is_close_xy


async def ensure_tip_node(state: MeasurementState) -> MeasurementState:
    """Put the tip where the pending measurement asks for it, in absolute
    scan-frame coordinates. Idempotent, same as ensure_stage.

    SIDE EFFECT when it moves: lateral tip motion in contact."""
    pending = state["pending"]
    target = pending.get("tip_xy_m")
    if target is None:
        return {}

    probe = state["instrument_state"].probe_position
    if probe is None:
        raise RuntimeError("ensure_tip needs a probe position — run calibrate_frame "
                           "before any tip placement")

    here = (probe.x_m, probe.y_m)
    if is_close_xy(target, here, TIP_TOL_M):
        return {}

    print(f"[ensure_tip] ({here[0]*1e6:+.4f}, {here[1]*1e6:+.4f}) -> "
          f"({target[0]*1e6:+.4f}, {target[1]*1e6:+.4f}) um")

    data = await call("move_tip", {"x_m": float(target[0]), "y_m": float(target[1])})

    err = hypot(data.get("x_error_m") or 0.0, data.get("y_error_m") or 0.0)
    if err > TIP_TOL_M:
        raise RuntimeError(f"move_tip landed {err*1e9:.1f} nm from the target — "
                           f"more than TIP_TOL_M ({TIP_TOL_M*1e9:.1f} nm)")

    print(f"[ensure_tip] achieved ({data['x_m']*1e6:+.4f}, {data['y_m']*1e6:+.4f}) um, "
          f"error {err*1e9:.1f} nm")
    return await sync_status_node(state)