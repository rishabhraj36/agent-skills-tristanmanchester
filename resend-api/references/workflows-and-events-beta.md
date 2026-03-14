# Workflows and Events beta/private-alpha

Workflows and Events are powerful, but they should not be presented as a stable default unless the
account has confirmed access.

## How to treat them

Assume:

- they are beta/private-alpha
- availability may be limited
- shapes and semantics may still change
- they should not be the default answer when stable primitives are enough

## When they are a good fit

Use them only when the user explicitly needs orchestration such as:

- waiting for a custom event
- branching conditions
- delayed follow-up sequences
- platform-managed workflow execution rather than application-managed orchestration

## When to avoid them

Prefer stable Resend APIs plus your own app logic when:

- a webhook + queue + normal email send is enough
- the integration must be conservative and production-stable
- the user's account access is unknown

## Agent guidance

If the user asks for Workflows or Events:

1. acknowledge the feature area
2. label it as beta/private-alpha
3. confirm the concept using the docs
4. avoid treating it as universally available
5. offer a stable fallback architecture when appropriate
