from afm_lib.config import loops_dir
from afm_lib.states.analysis_state import AnalysisState
from afm_lib.utils.loops_utils import segment_sspfm_loops


async def build_loop_node(state: AnalysisState) -> AnalysisState:
    """Segment the SS-PFM bias waveform into in-field / out-of-field loops.
    Deterministic: output fully defined by the input file.
    Expects 'file_channels' with a Bias channel (guaranteed by the router)."""
    dest = loops_dir() / state.get("out_stem", "current")
    dest.mkdir(parents=True, exist_ok=True)

    loops = segment_sspfm_loops(channels=state["file_channels"], out_dir=dest)

    print(f"[build_loop] {sorted(loops['loops'])}, "
          f"{loops.get('n_pulses')} pulses -> {dest}")
    return {"loops": loops}      # type: ignore