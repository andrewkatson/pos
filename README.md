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
  `account_banned` error, any live sessions are terminated the moment the
  ban is applied, and the user is emailed that their account has been
  suspended (with the reason and, for a temporary ban, when it lifts). Used
  for clear guideline violations: a temporary outright ban (set `expires`) is
  the standard response to a first or minor offense, and a permanent outright
  ban (no expiry) is for repeat offenders or severe violations (hate speech,
  harassment of a specific person, illegal content).
- **Shadow ban** — the user is *not* told. They can log in, post, and comment
  normally, but their content is invisible to everyone but themselves. Used
  for suspected spam, bots, and bad-faith actors, where telling the user they
  are banned would just help them evade it by making a new account. Shadow
  bans should normally carry an expiry; a permanent shadow ban is reserved
  for confirmed bots.

Whether a ban is temporary or permanent is controlled by the `expires` field
and is independent of the ban type. A temporary ban lifts itself once
`expires` passes — `UserBan.objects.active()` filters it out, so no scheduled
job is needed. Escalation for ordinary users follows the ladder: warning
(content hidden by reports) → temporary outright ban → permanent outright ban.

## New-device login emails

When a user logs in from a device we have not seen before, they get an email
alerting them to the login. A "device" is identified by its IP address: the
first time a user authenticates from a given IP, a `KnownDevice` record (see
`backend/user_system/models.py`) is created for that user/IP pair and the email
is sent. Subsequent logins from the same IP are silent.

The IP recorded at registration is treated as already-known, so a user's first
real login from the device they signed up on is not flagged. Both the
password login and the remember-me login paths perform the check. Sending the
email is best-effort — a mail failure is logged but never blocks the login.

## Post image cleanup

Post images live in two S3 buckets: clients upload the original to the source
bucket (`AWS_STORAGE_BUCKET_NAME`) and a Lambda mirrors a compressed copy to
`AWS_COMPRESSED_STORAGE_BUCKET_NAME` under the same key. Because the upload
happens before the backend ever sees the post, images can be left behind:
when a post is rejected outright by the classifier, deleted, or its appeal is
denied. Cleanup happens at two levels (see `backend/user_system/s3.py`):

- **Inline** — `delete_image` removes the key from both buckets the moment a
  post is outright-rejected or deleted. It is best-effort: failures are logged
  and never block the request.
- **Sweeper** — the `cleanup_orphan_images` management command lists both
  buckets and deletes any object no live `Post` references. A grace window
  (default 24h, `--grace-hours`) protects objects too new to have become a post
  yet and the brief window where the Lambda writes a compressed copy just after
  a rejection cleaned up the original. Run it with `--dry-run` to preview. It is
  scheduled as a daily systemd timer on the app host (`setup-django.sh`), not in
  CI, because it needs both the database and AWS credentials.

The backend's IAM credentials need `s3:DeleteObject` on both buckets for either
path to take effect.
