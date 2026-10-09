# Post classification (async)

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

Each model is also told **which line of defense it is** (issue #491), because
the three stages do not carry equal weight: a clear rejection from the *first*
reviewer is final and non-appealable, while the *third* reviewer's uncertainty
is itself a rejection, there being nobody left to escalate to. So stage 1 is
told that a middle score is a legitimate answer that escalates — cheap models
are overconfident, and the aim is to convert spurious hard rejections into
escalations — and stage 3 is told that a middle score no longer defers
anything, so it should not retreat there merely to avoid deciding. This is
about calibration, not making the first pass vaguer: clear content should still
be settled cheaply at stage 1.

What stage 3 is *not* told is that an unsure answer and a confident rejection
amount to the same thing, because they do not: a middle score at the last stage
is an **appealable** rejection, a reject-zone score a final one. Flattening that
would push a genuinely uncertain model into false confidence and quietly strip
the author's right to appeal — the very thing the middle zone preserves at the
last stage. The instruction is against strategic hedging only.

The earlier stages promise nothing about the reviewer that follows — not that
one is better, and not that one exists. Neither would be true in general.
Cheapest-first holds for a first look, but a later round puts fresh tiers first
and may rotate from a random start (below), so stage 2 can be a *cheaper* tier
than stage 1. And a middle score is not always an escalation: with a short
cascade it is the last word (an appealable rejection), and even with a full
cascade every remaining tier might error and leave that score standing. Whether
a later tier returns a usable score simply is not knowable when the prompt is
built, so the wording motivates abstaining without asserting a successor.
Two things are deliberately withheld. Models are never told the earlier
reviewers' **scores**, which would anchor them toward the middle and defeat the
point of asking again — each stage judges the content, not its predecessor. And
the stage is the reviewer's position among the scores that actually *counted*,
not its index in the tier order: a tier that errors or answers unusably is
skipped without consuming a stage, so the next tier inherits the line of defense
it failed to provide (the same number the cascade's own decision rules use).
Stage position is the only per-call context any model ever receives — in
particular the re-review a report triggers adds nothing about the report, by
design (see [Reporting](reporting.md)).

That fixed order is the order for a post's **first** look only. Content can be
judged by the cascade more than once — the retry of a classification that
reached no verdict, and the automated re-review a user report triggers (see
[Reporting](reporting.md)) — and a repeat round that
replayed the same order would just hand the content back to the model that
already decided it. So every post and comment keeps a **model chain** (issue
#511): which tiers have been consulted about it and which tier's score settled
each verdict (a duplicate-free list whose last entry is always the *final
determiner* of the latest decision — a tier that decides again moves to the
end; both lists are on the row as `classification_models_tried` /
`classification_model_chain`, and the moderator queue shows them). Each later
round is ordered to put fresh eyes first — tiers that have never looked at the
content, then tiers that looked but did not decide (a middle-zone score the
cascade escalated past, or an error), then the earlier deciders last as
fallbacks only, cheapest-first within each group. Once every available tier
has decided once, the cycle is complete: the lists are cleared and the next
round starts from a tier chosen at random (the cascade rotated to begin there),
so the second cycle is not a predictable replay of the first. A post's text and
image cascades share one order per round, so the same tier opens on both. See
`backend/user_system/classifiers/model_chain.py`. Model identities are
bookkeeping for the pipeline and moderators and are never exposed to users.

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
   On either rejection the author receives an email (with the public reason
   and, when appealable, how to appeal) and, best-effort, a native push
   notification (see [Push notifications](push-notifications.md)). Approval sends
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
`cleanup_orphan_images`) re-enqueues posts, **pending profile photos** and
**pending report reviews** stuck past a threshold (default 15 min,
`--stuck-minutes`), alerts (log error) once an item has exhausted its retry
budget — a report review escalates to the moderator queue instead, since its
content is visible meanwhile — and purges old final-rejection tombstones
(default 7 days, `--tombstone-days`; preview with `--dry-run`).

On the app host these async pieces are provisioned by `backend/tools/setup-django.sh`
as systemd units (see [Deploying and restarting services](deployment.md)):

- **`classification-worker.service`** — the long-lived RQ worker
  (`manage.py classification_worker`). Installed always but only enabled when
  `REDIS_URL` is set in `.env` (queue mode); in eager mode it is not needed.
- **`sweep-classifications.timer`** — runs `manage.py sweep_classifications`
  every 15 minutes (matching the stuck threshold).
- **`cleanup-orphan-images.timer`** — the daily S3 orphan sweep (see
  [Post image cleanup](images.md#post-image-cleanup)).

Comments are still classified inline in the request (text-only, much smaller
worst case); moving them to the same async flow is a tracked follow-up.
