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

Your **Followers** and **Following** counts are tappable on your own profile
only: each opens a list of those users, and tapping a name opens that user's
profile. These lists are private — you can only see your own. The endpoints
(`GET /users/followers/`, `GET /users/following/`) take no username and always
return the signed-in user's own lists, so another user's followers/following
can't be requested. On anyone else's profile the counts are shown but are not
tappable.

Tapping another user's name anywhere (a post author, a search result, a comment
author) opens that same profile view for them, with Follow and Block shown.
Tapping **your own** name goes to the Profile tab instead of pushing a separate
copy of the profile screen, so you always land on the same profile, with the
bottom bar and search still in place.

Each user may set a **profile photo**, shown next to their name everywhere it
appears — post authors in the feed and on post details, comment authors, search
results, the follower/following and blocked-user lists, and as a large avatar in
the profile header. A user sets or replaces their own photo from their Profile
tab (see **Profile photos** below); a user with no photo falls back to a neutral
placeholder.

Posts can be acted on directly from any list — the Profile grid, another user's
profile grid, and the Feed — without opening the post first:

- **Like / unlike**, with the current like count. Hidden on your own posts,
  which the backend refuses to let you like.
- **Save / unsave** (issue #193), a personal bookmark. Unlike a like it is
  offered on every post, including your own, since the saved list is a private
  collection rather than a public signal. Saved posts are collected on the
  **Saved Posts** screen, reachable from the Settings tab.
- **Report**, with a reason. A flag marks posts you have an active report on.
- **Retract report**, which shows the reason you originally gave.
- **Delete**, offered only on your own posts.
- **Share**, offered on every post (see [Sharing](#sharing)).

Each feed row additionally shows the author, the caption under the photo, how
long ago the post was made, and a comment count that opens the post when tapped.
The square profile tiles omit these — there is no room for them. A text-only
post already renders its caption as the tile in place of a photo, so the caption
is not repeated beneath it.

The post listing endpoints (`get_posts_in_feed`, `get_posts_for_followed_users`,
`get_posts_for_user`) therefore return `post_likes`, `is_liked`, `is_saved`,
`is_reported`, `report_reason`, `comment_count`, `creation_time` and `audience`
per post,
matching what the post-details endpoint returns. The state is gathered in grouped queries per
batch rather than per post, so a larger batch does not add queries. The comment
count respects the same visibility rule as the thread listing, so a row never
advertises comments the viewer would not be shown.

Deleting a post from a list removes just that row; the list is not reloaded,
which would otherwise reshuffle the weighted feed ordering under the user.
## Hashtags (#tags)

Captions can carry `#hashtags` (issue #379). When a post is created, the
backend parses every `#word` token out of the caption and stores the tags,
normalized to lowercase, in a shared `Tag` table linked to the post
(`backend/user_system/tags.py`, `Post.tags`). Normalization means `#Sunset`,
`#SUNSET` and `#sunset` are the same tag, and a tag row is shared across every
post that uses it. Parsing is forgiving — a caption is free text that already
passed the pre-filter/classifier, so extraction never rejects a post; it just
harvests what it finds. A tag is at most `MAX_TAG_LENGTH` characters and a post
keeps at most `MAX_TAGS_PER_POST` of them.

Every full post payload the API returns — the feed, followed-feed, profile,
saved-posts, tag-feed, and post-details endpoints — carries a `tags` array
(sorted tag names), so clients render the caption's `#tags` as links. (The
appeals/hidden-content listings return a reduced post shape and omit it.) Tapping a tag opens a **tag
feed**: `GET /tags/<tag>/posts/<batch>/` lists the visible posts carrying that
tag, newest first, batched like the other feeds. The tag feed applies exactly
the same visibility and block rules as every other listing endpoint
(`visible_posts` plus the per-viewer block filters), so a hidden, pending,
shadow-banned, or blocked author's post never surfaces there — the tag is only
an extra filter layered on top of the normal visibility query. Tags are
extracted even for a post still pending classification, but that post stays
author-only until it is approved, so its tags cannot leak into anyone else's
tag feed.

The **Saved Posts** screen (`get_saved_posts`) lists the posts you have saved,
most recently saved first. It runs through the same visibility filter as every
other listing, so a post that is hidden or whose author is shadow-banned after
you saved it silently drops off rather than rendering as an empty tile.
Unsaving a post from that screen removes its tile.

## Sharing

Every post's options menu offers **Share**, and every comment's options menu on
the post-detail screen does too (issue #34). Sharing hands off a link to the
item — the website's post page, `https://smiling.social/post/<post_identifier>`,
with a comment additionally carrying a `#comment-<comment_identifier>` fragment.
Share is available on any post or comment, your own and everyone else's; unlike
Like or Delete it has no ownership condition.

Each client uses its native mechanism: iOS presents the system share sheet,
Android fires an `ACTION_SEND` chooser, and the website uses the Web Share API
when the browser offers it (typically mobile), otherwise copying the link to the
clipboard and confirming with a "Link copied" prompt.

This is deliberately the client-only first step. A shared link today opens the
website and, because the single-post view is still behind auth, prompts a
signed-out recipient to log in; on mobile it opens the browser rather than the
app. Making a single post (and comment) publicly viewable with link-preview
metadata, and adding iOS Universal Links / Android App Links so a shared link
opens the app, are tracked follow-ups.

## Text formatting (issue #318)

Authors can style their text. The two surfaces work differently because the
styling means different things:

- **Post captions** carry a **whole-caption font** (`caption_font`) and a
  **whole-tile background color** (`background_color`). Both are single
  curated **keys**, not free-form values: fonts are `default`, `serif`,
  `monospace`, `rounded`, `handwriting`; colors are `default`, `sky`, `mint`,
  `blush`, `lemon`, `lavender`. Each client maps a key to a concrete,
  contrast-checked font/color, so rendering stays consistent and legible across
  web, iOS, and Android. Unknown keys are rejected; `default` reproduces the
  original rendering, so legacy posts and older clients are unaffected. The
  background color only shows on **text-only** posts: on a photo post the image
  fills the tile, so the color has no visible effect. To avoid promising a
  change that never appears, the composer **hides the background-color control
  while a photo is attached** and sends `default` for image posts (issue #421);
  the font, which does style an image post's caption, stays available.
- **Comments** carry **inline** formatting (`body_formatting`): a list of range
  **spans** over the plain comment text, each `{start, end, bold, italic,
  size}`, where `size` is one of `small`/`normal`/`large`/`xlarge` and offsets
  are **UTF-16 code-unit** indices (so JS/Kotlin/Swift index the string
  identically). Spans must stay within bounds, be sorted and non-overlapping,
  carry at least one active style, and number at most 100.

The key invariant: **formatting never changes the text itself.** The caption
and comment body are stored and moderated exactly as before — the AI
classifiers and every input-validation rule run on the untouched plain text,
and the formatting is separate metadata. There is no markup to parse, sanitize,
or classify, and clients render styles by applying attributes to plain-text
spans rather than interpreting embedded markup.

## Post classification (async)

Every new post is checked against the guidelines by an AI classifier — a text
cascade over the caption and, for image posts, a vision cascade over the
image (`backend/user_system/classifiers/`). Classification runs **off the
request path** (issue #282): `make_post` performs no LLM calls, so a slow
provider can never surface as a gateway timeout.

All non-prefilter classifier calls go through **OpenRouter** (issue #393), an
OpenAI-compatible gateway reached with a single `OPENROUTER_API_KEY`. The
cascade consults models in a fixed priority order — a free model first
(`gemma`), then `gemini`, then `openai` (ChatGPT), with Claude only as a last
resort — so clear content is usually settled by the free tier and only
ambiguous content escalates to the paid ones. The cascade decides by the third
usable score, so on the normal path only the first three tiers are consulted;
`claude` is a genuine last resort, reached only when one of the cheaper tiers
returns no usable score (an error or unparseable response). The model behind
each tier is overridable per deploy via `OPENROUTER_MODEL_GEMMA` / `_GEMINI` /
`_OPENAI` / `_CLAUDE` (see
`backend/user_system/classifiers/classifier_utils.py`), so swapping models is a
config change, not a code change.

The flow is:

1. A cheap local **text pre-filter** (`classifiers/prefilter.py`, no LLM) runs
   inline. It matches the caption against a curated slur list (reported as hate
   speech) and the vendored **LDNOOBW** profanity list (issue #393,
   "List of Dirty, Naughty, Obscene and Otherwise Bad Words",
   `classifiers/data/ldnoobw_en.txt`), on whole-word/phrase boundaries. A hit
   is rejected immediately with a final, non-appealable `400` and the post is
   never created (its uploaded image is cleaned up). The list is broad, so it
   errs toward catching blatant obscenity; subtler text is the async cascade's
   job.
2. Otherwise the post is created hidden in a **`pending_classification`**
   state and a job is enqueued; the request returns `201` with
   `status: "pending"`. A pending post is visible only to its author, who
   sees it in their own grid with an "In review" state.
3. A worker (RQ on the same Redis used for rate limiting; run
   `python manage.py classification_worker`) runs the text + image cascades
   and resolves the post exactly once. Image posts first pass a **local image
   pre-filter** (`classifiers/image_prefilter.py`, issue #393): blunt, zero-API
   detectors for the two most objective image violations — nudity (NudeNet) and
   gore (an optional ONNX NSFW/gore model at `LOCAL_GORE_MODEL_PATH`). A
   confident hit is a final rejection, skipping the paid vision cascade
   entirely, exactly like the text pre-filter. These detectors are heavy
   *optional* dependencies (`backend/requirements-local-image-filter.txt`,
   installed on the worker host); when absent or erroring the pre-filter **fails
   open** — it allows the image and defers to the AI cascade, so it can only
   ever add a rejection the cascade might also have made, never fail a post shut
   on infrastructure grounds. The post is then resolved to one of:
   - **visible** (`hidden_reason` cleared) — both cascades passed;
   - **hidden + appealable** (`classifier`) — an appealable rejection, which
     appears on the appeals screens as before;
   - **final rejection** (`classifier_final`) — a terminal, non-appealable
     tombstone: the S3 image is deleted, the row is kept (invisible to
     everyone, its author included) only so clients can reconcile the
     outcome, and the sweep purges it after a few days.
   On either rejection the author is emailed (with the public reason and,
   when appealable, how to appeal) and, best-effort, sent a native push
   notification (see [Push notifications](#push-notifications)). Approval sends
   neither — the post simply appears.
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
`sweep_classifications` management command (scheduled, like
`cleanup_orphan_images`) re-enqueues posts **and pending profile photos** stuck
pending past a threshold (default 15 min, `--stuck-minutes`), alerts (log error)
once an item has exhausted its retry budget, and purges old final-rejection
tombstones (default 7 days, `--tombstone-days`; preview with `--dry-run`).

On the app host these async pieces are provisioned by `backend/tools/setup-django.sh`
as systemd units (see [Deploying and restarting services](#deploying-and-restarting-services)):

- **`classification-worker.service`** — the long-lived RQ worker
  (`manage.py classification_worker`). Installed always but only enabled when
  `REDIS_URL` is set in `.env` (queue mode); in eager mode it is not needed.
- **`sweep-classifications.timer`** — runs `manage.py sweep_classifications`
  every 15 minutes (matching the stuck threshold).
- **`cleanup-orphan-images.timer`** — the daily S3 orphan sweep (see
  [Post image cleanup](#post-image-cleanup)).

Comments are still classified inline in the request (text-only, much smaller
worst case); moving them to the same async flow is a tracked follow-up.

## Push notifications

Because async classification decides a rejection *after* `make_post` has
already returned `201`, the author is told out-of-band. Alongside the rejection
email, the worker fires a **best-effort native push notification** (issues #342
/ #343) so the pop-up reaches the user even with the app closed.

Push is a **nudge, never the source of truth.** Permissions get denied and
tokens go stale, so a user who never receives the push must still see the
correct outcome via in-app reconciliation (the authoritative `GET
posts/<id>/status/` path above). Push and email never carry state; they only
bring the user back to look.

- **Device tokens.** Each client, after the OS grants notification permission,
  uploads its provider token to authenticated `POST /devices/register/`
  (`{platform, token}`, `platform ∈ {ios, android, web}`) and re-uploads on
  rotation. A `DeviceToken` row is keyed by `(platform, token)`, so
  re-registering an existing token repoints it at the current user rather than
  duplicating (a device can change accounts).
- **Send path.** `user_system.push.send_push(user, payload)` fans out to all a
  user's tokens, called by `classify_post` on a resolved rejection — off the
  request path, on the same durable queue, best-effort. The payload's `data`
  map carries the `post_identifier`, a `type` (`post_rejected`), whether it is
  `appealable`, and a `deep_link` (`<FRONTEND_BASE_URL>/post/<id>`) so the client
  can open the rejected post and its appeal UI. **All `data` values are strings**
  — FCM's data map only carries strings, so the shape is identical across
  providers (both APNs and FCM deliver it under a `data` key) and clients parse
  `appealable` as `"true"`/`"false"` rather than a boolean.
- **Providers.** iOS delivers through **APNs** directly (token-based `.p8`
  auth); Android and web both go through **FCM** (web uses FCM-for-web, so it
  registers with `platform: web` and needs no separate Web Push/VAPID path).
- **Dead-token pruning.** When a provider reports a token as gone (`410` /
  `Unregistered` on APNs, `404` / `NOT_FOUND` / `UNREGISTERED` on FCM), the send
  path deletes that `DeviceToken` row so we neither leak rows nor keep paying to
  send to it.

**Secrets** (all optional — an unconfigured provider is a logged no-op, so
local dev, tests, and a not-yet-provisioned deploy send nothing and still import
cleanly; set them like the `EMAIL_*` / `CLOUDFRONT_*` credentials):

- **APNs (iOS):** `APNS_AUTH_KEY` (the `.p8` PEM inline) or `APNS_AUTH_KEY_PATH`
  (a mounted file), plus `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_TOPIC` (the app
  bundle id), and `APNS_USE_SANDBOX=true` for development app builds.
- **FCM (Android + web):** `FCM_CREDENTIALS` (the service-account JSON inline)
  or `FCM_CREDENTIALS_PATH` (a mounted file).

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

## Relationship categories & post audience

Following is not all-or-nothing (issue #392). Every follow relationship carries
a **category** that the follower assigns to the person they follow, and the same
label does double duty: it filters your own feed *and* gates who may see your
posts. The categories, from broadest to closest, are:

- **Following** — the default "people I like" bucket every plain follow starts
  in.
- **Friend**
- **Family**

The category lives on the follow edge (`UserFollow.category`), so you can only
categorize someone you already follow, and unfollowing drops the label with it.
A follow request may set the category up front (`follow_user` accepts an
optional `category`), and an existing relationship is re-categorized with
`POST /users/<username>/category/`. A profile response carries the viewer's
`follow_category` for that user (null when not following).

Each post has an **audience** chosen at creation (`make_post` accepts an
optional `audience`, defaulting to `public` so older clients and pre-existing
posts are unaffected). The audiences are **nested circles**, each a subset of
the one before it:

- **Public** — anyone, even people who do not follow the author.
- **People I follow** (`following`) — everyone the author follows.
- **Friends** (`friends`) — people the author labeled friend *or* family.
- **Family** (`family`) — family only.

So a friends-only post also reaches family, and a family-only post reaches
family alone. The rule is enforced centrally in `visibility.py`
(`visible_posts` / `can_view_post`): a non-public post is shown to a viewer only
when the author has a follow edge to that viewer whose category is close enough
for the post's tier. The author always sees their own posts regardless of
audience, and the audience filter composes with the existing moderation
(hidden / shadow-ban / tombstone) rules and applies everywhere posts are listed
— feeds, profile grids, and post details alike.

Feeds can be **filtered by group**: the followed feed
(`GET /feed/followed/<batch>/`) takes an optional `?category=following|friend|family`
that narrows it to people you labeled with exactly that category (no argument
returns the whole following feed, as before). Feed filtering is an exact-category
match — "show me my family" means just family — while post audience nests, since
sharing with a wider circle should naturally include the closer ones.

## Blocking

Users can block each other from a profile. Blocking is a toggle
(`POST /users/<username>/block/`): blocking severs any follow relationship in
both directions, hides each user's posts from the other's feeds, and stops the
blocked user from finding the blocker in search (the blocker can still search
for the blocked user). Every client has a "Blocked Users" page under Settings,
backed by `GET /users/blocked/`, that lists everyone the signed-in user has
blocked and lets them unblock (the same toggle endpoint).

## Account settings

The Settings screen shows the signed-in account's own **username and registered
email** under a "Contact Information" heading, backed by `GET /me/` (scoped to
`request.user`, so it can only ever return the requester's own address). A
separate "Contact Us" entry lists the support address `katsonsoftware@gmail.com`
for feedback and help (issues #194/#197).

Users can also **change their password** from Settings via
`POST /password/change/` (issue #197). Unlike the reset flow, this requires an
authenticated session *and* the current password — a stolen session alone
cannot lock the real owner out. The new password must satisfy the same strength
policy as registration and must differ from the current one. On success every
*other* session and all remember-me cookies are invalidated (a password change
should evict other devices), while the caller's current session is preserved so
they stay logged in on the device they just used.

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

## Membership numbers

Every account carries a permanent join number — its position in line since
launch — so members can say "I'm #n on the app!" (issue #198). The number is a
`PositiveIntegerField` (`membership_number`), unique and never reused, separate
from the UUID primary key.

Numbers are handed out in join order. New members are stamped at registration
with one past the current highest number; because the field is unique, two
simultaneous signups that race for the same value cause one save to fail and
retry against the now-higher maximum. Assignment never blocks registration —
if it can't get a number after a few attempts the account is still created with
a null number. Accounts that predate the feature were numbered by a one-time
data migration in `creation_time` order (rows with no `creation_time` sort
first), so existing members keep their true join order.

That migration runs only once, so a null left by the rare registration-time
failure is not self-healing. The `backfill_membership_numbers` management
command is the repair path: it numbers any still-null accounts (in the same
join order, safe to re-run, `--dry-run` to preview), so every account ends up
with a permanent number.

Deploy ordering matters for join order: the one-time backfill must finish
before the new registration path serves traffic (the normal migrate-then-release
sequence). If a brand-new signup were numbered `max + 1` while older accounts
were still awaiting their backfilled numbers, it could leapfrog them. Both the
migration and the repair command write with a conditional UPDATE that only
touches rows still null at write time, so an already-assigned number is never
overwritten even if the windows do overlap; running migrate to completion first
is what keeps the ordering itself correct.

The number is public: it's returned on the profile endpoint and shown on every
member's profile, and the registration response includes it so a new member is
greeted with "You're member #n!" right after signing up.

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

## Serving post images

Post images live in two S3 buckets: clients upload the original to the source
bucket (`AWS_STORAGE_BUCKET_NAME`) and a Lambda mirrors a compressed copy to
`AWS_COMPRESSED_STORAGE_BUCKET_NAME` under the same key.

Both buckets are **private** (S3 Block Public Access + an Origin Access Control
bucket policy). Reads happen only through CloudFront, and the backend signs every
image URL it hands to a client, so an image is fetchable only with a valid,
time-limited signature — a bare object URL returns 403 (issues #332, #341).
Uploads are likewise never anonymous: clients PUT via short-lived presigned URLs
minted by `POST /posts/upload-url/` (issue #310), so no client ever holds AWS
credentials for either direction.

Because the two buckets hold the same object key, two CloudFront domains front
them (no URI rewriting needed):

- `CLOUDFRONT_IMAGES_DOMAIN` → distribution → compressed bucket. The serialized
  `image_url` is signed on this domain.
- `CLOUDFRONT_ORIGINALS_DOMAIN` → distribution → source bucket. The serialized
  `original_image_url` (the full-res fallback used while the async-compressed copy
  is still missing, #252/#254) is signed on this domain.

Signing lives in `backend/user_system/cloudfront.py` (`sign_compressed_url` /
`sign_original_url`), invoked from every post-serialization site in `views.py`. A
signed URL carries the object key as its path but **no bucket name**, and stays
valid for `CLOUDFRONT_SIGNED_URL_EXPIRY_SECONDS` (default 24h — comfortably longer
than a session, since clients embed these URLs in payloads they refetch on
mount/refresh, while still bounding a leaked URL). Server-side image access (the
classifier, `delete_image`, the orphan sweeper, `strip_image_metadata`) goes
through credentialed boto3 and is unaffected by the buckets being private.

If the CloudFront settings are unset — local dev, tests, or a not-yet-provisioned
deploy — signing degrades gracefully to the legacy unsigned URLs, so nothing
breaks; the read hole only actually closes once the infra below exists.

**Backend env vars:** `CLOUDFRONT_IMAGES_DOMAIN`, `CLOUDFRONT_ORIGINALS_DOMAIN`,
`CLOUDFRONT_KEY_PAIR_ID`, and the signing private key as either
`CLOUDFRONT_PRIVATE_KEY` (inline PEM) or `CLOUDFRONT_PRIVATE_KEY_PATH` (a mounted
file); optionally `CLOUDFRONT_SIGNED_URL_EXPIRY_SECONDS`.

**One-time AWS setup (not automated):**

1. Two CloudFront distributions with Origin Access Control to the compressed and
   source buckets, each on a custom domain (`images.smiling.social` /
   `originals.smiling.social`)
   with an ACM cert and DNS.
2. Turn on Block Public Access for both buckets and set a bucket policy allowing
   only the two OAC principals (removing any legacy public-read).
3. Create a CloudFront public key + key group (trusted signer) and attach it to
   both distributions; deliver the matching private key to the backend as
   `CLOUDFRONT_PRIVATE_KEY[_PATH]` and its id as `CLOUDFRONT_KEY_PAIR_ID`.

### BlurHash placeholders (issue #387)

Even with the `original_image_url` fallback, a grid tile is blank while its image
downloads — a grey/black square that flashes on every feed load. Each post
therefore carries a **BlurHash**: a ~30-character string
([woltapp/blurhash](https://github.com/woltapp/blurhash)) that encodes a tiny,
blurred version of the image. All three clients decode it locally and render the
blur in the tile *while the real image loads* (and leave it in place if the image
never loads), so a loading photo is a soft blur of itself instead of a flat box.

The BlurHash is stored on the post (`Post.image_blurhash`) and computed
best-effort by the async classification worker (`classify_post`), which already
has the image in hand — it downscales the image and encodes a 4x3 hash. It is
purely decorative: any failure (encode error, missing object, no credentials)
just leaves it null, and the clients fall back to their plain placeholder, so it
can never block a post from being published. It is skipped for final-rejected
posts (their image is deleted) and for text-only posts (which have no image), and
is serialized as `image_blurhash` alongside `image_url` in every listing/detail
payload. Older clients that don't know the field simply ignore it.

## Profile photos

A user's profile photo is stored on the user (`profile_image_url`) and served
next to their name in every list and detail payload as `author_profile_image_url`
with `author_profile_image_original_url` as the full-resolution fallback — the
same CloudFront-signed compressed-plus-original pairing post images use (see
**Serving post images** above), for the same reason (the compressed copy can
briefly lag; #252/#254). Only an **approved** photo is ever shown to anyone else.

Setting a photo reuses the post upload path: the client uploads a re-encoded,
EXIF-stripped JPEG through the presigned-PUT flow (`POST /posts/upload-url/`,
which scopes the key to the uploading user), then calls `POST /profile/photo/`
with the returned URL. Because a profile photo is an image broadcast next to the
user's name across the whole network, it is **moderated exactly like a post
image** and off the request path (issue #282's async pipeline): the upload is
stored on the user as `pending_profile_image_url` with
`profile_image_status = "pending"` and classified by the same image cascade in a
worker (`classify_profile_photo`). On approval it becomes the live
`profile_image_url` and the previously approved photo is cleaned from S3; on
rejection it is dropped (its S3 object deleted) and the owner is told in-app via
`profile_image_status = "rejected"` and `profile_image_reason_code`, so they can
pick a different picture. A previously approved photo stays live and visible
while a new upload is under review, and a rejected upload never replaces it.
Profile photos are **not appealable** — unlike a post, the remedy is simply to
choose another image — so there is no appealable/final split or tombstone. The
owner's own profile-details response carries the pending/rejected state
(`profile_image_status`, `profile_image_reason_code`,
`pending_profile_image_url`); no one else ever sees it. `POST /profile/photo/remove/`
clears the photo entirely.

Reconciliation mirrors posts: `sweep_classifications` re-enqueues a photo stuck
in `pending` past the threshold, or — once its retry budget is spent — leaves it
pending (fail closed, never shown) and alerts an operator exactly once.

## Bios

A user can write a short free-text **bio** shown on their profile (issue #380).
It is stored on the user (`bio`, empty string when unset) and returned in the
profile-details payload (`GET /users/<username>/profile/`) — already moderated
on write, so it is safe to show. It is redacted (returned empty) for a
requester the profile has blocked, exactly like the stats and avatar there, so
a blocked user cannot read the blocker's bio by name. `POST /profile/bio/` with
`{"bio": "..."}` sets it; an empty or whitespace-only value clears it.

Unlike a profile photo, a bio is **plain text**, so it is moderated
**synchronously by the text classifier on write** — exactly like a username or a
comment — rather than through the async image pipeline. There is no
pending/approved lifecycle: a bio that fails the positivity check is rejected
with a `400` (carrying a `reason_code`) and **never stored**, leaving any
existing bio untouched. The remedy is simply to edit it, so a rejection is **not
appealable**. Bios are capped at `MAX_BIO_LENGTH` (500) characters, counted as
unicode code points like captions and comments.

## Post image cleanup

Post images live in two S3 buckets: clients upload the original to the source
bucket (`AWS_STORAGE_BUCKET_NAME`) and a Lambda mirrors a compressed copy to
`AWS_COMPRESSED_STORAGE_BUCKET_NAME` under the same key. Profile photos live in
the same buckets under the same `{user_id}/` prefix and are cleaned up the same
way.

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
  buckets and deletes any object no live `Post` **and no user profile photo**
  references. Both a user's approved `profile_image_url` and any
  `pending_profile_image_url` still under review are treated as live, so the
  sweep never reclaims an avatar out from under a user or deletes an upload
  mid-review. A grace window (default 24h, `--grace-hours`) protects objects too
  new to have become a post yet and the brief window where the Lambda writes a
  compressed copy just after a rejection cleaned up the original. Run it with
  `--dry-run` to preview. It is scheduled as a daily systemd timer on the app
  host (`setup-django.sh`), not in CI, because it needs both the database and
  AWS credentials.

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

## Deploying and restarting services

The Django API runs on an EC2 host provisioned by `backend/tools/setup-django.sh`
(gunicorn behind nginx; the website is a separate S3 + CloudFront SPA published
with `website/deploy-web.sh`). Beyond gunicorn, the backend relies on several
**async background services**, all installed as systemd units by that script:

| Unit | Kind | What it does | Enabled when |
| --- | --- | --- | --- |
| `gunicorn.service` | long-lived | Serves the API (WSGI). | always |
| `classification-worker.service` | long-lived | RQ worker draining the async post/profile-photo moderation queue (`manage.py classification_worker`). | `REDIS_URL` set (queue mode) |
| `sweep-classifications.timer` | timer (15 min) | `manage.py sweep_classifications` — re-enqueues stuck-pending items and purges tombstones. | always |
| `cleanup-orphan-images.timer` | timer (daily) | `manage.py cleanup_orphan_images` — reclaims orphaned S3 images. | always |

**Restart every long-lived process on every deploy.** Both gunicorn *and* the
classification worker cache the imported source in memory, so a `git pull` alone
does not pick up new code. In issue #399 a profile photo was stuck "in review"
forever because the prod worker had been running since **before** the
profile-photo feature was committed and was never restarted after deploy — its
cached `user_system.tasks` lacked `classify_profile_photo`, so every job failed
on import and silently stranded classifications. The generated `~/update-app.sh`
therefore restarts gunicorn **and** the worker and reloads the timers after
migrating and collecting static files; use it (or replicate its steps) for every
by-hand deploy. (The timers run oneshot services that re-exec the new code on
their next fire, so they self-heal, but the units are reloaded in case their
definitions changed.)

**Queue vs eager mode.** `REDIS_URL` (set via `--redis-url`, written to
`backend/.env`) flips the app from eager in-process classification to queue mode.
Only in queue mode is a worker needed, so `setup-django.sh` installs
`classification-worker.service` unconditionally but only **enables** it when
`REDIS_URL` is present. To switch an existing eager host to queue mode: add
`REDIS_URL` to `.env`, restart gunicorn, then
`sudo systemctl enable --now classification-worker`.

**`.env` and systemd.** `manage.py` loads `.env` via `python-dotenv`, but
`wsgi.py` does not — so every systemd unit points at the `.env` with
`EnvironmentFile=$BACKEND_DIR/.env` (i.e. `backend/.env`, the same file
`setup-django.sh` generates), or the service would start without
`REDIS_URL`/DB/AWS credentials.

`backend/tools/status_check.sh` reports the health of all of the above — gunicorn,
nginx, the classification worker (active/enabled, or "stranding!" if enabled but
dead), the two timers (last/next run), and best-effort `classification` queue
depth — so a silently dead worker is visible at a glance.
