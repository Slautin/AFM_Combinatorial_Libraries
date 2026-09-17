# src/spm_agent/nodes/preflight_node.py
import json
import time

from afm_lib.config import run_dir
from afm_lib.instrument.session import call
from afm_lib.states.measurement_state import MeasurementState 
from afm_lib.states.lib_experiment_state import LibExperimentState

def _fmt(v, scale=1.0, unit="", fmt=".1f"):
    """Status fields are None when unreadable — never let a print kill the run."""
    return "n/a" if v is None else f"{v*scale:{fmt}}{unit}"

async def preflight_node(state: LibExperimentState) -> LibExperimentState:
    """Read-only readiness check. Runs BEFORE the first tip motion (calibration).
    Fails the run rather than driving an instrument in an unknown state."""
    raw = await call("get_experiment_status")

    want = state["recipe"].mode
    if raw.get("mode") != want:
        raise RuntimeError(f"recipe needs mode {want!r} but the instrument has {raw.get('mode')!r} "
                           "loaded — set it by hand (withdraw, set_imaging_mode, tune, setpoint, engage) "
                           "and start again")

    missing = [k for k in ("stage_x_m", "stage_y_m") if raw.get(k) is None]
    if missing:
        raise RuntimeError(
            f"stage position unreadable ({', '.join(missing)}) — a stage workflow "
            f"cannot run without it. Verify the StagePositionX/Y keys in "
            f"_STATUS_SPEC on this instrument. Status warnings: {raw.get('warnings')}")

    session = {
        "run_dir":              str(run_dir()),
        "started_ts":           time.time(),
        "instrument_directory": raw["directory"],       # where .ibw files land
    }

    (run_dir() / "session.json").write_text(
        json.dumps({**session, "status_at_start": raw}, indent=2), encoding="utf-8"
        )

    print(f"[preflight] stage ({raw['stage_x_m']*1e3:+.3f}, {raw['stage_y_m']*1e3:+.3f}) mm | "
          f"dir {raw.get('directory')!r} | feedback {raw.get('feedback_on')} | "
          f"frame {_fmt(raw.get('scan_size_m'), 1e6, ' um')} @ {raw.get('n_points')} px | "
          f"f_DART {_fmt(raw.get('f_dart_hz'), 1e-3, ' kHz')} | "
          f"V_ac {raw.get('v_ac_v')} V")
    if raw.get("warnings"):
        print(f"[preflight] WARNINGS: {'; '.join(raw['warnings'])}")
        
    return {"session_info": session}      # type: ignore