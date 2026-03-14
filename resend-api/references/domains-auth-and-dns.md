# Domains, auth, and DNS

This file covers the sending/receiving prerequisites that cause the highest number of Resend
integration failures.

## Raw REST auth

For direct HTTP calls you need:

- `Authorization: Bearer ...`
- `User-Agent: ...`

Missing `User-Agent` is easy to overlook and is one of the fastest things to check when a raw REST
call returns 403.

## Verified domains

Resend requires a verified domain for real sending and receiving.

Key principles:

- the `from` address must match the **exact verified domain**
- if you verified `mail.example.com`, do not send from `example.com`
- if you need to send to anyone other than the account owner, do not rely on `resend.dev`

## Domain creation

Useful fields on `POST /domains`:

- `name`
- `region`
- `tls`
- `capabilities.sending`
- `capabilities.receiving`

Sample:

- `assets/create-domain-sending-receiving.json`

## Regions

Common region choices:

- `us-east-1`
- `eu-west-1`
- `sa-east-1`
- `ap-northeast-1`

Choose the region intentionally rather than defaulting blindly.

## TLS mode

- `opportunistic` — try TLS, fall back if necessary
- `enforced` — require TLS or do not send

Use `enforced` only when the user explicitly wants stricter delivery behaviour and understands the
trade-offs.

## Receiving and MX conflicts

If the root domain already has MX records for another provider, prefer a **subdomain** for Resend
receiving.

Why:

- MX records apply to the exact domain/subdomain they are attached to
- a receiving setup on a dedicated subdomain avoids root-domain conflicts
- mixed-priority or duplicate MX plans on the same hostname are easy to misconfigure

## Verification flow

A good domain flow is:

1. create the domain
2. read the returned DNS records
3. have a human or DNS automation add those records
4. verify the domain
5. only then use it in `from` addresses

Do not imply that domain creation alone is enough.

## API keys

Use the narrowest key that fits the job:

- `sending_access` for send-only agents
- `full_access` only when the agent truly needs to manage other Resend resources

Domain restriction on an API key matters for `sending_access` keys.

Sample:

- `assets/create-api-key.json`
