"""Data tools. No access checks here on purpose: enforcement is the gateway's job."""
import json
from fastmcp import FastMCP
from config import DATA

mcp = FastMCP("rg-data")


@mcp.tool
def get_stock_data(ticker: str) -> dict:
    """Return key metrics for a stock ticker."""
    stocks = json.loads((DATA / "stocks.json").read_text())
    t = ticker.upper()
    if t not in stocks:
        return {"error": f"unknown ticker {t}"}
    return {"ticker": t, **stocks[t]}


@mcp.tool
def get_filing(ticker: str) -> str:
    """Return the latest results filing text for a ticker."""
    p = DATA / "filings" / f"{ticker.upper()}.txt"
    return p.read_text() if p.exists() else f"No filing for {ticker.upper()}"


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8001)
