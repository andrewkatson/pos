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
reports per rolling 24 hours, counted across posts and comments together, so no
single account can flood the queue. The budget counts **filings, not reports
currently standing**: retracting a report does not give budget back. That is why
a retraction stamps `retracted_time` on the report row instead of deleting it —
a deleted row would let one account cycle report → retract → report and open
unlimited reviews (each spending provider calls) while never holding more than
one live report. Everything that asks about the content rather than about the
reporter — is this reported, how many reports, what did the reporters say, does
this escalate — reads `PostReport/CommentReport.objects.active()`, so a
withdrawn report counts for nothing there.
