from django.db.models import Q

from .constants import BAN_TYPE_SHADOW, HIDDEN_REASON_CLASSIFIER_FINAL
from .models import Comment, UserBan


def _shadow_banned_user_ids():
    """User ids with a shadow ban currently in effect, usable as a subquery."""
    return UserBan.objects.active().filter(ban_type=BAN_TYPE_SHADOW).values_list('user_id', flat=True)


def is_minor(user):
    """Whether an account is a verified minor (16 or 17).

    Under-16s are refused at registration and identity verification (issue
    #337), so any identity-verified non-adult is necessarily 16 or 17. An
    account that never verified an age is *not* treated as a minor here: its age
    is unknown and it stays in the general (adult) pool. The segregation exists
    to keep adults away from *known* minors.
    """
    return bool(getattr(user, 'identity_is_verified', False) and not getattr(user, 'is_adult', False))


def in_same_age_band(user_a, user_b):
    """Whether two accounts may see and interact with each other on age grounds.

    Verified minors form one band and everyone else (adults plus unverified
    accounts) forms the other; the two bands are mutually invisible so an adult
    never sees an underage account and vice versa (issue #329).
    """
    return is_minor(user_a) == is_minor(user_b)


def _same_age_band_q(viewer, prefix):
    """Q keeping only rows whose related account is in the viewer's age band.

    `prefix` is the relation to the account being filtered — '' for a queryset
    of users, or e.g. 'author' for posts/comments. When the viewer is a minor
    only minors' rows survive; otherwise minors' rows are excluded.
    """
    field = f'{prefix}__' if prefix else ''
    minor_q = Q(**{f'{field}identity_is_verified': True, f'{field}is_adult': False})
    return minor_q if is_minor(viewer) else ~minor_q


def visible_posts(posts, viewer):
    """
    Posts the viewer is allowed to see. A viewer always sees their own posts,
    so a shadow ban (and report-hiding) stays invisible to the author;
    everyone else only sees posts that are not hidden, whose author is not
    shadow banned, and whose author is in the viewer's age band (so adults and
    underage accounts never see each other's posts). The author rule covers
    posts pending classification (hidden, author-only) without extra wiring.
    Final-rejection tombstones are excluded even for the author: the content is
    gone for good and clients learn the outcome via the status endpoint, not by
    rendering the post.
    """
    return posts.exclude(hidden_reason=HIDDEN_REASON_CLASSIFIER_FINAL).filter(
        Q(author=viewer) | (
            Q(hidden=False)
            & ~Q(author__in=_shadow_banned_user_ids())
            & _same_age_band_q(viewer, 'author')
        )
    )


def visible_comments(comments, viewer):
    """Same visibility rule as visible_posts, for comments."""
    return comments.filter(
        Q(author=viewer) | (
            Q(hidden=False)
            & ~Q(author__in=_shadow_banned_user_ids())
            & _same_age_band_q(viewer, 'author')
        )
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
    # Adults and underage accounts never see each other's posts (issue #329).
    if not in_same_age_band(post.author, viewer):
        return False
    return not UserBan.objects.active().filter(user=post.author, ban_type=BAN_TYPE_SHADOW).exists()


def searchable_users(users, viewer):
    """Excludes shadow-banned users, and users outside the viewer's age band,
    from user search results (so adults cannot find underage accounts and vice
    versa)."""
    return users.exclude(pk__in=_shadow_banned_user_ids()).filter(_same_age_band_q(viewer, ''))
