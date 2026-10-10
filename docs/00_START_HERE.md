# research-guard — START HERE (handoff for Claude)

Read this file first, then the others in order. They replace the chat history from the AFRS project
where this plan was worked out (Oct 2026).

## What this project is
`research-guard` is Anand's entry for the **AgntID Hackathon** ("Build an AI Agent You'd Actually Trust").
A multi-agent equity research workflow that produces a 1–2 page Microsoft earnings report with a
"latest developments" section and emails it to a distribution list — with **AgntID enforcing
runtime access control on every tool call**. The demo runs the same workflow before (unsafe) and after
(secured) enforcement. Goal is learning and a clean demo, not necessarily winning.

## Who Anand is (only what matters for this work)
Delivery Manager – Equity Research (11+ yrs, sell-side). Building GenAI / agentic AI skills; strong finance
domain, comfortable with Python, LangGraph, Agno, Qdrant, litellm, Groq. Separate larger project: AFRS
(multi-agent financial research system) — research-guard reuses its MSFT data via MCP, but is its own repo.

## How to work with Anand
- Direct, factual communication. No hype, no self-congratulation, no hedging filler.
- Code: give **complete files in code blocks with the exact path** (e.g. `core/gateway.py`) and say
  what changed. He applies edits and runs things himself. For small changes, show only the changed
  function/block plus where it goes.
- Test what you can in your sandbox before handing over; state clearly what was and wasn't verified.
- Keep his voice in any written submission text.
- Don't expand scope silently. Flag tradeoffs, recommend one option, let him decide.

## File index
| File | Contents |
|---|---|
| `01_HACKATHON_BRIEF.md` | The challenge, what AgntID evaluates, what the demo must show |
| `02_ARCHITECTURE.md` | Agents, MCP servers, gateway, flow, framework decisions, UI |
| `03_POLICIES_AND_SCENARIOS.md` | Policy table and the 8 demo scenarios |
| `04_STATUS_AND_PLAN.md` | What exists (tested), build order, open questions, risks |
| `05_AGNTID_SDK_NOTES.md` | AgntID Python SDK summary (from its public README) |

## Current state in one paragraph
A v0 codebase exists and is tested (synthetic tickers, 3 agents, local policy engine, unsafe/guarded
modes, all 7 v0 scenarios pass with a mock LLM). The agreed v1 plan replaces synthetic data with real
MSFT data from AFRS (via an `afrs_server` MCP server living in the AFRS repo), adds Serper news, Gmail
sending, a 4th agent, four decision types (allow / narrow / block / escalate), and a Streamlit UI with
Google login. AgntID hackathon resources and quick start had **not yet arrived** at handoff.

## Next action
Build step 1 of `04_STATUS_AND_PLAN.md`: the `afrs_server` MCP wrapper. Ask Anand to paste his AFRS
SQL fact-query function and Qdrant hybrid-search function so the wrapper calls them unchanged.
