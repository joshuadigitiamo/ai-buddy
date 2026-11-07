---
schema_version: 1
open_count: 6
waived_count: 0
fixed_count: 0
total_count: 6
last_updated: 2026-11-07T13:51:17.562Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 03 | unrun-verify | services/chat_bot/buddy_bot/mcp_client.py |  | 03-11: live bot-to-MCP Google ID token call (SA file or metadata server, BOT_SA_EMAILS check) not run offline; checked at 03-12 | open |  | 2026-11-07T12:36:13.913Z |  |
| 2 | 03 | unrun-verify | services/chat_bot/buddy_bot/service.py |  | 03-12: room @mention and bare '@AI Buddy' with blank argumentText not exercised live (03-04/03-09 risk) | open |  | 2026-11-07T13:51:16.980Z |  |
| 3 | 03 | unrun-verify | services/chat_bot/buddy_bot/render.py |  | 03-12: Guarda button #t= scene offset not verified live (Chat buttons expose no href) | open |  | 2026-11-07T13:51:17.091Z |  |
| 4 | 03 | unrun-verify | services/chat_bot/buddy_bot/service.py |  | 03-12: intro message on install not verified (first ADDED_TO_SPACE hit the publish permission error, not re-triggered) | open |  | 2026-11-07T13:51:17.235Z |  |
| 5 | 03 | unrun-verify | services/chat_bot/buddy_bot/prompts.py |  | 03-12: parking-style out-of-index question classification is model behaviour; cover in Phase 5 golden set | open |  | 2026-11-07T13:51:17.412Z |  |
| 6 | 03 | todo | .env.example |  | 03-12: VIDEO_THUMBNAIL_URL is Google's sample image; replace with Digitiamo logo (only SVG exists) | open |  | 2026-11-07T13:51:17.562Z |  |

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
  },
  {
    "id": 2,
    "kind": "unrun-verify",
    "phase": "03",
    "file": "services/chat_bot/buddy_bot/service.py",
    "line": null,
    "description": "03-12: room @mention and bare '@AI Buddy' with blank argumentText not exercised live (03-04/03-09 risk)",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-11-07T13:51:16.980Z",
    "resolved_at": null,
    "milestone": null
  },
  {
    "id": 3,
    "kind": "unrun-verify",
    "phase": "03",
    "file": "services/chat_bot/buddy_bot/render.py",
    "line": null,
    "description": "03-12: Guarda button #t= scene offset not verified live (Chat buttons expose no href)",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-11-07T13:51:17.091Z",
    "resolved_at": null,
    "milestone": null
  },
  {
    "id": 4,
    "kind": "unrun-verify",
    "phase": "03",
    "file": "services/chat_bot/buddy_bot/service.py",
    "line": null,
    "description": "03-12: intro message on install not verified (first ADDED_TO_SPACE hit the publish permission error, not re-triggered)",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-11-07T13:51:17.235Z",
    "resolved_at": null,
    "milestone": null
  },
  {
    "id": 5,
    "kind": "unrun-verify",
    "phase": "03",
    "file": "services/chat_bot/buddy_bot/prompts.py",
    "line": null,
    "description": "03-12: parking-style out-of-index question classification is model behaviour; cover in Phase 5 golden set",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-11-07T13:51:17.412Z",
    "resolved_at": null,
    "milestone": null
  },
  {
    "id": 6,
    "kind": "todo",
    "phase": "03",
    "file": ".env.example",
    "line": null,
    "description": "03-12: VIDEO_THUMBNAIL_URL is Google's sample image; replace with Digitiamo logo (only SVG exists)",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-11-07T13:51:17.562Z",
    "resolved_at": null,
    "milestone": null
  }
]
````
