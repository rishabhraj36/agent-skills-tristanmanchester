# Architecture Decision Tree

This document tells the agent which implementation style to choose.

## Start here

Answer these questions in order.

### 1. Does the repo already complete purchases itself?

If **yes**, strongly consider **Architecture B**:

- RevenueCat configured with `purchasesAreCompletedBy`
- existing purchase code remains in charge
- RevenueCat adds entitlement state, dashboards, analytics, and migration support

If **no**, continue.

### 2. Is Superwall the desired paywall surface?

If **yes**, strongly prefer **Architecture A**:

- `CustomPurchaseControllerProvider`
- `SuperwallProvider`
- RevenueCat as entitlement source of truth
- Superwall for placement, targeting, and paywall presentation

If **no**, this skill may not be the right fit. The user might instead want RevenueCat UI or another billing surface.

### 3. Is the app greenfield, or is it migrating an existing billing stack?

- **Greenfield or light integration**: Architecture A
- **Migration, existing transaction completion, or phased rollout**: Architecture B

### 4. Is the app login-first or guest-first?

This does not change the architecture by itself, but it changes identity handling:

- **login-first**: configure RevenueCat with a custom App User ID immediately when possible
- **guest-first**: configure anonymously, then `logIn()` later
- **strict-account products**: reconsider restore behaviour and avoid `logOut()` if anonymous state is forbidden

### 5. Are App Store Server Notifications, Google server notifications, or backend attribution important?

If **yes**:

- identity design matters more than usual
- keep the same stable user ID across RevenueCat and Superwall
- prefer a UUID v4 style ID
- for iOS, understand `appAccountToken` fallback behaviour
- for Android, understand whether you need `passIdentifiersToPlayStore`

Read `ios-uuid-appaccounttoken-and-server-notifications.md`.

### 6. Does Google Play use multiple base plans or offers?

If **yes**, Architecture A still works, but the purchase callback must not just call `purchaseStoreProduct(product)` blindly. It must inspect `basePlanId`, optional `offerId`, and match a RevenueCat `subscriptionOption`.

Read `android-base-plans-offers-and-pending.md`.

## Recommended defaults

## Architecture A: `CustomPurchaseControllerProvider`

Choose this when:

- building a new Expo subscription stack
- Superwall is the paywall and campaign system
- RevenueCat is the billing source of truth
- the repo does not already own purchase completion
- the team wants the clearest Expo implementation

Key benefits:

- best fit for Superwall's Expo guidance
- modern React component model
- easiest place to route Android base plans and offers
- straightforward entitlement mirroring into Superwall

Main risks:

- forgetting to sync `CustomerInfo` into Superwall
- assuming Android offers work with a simple product purchase call
- not planning identity and restore behaviour early enough

## Architecture B: `purchasesAreCompletedBy` / observer-mode migration

Choose this when:

- the repo already has purchase completion logic
- the team is migrating to RevenueCat without replacing everything immediately
- the project needs historical import behaviour via `syncPurchases()`
- changing store-facing billing logic right now would be risky

Key benefits:

- lowest migration risk
- RevenueCat can coexist with existing purchase code
- easier phased rollout in complex production apps

Main risks:

- calling `syncPurchases()` too often
- forgetting to set the iOS StoreKit version
- unclear ownership of restore flows
- duplicating or conflicting purchase completion paths

## Escalate to the user only when truly necessary

Do not stop for small uncertainties. Make the best grounded choice and state the assumption.

Examples:

- If the repo already has `react-native-iap` receipt handling, default to Architecture B.
- If there is no purchase code and the user explicitly wants Superwall paywalls, default to Architecture A.
- If the repo is authenticated and the team mentions webhooks or server notifications, assume identity strategy is a top-priority design constraint.
