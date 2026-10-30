import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Set

# Ensure parent directory is in sys.path when running script standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import INTERMEDIATE_DIR
from graph.state import PipelineState
from utils.json_io import save_json
from utils.mcp_client import fetch_news_via_mcp_sync

logger = logging.getLogger(__name__)


def news_fetch_node(state: PipelineState) -> Dict[str, Any]:
    """
    Agent 2 Node: News Fetch via MCP (7-day window, persona-agnostic).
    Reads `persona_profile["topics"]` from state, queries NewsAPI via MCP tool calls
    for top topics over the trailing 7-day window, deduplicates by article URL,
    saves `raw_articles.json` to intermediate data dir, and updates state.
    
    Args:
        state: PipelineState containing `persona_profile`.
        
    Returns:
        Dict update for state: {"raw_articles": deduped_list}
    """
    logger.info("--- Executing Agent 2: News Fetch via MCP (7-Day Window) ---")

    persona_profile = state.get("persona_profile", {})
    raw_topics = persona_profile.get("topics", [])
    
    # Normalize topics whether they are strings or dicts with 'keyword'/'weight'
    normalized_topics: List[str] = []
    if raw_topics:
        for t in raw_topics:
            if isinstance(t, dict) and "keyword" in t:
                normalized_topics.append(t["keyword"])
            elif isinstance(t, str) and t.strip():
                normalized_topics.append(t.strip())
            elif isinstance(t, dict) and "name" in t:
                normalized_topics.append(t["name"])

    if not normalized_topics:
        logger.warning("No topics found in persona_profile. Defaulting to 'technology'.")
        normalized_topics = ["technology"]

    # Cap topics to top 3-4 to manage rate limits & latency
    target_topics = normalized_topics[:4]
    
    # Calculate trailing 7 days date window
    now_utc = datetime.now(timezone.utc)
    from_date = (now_utc - timedelta(days=7)).strftime("%Y-%m-%d")
    logger.info(f"Agent 2 fetching news for topics: {target_topics} (from_date: {from_date})")

    aggregated_articles: List[Dict[str, Any]] = []
    seen_urls: Set[str] = set()

    for topic in target_topics:
        logger.info(f"Querying MCP News Server for topic: '{topic}' (window: >= {from_date})")
        try:
            response = fetch_news_via_mcp_sync(query=topic, from_date=from_date)
            articles = response.get("articles", [])
            logger.info(f"Topic '{topic}' returned {len(articles)} raw articles.")

            for article in articles:
                url = article.get("url", "").strip()
                # Deduplicate by URL
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    article_copy = dict(article)
                    article_copy["query_topic"] = topic
                    aggregated_articles.append(article_copy)
                elif not url:
                    # Keep article if URL is missing
                    aggregated_articles.append(dict(article))

        except Exception as e:
            logger.error(f"Error fetching news for topic '{topic}' via MCP: {e}")

    # Cap total raw articles to max 30
    max_article_cap = 30
    final_raw_articles = aggregated_articles[:max_article_cap]
    logger.info(f"Agent 2 aggregated {len(final_raw_articles)} unique raw articles.")

    # Save intermediate JSON snapshot
    output_path = INTERMEDIATE_DIR / "raw_articles.json"
    save_json(final_raw_articles, output_path)
    logger.info(f"Agent 2 finished successfully. Saved raw articles to {output_path}")

    return {"raw_articles": final_raw_articles}


if __name__ == "__main__":
    import json
    from dotenv import load_dotenv
    from utils.persona_loader import load_personas
    load_dotenv()

    personas = load_personas()
    test_persona = personas[0] if personas else {"topics": [{"keyword": "artificial intelligence", "weight": 0.9}]}

    print(f"--- Running Agent 2 Standalone Test for Persona: {test_persona.get('name')} ---")
    test_state: PipelineState = {"persona_profile": test_persona}
    res = news_fetch_node(test_state)

    raw_articles = res.get("raw_articles", [])
    print(f"\nFetched & Deduplicated Raw Articles Count: {len(raw_articles)}")
    if raw_articles:
        print("\nSample Article #1:")
        print(json.dumps(raw_articles[0], indent=2))
