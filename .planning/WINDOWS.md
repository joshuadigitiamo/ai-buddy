---
schema_version: 1
open_count: 1
waived_count: 0
fixed_count: 0
total_count: 1
last_updated: 2026-11-07T12:36:13.913Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 03 | unrun-verify | services/chat_bot/buddy_bot/mcp_client.py |  | 03-11: live bot-to-MCP Google ID token call (SA file or metadata server, BOT_SA_EMAILS check) not run offline; checked at 03-12 | open |  | 2026-11-07T12:36:13.913Z |  |

````json
[
  {
    "id": 1,
    "kind": "unrun-verify",
    "phase": "03",
    "file": "services/chat_bot/buddy_bot/mcp_client.py",
    "line": null,
    "description": "03-11: live bot-to-MCP Google ID token call (SA file or metadata server, BOT_SA_EMAILS check) not run offline; checked at 03-12",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-11-07T12:36:13.913Z",
    "resolved_at": null,
    "milestone": null
  }
]
````
