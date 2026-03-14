# Webhooks, errors, and debugging

This file covers signature verification, delivery semantics, and the highest-value failure checks.

## Webhook verification

Always verify against the **raw request body** before parsing JSON.

Headers to use:

- `svix-id`
- `svix-timestamp`
- `svix-signature`

Store the webhook signing secret securely.

## Delivery semantics

Design your webhook handler with these assumptions:

- delivery is at least once
- order is not guaranteed
- retries happen when you do not return a 2xx response

Practical consequences:

- deduplicate on `svix-id`
- make handlers idempotent
- use event timestamps when ordering matters

## Recommended webhook handler shape

1. read raw body
2. verify signature
3. parse JSON
4. dedupe on `svix-id`
5. persist event
6. dispatch business logic
7. return 2xx quickly

## Common error triage order

### 401/403

Check these first:

1. API key present and correct
2. raw REST request has a `User-Agent`
3. `from` domain exactly matches a verified Resend domain
4. not using `resend.dev` outside its testing rules

### 422

Common causes:

- malformed `from`
- invalid attachment
- unsupported attachment type
- using fake test domains in a real send flow
- payload shape mismatch

### 429

Treat 429 as a rate-limiting event, not a random transient failure.

Respect response headers and slow down globally.

### 409 / idempotency

If you see idempotency conflicts:

- do not spray retries with the same key in parallel
- keep one stable idempotency key per logical send operation
- wait for the in-flight request to resolve before retrying

## The bundled `doctor` command

Use the helper for quick first-pass triage:

```bash
python3 scripts/resend_api.py doctor --status 403 --message "1010"
python3 scripts/resend_api.py doctor --status 422 --message "invalid_attachment"
```

The helper is not a substitute for reading response bodies, but it is very good at catching the
usual fast-fail mistakes.
