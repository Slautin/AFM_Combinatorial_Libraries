import numpy as np

from afm_lib.config import frames_dir
from afm_lib.schemas.image_metrics import ImageMetrics
from afm_lib.states.analysis_state import AnalysisState
from afm_lib.utils.channel_utils import get_stats
from afm_lib.utils.image_utils import analyse_frame


def _channel(channels: dict, prefix: str):
    """Channel dict whose title starts with `prefix` (HeightRetrace, Height, ...), or None."""
    return next((c for c in channels.values() if c["title"].startswith(prefix)), None)


async def image_metrics_node(state: AnalysisState) -> AnalysisState:
    """Scalar descriptors of one topography frame. Deterministic: no LLM.
    Copies every channel plus the line-flattened height to frames/<out_stem>/
    (the scan analogue of loops/<stem>/) and re-points array_path there."""
    channels = {k: dict(c) for k, c in state["file_channels"].items()}
    px_m = state.get("px_m")
    if px_m is None:
        raise RuntimeError("image_metrics needs px_m (scan_size_m / pixels) from the caller")

    height = _channel(channels, "Height")
    if height is None:
        raise ValueError(f"no Height channel in {[c['title'] for c in channels.values()]}")
    amp   = _channel(channels, "Amplitude")
    phase = _channel(channels, "Phase")

    z = np.load(height["array_path"]).astype(float)
    a = np.load(amp["array_path"]).astype(float)   if amp   else None
    p = np.load(phase["array_path"]).astype(float) if phase else None

    metrics, z_flat = analyse_frame(z, px_m, amplitude=a, phase=p)

    dest = frames_dir() / state.get("out_stem", "current")
    dest.mkdir(parents=True, exist_ok=True)
    for c in channels.values():                      # raw channels, as delivered by the instrument
        path = dest / f"{c['title']}.npy"
        np.save(path, np.load(c["array_path"]))
        c["array_path"] = str(path)
    path = dest / "Height_flat.npy"                  # what the roughness numbers were computed on
    np.save(path, z_flat.astype(np.float32))
    channels["Height_flat"] = {**height, "title": "Height_flat", "array_path": str(path),
                               "stats": get_stats(z_flat)}

    print(f"[image_metrics] Rq {metrics['rq_m']*1e9:.2f} nm, {metrics['grain_count']} grains, "
          f"r_med {metrics['grain_radius_median_m']*1e9:.1f} nm -> {dest}")
    return {"image_metrics": ImageMetrics(**metrics), "file_channels": channels}   # type: ignore