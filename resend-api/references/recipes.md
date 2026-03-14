# Recipes

These are concise end-to-end patterns for common tasks.

## 1. Transactional send with retry safety

1. choose `POST /emails`
2. build the payload
3. add `Idempotency-Key`
4. send
5. store the returned message ID
6. verify via message retrieval or downstream webhook observation

Sample:
- `assets/send-email-basic.json`

## 2. Scheduled reminder

1. choose `POST /emails`
2. use `scheduled_at`
3. prefer an ISO timestamp in code
4. use `PATCH /emails/{id}` if the schedule changes
5. use `POST /emails/{id}/cancel` if it should not send

Samples:
- `assets/send-email-scheduled-iso.json`
- `assets/update-scheduled-email.json`

## 3. Chunked batch sending

1. choose `POST /emails/batch`
2. split the workload into chunks of 100 or fewer
3. validate that there are no attachments or `scheduled_at`
4. throttle requests to respect rate limits

Sample:
- `assets/send-batch.json`

## 4. Template lifecycle

1. create template
2. publish template
3. send using `template.id`
4. keep template variables stable and validated

Samples:
- `assets/create-template.json`
- `assets/send-email-template.json`

## 5. Sending + receiving domain setup

1. create domain with sending/receiving capabilities
2. return DNS records to the user
3. tell the user to add them in their DNS provider
4. verify domain
5. only then send or receive with it

Sample:
- `assets/create-domain-sending-receiving.json`

## 6. Inbound support mailbox

1. create webhook subscribing to `email.received`
2. verify signatures using the raw body
3. retrieve the full inbound email
4. fetch attachments if needed
5. send a threaded acknowledgement if required

Samples:
- `assets/create-webhook.json`
- `assets/send-email-threaded-reply.json`

## 7. Topic-based marketing model

1. create Contact Properties
2. create Topics
3. create Segments
4. create Contacts with properties and topic subscriptions
5. create a Broadcast tied to a Segment and Topic

Samples:
- `assets/create-contact-property.json`
- `assets/create-topic.json`
- `assets/create-segment.json`
- `assets/create-contact.json`
- `assets/create-broadcast-send.json`

## 8. 403 triage

1. check API key
2. check `User-Agent`
3. check exact-domain match
4. check `resend.dev` usage
5. inspect error payload for idempotency, quota, or attachment clues

Helper:
```bash
python3 scripts/resend_api.py doctor --status 403 --message "1010"
```
