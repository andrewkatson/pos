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

## Navigation and post actions

Every client (website, iOS, Android) shows the same four-item bottom bar:
**Profile**, **Feed**, **Post**, and **Settings**.

The Profile tab is the signed-in user's own profile — their Posts / Followers /
Following counts above their post grid — so it is always one tap away. It also
hosts the user-search bar; while a search is active the results list replaces
the profile body. Follow and Block are hidden on your own profile, since
neither applies to yourself.

Tapping another user's name anywhere (a post author, a search result, a comment
author) opens that same profile view for them, with Follow and Block shown.
Tapping **your own** name goes to the Profile tab instead of pushing a separate
copy of the profile screen, so you always land on the same profile, with the
bottom bar and search still in place.

Posts can be acted on directly from any list — the Profile grid, another user's
profile grid, and the Feed — without opening the post first:

- **Like / unlike**, with the current like count. Hidden on your own posts,
  which the backend refuses to let you like.
- **Report**, with a reason. A flag marks posts you have an active report on.
- **Retract report**, which shows the reason you originally gave.
- **Delete**, offered only on your own posts.

Each feed row additionally shows the author, how long ago the post was made, and
a comment count that opens the post when tapped. The square profile tiles omit
those two — there is no room for them.

The post listing endpoints (`get_posts_in_feed`, `get_posts_for_followed_users`,
`get_posts_for_user`) therefore return `post_likes`, `is_liked`, `is_reported`,
`report_reason`, `comment_count` and `creation_time` per post, matching what the
post-details endpoint returns. The state is gathered in grouped queries per
batch rather than per post, so a larger batch does not add queries. The comment
count respects the same visibility rule as the thread listing, so a row never
advertises comments the viewer would not be shown.

Deleting a post from a list removes just that row; the list is not reloaded,
which would otherwise reshuffle the weighted feed ordering under the user.
## Post classification (async)

