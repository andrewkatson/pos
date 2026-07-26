from django.db.models import Exists, OuterRef, Q

from .constants import (
    AUDIENCE_ALLOWED_CATEGORIES,
    BAN_TYPE_SHADOW,
    HIDDEN_REASON_CLASSIFIER_FINAL,
    POST_AUDIENCE_PUBLIC,
)
from .models import Comment, UserBan, UserFollow


def _shadow_banned_user_ids():
    """User ids with a shadow ban currently in effect, usable as a subquery."""
    return UserBan.objects.active().filter(ban_type=BAN_TYPE_SHADOW).values_list('user_id', flat=True)


def _audience_q(viewer):
    """
    A Q over Post matching those whose audience admits `viewer`, ignoring the
    author-owns-it rule (handled separately, so the author always sees their
    own posts whatever the audience). Public posts admit everyone. A restricted
    post admits the viewer only when its author has a follow edge to the viewer
    whose category is close enough for that audience tier — a "friends" post
    reaches people the author labeled friend or family, a "family" post only
    family (issue #392).
    """
    admits = Q(audience=POST_AUDIENCE_PUBLIC)
    if viewer is not None and getattr(viewer, 'is_authenticated', False):
        for audience, categories in AUDIENCE_ALLOWED_CATEGORIES.items():
            edge = UserFollow.objects.filter(
                user_from=OuterRef('author'), user_to=viewer, category__in=categories)
            admits |= (Q(audience=audience) & Exists(edge))
    return admits


def visible_posts(posts, viewer):
    """
    Posts the viewer is allowed to see. A viewer always sees their own posts,
    so a shadow ban (and report-hiding) stays invisible to the author;
    everyone else only sees posts that are not hidden, whose author is not
    shadow banned, and whose audience admits them (issue #392). The author rule
    covers posts pending classification (hidden, author-only) without extra
    wiring. Final-rejection tombstones are excluded even for the author: the
    content is gone for good and clients learn the outcome via the status
    endpoint, not by rendering the post.
    """
    return posts.exclude(hidden_reason=HIDDEN_REASON_CLASSIFIER_FINAL).filter(
        Q(author=viewer) | (
            Q(hidden=False)
            & ~Q(author__in=_shadow_banned_user_ids())
            & _audience_q(viewer)
        )
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


def _audience_allows(post, viewer):
    """Single-object mirror of _audience_q: whether this post's audience admits
    the viewer (the author-owns-it rule is checked separately)."""
    if post.audience == POST_AUDIENCE_PUBLIC:
        return True
    categories = AUDIENCE_ALLOWED_CATEGORIES.get(post.audience, [])
    if not categories or viewer is None or not getattr(viewer, 'is_authenticated', False):
        return False
    return UserFollow.objects.filter(
        user_from=post.author, user_to=viewer, category__in=categories).exists()


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
    if UserBan.objects.active().filter(user=post.author, ban_type=BAN_TYPE_SHADOW).exists():
        return False
    return _audience_allows(post, viewer)


def searchable_users(users):
    """Excludes shadow-banned users from user search results."""
    return users.exclude(pk__in=_shadow_banned_user_ids())
