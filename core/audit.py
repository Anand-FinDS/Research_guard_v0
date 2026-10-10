"""Append-only audit trail: who (user, agent), what (tool, args), decision, why."""
import json
from datetime import datetime
from config import LOGS

LOGS.mkdir(exist_ok=True)
AUDIT_FILE = LOGS / "audit.jsonl"


class AuditLog:
    def __init__(self):
        self.records = []

    def record(self, *, mode, run_id, task_id, user_id, agent_id, tool, args, allowed, rule, reason):
        safe_args = {k: (v[:60] + "...") if isinstance(v, str) and len(v) > 60 else v
                     for k, v in args.items()}
        rec = {"ts": datetime.now().isoformat(timespec="seconds"), "mode": mode, "run_id": run_id,
               "task_id": task_id, "user_id": user_id, "agent_id": agent_id, "tool": tool,
               "args": safe_args, "decision": "ALLOW" if allowed else "BLOCK",
               "rule": rule, "reason": reason}
        self.records.append(rec)
        with open(AUDIT_FILE, "a") as f:
            f.write(json.dumps(rec) + "\n")
        return rec
