import logging
import os
import sys

# Ensure parent directory is in sys.path when running script standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langgraph.graph import StateGraph, END
from graph.state import PipelineState
from agents.news_fetch import news_fetch_node
from agents.filtration_ranking import filtration_node
from agents.content_reshaping import reshaping_node
from agents.insight_generator import insight_generator_node
from agents.presentation_formatter import formatter_node

logger = logging.getLogger(__name__)


def build_pipeline_graph():
    """
    Assembles and compiles the refactored weekly news generation pipeline:
    news_fetch -> filtration_ranking -> content_reshaping -> insight_generator -> presentation_formatter -> END
    
    Returns:
        Compiled LangGraph runnable state graph.
    """
    logger.info("Initializing LangGraph StateGraph pipeline (Weekly Batch Architecture)...")
    builder = StateGraph(PipelineState)

    # Register the Node functions
    builder.add_node("news_fetch", news_fetch_node)
    builder.add_node("filtration_ranking", filtration_node)
    builder.add_node("content_reshaping", reshaping_node)
    builder.add_node("insight_generator", insight_generator_node)
    builder.add_node("presentation_formatter", formatter_node)

    # Wire linear execution edges starting directly at news_fetch
    builder.set_entry_point("news_fetch")
    builder.add_edge("news_fetch", "filtration_ranking")
    builder.add_edge("filtration_ranking", "content_reshaping")
    builder.add_edge("content_reshaping", "insight_generator")
    builder.add_edge("insight_generator", "presentation_formatter")
    builder.add_edge("presentation_formatter", END)

    # Compile into runnable graph object
    compiled_graph = builder.compile()
    logger.info("LangGraph pipeline successfully assembled and compiled.")
    return compiled_graph


# Singleton compiled graph instance for reuse
compiled_graph = build_pipeline_graph()


def get_compiled_graph():
    """Returns the compiled LangGraph pipeline instance."""
    return compiled_graph


if __name__ == "__main__":
    print("--- LangGraph Assembly Test ---")
    graph = get_compiled_graph()
    print("Compiled Graph Object:", graph)
    try:
        mermaid_ascii = graph.get_graph().draw_mermaid()
        print("\nMermaid Graph Flow Diagram:")
        print(mermaid_ascii)
    except Exception as e:
        print(f"Graph mermaid visualization note: {e}")
