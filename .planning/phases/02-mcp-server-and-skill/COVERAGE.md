# API Coverage — Phase 2

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Phase 2 integrates two external services (Google OAuth 2.0 / OpenID Connect, Cloud Firestore) and implements the server side of the MCP protocol. Each surface is listed below.

## Google OAuth 2.0 / OpenID Connect (plans 02-05, 02-07)

| capability | decision | reason |
|---|---|---|
| authorization endpoint (code flow with PKCE S256, hd hint) | INTEGRATE | |
| token endpoint: authorization-code exchange | INTEGRATE | |
| token endpoint: refresh_token grant (access_type offline) | INTEGRATE | |
| tokeninfo (access-token validation) | INTEGRATE | |
| userinfo (email, email_verified, hd) | INTEGRATE | |
| JWKS oauth2/v3/certs (service-account ID-token verification) | INTEGRATE | |
| token revocation endpoint | OPT-OUT | not needed yet: no logout requirement in MCP-07; proxy tokens expire; revisit before any rollout beyond Joshua |
| OIDC discovery document (.well-known/openid-configuration) | OPT-OUT | endpoints are fixed constants verified in research; avoids a network call at cold start |
| additional scopes (Drive, Calendar, ...) | OPT-OUT | explicitly out of scope: least privilege, only openid and userinfo.email |
| service-account ID-token minting (metadata server / IAM generateIdToken) | OPT-OUT | belongs to the bot side, Phase 3 (D-12) |
| Workspace Admin SDK directory / group lookup | OPT-OUT | not needed: verified e-mail domain plus hd is the access rule; per-section ACL is out of scope |

## Cloud Firestore (plans 02-03, 02-04, 02-07)

| capability | decision | reason |
|---|---|---|
| create document (collection.document().set) | INTEGRATE | |
| get document by id | INTEGRATE | |
| overwrite / update document | INTEGRATE | |
| delete document | INTEGRATE | |
| TTL policy on expire_at | INTEGRATE | |
| queries (where / order / limit) | OPT-OUT | not needed yet: gap-log review (CONT-03) is a later governance step |
| aggregation queries (count, sum) | OPT-OUT | not needed yet: same reason as queries |
| transactions and batched writes | OPT-OUT | not needed: every write is a single independent document |
| real-time listeners (on_snapshot) | OPT-OUT | not needed: stateless request/response server |
| security rules for client SDKs | OPT-OUT | not needed: only the server writes, with its own service credentials |
| composite indexes | OPT-OUT | not needed: no queries |

## MCP protocol, server side (plans 02-01, 02-02, 02-04, 02-05)

| capability | decision | reason |
|---|---|---|
| tools/list and tools/call with outputSchema / structuredContent | INTEGRATE | |
| resource templates (resources/templates/list, resources/read) | INTEGRATE | |
| streamable HTTP, stateless, JSON responses | INTEGRATE | |
| authorization (protected-resource metadata, 401, OAuth AS facade) | INTEGRATE | |
| static resources list (resources/list) | OPT-OUT | not needed: the template plus handbook_get() cover discovery (Claude's discretion, 02-02) |
| prompts | OPT-OUT | not needed: usage guidance ships as the Skill (MCP-08) |
| sampling and elicitation (server-to-client requests) | OPT-OUT | not needed: stateless server never calls back into the client |
| subscriptions and list-changed notifications | OPT-OUT | not needed: index loaded at cold start only, no held-open stream (MCP-01) |
| logging capability (server-to-client log messages) | OPT-OUT | not needed, and keeps question text out of any log channel |
| completions (argument autocompletion) | OPT-OUT | not needed yet: five tools with simple string arguments |
| SSE transport (HTTP+SSE) | OPT-OUT | deprecated transport; streamable HTTP only |
