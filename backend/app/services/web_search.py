import re
import structlog
from langchain_core.tools import tool
from tavily import AsyncTavilyClient
from app.core.config import settings

logger = structlog.get_logger(__name__)

# Tavily scores 0.0 - 1.0 — below 0.3 is usually noise
MIN_RELEVANCE_SCORE = 0.3

# Keeps context window manageable — full pages would exhaust tokens
MAX_CONTENT_LENGTH = 800

def _sanitize_search_query(query: str) -> str:
    query = query.strip()
    query = re.sub(r"[<>{}\[\]\\]", "", query)
    query = re.sub(r"\s+", " ", query)

    if len(query) > 400:
        query = query[:400]

    return query.strip()

def _format_results_for_llm(results: list[dict]) -> tuple[str, list[dict]]:
    if not results:
        return "No web search results found.", []

    context_parts = []
    citations = []

    for i, result in enumerate(results):
        title = result.get("title", "Untitled")
        url = result.get("url", "")
        content = result.get("content", "")
        score = result.get("score", 0.0)

        if len(content) > MAX_CONTENT_LENGTH:
            content = content[:MAX_CONTENT_LENGTH] + "..."

        context_parts.append(
            f"[Web Source {i+1}: {title}]\n"
            f"URL: {url}\n"
            f"{content}"
        )

        citations.append({
            "index": i + 1,
            "title": title,
            "url": url,
            "snippet": content[:200] + "..." if len(content) > 200 else content,
            "relevance_score": round(score, 3),
        })

    context = "\n\n---\n\n".join(context_parts)
    full_content = (
        f"Here are current web search results:\n\n"
        f"{context}\n\n"
        f"Use this information to answer the user's question. "
        f"Cite sources as [Web Source N] and include the URL."
    )

    return full_content, citations

async def _web_search(
        query: str,
        search_depth: str = "basic",
        max_results: int = None
) -> dict:
    """
    Execute a Tavily web search and return formatted results.

    search_depth:
      "basic"    → fast, good for most queries (1-2 seconds)
      "advanced" → deeper crawl, better for research (3-5 seconds)

    Returns dict with "content" (for LLM) and "citations" (for frontend).
    """
    if max_results is None:
        max_results = settings.tavily_max_results

    clean_query = _sanitize_search_query(query)
    if not clean_query:
        return {
            "content": "search query was empty after sanitization",
            "citations": []
        }
    
    logger.info(
        "web_search.starting",
        query=clean_query[:100],
        search_depth=search_depth,
        max_results=max_results
    )

    try:
        client = AsyncTavilyClient(api_key=settings.tavily_api_key)

        response = await client.search(
            query=clean_query,
            search_depth=search_depth,
            max_results=max_results,
            include_answer=False,
            include_raw_content=False
        )

        results = response.get("results", [])

        results = [
            r for r in results
            if r.get("score", 0.0) >= MIN_RELEVANCE_SCORE
        ]

        logger.info(
            "web_search.complete",
            query=clean_query[:100],
            total_results=len(response.get("results")),
            filtered_results=len(results)
        )

        if not results:
            return {
                "content": f"Web search for '{clean_query}' returned no relevant results",
                "citations": [],
            }
        content, citations = _format_results_for_llm(results)
        return {
            "content": content,
            "citations": citations
        }
    except Exception as e:
        logger.error("web_search.error", query=clean_query[:100], error=str(e))
        return {
            "content": f"Web search is temporarily unavailable: {str(e)}",
            "citations": []
        }
    
@tool
async def web_search_tool(query: str) -> dict:
    """
    Search the web for current information.

    Use this tool when:
    - The user asks about recent events or news
    - The user needs current data (prices, exchange rates, weather, news, information)
    - The question requires information beyond the uploaded documents
    - You need to verify a fact you're unsure about

    Do NOT use this for questions about the user's uploaded documents
    — use rag_search for those instead.

    Input: a clear, specific search query (not a question)
    Good: "M-Pesa API integration Kenya 2026"
    Bad: "Can you tell me how M-Pesa works?"
    """
    return await _web_search(query=query)

@tool
async def web_search_advanced_tool(query: str) -> dict:
    """
    Deep web search for complex research queries.
    Slower than web_search but returns more comprehensive results.
    Use for multi-part research questions that need thorough coverage.
    """
    return await _web_search(query=query, search_depth="advanced")


