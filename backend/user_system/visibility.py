from django.db.models import Count, Q

from .constants import (
    AUDIENCE_ALLOWED_CATEGORIES,
    BAN_TYPE_SHADOW,
    HIDDEN_REASON_CLASSIFIER_FINAL,
    POST_AUDIENCE_PUBLIC,
)
from .models import Comment, UserBan, UserFollow


# The viewer a signed-out visitor is represented by on the public share
# endpoints (issue #381). Every helper below already reads a `None` viewer
# correctly, so passing it through yields exactly the public rule without a
# parallel set of query builders:
#   - `Q(author=viewer)` becomes `author IS NULL`, which matches nothing (the FK
#     is non-null), so the "you always see your own content" branch never fires
#     and pending/hidden/report-hidden content stays invisible;
#   - `_audience_q` / `_audience_allows` fall through to public-audience only,
#     since an anonymous visitor is on nobody's follow list;
#   - `_privacy_q` / `privacy_admits` likewise admit only public accounts, since
#     an anonymous visitor follows nobody (issue #96);
#   - `_same_age_band_q` / `in_same_age_band` treat an unknown age as the adult
#     band, so a verified minor's post is never served to the open internet.
# Passed explicitly (rather than defaulting to `request.user`) so a signed-in
# browser hitting a public URL gets the same bytes a crawler would.
PUBLIC_VIEWER = None


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


def _privacy_q(viewer):
    """
    A Q over Post matching those whose author's privacy setting admits `viewer`
    (issue #96), ignoring the author-owns-it rule (handled separately). A public
    account's posts admit everyone; a private account's posts admit only its
    approved followers — viewers with a follow edge *to* the author. Note the
    direction: this is the viewer following the author, the reverse of the
    author-labels-viewer edge `_audience_q` reads, and a post from a private
    author has to pass both.

    The follower set is a subquery rather than a join so it adds no fan-out on
    top of `_audience_q`'s (issue #397). Pending follow requests live in their
    own table, so they never satisfy this.
    """
    admits = Q(author__is_private=False)
    if viewer is not None and getattr(viewer, 'is_authenticated', False):
        admits |= Q(author__in=UserFollow.objects.filter(user_from=viewer).values('user_to_id'))
    return admits


def privacy_admits(author, viewer):
    """Single-object mirror of _privacy_q: whether `author`'s privacy setting lets
    `viewer` see their posts (issue #96). The author always sees their own."""
    if not author.is_private or author == viewer:
        return True
    if viewer is None or not getattr(viewer, 'is_authenticated', False):
        return False
    return UserFollow.objects.filter(user_from=viewer, user_to=author).exists()


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
    shadow banned, whose audience admits them (issue #392), whose author is
    either public or followed by the viewer (issue #96), and whose author is
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
            & _privacy_q(viewer)
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

    Account privacy (issue #96) is deliberately *not* applied here: a private
    account's comment on someone else's post follows that comment's own
    audience, exactly like anyone else's. Comments on a private account's posts
    are still unreachable to non-followers, because every comment listing first
    checks the post itself with can_view_post.

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
    # A private account's posts reach only its approved followers (issue #96).
    if not privacy_admits(post.author, viewer):
        return False
    return _audience_allows(post, viewer)


def with_visible_follower_count(users, viewer):
    """Annotate `follower_count` on a user queryset, counting followers the way
    the profile header does (issue #398): a shadow-banned or cross-age-band
    follower is hidden from the follower list, so it doesn't count either. Keeps
    a ranked list (the most-followed board, issue #562) in step with the number
    each profile shows."""
    counted = (
        ~Q(followers_set__user_from__in=_shadow_banned_user_ids())
        & _same_age_band_q(viewer, 'followers_set__user_from')
    )
    return users.annotate(follower_count=Count('followers_set', filter=counted, distinct=True))


def same_age_band_users(users, viewer):
    """Narrow a queryset of users to those in the viewer's age band (issue
    #329) — the age half of searchable_users, for paths that must respect age
    segregation without the shadow-ban exclusion."""
    return users.filter(_same_age_band_q(viewer, ''))


def searchable_users(users, viewer):
    """Excludes shadow-banned users, and users outside the viewer's age band,
    from user search results (so adults cannot find underage accounts and vice
    versa)."""
    return users.exclude(pk__in=_shadow_banned_user_ids()).filter(_same_age_band_q(viewer, ''))
