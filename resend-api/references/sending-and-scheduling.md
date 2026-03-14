# Sending and scheduling

This file covers transactional sends, batch sends, templates, attachments, topics, testing, and
threaded replies.

## Single send

Use `POST /emails` for one logical email.

Checklist:

- `from`, `to`, and `subject` are required
- include either message content (`html`, `text`, or SDK-rendered React) **or** a published `template`
- add an `Idempotency-Key` if the operation could be retried
- keep `to` at 50 recipients or fewer
- if you omit `text`, Resend can derive plain text from HTML

Samples:

- `assets/send-email-basic.json`
- `assets/send-email-scheduled-iso.json`
- `assets/send-email-template.json`

## Scheduling

Resend supports scheduled sends on the Emails API.

Use ISO 8601 timestamps in code and generated examples because they are explicit and reproducible.
Natural-language scheduling can still be useful for operator-driven one-offs or dashboards.

Related endpoints:

- `POST /emails`
- `PATCH /emails/{email_id}`
- `POST /emails/{email_id}/cancel`

## Batch sends

Use `POST /emails/batch` when you need to submit up to 100 **distinct** transactional emails in one
request.

Important limitations:

- no `attachments`
- no `scheduled_at`
- each item still has its own `to` constraints

If the user needs 250 emails, chunk the work into multiple batch requests and throttle them.

Sample:

- `assets/send-batch.json`

## Templates

Recommended lifecycle:

1. create or update template
2. publish template
3. send with `POST /emails` using `template.id`

Rules:

- if `template` is present, do not also send raw `html`, `text`, or `react`
- only published templates can be sent
- validate variable names carefully
- reserve room in your implementation for template versioning and publish timing

Sample:

- `assets/create-template.json`
- `assets/send-email-template.json`

## Attachments

Attachments are allowed on `POST /emails` but not on `/emails/batch`.

Before sending attachments:

- ensure each attachment includes `content` or `path`
- estimate total size after Base64 encoding
- avoid file types Resend does not support for outbound attachment sending (`assets/unsupported-attachment-extensions.json`)

## Tags

Tags are useful for correlation, analytics, and debugging.

Good uses:

- environment markers such as `prod` or `staging`
- flow identifiers such as `password_reset`
- customer or tenant grouping keys

Keep tags short, machine-friendly, and stable.

## topic_id on sends

You can scope an email send to a Topic with `topic_id`.

This is not just for Broadcasts. It is useful when a user-specific send should still respect a
topic-based preference model.

## Testing safely

Do not use fake public examples like `@example.com` or `@test.com` as real send recipients.

Prefer the safe addresses in `assets/testing-addresses.json` and a verified test domain.

## Reply threading

To reply into an existing thread, send a normal outbound email but include:

- `In-Reply-To`
- `References`

The values should come from the inbound message IDs you retrieved via the Receiving API.

Sample:

- `assets/send-email-threaded-reply.json`
