"""Single choke point for every tool call.

  unsafe  -> agents call MCP servers directly (logged, never checked)
  guarded -> local policy engine decides (stand-in until AgntID access)
  agntid  -> calls go through the AgntID-wrapped MCP client  [VERIFY against quick start]

Agent code is identical in all three modes; only this layer changes."""
import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from fastmcp import Client

import config
from core.audit import AuditLog
from core.policy import LocalPolicyEngine


@dataclass
class ToolOutcome:
    ok: bool
    data: Any = None
    blocked: bool = False
    rule: str = ""
    reason: str = ""


def _unwrap(res) -> Any:
    data = getattr(res, "data", None)
    if data is not None:
        return data
    sc = getattr(res, "structured_content", None)
    if sc:
        return sc.get("result", sc)
    parts = [getattr(c, "text", "") for c in getattr(res, "content", []) or []]
    text = "\n".join(p for p in parts if p)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


@dataclass
class Task:
    gateway: "Gateway"
    agent_id: str
    user_id: str
    task_id: str
    calls: list = field(default_factory=list)

    async def call(self, tool: str, args: dict) -> ToolOutcome:
        return await self.gateway._call(self, tool, args)


class Gateway:
    def __init__(self, mode: str, run_id: str | None = None):
        assert mode in ("unsafe", "guarded", "agntid"), mode
        self.mode = mode
        self.run_id = run_id or uuid.uuid4().hex[:8]
        self.audit = AuditLog()
        self.policy = LocalPolicyEngine() if mode == "guarded" else None
        self._clients: dict[str, Client] = {}
        self._route: dict[str, str] = {}
        self._ag = None  # agntid client

    async def __aenter__(self):
        if self.mode == "agntid":
            import agntid  # pip install agntid-sdk
            self._agntid = agntid
            self._ag = agntid.AgntidMCPClient(config.AGNTID_PROXY_URL)
            await self._ag.__aenter__()
            self._wrapped = agntid.wrap_client(self._ag)
            return self
        for name, url in (("data", config.DATA_MCP_URL), ("comms", config.COMMS_MCP_URL)):
            c = Client(url)
            await c.__aenter__()
            self._clients[name] = c
            for t in await c.list_tools():
                self._route[t.name] = name
        return self

    async def __aexit__(self, *exc):
        if self._ag:
            await self._ag.__aexit__(*exc)
        for c in self._clients.values():
            await c.__aexit__(*exc)

    @asynccontextmanager
    async def task(self, agent_id: str, user_id: str, prompt: str):
        """One task per agent step: binds every tool call to agent + user + originating prompt."""
        if self.mode != "agntid":
            yield Task(self, agent_id, user_id, f"task-{uuid.uuid4().hex[:8]}")
            return
        ag = self._agntid
        task_id = ag.create_task(agent_id=agent_id, user_id=user_id, prompt=prompt)
        async with ag.task_context(self._ag, task_id):
            ok, msg = await ag.send_task_open_checked(self._ag, task_id, agent_id, user_id, prompt)
            if not ok:
                raise PermissionError(f"AgntID refused task open: {msg}")
            self._wrapped.set_task_id(task_id)
            yield Task(self, agent_id, user_id, task_id)

    async def _call(self, task: Task, tool: str, args: dict) -> ToolOutcome:
        log = dict(mode=self.mode, run_id=self.run_id, task_id=task.task_id,
                   user_id=task.user_id, agent_id=task.agent_id, tool=tool, args=args)

        if self.mode == "agntid":
            res = await self._wrapped.call_tool_async(tool, args)
            denial = self._agntid.get_last_denial(clear=True)
            if denial:
                reason = self._agntid.format_denial(denial)
                self.audit.record(**log, allowed=False, rule="agntid_policy", reason=reason)
                return ToolOutcome(False, blocked=True, rule="agntid_policy", reason=reason)
            self.audit.record(**log, allowed=True, rule="agntid_policy", reason="allowed by AgntID")
            return ToolOutcome(True, data=_unwrap(res))

        if self.mode == "guarded":
            d = self.policy.evaluate(task.agent_id, task.user_id, tool, args)
            self.audit.record(**log, allowed=d.allowed, rule=d.rule, reason=d.reason)
            if not d.allowed:
                return ToolOutcome(False, blocked=True, rule=d.rule, reason=d.reason)
        else:
            self.audit.record(**log, allowed=True, rule="none", reason="unsafe mode: not checked")

        server = self._route.get(tool)
        if not server:
            return ToolOutcome(False, reason=f"no MCP server exposes '{tool}'")
        res = await self._clients[server].call_tool(tool, args, raise_on_error=False)
        return ToolOutcome(True, data=_unwrap(res))
