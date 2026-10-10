# Architecture (v1 plan (next upgrade)

## Flow
```
Streamlit UI (Google login via st.login → verified operator email)
        |
LangGraph: Research → News → Writer → Distributor     (4 agent identities)
        |
Gateway (single MCP client choke point; stamps agent_id, user_id, task_id, resource)
        |
[ local policy engine now | AgntID proxy at event ]   → ALLOW / NARROW / BLOCK / ESCALATE
        |
MCP servers
  afrs_server   (lives in afrs-scaffold repo, AFRS env, port 8003) → SQLite facts + Qdrant hybrid search
  news_server   (Serper; cached fixtures for demo)                  → MSFT news, restricted-name redaction
  edgar_server  (optional; SEC EDGAR, free, no key)                 → latest MSFT filings
  comms_server  (Gmail API, OAuth for ONE authorised account)      → save_draft, send_report
```

## Roles (MCP basics, as agreed)
- **MCP server**: owns a tool and the real credentials (API keys, OAuth tokens, DB). Exposes tools with
  name, description, input schema. No LLM.
- **MCP client**: inside research-guard (the gateway). Lists tools, sends calls, returns results. No LLM.
- **Agent**: LLM + our code in a LangGraph node. LLM proposes a tool call as JSON; our code passes it to
  the gateway. The LLM never talks to MCP directly.
- AgntID slots in by pointing the client at AgntID's proxy URL instead of the servers.

## Agents
| Agent | Tools granted | LLM used for |
|---|---|---|
| Research | `get_financials`, `search_filings` | Minimal — fixed fetch template (same decision as AFRS analyst) |
| News | `search_news`, `get_recent_filings` | Choosing search queries |
| Writer | `save_draft` | Writing the 1–2 page report |
| Distributor | `send_report` | Recipients + send call (LLM tool-calling; injection target) |

Why News is separate from Research: it handles **untrusted internet content**. A poisoned news item
lands on an agent with no send rights. The human approver is not an agent. Enforcement is deliberately
not an LLM agent (it could be manipulated).

## Report (Writer output, 1–2 pages)
Headline results, segment highlights, margins, guidance/outlook, **latest developments** (news + filings),
sources. Based on AFRS data for MSFT FY26 Q4 / FY27 Q1 outlook.

## Design principles (keep these)
1. **Agents never hold credentials.** Servers do. A hijacked agent can only act through governed calls.
2. **Tool signatures expose what policy needs** as explicit params (ticker, recipients, date range,
   limits). A policy cannot check what is buried inside free text.
3. **One choke point**: every call goes through `core/gateway.py`. Agent code identical in all modes.
4. **Mode flag**: `unsafe` (direct, logged, unchecked) | `guarded` (local engine) | `agntid`.
5. **One task per agent step**, bound to agent + user + originating prompt + resource (ticker).
6. Enforcement is out-of-process, not prompt-based. The Distributor prompt is intentionally naive
   (follows instructions in source material) to show enforcement holds even when the agent is fooled.

## Framework decisions
- **Raw LangGraph** with fixed edges (deterministic routing → clean before/after comparison).
  Borrow task/delegation handling from AgntID's `examples/langchain-deepagents/`.
- Not Agno (MCPTools opens its own session, bypasses AgntID; no example), not ADK (new framework +
  alpha SDK, Gemini-first, callbacks are in-process only), not CrewAI (no example, rigid), not Deep
  Agents as runtime (supervisor routing is non-deterministic; used as reference code only).
- **No A2A.** Agents share one process and pass state; AgntID governs agent→tool (MCP), not agent↔agent.
  A2A is a "how it scales" talking point only.
- LLM via **litellm** (Groq default, e.g. `groq/openai/gpt-oss-120b`); `LLM_MODEL=mock` for deterministic
  offline rehearsal and event-day fallback.

## Repo / environment
- `research-guard/` is a **sibling** of `afrs-scaffold/`, its own git repo, its own `.venv`
  (AgntID SDK is alpha and wraps FastMCP — may pin versions that would break AFRS). Python ≥ 3.10.
- Run everything from repo root (root-level imports: `from config import ...`).
- `afrs_server` lives in **afrs-scaffold** and runs from the AFRS env; research-guard only knows its URL.
- `.gitignore`: `.venv/ .env logs/ outbox/ __pycache__/`

## UI (Streamlit, one page)
1. Google login → verified operator identity
2. Agent identity cards (from `policies/agents.json`)
3. Mode toggle + scenario picker + "Generate report"
4. Live tool-call stream: agent, MCP server/tool, params, decision
5. Escalation prompt (approve/reject unusual recipient) via LangGraph `interrupt()`
6. Report preview
7. Audit trail table

## Observability (talking points)
LangSmith traces (reasoning), AgntID audit log (decisions), Promptfoo red-team config firing injection
attempts at the Distributor → report block rate. Model Armor / Llama Guard = content layer (not built;
AgntID covers the action layer).
