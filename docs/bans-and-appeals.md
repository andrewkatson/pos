# Bans and appeals

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
(content hidden after [moderation review](reporting.md))
→ temporary outright ban → permanent outright ban.

## Appeals

A user can appeal moderation actions. Each appeal is an `Appeal` record (see
`backend/user_system/models.py`) that targets exactly one of a hidden post, a
hidden comment, or a ban, and carries the user's reason plus an admin
resolution trail.

- **Content appeals** (hidden posts and comments) are filed in-app. A signed-in
  user can list their own hidden posts/comments and their existing appeals, and
  submit an appeal, via the `appeals/...` endpoints. Content hidden by the
  classifier (including by the report-triggered re-review) and content a
  moderator hid after reviewing reports are both appealable. An item can be
  appealed only once. Posts still pending classification (nothing has been
  decided yet) and final classifier rejections (terminal by definition) are not
  appealable and never appear on the appeals screens. Approving an appeal also
  dismisses any moderation review of that content, so it is not immediately
  re-reviewed by the next report.
- **Ban appeals** go through the email-reply flow described in the suspension
  email, not an in-app endpoint: an outright-banned user has no active session
  and cannot log in, so they cannot reach an authenticated endpoint. Admins can
  record such an appeal against the ban for the audit trail.

Admins review appeals and either approve them — reversing the moderation action
(un-hiding the content) — or deny them.
