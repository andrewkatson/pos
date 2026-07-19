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

from .classifiers import image_classifier, text_classifier
from .classifiers.classifier_utils import ClassificationResult
from .constants import (
    HIDDEN_REASON_NONE, HIDDEN_REASON_CLASSIFIER,
    HIDDEN_REASON_PENDING_CLASSIFICATION, HIDDEN_REASON_CLASSIFIER_FINAL,
)
from .models import Post
from .s3 import delete_image

# Module-level aliases so tests can patch the classifiers here, mirroring the
# `user_system.views.text_classifier_class` pattern.
image_classifier_class = image_classifier
text_classifier_class = text_classifier

logger = logging.getLogger(__name__)

# Shared, bounded thread pool so a post's text and image cascades run
# concurrently (latency is max(text, image), not their sum) without a traffic
# spike spawning unbounded threads. The work is I/O-bound (external AI APIs).
_CLASSIFICATION_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="classify")

# The job is enqueued by dotted path so the web process never needs to pickle
# a callable, and RQ retries provider failures with growing backoff.
CLASSIFY_JOB_PATH = 'user_system.tasks.classify_post'
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

    # Count the attempt before doing the (fallible) external work, so the
    # sweep's alerting sees every try including ones that raised. The pending
    # filter makes the re-check and the increment one atomic UPDATE: a
    # duplicate delivery that lost the race neither burns retry budget nor
    # runs the (billable) cascades below.
    still_pending = Post.objects.filter(
        pk=post.pk, hidden_reason=HIDDEN_REASON_PENDING_CLASSIFICATION,
    ).update(classification_attempts=F('classification_attempts') + 1)
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
    final = ((not text_result and not text_result.appealable)
             or (not image_result and not image_result.appealable))
    # Text precedence for the recorded machine-readable code, matching the old
    # synchronous responses.
    reason_result = text_result if not text_result else image_result

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
        elif final:
            # Terminal rejection: keep the row as a tombstone (so the author's
            # client can reconcile the outcome) but strip the image reference;
            # the S3 object is deleted below, after the transition commits.
            claimed.hidden = True
            claimed.hidden_reason = HIDDEN_REASON_CLASSIFIER_FINAL
            claimed.classification_reason_code = reason_result.public_reason_code()
            image_url_to_delete = claimed.image_url
            claimed.image_url = None
        else:
            claimed.hidden = True
            claimed.hidden_reason = HIDDEN_REASON_CLASSIFIER
            claimed.classification_reason_code = reason_result.public_reason_code()
        claimed.save(update_fields=['hidden', 'hidden_reason', 'classification_reason_code', 'image_url'])

    # Side effects only after the one-time transition has committed, so they
    # can neither fire twice nor fire for a rolled-back transition.
    if allowed:
        logger.info("classify_post: post %s approved and visible.", post_identifier)
        return
    logger.info("classify_post: post %s rejected (final=%s, reason=%s).",
                post_identifier, final, reason_result.public_reason_code())
    _notify_author_of_rejection(claimed, text_result, image_result, final)
    if image_url_to_delete:
        # Best-effort: delete_image never raises, and cleanup_orphan_images is
        # the backstop for a missed delete (the row no longer references the
        # key, so the sweeper reclaims it after its grace window).
        delete_image(image_url_to_delete)
