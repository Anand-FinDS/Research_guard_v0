"""LLM access via litellm, one place for every agent.

LLM_MODEL=mock          -> no LLM calls; agents use deterministic mock paths (demo default)
LLM_MODEL=openai/...    -> primary model
LLM_FALLBACK_MODEL=...  -> tried once if the primary call fails (e.g. groq/llama-...)

chat() returns {"content": str, "tool_calls": [{"id", "name", "args"}], "model": str}."""
import json
import logging

import litellm

import config

log = logging.getLogger("research_guard.llm")
litellm.drop_params = True          # silently drop params a provider doesn't support


def is_mock() -> bool:
    return config.LLM_MODEL == "mock"


def _models() -> list[str]:
    return [m for m in (config.LLM_MODEL, config.LLM_FALLBACK_MODEL) if m and m != "mock"]


def _parse(resp) -> dict:
    msg = resp.choices[0].message
    calls = []
    for c in msg.tool_calls or []:
        try:
            args = json.loads(c.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {"_raw": c.function.arguments}
        calls.append({"id": c.id, "name": c.function.name, "args": args})
    return {"content": msg.content or "", "tool_calls": calls, "model": resp.model}


async def chat(messages: list[dict], tools: list[dict] | None = None,
               temperature: float = 0.2, **kwargs) -> dict:
    if is_mock():
        raise RuntimeError("llm.chat() called with LLM_MODEL=mock; agents should use their mock path")
    models = _models()
    last_err = None
    for model in models:
        try:
            resp = await litellm.acompletion(
                model=model, messages=messages, tools=tools or None,
                temperature=temperature, num_retries=1, timeout=60, **kwargs)
            out = _parse(resp)
            if model != models[0]:
                log.warning("LLM fallback used: %s failed, answered by %s", models[0], model)
            return out
        except Exception as e:  # noqa: BLE001 - any provider error -> try next model
            log.warning("LLM call failed on %s: %s", model, e)
            last_err = e
    raise RuntimeError(f"All LLM models failed ({', '.join(models)}): {last_err}") from last_err