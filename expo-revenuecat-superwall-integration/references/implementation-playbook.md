# Implementation Playbook

This is the main workflow for integrating RevenueCat plus Superwall into a React Native Expo app.

## 1. Preflight audit

Before editing code, answer:

1. Is the app using Expo Router or a plain `App.tsx` root?
2. Is auth required before purchase, optional, or absent?
3. Is there already purchase code in the repo?
4. Does the product have more than one entitlement tier?
5. Does Google Play use multiple base plans or offers?
6. Are webhooks, App Store Server Notifications, or backend attribution part of the project?

Then inspect:

- `package.json`
- `app.json` or `app.config.*`
- `App.tsx` or `app/_layout.tsx`
- auth provider files
- existing monetisation files
- environment handling

## 2. Choose the architecture

### Architecture A: Superwall paywalls plus RevenueCat entitlements via `CustomPurchaseControllerProvider`

Use this for most new Expo work.

Choose it when:

- Superwall is the paywall UI
- RevenueCat is the billing and entitlement source of truth
- the app does not already own transaction completion
- you want the cleanest modern Expo integration

### Architecture B: RevenueCat with `purchasesAreCompletedBy` and existing IAP code

Use this when:

- the repo already owns purchase completion logic
- the team is migrating an existing billing stack
- the team needs RevenueCat dashboards and entitlements without rewriting all purchase code at once
- you must import historical subscriptions carefully

Read `architecture-decision-tree.md` before choosing.

## 3. Install packages

Base install:

```bash
npx expo install expo-superwall react-native-purchases expo-build-properties
```

Optional RevenueCat UI only when explicitly requested:

```bash
npx expo install react-native-purchases-ui
```

Do not add the UI package if Superwall is the only paywall and management surface.

## 4. Update Expo config

Set minimum platform versions via `expo-build-properties`.

Example `app.config.ts` fragment:

```ts
export default {
  expo: {
    plugins: [
      [
        "expo-build-properties",
        {
          ios: {
            deploymentTarget: "15.1",
          },
          android: {
            minSdkVersion: 23,
          },
        },
      ],
    ],
  },
};
```

Also confirm:

- bundle identifiers and package names already exist
- EAS or native build pipeline is configured
- Android main activity launch mode is `standard` or `singleTop`

## 5. Add public environment variables

Typical keys:

```env
EXPO_PUBLIC_REVENUECAT_IOS_API_KEY=appl_xxx
EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY=goog_xxx
EXPO_PUBLIC_SUPERWALL_IOS_API_KEY=sw_ios_xxx
EXPO_PUBLIC_SUPERWALL_ANDROID_API_KEY=sw_android_xxx
```

Optional:

```env
EXPO_PUBLIC_DEFAULT_PLACEMENT=upgrade_pro
```

Never put RevenueCat secret keys or webhook secrets in the client.

## 6. Implement the root providers

### Plain Expo app

Use `references/examples/app.example.tsx`.

### Expo Router app

Use `references/examples/expo-router-layout.example.tsx`.

Normal root shape for Architecture A:

1. configure RevenueCat once
2. mount `CustomPurchaseControllerProvider`
3. mount `SuperwallProvider`
4. render `SuperwallLoading`
5. render the app inside `SuperwallLoaded`
6. mount one entitlement sync component inside the loaded tree
7. optionally mount one analytics bridge

### Why this order

- RevenueCat should be ready before purchase callbacks run.
- Superwall should load before placements are used.
- Subscription sync should run only once and as close to the root as practical.

## 7. Configure RevenueCat deliberately

### Guest-first apps

- configure without `appUserID`
- later call `Purchases.logIn(userId)` on auth success
- on logout, call `logOut()` only if the app genuinely supports anonymous state

### Login-first apps

- configure with the custom App User ID from the start
- avoid generating anonymous IDs at all
- do not call `logOut()` if every app session must always belong to a known account

### Production advice

- enable verbose or debug logging only in development
- reveal the App User ID somewhere in app settings for support
- use a UUID v4 or another non-guessable stable identifier
- never use an email address

## 8. Implement Architecture A purchase handling

Inside `CustomPurchaseControllerProvider`:

- resolve the requested RevenueCat `StoreProduct` using `productId`
- for Android subscriptions, use `basePlanId` and optional `offerId` to pick a matching `subscriptionOption`
- fall back to the product's default option only when appropriate
- call `purchaseStoreProduct` on iOS or when there is no special Android option selection
- return `cancelled`, `pending`, or `failed` explicitly when needed
- after purchase, check the resulting `CustomerInfo`
- only treat the purchase as successful when the expected entitlement state is active

See:

- `examples/monetization.shared.tsx`
- `examples/custom-purchase-controller.android-offers.tsx`
- `android-base-plans-offers-and-pending.md`

## 9. Implement Architecture B migration path

Use this only when the repo already owns purchase completion.

- configure RevenueCat with `purchasesAreCompletedBy`
- on iOS, set the StoreKit version to match the app
- keep the existing purchase completion logic
- call `syncPurchases()` after login or migration checkpoints, not every launch
- audit restore behaviour carefully before shipping

See `examples/observer-mode-migration.tsx`.

## 10. Sync entitlements into Superwall

This step is easy to miss and causes "purchase succeeded but app is still locked" bugs.

Recommended pattern:

- call `Purchases.getCustomerInfo()` on launch and when premium areas open
- add `Purchases.addCustomerInfoUpdateListener(...)`
- map `customerInfo.entitlements.active` keys into Superwall entitlements
- pass `ACTIVE`, `INACTIVE`, or `UNKNOWN` as appropriate

Prefer syncing the full entitlement set instead of just `isSubscribed`.

## 11. Sync identities across both systems

When auth resolves:

- RevenueCat: `logIn(userId)` or configure with `appUserID`
- Superwall: `identify(userId)`

When switching known account A to known account B:

- call `logIn(nextUserId)` directly
- call `identify(nextUserId)` directly
- do not force a pointless `logOut()` first

When signing out to guest state:

- RevenueCat: `logOut()` only if guest mode is real and desired
- Superwall: `signOut()`

When account switching or reinstall-heavy usage makes paywall assignment restoration important, consider Superwall's `restorePaywallAssignments` identity option. Use it intentionally, not by default.

## 12. Register placements

Examples:

- `upgrade_pro`
- `export_pdf`
- `voice_clone`
- `remove_generation_limit`

Recommendations:

- use one placement per business action
- keep names dashboard-friendly
- do not pre-emptively block every call with manual entitlement checks
- let Superwall audiences and entitlements decide whether to show a paywall when possible
- use `getPresentationResult()` when you need to inspect what would happen before presenting

See `examples/premium-gate.example.tsx`.

## 13. Add observability

Implement at least one of these:

- Superwall event forwarding via `useSuperwallEvents`
- analytics forwarding for paywall shown, purchase started, purchase result, restore started, restore result
- RevenueCat debug logging in development
- optional entitlement verification checks for high-risk products

## 14. Test with a real matrix

Use `testing-matrix.md`. Minimum cases:

- iOS purchase success
- Android purchase success
- cancel flow
- pending flow
- restore flow
- guest-to-authenticated upgrade
- authenticated purchase on a second account
- reinstall and restore
- full restart after dashboard changes
- webhook or server-notification identity checks when applicable

## 15. Final delivery checklist

When editing the user's repo, finish with:

- changed file list
- chosen architecture and why
- manual dashboard and console work still required
- assumptions and open questions
- exact run command for the development build
- test steps that cover the riskiest path first
