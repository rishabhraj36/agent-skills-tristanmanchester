# Marketing model

This file explains how Contacts, Topics, Contact Properties, Segments, and Broadcasts fit together.

## The correct mental model

- **Contacts** = people
- **Contact Properties** = typed profile fields
- **Segments** = sender-controlled target groups
- **Topics** = recipient-facing preference categories
- **Broadcasts** = campaign sends to Segments
- **global unsubscribed** = hard stop for all Broadcasts

## Contacts

A Contact can store:

- name fields
- global unsubscribed status
- arbitrary property values
- segment memberships
- topic subscriptions

Sample:

- `assets/create-contact.json`

## Contact Properties

Create Contact Properties first when you want stable, typed profile data that segments or internal
logic can depend on.

Good examples:

- `plan_tier` as a string
- `company_size` as a number
- `country` as a string

Sample:

- `assets/create-contact-property.json`

## Topics

Topics define preference buckets such as:

- product updates
- security notices
- newsletter
- billing tips

Use Topics when a recipient should be able to opt out of one category without leaving everything.

Important design note:

- the topic's `default_subscription` is a creation-time decision
- make this decision deliberately because it cannot simply be treated as a casual default later

Sample:

- `assets/create-topic.json`

## Segments

Segments are your internal targeting logic.

Examples:

- all paid users
- free users in Germany
- trial users who signed up in the last 14 days

Segments are not a substitute for Topics. They answer **who** you want to target, not **what
preference category** the message belongs to.

Sample:

- `assets/create-segment.json`

## Broadcasts

Use Broadcasts for campaign-style sends to a Segment.

Recommended pattern:

1. define Contact Properties
2. create Topics
3. create Segments
4. create Contacts with properties and topic subscriptions
5. create a Broadcast for a Segment
6. include `topic_id` when the content maps to a preference category

Samples:

- `assets/create-broadcast-draft.json`
- `assets/create-broadcast-send.json`

## Audiences

Audiences are legacy/deprecated territory for new designs.

For new builds, prefer Segments + Topics + Contacts.

## Global unsubscribed vs topic subscriptions

These are different layers:

- `unsubscribed: true` means the contact is unsubscribed from all Broadcasts
- per-topic subscription controls whether a contact wants a specific category

Do not collapse them into the same boolean.
