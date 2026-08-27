import os
import numpy as np
from matplotlib.figure import Figure

# numpy>=2.0 renamed trapz -> trapezoid
_trapz = getattr(np, "trapezoid", None) or np.trapz


# ----------------------------------------------------------------------
# 1. SS-PFM segmentation
# ----------------------------------------------------------------------
def segment_sspfm_loops(channels: dict, out_dir, skip_frac: float = 0.2,
                        exclude=("Bias", "Raw", "ZSnsr", "Defl", "Phas2"),
                        add_xy: bool = True) -> dict:
    """
    Segment an SS-PFM (DART) measurement into in-field / out-of-field loops.

    channels : 'file_channels' dict from state (needs 'array_path', 'units');
               must contain a Bias channel.
    out_dir  : directory for the .npy loops and the overview .png
    skip_frac: fraction of samples dropped at the start of each bias segment
               (transient after the bias step)

    Saves per channel: {title}_on.npy, {title}_off.npy
    Saves bias axes:   bias_on.npy / bias_off.npy (x-axis of the loops)
    Saves overview:    loops_overview.png
    """
    os.makedirs(out_dir, exist_ok=True)

    bias_key = next(k for k, c in channels.items() if c["title"].startswith("Bias"))
    bias = np.load(channels[bias_key]["array_path"]).ravel()

    # 1) keep only acquired samples (NaN padding at start/end)
    finite = np.isfinite(bias)
    bias_f = bias[finite]
    if bias_f.size == 0:
        raise ValueError("Bias channel contains no finite samples")

    # 2) run-length encode constant-bias segments
    #    FIX: relative threshold - an absolute 1e-9 shatters on DAC dither
    amp = float(np.nanmax(np.abs(bias_f)))
    step_tol = max(1e-4 * amp, 1e-12)
    change = np.where(np.abs(np.diff(bias_f)) > step_tol)[0] + 1
    bounds = np.concatenate([[0], change, [len(bias_f)]])

    # 3) classify segments; off-field inherits the preceding pulse bias
    tol = 1e-3 * amp
    on_slices, off_slices, on_bias, off_bias = [], [], [], []
    last_pulse = None
    for s, e in zip(bounds[:-1], bounds[1:]):
        v = bias_f[s]
        s_eff = s + max(1, int(np.ceil((e - s) * skip_frac)))
        if s_eff >= e:
            continue
        if np.abs(v) > tol:                      # on-field segment
            on_slices.append((s_eff, e)); on_bias.append(v); last_pulse = v
        elif last_pulse is not None:             # off-field, after a pulse
            off_slices.append((s_eff, e)); off_bias.append(last_pulse)

    # FIX: pair up on/off - the run can end on a pulse with no off-field read
    n_pairs = min(len(on_slices), len(off_slices))
    if n_pairs == 0:
        raise ValueError("no complete on/off pulse pair found")
    on_slices, off_slices = on_slices[:n_pairs], off_slices[:n_pairs]
    bias_on = np.asarray(on_bias[:n_pairs], dtype=np.float32)
    bias_off = np.asarray(off_bias[:n_pairs], dtype=np.float32)
    np.save(os.path.join(out_dir, "bias_on.npy"), bias_on)
    np.save(os.path.join(out_dir, "bias_off.npy"), bias_off)

    # 4) collect raw traces: measured + derived X/Y
    #    (X/Y are built from the RAW Amp/Phase, before segment averaging)
    #    FIX: the original file computed and saved `loops` twice - dead block removed
    traces = {}
    for k, ch in channels.items():
        title = ch["title"]
        if any(title.startswith(x) for x in exclude):
            continue
        y = np.load(ch["array_path"]).ravel()
        if y.size != bias.size:
            continue
        traces[title] = (y, ch.get("units", ""))

    if add_xy and "Amp" in traces and "Phase" in traces:
        a, units = traces["Amp"]
        phi = np.deg2rad(traces["Phase"][0])
        traces["X"] = (a * np.cos(phi), units)   # piezoresponse
        traces["Y"] = (a * np.sin(phi), units)   # quadrature

    def _seg_mean(arr, slices):
        out = np.full(len(slices), np.nan, dtype=np.float32)
        for i, (s, e) in enumerate(slices):
            w = arr[s:e]
            w = w[np.isfinite(w)]
            if w.size:
                out[i] = w.mean()
        return out

    loops = {}
    for title, (y, units) in traces.items():
        y = y[finite]
        y_on = _seg_mean(y, on_slices)
        y_off = _seg_mean(y, off_slices)
        p_on = os.path.join(out_dir, f"{title}_on.npy")
        p_off = os.path.join(out_dir, f"{title}_off.npy")
        np.save(p_on, y_on); np.save(p_off, y_off)
        loops[title] = {"on_path": p_on, "off_path": p_off,
                        "units": units, "n_points": int(y_on.size)}

    # 5) overview figure: rows = channels, cols = in-field / out-of-field
    fig = Figure(figsize=(8, 2.4 * len(loops)), dpi=120)
    axs = fig.subplots(len(loops), 2, squeeze=False, sharex=True)
    for r, (title, info) in enumerate(loops.items()):
        for c, (xax, suffix) in enumerate([(bias_on, "on"), (bias_off, "off")]):
            y = np.load(info[f"{suffix}_path"])
            axs[r][c].plot(xax, y, ".-", lw=0.7, ms=2)
            axs[r][c].set_ylabel(f"{title} [{info['units']}]", fontsize=8)
            axs[r][c].grid(True, alpha=0.3)
            if r == 0:
                axs[r][c].set_title(["in-field", "out-of-field"][c])
    for c in range(2):
        axs[-1][c].set_xlabel("Bias [V]")
    fig.tight_layout()
    fig_path = os.path.join(out_dir, "loops_overview.png")
    fig.savefig(fig_path)

    return {"bias_on_path": os.path.join(out_dir, "bias_on.npy"),
            "bias_off_path": os.path.join(out_dir, "bias_off.npy"),
            "loops": loops, "overview_path": fig_path,
            "n_pulses": int(bias_on.size)}


