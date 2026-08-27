from pathlib import Path

from afm_lib.instrument.session import call
from afm_lib.schemas.loop_plan import loop_plan_diff, validate_loop_plan
from afm_lib.states.measurement_state import MeasurementState

# LoopSettings field -> MCP argument name. Kept next to the tool it belongs to.
LOOP_ARGS = {"v_dc_max_v":       "v_dc_max",
             "frequency_hz":     "loop_frequency",
             "var0_phase":       "var0_loop_phase",
             "var1_pulsetime_s": "var1_pulsetime_s",
             "n_cycles":         "n_cycles"}

TUNE_PROBE = True          # retune the DART resonance before every loop


async def run_loop_node(state: MeasurementState) -> MeasurementState:
    """Measure one hysteresis loop at the current tip position.
    The location is never sent — ensure_stage and ensure_tip put the probe there."""
    pending = state["pending"]
    plan    = pending.get("params")
    live    = state.get("instrument_state")
    if plan is None or live is None:
        raise RuntimeError("run_loop requires pending['params'] and instrument_state")

    errors = validate_loop_plan(plan, live)
    if errors:
        raise RuntimeError("loop parameters rejected:\n  - " + "\n  - ".join(errors))

    ls   = plan.loop_settings
    args = {arg: getattr(ls, f) for f, arg in LOOP_ARGS.items()}
    secs = ls.n_cycles / ls.frequency_hz if ls.frequency_hz else float("nan")

    print(f"[run_loop] v_dc_max {ls.v_dc_max_v:.2f} V, {ls.frequency_hz:.3f} Hz, "
          f"{ls.n_cycles} cycles, pulse {ls.var1_pulsetime_s*1e3:.1f} ms "
          f"(~{secs:.0f} s); changes={loop_plan_diff(plan, live) or 'none'}")

    data = await call("pfm_measure_hysteresis_loop", {**args, "tune_probe": TUNE_PROBE})

    path = data.get("path")
    if not path:
        raise RuntimeError(f"loop returned no path: {data}")
    if not Path(path).exists():
        raise RuntimeError(
            f"loop file is not readable from here: {path!r} — this assumes the "
            f"notebook and the instrument share a filesystem")

    print(f"[run_loop] done -> {path}")
    return {"pending": {**pending, "file_path": path}}