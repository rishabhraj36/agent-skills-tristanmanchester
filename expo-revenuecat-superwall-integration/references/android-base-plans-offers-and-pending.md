# Android Base Plans, Offers, and Pending Purchases

Google Play subscriptions are often the place where a "working demo" breaks in production.

## The problem

Superwall can tell your purchase callback more than just a `productId`. On Android it can also provide:

- `basePlanId`
- `offerId` when present

If you ignore those and simply call `purchaseStoreProduct(product)`, you may buy the wrong option or rely on RevenueCat's default offer selection when the product actually needs explicit control.

## Recommended handling

1. Resolve the RevenueCat `StoreProduct` by `productId`.
2. Read `storeProduct.subscriptionOptions`.
3. Build the option identifier from `basePlanId` plus optional `offerId`.
4. Find the matching `SubscriptionOption`.
5. If an explicit match does not exist, decide whether falling back to `defaultOption` is acceptable.
6. Purchase the selected option using the method exposed by the installed `react-native-purchases` version.
7. Only report success to Superwall when the returned `CustomerInfo` has the expected active entitlement.

## When fallback to `defaultOption` is acceptable

Fallback is usually reasonable when:

- the dashboard is meant to choose the default trial or intro offer
- there is no special developer-determined offer logic
- the team is comfortable with RevenueCat selecting the longest free trial or cheapest eligible intro option

Fallback is not ideal when:

- specific Play offers map to specific campaigns or experiments
- you use developer-determined offers
- the business wants exact option control

## Pending purchases

Google Play can place a purchase into a pending state, especially with delayed payment methods or family approval.

Treat pending as its own result, not as a clean success.

Suggested behaviour:

- return `{ type: "pending" }` if your integration surface supports it
- otherwise return a clear failure-style message and explain that access will unlock after Google confirms payment
- keep entitlement checks in place because pending does not guarantee active access yet

## Purchase success is not the same as entitlement success

Even after a purchase callback returns without throwing:

- inspect the `CustomerInfo`
- confirm the expected entitlement is active
- if not active, do not quietly mark the purchase as complete inside your app state

This catches configuration problems such as:

- product IDs exist but entitlements are not attached in RevenueCat
- Superwall and RevenueCat products are out of sync
- the wrong base plan or offer was selected
- a pending purchase has not completed yet

## Developer-determined offer caveat

If the Play Console uses developer-determined offers, RevenueCat's automatic offer logic can still consider them unless you structure your offer setup carefully. For exact control, manually select the `SubscriptionOption` you intend to buy.

## Implementation pointers

- see `examples/custom-purchase-controller.android-offers.tsx`
- see the helper functions in `examples/monetization.shared.tsx`

## Debug checklist

If Android purchases behave unexpectedly:

- verify the incoming `productId`, `basePlanId`, and `offerId`
- inspect the resolved RevenueCat `StoreProduct`
- log the available `subscriptionOptions`
- confirm the expected entitlement becomes active in `CustomerInfo`
- confirm the same product and entitlement setup exists in both RevenueCat and Superwall
- confirm the Android main activity launch mode is `standard` or `singleTop`
