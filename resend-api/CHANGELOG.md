# Resend API skill v2

This version shifts the skill from a static reference bundle to an agent operating system for
Resend.

## What changed

- corrected scheduling guidance and separated **single send**, **batch**, and **broadcast** more clearly
- added an explicit **surface-selection model** across SDK, raw REST, the official MCP server, and the official CLI
- added a **mutation ladder** so agents lint, attach idempotency, mutate, verify, and persist IDs in a safer order
- added a much stronger **marketing model** around Topics, Segments, global unsubscribed state, Contact Properties, and Broadcasts
- added much sharper guidance for **inbound processing**, **reply threading**, **temporary attachment downloads**, and **webhook verification**
- expanded the bundled helper script with:
  - `recommend`
  - `lint`
  - `scaffold`
  - `doctor`
- updated the bundled OpenAPI snapshot and compact endpoint catalogue
- expanded the sample payload assets and eval coverage
- quarantined **Workflows/Events** into their own beta/private-alpha reference instead of treating them like stable defaults

## Why it is better for agents

Agents fail less often when they have:

1. a reliable way to choose the right primitive
2. a preflight/lint step before mutation
3. deterministic scaffolds for common tasks
4. a small, machine-readable error map for quick triage
5. instructions for what to verify after a change

That is the design centre of v2.
