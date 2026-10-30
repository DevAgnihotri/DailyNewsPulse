import json
import logging
import os
import sys
from typing import Dict, Any

# Ensure parent directory is in sys.path when running script standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import INTERMEDIATE_DIR
from graph.state import PipelineState
from utils.json_io import save_json
from utils.llm_clients import get_llm_for_agent, clean_markdown_code_fences

logger = logging.getLogger(__name__)

# --- STEP 8: PERSONA INTERPRETER SYSTEM PROMPT DESIGN ---
PERSONA_INTERPRETER_SYSTEM_PROMPT = """You are an expert Persona Interpreter AI for a news personalization engine.
Your job is to read raw, unstructured, or semi-structured user persona preferences and normalize them into a strict, validated JSON profile.

CRITICAL INSTRUCTIONS:
1. You MUST output ONLY raw valid JSON.
2. DO NOT include preamble, markdown formatting (no ```json code blocks), explanations, or postscript.
3. Normalize and expand short or messy topics into clear, standard news search keywords.

TARGET JSON SCHEMA:
{
  "topics": ["list", "of", "normalized", "positive", "search", "topics"],
  "exclude_topics": ["list", "of", "topics", "to", "exclude", "or", "filter", "out"],
  "tone": "one of: casual, professional, concise, friendly, technical, or analytical",
  "reading_level": "one of: beginner, intermediate, or advanced",
  "depth": "one of: summary (brief overview), or detailed (in-depth breakdown)"
}

FEW-SHOT EXAMPLE:
User Input:
{
  "name": "Alex",
  "interests": ["AI stuff", "quantum comp", "space rocket news"],
  "exclude": ["Hollywood gossip", "football"],
  "reading_level": "intermediate",
  "preferred_tone": "concise and analytical",
  "depth": "detailed"
}

Normalized Output:
{
  "topics": ["Artificial Intelligence", "Quantum Computing", "Space Exploration"],
  "exclude_topics": ["Celebrity Gossip", "Sports"],
  "tone": "concise and analytical",
  "reading_level": "intermediate",
  "depth": "detailed"
}
"""


def persona_interpreter_node(state: PipelineState) -> Dict[str, Any]:
    """
    Agent 1 Node: Persona Interpreter.
    Reads `persona_raw` from state, calls Groq LLM, parses JSON,
    saves `persona_profile.json` to intermediate data dir, and updates state.
    
    Args:
        state: PipelineState containing `persona_raw`.
        
    Returns:
        Dict update for state: {"persona_profile": normalized_dict}
    """
    logger.info("--- Executing Agent 1: Persona Interpreter ---")
    
    persona_raw = state.get("persona_raw", {})
    if not persona_raw:
        logger.warning("persona_raw in state is empty or missing.")
        raise ValueError("Cannot run persona_interpreter_node without 'persona_raw' in state.")

    user_prompt = f"Raw Persona Input:\n{json.dumps(persona_raw, indent=2)}\n\nNormalized Output JSON:"

    # Get LLM callable configured for Agent 1 (Groq)
    llm_call = get_llm_for_agent("persona_interpreter")
    if not llm_call:
        raise RuntimeError("No LLM configured for agent 'persona_interpreter'.")

    # Primary LLM invocation
    raw_response = llm_call(PERSONA_INTERPRETER_SYSTEM_PROMPT, user_prompt)
    cleaned_response = clean_markdown_code_fences(raw_response)

    parsed_profile = None
    try:
        parsed_profile = json.loads(cleaned_response)
    except json.JSONDecodeError as e:
        logger.warning(f"First attempt to parse JSON failed: {e}. Retrying once with strict re-prompt...")
        retry_sys_prompt = PERSONA_INTERPRETER_SYSTEM_PROMPT + "\n\nCRITICAL RE-PROMPT: Your previous response was invalid JSON. Reply ONLY with pure valid JSON!"
        retry_response = llm_call(retry_sys_prompt, user_prompt)
        retry_cleaned = clean_markdown_code_fences(retry_response)
        try:
            parsed_profile = json.loads(retry_cleaned)
        except json.JSONDecodeError as err:
            logger.error(f"Retry JSON parse failed: {err}. Raw output was: {retry_response}")
            raise ValueError(f"Agent 1 failed to produce valid JSON profile: {err}") from err

    # Ensure default fallback keys if missing
    parsed_profile.setdefault("topics", persona_raw.get("interests", ["General News"]))
    parsed_profile.setdefault("exclude_topics", persona_raw.get("exclude", []))
    parsed_profile.setdefault("tone", persona_raw.get("preferred_tone", "casual"))
    parsed_profile.setdefault("reading_level", persona_raw.get("reading_level", "intermediate"))
    parsed_profile.setdefault("depth", persona_raw.get("depth", "summary"))

    # Save intermediate JSON snapshot
    output_path = INTERMEDIATE_DIR / "persona_profile.json"
    save_json(parsed_profile, output_path)
    logger.info(f"Agent 1 finished successfully. Profile saved to {output_path}")

    return {"persona_profile": parsed_profile}


if __name__ == "__main__":
    from dotenv import load_dotenv
    from utils.json_io import load_json
    from config.settings import INPUT_DIR
    load_dotenv()
    
    sample_path = INPUT_DIR / "sample_persona.json"
    if sample_path.exists():
        raw_persona = load_json(sample_path)
    else:
        raw_persona = {
            "name": "Alex Tech",
            "interests": ["Artificial Intelligence", "Quantum Computing", "Space Exploration"],
            "exclude": ["Celebrity Gossip", "Sports Score"],
            "reading_level": "intermediate",
            "preferred_tone": "concise and analytical",
            "depth": "detailed"
        }
    
    print("--- Running Agent 1 (Persona Interpreter) Live Test with Groq ---")
    print("\nInput Raw Persona:")
    print(json.dumps(raw_persona, indent=2))
    print("\nCalling Groq LLM (Llama 3.3 70B)...")
    
    test_state: PipelineState = {"persona_raw": raw_persona}
    output_state = persona_interpreter_node(test_state)
    
    print("\nNormalized Persona Profile (Agent 1 Output):")
    print(json.dumps(output_state["persona_profile"], indent=2))

