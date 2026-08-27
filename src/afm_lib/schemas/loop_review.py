from typing import Literal, Optional
from pydantic import BaseModel, Field


class LoopReview(BaseModel, frozen=True):
    """Agentic double-check + interpretation of extracted loop parameters."""
    params_consistent: bool = Field(
        description="Do the overlaid Vc/remnant/branch markers match the data in the image?")
    loop_quality: Literal["good", "noisy", "unsaturated", "no_switching", "artifact"] = Field(
        description="Overall quality class of the off-field loop")
    is_ferroelectric_like: bool = Field(
        description="Does the off-field response show true polarization switching?")
    issues: list[str] = Field(
        description="Concrete problems observed")
    interpretation: str = Field(
        description="2-4 sentences: what this loop says about switching, imprint, disorder at this point")
    confidence: float = Field(ge=0, le=1)