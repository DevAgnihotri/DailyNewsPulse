from typing import TypedDict, Dict, List, Any, Optional

class PipelineState(TypedDict, total=False):
    """
    LangGraph Pipeline State holding the weekly news generation workflow data across nodes.
    
    Data Flow:
    1. Input: `persona_profile` (Pre-normalized persona specification from personas.json).
    2. Agent 2 (News Fetch via MCP): populates `raw_articles` (trailing 7 days, max 30).
    3. Agent 3 (Filtration & Ranking via Gemini): populates `filtered_articles` (top 10 capped).
    4. Agent 4 (Content Reshaping via Groq): populates `reshaped_articles` (2-4 simple bullet points).
    5. Insight Generator (Gemini): populates `weekly_insight` (4-6 sentence synthesis).
    6. Agent 5 (Presentation Formatter): populates `final_output` (metadata + insight + categories + articles).
    """
    persona_profile: Dict[str, Any]
    raw_articles: List[Dict[str, Any]]
    filtered_articles: List[Dict[str, Any]]
    reshaped_articles: List[Dict[str, Any]]
    weekly_insight: str
    final_output: Dict[str, Any]
    persona_raw: Optional[Dict[str, Any]]
