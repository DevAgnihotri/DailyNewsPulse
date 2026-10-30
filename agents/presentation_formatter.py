import math
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List

# Ensure parent directory is in sys.path when running script standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import OUTPUT_DIR
from graph.state import PipelineState
from utils.json_io import save_json

logger = logging.getLogger(__name__)


def _calculate_read_time_bullets(bullets: List[str]) -> int:
    """Calculates estimated read time in minutes for bullet points (average 200 words/min)."""
    if not bullets:
        return 1
    total_words = sum(len(b.split()) for b in bullets if isinstance(b, str))
    minutes = math.ceil(total_words / 200)
    return max(1, minutes)


def formatter_node(state: PipelineState) -> Dict[str, Any]:
    """
    Agent 5 Node: Presentation Formatter.
    Deterministic node that formats weekly dates, attaches `weekly_insight`,
    groups bulleted reshaped articles by category, calculates read time,
    assembles the final schema payload for the Frontend, saves to `final_output.json`,
    and updates state.
    
    Args:
        state: PipelineState containing `reshaped_articles`, `weekly_insight`, and `persona_profile`.
        
    Returns:
        Dict update for state: {"final_output": final_output_dict}
    """
    logger.info("--- Executing Agent 5: Presentation Formatter (Metadata + Insight + Bullets) ---")

    reshaped_articles = state.get("reshaped_articles", [])
    persona_profile = state.get("persona_profile", {})
    weekly_insight = state.get("weekly_insight", "")

    # Calculate weekly date window (trailing 7 days)
    now_utc = datetime.now(timezone.utc)
    week_end_date = now_utc.strftime("%Y-%m-%d")
    week_start_date = (now_utc - timedelta(days=7)).strftime("%Y-%m-%d")

    # Group articles by topic category
    categories_map: Dict[str, List[Dict[str, Any]]] = {}

    for article in reshaped_articles:
        topic = article.get("query_topic", "General News")
        title_text = article.get("reshaped_title") or article.get("title", "")
        bullets = article.get("bullets", [])
        if not isinstance(bullets, list) or len(bullets) == 0:
            desc = article.get("description") or article.get("original_description", "")
            bullets = [desc] if desc else ["Details available in full article."]

        read_time = _calculate_read_time_bullets(bullets)

        formatted_article = {
            "title": title_text,
            "bullets": bullets,
            "source": article.get("source", "Unknown Source"),
            "url": article.get("original_url") or article.get("url", ""),
            "published_at": article.get("published_at", ""),
            "relevance_score": article.get("relevance_score", 0.70),
            "scoring_reason": article.get("scoring_reason", ""),
            "read_time_minutes": read_time,
            "original_title": article.get("original_title", "")
        }

        categories_map.setdefault(topic, []).append(formatted_article)

    # Format categories array
    categories_list: List[Dict[str, Any]] = []
    for topic_name, articles_in_topic in categories_map.items():
        # Sort articles within topic by relevance score descending
        articles_in_topic.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)
        categories_list.append({
            "topic": topic_name,
            "count": len(articles_in_topic),
            "articles": articles_in_topic
        })

    # Sort categories alphabetically by topic name
    categories_list.sort(key=lambda c: c["topic"])

    # Construct final output schema payload
    persona_id = persona_profile.get("persona_id", "custom_persona")
    persona_name = persona_profile.get("name", "Valued Reader")
    persona_desc = persona_profile.get("description", "")

    final_output = {
        "persona_id": persona_id,
        "persona_name": persona_name,
        "persona_description": persona_desc,
        "week_start_date": week_start_date,
        "week_end_date": week_end_date,
        "weekly_insight": weekly_insight,
        "total_articles": len(reshaped_articles),
        "total_categories": len(categories_list),
        "categories": categories_list
    }

    # Save output to data/output/final_output.json
    output_path = OUTPUT_DIR / "final_output.json"
    save_json(final_output, output_path)
    logger.info(f"Agent 5 finished successfully. Final output saved to {output_path}")

    return {"final_output": final_output}


if __name__ == "__main__":
    import json
    from utils.json_io import load_json
    from utils.persona_loader import load_personas
    from config.settings import INTERMEDIATE_DIR

    personas = load_personas()
    test_persona = personas[0] if personas else {"persona_id": "tech_professional", "name": "Tech Professional"}

    reshaped_path = INTERMEDIATE_DIR / "reshaped_articles.json"
    insight_path = INTERMEDIATE_DIR / "weekly_insight.json"

    if reshaped_path.exists():
        reshaped = load_json(reshaped_path)
    else:
        reshaped = [{
            "reshaped_title": "AI Model Breakthrough",
            "bullets": ["Researchers release faster neural network model.", "Efficiency improved by 40%."],
            "source": "TechCrunch",
            "original_url": "https://techcrunch.com/1",
            "query_topic": "Artificial Intelligence",
            "relevance_score": 0.95
        }]

    weekly_insight_text = load_json(insight_path).get("weekly_insight", "Weekly synthesis...") if insight_path.exists() else "Weekly AI developments accelerated this week."

    print("--- Running Agent 5 Standalone Test ---")
    test_state: PipelineState = {
        "persona_profile": test_persona,
        "weekly_insight": weekly_insight_text,
        "reshaped_articles": reshaped
    }

    res = formatter_node(test_state)
    output = res.get("final_output", {})

    print(f"\nPersona: {output.get('persona_name')} ({output.get('persona_id')})")
    print(f"Week: {output.get('week_start_date')} to {output.get('week_end_date')}")
    print(f"Weekly Insight: {output.get('weekly_insight')}")
    print(f"Total Articles: {output.get('total_articles')}")
    print("\nPreview JSON:\n", json.dumps(output, indent=2)[:500], "...")
