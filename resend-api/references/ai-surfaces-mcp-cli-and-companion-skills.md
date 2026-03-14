# AI surfaces: SDK, MCP, CLI, and companion skills

Resend now provides several agent-friendly surfaces. This file helps decide which one to use.

## Official SDK

Prefer the official SDK when:

- the user already has application code in a supported language
- you are editing or extending an existing integration
- the task is mostly code generation rather than account operations

## Official MCP server

Prefer the official MCP server when:

- the agent environment already exposes Resend MCP tools
- the user wants live account operations such as sends, contacts, domains, or webhooks
- minimising hand-written transport code is more valuable than producing raw REST examples

Even with MCP, still apply this skill's payload and workflow guidance.

## Official CLI

Prefer the official CLI when:

- the agent is running commands locally or in CI
- structured JSON subprocess output is useful
- you want predictable stdout/stderr behaviour

The CLI is especially good for operational scripts and diagnostics. In agent or CI-style subprocess execution, structured JSON output is often easier to consume than scraping human-oriented terminal text.

## Raw REST

Prefer raw REST when:

- the user wants a portable example
- you are debugging headers or payloads
- there is no installed SDK/MCP/CLI surface

## Agent onboarding expectations

A human still needs to do some account bootstrap work:

- create a Resend account
- create an API key
- verify a domain for real sending/receiving
- add DNS records outside the API when domain verification requires it

Do not imply that an agent alone can finish DNS verification without access to the user's DNS
provider.

## Companion skills

If your environment has them, companion skills can help with adjacent tasks such as:

- React Email authoring
- best-practice email copy/layout
- inbox automation patterns

Keep this Resend skill focused on the platform primitives and operational correctness.

## Agent-facing docs and resources

Resend publishes agent-friendly resources such as markdown/LLM-oriented docs, which makes it reasonable for an agent to ground itself in first-party material before operating. Use those resources to validate behaviour, but still keep this skill as the operational playbook.
