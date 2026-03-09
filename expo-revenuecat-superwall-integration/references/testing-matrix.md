# Testing Matrix

Do not ship based on one successful sandbox purchase.

## Build setup checks

Before purchase testing:

- development build works on iOS and Android
- public SDK keys load correctly per platform
- app compiles with the chosen architecture
- at least one placement is active in Superwall
- products and entitlements exist in RevenueCat
- test users are ready in sandbox or test store as needed

## Recommended environments

### Early code validation

Use:

- development builds
- RevenueCat Test Store when appropriate
- mocked or internal analytics

### Pre-release validation

Use:

- iOS sandbox or TestFlight test accounts
- Google Play internal testing or closed testing
- real purchase flows through store sandboxes
- backend logging if server notifications or webhooks matter

## Scenario matrix

### A. App startup

1. cold start without auth
2. cold start with known authenticated user
3. cold start after reinstall
4. full restart after changing Superwall placements or campaigns

Expected results:

- providers initialise once
- no duplicate purchase listeners
- no placement-not-found surprises after a restart
- entitlement sync runs once

### B. Purchase flows

1. successful purchase on iOS
2. successful purchase on Android
3. user-cancelled purchase
4. network or store failure
5. pending Android purchase
6. purchase completes but entitlement is misconfigured

Expected results:

- success unlocks the correct entitlement
- cancellation is not shown as success
- pending does not falsely unlock premium access
- misconfigured entitlements are visible in logs and UI state

### C. Restore flows

1. explicit Restore Purchases button tapped by a guest user
2. restore on a signed-in user
3. restore after reinstall
4. restore when transfer behaviour matters across two accounts

Expected results:

- restore is user-triggered
- entitlement state updates correctly
- account ownership behaviour matches the chosen RevenueCat restore policy

### D. Identity transitions

1. guest uses app, then logs in
2. user A signs out to guest state
3. user A switches directly to user B
4. login-first app launches with custom ID from the start

Expected results:

- same ID is used in RevenueCat and Superwall
- direct account switch does not create unnecessary anonymous IDs
- support can inspect the active billing identity

### E. Webhook and attribution checks

Only for projects that need them.

1. make a fresh purchase after `identify()`
2. inspect backend webhook or server-notification payload
3. compare app identity, RevenueCat App User ID, and server-observed identifier
4. repeat with Android if Play-side identifier passthrough matters

Expected results:

- backend identifiers match the intended user model
- UUID expectations are met on iOS
- historical purchases made before the identity fix are understood and documented

## Release gate

Before sign-off, the project should be able to answer:

- which architecture is in use and why
- whether guest purchases are allowed
- which restore behaviour is configured in RevenueCat
- whether webhooks and server notifications rely on UUID billing IDs
- which entitlements unlock which features
- how support staff can find a user's App User ID
