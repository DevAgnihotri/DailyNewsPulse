import logging
import os
import sys
import requests
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Ensure parent directory is in sys.path so config can be loaded
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import NEWSAPI_KEY
from mcp.server.mcpserver import MCPServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NewsMCPServer")

# Initialize MCP Server instance
app = MCPServer("PersonaNewsMCPServer")

NEWS_API_URL = "https://newsapi.org/v2/everything"


def perform_news_search(query: str, from_date: Optional[str] = None, sort_by: str = "relevancy") -> Dict[str, Any]:
    """
    Core function that queries NewsAPI /v2/everything endpoint and normalizes results.
    """
    api_key = os.getenv("NEWSAPI_KEY", NEWSAPI_KEY)
    if not api_key or api_key == "your_newsapi_key_here":
        logger.error("NEWSAPI_KEY is not configured in environment.")
        return {
            "status": "error",
            "message": "NEWSAPI_KEY is missing or unconfigured. Please set your key in .env file.",
            "articles": []
        }

    params: Dict[str, Any] = {
        "q": query,
        "sortBy": sort_by or "relevancy",
        "language": "en",
        "pageSize": 20,
        "apiKey": api_key,
    }
    if from_date:
        params["from"] = from_date

    max_retries = 3
    retry_delays = [1.0, 2.0, 4.0]
    last_error_msg = ""

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(NEWS_API_URL, params=params, timeout=12)
            
            if response.status_code == 401:
                logger.error("NewsAPI Auth Error (401): Invalid API key.")
                return {"status": "error", "message": "Invalid NewsAPI key (401 Unauthorized).", "articles": []}
            elif response.status_code == 429:
                logger.error(f"NewsAPI Rate Limit Error (429) on attempt {attempt}/{max_retries}.")
                if attempt < max_retries:
                    time.sleep(retry_delays[attempt - 1] * 1.5)
                    continue
                return {"status": "error", "message": "NewsAPI rate limit reached (429).", "articles": []}
            elif response.status_code >= 500:
                logger.warning(f"NewsAPI 5xx Server Error ({response.status_code}) on attempt {attempt}/{max_retries}.")
                if attempt < max_retries:
                    time.sleep(retry_delays[attempt - 1])
                    continue
                return {"status": "error", "message": f"NewsAPI server error ({response.status_code}).", "articles": []}
            elif response.status_code != 200:
                logger.error(f"NewsAPI HTTP Error {response.status_code}: {response.text}")
                return {"status": "error", "message": f"NewsAPI returned HTTP status {response.status_code}.", "articles": []}

            data = response.json()
            raw_articles = data.get("articles", [])
            
            # Normalize response shape
            normalized_articles: List[Dict[str, Any]] = []
            for art in raw_articles:
                normalized_articles.append({
                    "title": art.get("title") or "Untitled",
                    "description": art.get("description") or "",
                    "source": art.get("source", {}).get("name", "Unknown Source"),
                    "url": art.get("url") or "",
                    "published_at": art.get("publishedAt") or "",
                })

            logger.info(f"Successfully fetched {len(normalized_articles)} articles for query: '{query}' (attempt {attempt})")
            return {
                "status": "ok",
                "count": len(normalized_articles),
                "query": query,
                "articles": normalized_articles
            }

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as net_err:
            last_error_msg = f"Network/Timeout error on attempt {attempt}/{max_retries}: {net_err}"
            logger.warning(last_error_msg)
            if attempt < max_retries:
                time.sleep(retry_delays[attempt - 1])
            else:
                return {"status": "error", "message": f"NewsAPI network timeout after {max_retries} attempts.", "articles": []}
        except Exception as e:
            logger.error(f"Unexpected error searching news for '{query}': {e}")
            return {"status": "error", "message": str(e), "articles": []}

    return {"status": "error", "message": last_error_msg or "Failed to fetch news after retries.", "articles": []}


@app.tool(
    name="search_news",
    description="Search news articles via NewsAPI by keyword query, optional from_date, and sort order."
)
def search_news(query: str, from_date: str = "", sort_by: str = "relevancy") -> Dict[str, Any]:
    """MCP Tool Handler for news search."""
    return perform_news_search(query=query, from_date=from_date or None, sort_by=sort_by)


if __name__ == "__main__":
    load_dotenv()
    # Standalone execution check
    if "--test" in sys.argv:
        print("--- Running News MCP Server Standalone Test ---")
        test_query = "artificial intelligence"
        res = perform_news_search(test_query)
        print(f"Test query: '{test_query}' | Status: {res['status']} | Articles returned: {len(res.get('articles', []))}")
        if res.get("articles"):
            print("First article sample:", res["articles"][0]["title"])
    else:
        # Run stdio transport server
        logger.info("Starting Persona News MCP Server on stdio transport...")
        app.run(transport="stdio")
