from afm_lib.states.analysis_state import Channel
from afm_lib.config import cache_dir

import os
import numpy as np
from PIL import Image as PILImage
import matplotlib
matplotlib.use("Agg")                      # no GUI backend in nodes
import matplotlib.pyplot as plt

from pathlib import Path


def get_stats(array) -> dict:
    """Basic channel stats, robust to nulls / non-numeric data."""
    array = np.asarray(array)

    if not np.issubdtype(array.dtype, np.number):
        try:
            array = array.astype(np.float64)   # converts None -> nan
        except (TypeError, ValueError):
            return {"ok": False,
                    "error": f"non-numeric data (dtype={array.dtype}, shape={array.shape})"}

    if np.iscomplexobj(array):
        array = np.abs(array)

    if np.isnan(array).all():
        return {"ok": False, "error": "all-NaN channel"}

    return {
        "ok": True,
        "min": float(np.nanmin(array)), 
        "max": float(np.nanmax(array)),
        "mean": float(np.nanmean(array)), 
        "std": float(np.nanstd(array)),
        "p01": float(np.nanpercentile(array, 1)),
        "p99": float(np.nanpercentile(array, 99)),
    }

def save_array(channel, out_dir=None) -> dict:
    """Cache the raw channel array for later analysis."""
    out_dir = Path(out_dir or cache_dir())
    out_dir.mkdir(parents=True, exist_ok=True)

    title = channel['title']
    arr_path = os.path.join(out_dir, f'{title}.npy')

    data = np.asarray(channel['data'], dtype=np.float32)
    try:
        np.save(arr_path, data)
        return {"ok": True, "path": str(arr_path), "error": None}
    except Exception as exc:
        return {"ok": False, "path": str(arr_path), "error": str(exc)}


def load_array(path: str) -> np.ndarray:
    """Load a cached raw channel array."""
    return np.load(path)


# title-prefix -> correct unit (Asylum/DART channels)
UNIT_OVERRIDES = {
    "Height": "m", "ZSnsr": "m", "Amp": "m",
    "Phas": "deg", "Freq": "Hz",
    "Bias": "V", "Defl": "V",
}

def fix_units(title: str, units: str) -> str:
    for prefix, u in UNIT_OVERRIDES.items():
        if title.startswith(prefix):
            return u
    return units


def save_preview(channel, out_dir=None) -> dict:
    """
    Save a PNG preview. Images -> grayscale raster; spectra -> line plot.
    """
    out_dir = Path(out_dir or cache_dir())
    out_dir.mkdir(parents=True, exist_ok=True)

    title = channel['title']
    im_path = os.path.join(out_dir, f'{title}.png')

    try:
        data = np.asarray(channel['data'], dtype=np.float64)
        is_spectrum = ('SPECTRUM' in str(channel.get('data_type', '')).upper()
                       or data.ndim == 1)

        if is_spectrum:
            _save_spectrum_png(data, channel, im_path)
        else:
            _save_image_png(data, im_path)

        return {"ok": True, "path": str(im_path), "error": None}
    except Exception as exc:
        return {"ok": False, "path": str(im_path), "error": str(exc)}


def _save_spectrum_png(data, channel, im_path, max_curves=8):
    # x-axis: dimension values if the reader provided them, else index
    x = np.asarray(channel['dim_values'], dtype=np.float64) if channel.get('dim_values') else None

    fig, ax = plt.subplots(figsize=(6, 4), dpi=120)

    if data.ndim == 1:
        curves = data[None, :]
    else:
        if data.shape[0] > data.shape[1]:      # make spectral axis the last one
            data = data.T
        curves = data[:max_curves]             # don't overplot; cap the count

    for i, y in enumerate(curves):
        xi = x if x is not None and x.size == y.size else np.arange(y.size)
        ax.plot(xi, y, lw=1, alpha=0.8,
                label=f"{i}" if len(curves) > 1 else None)

    ax.set_title(channel['title'])
    ax.set_xlabel(channel.get('dim_units', 'index'))
    ax.set_ylabel(channel.get('units', ''))
    ax.grid(True, alpha=0.3)
    if len(curves) > 1:
        ax.legend(fontsize=7, title=f"{len(curves)}/{data.shape[0]} shown")
    fig.tight_layout()
    fig.savefig(im_path, format="PNG")
    plt.close(fig)


def _save_image_png(data, im_path):
    finite = data[np.isfinite(data)]
    lo, hi = np.percentile(finite, (1, 99)) if finite.size else (0.0, 1.0)
    if hi <= lo:
        hi = lo + 1e-12
    norm = np.clip((data - lo) / (hi - lo), 0.0, 1.0)
    norm = np.nan_to_num(norm, nan=0.0)
    PILImage.fromarray((norm * 255).astype(np.uint8)).save(im_path, format="PNG")

def save_channel_grid(channels: dict, out_path, ncols: int = 3, panel_px: int = 512) -> dict:
    """One labelled contact sheet of all 2-D channels — the only preview the LLM is shown.
    Panels are drawn at ~native resolution; panel_px is the context-cost knob
    (512 -> ~2.1k image tokens for six channels, 384 -> ~1.2k)."""
    items = [(cid, ch) for cid, ch in channels.items()
             if len(ch.get("shape", [])) == 2 and ch.get("array_path")]
    if not items:
        return {"ok": False, "path": None, "error": "no 2-D channels to plot"}

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ncols = min(ncols, len(items))
    nrows = -(-len(items) // ncols)
    fig, axes = plt.subplots(nrows, ncols, dpi=100,
                             figsize=(ncols * panel_px / 100, nrows * panel_px / 100))
    axes = np.atleast_1d(axes).ravel()
    for ax in axes:
        ax.axis("off")

    for ax, (cid, ch) in zip(axes, items):
        a = np.load(ch["array_path"])                      # already oriented
        finite = a[np.isfinite(a)]
        lo, hi = np.percentile(finite, (1, 99)) if finite.size else (0.0, 1.0)
        if hi <= lo:
            hi = lo + 1e-12
        ax.imshow(a, cmap="gray", vmin=lo, vmax=hi)        # default origin: row 0 on top
        ax.set_title(f"{cid}  {ch.get('title')} [{ch.get('units')}]", fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return {"ok": True, "path": str(out_path), "error": None}

    


