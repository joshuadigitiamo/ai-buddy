---
schema_version: 1
open_count: 3
waived_count: 1
fixed_count: 3
total_count: 7
last_updated: 2026-11-07T15:33:38.453Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 03 | unrun-verify | services/chat_bot/buddy_bot/mcp_client.py |  | 03-11: live bot-to-MCP Google ID token call (SA file or metadata server, BOT_SA_EMAILS check) not run offline; checked at 03-12 | open |  | 2026-11-07T12:36:13.913Z |  |
| 2 | 03 | unrun-verify | services/chat_bot/buddy_bot/service.py |  | 03-12: room @mention and bare '@AI Buddy' with blank argumentText not exercised live (03-04/03-09 risk) | fixed |  | 2026-11-07T13:51:16.980Z | 2026-11-07T15:33:38.024Z |
| 3 | 03 | unrun-verify | services/chat_bot/buddy_bot/render.py |  | 03-12: Guarda button #t= scene offset not verified live (Chat buttons expose no href) | waived | Superseded: live check ran 2026-11-07; browser downloads mp4 instead of playing (hosting issue, tracked in new entry). Deferred to Phase 4 by Joshua | 2026-11-07T13:51:17.091Z | 2026-11-07T15:33:38.348Z |
| 4 | 03 | unrun-verify | services/chat_bot/buddy_bot/service.py |  | 03-12: intro message on install not verified (first ADDED_TO_SPACE hit the publish permission error, not re-triggered) | fixed |  | 2026-11-07T13:51:17.235Z | 2026-11-07T15:33:38.131Z |
| 5 | 03 | unrun-verify | services/chat_bot/buddy_bot/prompts.py |  | 03-12: parking-style out-of-index question classification is model behaviour; cover in Phase 5 golden set | open |  | 2026-11-07T13:51:17.412Z |  |
| 6 | 03 | todo | .env.example |  | 03-12: VIDEO_THUMBNAIL_URL is Google's sample image; replace with Digitiamo logo (only SVG exists) | fixed |  | 2026-11-07T13:51:17.562Z | 2026-11-07T15:33:38.241Z |
| 7 | 03 | deviation | services/chat_bot/buddy_bot/render.py |  | Guarda button opens mp4 as a download, #t= never applies: (1) GitHub release assets served as attachment; (2) joshuadigitiamo/Guides repo is private, video URLs 404 anonymously; (3) only 238 of 2524 video_map rows have start_seconds, 2286 are readme_fallback. Accepted for M1, deferred to Phase 4 by Joshua (access-controlled Cloud Storage video/mp4 inline + better timestamp coverage) | open |  | 2026-11-07T15:33:38.453Z |  |

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
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-11-07T13:51:16.980Z",
    "resolved_at": "2026-11-07T15:33:38.024Z",
    "milestone": null
  },
  {
    "id": 3,
    "kind": "unrun-verify",
    "phase": "03",
    "file": "services/chat_bot/buddy_bot/render.py",
    "line": null,
    "description": "03-12: Guarda button #t= scene offset not verified live (Chat buttons expose no href)",
    "status": "waived",
    "reason": "Superseded: live check ran 2026-11-07; browser downloads mp4 instead of playing (hosting issue, tracked in new entry). Deferred to Phase 4 by Joshua",
    "recorded_at": "2026-11-07T13:51:17.091Z",
    "resolved_at": "2026-11-07T15:33:38.348Z",
    "milestone": null
  },
  {
    "id": 4,
    "kind": "unrun-verify",
    "phase": "03",
    "file": "services/chat_bot/buddy_bot/service.py",
    "line": null,
    "description": "03-12: intro message on install not verified (first ADDED_TO_SPACE hit the publish permission error, not re-triggered)",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-11-07T13:51:17.235Z",
    "resolved_at": "2026-11-07T15:33:38.131Z",
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
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-11-07T13:51:17.562Z",
    "resolved_at": "2026-11-07T15:33:38.241Z",
    "milestone": null
  },
  {
    "id": 7,
    "kind": "deviation",
    "phase": "03",
    "file": "services/chat_bot/buddy_bot/render.py",
    "line": null,
    "description": "Guarda button opens mp4 as a download, #t= never applies: (1) GitHub release assets served as attachment; (2) joshuadigitiamo/Guides repo is private, video URLs 404 anonymously; (3) only 238 of 2524 video_map rows have start_seconds, 2286 are readme_fallback. Accepted for M1, deferred to Phase 4 by Joshua (access-controlled Cloud Storage video/mp4 inline + better timestamp coverage)",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-11-07T15:33:38.453Z",
    "resolved_at": null,
    "milestone": null
  }
]
````
