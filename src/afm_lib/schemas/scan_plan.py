# from math import isclose
# from pydantic import BaseModel, Field

# from spm_agent.config import SCAN_SIZES_PX, SCAN_BOUNDS, LOCKED_SCAN_ALWAYS, LOCKED_SCAN_FRAME, LOCKED_EXC_ALWAYS, MIN_ZOOM_FACTOR, LOCK_REASON
# from spm_agent.schemas.instrument import ScanSettings, PFMExcitation, InstrumentState

# class ScanPlan(BaseModel, frozen=True):
#     """Target instrument configuration for the next scan. Reuses the instrument
#     read-models: the diff against the live state becomes the tool calls."""
#     diagnosis: str = Field(
#         description="1-3 sentences: what the previous scan's statistics, warnings and "
#                     "segmentation show about acquisition quality — not about the sample")
#     scan_settings: ScanSettings = Field(
#         description="Target scan geometry. Copy the locked fields unchanged from the "
#                     "current settings")
#     pfm_excitation: PFMExcitation = Field(
#         description="Target excitation params.")
#     reasoning: str = Field(
#         description="2-3 sentences: why each changed value follows from the diagnosis "
#                     "and from what the decision asked for")

# def enforce_locks(plan: ScanPlan, live: InstrumentState, frame_action: str) -> ScanPlan:
#     """Overwrite every locked field with the live value.

#     The plan may not move these, so *rejecting* it when the model restates them
#     imprecisely is a constraint the model cannot satisfy — the human message shows
#     the centre at .3f um (1 nm quantum), the size at .2f um (10 nm) and f_DART at
#     .1f kHz (100 Hz), while validate_plan compares at rel_tol=1e-6. The model has
#     never been shown the exact value. Enforce instead of reject: whatever it 'chose'
#     for a locked field was never going to be used anyway.

#     frame_action still decides WHAT is locked — scan_size_m is free under a zoom, so
#     zoom plans pass through untouched and validate_plan keeps policing MIN_ZOOM_FACTOR."""
#     lock_scan, lock_exc = locked_fields(frame_action)
#     return plan.model_copy(update={
#         "scan_settings":  plan.scan_settings.model_copy(
#             update={f: getattr(live.scan_settings, f) for f in lock_scan}),
#         "pfm_excitation": plan.pfm_excitation.model_copy(
#             update={f: getattr(live.pfm_excitation, f) for f in lock_exc}),
#     })

# def validate_plan(plan: ScanPlan, live: InstrumentState,
#                   frame_action: str, rel_tol: float = 1e-6) -> list[str]:
#     errors: list[str] = []
#     ss, pe = plan.scan_settings, plan.pfm_excitation
#     changed = plan_diff(plan, live, rel_tol)

#     if frame_action in ("zoom_in", "zoom_out"):
#         live_size = live.scan_settings.scan_size_m
#         ratio = live_size / ss.scan_size_m if ss.scan_size_m else float("inf")
#         if frame_action == "zoom_in" and ratio < MIN_ZOOM_FACTOR:
#             errors.append(f"zoom_in requires scan_size_m at least {MIN_ZOOM_FACTOR}x smaller "
#                           f"than {live_size:.6g} (got {ss.scan_size_m:.6g})")
#         if frame_action == "zoom_out" and ratio > 1 / MIN_ZOOM_FACTOR:
#             errors.append(f"zoom_out requires scan_size_m at least {MIN_ZOOM_FACTOR}x larger "
#                           f"than {live_size:.6g} (got {ss.scan_size_m:.6g})")
#     elif frame_action not in ("hold", "relocate"):
#         errors.append(f"frame_action={frame_action!r} is not supported yet")

#     lock_scan, lock_exc = locked_fields(frame_action)
#     for obj, ref, fields in ((ss, live.scan_settings, lock_scan),
#                              (pe, live.pfm_excitation, lock_exc)):
#         for f in fields:
#             got, want = getattr(obj, f), getattr(ref, f)
#             if not isclose(got, want, rel_tol=rel_tol):
#                 errors.append(f"{f} is locked — {LOCK_REASON[f]} "
#                               f"(got {got:.6g}, must stay {want:.6g})")

#     if "pixels" in changed and ss.pixels not in SCAN_SIZES_PX:
#         errors.append(f"pixels must be one of {SCAN_SIZES_PX}, got {ss.pixels}")

#     for obj, field in ((ss, "scan_rate_hz"), (ss, "scan_size_m"),
#                        (pe, "drive_amplitude_v"), (pe, "dart_width_hz"), (pe, "dart_igain")):
#         if field not in changed:
#             continue
#         lo, hi = SCAN_BOUNDS[field]
#         v = getattr(obj, field)
#         if not (lo <= v <= hi):
#             errors.append(f"{field}={v:.6g} outside [{lo:.6g}, {hi:.6g}]")

#     return errors

# def plan_diff(plan: ScanPlan, live: InstrumentState,
#               rel_tol: float = 1e-6) -> dict[str, float | int]:
#     """Target fields that differ from the live state, keyed by schema field name.
#     Empty means the plan repeats the current configuration."""
#     ss, pe = plan.scan_settings, plan.pfm_excitation
#     lss, lpe = live.scan_settings, live.pfm_excitation

#     diff: dict[str, float | int] = {}
#     if ss.pixels != lss.pixels:
#         diff["pixels"] = ss.pixels
#     for obj, ref, field in ((ss, lss, "scan_rate_hz"), (ss, lss, "scan_size_m"),
#                             (pe, lpe, "drive_amplitude_v"), (pe, lpe, "dart_width_hz"),
#                             (pe, lpe, "dart_igain")):
#         v = getattr(obj, field)
#         if not isclose(v, getattr(ref, field), rel_tol=rel_tol):
#             diff[field] = v
#     return diff

# def locked_fields(frame_action: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
#     """(scan_settings fields, pfm_excitation fields) the plan must copy unchanged.
#     Only a zoom may move the frame size: hold keeps the frame, and relocate carries
#     it to the neighbouring region — the step it took was one frame wide."""
#     scan = LOCKED_SCAN_ALWAYS + (LOCKED_SCAN_FRAME
#                                  if frame_action in ("hold", "relocate") else ())
#     return scan, LOCKED_EXC_ALWAYS