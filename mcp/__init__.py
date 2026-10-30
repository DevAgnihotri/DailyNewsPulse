"""
MCP server package for persona-news-agent.
Extends __path__ so the official MCP SDK in site-packages remains importable.
"""
import sys
import os

# Allow importing official mcp SDK modules (e.g., mcp.server, mcp.client) alongside local mcp package files
_site_pkgs = [p for p in sys.path if "site-packages" in p]
for _sp in _site_pkgs:
    _pkg_dir = os.path.join(_sp, "mcp")
    if os.path.exists(_pkg_dir) and _pkg_dir not in __path__:
        __path__.append(_pkg_dir)
