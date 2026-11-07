# Phase 3: Google Chat Bot - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-07
**Phase:** 03-google-chat-bot
**Areas discussed:** Confidence + citation gate, Sensitive topics, Conversation flow, Dev wiring

---

## Confidence + citation gate

| Question | Options | Selected |
|----------|---------|----------|
| What decides confidence | Deterministic + LLM / Deterministic only / Separate judge call | Deterministic + LLM |
| Citation strictness | Source id match / Id + quoted span | Source id match |
| On gate fail | One retry, then refuse / Refuse immediately | One retry, then refuse |
| Referente source | Reuse the Skill table / Static role only | Reuse the Skill table |

## Sensitive topics

| Question | Options | Selected |
|----------|---------|----------|
| Detection | LLM classify step / Keyword list + LLM / Keyword list only | LLM classify step |
| Response shape | Rule + referral / Referral only | Rule + referral |
| Gap log when no rule | Yes, same as any gap / No, never log / Log topic only | Yes, same as any gap |
| Table location | Shared data file / Parse SKILL.md / Duplicate in bot config | Shared data file |

## Conversation flow

| Question | Options | Selected |
|----------|---------|----------|
| Reply delivery | Placeholder then edit / Single final message | Placeholder then edit |
| Memory | Stateless per message / Thread context in memory / Thread context persisted | Thread context, persisted |
| Memory safeguards | Hashed key + short TTL / Downgrade to in-memory / Persist as-is | Hashed key + short TTL |
| History use | Last 3 Q/A reformulation only / Last 5 Q/A every step | Last 3 Q/A, reformulation only |
| Non-question messages | Canned replies, no LLM / Everything through RAG | Canned replies, no LLM |
| Off-topic gap logging | No, classify first / Yes, log all refusals | No, classify first |

**Notes:** Claude flagged that persisted thread memory in a DM effectively links question text to one person (BOT-11 / art. 4). User accepted the HMAC key + 24 h TTL + no sender fields safeguard set; recheck before rollout.

## Dev wiring

| Question | Options | Selected |
|----------|---------|----------|
| Pub/Sub source | Real topic + emulator in tests / Emulator only | Real topic + emulator in tests |
| Meridian location | Own container in compose / Already running on host | Own container in compose |
| Models | Haiku reformulate + Sonnet answer / Sonnet both / Opus answer | Haiku reformulate, Sonnet answer |
| Live proof | Live Chat checkpoint / Automated only | Live Chat checkpoint |

## Claude's Discretion

Card layout and thumbnail source, Italian strings, graph node layout, structured-output schemas, default thresholds, Pub/Sub ack/idempotency, config names, BOT-08 guard mechanics, intake port design.

## Deferred Ideas

- Recheck the thread-memory privacy posture before any second user.
- Card layout refinements after Phase 5 feedback.
