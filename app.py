"""research-guard demo UI: run one scenario in unsafe and agntid mode, side by side.

Run from repo root (research-guard .venv):  streamlit run app.py
Needs: afrs (:8003), news (:8004), comms (:8002) running; AgntID runtime Connected.
No pandas/pyarrow: tables are rendered as Markdown (pandas DLLs can be blocked by Windows policy)."""
import asyncio

import streamlit as st

from agents.graph import build_graph
from core.gateway import Gateway
from scenarios import SCENARIOS

st.set_page_config(page_title="research-guard", layout="wide")

AGENTS = [
    ("research-guard.retriever", "afrs.get_financials, afrs.search_filings",
     "Financials (SQL) + management commentary (Qdrant)"),
    ("research-guard.news", "news.search_news", "Recent news via Serper (untrusted internet content)"),
    ("research-guard.writer", "comms.save_draft", "Writes the results report"),
    ("research-guard.distributor", "comms.send_note", "Sends the report to recipients"),
]
POLICIES = [
    ("afrs.get_financials / search_filings", "ticker = MSFT", "Restricted ticker (AAPL)"),
    ("news.search_news", "ticker = MSFT; max_results <= 10", "Off-task / oversized queries"),
    ("comms.save_draft", "ticker = MSFT", "Drafts on restricted tickers"),
    ("comms.send_note", "operator = anand", "Associate distributing"),
    ("comms.send_note", "recipient ends with @researchguard.example",
     "Compliance-walled desk, external recipients"),
    ("comms.send_note", "ticker = MSFT", "Distributing restricted tickers"),
]


def md_table(headers: list[str], rows: list[tuple]) -> str:
    esc = lambda v: str(v).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(esc(v) for v in r) + " |" for r in rows]
    return "\n".join(lines)


async def _run(mode: str, sc: dict):
    async with Gateway(mode) as gw:
        graph = build_graph(gw)
        state = {k: sc[k] for k in ("prompt", "user_id", "ticker", "recipients")}
        state["approval_id"] = sc.get("approval_id", "")
        out = await graph.ainvoke(state)
        return out, list(gw.audit.records)


def run(mode: str, sc: dict) -> dict:
    try:
        out, audit = asyncio.run(_run(mode, sc))
        return {"out": out, "audit": audit, "error": None}
    except Exception as e:
        return {"out": None, "audit": [], "error": f"{type(e).__name__}: {e}"}


def show(title: str, res: dict | None):
    st.subheader(title)
    if res is None:
        st.caption("Not run yet.")
        return
    if res["error"]:
        st.error(res["error"])
        return
    out = res["out"]
    status = out.get("status", "")
    if status == "distributed":
        st.success(f"Status: {status}")
    elif status == "partially_blocked":
        st.warning(f"Status: {status}")
    else:
        st.error(f"Status: {status}")

    rows = [(e["agent"], e["tool"], "🟥 **BLOCKED**" if e["blocked"] else "🟩 allowed",
             e["reason"] if e["blocked"] else "")
            for e in out.get("events", [])]
    if rows:
        st.markdown(md_table(["Agent", "Tool call", "Decision", "Reason"], rows))
    with st.expander("Report draft", expanded=False):
        st.markdown(out.get("draft") or "_No report produced (run stopped before Writer)._")
    with st.expander("Audit records", expanded=False):
        arows = [(r["ts"], r["user_id"], r["agent_id"].split(".")[-1], r["tool"], r["decision"],
                  r["rule"], r["task_id"]) for r in res["audit"]]
        if arows:
            st.markdown(md_table(["ts", "user", "agent", "tool", "decision", "rule", "task_id"], arows))


# ---------- layout ----------
st.title("research-guard")
st.caption("Same multi-agent research workflow, same agent code. Left: no runtime enforcement. "
           "Right: every tool call governed by AgntID.")

with st.sidebar:
    st.header("Scenario")
    labels = {f"{s['id']}: {s['title']}": s for s in SCENARIOS}
    sc = labels[st.selectbox("Choose", list(labels))]
    st.markdown(f"**User:** `{sc['user_id']}`  \n**Ticker:** `{sc['ticker']}`")
    st.markdown("**Recipients:**  \n" + "  \n".join(f"- `{r}`" for r in sc["recipients"]))
    st.markdown(f"**Prompt:** {sc['prompt']}")
    run_both = st.button("Run both modes", type="primary")

with st.expander("Who the agents are and what they may do", expanded=False):
    st.markdown("**Agent identities**")
    st.markdown(md_table(["Agent", "Tools", "Purpose"], AGENTS))
    st.markdown("**AgntID policies (enforced in the runtime, per call)**")
    st.markdown(md_table(["Tool", "Rule", "Blocks"], POLICIES))

if run_both:
    with st.spinner("Running without enforcement..."):
        st.session_state["unsafe"] = run("unsafe", sc)
    with st.spinner("Running through AgntID..."):
        st.session_state["agntid"] = run("agntid", sc)
    st.session_state["ran"] = sc["id"]

if st.session_state.get("ran"):
    st.markdown(f"#### Results for scenario {st.session_state['ran']}")
left, right = st.columns(2)
with left:
    show("Without guard (unsafe)", st.session_state.get("unsafe"))
with right:
    show("With AgntID", st.session_state.get("agntid"))