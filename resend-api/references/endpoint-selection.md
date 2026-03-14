# Endpoint selection

Pick the primitive first. Almost every bad Resend implementation starts by choosing the wrong one.

## Quick matrix

| Need | Use | Main endpoints | Notes |
| --- | --- | --- | --- |
| One logical email | Emails | `POST /emails` | Works even if `to` is an array |
| Scheduled one-off email | Emails | `POST /emails`, `PATCH /emails/{id}`, `POST /emails/{id}/cancel` | Prefer ISO timestamps in code |
| Up to 100 distinct transactional emails in one call | Batch emails | `POST /emails/batch` | No attachments, no `scheduled_at` |
| Reusable content with variables | Templates + Emails | `POST /templates`, `POST /templates/{id}/publish`, `POST /emails` | Send only published templates |
| Campaign to a target set of contacts | Broadcasts | `POST /broadcasts`, `POST /broadcasts/{id}/send` | Pair with Segments and preferably Topics |
| Verified sender or receiving domain | Domains | `POST /domains`, `POST /domains/{id}/verify`, `GET /domains` | DNS changes are still required after create |
| Scoped credentials | API Keys | `POST /api-keys`, `GET /api-keys` | Prefer narrow scope |
| Recipient preferences and targeting | Contacts / Topics / Segments / Contact Properties | multiple | New builds should prefer Segments over Audiences |
| Event delivery to your app | Webhooks | `POST /webhooks` | Always verify signatures |
| Inbound message processing | Receiving API + Webhook | `GET /emails/receiving*` + `email.received` | Fetch full content separately |
| Event-driven orchestration | Workflows + Events | beta/private-alpha | Confirm account availability first |

## Decision notes

### Single send vs batch

Use `POST /emails` when the request is really one email, even if there are multiple recipients in `to`.

Use `POST /emails/batch` when you have many **distinct** transactional emails and want to submit up
to 100 of them in one call.

### Emails vs Broadcasts

Use Emails for transactional or user-specific operational sends.

Use Broadcasts when you are sending campaign-style content to a Segment and want list-management
behaviour such as topic-based unsubscribe preferences.

### Topics vs Segments

- **Topics** = recipient-facing preference categories
- **Segments** = sender-controlled targeting groups

They work together rather than replacing each other.

### Inbound

For inbound, design the flow as:

1. webhook trigger
2. retrieve full message
3. retrieve attachment download URLs if required
4. process or reply

Do not assume the webhook payload is the full email.
