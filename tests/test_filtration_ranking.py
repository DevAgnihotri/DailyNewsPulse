import os
import sys
import pytest
from unittest.mock import patch

# Ensure parent directory is in sys.path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from graph.state import PipelineState
from agents.filtration_ranking import filtration_node, _exclude_keyword_filter, _deduplicate_similar_titles


def test_exclude_keyword_filter():
    raw_articles = [
        {"title": "Breakthrough in AI Research", "description": "New AI model unveiled"},
        {"title": "Celebrity Gossip Update", "description": "Hollywood news"},
        {"title": "Space Rocket Launch", "description": "Latest rocket launch update"}
    ]
    exclude_topics = ["Gossip", "Hollywood"]

    filtered = _exclude_keyword_filter(raw_articles, exclude_topics)
    assert len(filtered) == 2
    titles = [a["title"] for a in filtered]
    assert "Celebrity Gossip Update" not in titles


def test_deduplicate_similar_titles():
    articles = [
        {"title": "New AI Model Released by Tech Giant", "relevance_score": 0.9},
        {"title": "New AI Model Released By Tech Giant!", "relevance_score": 0.8},
        {"title": "Completely Different Story on Space", "relevance_score": 0.85}
    ]

    deduped = _deduplicate_similar_titles(articles, similarity_threshold=0.8)
    assert len(deduped) == 2
    titles = [a["title"] for a in deduped]
    assert "New AI Model Released by Tech Giant" in titles
    assert "New AI Model Released By Tech Giant!" not in titles


def test_filtration_node_with_mock_gemini(tmp_path):
    mock_state: PipelineState = {
        "persona_profile": {
            "topics": ["Artificial Intelligence"],
            "exclude_topics": ["Gossip"],
            "tone": "concise",
            "reading_level": "intermediate",
            "depth": "summary"
        },
        "raw_articles": [
            {"title": "AI Breakthrough in 2026", "description": "Deep learning milestone", "url": "http://ex.com/1"},
            {"title": "Celebrity Gossip News", "description": "Hollywood story", "url": "http://ex.com/2"},
            {"title": "Robotics Advancements", "description": "New robots created", "url": "http://ex.com/3"}
        ]
    }

    mock_gemini_json_response = """
    [
      {"index": 0, "relevance_score": 0.95, "reason": "High relevance to AI"},
      {"index": 1, "relevance_score": 0.60, "reason": "Moderate relevance"}
    ]
    """

    with patch("agents.filtration_ranking.get_llm_for_agent") as mock_get_llm, \
         patch("agents.filtration_ranking.INTERMEDIATE_DIR", tmp_path):
        
        mock_get_llm.return_value = lambda sys_p, usr_p: mock_gemini_json_response

        result = filtration_node(mock_state)

        assert "filtered_articles" in result
        filtered = result["filtered_articles"]
        # Excluded Gossip -> 2 remaining articles
        assert len(filtered) == 2
        assert filtered[0]["title"] == "AI Breakthrough in 2026"
        assert filtered[0]["relevance_score"] == 0.95
        assert (tmp_path / "filtered_articles.json").exists()


if __name__ == "__main__":
    pytest.main([__file__])
