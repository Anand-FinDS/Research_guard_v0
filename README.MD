# research-guard

A multi-agent equity research workflow that writes a Microsoft results report and distributes it, with
**AgntID enforcing access control on every tool call at runtime**. The same workflow runs twice: once
without enforcement and once through AgntID. Agent code is identical in both runs.

Built for the AgntID Hackathon ("Build an AI Agent You'd Actually Trust").
![research-guard architecture](docs/architecture.svg)
## What the workflow does

Four agents run in a fixed LangGraph pipeline:

```
Retriever  ->  News  ->  Writer  ->  Distributor
```

| Agent identity | Tools | Job |
|---|---|---|
| `research-guard.retriever` | `afrs.get_financials`, `afrs.search_filings` | Reported financials (SQLite) and management commentary (Qdrant hybrid search over the earnings call and press release) |
| `research-guard.news` | `news.search_news` | Recent company news via Serper |
| `research-guard.writer` | `comms.save_draft` | Writes the report: Headline, Segment Breakdown, Management Commentary and Outlook, Recent News, Sources |
| `research-guard.distributor` | `comms.send_note` | Sends the report to recipients |

The Writer can run with a real LLM (litellm) or in deterministic mock mode. The LLM prompt forbids new
or recalculated figures; numbers are formatted in code and the model only copies them.

## Where unrestricted access creates risk

In a sell-side research workflow, an agent with send and data tools can:

- research or distribute a **restricted ticker**
- send a report to someone behind a **compliance wall**
- send a report to an **external** address
- distribute on behalf of a user who is **not authorised to publish** (an associate can draft, not send)

Giving an agent `send_note` does not mean every `send_note` call should be allowed. Each call needs to
be checked against who is asking, for which ticker, to whom.
   ![research-guard architecture](docs/architecture.png)
## How it is governed

```
agents (LangGraph)
   |
core/gateway.py   single choke point; stamps agent, user, task; same agent code in every mode
   |
   |-- --mode unsafe  -> MCP servers directly (logged, not checked)
   |-- --mode agntid  -> AgntID runtime (MCP proxy + policy engine, :8082)
                              |
                              |-- afrs_server   :8003  (financials + commentary)
                              |-- news_server   :8004  (Serper)
                              |-- comms_server  :8002  (save_draft, send_note)
```

Design rules:

1. **Agents never hold credentials.** The MCP servers hold the Serper key, the database and the
   vector store. A misled agent can only act through governed tool calls.
2. **Tool signatures expose what policy needs.** `ticker`, `recipient`, `operator`, `max_results`
   are explicit parameters, so a policy can check them. Nothing important is buried in free text.
3. **Identity comes from the application, not the model.** The gateway stamps `operator` (the
   logged-in user) into every `send_note` call. The LLM cannot set or forge it.
4. **Enforcement is out of process.** It sits in the AgntID runtime, not in a prompt.

### AgntID policies

| Tool | Rule | What it blocks |
|---|---|---|
| `afrs.get_financials`, `afrs.search_filings` | `ticker` = `MSFT` | Restricted ticker (AAPL) |
| `news.search_news` | `ticker` = `MSFT`; `max_results` <= 10 | Off-task or oversized queries |
| `comms.save_draft` | `ticker` = `MSFT` | Drafts on restricted tickers |
| `comms.send_note` | `operator` = `anand` | Associate distributing |
| `comms.send_note` | `recipient` ends with `@researchguard.example` | Compliance-walled desk (`@wall.researchguard.example`) and external recipients |
| `comms.send_note` | `ticker` = `MSFT` | Distributing restricted tickers |

Runtime protection profile: **Medium** (reads and normal writes visible; delete/execute hidden).

### Audit

Every call is recorded twice:

- **AgntID Reporting**: agent, task, tool, parameters, decision, policy and reason.
- **Local JSONL** (`logs/audit.jsonl`): mode, run id, task id, user, agent, tool, arguments,
  decision, rule, reason. In AgntID mode the rule records the stage that denied the call
  (`agntid:policy_evaluation`), so a policy denial is distinguishable from a tool error.

