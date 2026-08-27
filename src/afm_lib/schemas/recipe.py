from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from afm_lib.schemas.instrument import LoopSettings


class SiteSpec(BaseModel, frozen=True):
    label: str
    x_stage_m: float
    y_stage_m: float


class LoopStep(BaseModel, frozen=True):
    kind: Literal["loop"] = "loop"
    points_m: list[tuple[float, float]] = Field(
        description="Tip positions as offsets from the scan-frame centre, meters")
    loop_settings: LoopSettings


class Recipe(BaseModel, frozen=True):
    """Immutable campaign definition. Loaded once, archived into the run dir."""
    name: str
    context: str = ""
    sites: list[SiteSpec]
    per_site: list[LoopStep]

class SiteMeasurement(BaseModel, frozen=True):
    """One measurement in a site's program — the expanded form of a LoopStep.

    dx_m / dy_m are offsets from the scan-frame centre, so the same program lands
    at the same scanner coordinates at every site; a stage move does not touch
    XOffset/YOffset. That is what makes the comparison across compositions
    controlled."""
    kind: Literal["loop"]
    step_index: int
    point_index: int
    dx_m: float
    dy_m: float
    loop_settings: LoopSettings


def load_recipe(path: str | Path) -> Recipe:
    """Validate the YAML before anything touches the instrument."""
    return Recipe(**yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def site_program(recipe: Recipe) -> list[SiteMeasurement]:
    """Expand recipe.per_site into the ordered measurements for ONE site.

    Pure and deterministic. Each LoopStep carries its OWN loop_settings, so the
    settings must travel with the point — expanding points alone would silently
    apply the first step's waveform to every point of a multi-step recipe."""
    out: list[SiteMeasurement] = []
    for si, step in enumerate(recipe.per_site):
        if step.kind != "loop":
            raise ValueError(f"unsupported step kind {step.kind!r} at per_site[{si}]")
        for pi, (dx, dy) in enumerate(step.points_m):
            out.append(SiteMeasurement(
                kind=step.kind, step_index=si, point_index=pi,
                dx_m=dx, dy_m=dy, loop_settings=step.loop_settings))
    return out