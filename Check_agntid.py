"""Phase 0 smoke test: one allowed and one denied afrs call through the AgntID runtime.

Run from repo root with the research-guard .venv:
    python check_agntid.py

Needs: AgntID runtime connected, afrs_server running bound to 0.0.0.0,
ticker = Exact "MSFT" policy on afrs.get_financials.
"""
import asyncio

import agntid

from config import AGNTID_PROXY_URL

AGENT_ID = "research-guard.research"
USER_ID = "operator-local"          # opaque placeholder; Google `sub` in Phase 4
PROMPT = "Get Microsoft total revenue for Q4-26 for the earnings report."

TOOL = "afrs_get_financials"        # runtime exposes afrs.get_financials as afrs_get_financials
METRIC = "Total revenue"            # use the exact metric string afrs_server accepts
PERIOD = "Q4-26"


async def call(wrapped, ticker: str) -> None:
    result = await wrapped.call_tool_async(
        TOOL, {"ticker": ticker, "metric": METRIC, "period": PERIOD}
    )
    if getattr(result, "denied", False):
        print(f"[{ticker}] DENIED: {result.message}")
    else:
        print(f"[{ticker}] ALLOWED: {result}")


async def main() -> None:
    async with agntid.AgntidMCPClient(AGNTID_PROXY_URL) as client:
        tools = await agntid.get_tools_list(client)
        names = sorted(t.name for t in tools)
        print("Visible tools:", names)
        if TOOL not in names:
            raise SystemExit(f"{TOOL} not visible; check profile / classification / sync.")

        task_id = agntid.create_task(AGENT_ID, USER_ID, PROMPT)
        wrapped = agntid.wrap_client(client, task_id)

        async with agntid.task_context(client, task_id):
            ok, msg = await agntid.send_task_open_checked(
                client, task_id, AGENT_ID, USER_ID, PROMPT
            )
            if not ok:
                raise SystemExit(f"Task not accepted: {msg}")
            print("Task opened:", task_id)

            await call(wrapped, "MSFT")
            await call(wrapped, "AAPL")

        print("Task closed. Search Reporting for task", task_id)


if __name__ == "__main__":
    asyncio.run(main())