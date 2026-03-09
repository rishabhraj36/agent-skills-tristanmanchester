# Troubleshooting

## 1. The app builds in Expo Go but monetisation does not work

Expected. The combined integration should be treated as a development-build setup, not a real Expo Go path.

Fix:

- create a development build
- confirm native modules are installed
- if native folders are stale, consider a clean prebuild path before rebuilding

## 2. `PlacementNotFound` for a placement that exists in the dashboard

In Expo development, Superwall dashboard changes do not hot-reload into the running app.

Fix:

- completely quit the development app
- relaunch the app
- then retry the placement

## 3. Purchase succeeded but premium UI stayed locked

Common causes:

- entitlement sync into Superwall is missing
- the wrong entitlement IDs are being mapped
- products exist in one dashboard but not the other
- entitlements do not match exactly
- Android selected the wrong base plan or offer
- the purchase is pending, not active

Fix:

- inspect `CustomerInfo.entitlements.active`
- inspect what `setSubscriptionStatus` receives
- confirm Superwall and RevenueCat dashboard products and entitlements align
- inspect Android `basePlanId` and `offerId`

## 4. Webhooks or server notifications show the wrong user

Common causes:

- `identify()` ran after the first purchase
- the billing ID is not a UUID on iOS
- old SDK versions are still in use
- Android identifier passthrough is not configured as intended
- historical purchases happened before the identity fix

Fix:

- identify before purchase
- use the same UUID billing ID in RevenueCat and Superwall
- update SDK versions
- document that old historical purchases may remain linked to alias IDs

## 5. Account switching creates confusing identity states

Common cause:

- logging out RevenueCat before logging in the next known account

Fix:

- when switching account A to account B, call `logIn(nextUserId)` directly
- call Superwall `identify(nextUserId)` directly
- only use `logOut()` when the product really supports guest state

## 6. Restore behaves differently than expected

Common causes:

- the RevenueCat restore-behaviour setting was never chosen intentionally
- the team expects strict account ownership but the dashboard is still on the default transfer model
- the product is guest-first but support expects login-first semantics

Fix:

- review `identity-and-restore-behaviour.md`
- confirm the dashboard setting
- document the chosen policy for support

## 7. Android purchase gets cancelled when the app backgrounds

Common cause:

- main activity launch mode is incompatible with Play verification flows

Fix:

- ensure Android launch mode is `standard` or `singleTop`

## 8. Existing subscribers do not show up after migration

Common cause:

- RevenueCat was added in observer mode or `purchasesAreCompletedBy` mode but no migration sync ran

Fix:

- call `syncPurchases()` after the user logs in or during a deliberate migration checkpoint
- do not add it to every app launch

## 9. Restoring old consumables or one-time purchases on Android is inconsistent

Common cause:

- the app uses affected versions around Google Billing Client 8 and older RevenueCat fixes are missing

Fix:

- upgrade `react-native-purchases`
- if one-time products matter, test reinstall and restore flows explicitly
- do not assume subscription testing covers one-time product recovery

## 10. The app seems right but dashboard targeting still feels wrong

Common causes:

- placements are too generic
- user attributes are missing
- the team manually gates too much in code and bypasses audience logic

Fix:

- register business-action placements
- set useful user attributes
- let Superwall audience targeting and entitlements do more of the work
