# Agent operating model

This file explains how to act like a careful Resend operator rather than a generic code generator.

## The decision tree

### A. What kind of task is this?

Classify the request first:

- **integration codegen** — add or edit code inside an application
- **live operation** — make a real API call against a Resend account
- **debugging** — explain a failure or fix a payload
- **architecture** — choose the correct Resend primitive or data model

### B. Which surface is best?

Use the surface that fits the environment, not the one you happen to know best.

| Surface | Best when | Avoid when |
| --- | --- | --- |
| Official SDK | The codebase already uses a supported SDK language | The user wants stack-neutral docs or simple shell steps |
| Official MCP | The environment already exposes Resend MCP tools for live account work | You need portable code snippets that must run outside the MCP host |
| Official CLI | You need structured JSON output in local scripts or CI | The environment cannot install or invoke local CLIs |
| Raw REST/cURL | You need language-neutral examples or low-level debugging | The user already has a well-integrated SDK and wants idiomatic code |

## The mutation ladder

For any action that changes state:

1. **recommend the primitive**
2. **inspect the schema**
3. **lint the payload**
4. **add safety headers**
5. **mutate**
6. **verify**
7. **persist IDs and next-step context**

Never skip straight from “user asked” to “POST request”.

## Default safety rules

- For raw REST, include both `Authorization` and `User-Agent`.
- For email sends, add `Idempotency-Key` before retrying.
- Prefer explicit ISO timestamps in code.
- Record the returned IDs from create/send operations.
- For any webhook plan, include signature verification, dedupe, and out-of-order handling.
- For any inbound plan, fetch the full message after the webhook trigger.

## Response template for agent answers

A good Resend answer usually follows this shape:

1. **Primitive**: which Resend object/endpoint to use
2. **Surface**: SDK, MCP, CLI, or REST
3. **Payload/code**: minimal runnable example
4. **Caveats**: only the operational details that matter here
5. **Verify**: how to prove it worked

## Common anti-patterns

- choosing `/emails/batch` just because there are multiple recipients
- using Broadcasts for transactional flows
- using raw REST examples without a `User-Agent`
- forgetting exact-domain matching in the `from` address
- treating `email.received` as if it contains the full inbound message body and attachment bytes
- using deprecated Audiences in a new design
- assuming Workflows/Events are generally available
