# iOS UUID, appAccountToken, and Server Notifications

This document matters whenever the project cares about backend attribution, webhooks, or server notifications.

## Why this exists

On iOS, Superwall supplies an `appAccountToken` with StoreKit 2 transactions.

That sounds great, but there is a crucial nuance:

- if you call `identify(userId)` with a valid UUID, that UUID can flow through as the `appAccountToken`
- if you have not identified yet, Superwall uses the anonymous alias UUID
- if you pass a non-UUID user ID, StoreKit rejects it and Superwall falls back to the alias UUID

This means the backend-observed identifier can differ from the app-level ID unless identity is designed carefully.

## Strong recommendation

If the project uses any of the following:

- App Store Server Notifications
- RevenueCat server-side purchase tracking
- custom attribution
- backend entitlement reconciliation
- webhook-driven account linking

then use the **same stable UUID v4** for:

- the app's billing identity
- RevenueCat App User ID
- Superwall identify ID

If the existing backend uses some other primary key, add a UUID mapping layer.

## RevenueCat interaction

RevenueCat warns that when using server-to-server tracking together with `appAccountToken` or `obfuscatedExternalAccountId`, those values should match the RevenueCat App User ID and that ID should be a valid UUID v4.

This is one of the most important production details in the whole integration.

## What to do in practice

### Login-first app

- generate or fetch the user's stable UUID before billing initialisation
- configure RevenueCat with that App User ID
- call Superwall `identify()` with the same UUID before the user purchases

### Guest-first app

- accept that early anonymous transactions may carry an alias UUID
- when the user later logs in, aliasing can still work, but historical server-side attribution may point at the earlier anonymous identifier
- if this is unacceptable, redesign the product flow so billing only begins after a known UUID exists

## Android note

If the business needs the Play-side identifier to map cleanly back to the app user, review whether Superwall should pass identifiers through to Google Play on Android. This is useful, but only if the identifier policy is compatible with exposing that stable opaque ID.

## Webhook troubleshooting checklist

If webhook or server-notification identities look wrong:

- confirm `identify()` runs before any purchase
- confirm the identifier is a UUID
- confirm the same value is used in RevenueCat and Superwall
- confirm Android identifier passthrough settings if testing Google Play
- update old SDK versions before debugging historical mismatches
- remember that historical purchases made before the identity fix may remain attached to the old alias identity

## Suggested team policy

Write this into the project docs:

- the canonical billing user ID format
- whether the app allows anonymous purchases
- whether server notifications are enabled
- whether Android Play-side identifier passthrough is enabled
- what support should do when a webhook points at an older alias ID
