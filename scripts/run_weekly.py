import argparse
import json
import logging
import os
import sys
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Ensure parent directory is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from config.settings import OUTPUT_DIR
from graph.build_graph import get_compiled_graph
from utils.json_io import save_json
from utils.persona_loader import load_personas, get_persona_by_id

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("WeeklyScheduler")


from utils.pipeline_tracker import (
    start_pipeline_run,
    update_pipeline_step,
    complete_pipeline_run,
    fail_pipeline_run,
    get_pipeline_status
)


def generate_feed_for_persona(persona: Dict[str, Any], compiled_graph=None) -> Dict[str, Any]:
    """
    Executes the weekly LangGraph pipeline for a single persona and persists
    the final output to `data/output/final_output_<persona_id>.json`.
    Synchronizes real-time terminal progress with the pipeline tracker.
    
    Args:
        persona: Persona profile dict.
        compiled_graph: Optional pre-compiled graph instance.
        
    Returns:
        Dict: Final output JSON payload.
    """
    graph = compiled_graph or get_compiled_graph()
    persona_id = persona.get("persona_id", "default_persona")
    persona_name = persona.get("name", "Reader")

    logger.info(f"Generating weekly feed for: {persona_name} ({persona_id})...")
    start_pipeline_run(persona_id, persona_name)

    initial_state = {"persona_profile": persona}
    accumulated_state = dict(initial_state)

    try:
        # Stream graph nodes so frontend and tracker sync 1:1 with terminal execution
        events_processed = False
        try:
            stream_iter = graph.stream(initial_state)
            for event in stream_iter:
                events_processed = True
                if isinstance(event, dict):
                    for node_name, node_output in event.items():
                        if isinstance(node_output, dict):
                            accumulated_state.update(node_output)

                        if node_name == "news_fetch":
                            raw_count = len(accumulated_state.get("raw_articles", []))
                            msg = f"Retrieved {raw_count} articles across target topics via News Protocol."
                            update_pipeline_step(persona_id, "news_fetch", msg, f"News Fetch Desk retrieved {raw_count} raw articles.")
                            update_pipeline_step(persona_id, "filtration_ranking", "Scoring articles against persona interests with Gemini 3.6 Flash...", "Relevance Ranker initiating Gemini batch scoring.")
                        elif node_name == "filtration_ranking":
                            filtered_count = len(accumulated_state.get("filtered_articles", []))
                            msg = f"Ranked & filtered to top {filtered_count} high-scoring stories."
                            update_pipeline_step(persona_id, "filtration_ranking", msg, f"Filter & Relevance Ranker retained top {filtered_count} articles.")
                            update_pipeline_step(persona_id, "content_reshaping", "Synthesizing executive summaries with Groq Compound Mini...", "Content Reshaper synthesizing takeaways.")
                        elif node_name == "content_reshaping":
                            reshaped_count = len(accumulated_state.get("reshaped_articles", []))
                            msg = f"Distilled {reshaped_count} articles into structured takeaways."
                            update_pipeline_step(persona_id, "content_reshaping", msg, f"Content Reshaper distilled {reshaped_count} articles.")
                            update_pipeline_step(persona_id, "insight_generator", "Synthesizing cross-story executive perspective with Gemini 3.6 Flash...", "Insight Generator analyzing macro trends.")
                        elif node_name == "insight_generator":
                            insights = accumulated_state.get("executive_insights", {})
                            title = insights.get("title", "Strategic Overview")
                            msg = f"Synthesized executive perspective: '{title}'."
                            update_pipeline_step(persona_id, "insight_generator", msg, f"Insight Generator produced weekly synthesis: '{title}'.")
                            update_pipeline_step(persona_id, "presentation_formatter", "Formatting final broadsheet structure and read time...", "Presentation Formatter assembling final output.")
                        elif node_name == "presentation_formatter":
                            update_pipeline_step(persona_id, "presentation_formatter", "Broadsheet JSON finalized and validated.", "Presentation Formatter complete.")
        except TypeError:
            events_processed = False

        if not events_processed and hasattr(graph, "invoke"):
            invoke_res = graph.invoke(initial_state)
            if isinstance(invoke_res, dict):
                accumulated_state.update(invoke_res)

        final_output = accumulated_state.get("final_output", {})
        if not final_output:
            # Fallback in case stream only returned state delta
            final_output = accumulated_state

        # Save to persona-specific output file: data/output/final_output_<persona_id>.json
        target_path = OUTPUT_DIR / f"final_output_{persona_id}.json"
        save_json(final_output, target_path)
        logger.info(f"Saved weekly feed for '{persona_id}' to: {target_path}")

        # Also save as latest final_output.json
        save_json(final_output, OUTPUT_DIR / "final_output.json")

        complete_pipeline_run(persona_id, final_output)
        return final_output

    except Exception as e:
        err_str = str(e)
        logger.error(f"Pipeline failure for persona '{persona_id}': {err_str}", exc_info=True)

        # Classify error to give simple, easy to understand guidance in UI
        error_title = "Agent Pipeline Interrupted"
        recovery_hint = "Check your network and API credentials, then retry refreshing the feed."
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            error_title = "API Rate Limit Exceeded (429)"
            recovery_hint = "The AI model provider quota was momentarily exceeded. Exponential backoff retry is active. Wait 15-30 seconds and click 'Refresh Feed'."
        elif "API_KEY" in err_str or "GEMINI_API_KEY" in err_str or "GROQ_API_KEY" in err_str or "api_key" in err_str.lower():
            error_title = "Missing or Invalid API Key"
            recovery_hint = "Check persona-news-agent/.env to ensure GEMINI_API_KEY, GROQ_API_KEY, and NEWS_API_KEY are properly configured."
        elif "newsapi" in err_str.lower() or "mcp" in err_str.lower() or "news protocol" in err_str.lower():
            error_title = "News Retrieval Error"
            recovery_hint = "Could not fetch fresh news via MCP protocol. The system will fall back to cached articles if available."

        current_status = get_pipeline_status(persona_id)
        failed_node = current_status.get("current_node") or "news_fetch"

        fail_pipeline_run(
            persona_id=persona_id,
            failed_node=failed_node,
            error_title=error_title,
            error_message=err_str,
            error_details=f"Agent '{failed_node}' raised an unhandled exception: {err_str}",
            recovery_hint=recovery_hint
        )
        raise e


