import os
import sys
import pytest
from unittest.mock import patch

# Ensure parent directory is in sys.path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from graph.state import PipelineState
from agents.news_fetch import news_fetch_node


def test_news_fetch_node_deduplication_and_capping(tmp_path):
    mock_state: PipelineState = {
        "persona_profile": {
            "topics": ["AI", "Robotics"]
        }
    }

    # Mock MCP response containing duplicates
    mock_mcp_response_ai = {
        "status": "ok",
        "articles": [
            {"title": "Article 1", "url": "https://example.com/1", "description": "AI news"},
            {"title": "Article 2", "url": "https://example.com/2", "description": "AI news 2"},
        ]
    }
    mock_mcp_response_robotics = {
        "status": "ok",
        "articles": [
            {"title": "Article 2 Duplicate", "url": "https://example.com/2", "description": "Duplicate URL"},
            {"title": "Article 3", "url": "https://example.com/3", "description": "Robotics news"},
        ]
    }

    def mock_fetch_news(query, **kwargs):
        if query == "AI":
            return mock_mcp_response_ai
        return mock_mcp_response_robotics

    with patch("agents.news_fetch.fetch_news_via_mcp_sync", side_effect=mock_fetch_news), \
         patch("agents.news_fetch.INTERMEDIATE_DIR", tmp_path):
        
        result = news_fetch_node(mock_state)

        assert "raw_articles" in result
        raw_articles = result["raw_articles"]
        # Article 2 duplicate URL should be removed -> total 3 unique articles
        assert len(raw_articles) == 3
        urls = [a["url"] for a in raw_articles]
        assert urls == ["https://example.com/1", "https://example.com/2", "https://example.com/3"]
        assert (tmp_path / "raw_articles.json").exists()


if __name__ == "__main__":
    pytest.main([__file__])