Task ids are shared, so a local record can be looked up in AgntID Reporting.

## Results: before vs after

| # | Scenario | Without guard | With AgntID |
|---|---|---|---|
| R1 | Anand sends the MSFT report to the approved list | distributed | distributed (allowed) |
| R2 | Anand's list includes a compliance-walled desk and an external client | sent to all 3 | desk sent; walled and external **blocked** |
| R3 | Associate builds and tries to send | sent | report saved; send **blocked** (operator) |
| R4 | Same workflow on AAPL (restricted) | ran end to end | **blocked** at the first data call (ticker) |

`python make_showcase.py` runs all scenarios in both modes and writes `outbox/showcase.html` with the
full per-call detail.

## Run it

Prerequisites: Python 3.10+, Docker Desktop, an AgntID portal account, a Serper API key.

1. **AgntID runtime**: follow the AgntID Quick Start (`docker compose up -d` with their compose file),
   register the runtime in the portal, choose the Medium profile.
2. **Environment** (repo root):
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   git clone https://github.com/AGNTID-AI/agntid-python.git ..\agntid-python
   pip install -e ..\agntid-python
   ```
   `.env`: `SERPER_API_KEY`, optional `LLM_MODEL` / `OPENAI_API_KEY` (default `LLM_MODEL=mock`).
3. **MCP servers**, each bound to `0.0.0.0` so the runtime container can reach them:
   ```
   $env:MCP_HOST="0.0.0.0"; python -m mcp_servers.news_server     # :8004
   $env:MCP_HOST="0.0.0.0"; python -m mcp_servers.comms_server    # :8002
   ```
   `afrs_server` (:8003) lives in my separate AFRS project; see "Limitations".
4. **Portal**: add each server as Remote HTTP (`http://host.docker.internal:<port>/mcp`, prefix =
   `afrs` / `news` / `comms`), approve the tool classifications, add the policies above.
5. **Run**:
   ```
   python check_agntid.py              # smoke test: MSFT allowed, AAPL denied
   python run_demo.py --mode unsafe
   python run_demo.py --mode agntid
   python make_showcase.py             # presentation page
   ```

Start order matters: MCP servers first, then the runtime. After restarting a server, restart the
runtime and make one warm-up call.

## What I learned about AgntID while building this

- **Tool classification decides visibility.** `save_draft` was first classified as operation
  `OTHER`, which the Medium profile excludes. Correcting the label to WRITE made it visible. Clear,
  verb-first tool descriptions help.
- **The visual policy editor's Exact match takes one value.** A recipient allowlist was modelled as a
  domain suffix, with the walled desk on a subdomain. A true per-address list would need the
  Advanced (Rego) editor.
- **Policies check parameters, so identity has to be a parameter.** User-aware rules work by having
  the gateway stamp the verified user into the call.
- **The runtime caches MCP sessions.** Restarting a server gives 404s until the runtime reconnects.
- **SDK 0.2.0 pins `fastmcp<3` and `mcp<2`.** This repo runs fastmcp 2.14.7 / mcp 1.29.0, the
  pair from the SDK's own lock file.

## Limitations

- `afrs_server` is in a separate repository (my AFRS project), so reviewers cannot run the
  Retriever as-is.
- One AgntID task per agent step. The target design is one root task per report with a delegation
  per agent.
- The local `guarded` mode (offline policy engine) predates the final scenarios and is not kept in
  sync with them.
- Recipients are synthetic `.example` addresses; `send_note` writes to `outbox/sent.jsonl` instead of
  sending email.

## Roadmap

- Human approval (AgntID review-required) for off-list internal recipients instead of a flat block
- Gmail sending from one authorised account
- Root task plus per-agent delegations
- Permission expiry test: replaying `send_note` after the task closes
- Restricted-company redaction in news results, and a prompt-injection fixture aimed at the Distributor
- Streamlit UI with Google login, using the verified identity as `operator`

## Data

Public Microsoft financial data and filings, public news via Serper, synthetic email addresses.
Nothing from my employer.
