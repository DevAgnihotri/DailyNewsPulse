import json
import logging
import os
import re
import sys
from difflib import SequenceMatcher
from typing import Dict, Any, List

# Ensure parent directory is in sys.path when running script standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import INTERMEDIATE_DIR
from graph.state import PipelineState
from utils.json_io import save_json
from utils.llm_clients import get_llm_for_agent, clean_markdown_code_fences

logger = logging.getLogger(__name__)

# --- AGENT 3 GEMINI RELEVANCE SCORING PROMPT DESIGN ---
FILTRATION_RANKING_SYSTEM_PROMPT = """You are an expert Content Relevance Ranker AI for a personalized news engine.
Your job is to evaluate a batch of news articles against a user's target persona profile and score each article's relevance.

CRITICAL INSTRUCTIONS:
1. Output ONLY a raw valid JSON array.
2. DO NOT include markdown formatting (no ```json code fences), preamble, or postscript.
3. Score each article from 0.00 (completely irrelevant) to 1.00 (highly relevant and interesting).

TARGET JSON ARRAY SCHEMA:
[
  {
    "index": 0,
    "relevance_score": 0.95,
    "reason": "Directly covers target topics with high relevance"
  },
  ...
]
"""


def _exclude_keyword_filter(articles: List[Dict[str, Any]], exclude_topics: List[Any]) -> List[Dict[str, Any]]:
    """Cheap pre-filtering step: removes articles containing excluded keywords in title or description."""
    if not exclude_topics:
        return articles

    clean_excludes: List[str] = []
    for k in exclude_topics:
        if isinstance(k, str) and k.strip():
            clean_excludes.append(k.strip().lower())
        elif isinstance(k, dict) and "keyword" in k:
            clean_excludes.append(k["keyword"].strip().lower())

    if not clean_excludes:
        return articles

    filtered: List[Dict[str, Any]] = []
    for art in articles:
        text_to_check = f"{art.get('title', '')} {art.get('description', '')}".lower()
        if any(exc in text_to_check for exc in clean_excludes):
            logger.info(f"Pre-filter excluded article: '{art.get('title')}' due to excluded keyword match.")
            continue
        filtered.append(art)
    return filtered


def _deduplicate_similar_titles(articles: List[Dict[str, Any]], similarity_threshold: float = 0.8) -> List[Dict[str, Any]]:
    """Deduplicates near-identical article titles using SequenceMatcher ratio, keeping higher scored article."""
    deduped: List[Dict[str, Any]] = []
    for art in articles:
        title = art.get("title", "").strip().lower()
        is_duplicate = False
        for kept in deduped:
            kept_title = kept.get("title", "").strip().lower()
            similarity = SequenceMatcher(None, title, kept_title).ratio()
            if similarity >= similarity_threshold:
                logger.info(f"Title similarity dedup ({similarity:.2f}) excluded: '{art.get('title')}' in favor of '{kept.get('title')}'")
                is_duplicate = True
                break
        if not is_duplicate:
            deduped.append(art)
    return deduped


