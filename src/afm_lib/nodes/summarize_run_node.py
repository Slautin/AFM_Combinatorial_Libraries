from afm_lib.config import run_dir
from afm_lib.states.lib_experiment_state import LibExperimentState
from afm_lib.utils.summary import write_run_summary


async def summarize_run_node(state: LibExperimentState) -> LibExperimentState:
    """Consolidate the finished run into summary.json + results.csv."""
    write_run_summary(run_dir())
    return {}