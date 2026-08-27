from typing_extensions import TypedDict, NotRequired
from typing import Literal

from afm_lib.schemas.recipe import Recipe
from afm_lib.states.measurement_state import MeasurementState


class Site(TypedDict):
    """One stage position in the library — one composition.
    `status` exists because a skipped site leaves no records either, so without it
    'failed' is indistinguishable from 'not yet reached'."""
    index: int
    x_stage_m: float
    y_stage_m: float
    label: NotRequired[str]
    status: Literal["pending", "done", "failed"]
    error: NotRequired[str]


class LibExperimentState(MeasurementState):
    """Combinatorial-library grid search. These three fields are read by exactly
    one node — the planner. Everything else works off MeasurementState."""
    recipe: Recipe
    sites: list[Site]
    site_index: int          # -1 before the first site; stored because the stage
                             # position leaves no trace in the records