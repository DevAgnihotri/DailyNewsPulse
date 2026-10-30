import json
import logging
import os
import sys
from typing import Dict, Any, List

# Ensure parent directory is in sys.path when running script standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import INTERMEDIATE_DIR
from graph.state import PipelineState
from utils.json_io import save_json
from utils.llm_clients import get_llm_for_agent, clean_markdown_code_fences

logger = logging.getLogger(__name__)

# --- AGENT INSIGHT GENERATOR PROMPT DESIGN (GEMINI) ---
INSIGHT_GENERATOR_SYSTEM_PROMPT = """You are a Senior Executive Intelligence Analyst AI for a personalized news engine.
Your mission is to analyze the complete batch of weekly news articles curated for a specific reader persona and produce a single, cohesive 4-6 sentence synthesis paragraph.

CRITICAL INSTRUCTIONS:
1. Synthesize the overarching trends, macroeconomic or industry shifts, and strategic themes connecting the week's stories.
2. Directly address the interests, perspective, and core focus of the target persona (e.g. tech developers vs finance investors vs college students).
3. Do NOT merely summarize article by article. Instead, connect the dots across stories into a meaningful high-level narrative.
4. Output EXACTLY ONE concise paragraph of 4 to 6 sentences.
5. Do NOT include markdown code blocks, bullet points, headers, or conversational fluff. Just the synthesis paragraph.
"""


def insight_generator_node(state: PipelineState) -> Dict[str, Any]:
    """
    Insight Generator Agent Node (Gemini).
    Takes all bulleted reshaped articles along with the target persona profile in a single call,
    prompts Gemini to synthesize a 4-6 sentence weekly insight paragraph,
    saves `weekly_insight.json` to intermediate data dir, and updates state.
    
    Args:
        state: PipelineState containing `reshaped_articles` and `persona_profile`.
        
    Returns:
        Dict update for state: {"weekly_insight": synthesis_paragraph}
    """
    logger.info("--- Executing Insight Generator Agent (Gemini) ---")

    reshaped_articles = state.get("reshaped_articles", [])
    persona_profile = state.get("persona_profile", {})

    persona_name = persona_profile.get("name", "Reader")
    persona_desc = persona_profile.get("description", "")
    persona_topics = [
        t.get("keyword") if isinstance(t, dict) else str(t)
        for t in persona_profile.get("topics", [])
    ]

    if not reshaped_articles:
        logger.warning("reshaped_articles is empty. Generating fallback weekly insight.")
        fallback_insight = f"This week saw steady developments across {', '.join(persona_topics[:3]) if persona_topics else 'general news'}. Continue tracking emerging stories in the upcoming cycle."
        return {"weekly_insight": fallback_insight}

    # Prepare condensed articles summary for the Gemini prompt
    articles_summary_list = []
    for idx, art in enumerate(reshaped_articles, 1):
        headline = art.get("reshaped_title") or art.get("title", "")
        bullets = art.get("bullets", [])
        bullets_text = " ".join(bullets) if isinstance(bullets, list) else str(bullets)
        articles_summary_list.append(f"Story {idx}: {headline} — {bullets_text}")

    articles_context = "\n".join(articles_summary_list)

    user_prompt = f"""Target Persona:
Name: {persona_name}
Description: {persona_desc}
Core Focus Topics: {', '.join(persona_topics)}

Curated Weekly Stories:
{articles_context}

Provide the 4-6 sentence weekly insight synthesis for {persona_name}:"""

    llm_call = get_llm_for_agent("insight_generator")
    if not llm_call:
        raise RuntimeError("No LLM configured for agent 'insight_generator'.")

    try:
        raw_response = llm_call(INSIGHT_GENERATOR_SYSTEM_PROMPT, user_prompt)
        weekly_insight = clean_markdown_code_fences(raw_response).strip()
        # Ensure single cohesive block
        weekly_insight = " ".join(weekly_insight.split())
        logger.info(f"Generated weekly insight snippet: {weekly_insight[:120]}...")
    except Exception as e:
        logger.error(f"Insight generator LLM call failed: {e}. Using fallback synthesis.")
        weekly_insight = (
            f"This week brought notable activity across key sectors relevant to {persona_name}, "
            f"particularly around {', '.join(persona_topics[:3]) if persona_topics else 'the main headlines'}. "
            "Strategic priorities continue to evolve as market leaders adapt to new developments. "
            "Staying informed on these core trends will provide a clear advantage in navigating the week ahead."
        )

    # Save intermediate JSON snapshot
    output_path = INTERMEDIATE_DIR / "weekly_insight.json"
    save_json({"persona_id": persona_profile.get("persona_id", "default"), "weekly_insight": weekly_insight}, output_path)
    logger.info(f"Insight generator finished successfully. Saved snapshot to {output_path}")

    return {"weekly_insight": weekly_insight}


if __name__ == "__main__":
    from dotenv import load_dotenv
    from utils.json_io import load_json
    from utils.persona_loader import load_personas
    load_dotenv()

    # Reconfigure stdout for utf-8 printing on Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    personas = load_personas()
    test_persona = personas[0] if personas else {"name": "Tech Professional", "topics": ["AI", "Cloud"]}

    reshaped_path = INTERMEDIATE_DIR / "reshaped_articles.json"
    if reshaped_path.exists():
        articles = load_json(reshaped_path)
    else:
        articles = [
            {"reshaped_title": "AI Models Accelerate Scientific Discovery", "bullets": ["Researchers achieve 10x faster simulations.", "Open source benchmarks released."]},
            {"reshaped_title": "Major Cloud Providers Expand Infrastructure", "bullets": ["New data centers announced globally.", "Focus shifts to energy efficiency."]}
        ]

    print(f"--- Running Insight Generator Standalone Test for: {test_persona.get('name')} ---")
    test_state: PipelineState = {
        "persona_profile": test_persona,
        "reshaped_articles": articles
    }

    res = insight_generator_node(test_state)
    print("\n--- Weekly Insight Output ---")
    print(res.get("weekly_insight"))
