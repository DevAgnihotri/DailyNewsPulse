import argparse
import json
import logging
import os
import sys
from dotenv import load_dotenv

# Reconfigure stdout for utf-8 printing on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from config.settings import OUTPUT_DIR, INTERMEDIATE_DIR
from graph.build_graph import get_compiled_graph
from utils.json_io import load_json, save_json
from utils.persona_loader import load_personas, get_persona_by_id

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("PersonaNewsMain")


def run_pipeline(persona_id: str = "tech_professional", custom_persona_path: str = None) -> dict:
    """
    Executes the refactored weekly news generation pipeline end-to-end for a target persona.
    
    Args:
        persona_id: ID of the persona to generate the feed for (e.g. 'tech_professional').
        custom_persona_path: Optional path to a custom persona JSON file.
        
    Returns:
        Final Output dictionary containing structured weekly news feed with insight & bullets.
    """
    load_dotenv()

    # Load target persona
    if custom_persona_path:
        logger.info(f"Loading custom persona from {custom_persona_path}...")
        persona_profile = load_json(custom_persona_path)
    else:
        logger.info(f"Loading static persona '{persona_id}' from personas.json...")
        persona_profile = get_persona_by_id(persona_id)
        if not persona_profile:
            all_personas = load_personas()
            persona_profile = all_personas[0] if all_personas else {}

    persona_name = persona_profile.get("name", "Valued Reader")
    persona_topics = [
        t.get("keyword") if isinstance(t, dict) else str(t)
        for t in persona_profile.get("topics", [])
    ]

    print("\n========================================================")
    print("🚀 STARTING PERSONA NEWS WEEKLY PIPELINE (END-TO-END)")
    print("========================================================")
    print(f"Target Persona: {persona_name} ({persona_profile.get('persona_id')})")
    print(f"Description: {persona_profile.get('description')}")
    print(f"Core Topics: {', '.join(persona_topics)}")
    print(f"Exclusions: {persona_profile.get('exclude_topics')}\n")

    compiled_graph = get_compiled_graph()
    initial_state = {"persona_profile": persona_profile}

    final_state = {}
    print("Executing LangGraph Pipeline Nodes (news_fetch -> filtration -> reshaping -> insight -> formatter)...")
    
    # Stream intermediate state progress across nodes
    for output_chunk in compiled_graph.stream(initial_state):
        for node_name, node_state_update in output_chunk.items():
            print(f"  ✓ Completed Node: [{node_name}]")
            final_state.update(node_state_update)

    final_output = final_state.get("final_output", {})
    output_file_path = OUTPUT_DIR / "final_output.json"
    save_json(final_output, output_file_path)

    print("\n========================================================")
    print("🎉 WEEKLY PIPELINE EXECUTION COMPLETED SUCCESSFULLY!")
    print("========================================================")
    print(f"Persona: {final_output.get('persona_name')} | Week: {final_output.get('week_start_date')} to {final_output.get('week_end_date')}")
    print(f"\n💡 Weekly Insight:\n   {final_output.get('weekly_insight')}\n")
    print(f"Total Articles Delivered: {final_output.get('total_articles', 0)}")
    print(f"Total Categories: {final_output.get('total_categories', 0)}")
    print(f"Output File: {output_file_path}")
    print("\nIntermediate Artifacts Saved:")
    print(f"  - Agent 2: {INTERMEDIATE_DIR / 'raw_articles.json'}")
    print(f"  - Agent 3: {INTERMEDIATE_DIR / 'filtered_articles.json'}")
    print(f"  - Agent 4: {INTERMEDIATE_DIR / 'reshaped_articles.json'}")
    print(f"  - Insight: {INTERMEDIATE_DIR / 'weekly_insight.json'}")
    print("========================================================\n")

    return final_output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Persona News Weekly Pipeline")
    parser.add_argument("--persona", type=str, help="Persona ID (e.g. tech_professional, finance_markets)", default="tech_professional")
    parser.add_argument("--file", type=str, help="Path to custom persona JSON file", default=None)
    args = parser.parse_args()

    run_pipeline(persona_id=args.persona, custom_persona_path=args.file)
