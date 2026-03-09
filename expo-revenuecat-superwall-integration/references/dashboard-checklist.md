# Dashboard and Console Checklist

Use this before deep code work and again before release.

## RevenueCat

- project created
- iOS app added
- Android app added
- public SDK keys copied for both platforms
- store products imported or created
- products attached to the correct entitlement or entitlements
- offerings created if the app uses them
- restore behaviour chosen intentionally
- any one-time products reviewed for restore implications
- server notifications or webhook settings reviewed if backend attribution matters
- app user ID policy documented for the team

## Superwall

- project created
- iOS public key copied
- Android public key copied
- placements created for the premium entry points
- paywalls and campaigns active
- products configured
- entitlements configured and matching the intended runtime mapping
- audience filters reviewed
- user attributes plan reviewed if segmentation matters
- event export or analytics plan reviewed

## App Store Connect / Google Play Console

- bundle IDs and package names match the app
- subscription groups or base plans created
- offers configured intentionally
- test accounts prepared
- internal testing track or TestFlight path ready
- business wants exact Google Play offer control or is happy with defaults

## Alignment rules between systems

The riskiest bugs usually come from mismatch.

Check:

- product IDs match store reality
- entitlement IDs are consistent with app feature names
- Superwall and RevenueCat both know about the relevant products
- the app knows which entitlement IDs should unlock which features
- if multi-tier, the app understands more than one active entitlement

## Identity policy checklist

- guest-first, login-optional, or login-required is documented
- RevenueCat App User ID format is documented
- Superwall user ID format is documented
- iOS UUID requirement is understood when server notifications matter
- Android Play identifier passthrough policy is documented
