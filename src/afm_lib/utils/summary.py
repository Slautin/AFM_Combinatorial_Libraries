import csv
import json
from pathlib import Path

from afm_lib.utils.geometry import stage_to_sample

BRANCHES = ("off_field", "on_field")

# LoopParams fields worth a column in the flat table
PARAM_COLS = ("n_cycles", "v_c_rising", "v_c_falling", "imprint_v", "loop_width_v",
              "remnant_rising_m", "remnant_falling_m", "loop_height_m",
              "sat_at_vplus_m", "sat_at_vminus_m", "response_offset_m",
              "loop_area_per_cycle", "direction",
              "branch_rms_noise", "quadrature_residual", "phase_offset_deg")

# ImageMetrics fields worth a column in the flat table
IMAGE_COLS = ("rq_m", "ra_m", "pv_m", "skewness", "kurtosis",
              "n_levels", "level_spacing_m",
              "corr_length_m", "psd_slope", "psd_knee_m",
              "grain_count", "grain_radius_median_m", "grain_radius_iqr_m",
              "grain_radius_mean_m", "grain_radius_std_m", "grain_height_std_m", "grain_coverage",
              "amp_rel_std", "phase_std_deg")


def _measurement(rec: dict) -> dict:
    """One record -> the comprehensive per-measurement entry."""
    inst = rec.get("instrument_params", {})
    loops = rec.get("loops", {})

    return {
        "labels": rec.get("labels", {}),
        "file_path": rec.get("file_path"),

        # what was asked for
        "requested": {
            "loop_settings": (rec.get("requested_params") or {}).get("loop_settings"),
            "scan_settings": (rec.get("requested_params") or {}).get("scan_settings"),
            "diagnosis":     (rec.get("requested_params") or {}).get("diagnosis"),
        },

        # what the instrument actually had at acquisition time
        "achieved": {
            "loop_settings":   inst.get("loop_settings"),
            "stage_position":  inst.get("stage_position"),
            "probe_position":  inst.get("probe_position"),
            "pfm_excitation":  inst.get("pfm_excitation"),
            "ac_excitation":   inst.get("ac_excitation"),
            "contact_feedback": inst.get("contact_feedback"),
            "scan_settings":   inst.get("scan_settings"),
            "mode":            inst.get("mode"),
        },

        # segmentation: shape and artifacts, not the arrays
        "segmentation": {
            "n_pulses":       loops.get("n_pulses"),
            "channels":       sorted(loops.get("loops", {})),
            "bias_on_path":   loops.get("bias_on_path"),
            "bias_off_path":  loops.get("bias_off_path"),
            "overview_path":  loops.get("overview_path"),
            "n_points":       {k: v.get("n_points")
                               for k, v in loops.get("loops", {}).items()},
        },

        "loop_params": rec.get("loop_params", {}),
        # scan branch: the frame as actually scanned, and its descriptors
        "achieved_frame": rec.get("achieved_frame"),
        "image_metrics":  rec.get("image_metrics"),
        "frame_arrays":   {c["title"]: c.get("array_path")
                           for c in rec.get("file_channels", {}).values()
                           if c.get("array_path")},

        # per-channel stats keyed by title rather than Channel_00N
        "channel_stats": {c["title"]: c.get("stats")
                          for c in rec.get("file_channels", {}).values()},
    }


def build_run_summary(run_dir) -> dict:
    """Consolidate one run directory into a single dict.
    Reads recipe.json, session.json and every records/*.json."""
    run_dir = Path(run_dir)

    def _load(p, default=None):
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default

    recipe  = _load(run_dir / "recipe.json", {})
    session = _load(run_dir / "session.json", {})

    files = sorted((run_dir / "records").glob("*.json"))
    measurements = [_measurement(json.loads(f.read_text(encoding="utf-8")))
                    for f in files]

    return {
        "run": {
            "name":     run_dir.name,
            "run_dir":  str(run_dir),
            "recipe_name": recipe.get("name"),
            "context":  recipe.get("context"),
            "started_ts": session.get("started_ts"),
            "instrument_directory": session.get("instrument_directory"),
            "n_measurements": len(measurements),
        },
        "recipe": recipe,
        "status_at_start": session.get("status_at_start"),
        "measurements": measurements,
    }


