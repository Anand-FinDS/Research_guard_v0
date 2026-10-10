"""Single choke point for every tool call.

  unsafe  -> direct MCP calls to each server (logged, never checked)
  guarded -> local policy engine decides (offline stand-in for AgntID)
  agntid  -> one SDK-wrapped client on the AgntID runtime (AGNTID_PROXY_URL); the
             runtime decides. Tool names are mapped to the runtime's prefixed names
             (get_financials -> afrs_get_financials). Portal prefix must equal the
             server key in config.MCP_SERVERS.

Agent code is identical in all three modes; only this layer changes."""
import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from fastmcp import Client
from langsmith import traceable

import config
from core.audit import AuditLog
from core.policy import LocalPolicyEngine

AGNTID_CONTROL_PREFIX = "agntid_"   # runtime control tools (task/delegation); never routed


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


def _unwrap_agntid(res) -> Any:
    """SDK success types -> plain data. ToolResult is a dict subclass; ToolResultScalar has .value."""
    if isinstance(res, dict):
        return dict(res)
    if hasattr(res, "value"):
        val = res.value
        return _unwrap(val) if hasattr(val, "content") else val
    return _unwrap(res)


def _agntid_routes(runtime_names: list[str]) -> dict[str, str]:
    """Map our bare tool names to the runtime's prefixed names, e.g. get_financials -> afrs_get_financials."""
    routes: dict[str, str] = {}
    for full in runtime_names:
        if full.startswith(AGNTID_CONTROL_PREFIX):
            continue
        for server in config.MCP_SERVERS:
            prefix = f"{server}_"
            if full.startswith(prefix):
                bare = full[len(prefix):]
                if bare in routes:
                    raise RuntimeError(f"Tool '{bare}' exposed as both '{routes[bare]}' and '{full}'")
                routes[bare] = full
                break
    return routes


@dataclass
class Task:
    gateway: "Gateway"
    agent_id: str
    user_id: str
    task_id: str
    calls: list = field(default_factory=list)

    async def call(self, tool: str, args: dict) -> ToolOutcome:
        return await self.gateway._call(self, tool, args)


def _trace_inputs(inputs: dict) -> dict:
    """What LangSmith shows as the input of a gateway call (skips self / Task internals)."""
    t = inputs.get("task")
    return {"agent_id": getattr(t, "agent_id", None), "user_id": getattr(t, "user_id", None),
            "task_id": getattr(t, "task_id", None), "tool": inputs.get("tool"), "args": inputs.get("args")}


