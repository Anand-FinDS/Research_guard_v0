"""Retriever -> Writer -> Distributor. Each node runs under its own agent identity."""
import json
import operator
import re
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.prompts import DISTRIBUTOR_SYSTEM, SEND_NOTE_TOOL, WRITER_SYSTEM
from core import llm
from core.gateway import Gateway

RETRIEVER = "research-guard.retriever"
WRITER = "research-guard.writer"
DISTRIBUTOR = "research-guard.distributor"
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


class RGState(TypedDict, total=False):
    prompt: str
    user_id: str
    ticker: str
    recipients: list[str]
    approval_id: str
    stock: dict
    filing: str
    draft: str
    draft_id: str
    status: str
    events: Annotated[list, operator.add]   # human-readable trace for CLI/UI


def _ev(agent, tool, outcome):
    return {"agent": agent, "tool": tool, "blocked": outcome.blocked,
            "reason": outcome.reason or "ok"}


def build_graph(gw: Gateway):

    async def retriever(s: RGState):
        async with gw.task(RETRIEVER, s["user_id"], s["prompt"]) as t:
            r1 = await t.call("get_stock_data", {"ticker": s["ticker"]})
            if r1.blocked:
                return {"status": "blocked_at_retriever", "events": [_ev("Retriever", "get_stock_data", r1)]}
            r2 = await t.call("get_filing", {"ticker": s["ticker"]})
            if r2.blocked:
                return {"status": "blocked_at_retriever",
                        "events": [_ev("Retriever", "get_stock_data", r1), _ev("Retriever", "get_filing", r2)]}
        return {"stock": r1.data, "filing": r2.data, "status": "retrieved",
                "events": [_ev("Retriever", "get_stock_data", r1), _ev("Retriever", "get_filing", r2)]}

    async def writer(s: RGState):
        if llm.is_mock():
            st = s["stock"]
            draft = (f"{st['name']} ({st['ticker']}): revenue +{st['rev_growth_yoy']:.1%} YoY, "
                     f"EBITDA margin {st['ebitda_margin']:.1%}, trading at {st['pe']}x P/E. "
                     f"Filing highlights: {s['filing'].splitlines()[1]}")
        else:
            out = await llm.chat([
                {"role": "system", "content": WRITER_SYSTEM},
                {"role": "user", "content": f"DATA:\n{json.dumps(s['stock'])}\n\nFILING:\n{s['filing']}"},
            ])
            draft = out["content"].strip()
        async with gw.task(WRITER, s["user_id"], s["prompt"]) as t:
            r = await t.call("save_draft", {"ticker": s["ticker"], "content": draft})
        draft_id = (r.data or {}).get("draft_id", "") if r.ok else ""
        return {"draft": draft, "draft_id": draft_id, "status": "drafted",
                "events": [_ev("Writer", "save_draft", r)]}

    async def distributor(s: RGState):
        events = []
        async with gw.task(DISTRIBUTOR, s["user_id"], s["prompt"]) as t:
            if llm.is_mock():
                # Mock obeys injected instructions too, so scenario 5 is reproducible offline.
                targets = list(s.get("recipients", [])) + EMAIL_RE.findall(s.get("filing", ""))
                for rcpt in dict.fromkeys(targets):
                    r = await t.call("send_note", {"recipient": rcpt, "ticker": s["ticker"],
                                                   "content": s["draft"],
                                                   "approval_id": s.get("approval_id", "")})
                    events.append(_ev("Distributor", f"send_note -> {rcpt}", r))
            else:
                msgs = [
                    {"role": "system", "content": DISTRIBUTOR_SYSTEM},
                    {"role": "user", "content": (
                        f"Ticker: {s['ticker']}\nRequested recipients: {s.get('recipients', [])}\n"
                        f"approval_id: {s.get('approval_id') or 'none'}\n\nNOTE:\n{s['draft']}\n\n"
                        f"SOURCE MATERIAL:\n{s['filing']}")},
                ]
                for _ in range(5):
                    out = await llm.chat(msgs, tools=[SEND_NOTE_TOOL])
                    if not out["tool_calls"]:
                        break
                    msgs.append({"role": "assistant", "content": out["content"], "tool_calls": [
                        {"id": c["id"], "type": "function",
                         "function": {"name": c["name"], "arguments": json.dumps(c["args"])}}
                        for c in out["tool_calls"]]})
                    for c in out["tool_calls"]:
                        r = await t.call(c["name"], c["args"])
                        events.append(_ev("Distributor", f"{c['name']} -> {c['args'].get('recipient')}", r))
                        result = {"blocked": True, "reason": r.reason} if r.blocked else r.data
                        msgs.append({"role": "tool", "tool_call_id": c["id"],
                                     "content": json.dumps(result, default=str)})
        status = "partially_blocked" if any(e["blocked"] for e in events) else "distributed"
        if events and all(e["blocked"] for e in events):
            status = "blocked_at_distributor"
        return {"status": status, "events": events}

    def after_retriever(s: RGState):
        return END if s.get("status") == "blocked_at_retriever" else "writer"

    def after_writer(s: RGState):
        return "distributor" if s.get("recipients") else END

    g = StateGraph(RGState)
    g.add_node("retriever", retriever)
    g.add_node("writer", writer)
    g.add_node("distributor", distributor)
    g.add_edge(START, "retriever")
    g.add_conditional_edges("retriever", after_retriever, ["writer", END])
    g.add_conditional_edges("writer", after_writer, ["distributor", END])
    g.add_edge("distributor", END)
    return g.compile()
