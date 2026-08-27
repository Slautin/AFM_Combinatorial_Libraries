from afm_lib.config import STAGE_TOL_M
from afm_lib.instrument.session import call
from afm_lib.nodes.sync_status_node import sync_status_node
from afm_lib.states.measurement_state import MeasurementState
from afm_lib.utils.geometry import is_close_xy


async def ensure_stage_node(state: MeasurementState) -> MeasurementState:
    """Put the stage where the pending measurement asks for it, if it is not
    already there. Idempotent: a pending that names the current site is a no-op,
    which is what lets this sit inside the per-point loop and still fire once
    per site.

    SIDE EFFECT when it moves: withdraw -> stage move -> re-approach.
    Workflow-agnostic — reads `pending`, never `sites`."""
    pending = state["pending"]
    target = pending.get("stage_xy_m")
    if target is None:
        return {}

    live = state["instrument_state"].stage_position
    here = (live.x_stage_m, live.y_stage_m)
    if is_close_xy(target, here, STAGE_TOL_M):
        return {}

    print(f"[ensure_stage] ({here[0]*1e3:+.3f}, {here[1]*1e3:+.3f}) -> "
          f"({target[0]*1e3:+.3f}, {target[1]*1e3:+.3f}) mm")

    data = await call("pfm_move_stage", {"x_stage_m": float(target[0]),
                                         "y_stage_m": float(target[1]),
                                         "approach_after": True})

    # if not data.get("feedback_on"):
    #     raise RuntimeError(
    #         f"stage moved to ({data['x_stage_m']:.6g}, {data['y_stage_m']:.6g}) but the "
    #         f"approach did not establish contact — {data.get('message')}")

    if not data.get("feedback_on"):
        print(f"[ensure_stage] WARNING: approach did not report contact — "
              f"{data.get('message')}")

    print(f"[ensure_stage] {data['message']}")
    return await sync_status_node(state)