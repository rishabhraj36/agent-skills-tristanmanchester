# Inbound, threading, and attachments

Inbound flows are easy to under-specify. This file shows the safe, complete model.

## Recommended inbound architecture

1. Subscribe to `email.received`
2. Verify the webhook signature on the raw body
3. Use the inbound email ID to retrieve the full email
4. If needed, fetch attachment download URLs
5. Process, store, route, or reply

## Why the webhook is not enough

Treat the webhook as the **trigger**, not the full payload of truth.

The full HTML, plain text, headers, and attachment details should be retrieved through the Receiving
API.

## Receiving endpoints

Common endpoints:

- `GET /emails/receiving`
- `GET /emails/receiving/{email_id}`
- `GET /emails/receiving/{email_id}/attachments`
- `GET /emails/receiving/{email_id}/attachments/{attachment_id}`

## Attachments

Inbound attachment retrieval returns metadata and temporary download URLs.

Design implications:

- fetch attachment data promptly if you need durable processing
- persist your own copy if you need long-term access
- do not assume attachment bytes are embedded in the webhook

## Replying in the same thread

To keep a reply in the same conversation thread:

- include `In-Reply-To` with the inbound message ID
- include `References` with prior message IDs, space-separated
- use `Re:` in the subject unless you explicitly want a new thread

Sample:

- `assets/send-email-threaded-reply.json`

## Forwarding or automation

A common pattern is:

1. receive an inbound support email
2. classify or route it
3. fetch attachments
4. create/update a ticket
5. optionally send a threaded acknowledgement

This is often a better first architecture than jumping to Workflows.
