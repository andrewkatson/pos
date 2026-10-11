# Authentication

## Signing in with Google

Anyone can sign in — and sign up — with a Google account instead of a username
and password (issue #10). Every client obtains a **Google ID token** natively
and posts it to `login/google/`, which verifies it and hands back exactly the
same session a password login would: same fields, same remember-me cookie, same
new-device email. Nothing downstream of login knows or cares how the session was
obtained.

**Verification.** The backend checks the token's RS256 signature against
Google's published keys, its issuer, its expiry, and — the part that matters —
its **audience**, which must be one of the OAuth client IDs in
`GOOGLE_OAUTH_CLIENT_IDS`. That list is the entire trust boundary: a token minted
for someone else's Google app is just a signed statement addressed elsewhere.
With the setting unset the endpoint refuses every request with
`google_sign_in_unavailable`, so a deployment that has not been configured
cannot accidentally accept anything. Google is also only ever trusted to assert
an address it has itself verified: a token whose `email_verified` claim is false
is rejected with `google_email_unverified`. Every way a *presented* token can
fail verification — bad signature, wrong audience, expired — collapses into one
opaque `invalid_google_token`, because telling a caller which check failed only
helps someone probing the endpoint. Input that isn't shaped like a JWT at all is
refused earlier, as an ordinary `Invalid fields [ID_TOKEN]` validation error
alongside every other malformed request; that reveals nothing, and keeps the
endpoint consistent with the rest of the API.

**Which account it is.** Google's `sub` claim is the join key, stored on
`PositiveOnlySocialUser.google_sub`. It is the only identifier Google guarantees
is permanent and never reused; an email address is neither, so someone who
renames their mailbox still lands on the same account. The email is used only
once, on the first sign-in, to find an account to link to.

**Linking.** If no account carries that `sub` yet but one already holds the
email address, the two are the same person and the Google identity is attached to
the existing account — matched case-insensitively, since accounts were registered
with whatever case the user typed while Google normalizes what it asserts. Both
ways in then work: the password still logs in, and so does Google. Because Google
has proven ownership of the address, linking also settles our own email
verification, so an account still sitting on an unclicked verification link
becomes verified. Nothing enforces email uniqueness in the database; in the rare
case that more than one account holds the address, the sign-in is refused with
`google_email_ambiguous` rather than handing the Google identity to whichever row
sorted first.

Every rejection above is a stable machine-readable code, never prose — clients
map `google_email_ambiguous`, `google_email_unverified`,
`invalid_google_token` and `google_sign_in_unavailable` to their own copy, the
same way they already do for `account_banned` and `email_not_verified`.

**Creating an account.** Otherwise the sign-in creates one. A Google account
brings no username, so one is generated from the email local part (non-word
characters stripped, padded to the ten-character minimum, and given random digits
if it is taken). The generated name still has to clear the positivity bar a
chosen username does — but the user did not choose this one, so a rejection falls
back to a neutral `friend…` name rather than refusing the sign-in over somebody's
email address. The account gets a membership number in the usual join order,
starts already email-verified, and has **no usable password**, so the password
login path can never let anyone in with a guess. Like registering without a date
of birth, it is left identity-unverified and not an adult. The response carries
`created_account: true` and the new membership number so clients can greet a new
member.

**Two-factor authentication is not bypassed.** An account with 2FA enabled
answers `login/google/` with the same short-lived challenge `login/` returns, and
the code is exchanged at `login/2fa/` as usual. Holding the Google account is a
first factor, not a way past a second one the user deliberately turned on. An
active outright ban is refused here exactly as it is on every other login path.

**Configuration.** Google issues a separate OAuth client ID per platform, and
each mints tokens addressed to itself, so all of them go in the backend's
comma-separated `GOOGLE_OAUTH_CLIENT_IDS`:

| Surface | Client ID | Where it is set | How the token is obtained |
| --- | --- | --- | --- |
| Website | Web | `VITE_GOOGLE_CLIENT_ID` (see `website/deploy-web.sh`) | Google Identity Services, loaded from Google's CDN |
| iOS | iOS | `GoogleSignInConfig.clientID` in `ios/…/api/GoogleSignIn.swift` | `ASWebAuthenticationSession` + OAuth 2.0 PKCE, no SDK |
| Android | **Web** | `GOOGLE_WEB_CLIENT_ID` gradle property | Credential Manager (Sign in with Google) |

Android really does want the *web* client ID — Credential Manager mints the token
addressed to it — though an Android client ID keyed to the app's signing
certificate must also exist in the same Google Cloud project. Every surface treats
an unset client ID as "the feature is off" and simply shows no Google button, so
CI and local runs need no Google credentials. Step-by-step wiring lives in
[Google sign-in setup](google-sign-in-setup.md).

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
