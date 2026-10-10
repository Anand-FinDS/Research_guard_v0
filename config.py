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

LLM_MODEL = os.getenv("LLM_MODEL", "mock")
DATA_MCP_URL = os.getenv("DATA_MCP_URL", "http://localhost:8001/mcp")
COMMS_MCP_URL = os.getenv("COMMS_MCP_URL", "http://localhost:8002/mcp")
AGNTID_PROXY_URL = os.getenv("AGNTID_PROXY_URL", "http://localhost:8082/mcp")


def today() -> date:
    d = os.getenv("DEMO_DATE")
    return date.fromisoformat(d) if d else date.today()
