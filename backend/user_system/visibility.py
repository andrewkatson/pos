from django.db.models import Q

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
            # Join the author's outgoing follow edges (following_set) and keep
            # rows whose edge points at this viewer. A plain Q join keeps the
            # whole filter combinable with the other Q terms in visible_posts.
            #
            # NOTE: this DOES fan out. `following_set` is multi-valued, and the
            # OR with the author-owns-it branch in visible_posts leaves the join
            # unrestricted for the author's own posts (viewer == author), so a
            # post is emitted once per follow edge its author has. visible_posts
            # must therefore .distinct() to collapse the duplicates (issue #397).
            admits |= Q(
                audience=audience,
                author__following_set__user_to=viewer,
                author__following_set__category__in=categories,
            )
    return admits


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
    shadow banned, whose audience admits them (issue #392), and whose author is
    in the viewer's age band (so adults and underage accounts never see each
    other's posts). The author rule covers posts pending classification (hidden,
    author-only) without extra wiring. Final-rejection tombstones are excluded
    even for the author: the content is gone for good and clients learn the
    outcome via the status endpoint, not by rendering the post.
    """
    return posts.exclude(hidden_reason=HIDDEN_REASON_CLASSIFIER_FINAL).filter(
        Q(author=viewer) | (
            Q(hidden=False)
            & ~Q(author__in=_shadow_banned_user_ids())
            & _audience_q(viewer)
            & _same_age_band_q(viewer, 'author')
        )
    # .distinct() collapses the audience-join fan-out from _audience_q: on the
    # author-owns-it branch the join over the author's outgoing follow edges is
    # unrestricted, so a viewer's own posts come back once per account they
    # follow — N copies on your own profile where N = accounts you follow
    # (issue #397). Plain row-level distinct is correct for every caller: the
    # duplicated rows are identical across all selected columns (the audience
    # edge is unique per (author, viewer)), and the callers' own orderings and
    # annotations (feed weight, -creation_time, saved posts' -saved_time) are
    # single-valued per post, so none of them split a post back into rows that
    # distinct would keep.
    ).distinct()


def _labeled_author_ids(viewer, category):
    """User ids the viewer has labeled with exactly `category` on their outgoing
    follow edges — the "show me my family" set behind the followed-feed toggle,
    reused for the comment toggle (issue #445)."""
    return UserFollow.objects.filter(
        user_from=viewer, category=category).values_list('user_to_id', flat=True)


def visible_comments(comments, viewer, category=None):
    """Same visibility rule as visible_posts, for comments (issue #392/#445): a
    viewer always sees their own comments, and otherwise only comments that are
    not hidden, whose author is not shadow banned, whose audience admits them,
    and whose author is in the viewer's age band.

    An optional `category` narrows the result to comments whose author the viewer
    labeled with exactly that relationship category — the followed-feed toggle
    applied to comments. Like the feed filter it is an exact-category match (and
    so naturally drops the viewer's own comments, since you do not follow
    yourself), independent of how the comments' own audiences nest.
    """
    visible = comments.filter(
        Q(author=viewer) | (
            Q(hidden=False)
            & ~Q(author__in=_shadow_banned_user_ids())
            & _audience_q(viewer)
            & _same_age_band_q(viewer, 'author')
        )
    # .distinct() collapses the audience-join fan-out from _audience_q exactly as
    # in visible_posts: the author-owns-it branch leaves the follow-edge join
    # unrestricted, so a viewer's own comments would otherwise come back once per
    # account they follow.
    ).distinct()
    if category:
        visible = visible.filter(author__in=_labeled_author_ids(viewer, category))
    return visible


def visible_comment_threads(threads, viewer, category=None):
    """
    Threads that contain at least one comment visible to the viewer. Filters
    via a subquery on thread ids rather than joining through comments so the
    like-count annotations applied later are not inflated by duplicate rows.

    An optional `category` applies the followed-feed toggle: a thread survives
    only when it has a visible comment by an author the viewer labeled with
    exactly that category.
    """
    visible_thread_ids = visible_comments(
        Comment.objects.filter(comment_thread__in=threads), viewer, category
    ).values_list('comment_thread_id', flat=True).distinct()
    return threads.filter(pk__in=visible_thread_ids)


def _audience_allows(content, viewer):
    """Single-object mirror of _audience_q: whether this post's or comment's
    audience admits the viewer (the author-owns-it rule is checked separately)."""
    if content.audience == POST_AUDIENCE_PUBLIC:
        return True
    categories = AUDIENCE_ALLOWED_CATEGORIES.get(content.audience, [])
    if not categories or viewer is None or not getattr(viewer, 'is_authenticated', False):
        return False
    return UserFollow.objects.filter(
        user_from=content.author, user_to=viewer, category__in=categories).exists()


def audience_admits(content, viewer):
    """Whether a single post's or comment's audience tier admits the viewer
    (issue #392/#445), ignoring hidden/ban/age — callers check those separately.
    The author is always admitted to their own content.

    Used to gate interactions with a comment reached by a known id (like,
    report, and their retractions): a comment whose audience excludes the caller
    is treated as absent, the same way a cross-age-band comment already is. It is
    audience-only on purpose — report retraction legitimately targets an
    already-hidden comment, so a full visibility check (which rejects hidden
    content) would break that flow."""
    if content.author == viewer:
        return True
    return _audience_allows(content, viewer)


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
    # Adults and underage accounts never see each other's posts (issue #329).
    if not in_same_age_band(post.author, viewer):
        return False
    return _audience_allows(post, viewer)


def searchable_users(users, viewer):
    """Excludes shadow-banned users, and users outside the viewer's age band,
    from user search results (so adults cannot find underage accounts and vice
    versa)."""
    return users.exclude(pk__in=_shadow_banned_user_ids()).filter(_same_age_band_q(viewer, ''))