Every new post is checked against the guidelines by an AI classifier — a text
cascade over the caption and, for image posts, a vision cascade over the
image (`backend/user_system/classifiers/`). Classification runs **off the
request path** (issue #282): `make_post` performs no LLM calls, so a slow
provider can never surface as a gateway timeout.

The flow is:

1. A cheap local **pre-filter** (`classifiers/prefilter.py`, no LLM) runs
   inline. A blatant hit (unambiguous profanity or slurs) is rejected
   immediately with a final, non-appealable `400` and the post is never
   created (its uploaded image is cleaned up).
2. Otherwise the post is created hidden in a **`pending_classification`**
   state and a job is enqueued; the request returns `201` with
   `status: "pending"`. A pending post is visible only to its author, who
   sees it in their own grid with an "In review" state.
3. A worker (RQ on the same Redis used for rate limiting; run
   `python manage.py classification_worker`) runs the text + image cascades
   and resolves the post exactly once to one of:
   - **visible** (`hidden_reason` cleared) — both cascades passed;
   - **hidden + appealable** (`classifier`) — an appealable rejection, which
     appears on the appeals screens as before;
   - **final rejection** (`classifier_final`) — a terminal, non-appealable
     tombstone: the S3 image is deleted, the row is kept (invisible to
     everyone, its author included) only so clients can reconcile the
     outcome, and the sweep purges it after a few days.
   On either rejection the author is emailed (with the public reason and,
   when appealable, how to appeal). Approval sends no email — the post simply
   appears.
4. Provider failures (no usable score from any AI, unreachable S3) are not
   verdicts: the job retries with backoff and, if retries are exhausted, the
   post **fails closed** — it stays hidden-pending rather than ever publishing
   unclassified content or falsely rejecting the author.

Clients reconcile the outcome via the author-only
`GET posts/<id>/status/` endpoint: after a pending create they poll it a
bounded handful of times (no standing timers), and the normal
load-on-mount/pull-to-refresh picks up the state after that. Author-facing
post payloads carry `status` / `reason_code` / `appealable` for the author's
own posts only.

Without `REDIS_URL` (local dev, tests, CI) there is no queue, so the job runs
eagerly in-process; production must set `REDIS_URL` and run the worker. The
`sweep_classifications` management command (cron, like
`cleanup_orphan_images`) re-enqueues posts stuck pending past a threshold,
alerts (log error) once a post has exhausted its retry budget, and purges old
final-rejection tombstones (default 7 days, `--tombstone-days`; preview with
`--dry-run`).

Comments are still classified inline in the request (text-only, much smaller
worst case); moving them to the same async flow is a tracked follow-up.

## Age and identity

The service is closed to under-16s, and adults and permitted minors are kept
apart. Age comes from a date of birth supplied at registration or later via
identity verification (`verify_identity`); the model keeps two derived flags
rather than the raw date — `identity_is_verified` (an age was given) and
`is_adult` (that age was 18 or older). The age thresholds live in
`backend/user_system/constants.py` (`MINIMUM_AGE = 16`, `ADULT_AGE = 18`).

Three rules follow from this:

1. **No under-16s (issue #337).** Registration and `verify_identity` refuse
   anyone who supplies a date of birth showing an age below `MINIMUM_AGE`:
   register returns `403` with `reason_code: "age_restricted"` and creates no
   account; `verify_identity` returns the same and leaves the account
   unverified. Because under-16s are turned away here, any account that *is*
   identity-verified but not an adult is necessarily 16 or 17 — a "permitted
   minor". A date of birth is still optional at registration; an account
   created without one is simply left unverified (and treated as an adult for
   the segregation below, since its age is unknown).

2. **Adults and minors are mutually invisible (issue #329).** Permitted minors
   (16-17) form one visibility band and everyone else — adults plus
   unverified accounts — forms the other. The two bands never see each other's
   posts, comments, profiles, or search results, and cannot follow across the
   divide. This is enforced centrally in
   `backend/user_system/visibility.py` (`is_minor` / `in_same_age_band` and the
   `visible_posts` / `visible_comments` / `searchable_users` / `can_view_post`
   helpers), so every content path inherits it; cross-band profile and follow
   attempts return the same "not found" / "does not exist" response as a
   genuinely missing user so neither side can confirm the other by name. An
   account always sees its own content.

3. **No photos of babies or children (issue #336).** Even a permitted adult may
   not post images of minors. This is content rule 9
   (`backend/user_system/classifiers/classifier_constants.py`): the image
   classifier rejects photos or images of babies, children, or anyone under 18,
   reported to the author with `reason_code: "minors"`.

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

## Blocking

Users can block each other from a profile. Blocking is a toggle
(`POST /users/<username>/block/`): blocking severs any follow relationship in
both directions, hides each user's posts from the other's feeds, and stops the
blocked user from finding the blocker in search (the blocker can still search
for the blocked user). Every client has a "Blocked Users" page under Settings,
backed by `GET /users/blocked/`, that lists everyone the signed-in user has
blocked and lets them unblock (the same toggle endpoint).

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
`2fa/totp/confirm/` takes the account password plus one code from the
authenticator to prove it was added correctly, enables 2FA, and returns ten
single-use recovery codes — shown exactly once and stored with Django's salted
password hasher (so a database leak can't be brute-forced offline). Re-running
setup before confirming just replaces the pending secret.

The password on confirm is what stops a stolen session from being upgraded into
a permanent takeover: without it a thief could bind their own authenticator,
read the one-time recovery codes off the response, and lock the real owner out
for good, since turning 2FA back off then requires a code only the thief holds.

**Login** becomes two steps for enrolled accounts. `login/` still checks the
password (and ban/email-verification gates) but returns
`two_factor_required: true` with a short-lived challenge token (5 minutes,
stored hashed) instead of a session. `login/2fa/` exchanges that challenge
plus a TOTP code — or a recovery code — for the real session, and ends in
exactly the same state as a plain login (session token, optional remember-me
cookie, new-device email). A challenge is invalidated after 5 failed code
attempts. Codes are accepted with one 30-second step of clock drift either
way, and an accepted code cannot be replayed within its validity window.
Recovery codes are issued as lowercase hex but accepted in any case and with
stray surrounding whitespace, since they get typed by hand.
Accounts without 2FA get the original single-step response, so older clients
keep working for them.

**Trusted devices**: the remember-me login (`login/remember/`) never asks for
a code — possession of a valid login cookie counts as the second factor.

**Abandoned challenges**: issuing a challenge clears any earlier one for that
user, so only one is ever live. A login that is started and never finished
still leaves a row until that user logs in again (forever, for someone who
never returns), so the `cleanup_expired_two_factor_challenges` management
command sweeps expired rows and is safe to run on a schedule.

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
`AWS_COMPRESSED_STORAGE_BUCKET_NAME` under the same key.

Every client strips image metadata before uploading. Each uploader (web
`s3Uploader.ts`, iOS `AWSManager.swift`, Android `ImageUploader.kt`) always
decodes the picked photo and re-encodes it as a fresh JPEG rather than sending
the original file, so no EXIF — most importantly the camera's GPS coordinates —
ever reaches the source bucket. Any orientation is baked into the pixels first
so the picture still displays upright. The compression Lambda likewise re-saves
without EXIF, so the compressed bucket is metadata-free too.

Images uploaded before clients stripped metadata can be cleaned in place with
the `strip_image_metadata` management command. It sweeps both buckets and
rewrites, losslessly (pixel data is copied verbatim, never re-encoded), any
JPEG that carries metadata: EXIF/XMP, IPTC, comments, and post-EOI trailers
are dropped, keeping only the EXIF Orientation tag so old photos — whose
pixels were never rotated upright by a client — still display correctly.
Already-clean objects are left untouched, so re-running it is cheap and safe.
Use `--dry-run` to preview. It needs the backend's AWS credentials with
`s3:ListBucket`, `s3:GetObject`, and `s3:PutObject` on both buckets, and
rewriting a source-bucket object re-triggers the compression Lambda (harmless
— it just refreshes the compressed copy).

Because the upload
happens before the backend ever sees the post, images can be left behind:
when a post is rejected outright by the classifier, deleted, or its appeal is
denied. Cleanup happens at two levels (see `backend/user_system/s3.py`):

- **Inline** — `delete_image` removes the key from both buckets the moment a
  post is deleted, fails the pre-filter, or is finally rejected by the
  classification worker. It is best-effort: failures are logged and never
  block the request (or the worker).
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
  Posts still pending classification (nothing has been decided yet) and
  final classifier rejections (terminal by definition) are not appealable and
  never appear on the appeals screens.
- **Ban appeals** go through the email-reply flow described in the suspension
  email, not an in-app endpoint: an outright-banned user has no active session
  and cannot log in, so they cannot reach an authenticated endpoint. Admins can
  record such an appeal against the ban for the audit trail.

Admins review appeals and either approve them — reversing the moderation action
(un-hiding the content) — or deny them.
