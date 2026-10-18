"""Push notifications for social activity (issue #444).

Beyond the post-rejection push (#342), a user can be told when someone they
follow publishes a post, when someone comments on their post or replies to
their comment, and when someone likes their post or comment. Each recipient
filters these in Settings by kind and by who the activity came from (the
category they gave the actor — following / friend / family — or "other" for
someone they do not follow); see PUSH_TYPE_TREE and push.is_push_type_enabled.

Push is a nudge, never the source of truth, so all of this is best-effort and
off the request path: the views and the classification worker only *enqueue*
a job here, and the job re-reads the content and re-checks visibility when it
runs, so a like withdrawn, a comment hidden or a block placed in the meantime
simply sends nothing. A recipient is only ever told about content they can
see — the same visibility rules (audience, privacy, age band, shadow ban,
hidden) that govern feeds and comment lists — and never about an actor they
have blocked or who has blocked them.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q

from . import push
from .constants import (
    AUDIENCE_ALLOWED_CATEGORIES, BAN_TYPE_SHADOW, POST_AUDIENCE_PUBLIC, PUSH_SOURCE_OTHER,
    PUSH_TYPE_NEW_POST, PUSH_TYPE_NEW_COMMENT, PUSH_TYPE_NEW_LIKE,
    push_source_type,
)
from .models import (
    Comment, CommentLike, DeviceToken, Post, PostLike, UserBan, UserBlock, UserFollow,
)
from .visibility import audience_admits, can_view_post, in_same_age_band

logger = logging.getLogger(__name__)

# Jobs are enqueued by dotted path, like the classification jobs in tasks.py.
_JOB_PATH_PREFIX = 'user_system.notifications.'

# Liking, unliking and liking again must not turn into a stream of pushes: the
# first like on a piece of content by a given user notifies, and repeats within
# this window are dropped.
LIKE_PUSH_DEDUPE_SECONDS = 24 * 60 * 60

# Followers one new-post job notifies. Each follower costs a few queries and a
# provider round trip, so a job stays well inside JOB_TIMEOUT_SECONDS; a larger
# following is worked through by a chain of continuation jobs.
NEW_POST_FANOUT_BATCH_SIZE = 50


# ---------------------------------------------------------------------------
# Enqueue (called from views and the classification worker)
# ---------------------------------------------------------------------------

def _enqueue(job_name, *args):
    """Run a notification job off the request path.

    Mirrors tasks.enqueue_post_categorization: inline in eager mode (dev/tests,
    no Redis), otherwise enqueued on commit so the worker never runs before the
    content it reads is visible. Jobs go to their own queue (PUSH_QUEUE_NAME),
    which the worker drains only when the classification queue is empty.
    Best-effort either way — no retry budget, and any failure is logged and
    swallowed, since a missed push is harmless.
    """
    if settings.CLASSIFICATION_EAGER:
        try:
            globals()[job_name](*args)
        except Exception:
            logger.exception("Eager notification job %s failed for %s.", job_name, args)
        return

    def _enqueue_on_commit():
        # Lazy: tasks imports this module (to notify followers on approval).
        from .tasks import _queue, JOB_TIMEOUT_SECONDS
        try:
            _queue(settings.PUSH_QUEUE_NAME).enqueue(
                _JOB_PATH_PREFIX + job_name, *args, job_timeout=JOB_TIMEOUT_SECONDS)
        except Exception:
            logger.exception("Failed to enqueue notification job %s for %s.", job_name, args)

    transaction.on_commit(_enqueue_on_commit)


def notify_new_post(post_identifier):
    """A post was just approved: tell the author's followers who can see it."""
    _enqueue('push_new_post', str(post_identifier))


def notify_new_comment(comment):
    """A visible comment or reply was just created."""
    _enqueue('push_new_comment', str(comment.comment_identifier))


def notify_post_like(post, liker):
    _enqueue('push_post_like', str(post.post_identifier), liker.pk)


def notify_comment_like(comment, liker):
    _enqueue('push_comment_like', str(comment.comment_identifier), liker.pk)


# ---------------------------------------------------------------------------
# Shared checks
# ---------------------------------------------------------------------------

