from afm_lib.schemas.loop_plan import LoopPlan
from afm_lib.schemas.scan_plan import ScanPlan
from afm_lib.schemas.instrument import ScanSettings
from afm_lib.states.lib_experiment_state import LibExperimentState
from afm_lib.schemas.recipe import site_program


async def next_measurement_node(state: LibExperimentState) -> LibExperimentState:
    """Emit the next measurement for the current site, or None when its program
    is complete. The only node in the site subgraph that reads the recipe.

    The point cursor is DERIVED: every completed measurement leaves a record, so
    `done` is a count, not stored state. A resumed run recovers it for free.

     Offsets in the recipe (loop points, frame centre) are relative to the
    CURRENT frame centre; they are made absolute here."""

    i    = state["site_index"]
    site = state["sites"][i]
    live = state.get("instrument_state")
    if live is None:
        raise RuntimeError("next_measurement requires instrument_state — "
                           "run sync_status first")

    program = site_program(state["recipe"])
    done = sum(1 for r in state.get("experimental_records", [])
               if r.get("labels", {}).get("site_index") == i)

    if done >= len(program):
        print(f"[next_measurement] site {site.get('label', i)} complete "
              f"({done}/{len(program)})")
        return {"pending": None}

    m  = program[done]
    ss = live.scan_settings
    x_m = ss.x_scan_center_m + m.dx_m
    y_m = ss.y_scan_center_m + m.dy_m
    label = site.get("label", i)
    why   = f"(deterministic) recipe {state['recipe'].name}, step {m.step_index}, point {m.point_index}"

    pending = {
        "kind":       m.kind,
        "stage_xy_m": (site["x_stage_m"], site["y_stage_m"]),
        "labels": {"site_index": i, "site_label": site.get("label"),
                   "step_index": m.step_index, "point_index": m.point_index},
    }


    if m.kind == "loop":
        # tip goes to the point; the frame is not touched
        pending["tip_xy_m"] = (x_m, y_m)
        pending["params"] = LoopPlan(
            diagnosis=why, loop_settings=m.loop_settings,
            reasoning="Fixed grid recipe; waveform is not adapted to prior loops.")
        print(f"[next_measurement] {label} {done + 1}/{len(program)}: loop at "
              f"({x_m*1e6:+.3f}, {y_m*1e6:+.3f}) um | "
              f"{m.loop_settings.v_dc_max_v:.1f} V, {m.loop_settings.n_cycles} cycles")
    else:
        # frame centre becomes absolute; run_scan moves the frame there and back
        r = m.scan_settings
        pending["params"] = ScanPlan(
            diagnosis=why,
            scan_settings=ScanSettings(x_scan_center_m=x_m, y_scan_center_m=y_m,
                                       scan_size_m=r.scan_size_m, pixels=r.pixels,
                                       scan_rate_hz=r.scan_rate_hz),
            reasoning="Fixed grid recipe; frame is not adapted to prior scans.")
        print(f"[next_measurement] {label} {done + 1}/{len(program)}: scan "
              f"{r.scan_size_m*1e6:.2f} um / {r.pixels} px / {r.scan_rate_hz} Hz at "
              f"({x_m*1e6:+.3f}, {y_m*1e6:+.3f}) um")

    return {"pending": pending}


def route_after_next_measurement(state: LibExperimentState) -> str:
    return "measure" if state.get("pending") else "site_done"

def route_by_kind(state: LibExperimentState) -> str:
    """Pick the run node for the pending measurement."""
    return state["pending"]["kind"]           # "loop" | "scan"