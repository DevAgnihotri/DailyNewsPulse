import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory of persona-news-agent project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file if present
load_dotenv(BASE_DIR / ".env")

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")

# LLM Models Configuration
# Groq: groq/compound-mini or groq/compound (Fast execution for structured & high-volume rewriting tasks)
GROQ_MODEL = os.getenv("GROQ_MODEL", "groq/compound-mini")

# Gemini: Gemini 3 Flash series (Strong reasoning & high efficiency for batch scoring)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# Temperatures per Agent Node
AGENT_TEMPERATURES = {
    "persona_interpreter": 0.1,  # Agent 1 (standalone): Strict JSON structure extraction
    "news_fetch": 0.0,          # Agent 2: Pure tool calling / MCP news search
    "filtration_ranking": 0.2,   # Agent 3: Batch relevance scoring with Gemini
    "content_reshaping": 0.5,   # Agent 4: Creative bullet point rewriting with Groq
    "insight_generator": 0.4,   # New Agent: Weekly narrative trend synthesis with Gemini
    "presentation_formatter": 0.0 # Agent 5: Deterministic grouping & read time calculation
}

# Provider Routing Table per Agent
# Why this split was chosen:
# - Groq (persona_interpreter, content_reshaping): High speed, low latency for structured extraction and per-article rewriting.
# - Gemini (filtration_ranking, insight_generator): Superior reasoning capability for batch evaluation & overarching weekly synthesis.
# - None (news_fetch, presentation_formatter): Deterministic tool/formatting steps requiring no LLM.
AGENT_PROVIDER_MAP = {
    "persona_interpreter": "groq",
    "news_fetch": None,
    "filtration_ranking": "gemini",
    "content_reshaping": "groq",
    "insight_generator": "gemini",
    "presentation_formatter": None,
}

def get_provider_for_agent(agent_name: str) -> str | None:
    """Returns the LLM provider ('groq', 'gemini', or None) for a given agent name."""
    return AGENT_PROVIDER_MAP.get(agent_name)

# Data Directory Paths
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
INTERMEDIATE_DIR = DATA_DIR / "intermediate"
OUTPUT_DIR = DATA_DIR / "output"

# Ensure directories exist
for directory in [DATA_DIR, INPUT_DIR, INTERMEDIATE_DIR, OUTPUT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)
