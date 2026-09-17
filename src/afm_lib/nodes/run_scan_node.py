from pathlib import Path

from afm_lib.config import MODES, FRAME_TOL_M
from afm_lib.instrument.session import call
from afm_lib.schemas.scan_plan import validate_scan_plan, scan_plan_diff
from afm_lib.states.measurement_state import MeasurementState
from afm_lib.utils.geometry import is_close_xy

# ScanSettings field -> MCP argument name. Kept next to the tool it belongs to.
SCAN_ARGS = {"scan_size_m": "scan_size_m", "pixels": "n_points", "scan_rate_hz": "scan_rate_hz"}


async def run_scan_node(state: MeasurementState) -> MeasurementState:
    """Acquire one topography frame with the scan tool of the current mode.

    A frame offset in the recipe is a property of THIS measurement: if the
    plan's centre differs from the live centre, the frame is moved there,
    scanned, and moved back — always, even if the scan fails — so the next
    measurement and the next site start from the same centre."""
    pending = state["pending"]
    plan    = pending.get("params")
    live    = state.get("instrument_state")
    if plan is None or live is None:
        raise RuntimeError("run_scan requires pending['params'] and instrument_state")

    errors = validate_scan_plan(plan, live)
    if errors:
        raise RuntimeError("scan parameters rejected:\n  - " + "\n  - ".join(errors))

    ss, lss = plan.scan_settings, live.scan_settings
    tool = MODES[live.mode].scan_tool
    args = {arg: getattr(ss, f) for f, arg in SCAN_ARGS.items()}

    target = (ss.x_scan_center_m, ss.y_scan_center_m)
    home   = (lss.x_scan_center_m, lss.y_scan_center_m)
    moved  = not is_close_xy(target, home, FRAME_TOL_M)

    print(f"[run_scan] {tool} {ss.scan_size_m*1e6:.2f} um / {ss.pixels} px / {ss.scan_rate_hz} Hz"
          f"{' at offset' if moved else ''}; changes={scan_plan_diff(plan, live) or 'none'}")

    if moved:
        r = await call("set_scan_center", {"x_offset_m": target[0], "y_offset_m": target[1]})
        if r.get("warnings"):
            raise RuntimeError(f"frame refused: {r['warnings']}")
    try:
        data = await call(tool, args)
    finally:
        if moved:                                   # displacement is per measurement
            await call("set_scan_center", {"x_offset_m": home[0], "y_offset_m": home[1]})

    path = data.get("path")
    if not path:
        raise RuntimeError(f"scan returned no path: {data}")
    if not Path(path).exists():
        raise RuntimeError(f"scan file is not readable from here: {path!r}")

    achieved = {"x_scan_center_m": data["x_scan_center_m"], "y_scan_center_m": data["y_scan_center_m"],
                "scan_size_m": data["ScanSize"], "pixels": data["PointsLines"], "scan_rate_hz": data["ScanRate"]}
    print(f"[run_scan] done -> {path}")
    return {"pending": {**pending, "file_path": path, "achieved_frame": achieved}}