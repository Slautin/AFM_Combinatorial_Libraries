from langgraph.graph import StateGraph, START, END

from afm_lib.states.lib_experiment_state import LibExperimentState
from afm_lib.nodes.init_run_node import init_run_node
from afm_lib.nodes.preflight_node import preflight_node
from afm_lib.nodes.calibrate_frame_node import calibrate_frame_node
from afm_lib.nodes.sync_status_node import sync_status_node
from afm_lib.nodes.next_site_node import next_site_node, route_after_next_site
from afm_lib.graphs.measure_site import build_measure_site_graph
from afm_lib.nodes.summarize_run_node import summarize_run_node


def build_grid_search_graph():
    g = StateGraph(LibExperimentState)
    g.add_node("init_run",        init_run_node)
    g.add_node("preflight",       preflight_node)
    g.add_node("calibrate_frame", calibrate_frame_node)
    g.add_node("sync_status",     sync_status_node)
    g.add_node("next_site",       next_site_node)
    g.add_node("measure_site",    build_measure_site_graph())
    g.add_node("summarize_run",   summarize_run_node)

    g.add_edge(START,             "init_run")
    g.add_edge("init_run",        "preflight")
    g.add_edge("preflight",       "calibrate_frame")
    g.add_edge("calibrate_frame", "sync_status")
    g.add_edge("sync_status",     "next_site")
    g.add_conditional_edges("next_site", route_after_next_site,
                            {"site": "measure_site", "done": "summarize_run"})
    
    g.add_edge("measure_site", "next_site")
    g.add_edge("summarize_run", END)

    return g.compile()