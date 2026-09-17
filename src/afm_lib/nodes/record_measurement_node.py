import shutil

from afm_lib.config import cache_dir, records_dir

from afm_lib.graphs.loop_analysis_graph import build_loop_analysis_graph
from afm_lib.graphs.image_analysis_graph import build_image_analysis_graph

from afm_lib.states.analysis_state import AnalysisState
from afm_lib.states.lib_experiment_state import LibExperimentState
from afm_lib.utils.io_utils import save_json

_graphs = {"loop": build_loop_analysis_graph(), "scan": build_image_analysis_graph()}

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
    if pending["kind"] == "scan":
        f = pending["achieved_frame"]
        payload["px_m"] = f["scan_size_m"] / f["pixels"]

    out = await _graphs[pending["kind"]].ainvoke(payload)

    expected = {"loop": "loop", "scan": "image"}[pending["kind"]]
    if out.get("kind") != expected:
        raise RuntimeError(f"ordered a {pending['kind']} but the file classifies as "
                           f"{out.get('kind')!r}: {pending['file_path']}")

    for ch in out.get("file_channels", {}).values():
        ch.pop("preview_path", None)
        if pending["kind"] == "loop":
            ch.pop("array_path", None)
    shutil.rmtree(cache_dir() / stem, ignore_errors=True)

    record = {**out,
              "instrument_params": state["instrument_state"],
              "requested_params":  pending.get("params"),
              "achieved_frame":    pending.get("achieved_frame"),  
              "labels":            labels}
    save_json(records_dir() / f"{stem}.json", record)


    if pending["kind"] == "loop":
        p = out["loop_params"]["off_field"]
        print(f"[record] {stem}  Vc {p.v_c_rising}/{p.v_c_falling} V, imprint {p.imprint_v}, "
              f"noise {p.branch_rms_noise:.3g}  ({len(recs) + 1} records)")
    else:
        im = out["image_metrics"]
        print(f"[record] {stem}  Rq {im.rq_m*1e9:.2f} nm, {im.grain_count} grains, "
              f"r_med {im.grain_radius_median_m*1e9:.1f} nm  ({len(recs) + 1} records)")
        
    return {"experimental_records": recs + [record], "pending": None}