class Gateway:
    def __init__(self, mode: str, run_id: str | None = None):
        assert mode in ("unsafe", "guarded", "agntid"), mode
        self.mode = mode
        self.run_id = run_id or uuid.uuid4().hex[:8]
        self.audit = AuditLog()
        self.policy = LocalPolicyEngine() if mode == "guarded" else None
        self._clients: dict[str, Client] = {}
        self._route: dict[str, str] = {}   # unsafe/guarded: tool -> server; agntid: tool -> runtime name
        self._ag = None                    # agntid: AgntidMCPClient
        self._agntid = None                # agntid: the SDK module
        self._wrapped = None               # agntid: task-correlating wrapper

    async def __aenter__(self):
        if self.mode == "agntid":
            await self._enter_agntid()
            return self
        try:
            for name, url in config.MCP_SERVERS.items():
                c = Client(url)
                try:
                    await c.__aenter__()
                except Exception as e:
                    raise RuntimeError(
                        f"MCP server '{name}' not reachable at {url} - is it running?") from e
                self._clients[name] = c
                for t in await c.list_tools():
                    if t.name in self._route:
                        raise RuntimeError(
                            f"Tool '{t.name}' exposed by both '{self._route[t.name]}' and '{name}'")
                    self._route[t.name] = name
        except Exception:
            await self.__aexit__(None, None, None)
            raise
        return self

    async def _enter_agntid(self):
        import agntid  # source install of agntid-python (0.2.0)
        self._agntid = agntid
        ag = agntid.AgntidMCPClient(config.AGNTID_PROXY_URL)
        try:
            await ag.__aenter__()
        except Exception as e:
            raise RuntimeError(f"AgntID runtime not reachable at {config.AGNTID_PROXY_URL} - "
                               "is the runtime up and Connected?") from e
        self._ag = ag
        try:
            tools = await agntid.get_tools_list(ag)
            self._route = _agntid_routes([t.name for t in tools])
            self._wrapped = agntid.wrap_client(ag)
        except Exception:
            await self.__aexit__(None, None, None)
            raise

    async def __aexit__(self, *exc):
        if self._ag:
            await self._ag.__aexit__(*exc)
            self._ag = None
        for c in self._clients.values():
            await c.__aexit__(*exc)
        self._clients.clear()

    @asynccontextmanager
    async def task(self, agent_id: str, user_id: str, prompt: str):
        """One task per agent step: binds every tool call to agent + user + originating prompt.
        (Target design: one root task per run + one delegation per agent - next increment.)"""
        if self.mode != "agntid":
            yield Task(self, agent_id, user_id, f"task-{uuid.uuid4().hex[:8]}")
            return
        ag = self._agntid
        task_id = ag.create_task(agent_id=agent_id, user_id=user_id, prompt=prompt)
        async with ag.task_context(self._ag, task_id):
            ok, msg = await ag.send_task_open_checked(self._ag, task_id, agent_id, user_id, prompt)
            if not ok:
                raise PermissionError(f"AgntID refused task open: {msg}")
            yield Task(self, agent_id, user_id, task_id)

    @traceable(run_type="tool", name="gateway_call", process_inputs=_trace_inputs)
    async def _call(self, task: Task, tool: str, args: dict) -> ToolOutcome:
        if tool == "send_note":
            # Trusted identity stamped by the gateway, never by the LLM; lets policy check the sender.
            args = {**args, "operator": task.user_id}
        log = dict(mode=self.mode, run_id=self.run_id, task_id=task.task_id,
                   user_id=task.user_id, agent_id=task.agent_id, tool=tool, args=args)

        if self.mode == "agntid":
            return await self._call_agntid(task, log, tool, args)

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

    async def _call_agntid(self, task: Task, log: dict, tool: str, args: dict) -> ToolOutcome:
        ag = self._agntid
        full = self._route.get(tool)
        if not full:
            # Not in the runtime's tool list: unregistered, unreviewed, or excluded by profile.
            reason = f"'{tool}' not visible on the AgntID runtime (unregistered or excluded by profile)"
            self.audit.record(**log, allowed=False, rule="agntid:visibility", reason=reason)
            return ToolOutcome(False, blocked=True, rule="agntid:visibility", reason=reason)

        self._wrapped.set_task_id(task.task_id)   # set per call: correct even if tasks interleave
        ag.get_last_denial(clear=True)            # drop any stale denial from an earlier call
        try:
            res = await self._wrapped.call_tool_async(full, args)
        except Exception as e:                    # non-denial errors are re-raised by the SDK
            reason = f"tool error via AgntID: {e}"
            self.audit.record(**log, allowed=False, rule="agntid:error", reason=reason)
            return ToolOutcome(False, rule="agntid:error", reason=reason)

        if getattr(res, "denied", False):
            denial = ag.get_last_denial(clear=True) or {}
            step = denial.get("denial_step") or "policy"
            reason = getattr(res, "message", "") or denial.get("reason", "denied by AgntID")
            rule = f"agntid:{step}"
            self.audit.record(**log, allowed=False, rule=rule, reason=reason)
            return ToolOutcome(False, blocked=True, rule=rule, reason=reason)

        if isinstance(res, dict) and "error" in res:   # server-side error passed through
            reason = f"tool error: {res['error']}"
            self.audit.record(**log, allowed=True, rule="agntid:allowed", reason=reason)
            return ToolOutcome(False, rule="agntid:error", reason=reason)

        self.audit.record(**log, allowed=True, rule="agntid:allowed", reason="allowed by AgntID")
        return ToolOutcome(True, data=_unwrap_agntid(res))