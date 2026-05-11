"""
LangGraph analysis pipeline for Claw productivity tracking.

Graph flow:
  ingest → classify → [retry → ingest | continue] → goal_tracker
         → pattern_analyzer → insight_generator → report_writer
"""
from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from claw.pipeline.state import ProductivityState
from claw.pipeline.nodes import (
    ingest,
    classify,
    needs_more_data,
    goal_tracker,
    pattern_analyzer,
    insight_generator,
    report_writer,
)

# ---- helper for retry counter ------------------------------------------------

def _increment_retry(state: ProductivityState) -> dict:
    return {"retry_count": state.retry_count + 1}


# ---- build the graph ---------------------------------------------------------

_builder = StateGraph(ProductivityState)

_builder.add_node("ingest", ingest)
_builder.add_node("classify", classify)
_builder.add_node("increment_retry", _increment_retry)
_builder.add_node("goal_tracker", goal_tracker)
_builder.add_node("pattern_analyzer", pattern_analyzer)
_builder.add_node("insight_generator", insight_generator)
_builder.add_node("report_writer", report_writer)

# Entry point
_builder.add_edge(START, "ingest")
_builder.add_edge("ingest", "classify")

# Conditional cycle: retry ingest if data confidence is low
_builder.add_conditional_edges(
    "classify",
    needs_more_data,
    {
        "retry": "increment_retry",
        "continue": "goal_tracker",
    },
)
_builder.add_edge("increment_retry", "ingest")

# Main flow
_builder.add_edge("goal_tracker", "pattern_analyzer")
_builder.add_edge("pattern_analyzer", "insight_generator")
_builder.add_edge("insight_generator", "report_writer")
_builder.add_edge("report_writer", END)

# Compiled graph — exposed for langgraph_wrapper and direct invocation
compiled_graph = _builder.compile()
