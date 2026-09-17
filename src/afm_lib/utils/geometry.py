from math import hypot


def is_close_xy(a: tuple[float, float], b: tuple[float, float], tol_m: float) -> bool:
    """Are two XY positions the same to within tol_m? Used by the ensure_* nodes
    to decide whether a move is needed at all."""
    return hypot(a[0] - b[0], a[1] - b[1]) <= tol_m


def sample_axes(origin, direction, mirror=False, axis="x"):
    """Unit vectors (e1, e2) of the sample frame in stage coordinates.

    direction : "x" | "y" (a stage axis) or (x, y), a second stage point.
                The line origin -> direction is the sample axis named by `axis`.
    axis      : "x" -> that line is sample +x (default); "y" -> it is sample +y.
    mirror    : True if the stage image of the sample is mirrored (flips the other axis)."""
    if direction == "x":
        u = (1.0, 0.0)
    elif direction == "y":
        u = (0.0, 1.0)
    else:
        dx, dy = direction[0] - origin[0], direction[1] - origin[1]
        n = hypot(dx, dy)
        if n == 0:
            raise ValueError("direction point coincides with origin")
        u = (dx / n, dy / n)
    if axis == "x":
        e1, e2 = u, (-u[1], u[0])              # e2 = e1 rotated +90 deg
        if mirror:
            e2 = (-e2[0], -e2[1])
    elif axis == "y":
        e2, e1 = u, (u[1], -u[0])              # e1 = e2 rotated -90 deg
        if mirror:
            e1 = (-e1[0], -e1[1])
    else:
        raise ValueError("axis must be 'x' or 'y'")
    return e1, e2


def stage_to_sample(xy_stage, origin, direction, mirror=False, axis="x"):
    """Stage (x, y) -> sample (x, y), metres. Pure geometry, no state."""
    e1, e2 = sample_axes(origin, direction, mirror, axis)
    dx, dy = xy_stage[0] - origin[0], xy_stage[1] - origin[1]
    return dx * e1[0] + dy * e1[1], dx * e2[0] + dy * e2[1]