"""python run_demo.py --mode unsafe|guarded|agntid [--scenario 5]"""
import argparse
import asyncio

from rich.console import Console
from rich.table import Table

from agents.graph import build_graph
from core.gateway import Gateway
from scenarios import SCENARIOS

console = Console()


async def main(mode: str, only: str | None):
    async with Gateway(mode) as gw:
        graph = build_graph(gw)
        for sc in SCENARIOS:
            if only and sc["id"] != only:
                continue
            console.rule(f"[bold]Scenario {sc['id']}: {sc['title']}  [dim]({mode})")
            state = {k: sc[k] for k in ("prompt", "user_id", "ticker", "recipients")}
            state["approval_id"] = sc.get("approval_id", "")
            out = await graph.ainvoke(state)
            for e in out.get("events", []):
                tag = "[red]BLOCKED[/]" if e["blocked"] else "[green]ok[/]"
                console.print(f"  {e['agent']:<12} {e['tool']:<45} {tag}  [dim]{e['reason']}")
            console.print(f"  [bold]status:[/] {out.get('status')}")

        t = Table(title=f"Audit trail - run {gw.run_id} ({mode})")
        for col in ("user", "agent", "tool", "decision", "rule", "reason"):
            t.add_column(col)
        for r in gw.audit.records:
            style = "red" if r["decision"] == "BLOCK" else None
            t.add_row(r["user_id"], r["agent_id"].split(".")[-1], r["tool"], r["decision"],
                      r["rule"], r["reason"], style=style)
        console.print(t)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["unsafe", "guarded", "agntid"], default="unsafe")
    p.add_argument("--scenario")
    a = p.parse_args()
    asyncio.run(main(a.mode, a.scenario))