# ----------------------------------------------------------------------
# 2. measurement classifier (unchanged)
# ----------------------------------------------------------------------
def classify_measurement(arrays: dict[str, np.ndarray]) -> str:
    """Classify a measurement as 'image', 'loop' (SS-PFM), or 'spectrum'."""
    if any(a.ndim >= 2 and min(a.shape) > 1 for a in arrays.values()):
        return "image"

    bias = next((a for t, a in arrays.items() if t.startswith("Bias")), None)
    if bias is None:
        return "spectrum"

    b = bias.ravel()
    b = b[np.isfinite(b)]
    if b.size < 100 or np.max(np.abs(b)) < 1e-6:
        return "spectrum"

    change = np.where(np.abs(np.diff(b)) > 1e-9)[0] + 1
    bounds = np.concatenate([[0], change, [len(b)]])
    lens = np.diff(bounds)
    vals = b[bounds[:-1]]

    dwell = (lens >= 3).mean()
    zero = np.abs(vals) < 1e-3 * np.abs(b).max()
    altern = (np.diff(zero.astype(int)) != 0).mean()

    if len(lens) >= 20 and dwell > 0.8 and 0.2 < zero.mean() < 0.8 and altern > 0.8:
        return "loop"
    return "spectrum"


# ----------------------------------------------------------------------
# 3. hysteresis parameter extraction
# ----------------------------------------------------------------------
def _monotone_segments(bias, min_span_frac: float = 0.8):
    """
    Split a bias waveform into monotone sweeps and keep only the COMPLETE ones.

    A sweep is complete if it reaches both ends of the bias range (within
    (1 - min_span_frac) of the range). This discards the virgin ramp at the
    start and any truncated ramp at the end - lumping those into a branch is
    what produced the zig-zag artefact.

    Returns [(slice, 'rising' | 'falling'), ...] in acquisition order.
    Consecutive segments share their turning point by design.
    """
    b = np.asarray(bias, float)
    if b.size < 4:
        return []

    d = np.diff(b)
    s = np.sign(d)
    # forward-fill plateaus (sign 0) so they do not fake a turning point
    nz = np.flatnonzero(s)
    if nz.size == 0:
        return []
    s[:nz[0]] = s[nz[0]]
    for i in range(1, s.size):
        if s[i] == 0:
            s[i] = s[i - 1]

    turn = np.flatnonzero(np.diff(s)) + 1
    edges = np.concatenate([[0], turn, [b.size - 1]])

    bmin, bmax = float(b.min()), float(b.max())
    tol = (1.0 - min_span_frac) * (bmax - bmin)

    segs = []
    for a, e in zip(edges[:-1], edges[1:]):
        if e - a < 2:                      # need >= 3 points to interpolate
            continue
        sl = slice(int(a), int(e) + 1)
        if b[sl].min() > bmin + tol or b[sl].max() < bmax - tol:
            continue                       # partial ramp -> drop
        segs.append((sl, "rising" if b[e] > b[a] else "falling"))
    return segs


