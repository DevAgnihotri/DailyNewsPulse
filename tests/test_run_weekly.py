import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.run_weekly import generate_feed_for_persona, run_weekly_batch


def test_generate_feed_for_persona(tmp_path):
    mock_persona = {
        "persona_id": "tech_professional",
        "name": "Tech Professional",
        "topics": [{"keyword": "AI", "weight": 0.9}]
    }

    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "final_output": {
            "persona_id": "tech_professional",
            "total_articles": 5,
            "weekly_insight": "AI innovation continues."
        }
    }

    with patch("scripts.run_weekly.OUTPUT_DIR", tmp_path):
        result = generate_feed_for_persona(mock_persona, compiled_graph=mock_graph)
        assert result["persona_id"] == "tech_professional"
        assert (tmp_path / "final_output_tech_professional.json").exists()
        assert (tmp_path / "final_output.json").exists()


def test_run_weekly_batch_single_persona(tmp_path):
    mock_persona = {
        "persona_id": "tech_professional",
        "name": "Tech Professional",
        "topics": [{"keyword": "AI", "weight": 0.9}]
    }

    with patch("scripts.run_weekly.get_persona_by_id", return_value=mock_persona), \
         patch("scripts.run_weekly.generate_feed_for_persona", return_value={"persona_id": "tech_professional"}), \
         patch("scripts.run_weekly.OUTPUT_DIR", tmp_path):
        
        summary = run_weekly_batch(target_persona_id="tech_professional")
        assert summary["status"] == "completed"
        assert summary["successful_count"] == 1
        assert "tech_professional" in summary["successful_personas"]
