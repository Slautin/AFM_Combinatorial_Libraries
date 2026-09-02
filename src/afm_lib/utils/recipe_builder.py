from pathlib import Path

import numpy as np
import yaml

from afm_lib.schemas.recipe import Recipe

STAGE_LIMIT_M = 0.10        # matches STAGE_LIMIT_M in the MCP server's move_stage.py


def line_sites(p0, p1, n):
    """n stage positions from p0 to p1 inclusive, evenly spaced.
    p0 and p1 are (x_m, y_m) tuples read from the instrument."""
    if n < 2:
        raise ValueError("n must be >= 2 — p0 and p1 are both included")
    xs = np.linspace(p0[0], p1[0], n)
    ys = np.linspace(p0[1], p1[1], n)
    return [(float(x), float(y)) for x, y in zip(xs, ys)]


def grid_sites(line, n_rows=1, row_spacing_m=0.0, serpentine=False):
    """Repeat a line n_rows times, offset PERPENDICULAR to the line direction.

    The offset direction is the line's own direction rotated +90 deg, so rows stay
    parallel and the cells come out square regardless of how the P0->P1 line is
    oriented on the stage. A +y shift would shear the grid whenever the line is not
    along x — and on a composition gradient that means row 2 sits at a slightly
    different composition than row 1.

    Row 0 is the line as given. Negative row_spacing_m puts the rows on the other
    side. serpentine=True reverses odd rows so the stage does not travel back
    across the whole line between rows.
    """
    if n_rows > 1 and row_spacing_m:
        (x0, y0), (x1, y1) = line[0], line[-1]
        dx, dy = x1 - x0, y1 - y0
        length = (dx * dx + dy * dy) ** 0.5
        if length == 0:
            raise ValueError("line has zero length — cannot derive a perpendicular")
        nx, ny = -dy / length, dx / length          # +90 deg rotation
    else:
        nx = ny = 0.0

    out = []
    for r in range(n_rows):
        ox, oy = r * row_spacing_m * nx, r * row_spacing_m * ny
        cols = list(enumerate(line))
        if serpentine and r % 2:
            cols = cols[::-1]
        for c, (x, y) in cols:
            out.append({"label": f"r{r}c{c:02d}",
                        "x_stage_m": x + ox,
                        "y_stage_m": y + oy})
    return out


def check_sites(sites, limit_m=STAGE_LIMIT_M):
    """Return a list of problems: outside travel, or too close to distinguish."""
    problems = []
    for s in sites:
        if max(abs(s["x_stage_m"]), abs(s["y_stage_m"])) > limit_m:
            problems.append(f"{s['label']} outside +/-{limit_m*1e3:.0f} mm travel")

    pts = [(s["x_stage_m"], s["y_stage_m"]) for s in sites]
    gaps = [np.hypot(a[0] - b[0], a[1] - b[1])
            for i, a in enumerate(pts) for b in pts[i + 1:]]
    if gaps:
        smallest = min(gaps)
        problems.append(f"closest pair: {smallest*1e6:.0f} um "
                        f"(must exceed STAGE_TOL_M or ensure_stage will skip the move)")
    return problems


def preview_sites(sites, limit_m=STAGE_LIMIT_M):
    """Sanity plot of the site layout, in stage millimetres."""
    import matplotlib.pyplot as plt

    x = [s["x_stage_m"] * 1e3 for s in sites]
    y = [s["y_stage_m"] * 1e3 for s in sites]

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(x, y, "-", lw=1, color="#c9ccd1", zorder=1)          # visit order
    ax.scatter(x, y, s=28, color="#3b6ea5", zorder=2)
    if len(sites) <= 24:
        for s, xi, yi in zip(sites, x, y):
            ax.annotate(s["label"], (xi, yi), textcoords="offset points",
                        xytext=(5, 4), fontsize=7, color="#5a5f66")

    ax.set_xlabel("stage X, mm")
    ax.set_ylabel("stage Y, mm")
    ax.set_title(f"{len(sites)} sites")
    ax.set_aspect("equal")                                        # physical space
    ax.grid(True, lw=0.5, color="#e6e8ea")
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    plt.tight_layout()
    plt.show()


def write_recipe(path, name, sites, loop_settings, points_m, context=""):
    """Validate through the Recipe model, then write the YAML.
    Nothing is written if validation fails."""
    data = {
        "name": name,
        "context": context,
        "sites": sites,
        "per_site": [{"kind": "loop",
                      "points_m": [list(p) for p in points_m],
                      "loop_settings": dict(loop_settings)}],
    }
    Recipe(**data)                       # raises before touching the disk

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
                    encoding="utf-8")
    return path