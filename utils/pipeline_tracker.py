"""
Thread-safe Pipeline Progress & Telemetry Tracker.
Synchronizes real-time terminal agent execution with the Web UI.
"""
import time
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

_lock = threading.Lock()
_tracker_store: Dict[str, Dict[str, Any]] = {}

AGENT_METADATA = {
    "news_fetch": {
        "step": 1,
        "name": "News Fetch Desk",
        "engine": "MCP News Protocol",
        "description": "Fetching verified 7-day articles across persona target topics via MCP stdio client.",
        "icon": "globe"
    },
    "filtration_ranking": {
        "step": 2,
        "name": "Filter & Relevance Ranker",
        "engine": "Google Gemini 3.6 Flash",
        "description": "Batch scoring stories against persona profile, negative filtering & top-10 cap.",
        "icon": "filter"
    },
    "content_reshaping": {
        "step": 3,
        "name": "Content Reshaper",
        "engine": "Groq Compound Mini",
        "description": "Distilling complex articles into 2–4 simple, high-impact bullet points and takeaways.",
        "icon": "edit"
    },
    "insight_generator": {
        "step": 4,
        "name": "Executive Insight Synthesis",
        "engine": "Google Gemini 3.6 Flash",
        "description": "Analyzing cross-story macro patterns to generate weekly executive perspective.",
        "icon": "cpu"
    },
    "presentation_formatter": {
        "step": 5,
        "name": "Presentation Formatter",
        "engine": "Deterministic Engine",
        "description": "Assembling broadsheet categories, estimating read time, and formatting final JSON.",
        "icon": "layout"
    }
}


def start_pipeline_run(persona_id: str, persona_name: str):
    """Initializes a new pipeline run for a persona."""
    with _lock:
        _tracker_store[persona_id] = {
            "persona_id": persona_id,
            "persona_name": persona_name,
            "status": "running",  # "running", "completed", "error"
            "current_node": "news_fetch",
            "current_step": 1,
            "total_steps": 5,
            "step_name": AGENT_METADATA["news_fetch"]["name"],
            "step_engine": AGENT_METADATA["news_fetch"]["engine"],
            "message": f"Starting multi-agent news intelligence pipeline for '{persona_name}'...",
            "logs": [f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] LangGraph StateGraph initiated for {persona_name}."],
            "error": None,
            "start_time": time.time(),
            "updated_at": time.time(),
            "elapsed_seconds": 0.0,
            "step_history": []
        }


def update_pipeline_step(persona_id: str, node_name: str, message: str = "", log_line: str = ""):
    """Updates the currently executing agent node and live terminal log."""
    with _lock:
        if persona_id not in _tracker_store:
            _tracker_store[persona_id] = {
                "persona_id": persona_id,
                "persona_name": persona_id.replace("_", " ").title(),
                "status": "running",
                "logs": [],
                "error": None,
                "start_time": time.time(),
                "step_history": []
            }

        state = _tracker_store[persona_id]
        meta = AGENT_METADATA.get(node_name, {
            "step": 1,
            "name": node_name,
            "engine": "Pipeline",
            "description": message
        })

        state["status"] = "running"
        state["current_node"] = node_name
        state["current_step"] = meta["step"]
        state["total_steps"] = 5
        state["step_name"] = meta["name"]
        state["step_engine"] = meta["engine"]
        state["message"] = message or meta["description"]
        state["updated_at"] = time.time()
        state["elapsed_seconds"] = round(state["updated_at"] - state.get("start_time", state["updated_at"]), 1)

        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        if log_line:
            state["logs"].append(f"[{timestamp}] {log_line}")
        elif message:
            state["logs"].append(f"[{timestamp}] [{meta['name']}] {message}")

        # Keep last 15 log lines for concise UI display
        if len(state["logs"]) > 15:
            state["logs"] = state["logs"][-15:]

        if node_name not in state["step_history"]:
            state["step_history"].append(node_name)


def complete_pipeline_run(persona_id: str, final_feed: Optional[Dict[str, Any]] = None):
    """Marks a pipeline run as successfully completed."""
    with _lock:
        if persona_id in _tracker_store:
            state = _tracker_store[persona_id]
            state["status"] = "completed"
            state["current_step"] = 5
            state["current_node"] = "completed"
            state["step_name"] = "All Agents Complete"
            state["step_engine"] = "Verified 100% Curation"
            total_articles = final_feed.get("total_articles", 10) if final_feed else 10
            state["message"] = f"Broadsheet compilation finalized successfully ({total_articles} key stories curated)."
            state["updated_at"] = time.time()
            state["elapsed_seconds"] = round(state["updated_at"] - state.get("start_time", state["updated_at"]), 1)
            timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
            state["logs"].append(f"[{timestamp}] Pipeline execution finished successfully in {state['elapsed_seconds']}s.")
            state["error"] = None


def fail_pipeline_run(
    persona_id: str,
    failed_node: str,
    error_title: str,
    error_message: str,
    error_details: str = "",
    recovery_hint: str = ""
):
    """Records a clear, prominent failure in the pipeline."""
    with _lock:
        if persona_id not in _tracker_store:
            _tracker_store[persona_id] = {
                "persona_id": persona_id,
                "persona_name": persona_id.replace("_", " ").title(),
                "logs": [],
                "start_time": time.time()
            }

        state = _tracker_store[persona_id]
        meta = AGENT_METADATA.get(failed_node, {"step": 1, "name": failed_node, "engine": "Agent"})
        state["status"] = "error"
        state["current_node"] = failed_node
        state["current_step"] = meta["step"]
        state["step_name"] = meta["name"]
        state["step_engine"] = meta["engine"]
        state["message"] = f"Pipeline paused: {error_title}"
        state["updated_at"] = time.time()
        state["elapsed_seconds"] = round(state["updated_at"] - state.get("start_time", state["updated_at"]), 1)

        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        state["logs"].append(f"[{timestamp}] [ERROR at {meta['name']}]: {error_message}")

        state["error"] = {
            "failed_agent": meta["name"],
            "failed_engine": meta["engine"],
            "failed_node": failed_node,
            "error_title": error_title,
            "error_message": error_message,
            "error_details": error_details,
            "recovery_hint": recovery_hint or "The system will attempt fallback models and cached editions automatically."
        }


def get_pipeline_status(persona_id: str) -> Dict[str, Any]:
    """Returns the current pipeline telemetry and status for a persona."""
    with _lock:
        if persona_id in _tracker_store:
            data = dict(_tracker_store[persona_id])
            data["elapsed_seconds"] = round(time.time() - data.get("start_time", time.time()), 1) if data.get("status") == "running" else data.get("elapsed_seconds", 0.0)
            return data
        
        # Default idle state
        return {
            "persona_id": persona_id,
            "status": "idle",
            "current_node": None,
            "current_step": 0,
            "total_steps": 5,
            "step_name": "Standby",
            "step_engine": "LangGraph Orchestrator",
            "message": "Pipeline is in standby. It activates dynamically when you click Refresh Feed or change persona.",
            "logs": ["Pipeline ready on demand."],
            "error": None,
            "elapsed_seconds": 0.0,
            "step_history": []
        }
