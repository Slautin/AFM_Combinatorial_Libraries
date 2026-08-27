from langgraph.graph import StateGraph, START, END

from afm_lib.states.lib_experiment_state import LibExperimentState
from afm_lib.nodes.next_measurement_node import (
    next_measurement_node, route_after_next_measurement)
from afm_lib.nodes.ensure_stage_node import ensure_stage_node
from afm_lib.nodes.ensure_tip_node import ensure_tip_node
from afm_lib.nodes.run_loop_node import run_loop_node
from afm_lib.nodes.sync_status_node import sync_status_node
from afm_lib.nodes.record_measurement_node import record_measurement_node


def build_measure_site_graph():
    """Execute one site's program. Reusable: every node below reads `pending`,
    so a different top-level driver (adaptive site choice, an LLM) reuses this
    unchanged."""
    g = StateGraph(LibExperimentState)
    g.add_node("next_measurement", next_measurement_node)
    g.add_node("ensure_stage",     ensure_stage_node)
    g.add_node("ensure_tip",       ensure_tip_node)
    g.add_node("run_loop",         run_loop_node)
    g.add_node("sync_status",      sync_status_node)
    g.add_node("record",           record_measurement_node)

    g.add_edge(START, "next_measurement")
    g.add_conditional_edges("next_measurement", route_after_next_measurement,
                            {"measure": "ensure_stage", "site_done": END})
    g.add_edge("ensure_stage", "ensure_tip")
    g.add_edge("ensure_tip",   "run_loop")
    g.add_edge("run_loop",     "sync_status")
    g.add_edge("sync_status",  "record")
    g.add_edge("record",       "next_measurement")
    return g.compile()