# Good Vibes Only (formerly Positive Only Social) 
[![Android Tests](https://github.com/andrewkatson/pos/actions/workflows/android-tests.yml/badge.svg)](https://github.com/andrewkatson/pos/actions/workflows/android-tests.yml)
[![iOS Tests](https://github.com/andrewkatson/pos/actions/workflows/ios-tests.yml/badge.svg)](https://github.com/andrewkatson/pos/actions/workflows/ios-tests.yml)
[![Backend Tests](https://github.com/andrewkatson/pos/actions/workflows/backend-tests.yml/badge.svg)](https://github.com/andrewkatson/pos/actions/workflows/backend-tests.yml)

## Overview

Social media site that only allows positive or neutral text and image posts. The guidelines are as follows.

1. No swear words
2. No nudity
3. No sexually suggestive content
4. No gore
5. No hate speech
6. No harassment
7. No bullying
8. No misinformation

Neutral content is allowed. Content that starts sad but ends on a happy or hopeful note is also allowed.

These will be updated as time goes on.

## Banning

Users who violate the guidelines can be banned. Every ban is a `UserBan`
record (see `backend/user_system/models.py`) with a type, a reason, an
optional expiry, and the admin who issued it, so there is an audit trail and
a future appeals system can reference the specific ban.

There are two kinds of ban:

- **Outright ban** — the user is told. Login is rejected with an
  `account_banned` error, and any live sessions are terminated the moment the
  ban is applied. Used for clear guideline violations: a temporary outright
  ban (set `expires`) is the standard response to a first or minor offense,
  and a permanent outright ban (no expiry) is for repeat offenders or severe
  violations (hate speech, harassment of a specific person, illegal content).
- **Shadow ban** — the user is *not* told. They can log in, post, and comment
  normally, but their content is invisible to everyone but themselves. Used
  for suspected spam, bots, and bad-faith actors, where telling the user they
  are banned would just help them evade it by making a new account. Shadow
  bans should normally carry an expiry; a permanent shadow ban is reserved
  for confirmed bots.

Whether a ban is temporary or permanent is controlled by the `expires` field
and is independent of the ban type. Escalation for ordinary users follows
the ladder: warning (content hidden by reports) → temporary outright ban →
permanent outright ban.
