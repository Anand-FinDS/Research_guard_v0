# AgntID Hackathon — brief

## The challenge (organiser's six requirements)
1. Build a useful AI agent or multi-agent workflow.
2. Connect it to one or more external tools.
3. Identify where unrestricted access creates risk.
4. Define which actions, resources and parameters are allowed, denied, or require approval.
5. Use AgntID to enforce those boundaries while the agent is running.
6. Demonstrate the same workflow before and after runtime enforcement.

Core message from organisers: giving an agent access to a tool does not mean every action with that
tool should be allowed. Think **per action, not per session** — traditional IAM grants broad access up
front; AgntID evaluates each tool call at execution time.

## What AgntID is
Runtime access-control layer between an agent and its tools (MCP proxy + policy engine). Gives agents a
verifiable identity; applies policies, approvals and audit trails. Works with existing tools, IAM and MCP
servers (vendor-hosted, customer-hosted or custom). Enforcement must sit in the execution path.

For each tool invocation AgntID can evaluate:
- which agent is acting
- which user / principal it acts for
- the task and intended action
- the tool and operation requested
- the resource being accessed
- the parameters supplied
- applicable policies and approval conditions

Possible outcomes: **allow, narrow, block, escalate** — and the decision is recorded for audit.

## Questions organisers want each project to answer
- Should this agent call this tool for this task?
- Is it acting on the correct resource?
- Are parameters within safe limits?
- Should the permission expire after this action / task?
- Does this action require human approval?
- What should be logged so the decision can be reviewed later?

Earlier framing questions (also answer in README / pitch):
what workflow; who may access or operate it; what actions allowed/blocked; what data/tools/systems it can
reach; where human approval is needed; how it is monitored, audited, explained.

## Final demo must make clear
1. **Who** the agent is.
2. **What** it is allowed to do.
3. **How** its actions are governed, monitored and audited.

## Logistics
- There is a separate submission portal (details pending). Check whether it wants repo link, video,
  and/or live URL — this decides whether the UI must be deployed or only shown locally.
- Use public or synthetic data only; nothing from Anand's employer.
