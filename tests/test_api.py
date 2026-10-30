import os
import sys
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_serve_frontend_static_files(client):
    root_resp = client.get("/")
    assert root_resp.status_code == 200
    assert "PulsePersona" in root_resp.text

    css_resp = client.get("/style.css")
    assert css_resp.status_code == 200

    js_resp = client.get("/app.js")
    assert js_resp.status_code == 200


def test_get_personas(client):
    response = client.get("/personas")
    assert response.status_code == 200
    personas = response.json()
    assert isinstance(personas, list)
    assert len(personas) == 10
    assert any(p["persona_id"] == "tech_professional" for p in personas)


def test_get_feed_success(client, tmp_path):
    mock_feed = {
        "persona_id": "tech_professional",
        "persona_name": "Tech Professional",
        "persona_description": "Tech readers.",
        "week_start_date": "2026-09-09",
        "week_end_date": "2026-09-16",
        "weekly_insight": "Tech innovation summary for the week.",
        "total_articles": 1,
        "total_categories": 1,
        "categories": [
            {
                "topic": "AI",
                "count": 1,
                "articles": [
                    {
                        "title": "AI Breakthrough",
                        "bullets": ["Bullet 1", "Bullet 2"],
                        "source": "TechCrunch",
                        "url": "https://example.com/ai",
                        "published_at": "2026-09-16",
                        "relevance_score": 0.95,
                        "scoring_reason": "High relevance",
                        "read_time_minutes": 1,
                        "original_title": "Original"
                    }
                ]
            }
        ]
    }

    with patch("api.main.OUTPUT_DIR", tmp_path):
        from utils.json_io import save_json
        save_json(mock_feed, tmp_path / "final_output_tech_professional.json")

        response = client.get("/feed/tech_professional")
        assert response.status_code == 200
        data = response.json()
        assert data["persona_id"] == "tech_professional"
        assert len(data["categories"]) == 1
        assert data["categories"][0]["articles"][0]["bullets"] == ["Bullet 1", "Bullet 2"]


def test_get_feed_not_found(client, tmp_path):
    with patch("api.main.OUTPUT_DIR", tmp_path):
        response = client.get("/feed/non_existent_persona")
        assert response.status_code == 404


def test_record_feedback(client, tmp_path):
    feedback_file = tmp_path / "feedback.json"
    with patch("api.main.FEEDBACK_FILE_PATH", feedback_file):
        payload = {
            "persona_id": "tech_professional",
            "topic": "artificial intelligence",
            "action": "clicked"
        }
        response = client.post("/feedback", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert feedback_file.exists()


def test_trigger_weekly_run(client):
    with patch("api.main.run_weekly_batch") as mock_batch:
        response = client.post("/admin/run-weekly", json={"persona_id": "tech_professional"})
        assert response.status_code == 200
        assert response.json()["status"] == "accepted"
