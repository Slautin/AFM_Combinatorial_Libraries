from afm_lib.instrument.session import call
from afm_lib.schemas.scanner_calibrations import to_scanner_calibration_state
from afm_lib.states.measurement_state import MeasurementState


async def calibrate_frame_node(state: MeasurementState) -> MeasurementState:
    """Measure the LVDT-to-scan-frame offset, once per session.

    SIDE EFFECT: moves the tip. calibrate_xy_frame clears any force marker and
    drives the tip to the scan-frame centre. This is the first tip motion of the
    run — everything before it is read-only."""
    data = await call("calibrate_xy_frame")
    cal = to_scanner_calibration_state(data)

    print(f"[calibrate] offset ({cal.x_scanner_offset_m*1e6:+.3f}, "
          f"{cal.y_scanner_offset_m*1e6:+.3f}) um | "
          f"sens {cal.x_lvdt_sens_m_per_v:.4e} / {cal.y_lvdt_sens_m_per_v:.4e} m/V")

    return {"scanner_calibrations": cal}