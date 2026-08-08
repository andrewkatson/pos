"""Async post classification (issue #282).

make_post used to run the text/image AI cascades inline, which put minutes of
worst-case LLM latency on the request path and could surface as a 504. Now the
post is created hidden in a pending state and the cascade runs here instead:
either in an RQ worker fed by `enqueue_classification` (production, REDIS_URL
set) or eagerly in-process (dev/tests, no Redis).

The job is safe under at-least-once delivery: it only acts on posts still in
`pending_classification` and claims the row with `select_for_update` before
transitioning, so a redelivered or duplicate job is a no-op. Provider failures
(no usable score from any AI, unreachable S3) raise instead of rejecting, so
RQ retries them with backoff; when retries are exhausted the post simply stays
pending — fail closed, never publish unclassified content — and the
`sweep_classifications` command re-enqueues or alerts.
"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .blurhash_utils import compute_blurhash_for_image_url
from .classifiers import image_classifier, text_classifier, interest_classifier
from .classifiers.classifier_utils import ClassificationResult
from .classifiers.prefilter import prefilter_text
from .constants import (
    CLASSIFICATION_MAX_ATTEMPTS,
    HIDDEN_REASON_NONE, HIDDEN_REASON_CLASSIFIER,
    HIDDEN_REASON_PENDING_CLASSIFICATION, HIDDEN_REASON_CLASSIFIER_FINAL,
    PROFILE_IMAGE_STATUS_PENDING, PROFILE_IMAGE_STATUS_APPROVED,
    PROFILE_IMAGE_STATUS_REJECTED,
    MAX_INTEREST_TAGS_PER_POST, NON_CATEGORIZABLE_HIDDEN_REASONS,
    REVIEW_STATUS_PENDING, REVIEW_STATUS_CLEARED, REVIEW_STATUS_ESCALATED,
    REVIEW_STATUS_HIDDEN,
)
from .models import Post, PositiveOnlySocialUser, InterestCategory, ModerationReview
from . import push
from .s3 import delete_image

# Module-level aliases so tests can patch the classifiers here, mirroring the
# `user_system.views.text_classifier_class` pattern.
image_classifier_class = image_classifier
text_classifier_class = text_classifier
interest_classifier_class = interest_classifier
# Aliased here for the same reason (patchable in tests) and so the (best-effort)
# BlurHash computation lives behind one name at its single call site.
compute_blurhash = compute_blurhash_for_image_url

logger = logging.getLogger(__name__)

# Shared, bounded thread pool so a post's text and image cascades run
# concurrently (latency is max(text, image), not their sum) without a traffic
# spike spawning unbounded threads. The work is I/O-bound (external AI APIs).
_CLASSIFICATION_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="classify")

# The job is enqueued by dotted path so the web process never needs to pickle
# a callable, and RQ retries provider failures with growing backoff.
CLASSIFY_JOB_PATH = 'user_system.tasks.classify_post'
CLASSIFY_PROFILE_PHOTO_JOB_PATH = 'user_system.tasks.classify_profile_photo'
# Offline interest categorization (issues #446/#35). Best-effort topic tagging
# of an already-approved post, so — unlike classification — it carries no retry
# budget: a miss is harmless and the `categorize_posts` command re-runs it.
POST_CATEGORIZE_JOB_PATH = 'user_system.tasks.categorize_post'
# Report-triggered re-review of already-published content (issue #467). Carries
# the same retry budget as classification: a provider outage must not decide
# anything, so the job retries and the review escalates to a human if the
# budget runs out.
REPORT_REVIEW_JOB_PATH = 'user_system.tasks.review_reported_content'
RETRY_INTERVALS_SECONDS = [60, 300, 900]

# RQ kills jobs that exceed this. Worst case is two sequential cascades of
# three ~15s LLM calls plus an S3 fetch, so 5 minutes is comfortable headroom
# without letting a wedged job occupy the worker forever.
JOB_TIMEOUT_SECONDS = 300


class ClassificationProviderError(Exception):
    """No provider could evaluate the content (infrastructure, not a verdict).

    Raised so RQ retries the job; the post stays pending (hidden) meanwhile.
    """


def _queue():
    # Imported lazily so simply importing this module (e.g. from views) never
    # requires rq/redis to be importable in environments that run eagerly.
    from redis import Redis
    from rq import Queue
    return Queue(
        settings.CLASSIFICATION_QUEUE_NAME,
        connection=Redis.from_url(os.environ['REDIS_URL']),
    )


def enqueue_classification(post_identifier):
    """Schedule async classification for a freshly created pending post.

    In eager mode (no Redis) the job runs inline; a failure is swallowed
    because the post is already safely hidden-pending and the sweep command
    will pick it up. In queue mode the enqueue is deferred to on_commit so the
    worker can never fetch the job before the Post row is visible to it.
    """
    post_identifier = str(post_identifier)
    if settings.CLASSIFICATION_EAGER:
        try:
            classify_post(post_identifier)
        except Exception:
            logger.exception("Eager classification failed for post %s; it stays pending.", post_identifier)
        return

    def _enqueue():
        from rq import Retry
        try:
            _queue().enqueue(
                CLASSIFY_JOB_PATH,
                post_identifier,
                retry=Retry(max=len(RETRY_INTERVALS_SECONDS), interval=RETRY_INTERVALS_SECONDS),
                job_timeout=JOB_TIMEOUT_SECONDS,
            )
        except Exception:
            # The post is hidden-pending either way; the sweep re-enqueues it.
            logger.exception("Failed to enqueue classification for post %s; the sweep will retry it.", post_identifier)

    transaction.on_commit(_enqueue)


def enqueue_post_categorization(post_identifier):
    """Schedule offline interest categorization for an approved post.

    Mirrors enqueue_classification's eager/queue split, but best-effort: no
    Retry budget (a categorization miss is harmless; the `categorize_posts`
    command is the backstop) and eager failures are swallowed. In queue mode the
    enqueue is deferred to on_commit so the worker can't run before the post's
    approval transition is visible.
    """
    post_identifier = str(post_identifier)
    if settings.CLASSIFICATION_EAGER:
        try:
            categorize_post(post_identifier)
        except Exception:
            logger.exception("Eager categorization failed for post %s; a later sweep can retry it.", post_identifier)
        return

    def _enqueue():
        try:
            _queue().enqueue(POST_CATEGORIZE_JOB_PATH, post_identifier, job_timeout=JOB_TIMEOUT_SECONDS)
        except Exception:
            logger.exception("Failed to enqueue categorization for post %s; the categorize_posts command will retry it.",
                             post_identifier)

    transaction.on_commit(_enqueue)


def categorize_post(post_identifier):
    """Assign interest buckets to one approved post (issues #446/#35).

    Best-effort and idempotent: runs the interest categorizer over the caption
    and image, unions/caps the results, and replaces the post's
    interest_categories — except that an empty result never clears existing
    buckets, since the categorizer cannot distinguish "matches nothing" from
    "could not run" (see below). A post that never passed classification
    (pending or rejected) is skipped — there is nothing to surface. The
    categorizer helpers never raise, so this only fails on a DB error, which
    RQ/the command treats as a retryable miss.
    """
    post_identifier = str(post_identifier)
    try:
        post = Post.objects.get(post_identifier=post_identifier)
    except Post.DoesNotExist:
        logger.info("categorize_post: post %s no longer exists; nothing to do.", post_identifier)
        return
    if post.hidden_reason in NON_CATEGORIZABLE_HIDDEN_REASONS:
        logger.info("categorize_post: post %s is not approved (%s); skipping categorization.",
                    post_identifier, post.hidden_reason)
        return

    text_slugs = interest_classifier_class.categorize_text_interests(post.caption or "")
    image_slugs = (interest_classifier_class.categorize_image_interests(post.image_url)
                   if post.image_url else [])

    # Union in text-first order, capped — a post gets a handful of "what this is
    # about" buckets, not an exhaustive labeling. The order decides *which*
    # buckets survive the cap (caption beats image); it carries no meaning once
    # stored, since interest_categories is an unordered M2M.
    slugs = []
    for slug in list(text_slugs) + list(image_slugs):
        if slug not in slugs:
            slugs.append(slug)
        if len(slugs) >= MAX_INTEREST_TAGS_PER_POST:
            break

    if not slugs:
        # The categorizer is best-effort: it returns nothing both when the
        # content genuinely matches no bucket AND when it could not run at all
        # (no provider configured, provider down, unparseable reply). Those are
        # indistinguishable here, so never let an empty result *clear* tags a
        # previous run found — a redelivered job during an outage would
        # otherwise silently strip a post's buckets and degrade its feed
        # weighting. Leaving them is the safe reading of an empty result, and
        # for a post with no tags this is a no-op either way.
        logger.info("categorize_post: post %s produced no interest buckets; "
                    "leaving any existing ones untouched.", post_identifier)
        return

    # Re-order the fetched rows back into slug order (the queryset returns them
    # in the model's default ordering, by name) so the log below reports them by
    # priority rather than alphabetically.
    by_slug = {c.slug: c for c in InterestCategory.objects.filter(slug__in=slugs)}
    categories = [by_slug[s] for s in slugs if s in by_slug]
    post.interest_categories.set(categories)
    logger.info("categorize_post: post %s tagged with interests %s",
                post_identifier, [c.slug for c in categories])


def _blocked_parts(text_result, image_result):
    """User-facing phrases for what was rejected, mirroring the wording the old
    synchronous make_post response used."""
    parts = []
    if not text_result:
        parts.append(f"your caption {text_result.public_reason()}")
    if not image_result:
        parts.append(f"your image {image_result.public_reason()}")
    return parts


def _notify_author_of_rejection(post, text_result, image_result, final):
    """Email the author that their post was rejected (appealable or final).

    This rides the one-time pending -> rejected transition, so it fires exactly
    once per post. Best-effort like the ban email: a mail failure is logged and
    swallowed, and never blocks recording the classification outcome. There is
    deliberately no email on approval — the post simply appears.
    """
    if not post.author.email:
        return
    what = ' and '.join(_blocked_parts(text_result, image_result))
    if final:
        outcome = ("The decision is final and cannot be appealed, and the post "
                   "has been removed.")
    else:
        outcome = ("The post is hidden for now, but you can appeal the decision "
                   f"from the app or at {settings.FRONTEND_BASE_URL}.")
    body = (
        "Your recent post did not pass automated review because "
        f"{what}. {outcome}"
    )
    try:
        send_mail(
            "Your post was not approved",
            body,
            settings.EMAIL_HOST_USER,
            [post.author.email],
        )
    except Exception:
        logger.exception("Failed to send rejection email for post %s", post.post_identifier)


def _push_author_of_rejection(post, final):
    """Fire a best-effort native push that the author's post was rejected.

    Rides the same one-time pending -> rejected transition as the rejection
    email, so it notifies exactly once per post. Push is a nudge, never the
    source of truth (#282 in-app reconciliation is), so a failure — no device
    registered, provider down, permission denied — is logged and swallowed and
    never blocks recording the outcome. There is deliberately no push on
    approval; the post simply appears.
    """
    try:
        payload = push.build_rejection_payload(post, final)
        push.send_push(post.author, payload, push.PUSH_TYPE_POST_REJECTED)
    except Exception:
        logger.exception("Failed to send rejection push for post %s", post.post_identifier)


def classify_post(post_identifier):
    """RQ job: classify one pending post and record the outcome.

    Transitions (one-way): pending_classification -> visible, or
    -> classifier (hidden, appealable), or -> classifier_final (tombstone,
    image deleted). Any post not in pending_classification — already resolved,
    or deleted by its author while queued — is left alone, which is the whole
    idempotency story for at-least-once delivery.
    """
    try:
        post = Post.objects.get(post_identifier=post_identifier)
    except Post.DoesNotExist:
        logger.info("classify_post: post %s no longer exists; nothing to do.", post_identifier)
        return
    if post.hidden_reason != HIDDEN_REASON_PENDING_CLASSIFICATION:
        logger.info("classify_post: post %s already resolved (%s); nothing to do.",
                    post_identifier, post.hidden_reason)
        return

    # Hard cap on the retry budget: once it is spent, return successfully
    # (no raise) so RQ stops retrying, do no further (billable) provider
    # work, and leave the post hidden-pending — the fail-closed terminal
    # state the sweep alerts on.
    if post.classification_attempts >= CLASSIFICATION_MAX_ATTEMPTS:
        logger.error(
            "classify_post: post %s has exhausted its %d classification attempts; "
            "leaving it pending (fail closed) and dropping the job.",
            post_identifier, post.classification_attempts)
        return

    # Count the attempt before doing the (fallible) external work, so the
    # sweep's alerting sees every try including ones that raised. The pending
    # filter makes the re-check and the increment one atomic UPDATE: a
    # duplicate delivery that lost the race neither burns retry budget nor
    # runs the (billable) cascades below. updated_time is bumped explicitly
    # (queryset updates skip auto_now) so the sweep can tell "no recent
    # classification activity" apart from merely "created a while ago".
    still_pending = Post.objects.filter(
        pk=post.pk, hidden_reason=HIDDEN_REASON_PENDING_CLASSIFICATION,
    ).update(classification_attempts=F('classification_attempts') + 1,
             updated_time=timezone.now())
    if not still_pending:
        logger.info("classify_post: post %s was resolved concurrently; nothing to do.", post_identifier)
        return

    # The cascades run outside any DB transaction/lock: they can take minutes
    # in the worst case and must never pin a row lock while they do.
    text_future = _CLASSIFICATION_EXECUTOR.submit(text_classifier_class.is_text_positive, post.caption)
    image_future = (_CLASSIFICATION_EXECUTOR.submit(image_classifier_class.is_image_positive, post.image_url)
                    if post.image_url else None)
    text_result = text_future.result()
    # A text-only post has no image to classify; visibility depends solely on
    # the text result.
    image_result = image_future.result() if image_future else ClassificationResult(allowed=True)

    if text_result.provider_failure or image_result.provider_failure:
        # Not a verdict on the content: fail closed (stay pending) and let RQ
        # retry with backoff.
        raise ClassificationProviderError(
            f"Providers unavailable while classifying post {post_identifier} "
            f"(text failure={text_result.provider_failure}, image failure={image_result.provider_failure})")

    allowed = bool(text_result) and bool(image_result)
    text_final = not text_result and not text_result.appealable
    image_final = not image_result and not image_result.appealable
    final = text_final or image_final
    # The recorded machine-readable code comes from the decisive rejection:
    # a final rejection outranks an appealable one (a final image rejection is
    # what actually sank a post whose caption was merely appealable), and when
    # both sides carry the same finality, text takes precedence — both rules
    # matching the old synchronous responses.
    if final:
        reason_result = text_result if text_final else image_result
    else:
        reason_result = text_result if not text_result else image_result

    # Best-effort BlurHash placeholder for the image (issue #387), computed off
    # the request path here in the worker. Done before the transaction so the
    # (slow) S3 fetch + encode never pins the row lock, and skipped for final
    # rejections (their image is deleted below, so a placeholder is pointless).
    image_blurhash = (compute_blurhash(post.image_url)
                      if post.image_url and not final else None)

    image_url_to_delete = None
    with transaction.atomic():
        # Re-claim the row under lock so a concurrent duplicate delivery
        # cannot apply the transition (and its side effects) twice.
        claimed = Post.objects.select_for_update().filter(
            pk=post.pk, hidden_reason=HIDDEN_REASON_PENDING_CLASSIFICATION).first()
        if claimed is None:
            logger.info("classify_post: post %s was resolved concurrently; nothing to do.", post_identifier)
            return
        if allowed:
            claimed.hidden = False
            claimed.hidden_reason = HIDDEN_REASON_NONE
            # Explicitly cleared (it is in update_fields below) so a stale
            # value — e.g. a manual admin edit — can never survive an approval
            # and leak into the author-visible status payloads.
            claimed.classification_reason_code = None
            claimed.image_blurhash = image_blurhash
        elif final:
            # Terminal rejection: keep the row as a tombstone (so the author's
            # client can reconcile the outcome) but strip the image reference;
            # the S3 object is deleted below, after the transition commits.
            claimed.hidden = True
            claimed.hidden_reason = HIDDEN_REASON_CLASSIFIER_FINAL
            claimed.classification_reason_code = reason_result.public_reason_code()
            image_url_to_delete = claimed.image_url
            claimed.image_url = None
            claimed.image_blurhash = None
        else:
            claimed.hidden = True
            claimed.hidden_reason = HIDDEN_REASON_CLASSIFIER
            claimed.classification_reason_code = reason_result.public_reason_code()
            # Kept even while hidden: an appeal can un-hide this post later
            # (without re-running classification), and the placeholder should be
            # ready when it does.
            claimed.image_blurhash = image_blurhash
        claimed.save(update_fields=['hidden', 'hidden_reason', 'classification_reason_code',
                                    'image_url', 'image_blurhash'])

    # Side effects only after the one-time transition has committed, so they
    # can neither fire twice nor fire for a rolled-back transition.
    if allowed:
        logger.info("classify_post: post %s approved and visible.", post_identifier)
        # Now that the post is public, tag it with interest buckets for feed
        # weighting (issues #446/#35). Best-effort and off the approval's
        # critical path: enqueue_post_categorization swallows eager failures and
        # carries no retry budget, so a categorization hiccup never disturbs the
        # (already committed) approval.
        enqueue_post_categorization(post_identifier)
        return
    logger.info("classify_post: post %s rejected (final=%s, reason=%s).",
                post_identifier, final, reason_result.public_reason_code())
    _notify_author_of_rejection(claimed, text_result, image_result, final)
    _push_author_of_rejection(claimed, final)
    if image_url_to_delete:
        # Best-effort: delete_image never raises, and cleanup_orphan_images is
        # the backstop for a missed delete (the row no longer references the
        # key, so the sweeper reclaims it after its grace window).
        delete_image(image_url_to_delete)


def _notify_author_of_review_hide(post, text_result, image_result):
    """Email the author that a reported post was hidden by the automated re-review.

    Deliberately says nothing about who reported it or how many did: reports
    trigger a look at the content, they never decide the outcome, and telling
    authors otherwise would advertise mass-reporting as a weapon. Best-effort
    like every other moderation email — a mail failure is logged and swallowed.
    """
    if not post.author.email:
        return
    what = ' and '.join(_blocked_parts(text_result, image_result))
    body = (
        "A post of yours was re-checked against our content guidelines and did "
        f"not pass because {what}. The post is hidden for now, but you can "
        f"appeal the decision from the app or at {settings.FRONTEND_BASE_URL}."
    )
    try:
        send_mail(
            "Your post was hidden after a review",
            body,
            settings.EMAIL_HOST_USER,
            [post.author.email],
        )
    except Exception:
        logger.exception("Failed to send review-hide email for post %s", post.post_identifier)


def enqueue_report_review(review_identifier):
    """Schedule the automated re-review of freshly reported content (issue #467).

    Mirrors enqueue_classification: inline in eager mode (dev/tests), otherwise
    queued on_commit so the worker cannot fetch the job before the review row is
    visible to it. An eager failure is swallowed — the review simply stays
    pending, and nothing about the content changes until a verdict exists.
    """
    review_identifier = str(review_identifier)
    if settings.CLASSIFICATION_EAGER:
        try:
            review_reported_content(review_identifier)
        except Exception:
            logger.exception("Eager report review failed for review %s; it stays pending.", review_identifier)
        return

    def _enqueue():
        from rq import Retry
        try:
            _queue().enqueue(
                REPORT_REVIEW_JOB_PATH,
                review_identifier,
                retry=Retry(max=len(RETRY_INTERVALS_SECONDS), interval=RETRY_INTERVALS_SECONDS),
                job_timeout=JOB_TIMEOUT_SECONDS,
            )
        except Exception:
            logger.exception("Failed to enqueue report review %s; it stays pending for a moderator.",
                             review_identifier)

    transaction.on_commit(_enqueue)


def _review_content_results(target, is_post):
    """Run the moderation cascades over reported content and return
    (text_result, image_result).

    The content and nothing else is classified: the report count, the reporters'
    identities and the reasons they typed are never passed to a model. That is
    what makes the verdict unspammable — and it also keeps reporter-authored
    text out of a prompt, so a report cannot be written to steer the answer.
    """
    text = (target.caption if is_post else target.body) or ''
    image_url = target.image_url if is_post else None

    if text:
        # The zero-cost local list check first, exactly as make_post runs it —
        # the word lists grow over time, so content published before an addition
        # is caught here without spending a provider call.
        prefiltered = prefilter_text(text)
        if not prefiltered:
            return prefiltered, ClassificationResult(allowed=True)

    text_future = (_CLASSIFICATION_EXECUTOR.submit(text_classifier_class.is_text_positive, text)
                   if text else None)
    image_future = (_CLASSIFICATION_EXECUTOR.submit(image_classifier_class.is_image_positive, image_url)
                    if image_url else None)
    text_result = text_future.result() if text_future else ClassificationResult(allowed=True)
    image_result = image_future.result() if image_future else ClassificationResult(allowed=True)
    return text_result, image_result


def review_reported_content(review_identifier):
    """RQ job: re-examine one reported post or comment and record the outcome.

    Transitions out of `pending` (one-way): `hidden` when the cascades reject the
    content, or `cleared` when they do not — and `escalated` when no verdict can
    be reached, so an outage sends the case to a human instead of hiding
    anything. A rejection here is always recorded as an APPEALABLE classifier
    hide, even when the cascade's verdict was a final one: this content was
    already published under an earlier verdict, so its author gets a route back.

    Only acts on a review still in `pending` and claims the row before
    transitioning, so a redelivered or duplicate job is a no-op (the same
    idempotency story as classify_post). Provider failures raise so RQ retries
    with backoff; the content stays visible meanwhile — reports must never fail
    closed, or an outage would hand reporters the takedown power this whole
    design removes.
    """
    review = ModerationReview.objects.filter(review_identifier=review_identifier).first()
    if review is None:
        logger.info("review_reported_content: review %s no longer exists; nothing to do.", review_identifier)
        return
    if review.status != REVIEW_STATUS_PENDING:
        logger.info("review_reported_content: review %s already resolved (%s); nothing to do.",
                    review_identifier, review.status)
        return

    target = review.target
    is_post = review.post_id is not None
    if target.hidden:
        # Already hidden (classifier, or a moderator) — there is nothing for the
        # re-review to decide, and its reason must not be overwritten.
        ModerationReview.objects.filter(pk=review.pk, status=REVIEW_STATUS_PENDING).update(
            status=REVIEW_STATUS_HIDDEN, reviewed_time=timezone.now(), updated=timezone.now(),
            resolution_note=f"Already hidden ({target.hidden_reason or 'unspecified'}) when the review ran")
        logger.info("review_reported_content: review %s targets already-hidden content; closing it.",
                    review_identifier)
        return

    if review.review_attempts >= CLASSIFICATION_MAX_ATTEMPTS:
        # The retry budget is spent and no verdict was reached. Escalate rather
        # than retry or hide: a human decides what an unreachable provider could
        # not. Returning successfully stops RQ retrying.
        ModerationReview.objects.filter(pk=review.pk, status=REVIEW_STATUS_PENDING).update(
            status=REVIEW_STATUS_ESCALATED, updated=timezone.now(),
            resolution_note="Automated review could not reach a verdict; escalated for a moderator")
        logger.error("review_reported_content: review %s exhausted its %d attempts; escalating to a moderator.",
                     review_identifier, review.review_attempts)
        return

    # Claim the attempt before doing the fallible (and billable) external work.
    #
    # This is a compare-and-swap, not just a still-pending check: the WHERE pins
    # the attempt count this job read, and the SET writes the successor
    # explicitly rather than as F('review_attempts') + 1. That matters because a
    # bare status=pending guard does NOT serialize duplicate deliveries — two
    # jobs that both read the row before either resolves it would both match it
    # and both run the cascades, since the row lock only orders the UPDATEs, it
    # never makes one of them fail. With the count pinned, the loser
    # re-evaluates its WHERE against the winner's committed row, matches
    # nothing, and drops out here.
    #
    # What this does not buy is a lease: a delivery that arrives *after* the
    # winner claimed — reading the already-incremented count — claims the next
    # attempt and runs its own cascade. Holding that off needs a locked_at lease
    # with an expiry, and a stuck-lease state for the sweep to reconcile, which
    # is not worth it here: the cost of that rarer overlap is duplicate provider
    # spend, never a duplicate outcome (the select_for_update claim below admits
    # exactly one verdict), and the `updated` bump this UPDATE performs already
    # keeps the sweep from re-enqueueing a review that was claimed recently.
    claimed_attempt = review.review_attempts
    claimed = ModerationReview.objects.filter(
        pk=review.pk, status=REVIEW_STATUS_PENDING, review_attempts=claimed_attempt,
    ).update(review_attempts=claimed_attempt + 1, updated=timezone.now())
    if not claimed:
        logger.info("review_reported_content: review %s was claimed or resolved concurrently; nothing to do.",
                    review_identifier)
        return

    # The cascades run outside any transaction/lock: they can take minutes.
    text_result, image_result = _review_content_results(target, is_post)

    if text_result.provider_failure or image_result.provider_failure:
        # Not a verdict on the content: leave the content visible and let RQ
        # retry with backoff.
        raise ClassificationProviderError(
            f"Providers unavailable while reviewing reported content for review {review_identifier} "
            f"(text failure={text_result.provider_failure}, image failure={image_result.provider_failure})")

    allowed = bool(text_result) and bool(image_result)
    reason_result = text_result if not text_result else image_result
    now = timezone.now()

    with transaction.atomic():
        # Re-claim the row under lock so a concurrent duplicate delivery cannot
        # apply the transition (and its side effects) twice.
        claimed = ModerationReview.objects.select_for_update().filter(
            pk=review.pk, status=REVIEW_STATUS_PENDING).first()
        if claimed is None:
            logger.info("review_reported_content: review %s was resolved concurrently; nothing to do.",
                        review_identifier)
            return
        # Re-read the target inside the lock, because the pre-cascade check that
        # it was visible is minutes stale by now: a moderator (or any other hide
        # path) can have hidden it while the providers were being consulted. The
        # verdict computed against a since-hidden target is moot, and applying it
        # would overwrite whatever reason actually hid it — the same invariant
        # the pre-cascade check enforces, which must hold here too. Overwriting a
        # classifier_final reason would be worse than untidy: it would make a
        # terminal, image-deleted tombstone look appealable again.
        target = claimed.target
        if target.hidden:
            claimed.status = REVIEW_STATUS_HIDDEN
            claimed.reviewed_time = now
            claimed.resolution_note = (
                f"Already hidden ({target.hidden_reason or 'unspecified'}) "
                "by the time the review finished")
            claimed.save(update_fields=['status', 'reviewed_time', 'resolution_note', 'updated'])
            logger.info("review_reported_content: review %s found its %s already hidden (%s); "
                        "leaving that decision alone.",
                        review_identifier, claimed.target_kind, target.hidden_reason or 'unspecified')
            return
        if allowed:
            claimed.status = REVIEW_STATUS_CLEARED
            # Reports counted from here decide whether a human takes a look, so
            # the ones this review already accounted for cannot escalate it too.
            claimed.reports_at_last_review = claimed.report_count()
        else:
            claimed.status = REVIEW_STATUS_HIDDEN
            target.hidden = True
            target.hidden_reason = HIDDEN_REASON_CLASSIFIER
            if is_post:
                target.classification_reason_code = reason_result.public_reason_code()
                target.save(update_fields=['hidden', 'hidden_reason', 'classification_reason_code'])
            else:
                target.save(update_fields=['hidden', 'hidden_reason'])
        claimed.reviewed_time = now
        claimed.save(update_fields=['status', 'reports_at_last_review', 'reviewed_time', 'updated'])

    # Side effects only after the one-time transition has committed.
    if allowed:
        logger.info("review_reported_content: review %s cleared; the %s stays visible.",
                    review_identifier, claimed.target_kind)
        return
    logger.info("review_reported_content: review %s hid the %s (reason=%s).",
                review_identifier, claimed.target_kind, reason_result.public_reason_code())
    if is_post:
        # Comments are hidden silently, as they always have been; only posts
        # carry an author-facing moderation lifecycle (email + push + appeal).
        _notify_author_of_review_hide(target, text_result, image_result)
        _push_author_of_rejection(target, final=False)


def enqueue_profile_photo_classification(user_id):
    """Schedule async classification for a freshly uploaded pending profile photo.

    The user's pending_profile_image_url is already stored (and never shown to
    others) before this runs, so — exactly like enqueue_classification for
    posts — an eager failure is swallowed (the sweep re-enqueues) and the queued
    enqueue is deferred to on_commit so the worker cannot fetch the job before
    the pending photo is visible to it.
    """
    user_id = str(user_id)
    if settings.CLASSIFICATION_EAGER:
        try:
            classify_profile_photo(user_id)
        except Exception:
            logger.exception("Eager profile-photo classification failed for user %s; it stays pending.", user_id)
        return

    def _enqueue():
        from rq import Retry
        try:
            _queue().enqueue(
                CLASSIFY_PROFILE_PHOTO_JOB_PATH,
                user_id,
                retry=Retry(max=len(RETRY_INTERVALS_SECONDS), interval=RETRY_INTERVALS_SECONDS),
                job_timeout=JOB_TIMEOUT_SECONDS,
            )
        except Exception:
            logger.exception("Failed to enqueue profile-photo classification for user %s; the sweep will retry it.", user_id)

    transaction.on_commit(_enqueue)


def classify_profile_photo(user_id):
    """RQ job: classify one user's pending profile photo and record the outcome.

    Transitions (one-way, from the pending state): approved — the pending photo
    becomes the live profile_image_url and the previously approved photo (if
    any) is cleaned from S3; or rejected — the pending photo is dropped and its
    S3 object cleaned up, while any previously approved photo is left untouched.
    Only acts on a user still in PROFILE_IMAGE_STATUS_PENDING and re-claims the
    row under lock before transitioning, so a redelivered or duplicate job is a
    no-op (the idempotency story for at-least-once delivery, mirroring
    classify_post). A provider failure raises so RQ retries with backoff; the
    photo stays pending (never shown) meanwhile.
    """
    try:
        user = PositiveOnlySocialUser.objects.get(pk=user_id)
    except PositiveOnlySocialUser.DoesNotExist:
        logger.info("classify_profile_photo: user %s no longer exists; nothing to do.", user_id)
        return
    if user.profile_image_status != PROFILE_IMAGE_STATUS_PENDING or not user.pending_profile_image_url:
        logger.info("classify_profile_photo: user %s has no pending photo (status=%s); nothing to do.",
                    user_id, user.profile_image_status)
        return

    # Hard cap on the retry budget: once spent, return successfully (no raise)
    # so RQ stops retrying and no further billable provider work runs; the photo
    # stays pending (fail closed — never shown) and the sweep alerts.
    if user.profile_image_classification_attempts >= CLASSIFICATION_MAX_ATTEMPTS:
        logger.error(
            "classify_profile_photo: user %s has exhausted its %d classification attempts; "
            "leaving the photo pending (fail closed) and dropping the job.",
            user_id, user.profile_image_classification_attempts)
        return

    # The exact upload this job is about. Both the increment-UPDATE and the
    # row-claim below filter on it, so if the user replaces their pending photo
    # while this job runs (or a duplicate delivery already resolved it), this job
    # becomes a no-op: it neither burns retry budget nor applies its verdict to a
    # *different* upload than the one it classified.
    pending_url = user.pending_profile_image_url

    # Count the attempt before the fallible external work (so the sweep sees
    # every try) and bump classification_time so "stuck" means "no recent
    # activity". Filtering on the specific pending URL makes the re-check and
    # increment one atomic UPDATE.
    still_pending = PositiveOnlySocialUser.objects.filter(
        pk=user.pk, profile_image_status=PROFILE_IMAGE_STATUS_PENDING,
        pending_profile_image_url=pending_url,
    ).update(profile_image_classification_attempts=F('profile_image_classification_attempts') + 1,
             profile_image_classification_time=timezone.now())
    if not still_pending:
        logger.info("classify_profile_photo: user %s pending photo changed or was resolved concurrently; nothing to do.", user_id)
        return

    result = image_classifier_class.is_image_positive(pending_url)
    if result.provider_failure:
        # Not a verdict on the content: fail closed (stay pending) and let RQ
        # retry with backoff.
        raise ClassificationProviderError(
            f"Provider unavailable while classifying profile photo for user {user_id}")

    allowed = bool(result)

    # Best-effort BlurHash placeholder for the avatar (issue #460), the profile
    # counterpart of the one classify_post computes. Done here, before the
    # transaction, so the (slow) S3 fetch + encode never pins the row lock, and
    # only for an approval — a rejected upload's image is deleted below, and a
    # pending one is never shown to anyone, so neither needs a placeholder.
    profile_image_blurhash = compute_blurhash(pending_url) if allowed else None

    old_live_url = None
    rejected_url = None
    with transaction.atomic():
        # Re-claim on the same specific pending URL: a photo swapped out from
        # under this job (now a different pending_profile_image_url) must not be
        # transitioned by this job's stale verdict.
        claimed = PositiveOnlySocialUser.objects.select_for_update().filter(
            pk=user.pk, profile_image_status=PROFILE_IMAGE_STATUS_PENDING,
            pending_profile_image_url=pending_url).first()
        if claimed is None:
            logger.info("classify_profile_photo: user %s pending photo changed or was resolved concurrently; nothing to do.", user_id)
            return
        if allowed:
            # Promote the pending photo to live; the previously approved photo
            # (if different) is now orphaned and deleted after the commit.
            old_live_url = claimed.profile_image_url
            claimed.profile_image_url = claimed.pending_profile_image_url
            claimed.pending_profile_image_url = None
            claimed.profile_image_status = PROFILE_IMAGE_STATUS_APPROVED
            claimed.profile_image_reason_code = None
            # Always assigned (it is in update_fields below), so the previous
            # photo's hash can never survive as a placeholder for a new one —
            # a None here just means "no placeholder", never "the old blur".
            claimed.profile_image_blurhash = profile_image_blurhash
        else:
            # Drop the rejected photo; keep any previously approved photo intact
            # so a bad new upload does not wipe out a good current avatar.
            rejected_url = claimed.pending_profile_image_url
            claimed.pending_profile_image_url = None
            claimed.profile_image_status = PROFILE_IMAGE_STATUS_REJECTED
            claimed.profile_image_reason_code = result.public_reason_code()
        claimed.save(update_fields=[
            'profile_image_url', 'pending_profile_image_url',
            'profile_image_status', 'profile_image_reason_code',
            'profile_image_blurhash',
        ])

    # Side effects only after the one-time transition has committed, so they can
    # neither fire twice nor fire for a rolled-back transition.
    if allowed:
        logger.info("classify_profile_photo: user %s photo approved.", user_id)
        if old_live_url and old_live_url != claimed.profile_image_url:
            delete_image(old_live_url)
        return
    logger.info("classify_profile_photo: user %s photo rejected (reason=%s).",
                user_id, result.public_reason_code())
    if rejected_url:
        delete_image(rejected_url)
