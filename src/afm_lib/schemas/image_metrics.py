from pydantic import BaseModel, Field


class ImageMetrics(BaseModel, frozen=True):
    """Scalar descriptors of one topography frame (the scan analogue of LoopParams).
    All lengths in metres. Computed by utils/image_utils.analyse_frame."""
    # roughness — line-flattened height
    rq_m: float = Field(description="RMS roughness")
    ra_m: float = Field(description="mean absolute roughness")
    pv_m: float = Field(description="peak-to-valley between the 1st and 99th height percentile")
    skewness: float = Field(description="height skewness: >0 peaks/particles, <0 pits")
    kurtosis: float = Field(description="excess kurtosis: 0 Gaussian, >0 spiky (particles)")
    # levels — plane-flattened height
    n_levels: int = Field(description="modes of the height histogram; >1 = terraces or multi-level grains")
    level_spacing_m: float = Field(description="height difference of the two strongest modes; 0 if one level")
    # lateral scale
    corr_length_m: float = Field(description="1/e radius of the height autocorrelation (feature scale)")
    psd_slope: float = Field(description="log-log slope of the radial PSD in the mid band")
    psd_knee_m: float = Field(description="wavelength where the PSD leaves its low-frequency plateau")
    # grains — watershed on the smoothed height, edge-touching grains excluded
    grain_count: int
    grain_radius_median_m: float = Field(description="median equivalent radius (area-based)")
    grain_radius_iqr_m: float = Field(description="interquartile range of the equivalent radius")
    grain_radius_mean_m: float
    grain_radius_std_m: float
    grain_height_std_m: float = Field(description="spread of per-grain mean height (level spread between grains)")
    grain_coverage: float = Field(description="fraction of the frame covered by interior grains")
    # tracking quality — no calibration needed
    amp_rel_std: float | None = Field(None, description="std/mean of the amplitude channel; large = tip not tracking")
    phase_std_deg: float | None = Field(None, description="std of the phase channel")