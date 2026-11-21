# Accounts

## Account settings

The Settings screen shows the signed-in account's own **username and registered
email** under a "Contact Information" heading, backed by `GET /me/` (scoped to
`request.user`, so it can only ever return the requester's own address). A
separate "Contact Us" entry lists the support address `katsonsoftware@gmail.com`
for feedback and help (issues #194/#197).

A "Privacy" section holds the **Private Account** switch and the **Follow
Requests** list (issue #96); see
[private accounts](audience-and-relationships.md#private-accounts-issue-96).

Users can also **change their password** from Settings via
`POST /password/change/` (issue #197). Unlike the reset flow, this requires an
authenticated session *and* the current password — a stolen session alone
cannot lock the real owner out. The new password must satisfy the same strength
policy as registration and must differ from the current one. On success every
*other* session and all remember-me cookies are invalidated (a password change
should evict other devices), while the caller's current session is preserved so
they stay logged in on the device they just used.

**Usernames** are 10–150 word characters (Unicode letters, digits and
underscores; length counted in code points) — `Patterns.username`, mirrored by
the registration hints on every client. The 150 ceiling is the username
column's `max_length`, so a longer name is refused as an ordinary validation
error (`Invalid fields ['USERNAME']`, 400) rather than failing at the database.
A username is set at registration (or generated on a first Google sign-in, see
[Signing in with Google](authentication.md#signing-in-with-google)) and can be
changed later from Settings — see [Changing the username](#changing-the-username-issue-594).
Session and remember-me tokens are validated by the separate
`Patterns.alphanumeric`, which is not a username rule.

## Changing the username (issue #594)

Settings → Contact Information shows the username with a **Change** action,
backed by `POST /me/username/` with `{"username": "<new name>"}`. The username
and the email are changed separately: the username is a public handle, so its
risks are moderation, links and impersonation, while the email is a private
credential that must be proven before it takes effect (see
[Changing the email](#changing-the-email-issue-594)).

**Checks.** The new name goes through exactly what a registration name does:
`Patterns.username`, nobody else holding it, and the positivity classifier. A
classifier rejection is not appealable — pick another name. A name equal to the
current one is refused. No password is asked for: a username is not a
credential, and the cooldown caps what a stolen session could do with it.

**Cooldown.** An account may rename once every `USERNAME_CHANGE_COOLDOWN_DAYS`
(30), tracked in `username_changed_time`, so renaming can't be used to churn
names to shake off reports and blocks or to cycle impersonation names. A rename
inside the window answers `username_change_too_soon` with
`next_username_change_time`, and `GET /me/` reports the same field (null when a
rename is allowed now) so clients disable the row and say when it reopens.
`GET /me/` and the rename response also carry `former_username_held_until`
(see below).

**The old name is held.** The name given up becomes a `UsernameHold` for
`USERNAME_HOLD_DAYS` (30). During the hold:

- nobody else can register it, rename to it, or be generated it on a first
  Google sign-in — refused as `username_taken`, like a name in use;
- every `users/<username>/…` route (profile, posts, follow, block, report,
  follow requests) and the public profile routes still resolve it to the
  account, through `get_user_by_handle`, so share links, push notifications
  already delivered and other devices' cached names keep working;
- the former owner can take it back (subject to the cooldown), which just ends
  the hold.

Registration, a first Google sign-in and a rename each re-check the hold
*after* writing the name, in the same transaction. A write that collided with a
rename on the username's unique index only proceeds once that rename — and the
hold it creates in the same commit — is visible, so a check made only beforehand
could hand the reserved name to someone else.

Sign-in, registration and password reset match the *current* username only: an
old name is a pointer to the account, not a credential for it. A hold past its
expiry is ignored everywhere, and expired rows are swept on the next rename. A
current username always wins over a hold, so a name freed after its hold
belongs to whoever takes it next.

Every relation (posts, comments, follows, blocks, reports, appeals, sessions)
points at the user's UUID, so a rename rewrites nothing else. It does change the
profile under [account report review](reporting.md#reporting-an-account-issue-602),
so it releases a decided review exactly like a new bio does
(`moderation.profile_content_changed`).

**Clients.** Each client caches the signed-in username for "is this me?"
checks (website `localStorage`/`sessionStorage`, iOS and Android the keychain
session). The device that renames updates its cache from the response and
tells views that already read it: the website through `useCurrentUsername`
(an event-backed hook its ownership checks use), iOS through the
`.usernameChanged` notification, Android through `SessionEvents`, which the
view models kept alive across tabs listen to. The website also refreshes the
cache from `GET /me/` on startup and when Settings opens, so a rename made on
another device catches up, and a view that rendered with the old name updates
when the refresh lands (a startup response is dropped if the session or the
cached name changed while it was in flight).

Rows already on screen — and loads that started before the rename — still
carry the old author name. Rather than refetch, each client remembers the names
the account gave up during the session and counts them as the user's own for
"is this mine?" checks (website `useOwnUsernames`, iOS
`PostActionsViewModel.isOwnUsername`, Android `PostListActions.isOwnPost`).
That is safe only while the name is held for its former owner, so the rename
response and `GET /me/` report `former_username_held_until` — when the hold on
the name given up at the last rename ends (null when there is none) — and
clients remember a former name only with a hold still running and stop
counting it once that passes. A refresh that finds the hold already over
remembers nothing. The website derives comment ownership at render time from
these names rather than storing it per comment, so a refresh that lands after
the comments loaded is reflected at once. The website's `/profile/<old name>` page replaces itself
with the current name once the profile loads; the native clients rely on the
backend resolving the old name.

## Changing the email (issue #594)

Settings → Contact Information shows the email with a **Change** action. The
change is a request that only takes effect once the new address is proven:

1. `POST /me/email/` with the new `email` plus proof that the owner is asking:
   the account `password`, or — for a Google-only account, which has no
   password (`GET /me/` reports `has_password: false`) — a fresh Google
   `id_token` whose `sub` is the Google account already linked to it. A stolen
   session alone can't redirect where password resets go, the same reasoning
   as changing the password. A failure answers `reauthentication_required`.
   The proof is judged against the user row as locked for the write, not the
   copy loaded at authentication, and the request's session must still exist
   then: a password changed or reset mid-request (which also revokes sessions)
   stops it.
2. The address must differ from the current one and must not be held by any
   other account, both compared **case-insensitively** (`email_in_use`
   otherwise). Registration only rejects exact matches, but addresses differing
   in case are one mailbox, and two accounts sharing one is what makes Google
   sign-in refuse with `google_email_ambiguous`, so a change never creates that.
3. The new address is stored as `pending_email` with a token (SHA-256 hash
   only, `EMAIL_CHANGE_TOKEN_HOURS` = 24h) and mailed a link to
   `https://smiling.social/verify-email-change?token=...`. The current address
   keeps working for login, password reset and every notice until then, and the
   account stays verified throughout. Requesting again replaces the pending
   address and invalidates the old link; `POST /me/email/cancel/` withdraws it.
   `GET /me/` reports `pending_email` so Settings can show it with a cancel
   action.
4. The website page POSTs the token to `verify-email-change/`, which needs no
   session (the link may be opened on any device, so the page is in
   `PUBLIC_PATHS`: a dead session in that browser is cleared without bouncing
   to `/login`). Under a lock on the address — the same one registration and a
   first Google sign-in take, a Postgres advisory lock on the lowercased
   address, since no database constraint makes emails unique — it re-checks
   that no other account took the address meanwhile (clearing the request with
   `email_in_use` if one did), swaps it in, marks the account verified, and
   voids both stages of any outstanding password reset (the emailed code and
   the reset token), since they went to the old address. The **old address is then emailed** that the change happened, so an
   owner whose account was taken over hears about it where they still read
   mail.

A password change or password reset clears any pending email change: it was
authorized by the old credentials, and a reset is account recovery, so a change
someone else requested before it must not be completable after. Issuing a
password-reset code locks and re-reads the account (the lock confirmation
takes), so a reset in flight can't store a code for the old mailbox after a
confirmation voided reset codes. Linking a Google identity to an account found
by its email does the same and refuses to link if the account no longer holds
that address — the sign-in then proceeds as if nothing matched.

Other sessions are not signed out by an email change. Google sign-in keeps
working because it finds the account by `google_sub`, not by email. Password
reset matches on username plus email, so it simply uses the new values.
Authenticator apps keep the old address as the account's label (the TOTP
provisioning URI is built from the email at enrollment), which is cosmetic.

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

## Account & data deletion

Every client can **delete the account** from the Settings tab (a confirmation
dialog, then `POST /user/delete/`), which cascades to the user's posts (and
their S3 images), comments, likes, saved posts, follows, blocks, appeals,
sessions, and remembered devices.

Google Play additionally requires a **stable, publicly reachable web URL** where
a user can request account and data deletion without going through the app, so
the website serves a standalone page at `https://smiling.social/delete-account`
(issue #439). It is reachable without an existing session — linked from the
landing-page footer and the public privacy-policy page — and walks the visitor
through three steps: sign in (username/email + password, plus the two-factor
step for enrolled accounts, so no one else can delete an account that isn't
theirs), an explicit acknowledgement of what will be removed, and the permanent
delete. It reuses the same `POST /user/delete/` endpoint, so the deleted data is
exactly the cascade above; on success the local session is cleared and a
confirmation is shown. A session already restored on page load skips straight to
the confirmation step.

## Terms of service (issue #493)

The website serves the terms at `https://smiling.social/terms-of-service`, a
public page needing no session, next to the privacy policy it mirrors. Google's
OAuth consent screen requires a terms URL that is reachable from the app's home
page before it will verify the app, and both app stores ask for the same, so the
**landing-page footer links to it** alongside "Privacy Policy" and "Delete
Account", and the two legal pages cross-link to each other.

The text lives in `website/src/termsOfService.ts` as an ordered list of
`{heading, body}` sections — one source shared by the public page and the
Settings → "Terms of Service" modal, so the signed-out and signed-in copies
cannot drift (the privacy policy does the same with `website/src/privacyPolicy.ts`).
Both unauthenticated pages share `website/src/pages/LegalPage.css`.

**Every client carries the terms, not just the website.** OAuth needs only the
one URL above — the consent screen is configured per Google Cloud project, and
all three clients authenticate against it — but Apple's UGC rules expect the
terms to be agreed to and readable inside the app, so iOS and Android each ship
their own copy the way they already ship the privacy policy:

| Surface | Text | Where it is shown |
| --- | --- | --- |
| Website | `website/src/termsOfService.ts` | `/terms-of-service` page, Settings modal |
| iOS | `GVOAppConstants.termsOfServiceSections` | `TermsOfServiceView` sheet, from Settings and Register |
| Android | `Constants.TERMS_OF_SERVICE_SECTIONS` | `TermsOfServiceDialog`, from Settings and Register |

The section list is duplicated per client, exactly as `privacyPolicyText` /
`PRIVACY_POLICY_TEXT` already are — there is no endpoint serving policy text —
so a wording change has to be made in all three places. The privacy policy is a
single paragraph and fits an alert; the terms run to ten sections, so on both
mobile clients they get a scrollable sheet/dialog rather than an alert.

On mobile, registering is the acceptance: the register screen carries the same
"By creating an account you agree to our Terms of Service" line the website
does, with the terms one tap away, since a signed-out user cannot reach
Settings. The privacy policy stays the confirmation dialog that Register already
puts up on both clients.

What the terms cover follows the behavior documented elsewhere in these docs:
the 16+ [age floor and the adult/minor split](age-and-identity.md), the
[content guidelines](../README.md#content-guidelines), [automated moderation](post-classification.md),
[bans and shadow bans](bans-and-appeals.md#banning), [appeals](bans-and-appeals.md#appeals), what
[Google sign-in](authentication.md#signing-in-with-google) shares, and what
[account deletion](#account--data-deletion) removes. Changing any of that
behavior means updating the terms text with it. The website's register page
carries a
"By creating an account you agree to our Terms of Service and Privacy Policy"
line covering both the form and the Google button; its links open in a new tab
so reading them cannot discard a half-filled form or a Google credential still
waiting on the privacy-policy confirmation.

## Support page

Apple requires a **Support URL** on every App Store listing, so the website
serves a public support page at `https://smiling.social/support`. Like the
legal pages it needs no session — which is the point: the people most likely to
open it are a suspended user who cannot log in and a shopper who has not
installed anything yet. The landing-page footer links to it alongside "Privacy
Policy", "Terms of Service" and "Delete Account".

The page leads with the support address `katsonsoftware@gmail.com` as a
`mailto:` link, then covers what to include in a message, how to
[report a post or comment](reporting.md), how to
[appeal hidden content](bans-and-appeals.md#appeals) in-app, how a
[suspended user appeals by email](bans-and-appeals.md#appeals), and where to go
for [account and data deletion](#account--data-deletion).

The copy has to match what the system actually does, because the people reading
it are already in trouble. On [reporting](reporting.md) it says that the first
report triggers an automated re-review that never sees the report count or the
reasons, that content which clears it and keeps being reported escalates to a
moderator, and that a moderator's dismissal is the end of it. It says that
content still being classified and
outright classifier rejections are *not* appealable, that an appeal is one per
item, and that a denied appeal **deletes a post** and leaves a comment hidden —
all as [appeals](bans-and-appeals.md#appeals) implements it. For deletion it
says the page signs you in first and that the sign-in is refused for suspended
or unverified accounts, pointing those users at the support address instead of
at a page that cannot help them.

**A dead session must not redirect these pages away.** Startup does
authenticated work (remember-me rotation, push registration), and a stored
session belonging to a suspended or unverified account fails it with
`account_banned` / `email_not_verified`, whose handlers send the tab to
`/login`. That would eject precisely the visitors the support page is for, so
`website/src/publicPaths.ts` lists `/support`, `/privacy-policy` and
`/terms-of-service`: on those paths `installAuthFailureHandlers`
(`website/src/api/authFailureRedirects.ts`) clears the dead session but stays
put. `/delete-account` is deliberately excluded — it signs the visitor in
itself and reports those same errors in its own form.

Only the redirect is suppressed. The startup work still runs on these pages,
because push registration is the one thing that subscribes a tab to foreground
messages and nothing re-runs it on the client-side navigation that takes a
signed-in reader from the support page into the app — skipping it there would
leave that tab's notifications silently dead for the rest of the session.

The address and the section list live in `website/src/support.ts` as
`SUPPORT_EMAIL` and an ordered list of `{heading, body}` sections — the same
one-source-shared pattern `termsOfService.ts` uses — so the public page and the
Settings → "Contact Us" row cannot name different addresses. The page shares
`website/src/pages/LegalPage.css` with the privacy policy and the terms.

Apple's other listing URLs map to pages that already exist: the **Privacy
Policy URL** (also required) is `/privacy-policy`, and the optional
**Marketing URL** is the landing page, `https://smiling.social`.
