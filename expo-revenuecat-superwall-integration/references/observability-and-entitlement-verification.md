# Observability and Entitlement Verification

A production integration should be observable, not just compilable.

## Minimum observability

Add these in development at least:

- RevenueCat debug or verbose logging
- Superwall placement callbacks or `useSuperwallEvents`
- logs for current billing identity after auth changes
- logs for active entitlements after `CustomerInfo` updates

## Forward Superwall events to analytics

Useful events to forward:

- paywall will present
- paywall did present
- paywall dismissed
- paywall skipped
- purchase started
- purchase result
- restore started
- restore result
- subscription status changed
- custom paywall action tapped

These events are valuable for:

- funnel analysis
- experiment validation
- debugging
- support

## Suggested analytics payload shape

Keep a consistent envelope:

```ts
type BillingAnalyticsEvent = {
  name: string;
  appUserId?: string | null;
  superwallUserId?: string | null;
  placement?: string;
  paywallId?: string;
  productId?: string;
  entitlementIds?: string[];
  result?: "presented" | "dismissed" | "purchased" | "restored" | "failed" | "cancelled" | "pending";
  platform: "ios" | "android";
};
```

## RevenueCat trusted entitlements

Trusted Entitlements can provide integrity verification data for entitlement responses.

Important nuance:

- newer RevenueCat SDKs provide verification data by default
- the result is informational only unless the app actually checks it
- RevenueCat does not automatically block unverified entitlements for you

Use this when the app has a strong fraud or tampering risk model.

## Sensible default policy

For most apps:

- log the verification result in debug builds
- keep access decisions based on normal entitlement state
- escalate to stricter handling only if the business has a clear need

For high-risk apps:

- inspect the verification result
- decide whether unverified entitlements should reduce access or trigger review
- coordinate this with backend policy, not just the mobile app

## Other useful signals

Also log:

- current App User ID
- current Superwall identified user
- active offering and product IDs during test purchases
- current restore-behaviour policy in team docs
- launch mode on Android when debugging odd cancellation paths

## Example wiring

See `examples/monetization.shared.tsx` for a simple event bridge shape and `examples/premium-gate.example.tsx` for placement-level hooks.
