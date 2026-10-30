import os
import sys
import pytest

# Ensure parent directory is in sys.path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from graph.build_graph import get_compiled_graph, build_pipeline_graph


def test_build_pipeline_graph():
    graph = build_pipeline_graph()
    assert graph is not None
    
    # Verify singleton getter
    compiled = get_compiled_graph()
    assert compiled is not None
    
    # Verify nodes in the compiled graph
    graph_dict = graph.get_graph().nodes
    assert "news_fetch" in graph_dict
    assert "filtration_ranking" in graph_dict
    assert "content_reshaping" in graph_dict
    assert "insight_generator" in graph_dict
    assert "presentation_formatter" in graph_dict


if __name__ == "__main__":
    pytest.main([__file__])
