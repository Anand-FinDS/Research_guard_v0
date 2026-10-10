"""Local policy engine: a stand-in for AgntID's runtime so the demo works before the SDK arrives.
Same inputs AgntID sees: agent_id, user_id, tool, args."""
import json
from dataclasses import dataclass
from datetime import date
from config import DATA, POLICIES, today

V0_DATA_TOOLS = ("get_stock_data", "get_filing")
AFRS_TOOLS = ("get_financials", "search_filings")


@dataclass
class Decision:
    allowed: bool
    rule: str
    reason: str


def _load(path):
    return json.loads(path.read_text())


class LocalPolicyEngine:
    def __init__(self):
        self.agents = _load(POLICIES / "agents.json")
        self.policy = _load(POLICIES / "local_policy.json")
        self.users = _load(DATA / "users.json")
        self.stocks = _load(DATA / "stocks.json")
        self.restricted = set(_load(DATA / "restricted_list.json")["restricted"])
        self.quiet = _load(DATA / "quiet_periods.json")
        self.approvals = _load(DATA / "approvals.json")
        self.internal = set(self.policy["internal_domains"])
        self.afrs_coverage = set(self.policy["afrs_coverage"])

    def evaluate(self, agent_id: str, user_id: str, tool: str, args: dict) -> Decision:
        agent = self.agents.get(agent_id)
        user = self.users.get(user_id)
        if not agent:
            return Decision(False, "agent_tool_grant", f"Unknown agent identity '{agent_id}'")
        if not user or user["role"] not in agent["operable_by_roles"]:
            role = user["role"] if user else "unknown"
            return Decision(False, "user_can_operate_agent",
                            f"User '{user_id}' (role: {role}) may not operate {agent['display_name']}")
        if tool not in agent["allowed_tools"]:
            return Decision(False, "agent_tool_grant",
                            f"{agent['display_name']} is not granted tool '{tool}'")

        ticker = str(args.get("ticker", "")).upper()

        if tool in V0_DATA_TOOLS:
            if ticker not in self.stocks or not self.stocks[ticker]["covered"]:
                return Decision(False, "coverage_only", f"{ticker} is not in coverage")

        if tool in AFRS_TOOLS and ticker not in self.afrs_coverage:
            return Decision(False, "coverage_only", f"{ticker} is not in AFRS coverage")

        if tool in (*V0_DATA_TOOLS, *AFRS_TOOLS, "send_note") and ticker in self.restricted:
            return Decision(False, "restricted_list", f"{ticker} is on the restricted list")

        if tool == "send_note":
            q = self.quiet.get(ticker)
            if q and date.fromisoformat(q["start"]) <= today() <= date.fromisoformat(q["end"]):
                return Decision(False, "quiet_period",
                                f"{ticker} is in quiet period {q['start']}..{q['end']} ({q['reason']})")
            domain = str(args.get("recipient", "")).split("@")[-1].lower()
            if domain not in self.internal:
                ok, why = self._approval_ok(args.get("approval_id", ""), ticker, domain)
                if not ok:
                    return Decision(False, "external_needs_approval",
                                    f"External recipient @{domain}: {why}")
                return Decision(True, "external_needs_approval", f"Approved via {args['approval_id']}")

        return Decision(True, "default_allow", "All checks passed")

    def _approval_ok(self, approval_id: str, ticker: str, domain: str):
        if not approval_id:
            return False, "no approval_id supplied"
        a = self.approvals.get(approval_id)
        if not a:
            return False, f"approval {approval_id} not found"
        if a["ticker"] != ticker or a["recipient_domain"] != domain:
            return False, f"approval {approval_id} does not cover {ticker} -> @{domain}"
        if today() > date.fromisoformat(a["expires"]):
            return False, f"approval {approval_id} expired"
        return True, "ok"