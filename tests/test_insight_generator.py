import os
import sys
import pytest
from unittest.mock import patch

# Ensure parent directory is in sys.path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from graph.state import PipelineState
from agents.insight_generator import insight_generator_node


def test_insight_generator_node_success(tmp_path):
    mock_state: PipelineState = {
        "persona_profile": {
            "persona_id": "tech_professional",
            "name": "Tech Professional",
            "description": "Engineers and developers tracking tech trends.",
            "topics": [{"keyword": "AI", "weight": 0.9}]
        },
        "reshaped_articles": [
            {
                "reshaped_title": "AI Breakthrough Announced",
                "bullets": ["New neural network scales compute efficiency.", "Benchmark records broken."],
                "source": "TechDaily"
            }
        ]
    }

    mock_llm_insight = "This week in technology, generative intelligence advancements dominated the conversation. Compute optimizations reached new benchmarks, providing engineering teams with scalable tools. Strategic investments in infrastructure indicate long-term enterprise commitment. Monitoring these efficiency shifts remains critical for engineering leaders."

    with patch("agents.insight_generator.get_llm_for_agent") as mock_get_llm, \
         patch("agents.insight_generator.INTERMEDIATE_DIR", tmp_path):
        
        mock_get_llm.return_value = lambda sys_p, usr_p: mock_llm_insight

        result = insight_generator_node(mock_state)

        assert "weekly_insight" in result
        assert isinstance(result["weekly_insight"], str)
        assert len(result["weekly_insight"]) > 50
        assert "generative intelligence" in result["weekly_insight"]
        assert (tmp_path / "weekly_insight.json").exists()


if __name__ == "__main__":
    pytest.main([__file__])
