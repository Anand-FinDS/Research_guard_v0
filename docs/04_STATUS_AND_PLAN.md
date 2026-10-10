# Status and build plan

## What exists — v0 (tested)
Codebase `research-guard` v0 (zip delivered with these docs). Synthetic tickers ABCM, XYZL (restricted),
QRST (quiet period), PQRI (filing with injected instruction). 3 agents (retriever, writer, distributor),
2 FastMCP servers (data :8001, comms :8002), `core/gateway.py` with unsafe | guarded | agntid modes,
local policy engine, JSONL audit log, `run_demo.py` CLI with rich output.

Verified: unsafe + guarded with `LLM_MODEL=mock` on FastMCP 4.1 / LangGraph 1.2 — all 7 v0 scenarios
behave as expected. **Not verified**: real-LLM mode (sandbox had no Groq access) and `agntid` mode
(written from SDK README quick start only).

v0 layout:
```
config.py  requirements.txt  .env.example  scenarios.py  run_demo.py
data/{stocks,restricted_list,quiet_periods,users,approvals}.json  data/filings/*.txt
policies/{agents,local_policy}.json
mcp_servers/{data_server,comms_server}.py
core/{gateway,policy,audit,llm}.py
agents/{graph,prompts}.py
```
v1 evolves this codebase; keep the gateway / task / audit pattern.

## AFRS assets being reused (via afrs_server MCP)
- SQLite `afrs_financials.db`, table `financial_facts` (~1,846 verified facts parsed from MSFT Excel).
- Qdrant Cloud hybrid collection: press release + transcript chunks; dense OpenAI
  `text-embedding-3-small` + fastembed BM25 sparse, RRF fusion.
- Qdrant cluster unsuspended 10 Oct 2026 (afrs_mfst: 352 points, green). Keep-alive ping still to do.

## Build order (v1)
1. ✅ `afrs_server` (afrs-scaffold/mcp_servers/afrs_server.py, AFRS env, :8003) — DONE 10 Oct 2026.
   Tools: `get_financials(ticker, metric, period, segment=None)`, `search_filings(ticker, query, k)`.
   Wraps SQLFinancialsAgent / ContextAgent unchanged. Verified on real data (Q4-26 revenue 90,007;
   Intelligent Cloud 39,306; transcript hits). Period labels: `Q4-26` (SQL), `FY26Q4` (Qdrant payload).
   `AFRS_STUB=1` = stub mode. Non-MSFT tickers return empty + note (data coverage, not policy).
   Notes: AFRS returns delta_qoq/yoy = null → fetch prior period for YoY in step 3; chunks are
   sentence-sized → use k=8–10 and targeted queries in the Research fetch template.
   Remaining: repoint research-guard Research agent to :8003.
2. `news_server` (Serper): structured items incl. `tickers_mentioned`; fixtures mode + live mode;
   restricted-name redaction; param limits.
3. Writer → 1–2 page report (results, guidance, latest developments, sources).
4. `comms_server` (Gmail API, OAuth for authorised account), distribution list, ESCALATE via
   LangGraph `interrupt()`, task expiry check. Policy engine upgraded to 4 decision types + resource scope.
5. Streamlit UI with `st.login()` Google OIDC.
6. Optional `edgar_server`.
7. At event: install `agntid-sdk`, translate `local_policy.json` to AgntID policies, run `--mode agntid`.

Steps 1–4 testable from CLI before any UI.

## Open questions for AgntID docs / organisers
1. How is a **narrow** rule written, and what does the agent get back?
2. How does **escalation** work — AgntID holds and calls back, or returns "pending" for us to handle?
3. Can policies inspect tool **responses**?
4. Does permission **expiry** happen automatically at task close?
5. Does one proxy URL front multiple MCP servers?
6. Multiple agents: one task per agent, or their **delegation contract** (see Deep Agents example)?
7. Native approval objects vs passing an `approval_id` param?
8. Submission format (repo / video / live URL).

## Risks / checks
- Real LLMs may refuse injected instructions → unsafe demo less dramatic; mock mode guarantees it.
- AgntID SDK may pin an older FastMCP; install SDK first and let it resolve. Code uses only stable APIs
  (`Client`, `call_tool`, `list_tools`, `@mcp.tool`).
- Serper free tier limits; use fixtures for the demo.
- Gmail: send only to own test addresses; OAuth token stays in comms_server.
- Screener.in rejected: India-only (no MSFT), no official API (scraping/ToS risk).

## Optional extensions (only if core is done)
- Peer comparison tool where peer set includes a restricted ticker (aggregation-leak case).
- In-process guardrail vs proxy comparison slide (guardrail missing on one agent → leak; proxy holds).
- Promptfoo red-team config → block-rate metric.
