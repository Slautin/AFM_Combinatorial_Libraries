from typing_extensions import TypedDict, NotRequired
from typing import Literal

from afm_lib.schemas.loop_params import LoopParams        # note: loop_params, not loops_params
from afm_lib.schemas.loop_review import LoopReview


#channels schemes
class ChannelStats(TypedDict):
    min: float
    max: float
    mean: float
    std: float
    p01: float
    p99: float

class Channel(TypedDict):
    title: str
    units: str
    data_type: str
    shape: list
    preview_path: str
    array_path: str
    stats: ChannelStats

#scan schemes
# class SegmentationResult(TypedDict):
#     task: str                 # joins back to channel_recommendations
#     channel: str              # channel ID the agent worked on
#     mask_path: str            # .npy boolean mask  (the pixels live here, not in state)
#     overlay_path: str         # .png preview + red mask, for human/inspection
#     n_regions: int            # connected components in the final mask
#     coverage: float           # fraction of pixels masked (0..1)
#     ops: list                 # ordered tool log = the reproducible "program"
#     reasoning: str            # agent's final justification

# class ImportanceMapResult(TypedDict):
#     experiment_task: str            # free-form goal — lives HERE, per your point
#     components_path: str        # .npy, pixel grid
#     components_json_path: str
#     components_meta: ComponentsMeta

#     task_map_path: str              # equal-weight overview of the task criteria, 0..100
#     safety_map_path: str            # safety [0,1]
#     safety_json_path: str           
#     safety_meta: SafetyMeta         
#     importance_map_path: str        # task x safety — digest figure + no-criterion fallback 

#     scoring_code_path: str
#     reasoning: str
#     figures: list[str]
#     warnings: list[str]             # advisory validation findings, kept not raised

#loop schemes
class LoopChannel(TypedDict):
    on_path: str          # .npy, in-field response
    off_path: str         # .npy, out-of-field response
    units: str
    n_points: int

class LoopData(TypedDict):
    bias_on_path: str     # x-axis for in-field loops
    bias_off_path: str    # x-axis for out-of-field loops (= preceding pulse)
    loops: dict[str, LoopChannel]
    overview_path: str    # .png for vision review
    n_pulses: int
    

class CriteriaSegmentationResult(TypedDict):
    experiment_task: str
    labels_path: str            # int16 (H, W) class-label map
    criteria_json_path: str
    #criteria_meta: "CriteriaMeta"
    criteria_code_path: str
    reasoning: str
    figures: list[str]

#main analysis state

class AnalysisState(TypedDict):
    file_path: str
    experiment_tasks: NotRequired[list[str]] 
    experiment_context: NotRequired[str]
    scan_index: NotRequired[int]
    decision_index: NotRequired[int]
    out_stem: NotRequired[str]      # per-measurement artifact directory name

    # --- readfile ---
    file_channels: NotRequired[dict[str, Channel]]
    kind: NotRequired[Literal["spectrum", "loop", "image"]]
    preview_grid_path: NotRequired[str]  

    #scan branch
    # channel_recommendations: NotRequired[TaskChannelReccomendationReport]
    # channel_recommendations_path: NotRequired[str]
    # segmentation_results: NotRequired[dict[str, SegmentationResult]]
    # importance_maps: NotRequired[list[ImportanceMapResult]] 

    #loop branch
    loops: NotRequired[LoopData]
    loop_params: NotRequired[dict[str, LoopParams]] 
    loop_review: NotRequired[LoopReview]
