"""Comms tools. send_note takes ticker/recipient/approval_id as explicit params
so a policy engine can see them (the key design decision)."""
import json
import uuid
from datetime import datetime
from fastmcp import FastMCP
from config import OUTBOX

mcp = FastMCP("rg-comms")
(OUTBOX / "drafts").mkdir(parents=True, exist_ok=True)


@mcp.tool
def save_draft(ticker: str, content: str) -> dict:
    """Save a research note draft. Returns the draft id."""
    draft_id = f"DRAFT-{uuid.uuid4().hex[:6].upper()}"
    (OUTBOX / "drafts" / f"{draft_id}.md").write_text(f"# {ticker}\n\n{content}\n")
    return {"draft_id": draft_id, "ticker": ticker}


@mcp.tool
def send_note(recipient: str, ticker: str, content: str, approval_id: str = "") -> dict:
    """Send a research note on `ticker` to `recipient` (email). approval_id is required by
    compliance for external recipients."""
    rec = {"ts": datetime.now().isoformat(timespec="seconds"), "recipient": recipient,
           "ticker": ticker, "approval_id": approval_id, "chars": len(content)}
    with open(OUTBOX / "sent.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"[comms] SENT {ticker} note -> {recipient}")
    return {"status": "sent", **rec}


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8002)
