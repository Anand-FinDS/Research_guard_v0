import os
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
DATA = ROOT / "data"
POLICIES = ROOT / "policies"
LOGS = ROOT / "logs"
OUTBOX = ROOT / "outbox"

LLM_MODEL = os.getenv("LLM_MODEL", "mock")                  # "mock" = no LLM calls (deterministic demo)
LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "")    # used only if LLM_MODEL errors
COMMS_MCP_URL = os.getenv("COMMS_MCP_URL", "http://localhost:8002/mcp")
AFRS_MCP_URL = os.getenv("AFRS_MCP_URL", "http://localhost:8003/mcp")
NEWS_MCP_URL = os.getenv("NEWS_MCP_URL", "http://localhost:8004/mcp")
AGNTID_PROXY_URL = os.getenv("AGNTID_PROXY_URL", "http://localhost:8082/mcp")

# Every MCP server the gateway connects to (name -> URL). All must be running.
# Keys must equal the tool prefixes set in the AgntID portal (afrs_, comms_, news_).
MCP_SERVERS = {"comms": COMMS_MCP_URL, "afrs": AFRS_MCP_URL, "news": NEWS_MCP_URL}

# Tickers with data in afrs_server (data coverage, not policy).
AFRS_TICKERS = {"MSFT"}


def today() -> date:
    d = os.getenv("DEMO_DATE")
    return date.fromisoformat(d) if d else date.today()