def filtration_node(state: PipelineState) -> Dict[str, Any]:
    """
    Agent 3 Node: Relevance Scoring & Filtering (Gemini).
    Performs keyword pre-filtering, calls Gemini LLM for batch relevance scoring,
    sorts articles by score, deduplicates near-identical titles, caps final output
    count to max 10 articles (with graceful fallback if under 10), saves
    `filtered_articles.json` to intermediate data dir, and updates state.
    
    Args:
        state: PipelineState containing `raw_articles` and `persona_profile`.
        
    Returns:
        Dict update for state: {"filtered_articles": final_filtered_list}
    """
    logger.info("--- Executing Agent 3: Relevance Scoring & Filtering (Gemini) ---")

    raw_articles = state.get("raw_articles", [])
    persona_profile = state.get("persona_profile", {})

    if not raw_articles:
        logger.warning("raw_articles in state is empty. Returning empty filtered list.")
        return {"filtered_articles": []}

    # Step 1: Cheap Keyword Pre-Filter
    exclude_topics = persona_profile.get("exclude_topics", [])
    pre_filtered_articles = _exclude_keyword_filter(raw_articles, exclude_topics)
    logger.info(f"Pre-filter kept {len(pre_filtered_articles)} / {len(raw_articles)} articles.")

    if not pre_filtered_articles:
        logger.warning("All articles were excluded by pre-filter keyword match. Proceeding with empty list.")
        return {"filtered_articles": []}

    # Step 2: Prepare Batch Prompt for Gemini Relevance Scoring
    batch_articles_payload = [
        {
            "index": idx,
            "title": art.get("title", ""),
            "description": art.get("description", ""),
            "query_topic": art.get("query_topic", "")
        }
        for idx, art in enumerate(pre_filtered_articles)
    ]

    user_prompt = f"""Persona Profile Context:
Target Topics: {json.dumps(persona_profile.get("topics", []))}
Exclude Topics: {json.dumps(exclude_topics)}
Persona Name: {persona_profile.get("name", "General Reader")}
Persona Description: {persona_profile.get("description", "")}

Articles Batch to Evaluate:
{json.dumps(batch_articles_payload, indent=2)}

Return JSON Array of Relevance Scores:"""

    # Get LLM callable for Agent 3 (Gemini)
    llm_call = get_llm_for_agent("filtration_ranking")
    if not llm_call:
        raise RuntimeError("No LLM configured for agent 'filtration_ranking'.")

    # Step 3: Invoke Gemini for Batch Scoring
    scored_articles_map: Dict[int, Dict[str, Any]] = {}
    try:
        raw_response = llm_call(FILTRATION_RANKING_SYSTEM_PROMPT, user_prompt)
        cleaned_response = clean_markdown_code_fences(raw_response)
        
        # Try finding JSON array substring using regex if direct load fails
        scores_list = None
        try:
            scores_list = json.loads(cleaned_response)
        except json.JSONDecodeError:
            match = re.search(r"\[\s*\{.*\}\s*\]", cleaned_response, re.DOTALL)
            if match:
                scores_list = json.loads(match.group(0))
            else:
                try:
                    scores_list = eval(cleaned_response)
                except Exception:
                    pass

        if isinstance(scores_list, list):
            for item in scores_list:
                if isinstance(item, dict):
                    idx = item.get("index")
                    if idx is not None and isinstance(idx, int) and 0 <= idx < len(pre_filtered_articles):
                        scored_articles_map[idx] = {
                            "relevance_score": float(item.get("relevance_score", 0.5)),
                            "scoring_reason": str(item.get("reason", ""))
                        }
            logger.info(f"Successfully received and parsed {len(scored_articles_map)} scores from Gemini.")
    except Exception as e:
        logger.error(f"Agent 3 Gemini scoring failed: {e}. Defaulting to baseline relevance scores.")

    # Attach scores to articles
    scored_articles: List[Dict[str, Any]] = []
    for idx, art in enumerate(pre_filtered_articles):
        art_copy = dict(art)
        score_info = scored_articles_map.get(idx, {"relevance_score": 0.70, "scoring_reason": "Baseline relevance match"})
        art_copy["relevance_score"] = round(score_info["relevance_score"], 2)
        art_copy["scoring_reason"] = score_info["scoring_reason"]
        scored_articles.append(art_copy)

    # Step 4: Sort Articles by Relevance Score Descending
    scored_articles.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)

    # Step 5: Near-Duplicate Title Detection
    deduped_articles = _deduplicate_similar_titles(scored_articles, similarity_threshold=0.8)

    # Step 6: Hard Cap Final Filtered List at Exactly 10 Articles (or fewer if less available)
    max_filtered_cap = 10
    final_filtered_articles = deduped_articles[:max_filtered_cap]
    logger.info(f"Agent 3 final filtered count: {len(final_filtered_articles)} articles (cap: {max_filtered_cap}).")

    # Save intermediate JSON snapshot
    output_path = INTERMEDIATE_DIR / "filtered_articles.json"
    save_json(final_filtered_articles, output_path)
    logger.info(f"Agent 3 finished successfully. Saved filtered articles to {output_path}")

    return {"filtered_articles": final_filtered_articles}


if __name__ == "__main__":
    from dotenv import load_dotenv
    from utils.json_io import load_json
    load_dotenv()

    profile_path = INTERMEDIATE_DIR / "persona_profile.json"
    raw_articles_path = INTERMEDIATE_DIR / "raw_articles.json"

    if profile_path.exists() and raw_articles_path.exists():
        profile = load_json(profile_path)
        articles = load_json(raw_articles_path)
    else:
        profile = {"name": "Tech Dev", "topics": ["AI", "Space"], "exclude_topics": ["Gossip"]}
        articles = [
            {"title": "Breakthrough in AI Research", "description": "New AI model unveiled", "url": "http://ex.com/1"},
            {"title": "Celebrity Gossip Update", "description": "Hollywood news", "url": "http://ex.com/2"},
            {"title": "Space Rocket Launch", "description": "Space exploration news", "url": "http://ex.com/3"}
        ]

    print("--- Running Agent 3 Standalone Test ---")
    test_state: PipelineState = {
        "persona_profile": profile,
        "raw_articles": articles
    }

    res = filtration_node(test_state)
    filtered = res.get("filtered_articles", [])
    print(f"\nFiltered Articles Count: {len(filtered)}")
    if filtered:
        print("\nTop Ranked Article Sample:")
        print(json.dumps(filtered[0], indent=2))
