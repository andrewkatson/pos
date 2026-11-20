# Reporting and user moderation (issue #467)

Any user can **report** a post or comment with a reason, and retract that report
later. What a report does *not* do is hide anything.

Reporting used to be a headcount: past a fixed number of reports the content was
hidden automatically, and dropping back under the bar un-hid it. That made
takedown a group vote — any coordinated set of accounts could remove anything,
and one user could be spammed into invisibility. A report count now hides
nothing at all. Instead the first report on a piece of content opens a
**moderation review** (`ModerationReview`, one row per post/comment, which *is*
that content's review state), and the review has two stages:

1. **Automated re-review.** The same classifier cascade that gates new posts is
   re-run — the local word-list pre-filter first, then the text and image
   cascades — over the **content alone**. The report count, the reporters, and
   the reasons they typed are never shown to a model, so no report can influence
   the verdict (and no crafted report reason can be written to steer it). Not
   even the bare fact that the content was reported is passed along: a model
   primed that *somebody thinks this is bad* leans toward rejection, which would
   rebuild the coordinated-report takedown this design removed, while priming it
   the other way ("this was already published") would make re-review laxer than
   the original gate. The re-review's protections are therefore structural — the
   appealable-verdict and escalate-on-outage asymmetries below — rather than
   hints in a prompt. A re-reviewing model receives exactly what a first-look
   model receives: its stage in the cascade (see
   [Post classification](post-classification.md)).
   The cascade is *ordered* differently from the first look, though: the
   re-review is a second opinion, so it leads with a tier that has not judged
   this content and consults the tier that approved it at creation last, as a
   fallback only (the per-content model chain, issue #511 — see
   [Post classification](post-classification.md)). Comments get the same
   treatment: their inline classification at creation is recorded as the first
   round. Rejected content is hidden as `hidden_reason: "classifier"` and its
   author is emailed; content that passes stays visible and the review is marked
   `cleared`. Two deliberate asymmetries: a *final* (normally non-appealable)
   verdict on re-review is still recorded as **appealable**, since this content
   was already published under an earlier verdict; and a provider outage
   **escalates to a human** rather than hiding, so reports can never fail closed.
2. **Human review.** Reports filed *after* a clear count toward escalation
   (`REPORTS_AFTER_CLEAR_BEFORE_ESCALATION`, default 3), which puts the review in
   the moderator queue — Django admin, *Moderation reviews*, filtered to
   "Escalated to a moderator". There an admin either **hides** the content
   (`hidden_reason: "reports"`, appealable) or **dismisses** the reports.

A moderator's decision is terminal *as far as reports are concerned*: dismissed
content is immune — further reports never reopen the case or spend another
provider call on it, so piling on is pointless — while a moderator can still
revisit their own decision from the queue (dismissing restores content the queue
hid, which is how a mistaken hide is undone without making the author appeal).
Approving an appeal likewise dismisses the content's review, so restored content
is not left one report away from another automated pass.

A review whose job never completes (worker crash, sustained provider outage) is
not left silently pending while the content stays up: `sweep_classifications`
re-enqueues stuck reviews and escalates the ones whose retry budget is spent
straight to the moderator queue.

Retracting a report never un-hides anything — hiding is a decision, not a
reversible vote. The one thing a retraction does is de-escalate a review whose
reports have *all* been withdrawn, sparing a moderator an empty queue entry.

Reporter-side limits: the report endpoints are rate limited per user, and on top
of that one account may file at most `MAX_REPORTS_PER_USER_PER_DAY` (default 30)
reports per rolling 24 hours, counted across posts, comments and accounts together, so no
single account can flood the queue. The budget counts **filings, not reports
currently standing**: retracting a report does not give budget back. That is why
a retraction stamps `retracted_time` on the report row instead of deleting it —
a deleted row would let one account cycle report → retract → report and open
unlimited reviews (each spending provider calls) while never holding more than
one live report. Everything that asks about the content rather than about the
reporter — is this reported, how many reports, what did the reporters say, does
this escalate — reads `PostReport/CommentReport/AccountReport.objects.active()`, so a
withdrawn report counts for nothing there.

## Reporting an account (issue #602)

Any signed-in user can report another **account** — a complaint about who
someone presents themselves as rather than about any one thing they posted —
from the ⋯ options menu on that person's profile, on every client, with a reason,
and retract it later (`POST /users/<username>/report/` and
`/users/<username>/report/retract/`). The profile-details payload carries the
viewer's own `is_reported` / `report_reason` so the menu can offer *Retract
report*; it is never present on your own profile, and nobody learns who else
reported an account. You cannot report yourself, a cross-age-band account is
treated as absent (as everywhere else), and an account that has blocked you can
still be reported — blocking hides a profile's details, not who someone is.
Account reports count against the same daily budget, and retraction stamps the
row the same way.

An account report runs through the same pipeline: the first one opens a
`ModerationReview` whose target is the account (`ModerationReview.account`; a
review has exactly one of post, comment or account), and nothing is hidden by
a headcount. What the automated re-review classifies is the account's
**username**, **bio** and **approved profile photo** — each separately, the
texts through the word-list pre-filter and the text cascade and the photo
through the image cascade, never the reports. Profiles keep no model-chain
lists, so the cascade runs in its normal order. What a failing verdict does
depends on the part:

- **Bio** — removed (set to empty), exactly the state a bio rejected on write
  would have left. The owner is emailed and can write a new one.
- **Photo** — removed, its S3 object deleted, and the owner told via
  `profile_image_status = "rejected"` and its reason code (plus an email). A
  photo upload still pending its own classification is a different picture and
  is left alone, along with its pending status.
- **Username** — a username is fixed once chosen, so it cannot be removed: the
  review escalates to the moderator queue, where a moderator can ban the
  account from the user admin.

Neither removal is appealable, for the same reason a rejected bio or photo is
not: the remedy is to set another. Only the exact bio and photo that were judged
are ever removed — one the owner replaced while the cascade ran was moderated on
its own way in. A profile that passes, or whose failing bio/photo was removed,
is `cleared`, and further reports count toward a human look as for posts. A
provider outage retries and then escalates, never removes.

In the moderator queue an account review shows the username, whether there is a
photo, and the bio. *Hide* removes the bio and photo (the account itself is
untouched — banning stays the user admin's job); *Dismiss* leaves the profile as
it is, and cannot restore a bio or photo an earlier step removed.

One difference from posts: a profile keeps changing. A decision about it must
not bind the profile that replaces it — a dismissal would make a later,
unacceptable bio unreportable, and a moderator's removal would leave the account
deaf to reports forever. So when the owner saves a new bio or a new photo is
approved, a `cleared`, `hidden` or `dismissed` account review drops back to
`cleared` with its escalation count reset: reports from then on are about the
profile as it now stands. A `pending` or `escalated` review is left alone, since
the re-review and the moderator look at the profile as it is when they reach it.
`set_bio`, the photo worker, the report endpoints and the moderator actions all
lock the user's row before the review row — the same content-then-review lock
order posts and comments use.
