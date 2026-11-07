# AI Buddy answer length, persona and tone: research report
*Generated: 2026-11-07 | Sources: 14 | Confidence: Medium (strong agreement on direction, few hard numbers)*

## Executive summary

Every source points the same way: in a chat surface the answer goes first, in one to four sentences or a short list, with no preamble, and detail lives behind the source link or the card. The bot's answer prompt currently gives only a 1200-character cap and no role, so Sonnet fills the space with every step from the page. Anthropic's own guidance for Sonnet 5 is a short conciseness instruction plus **positive examples** of the desired length, which work better than "don't" rules. A persona of one identity sentence plus 3-5 traits is the enterprise norm (Microsoft). Conciseness must not drop conditions, exceptions or deadlines. The bot also adds length itself: long citation lines with raw GitHub URLs. Measure verbosity with a length metric against a minimal reference answer, not only an LLM judge, because LLM judges prefer longer answers.

## 1. Length and structure in chat

- Answer in the first sentence; one to four sentences; a list only for steps or options; link instead of pasting; no "Great question"-style warm-up; say "I don't know" first ([ChatBento](https://chatbento.com/blog/chatbot-answer-length)).
- "Saying too much is as uncooperative as saying too little"; give the core info, put peripheral detail in visuals or omit it ([Google conversation design](https://developers.google.com/assistant/conversation-design/learn-about-conversation), [informational statements](https://developers.google.com/assistant/conversation-design/informational-statements)).
- Keep it short, one idea per message ([Google Business Messages](https://developers.google.com/business-communications/business-messages/guides/how-to/design/language)).
- In channels respond in threads and keep it minimal; DMs can be more conversational ([Slack agent design](https://docs.slack.dev/concepts/agent-design/)).
- Read rates fall sharply above ~80 words; sweet spot 15-35 words ([Conferbot](https://www.conferbot.com/blog/chatbot-conversation-design-masterclass)). **Single vendor source, unverified numbers** — treat as directional only.
- Inverted pyramid: answer, then why, then context ([Being Agent](https://beingagent.org/streaming-and-partial-output)).

## 2. Persona and system prompt

- One sentence of role in the system prompt is the strongest lever; task instructions can follow ([Anthropic: system prompts](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/system-prompts), [best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)).
- Enterprise HR/IT assistants: clear identity statement ("a helpful teammate"), 3-5 traits each with example phrases, "Do: concise answers in 2-3 sentences", warmer on HR topics, more direct on technical ones ([Microsoft Employee Self-Service](https://learn.microsoft.com/en-us/microsoft-365/copilot/employee-self-service/design-best-practices)).
- Microsoft's company-policy template: "professional, approachable, and concise; neutral and non-judgmental on sensitive HR topics" ([template](https://github.com/MicrosoftDocs/m365copilot-docs/blob/main/docs/agent-template-my-company-policy.md)); its eval set has a dedicated Tone & Persona category ([eval sets](https://github.com/microsoft/m365-agent-templates/tree/main/My%20Company%20Policy/Eval%20Sets)).
- KB persona: "Give the key information first, then link to the full document"; neutral, no editorializing; mention exceptions briefly ([CustomGPT](https://docs.customgpt.ai/docs/knowledge-base-assistant-persona)).
- **tu vs Lei:** no authoritative Italian source found. General guidance is to match the company's internal communication style ([Google Business Messages IT](https://developers.google.com/business-communications/business-messages/guides/how-to/design/language?hl=it)). Inference: a colleague-style internal bot in an Italian tech company usually uses "tu" — Joshua decides.

## 3. Concise without losing grounding

- Sonnet 5 calibrates length to task complexity; to reduce verbosity add "Provide concise, focused responses. Skip non-essential context", and prefer **positive examples** over negative rules ([Anthropic: Sonnet 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5)).
- Keep conditions: state prerequisites, exceptions, approval steps and deadlines, not only the headline rule ([OpenMax](https://openmax.com/resources/blog/employee-policy-ai-assistant)). So: short, but the key condition stays.
- On average the core answer is ~42% of an LLM response; the rest is explanation, examples, redundancy ([arXiv 2506.08686](https://arxiv.org/html/2506.08686)).
- Users prefer concise, source-attributed answers over elaborate ones ([arXiv 2508.04713](https://arxiv.org/html/2508.04713)) — single study, self-reported scale.
- Verbosity correlates with model uncertainty ("verbosity compensation") ([ACL 2025](https://aclanthology.org/2025.uncertainlp-main.14.pdf)); a long answer is a weak low-confidence signal.

## 4. How many sources, and how to show them

- Cite the exact document/section/date; every claim traceable ([OpenMax](https://openmax.com/resources/blog/employee-policy-ai-assistant), [Microsoft template](https://github.com/MicrosoftDocs/m365copilot-docs/blob/main/docs/agent-template-my-company-policy.md)).
- Numbered or linked references the user can click, rather than long inline text ([CustomGPT](https://docs.customgpt.ai/docs/knowledge-base-assistant-persona)).
- Insufficient data on an optimal *number* of sources. Inference: show only sources actually cited, cap at 3, and render each as a short linked title.

## 5. Evaluating verbosity

- YapScore: excess characters beyond a curated minimal sufficient answer per prompt ([YapBench, arXiv 2601.00624](https://arxiv.org/pdf/2601.00624)).
- Concise accuracy: correct AND under length k (HCA(k)), soft penalty variant SCA ([Nayab et al. 2026](https://doi.org/10.1016/j.ins.2026.123939)).
- LLM judges prefer longer answers even at equal quality ([verbosity bias, arXiv 2310.10076](https://arxiv.org/abs/2310.10076)) — don't rely only on an LLM judge for "quality"; pair with a length metric.

## Recommendations for AI Buddy (inference from the above)

1. **Persona line** at the top of ANSWER_SYSTEM and ANSWER_SENSITIVE_SYSTEM: "Sei AI Buddy, il collega di Digitiamo che conosce il manuale aziendale e le Guide tecniche: cordiale, diretto, preciso." + register (tu, pending Joshua).
2. **Answer-first rule + length**: first sentence answers; then at most 3-4 short steps only if needed; keep the key condition/deadline; no preamble ("Secondo il manuale…"); `answer` max ~600 chars.
3. **Two positive few-shot examples** (one procedure, one fact) in Italian showing the target length — per Anthropic, more effective than more rules.
4. **Citations**: only sources in `citations`, max 3; render as short link text instead of raw URLs (e.g. `Fonte: Ferie e Permessi (rev. 2026-07-29)`, Guides as linked section title). Verify Google Chat's link syntax for the app's Markdown setting [Medium].
5. **Video card carries the detail**: when a card exists, prose stays to the answer.
6. **Phase 5 evals**: add a minimal reference answer per golden item; track YapScore/HCA(600) alongside correctness and "conditions preserved".

## Methodology

7 searches (Exa + web), 3 sources read in full or near-full (Anthropic Sonnet 5 prompting, Microsoft ESS design guidance, ChatBento). Exa free tier rate-limited 2 queries; retried via web search. Sub-questions: chat answer length/structure; persona/system prompt; concise-but-grounded; number/format of citations; verbosity evaluation; Italian tu/Lei.
Gaps: no authoritative tu/Lei source; no hard data on optimal number of citations; message-length numbers come from one vendor.

## Decision (Joshua, 2026-11-07)

- Register: **tu**.
- `answer` cap: **600 characters**.
- Apply recommendations 1-6 after the 03 review fixes land.
