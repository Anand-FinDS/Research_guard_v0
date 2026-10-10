# AgntID Python SDK — notes (from public README, github.com/AGNTID-AI/agntid-python, Oct 2026)

Status: **alpha**, v0.2.x on main (release wheel v0.1.1). Python ≥ 3.10. MIT.
Install: `pip install agntid-sdk` (extras: `[msk]`, `[openai]`).

Architecture: agent → AgntID Python SDK → AgntID Runtime (MCP proxy + policy engine) → MCP tool servers.
The SDK correlates every tool call to the user prompt that triggered it ("task intent").

## Quick start flow
```python
import agntid
mcp_client = agntid.AgntidMCPClient("http://localhost:8082/mcp")
async with mcp_client:
    tools = await agntid.get_tools_list(mcp_client)
    wrapped = agntid.wrap_client(mcp_client)
    task_id = agntid.create_task(agent_id="my-agent", user_id="user-123", prompt=user_prompt)
    async with agntid.task_context(mcp_client, task_id):          # sends task_close on exit
        ok, msg = await agntid.send_task_open_checked(mcp_client, task_id, "my-agent", "user-123", user_prompt)
        wrapped.set_task_id(task_id)
        result = await wrapped.call_tool_async("my_tool", {"arg": "value"})
```

## Core API
`AgntidMCPClient(url)` (wraps FastMCP) · `wrap_client(client, task_id=None)` (injects `_task_id`, strips
`__agntid_*`) · `create_task` · `close_task` · `task_context` · `send_task_open_checked` → `(ok, msg)` ·
`get_tools_list` · `get_last_denial(clear=True)` · `format_denial` · `print_denial` · `ToolResult` ·
`DenialResult` (falsy) · `require_env`.
Adapter: `agntid.adapters.langchain_deep_agents.DeepAgentsAdapter` converts framework context and
delegations into AgntID's canonical task/delegation contract (no LangChain import needed).

## Examples in repo
- `examples/langchain-deepagents/` — supervisor + specialist subagents, multi-turn, HITL, execution
  evidence. **Closest match; read first.**
- `examples/agentcore/` — Amazon Bedrock AgentCore + LangGraph, AWS-free tests.
- `examples/fastmcp/` — OpenAI function-calling + FastMCP, no framework.
- `examples/msk/` — Semantic Kernel.

## Not in README (ask organisers)
Policy syntax; narrow/escalate mechanics; response inspection; expiry semantics; multi-server proxying.
