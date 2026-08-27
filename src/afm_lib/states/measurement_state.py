from typing_extensions import TypedDict, NotRequired
from typing import Literal

from afm_lib.schemas.instrument import InstrumentState
from afm_lib.schemas.scanner_calibrations import ScannerCalibrations
from afm_lib.schemas.loop_plan import LoopPlan
from afm_lib.states.analysis_state import AnalysisState


class SessionInfo(TypedDict):
    """Session-scoped facts read once at preflight, before the first tip motion.
    Internal — never rendered into LLM context."""
    run_dir: str
    started_ts: float                  # cutoff for "which .ibw file is new"
    instrument_directory: str          # where the instrument writes .ibw files


class PendingMeasurement(TypedDict):
    """The measurement being ordered/executed — the ONLY interface between a
    workflow's planner and the shared instrument nodes.

    A planner fills whichever positioning levels its experiment controls; the
    ensure_* nodes treat an absent level as "leave it alone". Grid search sets
    stage + tip, a loop map sets tip only, a frame survey sets frame only."""
    kind: Literal["scan", "loop"]
    params: NotRequired[LoopPlan]

    stage_xy_m: NotRequired[tuple[float, float]]   # which site / composition
    frame_xy_m: NotRequired[tuple[float, float]]   # scan-frame centre
    tip_xy_m:   NotRequired[tuple[float, float]]   # tip inside the frame

    labels: NotRequired[dict]        # provenance only — site_index, point_index,
                                     # decision_index, pixel_yx, site label.
                                     # Never read to decide what to do.
    file_path: NotRequired[str]      # set by the run node


class ExperimentalRecord(AnalysisState):
    """One completed measurement plus its analysis. Append-only.
    `instrument_params` is the acquisition-time snapshot — it already carries the
    ACHIEVED stage and probe position, so no coordinates are duplicated here."""
    instrument_params: InstrumentState
    requested_params: NotRequired[LoopPlan]
    labels: NotRequired[dict]              # type: ignore     # copied from the pending that ordered it
    pixel_yx: NotRequired[tuple[int, int]]      # type: ignore # type ignore  loop-map workflow only


class MeasurementState(TypedDict):
    """What every instrument workflow carries, whatever drives it.
    Nodes typed on this are workflow-agnostic and never change."""
    session_info: SessionInfo
    instrument_state: InstrumentState
    scanner_calibrations: ScannerCalibrations
    experimental_records: NotRequired[list[ExperimentalRecord]]
    pending: NotRequired[PendingMeasurement | None]