def extract_loop_params(bias, x, y=None, rotate=True, grid_n=201,
                        fig_path=None, units="", min_span_frac=0.8,
                        phase_offset_deg=None) -> dict:
    """
    Extract hysteresis parameters from one SS-PFM loop (bias, x [, y]).

    bias, x, y : 1D arrays in acquisition order (multi-cycle OK).
                 x, y = lock-in quadratures; passing y enables phase
                 rotation and the quadrature QC metric.
    rotate     : rotate (x, y) by the PCA angle phi0 so the switching signal
                 lands entirely in x' (instrument-phase independent). The sign
                 is then pinned so that x' increases with bias.
    phase_offset_deg : force a specific rotation angle instead of fitting one.
                 Pass the angle returned by the OUT-OF-FIELD loop when
                 analysing the matching IN-FIELD loop, so both share one
                 sign convention.

    Branches are averaged sweep-by-sweep (each complete monotone sweep is
    interpolated onto the common grid, then the sweeps are averaged). Binning
    raw points into a fine grid does NOT work: consecutive cycles are offset
    in bias by a fraction of a step and fall into different bins, which makes
    the interpolated branch oscillate between cycles.

    Coercive voltages = steepest crossings of the offset level on the
    cycle-averaged rising/falling branches.
    """
    bias = np.asarray(bias, float).ravel()
    x = np.asarray(x, float).ravel()
    y = None if y is None else np.asarray(y, float).ravel()
    if bias.size != x.size or (y is not None and y.size != bias.size):
        raise ValueError("bias, x (and y) must have the same length")

    # drop non-finite samples up front so segmentation indices stay valid
    good = np.isfinite(bias) & np.isfinite(x)
    if y is not None:
        good &= np.isfinite(y)
    bias, x = bias[good], x[good]
    if y is not None:
        y = y[good]
    if bias.size < 8:
        raise ValueError(f"only {bias.size} finite points - not a loop")

    out = {"n_points": int(bias.size), "n_points_dropped": int((~good).sum())}

    # ---- 0) quadrature rotation ---------------------------------------
    if rotate and y is not None:
        if phase_offset_deg is not None:
            phi0 = float(np.deg2rad(phase_offset_deg))
            flipped = None                      # caller owns the convention
        else:
            xc, yc = x - x.mean(), y - y.mean()
            phi0 = 0.5 * np.arctan2(2 * (xc * yc).mean(),
                                    (xc ** 2 - yc ** 2).mean())
        xr = x * np.cos(phi0) + y * np.sin(phi0)
        yr = -x * np.sin(phi0) + y * np.cos(phi0)
        if phase_offset_deg is None:
            # FIX: arctan2/2 lands in (-90, 90] deg, so the rotation may invert
            # the loop. Pin the convention: response increases with bias.
            flipped = bool(np.corrcoef(bias, xr)[0, 1] < 0)
            if flipped:
                xr, yr = -xr, -yr
                phi0 += np.pi
        out["phase_offset_deg"] = float(np.degrees(phi0))
        out["response_sign_flipped"] = flipped
        out["quadrature_residual"] = float(np.std(yr) / max(np.std(xr), 1e-30))
        x = xr
    else:
        out["phase_offset_deg"] = None
        out["response_sign_flipped"] = None
        out["quadrature_residual"] = None

    # ---- 1) branch split: COMPLETE monotone sweeps only ----------------
    segs = _monotone_segments(bias, min_span_frac)
    n_rise = sum(k == "rising" for _, k in segs)
    n_fall = sum(k == "falling" for _, k in segs)
    if n_rise == 0 or n_fall == 0:
        raise ValueError(f"no complete rising/falling sweep pair "
                         f"(rising={n_rise}, falling={n_fall}); "
                         f"waveform may be truncated")
    out["n_sweeps_rising"] = n_rise
    out["n_sweeps_falling"] = n_fall
    out["n_cycles"] = int(min(n_rise, n_fall))
    out["n_points_used"] = int(sum(sl.stop - sl.start for sl, _ in segs))

    # ---- 2) cycle-average each branch ----------------------------------
    grid = np.linspace(bias.min(), bias.max(), int(grid_n))

    def branch_avg(kind):
        curves = []
        for sl, k in segs:
            if k != kind:
                continue
            bs, xs = bias[sl], x[sl]
            o = np.argsort(bs, kind="stable")
            curves.append(np.interp(grid, bs[o], xs[o],
                                    left=np.nan, right=np.nan))
        stack = np.vstack(curves)
        cnt = np.isfinite(stack).sum(axis=0)
        tot = np.nansum(stack, axis=0)
        c = np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan)
        ok = np.isfinite(c)
        return np.interp(grid, grid[ok], c[ok])   # extend flat past the ends

    x_rise, x_fall = branch_avg("rising"), branch_avg("falling")

    # rms scatter of the used points around their own branch (noise metric)
    res = [x[sl] - np.interp(bias[sl], grid,
                             x_rise if k == "rising" else x_fall)
           for sl, k in segs]
    out["branch_rms_noise"] = float(np.sqrt(np.mean(np.concatenate(res) ** 2)))

    # ---- 3) saturation & vertical offset (outer 15% of the bias RANGE) --
    span = float(grid.max() - grid.min())
    hi = grid > grid.max() - 0.15 * span
    lo = grid < grid.min() + 0.15 * span
    sat_p = float(np.mean(np.concatenate([x_rise[hi], x_fall[hi]])))
    sat_m = float(np.mean(np.concatenate([x_rise[lo], x_fall[lo]])))
    v_offset = 0.5 * (sat_p + sat_m)
    out.update(sat_at_vplus_m=sat_p, sat_at_vminus_m=sat_m,
               response_offset_m=float(v_offset))

    # ---- 4) coercive voltages: steepest crossing of the offset level ----
    def crossing(xb):
        s = xb - v_offset
        idx = np.flatnonzero(np.signbit(s[:-1]) != np.signbit(s[1:]))
        if idx.size == 0:
            return None
        i = int(idx[np.argmax(np.abs(np.diff(xb))[idx])])
        den = s[i + 1] - s[i]
        if abs(den) < 1e-30:
            return float(grid[i])
        return float(grid[i] - s[i] * (grid[i + 1] - grid[i]) / den)

    vc_rise, vc_fall = crossing(x_rise), crossing(x_fall)
    out["v_c_rising"], out["v_c_falling"] = vc_rise, vc_fall
    if vc_rise is not None and vc_fall is not None:
        out["imprint_v"] = float((vc_rise + vc_fall) / 2)
        out["loop_width_v"] = float(abs(vc_rise - vc_fall))
    else:
        out["imprint_v"] = out["loop_width_v"] = None

    # ---- 5) remnant response: branch values at V = 0 --------------------
    r_rise = float(np.interp(0.0, grid, x_rise))
    r_fall = float(np.interp(0.0, grid, x_fall))
    out.update(remnant_rising_m=r_rise, remnant_falling_m=r_fall,
               loop_height_m=float(abs(r_fall - r_rise)))

    # ---- 6) area: integral BETWEEN the averaged branches -----------------
    # Closed by construction, already per cycle, insensitive to how many
    # sweeps or partial ramps the waveform contained.
    area = float(_trapz(x_fall - x_rise, grid))
    out["loop_area_per_cycle"] = abs(area)
    out["loop_area_units"] = f"V*{units}" if units else "V*a.u."
    out["direction"] = "ccw" if area > 0 else "cw"

    # ---- 7) QC flags for benchmarking -----------------------------------
    steps = np.concatenate([np.abs(np.diff(bias[sl])) for sl, _ in segs])
    step = float(np.median(steps)) if steps.size else float("inf")
    out["qc_symmetric_waveform"] = bool(n_rise == n_fall)
    out["qc_all_points_used"] = bool(out["n_points_used"] == bias.size)
    out["qc_bias_step_v"] = step
    out["snr"] = float(out["loop_height_m"] / max(out["branch_rms_noise"], 1e-30))

    out["annotated_path"] = None
    if fig_path is not None:
        _save_annotated_loop(fig_path, bias, x, grid, x_rise, x_fall,
                             out, units, segs)
        out["annotated_path"] = str(fig_path)

    return out


