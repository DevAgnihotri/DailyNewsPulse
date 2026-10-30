import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from config.settings import OUTPUT_DIR, DATA_DIR, BASE_DIR
from utils.json_io import load_json, save_json
from utils.persona_loader import load_personas, get_persona_by_id
from utils.pipeline_tracker import get_pipeline_status
from scripts.run_weekly import run_weekly_batch, generate_feed_for_persona

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("PersonaNewsAPI")

FEEDBACK_FILE_PATH = DATA_DIR / "feedback" / "feedback.json"
FEEDBACK_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="Persona News Agent API",
    description="Backend API serving pre-generated weekly personalized news feeds with AI insights and simple bullet summaries.",
    version="2.0.0"
)

# Enable CORS for Frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend static files if directory exists
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
}

@app.get("/", include_in_schema=False)
def serve_frontend_root():
    """Serves the frontend single-page web app index.html."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file, headers=NO_CACHE_HEADERS)
    return {"message": "PulsePersona API is running. Access /docs for API documentation."}

@app.get("/style.css", include_in_schema=False)
def serve_style_css():
    """Serves the frontend stylesheet."""
    css_file = FRONTEND_DIR / "style.css"
    if css_file.exists():
        return FileResponse(css_file, media_type="text/css", headers=NO_CACHE_HEADERS)
    raise HTTPException(status_code=404, detail="CSS file not found")

@app.get("/app.js", include_in_schema=False)
def serve_app_js():
    """Serves the frontend JavaScript application logic."""
    js_file = FRONTEND_DIR / "app.js"
    if js_file.exists():
        return FileResponse(js_file, media_type="application/javascript", headers=NO_CACHE_HEADERS)
    raise HTTPException(status_code=404, detail="JS file not found")


# --- Pydantic Schema Models ---

class TopicItem(BaseModel):
    keyword: Optional[str] = None
    name: Optional[str] = None
    weight: Optional[float] = 0.5


class PersonaSchema(BaseModel):
    persona_id: str
    name: str
    description: str
    topics: List[Any] = Field(default_factory=list)
    exclude_topics: List[str] = Field(default_factory=list)
    tone: Optional[str] = "casual"
    reading_level: Optional[str] = "intermediate"
    depth: Optional[str] = "summary"


class ArticleItem(BaseModel):
    title: str
    bullets: List[str]
    source: str
    url: str
    published_at: str
    relevance_score: float
    scoring_reason: Optional[str] = ""
    read_time_minutes: int
    original_title: Optional[str] = ""


class CategoryGroup(BaseModel):
    topic: str
    count: int
    articles: List[ArticleItem]


class FeedResponse(BaseModel):
    persona_id: str
    persona_name: str
    persona_description: Optional[str] = ""
    week_start_date: str
    week_end_date: str
    weekly_insight: str
    total_articles: int
    total_categories: int
    categories: List[CategoryGroup]


class FeedbackPayload(BaseModel):
    persona_id: str = Field(..., description="The persona ID associated with the interaction")
    topic: str = Field(..., description="The topic keyword receiving feedback")
    action: str = Field(..., description="The user action: 'clicked' (interested) or 'skipped' (not interested)")


class AdminRunWeeklyPayload(BaseModel):
    persona_id: Optional[str] = Field(None, description="Optional single persona_id to generate feed for")


# --- API Routes ---

@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint confirming API service is operational."""
    return {"status": "healthy", "service": "persona-news-api", "version": "2.0.0"}


@app.get("/personas", response_model=List[PersonaSchema], tags=["Personas"])
def get_personas():
    """Returns the list of all available curated reader personas."""
    try:
        personas = load_personas()
        return personas
    except Exception as e:
        logger.error(f"Error loading personas: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load personas: {str(e)}")


