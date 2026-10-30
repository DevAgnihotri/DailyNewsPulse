import os
import sys
import pytest
from unittest.mock import patch

# Ensure parent directory is in sys.path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from graph.state import PipelineState
from agents.presentation_formatter import formatter_node, _calculate_read_time_bullets


def test_calculate_read_time_bullets():
    short_bullets = ["Hello world.", "This is a test."]
    assert _calculate_read_time_bullets(short_bullets) == 1

    long_bullets = [" ".join(["word"] * 250), " ".join(["word"] * 200)]
    assert _calculate_read_time_bullets(long_bullets) == 3


def test_formatter_node(tmp_path):
    mock_state: PipelineState = {
        "persona_profile": {
            "persona_id": "tech_professional",
            "name": "Tech Professional",
            "description": "Tech developers tracking news.",
            "topics": [{"keyword": "AI", "weight": 0.9}]
        },
        "weekly_insight": "AI innovation accelerated this week across foundational models and enterprise infrastructure.",
        "reshaped_articles": [
            {
                "reshaped_title": "AI Breakthrough",
                "bullets": ["New AI model unveiled.", "Speed improved by 2x."],
                "source": "TechCrunch",
                "original_url": "https://example.com/ai",
                "published_at": "2026-09-16",
                "query_topic": "AI",
                "relevance_score": 0.95
            },
            {
                "reshaped_title": "Quantum Experiment",
                "bullets": ["Photonic qubit test success."],
                "source": "ScienceDaily",
                "original_url": "https://example.com/quantum",
                "published_at": "2026-09-16",
                "query_topic": "Quantum Computing",
                "relevance_score": 0.88
            }
        ]
    }

    with patch("agents.presentation_formatter.OUTPUT_DIR", tmp_path):
        result = formatter_node(mock_state)

        assert "final_output" in result
        output = result["final_output"]
        assert output["persona_id"] == "tech_professional"
        assert output["persona_name"] == "Tech Professional"
        assert "week_start_date" in output
        assert "week_end_date" in output
        assert "weekly_insight" in output
        assert output["total_articles"] == 2
        assert output["total_categories"] == 2
        assert len(output["categories"]) == 2
        
        # Check first category article has bullets
        art = output["categories"][0]["articles"][0]
        assert "bullets" in art
        assert isinstance(art["bullets"], list)
        assert (tmp_path / "final_output.json").exists()


if __name__ == "__main__":
    pytest.main([__file__])
