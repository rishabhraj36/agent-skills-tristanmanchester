# Identity and Restore Behaviour

This is the highest-risk part of a RevenueCat plus Superwall integration.

## Core identity rules

Use the same stable business identity in both systems whenever the product has authentication.

Good identifiers:

- UUID v4
- stable internal opaque IDs
- non-guessable backend-generated IDs

Bad identifiers:

- email addresses
- IDFA or device IDs
- hardcoded strings
- placeholder strings like `guest`, `unknown`, `0`, or `null`

If the app already has numeric or human-readable legacy IDs, strongly consider adding a backend UUID mapping layer rather than sending raw legacy IDs everywhere.

## RevenueCat identity model

### Guest-first products

Recommended flow:

1. configure RevenueCat without `appUserID`
2. let RevenueCat create an anonymous App User ID
3. when auth resolves, call `Purchases.logIn(userId)`

Use this when the product allows purchasing before account creation.

### Login-first products

Recommended flow:

1. resolve auth before configuring billing
2. configure RevenueCat with a known `appUserID`
3. do not call `logOut()` if the product never allows anonymous state

Use this when every purchase must belong to a real account.

### Switching from one logged-in account to another

Use:

```ts
await Purchases.logIn(nextUserId);
```

Do not force a `logOut()` first. That just creates a temporary anonymous ID and adds unnecessary aliasing risk.

### Logging out

Only call:

```ts
await Purchases.logOut();
```

when the product genuinely supports a guest state after logout.

If the product is custom-ID-only, do not log the SDK out. Wait until the next user logs in and then call `logIn(nextUserId)`.

## Superwall identity model

When auth resolves:

```ts
await identify(userId);
```

When signing out to guest state:

```ts
await signOut();
```

If users frequently reinstall or switch accounts and correct paywall assignments matter immediately, consider the `restorePaywallAssignments` option on identify. Use it deliberately because it changes paywall startup behaviour.

## Restore behaviour in RevenueCat

RevenueCat restore behaviour is a dashboard-level policy. Pick it intentionally.

### Default and usually recommended: Transfer to new App User ID

Use when:

- the app is guest-first
- login is optional
- easy recovery matters more than strict account ownership
- the team wants the least painful restore experience

### Keep with original App User ID

Use only when:

- every purchaser must have an account
- purchases must never transfer across accounts
- the support team can recover lost account ownership safely

This is stricter and can create support burden.

### Important nuance with anonymous users

Anonymous users can be aliased with a known App User ID later. That can be good for guest-first products, but confusing for strict-account products.

## Restores versus sync

### `restorePurchases()`

Use only from an explicit user action such as a Restore Purchases button.

Reason:

- it can trigger store account prompts
- it is the user-facing restore path

### `syncPurchases()`

Use only for intentional cases such as:

- importing historical purchases during migration
- syncing past subscriptions after login in observer mode
- specific recovery flows

Do not run it on every launch.

## Product-shape recommendations

### Login required before purchase

- configure RevenueCat with custom App User ID from the start
- identify the same ID in Superwall
- avoid anonymous sessions
- consider whether `Keep with original App User ID` is worth the support cost

### Login optional

- allow anonymous state
- `logIn()` when auth appears
- keep default transfer behaviour unless the business has a strong reason not to

### Guest-first purchase flow

- anonymous configuration is normal
- users will later alias into known accounts
- make restore UX clear inside settings
- support staff should know how aliases and restores behave

## Support and debugging advice

- show the current App User ID in app settings
- keep both RevenueCat and Superwall user IDs visible in debug builds if possible
- note the chosen restore-behaviour policy in the project README or team docs
- if you rely on webhooks or server notifications, verify that the ID observed on the backend matches the intended business user