@app.get("/feed/{persona_id}", response_model=FeedResponse, tags=["Feeds"])
def get_feed_for_persona(persona_id: str):
    """
    Retrieves the pre-generated weekly news feed for a given persona ID.
    Performs fast static file read without live LLM latency.
    """
    target_file = OUTPUT_DIR / f"final_output_{persona_id}.json"

    # Fallback to final_output.json if it matches the requested persona_id
    if not target_file.exists():
        fallback_file = OUTPUT_DIR / "final_output.json"
        if fallback_file.exists():
            try:
                candidate_data = load_json(fallback_file)
                if candidate_data.get("persona_id") == persona_id:
                    return candidate_data
            except Exception:
                pass

        # Check if persona exists at all
        persona = get_persona_by_id(persona_id)
        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona with ID '{persona_id}' does not exist."
            )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Weekly feed for persona '{persona_id}' has not been generated yet. Please trigger /admin/run-weekly or run the scheduler script."
        )

    try:
        feed_data = load_json(target_file)
        return feed_data
    except Exception as e:
        logger.error(f"Error reading feed file for '{persona_id}': {e}")
        raise HTTPException(status_code=500, detail=f"Error reading feed file: {str(e)}")


@app.post("/feedback", tags=["Feedback"])
def record_feedback(payload: FeedbackPayload):
    """
    Records a user feedback event (clicked / skipped) for an article topic on a persona.
    Appends the interaction record to feedback/feedback.json for subsequent weekly tuning.
    """
    feedback_entry = {
        "persona_id": payload.persona_id,
        "topic": payload.topic,
        "action": payload.action,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    try:
        existing_feedback = []
        if FEEDBACK_FILE_PATH.exists():
            try:
                loaded = load_json(FEEDBACK_FILE_PATH)
                if isinstance(loaded, list):
                    existing_feedback = loaded
            except Exception:
                existing_feedback = []

        existing_feedback.append(feedback_entry)
        save_json(existing_feedback, FEEDBACK_FILE_PATH)
        logger.info(f"Recorded feedback: persona='{payload.persona_id}', topic='{payload.topic}', action='{payload.action}'")
        return {"status": "success", "message": "Feedback recorded successfully", "entry": feedback_entry}
    except Exception as e:
        logger.error(f"Failed to record feedback: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save feedback: {str(e)}")


@app.get("/pipeline/status/{persona_id}", tags=["Pipeline"])
def get_current_pipeline_status(persona_id: str):
    """
    Returns the real-time telemetry, terminal logs, and step execution status
    for the multi-agent pipeline associated with a persona.
    """
    return get_pipeline_status(persona_id)


@app.post("/feed/{persona_id}/refresh", tags=["Feeds"])
def refresh_persona_feed(persona_id: str, background_tasks: BackgroundTasks):
    """
    Triggers generation/refresh of the weekly news feed for a given persona ID.
    Executes the multi-agent pipeline and returns the newly generated feed.
    If an error occurs, detailed diagnostic telemetry is returned immediately.
    """
    persona = get_persona_by_id(persona_id)
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona with ID '{persona_id}' not found."
        )

    logger.info(f"Manual feed refresh triggered for persona: '{persona_id}'")
    try:
        fresh_feed = generate_feed_for_persona(persona)
        return {
            "status": "success",
            "message": f"Successfully refreshed feed for '{persona_id}'",
            "feed": fresh_feed,
            "pipeline_status": get_pipeline_status(persona_id)
        }
    except Exception as e:
        logger.error(f"Feed generation error for '{persona_id}': {e}")
        status_info = get_pipeline_status(persona_id)
        return {
            "status": "error",
            "message": f"Pipeline execution error for persona '{persona_id}': {str(e)}",
            "pipeline_status": status_info
        }


@app.post("/admin/run-weekly", tags=["Admin"])
def trigger_weekly_run(payload: AdminRunWeeklyPayload, background_tasks: BackgroundTasks):
    """
    Triggers the weekly batch generation pipeline in the background for live demos or on-demand refresh.
    """
    logger.info(f"Admin triggered weekly run (persona: {payload.persona_id or 'ALL'})...")
    background_tasks.add_task(run_weekly_batch, target_persona_id=payload.persona_id)
    return {
        "status": "accepted",
        "message": f"Weekly batch generation triggered in background for persona: '{payload.persona_id or 'all personas'}'"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
