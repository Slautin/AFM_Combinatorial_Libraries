from afm_lib.schemas.loop_plan import LoopPlan
from afm_lib.states.lib_experiment_state import LibExperimentState
from afm_lib.schemas.recipe import site_program


async def next_measurement_node(state: LibExperimentState) -> LibExperimentState:
    """Emit the next measurement for the current site, or None when its program
    is complete. The only node in the site subgraph that reads the recipe.

    The point cursor is DERIVED: every completed measurement leaves a record, so
    `done` is a count, not stored state. A resumed run recovers it for free."""
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

    print(f"[next_measurement] {site.get('label', i)} "
          f"{done + 1}/{len(program)}: {m.kind} at "
          f"({m.dx_m * 1e6:+.3f}, {m.dy_m * 1e6:+.3f}) um from centre "
          f"-> ({x_m * 1e6:+.3f}, {y_m * 1e6:+.3f}) um | "
          f"{m.loop_settings.v_dc_max_v:.1f} V, {m.loop_settings.n_cycles} cycles")

    return {"pending": {
        "kind":       m.kind,
        "stage_xy_m": (site["x_stage_m"], site["y_stage_m"]),
        "tip_xy_m":   (x_m, y_m),
        "params":     LoopPlan(
            diagnosis=f"(deterministic) recipe {state['recipe'].name}, "
                      f"step {m.step_index}, point {m.point_index}",
            loop_settings=m.loop_settings,
            reasoning="Fixed grid recipe; waveform is not adapted to prior loops."),
        "labels": {"site_index":  i,
                   "site_label":  site.get("label"),
                   "step_index":  m.step_index,
                   "point_index": m.point_index},
    }}


def route_after_next_measurement(state: LibExperimentState) -> str:
    return "measure" if state.get("pending") else "site_done"