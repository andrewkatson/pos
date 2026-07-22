from django.db.models import Q

from .constants import BAN_TYPE_SHADOW, HIDDEN_REASON_CLASSIFIER_FINAL
from .models import Comment, UserBan


def _shadow_banned_user_ids():
    """User ids with a shadow ban currently in effect, usable as a subquery."""
    return UserBan.objects.active().filter(ban_type=BAN_TYPE_SHADOW).values_list('user_id', flat=True)


def visible_posts(posts, viewer):
    """
    Posts the viewer is allowed to see. A viewer always sees their own posts,
    so a shadow ban (and report-hiding) stays invisible to the author;
    everyone else only sees posts that are not hidden and whose author is not
    shadow banned. The author rule covers posts pending classification
    (hidden, author-only) without extra wiring. Final-rejection tombstones are
    excluded even for the author: the content is gone for good and clients
    learn the outcome via the status endpoint, not by rendering the post.
    """
    return posts.exclude(hidden_reason=HIDDEN_REASON_CLASSIFIER_FINAL).filter(
        Q(author=viewer) | (Q(hidden=False) & ~Q(author__in=_shadow_banned_user_ids()))
    )


def visible_comments(comments, viewer):
    """Same visibility rule as visible_posts, for comments."""
    return comments.filter(
        Q(author=viewer) | (Q(hidden=False) & ~Q(author__in=_shadow_banned_user_ids()))
    )


def visible_comment_threads(threads, viewer):
    """
    Threads that contain at least one comment visible to the viewer. Filters
    via a subquery on thread ids rather than joining through comments so the
    like-count annotations applied later are not inflated by duplicate rows.
    """
    visible_thread_ids = visible_comments(
        Comment.objects.filter(comment_thread__in=threads), viewer
    ).values_list('comment_thread_id', flat=True).distinct()
    return threads.filter(pk__in=visible_thread_ids)


def can_view_post(post, viewer):
    """Visibility check for a single already-fetched post."""
    # A final-rejection tombstone is viewable by nobody, its author included
    # (matching visible_posts): the content is removed, and only the status
    # endpoint reports what happened to it.
    if post.hidden_reason == HIDDEN_REASON_CLASSIFIER_FINAL:
        return False
    if post.author == viewer:
        return True
    if post.hidden:
        return False
    return not UserBan.objects.active().filter(user=post.author, ban_type=BAN_TYPE_SHADOW).exists()


def searchable_users(users):
    """Excludes shadow-banned users from user search results."""
    return users.exclude(pk__in=_shadow_banned_user_ids())
