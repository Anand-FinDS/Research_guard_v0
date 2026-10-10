"""Run every scenario in unsafe and agntid mode and write one self-contained HTML page
for the presentation: outbox/showcase.html (open it in a browser, no server needed).

Run from repo root (research-guard .venv), with all servers + AgntID runtime up:
    python make_showcase.py"""
import asyncio
import html
import webbrowser
from datetime import datetime

from agents.graph import build_graph
from config import OUTBOX
from core.gateway import Gateway
from scenarios import SCENARIOS

MODES = [("unsafe", "Without guard"), ("agntid", "With AgntID")]

AGENTS = [
    ("research-guard.retriever", "afrs.get_financials, afrs.search_filings", "Financials (SQL) + management commentary (Qdrant)"),
    ("research-guard.news", "news.search_news", "Recent news via Serper (untrusted internet content)"),
    ("research-guard.writer", "comms.save_draft", "Writes the results report"),
    ("research-guard.distributor", "comms.send_note", "Sends the report to recipients"),
]
POLICIES = [
    ("afrs.get_financials / search_filings", "ticker = MSFT", "Restricted ticker (AAPL)"),
    ("news.search_news", "ticker = MSFT; max_results &le; 10", "Off-task / oversized queries"),
    ("comms.save_draft", "ticker = MSFT", "Drafts on restricted tickers"),
    ("comms.send_note", "operator = anand", "Associate distributing"),
    ("comms.send_note", "recipient ends with @researchguard.example", "Compliance-walled desk, external recipients"),
    ("comms.send_note", "ticker = MSFT", "Distributing restricted tickers"),
]


async def collect() -> dict:
    results = {}
    for mode, _ in MODES:
        async with Gateway(mode) as gw:
            graph = build_graph(gw)
            for sc in SCENARIOS:
                state = {k: sc[k] for k in ("prompt", "user_id", "ticker", "recipients")}
                state["approval_id"] = sc.get("approval_id", "")
                start = len(gw.audit.records)
                try:
                    out = await graph.ainvoke(state)
                    results[(sc["id"], mode)] = {"out": out, "audit": gw.audit.records[start:], "error": None}
                except Exception as e:
                    results[(sc["id"], mode)] = {"out": {}, "audit": [], "error": f"{type(e).__name__}: {e}"}
    return results


e = lambda v: html.escape(str(v))


def _status(res) -> str:
    if res["error"]:
        return '<span class="pill red">error</span>'
    s = res["out"].get("status", "")
    cls = {"distributed": "green", "partially_blocked": "amber"}.get(s, "red")
    return f'<span class="pill {cls}">{e(s)}</span>'


def _sends(res) -> str:
    ev = [x for x in res["out"].get("events", []) if x["agent"] == "Distributor"]
    sent = sum(not x["blocked"] for x in ev)
    blocked = sum(x["blocked"] for x in ev)
    return f"{sent} sent / {blocked} blocked" if ev else "&mdash;"


def _table(headers, rows) -> str:
    th = "".join(f"<th>{h}</th>" for h in headers)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"


def _events(res) -> str:
    if res["error"]:
        return f'<p class="err">{e(res["error"])}</p>'
    rows = []
    for x in res["out"].get("events", []):
        dec = '<span class="pill red">BLOCKED</span>' if x["blocked"] else '<span class="pill green">allowed</span>'
        rows.append((e(x["agent"]), e(x["tool"]), dec, e(x["reason"]) if x["blocked"] else ""))
    return _table(["Agent", "Tool call", "Decision", "Reason"], rows)


def render(results: dict) -> str:
    matrix = []
    for sc in SCENARIOS:
        u, a = results[(sc["id"], "unsafe")], results[(sc["id"], "agntid")]
        matrix.append((f"<b>{e(sc['id'])}</b>", e(sc["title"]), f"<code>{e(sc['user_id'])}</code>",
                       f"<code>{e(sc['ticker'])}</code>", _status(u), _sends(u), _status(a), _sends(a)))

    details = []
    for sc in SCENARIOS:
        cols = []
        for mode, label in MODES:
            res = results[(sc["id"], mode)]
            tasks = sorted({r["task_id"] for r in res["audit"]})
            task_note = (f'<p class="muted">AgntID task ids: {", ".join(e(t) for t in tasks)}</p>'
                         if mode == "agntid" and tasks else "")
            cols.append(f'<div class="col"><h4>{label} {_status(res)}</h4>{_events(res)}{task_note}</div>')
        rcpts = ", ".join(f"<code>{e(r)}</code>" for r in sc["recipients"])
        details.append(f'<section><h3>{e(sc["id"])}: {e(sc["title"])}</h3>'
                       f'<p class="muted">User <code>{e(sc["user_id"])}</code> &middot; ticker '
                       f'<code>{e(sc["ticker"])}</code> &middot; recipients {rcpts}</p>'
                       f'<div class="cols">{"".join(cols)}</div></section>')

    sample = results.get((SCENARIOS[0]["id"], "agntid"), {}).get("out", {}).get("draft", "")
    css = """
    body{font-family:Segoe UI,Arial,sans-serif;margin:32px auto;max-width:1280px;color:#1d2433;padding:0 20px}
    h1{margin:0}.sub{color:#5b6475;margin:4px 0 24px}
    h2{border-bottom:2px solid #e3e7ee;padding-bottom:6px;margin-top:36px}
    table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0}
    th,td{border:1px solid #e3e7ee;padding:6px 8px;text-align:left;vertical-align:top}
    th{background:#f4f6f9}
    .pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600}
    .green{background:#d8f3e3;color:#11643a}.amber{background:#fdf0d2;color:#7a5200}.red{background:#fbdcdc;color:#8a1c1c}
    .cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}.col{overflow-x:auto}
    section{margin-bottom:28px}.muted{color:#5b6475;font-size:13px}.err{color:#8a1c1c}
    pre{background:#f4f6f9;padding:12px;white-space:pre-wrap;font-size:13px}
    code{background:#f4f6f9;padding:1px 4px;border-radius:3px}"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>research-guard showcase</title>
<style>{css}</style></head><body>
<h1>research-guard</h1>
<p class="sub">Same multi-agent equity research workflow, same agent code, run twice: without runtime
enforcement and with every tool call governed by AgntID. Generated {datetime.now():%d %b %Y %H:%M}.</p>
<h2>Before vs after</h2>
{_table(["#", "Scenario", "User", "Ticker", "Without guard", "Sends", "With AgntID", "Sends"], matrix)}
<h2>Who the agents are and what they may do</h2>
{_table(["Agent identity", "Tools", "Purpose"], [(f"<code>{a}</code>", e(t), e(p)) for a, t, p in AGENTS])}
<h2>AgntID policies (enforced in the runtime on every call)</h2>
{_table(["Tool", "Rule", "Blocks"], [(e(t), r, e(b)) for t, r, b in POLICIES])}
<h2>Scenario detail</h2>
{"".join(details)}
<h2>Report produced ({e(SCENARIOS[0]["id"])}, with AgntID)</h2>
<pre>{e(sample) or "No report produced."}</pre>
</body></html>"""


def main():
    results = asyncio.run(collect())
    OUTBOX.mkdir(exist_ok=True)
    path = OUTBOX / "showcase.html"
    path.write_text(render(results), encoding="utf-8")
    print(f"Wrote {path}")
    webbrowser.open(path.resolve().as_uri())


if __name__ == "__main__":
    main()