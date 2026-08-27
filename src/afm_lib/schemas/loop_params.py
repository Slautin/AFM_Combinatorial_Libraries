# schemas/loop_params.py
from typing import Literal, Optional
from pydantic import BaseModel, Field


class LoopParams(BaseModel, frozen=True):
    """Hysteresis parameters of one SS-PFM loop, from extract_loop_params()."""

    # quadrature rotation / QC
    phase_offset_deg: Optional[float] = Field(
        description="PCA rotation angle applied to (X,Y); None if rotation disabled")
    quadrature_residual: Optional[float] = Field(
        description="std(Y')/std(X') after rotation; small = clean two-state switching")
    n_cycles: int = Field(ge=1, description="Number of bias cycles detected")
    branch_rms_noise: float = Field(
        ge=0, description="RMS scatter of points around cycle-averaged branches")

    # saturation / offset
    sat_at_vplus_m: float = Field(description="Mean response at V > 0.85*Vmax")
    sat_at_vminus_m: float = Field(description="Mean response at V < 0.85*Vmin")
    response_offset_m: float = Field(description="Vertical loop offset, (sat+ + sat-)/2")

    # switching
    v_c_rising: Optional[float] = Field(
        description="Coercive voltage on the rising branch, V; None if no crossing")
    v_c_falling: Optional[float] = Field(
        description="Coercive voltage on the falling branch, V; None if no crossing")
    imprint_v: Optional[float] = Field(description="(Vc_rise + Vc_fall)/2, V")
    loop_width_v: Optional[float] = Field(description="|Vc_rise - Vc_fall|, V")

    # remnant state
    remnant_rising_m: float = Field(description="Branch value at V=0, rising branch")
    remnant_falling_m: float = Field(description="Branch value at V=0, falling branch")
    loop_height_m: float = Field(ge=0, description="|remnant_falling - remnant_rising|")

    # area / direction
    loop_area_per_cycle: float = Field(
        ge=0, description="Enclosed area of the time-ordered path per cycle (shoelace)")
    direction: Literal["cw", "ccw"] = Field(description="Loop rotation sense")

    annotated_path: Optional[str] = Field(
        description=".png of the loop with branches, Vc, remnants and stats overlaid")