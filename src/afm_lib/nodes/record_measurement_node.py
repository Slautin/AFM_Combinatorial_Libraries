from afm_lib.config import records_dir
from afm_lib.graphs.loop_analysis_graph import build_loop_analysis_graph
from afm_lib.states.analysis_state import AnalysisState
from afm_lib.states.lib_experiment_state import LibExperimentState
from afm_lib.utils.io_utils import save_json

_analysis_graph = build_loop_analysis_graph()


async def record_measurement_node(state: LibExperimentState) -> LibExperimentState:
    """Analyse the just-acquired file and pack it into an ExperimentalRecord.
    Consumes `pending`: verifies intent vs outcome, attributes the record, clears it."""
    recs    = state.get("experimental_records", [])
    pending = state["pending"]

    labels = pending.get("labels") or {}
    if "site_index" not in labels:
        raise RuntimeError("record has no labels['site_index'] — the point cursor is "
                           "derived from it and the site would loop forever")

    stem = (f"site{labels['site_index']:02d}"
            f"_step{labels.get('step_index', 0)}"
            f"_pt{labels.get('point_index', 0):02d}")

    payload: AnalysisState = {"file_path": pending["file_path"], "out_stem": stem}
    if state["recipe"].context:
        payload["experiment_context"] = state["recipe"].context

    out = await _analysis_graph.ainvoke(payload)

    if out.get("kind") != "loop":
        raise RuntimeError(f"ordered a loop but the file classifies as "
                           f"{out.get('kind')!r}: {pending['file_path']}")

    record = {**out,
              "instrument_params": state["instrument_state"],
              "requested_params":  pending.get("params"),
              "labels":            labels}
    save_json(records_dir() / f"{stem}.json", record)

    p = out["loop_params"]["off_field"]
    print(f"[record] {stem}  Vc {p.v_c_rising}/{p.v_c_falling} V, "
          f"imprint {p.imprint_v}, noise {p.branch_rms_noise:.3g}  "
          f"({len(recs) + 1} records)")

    return {"experimental_records": recs + [record], "pending": None}