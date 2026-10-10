"""Thin litellm wrapper. LLM_MODEL=mock gives deterministic offline behaviour."""
import json
import litellm
import config


def is_mock() -> bool:
    return config.LLM_MODEL == "mock"


async def chat(messages: list, tools: list | None = None) -> dict:
    resp = await litellm.acompletion(model=config.LLM_MODEL, messages=messages,
                                     tools=tools, temperature=0)
    msg = resp.choices[0].message
    calls = []
    for tc in msg.tool_calls or []:
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        calls.append({"id": tc.id, "name": tc.function.name, "args": args})
    return {"content": msg.content or "", "tool_calls": calls, "raw": msg}
