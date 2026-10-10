"""Comms tools. send_note takes ticker/recipient/operator/approval_id as explicit params
so a policy engine can see them (the key design decision)."""
import json
import os
import uuid
from datetime import datetime

from fastmcp import FastMCP

from config import OUTBOX

mcp = FastMCP("rg-comms")
(OUTBOX / "drafts").mkdir(parents=True, exist_ok=True)


@mcp.tool
def save_draft(ticker: str, content: str) -> dict:
    """Save (write) a research report draft to the outbox. Returns the draft id."""
    draft_id = f"DRAFT-{uuid.uuid4().hex[:6].upper()}"
    (OUTBOX / "drafts" / f"{draft_id}.md").write_text(content + "\n", encoding="utf-8")
    return {"draft_id": draft_id, "ticker": ticker}


@mcp.tool
def send_note(recipient: str, ticker: str, content: str, operator: str = "",
              approval_id: str = "") -> dict:
    """Send a research note on `ticker` to `recipient` (email). `operator` is the user the
    send is made for (stamped by the gateway). approval_id is required by compliance for
    external recipients."""
    rec = {"ts": datetime.now().isoformat(timespec="seconds"), "recipient": recipient,
           "ticker": ticker, "operator": operator, "approval_id": approval_id,
           "chars": len(content)}
    with open(OUTBOX / "sent.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"[comms] SENT {ticker} note -> {recipient} (operator: {operator})")
    return {"status": "sent", **rec}


if __name__ == "__main__":
    mcp.run(transport="http", host=os.getenv("MCP_HOST", "127.0.0.1"), port=8002)