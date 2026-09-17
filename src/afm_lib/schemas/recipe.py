from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, Field, field_validator
from afm_lib.config import MODES, MODE_DART

from afm_lib.schemas.instrument import LoopSettings, ScanSettings


class SiteSpec(BaseModel, frozen=True):
    label: str
    x_stage_m: float
    y_stage_m: float


class LoopStep(BaseModel, frozen=True):
    """One or more hysteresis loops at tip positions inside the frame."""
    kind: Literal["loop"] = "loop"
    points_m: list[tuple[float, float]] = Field(
        description="Tip positions as offsets from the scan-frame centre, meters")
    loop_settings: LoopSettings

class ScanStep(BaseModel, frozen=True):
    """One topography frame."""
    kind: Literal["scan"] = "scan"
    scan_settings: ScanSettings

# `kind` in the YAML decides which model validates the step.
Step = Annotated[LoopStep | ScanStep, Field(discriminator="kind")]


class SampleFrame(BaseModel, frozen=True):
    """Sample coordinate system, declared in stage coordinates so that runs of
    different modalities on the same sample can be joined on (x_sample, y_sample).
    Applied at summary time (utils/summary.py); records stay in stage coordinates."""
    origin_stage_m: tuple[float, float] = Field(
        description="Stage position of the sample origin (e.g. a named electrode corner)")
    direction: Literal["x", "y"] | tuple[float, float] = Field(
        description='"x"/"y": sample +x parallel to that stage axis; or the stage position '
                    "of a second point on the sample +x axis")
    axis: Literal["x", "y"] = Field("x", description="Which sample axis the origin->direction line is")
    mirror: bool = Field(False, description="True if the stage image of the sample is mirrored")
    note: str = ""


class Recipe(BaseModel, frozen=True):
    """Immutable campaign definition. Loaded once, archived into the run dir."""
    name: str
    context: str = ""
    mode: str = MODE_DART
    sample_frame: SampleFrame | None = None 
    sites: list[SiteSpec]
    per_site: list[Step]

    @field_validator("mode")
    @classmethod
    def _known_mode(cls, v: str) -> str:
        if v not in MODES:
            raise ValueError(f"mode {v!r} unknown; known: {list(MODES)}")
        return v

class SiteMeasurement(BaseModel, frozen=True):
    """One measurement in a site's program — the expanded form of of a Step.

    dx_m / dy_m are offsets from the scan-frame centre. For a loop they place the
    tip; for a scan they place the frame. Exactly one of loop_settings /
    scan_settings is set, according to `kind`."""

    kind: Literal["loop", "scan"]
    step_index: int
    point_index: int
    dx_m: float
    dy_m: float
    loop_settings: LoopSettings | None = None
    scan_settings: ScanSettings | None = None


def load_recipe(path: str | Path) -> Recipe:
    """Validate the YAML before anything touches the instrument."""
    return Recipe(**yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def site_program(recipe: Recipe) -> list[SiteMeasurement]:
    """Expand recipe.per_site into the ordered measurements for ONE site.

    Pure and deterministic.Each step carries its own settings, so the settings
    travel with the point/frame."""
    out: list[SiteMeasurement] = []
    for si, step in enumerate(recipe.per_site):
        if step.kind == "loop":
            for pi, (dx, dy) in enumerate(step.points_m):
                out.append(SiteMeasurement(
                    kind="loop", step_index=si, point_index=pi,
                    dx_m=dx, dy_m=dy, loop_settings=step.loop_settings))
        elif step.kind == "scan":
            ss = step.scan_settings
            out.append(SiteMeasurement(
                kind="scan", step_index=si, point_index=0,
                dx_m=ss.x_scan_center_m, dy_m=ss.y_scan_center_m,   # offsets, see ScanStep
                scan_settings=ss))
        else:
            raise ValueError(f"unsupported step kind {step.kind!r} at per_site[{si}]")
    return out