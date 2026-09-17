"""
image_utils.py — deterministic descriptors of one AFM topography frame.

Every function takes a 2-D height array in metres plus the pixel size in metres
and returns plain floats / arrays. No instrument, no LLM, no state.

Two flattening levels are used on purpose:
  plane-flattened  -> level statistics (terraces / multi-level grains survive)
  line-flattened   -> roughness, autocorrelation, PSD, grains (scan-line noise removed)
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage, stats
from scipy.signal import find_peaks
from skimage.feature import peak_local_max
from skimage.measure import regionprops
from skimage.segmentation import watershed


# ---------------------------------------------------------------- flattening

def plane_flatten(z: np.ndarray) -> np.ndarray:
    """Subtract the best-fit plane (global tilt). Keeps terraces and levels."""
    ny, nx = z.shape
    y, x = np.mgrid[:ny, :nx]
    A = np.column_stack([x.ravel(), y.ravel(), np.ones(z.size)])
    coef, *_ = np.linalg.lstsq(A, z.ravel(), rcond=None)
    return z - (A @ coef).reshape(z.shape)


def line_flatten(z: np.ndarray, order: int = 1) -> np.ndarray:
    """Subtract a polynomial of `order` from every fast-scan line (row).
    Removes line-to-line offsets and drift; also removes real level steps
    between lines, so use it for roughness, not for level statistics."""
    x = np.arange(z.shape[1])
    out = np.empty_like(z)
    for i, row in enumerate(z):
        c = np.polyfit(x, row, order)
        out[i] = row - np.polyval(c, x)
    return out


# ---------------------------------------------------------------- roughness

def roughness(z: np.ndarray) -> dict:
    """Amplitude descriptors of a flattened height map."""
    zc = z - z.mean()
    return {
        "rq_m":      float(np.sqrt(np.mean(zc**2))),
        "ra_m":      float(np.mean(np.abs(zc))),
        "pv_m":      float(np.percentile(zc, 99) - np.percentile(zc, 1)),   # robust peak-to-valley
        "skewness":  float(stats.skew(zc.ravel())),
        "kurtosis":  float(stats.kurtosis(zc.ravel())),                      # excess; 0 = Gaussian
    }


# ---------------------------------------------------------------- levels

def level_stats(z_plane: np.ndarray, n_bins: int = 128) -> dict:
    """Modes of the height histogram of the PLANE-flattened image.
    One mode = single-level surface; two or more = terraces or grains on
    different levels. Peaks must be separated by > 4 bins and stand at least
    10 % of the highest peak."""
    zc = z_plane - np.median(z_plane)
    hist, edges = np.histogram(zc, bins=n_bins)
    hist = ndimage.gaussian_filter1d(hist.astype(float), 1.5)
    centers = 0.5 * (edges[1:] + edges[:-1])
    peaks, props = find_peaks(hist, distance=4, prominence=0.10 * hist.max())
    order = np.argsort(hist[peaks])[::-1]
    levels = centers[peaks][order]
    return {
        "n_levels":        int(len(levels)),
        "level_spacing_m": float(np.abs(levels[0] - levels[1])) if len(levels) > 1 else 0.0,
    }


# ---------------------------------------------------------------- lateral scale

def radial_profile(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Azimuthal average of a centred 2-D map -> (radius_px, value)."""
    ny, nx = img.shape
    y, x = np.indices(img.shape)
    r = np.hypot(x - nx // 2, y - ny // 2).astype(int)
    tbin = np.bincount(r.ravel(), img.ravel())
    nr = np.bincount(r.ravel())
    return np.arange(len(tbin)), tbin / np.maximum(nr, 1)


def autocorrelation_length(z: np.ndarray, px_m: float) -> float:
    """Radius at which the normalised autocorrelation drops to 1/e, metres.
    A model-free grain / feature scale."""
    zc = z - z.mean()
    f = np.fft.fft2(zc)
    acf = np.fft.fftshift(np.real(np.fft.ifft2(f * np.conj(f))))
    acf /= acf.max()
    r, prof = radial_profile(acf)
    below = np.where(prof < np.exp(-1))[0]
    if len(below) == 0:
        return float("nan")
    i = below[0]
    # linear interpolation between the last point above and the first below
    frac = (prof[i - 1] - np.exp(-1)) / (prof[i - 1] - prof[i]) if i > 0 else 0.0
    return float((i - 1 + frac) * px_m)


def psd_descriptors(z: np.ndarray, px_m: float) -> dict:
    """Radially averaged power spectral density.
    psd_slope: log-log slope over the mid band (self-affine exponent proxy).
    psd_knee_m: wavelength where the PSD leaves the low-frequency plateau —
    a second characteristic scale that a watershed does not see."""
    zc = z - z.mean()
    p = np.abs(np.fft.fftshift(np.fft.fft2(zc)))**2
    r, prof = radial_profile(p)
    n = z.shape[0]
    k = r[1:n // 2] / (n * px_m)            # spatial frequency, 1/m
    s = prof[1:n // 2]
    ok = s > 0
    lk, ls = np.log10(k[ok]), np.log10(s[ok])
    # mid band: skip the 3 lowest and the highest quarter (noise floor)
    lo, hi = 3, int(0.75 * len(lk))
    slope = float(np.polyfit(lk[lo:hi], ls[lo:hi], 1)[0]) if hi - lo > 4 else float("nan")
    # knee: where the smoothed spectrum falls 3 dB below the low-k plateau
    sm = ndimage.uniform_filter1d(ls, 3)
    plateau = np.median(sm[:3])
    drop = np.where(sm < plateau - 0.3)[0]
    knee = float(1.0 / k[ok][drop[0]]) if len(drop) else float("nan")
    return {"psd_slope": slope, "psd_knee_m": knee}


# ---------------------------------------------------------------- grains

def segment_grains(z: np.ndarray, px_m: float, sigma_px: float = 1.5,
                   min_distance_px: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """Watershed on the inverted, smoothed height: every local maximum seeds a
    grain, boundaries fall in the valleys. Returns (label_map, grains) where
    grains has one row per grain that does NOT touch the frame edge:
      [label, area_m2, radius_eq_m, mean_height_m, max_height_m, cx_m, cy_m]
    Edge-touching grains are cut by the frame and would bias the size stats."""
    zs = ndimage.gaussian_filter(z, sigma_px)
    markers_xy = peak_local_max(zs, min_distance=min_distance_px, exclude_border=False)
    markers = np.zeros(z.shape, dtype=np.int32)
    markers[tuple(markers_xy.T)] = np.arange(1, len(markers_xy) + 1)
    labels = watershed(-zs, markers)
    ny, nx = z.shape
    rows = []
    for p in regionprops(labels, intensity_image=z):
        minr, minc, maxr, maxc = p.bbox
        if minr == 0 or minc == 0 or maxr == ny or maxc == nx:
            continue                                   # touches the frame edge
        area = p.area * px_m**2
        rows.append([p.label, area, np.sqrt(area / np.pi),
                     p.intensity_mean, p.intensity_max,
                     p.centroid[1] * px_m, p.centroid[0] * px_m])
    return labels, np.array(rows, dtype=float).reshape(-1, 7)


def grain_stats(grains: np.ndarray, labels: np.ndarray, px_m: float) -> dict:
    """Scalars from the per-grain table. Radii are usually log-normal, so the
    median and IQR are reported next to the mean."""
    if len(grains) == 0:
        return {"grain_count": 0, "grain_radius_median_m": float("nan"),
                "grain_radius_iqr_m": float("nan"), "grain_radius_mean_m": float("nan"),
                "grain_radius_std_m": float("nan"), "grain_height_std_m": float("nan"),
                "grain_coverage": 0.0}
    r = grains[:, 2]
    q1, q3 = np.percentile(r, [25, 75])
    return {
        "grain_count":           int(len(grains)),
        "grain_radius_median_m": float(np.median(r)),
        "grain_radius_iqr_m":    float(q3 - q1),
        "grain_radius_mean_m":   float(r.mean()),
        "grain_radius_std_m":    float(r.std()),
        "grain_height_std_m":    float(grains[:, 3].std()),   # spread of per-grain mean height = level spread
        "grain_coverage":        float(grains[:, 1].sum() / (labels.size * px_m**2)),
    }


# ---------------------------------------------------------------- quality

def tracking_quality(amplitude: np.ndarray | None, phase: np.ndarray | None) -> dict:
    """Feedback-tracking indicators that need no calibration:
    amp_rel_std  — relative amplitude error; large = tip not tracking (parachuting)
    phase_std    — phase spread; large = varying tip–sample interaction or bad tracking"""
    out = {}
    if amplitude is not None:
        a = amplitude[np.isfinite(amplitude)]
        out["amp_rel_std"] = float(a.std() / a.mean()) if a.mean() else float("nan")
    if phase is not None:
        out["phase_std_deg"] = float(np.nanstd(phase))
    return out


# ---------------------------------------------------------------- one call

def analyse_frame(height: np.ndarray, px_m: float,
                  amplitude: np.ndarray | None = None,
                  phase: np.ndarray | None = None,
                  sigma_px: float = 1.5, min_distance_px: int = 3) -> tuple[dict, np.ndarray]:
    """All scalar descriptors of one frame.
    Returns (metrics, height_flat): metrics is flat and JSON-safe, height_flat is
    the line-flattened height in metres (saved next to the raw channels)."""
    z_plane = plane_flatten(height)
    z_line  = line_flatten(z_plane)

    labels, grains = segment_grains(z_line, px_m, sigma_px, min_distance_px)
    m = {}
    m.update(roughness(z_line))
    m.update(level_stats(z_plane))
    m["corr_length_m"] = autocorrelation_length(z_line, px_m)
    m.update(psd_descriptors(z_line, px_m))
    m.update(grain_stats(grains, labels, px_m))
    m.update(tracking_quality(amplitude, phase))
    return m, z_line
