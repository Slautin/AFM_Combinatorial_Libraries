from langgraph.graph import StateGraph, START, END

from afm_lib.states.analysis_state import AnalysisState
from afm_lib.nodes.readfile_node import readfile_node
from afm_lib.nodes.build_loop_node import build_loop_node
from afm_lib.nodes.loop_params_node import loop_params_node


def _route_by_kind(state: AnalysisState) -> str:
    return "loop" if state.get("kind") == "loop" else "other"


def build_loop_analysis_graph():
    """Deterministic loop analysis: read -> segment -> extract parameters.
    The simple agent's loop branch minus loop_review, its LLM vision QC."""
    g = StateGraph(AnalysisState)
    g.add_node("readfile",    readfile_node)
    g.add_node("build_loop",  build_loop_node)
    g.add_node("loop_params", loop_params_node)

    g.add_edge(START, "readfile")
    g.add_conditional_edges("readfile", _route_by_kind,
                            {"loop": "build_loop", "other": END})
    g.add_edge("build_loop", "loop_params")
    g.add_edge("loop_params", END)
    return g.compile()