def _is_shadow_banned(user):
    return UserBan.objects.active().filter(user=user, ban_type=BAN_TYPE_SHADOW).exists()


def _may_notify(recipient, actor):
    """Whether `recipient` may hear about anything `actor` did: never about
    themselves, never across age bands, never from a shadow-banned actor (whose
    activity nobody else can see), and never across a block in either
    direction."""
    if recipient.pk == actor.pk:
        return False
    if not in_same_age_band(recipient, actor):
        return False
    if _is_shadow_banned(actor):
        return False
    return not UserBlock.objects.filter(
        Q(user_blocker=recipient, user_blocked=actor) | Q(user_blocker=actor, user_blocked=recipient)
    ).exists()


def _source(recipient, actor):
    """Who `actor` is to `recipient`: the category on the recipient's follow
    edge to them, or "other" when the recipient does not follow them."""
    category = UserFollow.objects.filter(
        user_from=recipient, user_to=actor).values_list('category', flat=True).first()
    return category or PUSH_SOURCE_OTHER


def _send(recipient, payload, notification_type, **kwargs):
    """send_push for one recipient, isolated so one failure never stops a
    fan-out to the others."""
    try:
        push.send_push(recipient, payload, notification_type, **kwargs)
    except Exception:
        logger.exception("Activity push %s failed for user %s", notification_type, recipient.pk)


def _first_like(kind, target_id, liker_id):
    """True the first time this user's like on this content is seen inside the
    dedupe window; False for a like/unlike/like repeat."""
    return cache.add(f"push:like:{kind}:{target_id}:{liker_id}", True, LIKE_PUSH_DEDUPE_SECONDS)


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def push_new_post(post_identifier, after_follow_id=None):
    """Fan a newly approved post out to the author's followers.

    Only followers are ever told (the category on their follow edge picks the
    preference type), and each must be able to see the post — so a friends-only
    post reaches friends and family alone, exactly as the feed would show it.

    One job handles a bounded batch of follow edges, in id order after
    `after_follow_id`. When the batch is full it enqueues the next one *before*
    sending, so a batch that dies (a timeout behind a slow provider) costs only
    its own followers, never the rest. Each batch re-reads the post, so one
    hidden or deleted mid-way stops the remaining batches.

    Everything a batch needs is loaded up front in a handful of queries, not
    per follower: the post-level checks (hidden, the author's shadow ban) run
    once, and blocks, the post's audience, preferences and device tokens are
    each read for the whole batch. Together with the age-band check these are
    exactly can_view_post plus _may_notify — privacy needs no check, since
    every recipient follows the author.
    """
    post = Post.objects.select_related('author').filter(post_identifier=post_identifier).first()
    if post is None or post.hidden:
        return
    author = post.author
    if _is_shadow_banned(author):
        return
    edges = UserFollow.objects.filter(user_to=author).select_related('user_from').order_by('pk')
    if after_follow_id is not None:
        edges = edges.filter(pk__gt=after_follow_id)
    batch = list(edges[:NEW_POST_FANOUT_BATCH_SIZE])
    if len(batch) == NEW_POST_FANOUT_BATCH_SIZE:
        _enqueue('push_new_post', str(post_identifier), batch[-1].pk)
    follower_ids = [edge.user_from_id for edge in batch]
    blocked_ids = set()
    for blocker_id, blocked_id in UserBlock.objects.filter(
            Q(user_blocker=author, user_blocked_id__in=follower_ids)
            | Q(user_blocked=author, user_blocker_id__in=follower_ids)
    ).values_list('user_blocker_id', 'user_blocked_id'):
        blocked_ids.add(blocked_id if blocker_id == author.pk else blocker_id)
    if post.audience == POST_AUDIENCE_PUBLIC:
        admitted_ids = set(follower_ids)
    else:
        # The author's own labels decide a restricted post's audience.
        admitted_ids = set(UserFollow.objects.filter(
            user_from=author, user_to_id__in=follower_ids,
            category__in=AUDIENCE_ALLOWED_CATEGORIES.get(post.audience, []),
        ).values_list('user_to_id', flat=True))
    disabled = push.disabled_push_types(follower_ids)
    tokens_by_user = {}
    for row in DeviceToken.objects.filter(user_id__in=follower_ids):
        tokens_by_user.setdefault(row.user_id, []).append(row)

    payload = push.build_activity_payload(
        PUSH_TYPE_NEW_POST, post, f"{author.username} shared a new post", post.caption or "Tap to see it.")
    for edge in batch:
        follower = edge.user_from
        if (follower.pk == author.pk or follower.pk in blocked_ids or follower.pk not in admitted_ids
                or not in_same_age_band(follower, author)):
            continue
        notification_type = push_source_type(PUSH_TYPE_NEW_POST, edge.category)
        if not push.push_type_enabled_in(disabled.get(follower.pk, ()), notification_type):
            continue
        tokens = tokens_by_user.get(follower.pk)
        if not tokens:
            continue
        _send(follower, payload, notification_type, tokens=tokens)


