from __future__ import annotations

from typing import Dict, Any
from langgraph.graph import StateGraph, START, END

from src.agents.nodes_dummy import (
    master_node,
    imageops_node,
    compliance_node,
    exporter_node,
    summarizer_node,
)
from src.agents.copy_validator_agent import run_copy_validator
from src.agents.layout_planner_agent import run_layout_planner
from src.graph.routers import (
    route_after_master,
    route_after_copy,
    route_after_layout,
    route_after_compliance,
)


def build_graph() -> "StateGraph":
    """
    Phase 4G Graph with smart retry logic:
    - START -> master
    - master -> (skip to imageops if copy+layout OK, else copy_validator)
    - copy_validator -> (retry copy OR proceed to layout OR give up to summarizer)
    - layout_planner -> (retry layout OR proceed to imageops OR give up to summarizer)
    - imageops -> compliance
    - compliance -> (pass to exporter OR retry specific node OR give up to summarizer)
    - exporter -> summarizer -> END
    """
    g = StateGraph(dict)  # state is a Dict[str, Any]

    # Add all nodes (using real agent functions for copy/layout, node wrappers for others)
    g.add_node("master", master_node)
    g.add_node("copy_validator", run_copy_validator)
    g.add_node("layout_planner", run_layout_planner)
    g.add_node("imageops", imageops_node)
    g.add_node("compliance", compliance_node)
    g.add_node("exporter", exporter_node)
    g.add_node("summarizer", summarizer_node)

    # Entry point
    g.add_edge(START, "master")

    # Phase 4G: Smart routing at each stage
    g.add_conditional_edges(
        "master",
        route_after_master,
        {
            "copy_validator": "copy_validator",
            "imageops": "imageops",
        },
    )

    g.add_conditional_edges(
        "copy_validator",
        route_after_copy,
        {
            "copy_validator": "copy_validator",
            "layout_planner": "layout_planner",
            "summarizer": "summarizer",
        },
    )

    g.add_conditional_edges(
        "layout_planner",
        route_after_layout,
        {
            "layout_planner": "layout_planner",
            "imageops": "imageops",
            "summarizer": "summarizer",
        },
    )

    # imageops always goes to compliance
    g.add_edge("imageops", "compliance")

    # Compliance: smart retry or proceed
    g.add_conditional_edges(
        "compliance",
        route_after_compliance,
        {
            "exporter": "exporter",
            "copy_validator": "copy_validator",
            "layout_planner": "layout_planner",
            "imageops": "imageops",
            "summarizer": "summarizer",
        },
    )

    # Final stages
    g.add_edge("exporter", "summarizer")
    g.add_edge("summarizer", END)

    return g
