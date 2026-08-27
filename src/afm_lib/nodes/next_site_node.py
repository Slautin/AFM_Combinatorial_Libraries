from afm_lib.states.lib_experiment_state import LibExperimentState


async def next_site_node(state: LibExperimentState) -> LibExperimentState:
    """Advance the site cursor. The only node that touches `sites`/`site_index`.

    Deterministic — the recipe fixes the order. Marks the site just finished as
    done before moving on; a failed site is marked by whoever caught the failure,
    not here."""
    i = state["site_index"]
    sites = [dict(s) for s in state["sites"]]

    if 0 <= i < len(sites) and sites[i]["status"] == "pending":
        sites[i]["status"] = "done"

    i += 1
    if i < len(sites):
        s = sites[i]
        print(f"[next_site] {i + 1}/{len(sites)}  {s.get('label', '?')} -> "
              f"({s['x_stage_m'] * 1e3:+.3f}, {s['y_stage_m'] * 1e3:+.3f}) mm")
    else:
        n_done = sum(1 for s in sites if s["status"] == "done")
        print(f"[next_site] all sites visited ({n_done} done, "
              f"{sum(1 for s in sites if s['status'] == 'failed')} failed)")

    return {"sites": sites, "site_index": i}


def route_after_next_site(state: LibExperimentState) -> str:
    return "site" if state["site_index"] < len(state["sites"]) else "done"