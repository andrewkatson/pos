# Accounts

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

**Usernames** are 10–150 word characters (Unicode letters, digits and
underscores; length counted in code points) — `Patterns.username`, mirrored by
the registration hints on every client. The 150 ceiling is the username
column's `max_length`, so a longer name is refused as an ordinary validation
error (`Invalid fields ['USERNAME']`, 400) rather than failing at the database.
A username is fixed once chosen: it is set at registration (or generated on a
first Google sign-in, see [Signing in with Google](authentication.md#signing-in-with-google)) and there is no rename endpoint. Session and
remember-me tokens are validated by the separate `Patterns.alphanumeric`, which
is not a username rule.

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
