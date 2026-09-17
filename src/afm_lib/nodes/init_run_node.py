from afm_lib.config import new_run
from afm_lib.states.lib_experiment_state import LibExperimentState
from afm_lib.schemas.recipe import site_program


async def init_run_node(state: LibExperimentState) -> LibExperimentState:
    """Open a run directory, archive the recipe, expand its sites into runtime state.
    Pure — touches no instrument. The recipe is loaded by the caller so a YAML error
    fails before the graph starts."""
    recipe = state["recipe"]
    d = new_run(recipe.name)
    (d / "recipe.json").write_text(recipe.model_dump_json(indent=2), encoding="utf-8")

    sites = [{"index": i,
              "x_stage_m": s.x_stage_m,
              "y_stage_m": s.y_stage_m,
              "label": s.label,
              "status": "pending"}
             for i, s in enumerate(recipe.sites)]

    n_meas = len(site_program(recipe))
    print(f"[init_run] {recipe.name}: {len(sites)} sites x {n_meas} measurements "
          f"= {len(sites) * n_meas} total -> {d}")

    return {"sites": sites, "site_index": -1}