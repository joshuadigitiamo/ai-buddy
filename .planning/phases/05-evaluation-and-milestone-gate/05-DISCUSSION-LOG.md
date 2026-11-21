# Phase 5: Evaluation and Milestone Gate - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-21
**Phase:** 05-evaluation-and-milestone-gate
**Areas discussed:** Guides checkout, Golden set storage, Judging method, Eval runtime + budget, MLflow scope

---

## Guides checkout (raised mid-session: "my other PC I pushed some updates on Guide repo")

| Option | Description | Selected |
|--------|-------------|----------|
| Pull + note re-sync | Fast-forward now; CONTEXT records regenerate GUIDES_INDEX.md + re-sync as prerequisite | ✓ |
| Pull + re-sync now | Pull, run sync, check drift before continuing | |
| Don't pull | Leave it | |

**User's choice:** Pull + note re-sync. Pulled to 4526500.

## Golden set storage

| Question | Options | Selected |
|----------|---------|----------|
| Storage | Split file (Guides committed, handbook gitignored) / All gitignored / All committed paraphrased | Split file |
| Mix | ~40: 15H/13G/7N/5S / 30 minimal / 50 max | ~40 |
| Review | status field gates the gate / status recorded only | status field gates |
| Follow-ups | Single-turn only / a few 2-turn items | Single-turn only |

## Judging method, Eval runtime + budget, MLflow scope

**User's choice:** "On this phase accept all your recommendations." No per-question prompts. Claude's recommended options were recorded as D-08..D-21. Main alternatives considered:
- **Judge:** Opus 5.5 via LlmClient (chosen) vs Sonnet as judge (self-preference) vs Joshua-only manual scoring vs MLflow built-in judges (provider wiring around Meridian).
- **Runtime:** in-process `run_workflow` against compose mcp-server (chosen) vs Chat/Cloud Run end to end.
- **Recall query:** reformulated query, cached (chosen) vs raw Italian question.
- **Empty-context:** unrelated fixture index (chosen) vs truly empty index.
- **MLflow:** eval-only autolog (chosen) vs manual spans in bot vs tracing the live bot.

## Claude's Discretion

Paths and names, judge prompt and schema, report format, fixture content, eval-profile networking.

## Deferred Ideas

Judge-verdict override; live bot tracing; LLM eval in CI; hybrid retrieval (D5 trigger); multi-turn items; HR golden set.
