# app/tools/tavily.py
import os
from tavily import TavilyClient

_api_key = os.getenv("TAVILY_API_KEY")
_client = TavilyClient(api_key=_api_key) if _api_key else None

def tavily_available() -> bool:
    return _client is not None

def web_search(query: str, max_results: int = 3):
    """
    Returns (answer, sources) from Tavily.
    sources = [{title,url,snippet}]
    """
    if not _client:
        return "", []
    res = _client.search(
        query=query,
        search_depth="basic",
        max_results=max_results,
        include_answer=True,
    )
    answer = res.get("answer", "") or ""
    sources = []
    for r in (res.get("results") or [])[:max_results]:
        sources.append({
            "title": r.get("title") or "",
            "url": r.get("url") or "",
            "snippet": (r.get("content") or "")[:300]
        })
    return answer, sources
