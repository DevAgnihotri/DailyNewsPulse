import os
import sys
import pytest
from unittest.mock import patch

# Ensure parent directory is in sys.path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from graph.state import PipelineState
from agents.content_reshaping import reshaping_node


def test_reshaping_node_success(tmp_path):
    mock_state: PipelineState = {
        "persona_profile": {
            "name": "Finance & Markets Enthusiast",
            "tone": "analytical",
            "reading_level": "advanced",
            "depth": "detailed"
        },
        "filtered_articles": [
            {
                "title": "Quantum Computing Breakthrough Achieved",
                "description": "Scientists demonstrate photonic qubit synchronization.",
                "source": "TechDaily",
                "url": "https://example.com/quantum",
                "relevance_score": 0.95
            }
        ]
    }

    mock_llm_json_response = """
    {
      "reshaped_title": "Huge Quantum Computer Breakthrough",
      "bullets": [
        "Scientists connected quantum light particles across long distances.",
        "The discovery paves the way for scalable quantum networks.",
        "Future computing speeds could increase exponentially."
      ]
    }
    """

    with patch("agents.content_reshaping.get_llm_for_agent") as mock_get_llm, \
         patch("agents.content_reshaping.INTERMEDIATE_DIR", tmp_path):
        
        mock_get_llm.return_value = lambda sys_p, usr_p: mock_llm_json_response

        result = reshaping_node(mock_state)

        assert "reshaped_articles" in result
        reshaped = result["reshaped_articles"]
        assert len(reshaped) == 1
        item = reshaped[0]
        assert item["reshaped_title"] == "Huge Quantum Computer Breakthrough"
        assert isinstance(item["bullets"], list)
        assert len(item["bullets"]) == 3
        assert item["original_title"] == "Quantum Computing Breakthrough Achieved"
        assert item["original_url"] == "https://example.com/quantum"
        assert item["relevance_score"] == 0.95
        assert (tmp_path / "reshaped_articles.json").exists()


if __name__ == "__main__":
    pytest.main([__file__])