def run_weekly_batch(target_persona_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes the weekly batch pipeline across all personas (or a specific persona if target_persona_id is passed).
    Wrapped in try/except per persona so single-persona failures do not abort the entire batch.
    
    Args:
        target_persona_id: Optional persona_id string to run only for that persona.
        
    Returns:
        Dict summarizing the batch run status: total, successful, failed, and file paths.
    """
    load_dotenv()
    graph = get_compiled_graph()

    if target_persona_id:
        persona = get_persona_by_id(target_persona_id)
        if not persona:
            raise ValueError(f"Persona with ID '{target_persona_id}' not found in personas.json")
        personas_to_run = [persona]
    else:
        personas_to_run = load_personas()

    logger.info(f"=== Starting Weekly Batch Run for {len(personas_to_run)} Persona(s) ===")
    
    successful: List[str] = []
    failed: List[Dict[str, str]] = []
    generated_files: Dict[str, str] = {}

    for idx, persona in enumerate(personas_to_run, 1):
        pid = persona.get("persona_id", f"unknown_{idx}")
        pname = persona.get("name", "Unknown")
        logger.info(f"[{idx}/{len(personas_to_run)}] Processing persona '{pname}' ({pid})...")
        
        try:
            feed_output = generate_feed_for_persona(persona, compiled_graph=graph)
            successful.append(pid)
            out_file = str(OUTPUT_DIR / f"final_output_{pid}.json")
            generated_files[pid] = out_file
            logger.info(f"[{idx}/{len(personas_to_run)}] Completed '{pid}' successfully ({feed_output.get('total_articles', 0)} articles).")
        except Exception as e:
            logger.error(f"[{idx}/{len(personas_to_run)}] Failed generating feed for persona '{pid}': {e}", exc_info=True)
            failed.append({"persona_id": pid, "error": str(e)})

    summary = {
        "status": "completed" if not failed else "completed_with_errors",
        "total_attempted": len(personas_to_run),
        "successful_count": len(successful),
        "failed_count": len(failed),
        "successful_personas": successful,
        "failed_personas": failed,
        "generated_files": generated_files
    }

    logger.info(f"=== Weekly Batch Run Complete: {len(successful)} Succeeded, {len(failed)} Failed ===")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Weekly Batch News Generation for Personas")
    parser.add_argument("--persona", type=str, help="Specific persona_id to run (e.g. tech_professional)", default=None)
    args = parser.parse_args()

    # Reconfigure stdout for utf-8 printing on Windows console
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    batch_summary = run_weekly_batch(target_persona_id=args.persona)
    print("\n--- Weekly Batch Run Summary ---")
    print(json.dumps(batch_summary, indent=2))
