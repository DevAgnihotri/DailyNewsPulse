import asyncio
import importlib.util
import json
import logging
import os
import sys
from typing import Dict, Any, List, Optional

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

logger = logging.getLogger(__name__)

# Base directory path of persona-news-agent
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER_SCRIPT_PATH = os.path.join(PROJECT_ROOT, "mcp", "news_server.py")

# Dynamically import perform_news_search from local mcp/news_server.py file
spec = importlib.util.spec_from_file_location("local_news_server", SERVER_SCRIPT_PATH)
local_news_server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local_news_server)
perform_news_search = local_news_server.perform_news_search


async def fetch_news_via_mcp(
    query: str,
    from_date: Optional[str] = None,
    sort_by: str = "relevancy",
    use_subprocess: bool = True,
) -> Dict[str, Any]:
    """
    Connects to the MCP News Server via stdio transport, calls `search_news` tool,
    and returns parsed JSON results.
    
    Args:
        query: News search topic query.
        from_date: Optional YYYY-MM-DD date string.
        sort_by: Sorting preference ("relevancy", "popularity", "publishedAt").
        use_subprocess: If True, spawns stdio MCP subprocess; if False/fails, uses direct fallback.
        
    Returns:
        Dictionary containing status, query, article count, and list of normalized articles.
    """
    if not use_subprocess:
        logger.info(f"Using direct news search fallback for query: '{query}'")
        return perform_news_search(query=query, from_date=from_date, sort_by=sort_by)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_SCRIPT_PATH],
        env=dict(os.environ),
    )

    try:
        logger.info(f"Connecting to MCP News Server stdio transport for query: '{query}'...")
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Call search_news tool via MCP protocol
                result = await session.call_tool(
                    name="search_news",
                    arguments={
                        "query": query,
                        "from_date": from_date or "",
                        "sort_by": sort_by or "relevancy",
                    },
                )
                
                # Extract text content from MCP CallToolResult payload
                if result and result.content:
                    for content_item in result.content:
                        if hasattr(content_item, "text"):
                            text_data = content_item.text
                            try:
                                return json.loads(text_data)
                            except json.JSONDecodeError:
                                return eval(text_data)
                        elif isinstance(content_item, dict):
                            return content_item
                
                logger.warning("Empty content returned from MCP server tool call.")
                return {"status": "error", "message": "Empty content returned", "articles": []}

    except Exception as e:
        logger.warning(f"MCP stdio client error for query '{query}': {e}. Falling back to direct execution...")
        return perform_news_search(query=query, from_date=from_date, sort_by=sort_by)


def fetch_news_via_mcp_sync(
    query: str,
    from_date: Optional[str] = None,
    sort_by: str = "relevancy",
) -> Dict[str, Any]:
    """Synchronous wrapper for fetch_news_via_mcp for easy invocation from sync nodes."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        return loop.run_until_complete(fetch_news_via_mcp(query, from_date, sort_by))
    else:
        return asyncio.run(fetch_news_via_mcp(query, from_date, sort_by))


if __name__ == "__main__":
    print("--- Running MCP Client Wrapper Standalone Test ---")
    res = fetch_news_via_mcp_sync(query="technology")
    print(f"Status: {res.get('status')} | Articles fetched: {len(res.get('articles', []))}")
    if res.get("articles"):
        print("Sample Article Title:", res["articles"][0].get("title"))
