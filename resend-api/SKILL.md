---
name: resend-api
description: "Use this skill when the task is specifically about Resend or the Resend API/SDK/MCP/CLI: sending or scheduling emails, batch sends, templates, domains and DNS verification, API keys, contacts, segments, topics, broadcasts, inbound email, webhook verification, reply threading, or debugging Resend errors such as 403/1010, domain mismatch, resend.dev restrictions, idempotency, or rate limits. Trigger on mentions of Resend, resend-mcp, svix, email.received, topic_id, verified domains, broadcasts, templates, receiving, or send-email architecture."
compatibility: "Designed for skills-compatible coding agents. Live operations require internet access and a RESEND_API_KEY. The bundled helper uses Python 3.10+ standard library only."
metadata:
  author: OpenAI
  version: "2.0.0"
  openapi-version: "1.5.0"
  source: "https://resend.com/docs/api-reference/introduction"
  last-reviewed: "2026-03-13"
---

# Resend API

This skill is optimised for agents that need to **design**, **generate**, **operate**, or
**debug** Resend integrations with minimal ambiguity.

The goal is not just to know the endpoints. The goal is to make the agent reliably choose the
right Resend primitive, use the safest execution surface, catch common payload mistakes before
mutation, and explain failures in the order that actually saves time.

## Start small

Load only the file that matches the job:

- `references/agent-operating-model.md` — how to think and act like a reliable Resend operator
- `references/endpoint-selection.md` — fast routing across single send, batch, broadcast, template, inbound, and domains
- `references/sending-and-scheduling.md` — sends, scheduling, batching, templates, attachments, reply threading
- `references/domains-auth-and-dns.md` — auth, `User-Agent`, verified domains, DNS, API keys, MX/subdomain caveats
- `references/marketing-model.md` — contacts, topics, contact properties, segments, broadcasts, unsubscribes
- `references/inbound-threading-and-attachments.md` — `email.received`, full-message retrieval, attachments, replies
- `references/webhooks-errors-and-debugging.md` — webhook verification, retries, ordering, rate/quota/idempotency failures
- `references/ai-surfaces-mcp-cli-and-companion-skills.md` — when to prefer SDK vs REST vs official MCP vs official CLI
- `references/recipes.md` — end-to-end flows for the most common real tasks
- `references/workflows-and-events-beta.md` — beta/private-alpha guidance for Workflows and Events
- `assets/endpoint-catalog.json` — compact stable endpoint catalogue plus beta notes
- `assets/resend-openapi.yaml` — full stable OpenAPI snapshot
- `assets/task-router.json` — machine-readable task routing hints
- `assets/error-map.json` — machine-readable failure triage hints
- `assets/testing-addresses.json` — safe Resend testing recipients and blocked fake-domain reminders
- `assets/unsupported-attachment-extensions.json` — outbound attachment extensions that Resend blocks

## Core operating model

### 1) Choose the correct Resend primitive first

Do not jump straight into code.

- **One logical email** → `POST /emails`
- **Up to 100 distinct transactional emails in one request** → `POST /emails/batch`
- **Campaign to a segment** → Broadcasts
- **Reusable message content** → Templates
- **Sender or receiving setup** → Domains
- **Scoped credentials** → API Keys
- **Recipient data and preferences** → Contacts, Topics, Contact Properties, Segments
- **Inbound processing** → Receiving API + `email.received` webhook
- **Event delivery to your app** → Webhooks
- **Custom event-driven orchestration** → Workflows + Events, but treat them as non-GA unless confirmed

If the user is unsure which primitive they need, load `references/endpoint-selection.md` before
writing code.

### 2) Choose the best execution surface

Default order of preference:

1. **Official SDK** when editing an app that already uses a supported language SDK
2. **Official MCP server** when the environment already exposes Resend MCP tools and the task is a live account operation
3. **Official CLI** when the agent needs structured subprocess output in local/CI automation
4. **Raw REST/cURL** for stack-agnostic examples, debugging, or when no better surface is available

Load `references/ai-surfaces-mcp-cli-and-companion-skills.md` if the right surface is part of the
decision.

### 3) Follow the mutation ladder

