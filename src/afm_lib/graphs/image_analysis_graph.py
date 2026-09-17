from langgraph.graph import StateGraph, START, END

from afm_lib.states.analysis_state import AnalysisState
from afm_lib.nodes.readfile_node import readfile_node
from afm_lib.nodes.image_metrics_node import image_metrics_node


def _route_by_kind(state: AnalysisState) -> str:
    return "image" if state.get("kind") == "image" else "other"


def build_image_analysis_graph():
    """Deterministic frame analysis: read -> scalar descriptors.
    Mirror of loop_analysis_graph for scans."""
    g = StateGraph(AnalysisState)
    g.add_node("readfile",      readfile_node)
    g.add_node("image_metrics", image_metrics_node)

    g.add_edge(START, "readfile")
    g.add_conditional_edges("readfile", _route_by_kind,
                            {"image": "image_metrics", "other": END})
    g.add_edge("image_metrics", END)
    return g.compile()