def _save_annotated_loop(fig_path, bias, x, grid, x_rise, x_fall, out,
                         units="", segs=()):
    """Annotated loop preview for vision-model review."""
    fig = Figure(figsize=(7, 5), dpi=120)
    ax = fig.add_subplot()

    used = np.zeros(bias.size, bool)
    for sl, _ in segs:
        used[sl] = True
    if (~used).any():
        ax.plot(bias[~used], x[~used], "x", ms=4, alpha=0.5, color="0.75",
                label="excluded (partial ramp)")
    ax.plot(bias[used], x[used], ".", ms=3, alpha=0.45, color="gray",
            label="data used")
    ax.plot(grid, x_rise, "-", lw=2, color="tab:blue", label="rising branch")
    ax.plot(grid, x_fall, "-", lw=2, color="tab:orange", label="falling branch")

    off = out["response_offset_m"]
    ax.axhline(off, ls=":", c="k", lw=0.8)
    ax.axvline(0, ls=":", c="k", lw=0.8)

    for vc, c, nm in [(out["v_c_rising"], "tab:blue", "Vc↑"),
                      (out["v_c_falling"], "tab:orange", "Vc↓")]:
        if vc is not None:
            ax.axvline(vc, ls="--", c=c, lw=1.2)
            ax.annotate(f"{nm} {vc:+.2f} V", (vc, off), fontsize=8,
                        rotation=90, va="bottom", ha="right", color=c)

    ax.plot([0, 0], [out["remnant_rising_m"], out["remnant_falling_m"]],
            "rs", ms=7, zorder=5, label="remnants @ 0 V")

    fmt = lambda v, p="{:+.3g}": "n/a" if v is None else p.format(v)
    stats = (f"imprint    {fmt(out['imprint_v'], '{:+.2f}')} V\n"
             f"width      {fmt(out['loop_width_v'], '{:.2f}')} V\n"
             f"height     {out['loop_height_m']:.3g} {units}\n"
             f"area/cycle {out['loop_area_per_cycle']:.3g} {out['loop_area_units']}\n"
             f"direction  {out['direction']}, {out['n_cycles']} cycle(s)\n"
             f"sweeps     {out['n_sweeps_rising']}up / {out['n_sweeps_falling']}dn\n"
             f"SNR        {out['snr']:.1f}\n"
             f"quad.res.  {fmt(out['quadrature_residual'], '{:.3f}')}")
    ax.text(0.02, 0.02, stats, transform=ax.transAxes, fontsize=8,
            family="monospace", va="bottom",
            bbox=dict(boxstyle="round", fc="white", alpha=0.85, ec="0.7"))

    ax.set_xlabel("Bias [V]")
    ax.set_ylabel(f"X' [{units}]" if units else "X'")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(fig_path)