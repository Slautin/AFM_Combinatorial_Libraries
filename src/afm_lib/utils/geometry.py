from math import hypot


def is_close_xy(a: tuple[float, float], b: tuple[float, float], tol_m: float) -> bool:
    """Are two XY positions the same to within tol_m? Used by the ensure_* nodes
    to decide whether a move is needed at all."""
    return hypot(a[0] - b[0], a[1] - b[1]) <= tol_m