def _identity(m: dict, frame: dict | None) -> dict:
    """Columns shared by every row, whatever the measurement kind.
    x/y_sample_m: the site position in the sample frame declared by the recipe
    (stage position transformed; the um-scale probe/frame offsets stay in the
    scan frame, whose orientation relative to the stage is not calibrated)."""
    lab   = m["labels"]
    stage = m["achieved"].get("stage_position") or {}
    probe = m["achieved"].get("probe_position") or {}
    fb    = m["achieved"].get("contact_feedback") or {}
    xs, ys = stage.get("x_stage_m"), stage.get("y_stage_m")
    if frame and xs is not None and ys is not None:
        x_sample, y_sample = stage_to_sample((xs, ys), frame["origin_stage_m"], frame["direction"],
                                    frame.get("mirror", False), frame.get("axis", "x"))
    else:
        x_sample = y_sample = None
    return {
        "site_index":  lab.get("site_index"),
        "site_label":  lab.get("site_label"),
        "step_index":  lab.get("step_index"),
        "point_index": lab.get("point_index"),
        "x_stage_m":   xs,
        "y_stage_m":   ys,
        "x_sample_m":  x_sample,
        "y_sample_m":  y_sample,
        "x_probe_m":   probe.get("x_m"),
        "y_probe_m":   probe.get("y_m"),
        "feedback_on": fb.get("feedback_on"),
    }


def loop_rows(m: dict, frame: dict | None) -> list[dict]:
    """One row per branch for a loop measurement (unchanged contract)."""
    req = m["requested"].get("loop_settings") or {}
    rows = []
    for branch in BRANCHES:
        p = m["loop_params"].get(branch)
        if not p:
            continue
        row = {**_identity(m, frame), "branch": branch,
               "v_dc_max_v_req": req.get("v_dc_max_v"),
               "n_cycles_req":   req.get("n_cycles"),
               "n_pulses":       m["segmentation"].get("n_pulses")}
        row.update({c: p.get(c) for c in PARAM_COLS})
        row["file_path"] = m["file_path"]
        rows.append(row)
    return rows


def scan_rows(m: dict, frame: dict | None) -> list[dict]:
    """One row per frame for a scan measurement."""
    im = m.get("image_metrics")
    if not im:
        return []
    af = m.get("achieved_frame") or {}
    ac = m["achieved"].get("ac_excitation") or {}
    fb = m["achieved"].get("contact_feedback") or {}
    row = {**_identity(m, frame),
           "x_frame_m":    af.get("x_scan_center_m"),
           "y_frame_m":    af.get("y_scan_center_m"),
           "scan_size_m":  af.get("scan_size_m"),
           "pixels":       af.get("pixels"),
           "scan_rate_hz": af.get("scan_rate_hz"),
           "f_drive_hz":   ac.get("drive_frequency_hz"),
           "v_ac_v":       ac.get("drive_amplitude_v"),
           "setpoint_v":   fb.get("setpoint_v")}
    row.update({c: im.get(c) for c in IMAGE_COLS})
    row["file_path"] = m["file_path"]
    return [row]


def summary_rows(summary: dict) -> list[dict]:
    """Flat table. Loops -> one row per (measurement, branch); scans -> one row per frame.
    DictWriter is given the union of columns so a mixed recipe truncates nothing."""
    frame = (summary.get("recipe") or {}).get("sample_frame")
    rows = []
    for m in summary["measurements"]:
        rows += loop_rows(m, frame) if m.get("loop_params") else scan_rows(m, frame)
    return rows


def write_run_summary(run_dir) -> tuple[Path, Path]:
    """Write summary.json and results.csv into the run directory."""
    run_dir = Path(run_dir)
    summary = build_run_summary(run_dir)

    js = run_dir / "summary.json"
    js.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    rows = summary_rows(summary)
    csv_path = run_dir / "results.csv"
    if rows:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            fieldnames = list(dict.fromkeys(k for r in rows for k in r))    # union, first-seen order
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

    print(f"{run_dir.name}: {len(summary['measurements'])} measurements, "
          f"{len(rows)} rows -> summary.json, results.csv")
    return js, csv_path