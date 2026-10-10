"""news_server: recent company news via Serper (google.serper.dev/news).

Run from repo root:  $env:MCP_HOST="0.0.0.0"; python -m mcp_servers.news_server   (:8004)
Needs SERPER_API_KEY in .env. The server holds the key; agents never see it.
Limits (max_results, days) are explicit params so AgntID policy can check them."""
import os

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()
SERPER_URL = "https://google.serper.dev/news"
COMPANY = {"MSFT": "Microsoft", "AAPL": "Apple"}

mcp = FastMCP("news")


def _tbs(days: int) -> str:
    if days <= 1:
        return "qdr:d"
    if days <= 7:
        return "qdr:w"
    if days <= 31:
        return "qdr:m"
    return "qdr:y"


@mcp.tool
def search_news(ticker: str, query: str = "", max_results: int = 5, days: int = 30) -> dict:
    """Search (read) recent news articles about one company ticker. Read-only; no side effects.
    ticker: stock ticker, e.g. MSFT. query: optional extra keywords.
    max_results: number of articles. days: look-back window in days."""
    key = os.getenv("SERPER_API_KEY")
    if not key:
        return {"ticker": ticker, "items": [], "note": "SERPER_API_KEY not set"}
    q = f"{COMPANY.get(ticker.upper(), ticker)} {query}".strip()
    resp = httpx.post(SERPER_URL, headers={"X-API-KEY": key, "Content-Type": "application/json"},
                      json={"q": q, "num": min(max(max_results, 1), 20), "tbs": _tbs(days)},
                      timeout=20)
    resp.raise_for_status()
    items = [{"title": n.get("title", ""), "source": n.get("source", ""), "date": n.get("date", ""),
              "snippet": n.get("snippet", ""), "link": n.get("link", "")}
             for n in resp.json().get("news", [])[:max_results]]
    return {"ticker": ticker, "query": q, "count": len(items), "items": items}


if __name__ == "__main__":
    mcp.run(transport="http", host=os.getenv("MCP_HOST", "127.0.0.1"), port=8004)