def push_new_comment(comment_identifier):
    """Tell the people a new comment or reply concerns.

    A top-level comment notifies the post's author. A reply notifies the
    thread's starter ("replied to your comment") and, when that is someone
    else, the post's author too. Each recipient must be able to see both the
    post and the comment (its audience may exclude them).
    """
    comment = (Comment.objects
               .select_related('author', 'comment_thread__post__author')
               .filter(comment_identifier=comment_identifier).first())
    if comment is None or comment.hidden:
        return
    actor = comment.author
    post = comment.comment_thread.post
    starter = (Comment.objects.filter(comment_thread=comment.comment_thread)
               .select_related('author').order_by('creation_time', 'pk').first())
    is_reply = starter is not None and starter.pk != comment.pk

    recipients = []
    if is_reply:
        recipients.append((starter.author, f"{actor.username} replied to your comment"))
        if starter.author_id != post.author_id:
            recipients.append((post.author, f"{actor.username} replied to a comment on your post"))
    else:
        recipients.append((post.author, f"{actor.username} commented on your post"))

    for recipient, title in recipients:
        if not _may_notify(recipient, actor):
            continue
        if not can_view_post(post, recipient) or not audience_admits(comment, recipient):
            continue
        payload = push.build_activity_payload(PUSH_TYPE_NEW_COMMENT, post, title, comment.body)
        _send(recipient, payload, push_source_type(PUSH_TYPE_NEW_COMMENT, _source(recipient, actor)))


def push_post_like(post_identifier, liker_id):
    """Tell a post's author someone liked it (once per liker per window)."""
    post = Post.objects.select_related('author').filter(post_identifier=post_identifier).first()
    liker = get_user_model().objects.filter(pk=liker_id).first()
    if post is None or liker is None or post.hidden:
        return
    # Unliked before the job ran: nothing to announce.
    if not PostLike.objects.filter(post=post, user=liker).exists():
        return
    author = post.author
    if not _may_notify(author, liker):
        return
    if not _first_like('post', post.post_identifier, liker.pk):
        return
    payload = push.build_activity_payload(
        PUSH_TYPE_NEW_LIKE, post, f"{liker.username} liked your post", post.caption)
    _send(author, payload, push_source_type(PUSH_TYPE_NEW_LIKE, _source(author, liker)))


def push_comment_like(comment_identifier, liker_id):
    """Tell a comment's author someone liked it (once per liker per window)."""
    comment = (Comment.objects
               .select_related('author', 'comment_thread__post__author')
               .filter(comment_identifier=comment_identifier).first())
    liker = get_user_model().objects.filter(pk=liker_id).first()
    if comment is None or liker is None or comment.hidden:
        return
    if not CommentLike.objects.filter(comment=comment, user=liker).exists():
        return
    author = comment.author
    post = comment.comment_thread.post
    # The commenter may have lost sight of the post since (it went private,
    # was hidden); then the push would point at something they cannot open.
    if not _may_notify(author, liker) or not can_view_post(post, author):
        return
    if not _first_like('comment', comment.comment_identifier, liker.pk):
        return
    payload = push.build_activity_payload(
        PUSH_TYPE_NEW_LIKE, post, f"{liker.username} liked your comment", comment.body)
    _send(author, payload, push_source_type(PUSH_TYPE_NEW_LIKE, _source(author, liker)))