For any live operation that changes state:

1. **Classify** the task
2. **Recommend** the primitive and surface
3. **Inspect** the schema (`python3 scripts/resend_api.py schema METHOD PATH`)
4. **Lint** the payload before sending (`python3 scripts/resend_api.py lint ...`)
5. **Attach idempotency** for send mutations
6. **Mutate**
7. **Verify** with a read/list call or follow-up check
8. **Persist IDs** you will need later (domain IDs, template IDs, message IDs, webhook IDs, segment IDs)

### 4) Use the right debug order

When a Resend task is failing, inspect these first:

1. Missing or wrong API key
2. Missing `User-Agent` on raw REST
3. `from` address not matching the exact verified domain/subdomain
4. Attempting to use `resend.dev` beyond its testing limits
5. Idempotency misuse
6. Batch limitations
7. Template publication state and variable issues
8. Rate or quota limits
9. Webhook verification/order assumptions
10. Inbound assumptions such as expecting the full message inside the webhook payload

## High-value guardrails

- Prefer **ISO 8601** timestamps in generated code, even though Resend also accepts natural-language scheduling.
- Add an **`Idempotency-Key`** for any `POST /emails` or `POST /emails/batch` request that might be retried.
- For raw REST, always include **`Authorization`** and **`User-Agent`**.
- The `from` address must use the **exact verified domain**, including the verified subdomain.
- `resend.dev` is **testing-only**.
- `/emails/batch` does **not** support `attachments` or `scheduled_at`.
- Treat `email.received` as a **trigger**, then fetch the full inbound message and attachments separately.
- Verify webhook signatures against the **raw request body**, not parsed JSON.
- Use **Topics + Segments** for new marketing/subscription architecture. Avoid building new flows around deprecated Audiences.
- Treat Workflows and Events as **beta/private-alpha**, not a stable production default.

## Bundled helper script

`scripts/resend_api.py` is intentionally agent-oriented.

Commands:

- `catalog` — list known endpoints from the bundled catalogue
- `schema` — inspect a compact endpoint schema summary
- `recommend` — route a free-text task to the right Resend primitive
- `lint` — statically validate common payload and header mistakes
- `scaffold` — print a reusable JSON payload or cURL command from bundled assets
- `doctor` — explain likely causes of common Resend failures
- `request` — make a live API request with cautious retry rules

Examples:

```bash
python3 scripts/resend_api.py catalog --group Emails
python3 scripts/resend_api.py schema POST /emails
python3 scripts/resend_api.py recommend "set up inbound support@ with webhook verification"
python3 scripts/resend_api.py lint POST /emails --json-file assets/send-email-template.json --header "Idempotency-Key: welcome-001"
python3 scripts/resend_api.py scaffold send-batch --format curl
python3 scripts/resend_api.py doctor --status 403 --message "1010 forbidden" --from-address "Acme <alerts@resend.dev>" --to-address "alice@example.com"
python3 scripts/resend_api.py request POST /emails --json-file assets/send-email-basic.json --idempotency-key reset-001
```

## Output expectations

When this skill is active, a strong answer usually includes:

1. The **exact Resend primitive** and endpoint(s)
2. The **best execution surface** for the user's environment
3. A **minimal runnable payload or code example**
4. The **operational caveats** that change the implementation
5. The **verification step** that proves the operation worked

## When to hand off

This skill is Resend-specific. If the user mostly needs one of the following, use or suggest a
more specialised companion skill if available:

- email copywriting/content strategy
- React Email component authoring without much Resend-specific logic
- broader deliverability strategy unrelated to Resend APIs
- generic webhook infrastructure not tied to Resend behaviour

## Example prompts this skill should handle

- “Add Resend to this Next.js app and schedule a password reset email”
- “Why is my raw Resend call failing with 403 and error 1010?”
- “Should I use batch sends, broadcasts, or templates here?”
- “Create a verified sending+receiving domain in eu-west-1”
- “Set up product update preferences with topics, segments, and broadcasts”
- “Build an inbound webhook for support@ and reply in the same thread”
- “Can Resend wait for my custom event before sending a follow-up?”
