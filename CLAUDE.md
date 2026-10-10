# CLAUDE.md — research-guard

AgntID hackathon project. Read `docs/00_START_HERE.md` first; it indexes the rest of `docs/`.

Rules:
- Every tool call goes through `core/gateway.py`. Never let agent code talk to MCP servers directly.
- Agents never hold credentials; MCP servers do.
- Keep agent code identical across `--mode unsafe | guarded | agntid`.
- Synthetic or public data only.
- Run from repo root; use the repo's own `.venv`. `afrs_server` lives in the separate afrs-scaffold repo.
- After changes, run `python run_demo.py --mode guarded` (mock LLM) and confirm scenario outcomes
  in `docs/03_POLICIES_AND_SCENARIOS.md` still hold.
