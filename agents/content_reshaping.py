import json
import logging
import os
import re
import sys
from typing import Dict, Any, List

# Ensure parent directory is in sys.path when running script standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import INTERMEDIATE_DIR
from graph.state import PipelineState
from utils.json_io import save_json
from utils.llm_clients import get_llm_for_agent, clean_markdown_code_fences

logger = logging.getLogger(__name__)

# --- AGENT 4 CONTENT RESHAPING PROMPT DESIGN (GROQ) ---
CONTENT_RESHAPING_SYSTEM_PROMPT = """You are an expert News Editor AI.
Your job is to transform any news article into a clear headline and 2 to 4 simple, highly accessible English bullet points.

CRITICAL INSTRUCTIONS:
1. Output ONLY a raw valid JSON object.
2. DO NOT include preamble, markdown formatting (no ```json code fences), or explanations.
3. Keep bullet points direct, factual, jargon-free, and easy for any reader to understand in seconds.
4. Each bullet point should be 1-2 concise sentences.

TARGET JSON SCHEMA:
{
  "reshaped_title": "Clear, engaging headline in simple English",
  "bullets": [
    "First key factual takeaway or main event.",
    "Why it matters or context behind the story.",
    "Key impact, numbers, or next steps."
  ]
}

FEW-SHOT EXAMPLE:
Source Article: "Federal Reserve signals potential rate cuts amid easing inflationary pressures and labor market normalization."
Output:
{
  "reshaped_title": "Federal Reserve Hints at Possible Interest Rate Cuts Soon",
  "bullets": [
    "The central bank indicated it may lower interest rates as inflation cools down.",
    "The job market is returning to a stable and balanced pace after years of volatility.",
    "Lower interest rates could reduce borrowing costs for mortgages, car loans, and credit cards."
  ]
}
"""


def _reshape_single_article(article: Dict[str, Any], llm_call: Any) -> Dict[str, Any]:
    """Helper function to boil down an article into 2-4 simple bullet points using Groq LLM."""
    user_prompt = f"""Source Article:
Title: {article.get('title', '')}
Description: {article.get('description', '')}

Transform this article into clear headline and 2-4 simple bullet points JSON:"""

    try:
        raw_response = llm_call(CONTENT_RESHAPING_SYSTEM_PROMPT, user_prompt)
        cleaned_response = clean_markdown_code_fences(raw_response)
        
        parsed = None
        try:
            parsed = json.loads(cleaned_response)
        except json.JSONDecodeError:
            match = re.search(r"\{\s*\"reshaped_title\".*\}", cleaned_response, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))

        if isinstance(parsed, dict):
            reshaped_title = parsed.get("reshaped_title") or article.get("title", "")
            bullets = parsed.get("bullets", [])
            if not isinstance(bullets, list) or len(bullets) == 0:
                desc = article.get("description", "")
                bullets = [desc] if desc else ["Details available in full article."]
        else:
            reshaped_title = article.get("title", "")
            desc = article.get("description", "")
            bullets = [desc] if desc else ["Details available in full article."]

    except Exception as e:
        logger.warning(f"Reshaping failed for article '{article.get('title')}': {e}. Using fallback bullets.")
        reshaped_title = article.get("title", "")
        desc = article.get("description", "")
        bullets = [desc] if desc else ["Details available in full article."]

    # Construct reshaped article object preserving original metadata
    return {
        "reshaped_title": reshaped_title,
        "bullets": bullets,
        "original_title": article.get("title", ""),
        "original_description": article.get("description", ""),
        "source": article.get("source", "Unknown Source"),
        "original_url": article.get("url", ""),
        "published_at": article.get("published_at", ""),
        "query_topic": article.get("query_topic", "General"),
        "relevance_score": article.get("relevance_score", 0.70),
        "scoring_reason": article.get("scoring_reason", "")
    }


def reshaping_node(state: PipelineState) -> Dict[str, Any]:
    """
    Agent 4 Node: Content Reshaping (Groq).
    Loops through `filtered_articles`, calls Groq LLM per article to rewrite
    title and produce 2-4 simple English bullet points (`bullets: list[str]`),
    saves `reshaped_articles.json` to intermediate data dir, and updates state.
    
    Args:
        state: PipelineState containing `filtered_articles`.
        
    Returns:
        Dict update for state: {"reshaped_articles": reshaped_list}
    """
    logger.info("--- Executing Agent 4: Content Reshaping (Simple Bullets via Groq) ---")

    filtered_articles = state.get("filtered_articles", [])

    if not filtered_articles:
        logger.warning("filtered_articles in state is empty. Returning empty reshaped list.")
        return {"reshaped_articles": []}

    llm_call = get_llm_for_agent("content_reshaping")
    if not llm_call:
        raise RuntimeError("No LLM configured for agent 'content_reshaping'.")

    reshaped_articles: List[Dict[str, Any]] = []
    logger.info(f"Agent 4 reshaping {len(filtered_articles)} articles into simple bullet points...")

    for idx, article in enumerate(filtered_articles, 1):
        logger.info(f"Reshaping article {idx}/{len(filtered_articles)}: '{article.get('title')}'")
        reshaped_item = _reshape_single_article(article, llm_call)
        reshaped_articles.append(reshaped_item)

    # Save intermediate JSON snapshot
    output_path = INTERMEDIATE_DIR / "reshaped_articles.json"
    save_json(reshaped_articles, output_path)
    logger.info(f"Agent 4 finished successfully. Saved reshaped articles to {output_path}")

    return {"reshaped_articles": reshaped_articles}


if __name__ == "__main__":
    from dotenv import load_dotenv
    from utils.json_io import load_json
    load_dotenv()

    # Reconfigure stdout for utf-8 printing on Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    filtered_path = INTERMEDIATE_DIR / "filtered_articles.json"

    if filtered_path.exists():
        filtered_arts = load_json(filtered_path)
    else:
        filtered_arts = [{
            "title": "Could AI pose a threat to humanity, and can it be regulated?",
            "description": "The BBC's AI correspondent explains what artificial intelligence is and whether it could cause a threat.",
            "source": "BBC News",
            "url": "https://bbc.com/1",
            "relevance_score": 0.95
        }]

    print("--- Running Agent 4 Standalone Test (Simple Bullets) ---")
    test_state: PipelineState = {
        "filtered_articles": filtered_arts[:2]
    }

    res = reshaping_node(test_state)
    reshaped_results = res.get("reshaped_articles", [])

    print(f"\nReshaped Articles Count: {len(reshaped_results)}")
    if reshaped_results:
        sample = reshaped_results[0]
        print(f"\nHeadline: {sample['reshaped_title']}")
        print("Bullets:")
        for b in sample["bullets"]:
            print(f" - {b}")
