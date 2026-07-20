# Good Vibes Only (formerly Positive Only Social) 
[![Android Tests](https://github.com/andrewkatson/pos/actions/workflows/android-tests.yml/badge.svg)](https://github.com/andrewkatson/pos/actions/workflows/android-tests.yml)
[![iOS Tests](https://github.com/andrewkatson/pos/actions/workflows/ios-tests.yml/badge.svg)](https://github.com/andrewkatson/pos/actions/workflows/ios-tests.yml)
[![Backend Tests](https://github.com/andrewkatson/pos/actions/workflows/backend-tests.yml/badge.svg)](https://github.com/andrewkatson/pos/actions/workflows/backend-tests.yml)
[![Website Tests](https://github.com/andrewkatson/pos/actions/workflows/website-tests.yml/badge.svg)](https://github.com/andrewkatson/pos/actions/workflows/website-tests.yml)

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

## Email verification

Registering does not prove you own the email address you signed up with, so
every new account starts unverified and must click a verification link before
it can be used. This stops someone from creating an account with another
person's email address (issue #237).

At registration a random token is generated (`secrets.token_urlsafe`, stored
only as a SHA-256 hash with a 24-hour expiry, like the password-reset flow)
and the welcome email carries a link to
`https://smiling.social/verify-email?token=...` (base URL configurable via
`FRONTEND_BASE_URL`). The website page POSTs the token to `verify-email/`,
which marks the account verified and clears the token. Sending the email is
best-effort and never blocks registration; `resend-verification-email/`
(rate-limited) issues a fresh token, invalidating the old one.

Until the address is verified, the account is rejected with an
`email_not_verified` error at every entry point: password login, remember-me
login, and every authenticated endpoint (the session issued at registration
is therefore unusable until verification). Accounts created before this
feature existed are grandfathered in as verified by the migration.

## Two-factor authentication (TOTP)

Users can opt in to two-factor authentication with a standard authenticator
app (Google Authenticator, 1Password, etc.) using time-based one-time
passwords (issue #348). SMS is deliberately not offered.

**Enrollment** is a two-step handshake from an authenticated session:
`2fa/totp/setup/` generates a secret and returns it with an `otpauth://`
provisioning URI (rendered as a QR code by clients); nothing is enforced yet.
`2fa/totp/confirm/` takes one code from the authenticator to prove it was
added correctly, enables 2FA, and returns ten single-use recovery codes —
shown exactly once and stored with Django's salted password hasher (so a
database leak can't be brute-forced offline). Re-running setup before
confirming just replaces the pending secret.

**Login** becomes two steps for enrolled accounts. `login/` still checks the
password (and ban/email-verification gates) but returns
`two_factor_required: true` with a short-lived challenge token (5 minutes,
stored hashed) instead of a session. `login/2fa/` exchanges that challenge
plus a TOTP code — or a recovery code — for the real session, and ends in
exactly the same state as a plain login (session token, optional remember-me
cookie, new-device email). A challenge is invalidated after 5 failed code
attempts. Codes are accepted with one 30-second step of clock drift either
way, and an accepted code cannot be replayed within its validity window.
Accounts without 2FA get the original single-step response, so older clients
keep working for them.

**Trusted devices**: the remember-me login (`login/remember/`) never asks for
a code — possession of a valid login cookie counts as the second factor.

**Disabling** (`2fa/disable/`) requires the account password *plus* a current
TOTP or unused recovery code, so a stolen logged-in session alone cannot
strip the protection. Losing the authenticator is what recovery codes are
for; a user who loses both is locked out and must contact support.

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
path to take effect, plus `s3:ListBucket` on both buckets for the sweeper to
enumerate them (without it `cleanup_orphan_images` fails with AccessDenied).

## Appeals

A user can appeal moderation actions. Each appeal is an `Appeal` record (see
`backend/user_system/models.py`) that targets exactly one of a hidden post, a
hidden comment, or a ban, and carries the user's reason plus an admin
resolution trail.

- **Content appeals** (hidden posts and comments) are filed in-app. A signed-in
  user can list their own hidden posts/comments and their existing appeals, and
  submit an appeal, via the `appeals/...` endpoints. Both classifier-hidden and
  report-hidden content is appealable. An item can be appealed only once.
- **Ban appeals** go through the email-reply flow described in the suspension
  email, not an in-app endpoint: an outright-banned user has no active session
  and cannot log in, so they cannot reach an authenticated endpoint. Admins can
  record such an appeal against the ban for the audit trail.

Admins review appeals and either approve them — reversing the moderation action
(un-hiding the content) — or deny them.
