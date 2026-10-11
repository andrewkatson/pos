# Documentation

These docs are the product spec: they describe how Good Vibes Only behaves, in
detail, across the backend and all three clients. Consult the relevant page
before changing domain logic, and update it in the same change when behavior
changes.

## Using the app

- [Navigation and post actions](navigation-and-post-actions.md) — the bottom
  bar, user search, follower lists, the post options menu, who liked a post,
  saved posts, and locking comments.
- [Text formatting](text-formatting.md) — caption fonts and background colors,
  the Text / Image composer, and inline comment formatting.
- [Hashtags](hashtags.md) — `#tag` parsing and tag feeds.
- [Positive interest tags](interest-tags.md) — the interest vocabulary and how
  it personalizes the discovery feed ranking.
- [Audience, relationships and blocking](audience-and-relationships.md) —
  follow categories, nested post/comment audiences, audience badges, and
  blocking.
- [Sharing](sharing.md) — share links, the public post and profile pages, link
  previews, and Universal Links / App Links.
- [Profiles](profiles.md) — profile photos (and their moderation) and bios.

## Moderation and safety

- [Post classification](post-classification.md) — the async AI classifier
  cascade, pre-filters, model chain, and the classification worker.
- [Reporting and user moderation](reporting.md) — how a report triggers
  automated re-review and, if needed, human review.
- [Bans and appeals](bans-and-appeals.md) — outright vs. shadow bans, and
  appealing hidden content or a ban.
- [Age and identity](age-and-identity.md) — the 16+ floor, adult/minor
  segregation, and the no-photos-of-children rule.

## Accounts and sign-in

- [Accounts](accounts.md) — account settings, usernames, membership numbers,
  account deletion, and the terms of service.
- [Authentication](authentication.md) — Google sign-in, email verification,
  two-factor authentication, and new-device login emails.
- [Google sign-in setup](google-sign-in-setup.md) — wiring the OAuth client
  IDs for each surface.
- [Push notifications](push-notifications.md) — device tokens, per-type
  preferences, APNs/FCM delivery, and the required secrets.

## Infrastructure and operations

- [Images](images.md) — S3 buckets, CloudFront-signed URLs, BlurHash
  placeholders, metadata stripping, and orphan cleanup.
- [Deploying and restarting services](deployment.md) — systemd units, queue
  vs. eager mode, gunicorn keepalive tuning, and backend log rotation.

Per-client push setup lives next to each client:
[website](../website/PUSH_SETUP.md), [iOS](../ios/PUSH_SETUP.md),
[Android](../android/PUSH_SETUP.md).
