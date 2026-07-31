from django.db.models import (
    Q, Count, F, ExpressionWrapper, FloatField, DurationField,
    IntegerField, OuterRef, Subquery,
)
from django.db.models.functions import Power, Now, Coalesce
from django.db.models import Func
import logging

from ..constants import INTEREST_BOOST

logger = logging.getLogger(__name__)


class DurationToSeconds(Func):
    """Converts a DurationField expression to elapsed seconds as a float.

    PostgreSQL stores durations as interval; EXTRACT(EPOCH FROM ...) is needed
    to get a numeric value.  SQLite stores durations as microseconds (integer),
    so a plain division suffices.
    """
    arity = 1
    output_field = FloatField()

    def as_postgresql(self, compiler, connection, **extra_context):
        return self.as_sql(
            compiler, connection,
            template='EXTRACT(EPOCH FROM %(expressions)s)',
            **extra_context,
        )

    def as_sqlite(self, compiler, connection, **extra_context):
        return self.as_sql(
            compiler, connection,
            template='(%(expressions)s / 1000000.0)',
            **extra_context,
        )


def calculate_weights(qs, like_field, G=1.8, user=None, interest_category_ids=None):
    logger.debug(f"Calculating feed weights with gravity G={G}")
    # 1. Annotate the like count for each post.
    #    distinct=True is load-bearing, not decoration: the caller layers
    #    visible_posts() on top of this queryset, whose audience filter LEFT
    #    JOINs the author's following_set (see visibility._audience_q, which
    #    documents that it fans out). Without distinct, a plain COUNT counts
    #    each like once per follow edge the author has — a post with one like
    #    from an author following 200 people scored as if it had 200 — so
    #    ranking quietly favored authors who follow a lot of people. The
    #    .distinct() visible_posts applies collapses duplicate *rows*; it does
    #    not undo an aggregate computed over them.
    qs = qs.annotate(
        like_count=Count(like_field, distinct=True)
    )

    # 2. Annotate the age of the post in hours as a pure float.
    #    DurationToSeconds handles the DB difference: PostgreSQL keeps interval
    #    arithmetic as interval, so EXTRACT(EPOCH FROM ...) is required; SQLite
    #    stores durations as microseconds integers, so dividing by 1e6 suffices.
    qs = qs.annotate(
        age_in_hours=ExpressionWrapper(
            DurationToSeconds(
                ExpressionWrapper(Now() - F('creation_time'), output_field=DurationField())
            ) / 3600.0,
            output_field=FloatField()
        )
    )

    # 3. The base "hot" score.
    base_score = ExpressionWrapper(
        (F('like_count') + 1) / Power(F('age_in_hours') + 2.0, G),
        output_field=FloatField()
    )

    # 3b. Personalization (issues #446/#35): boost posts that share interest
    #     buckets with the viewer. The hot score is multiplied by
    #     (1 + INTEREST_BOOST * overlap), linear in the number of shared buckets
    #     (NOT (1 + INTEREST_BOOST) per bucket — no exponential compounding), so
    #     a fresh, liked, on-topic post rises while an ancient on-topic post
    #     still decays — the boost scales the rank, it doesn't replace it. When
    #     the viewer has no interests this branch is skipped entirely, so no
    #     boost is applied and the score is the plain hot rank. (Not identical
    #     to what shipped before this feature, though: the distinct fix above
    #     corrects like counts the audience join used to inflate, so scores can
    #     move for posts by authors who follow a lot of people.)
    #
    #     The match count comes from a correlated Subquery over the M2M through
    #     table rather than a second Count annotation: two Counts over different
    #     multi-valued relations would multiply each other's join rows and
    #     corrupt like_count. The subquery counts join rows for this post whose
    #     category is one the viewer wants, coalesced to 0.
    if interest_category_ids:
        through = qs.model.interest_categories.through
        matched = through.objects.filter(
            post_id=OuterRef('pk'),
            interestcategory_id__in=list(interest_category_ids),
        ).order_by().values('post_id').annotate(c=Count('*')).values('c')[:1]
        qs = qs.annotate(
            interest_matches=Coalesce(
                Subquery(matched, output_field=IntegerField()), 0
            )
        )
        score = ExpressionWrapper(
            base_score * (1.0 + INTEREST_BOOST * F('interest_matches')),
            output_field=FloatField()
        )
    else:
        score = base_score

    # 4. Annotate the final score, filter out the user's own posts, and order.
    qs = qs.annotate(score=score)
    if user:
        return qs.filter(~Q(author=user)).order_by('-score')
    else:
        # Unless no user is provided
        return qs.order_by('-score')


def get_posts_weighted(user, posts_model):
    """
    Gets all posts NOT by the user, ordered by a "hot" ranking algorithm.
    Algorithm: Score = (Likes + 1) / (Age_in_Hours + 2)^G
    """
    # Gravity constant. Higher value = time matters more.
    G = 1.8
    logger.debug("Ranking all posts for feed via hot algorithm")
    # The viewer's interest buckets personalize the ranking (issues #446/#35).
    # Anonymous or interest-less viewers get None -> the plain hot rank.
    interest_category_ids = None
    if user is not None and getattr(user, 'is_authenticated', False):
        interest_category_ids = list(user.interest_categories.values_list('id', flat=True))
    return calculate_weights(posts_model.objects.all(), 'postlike', G, user, interest_category_ids)


def get_posts_weighted_for_user(user, posts_model):
    """
    Gets all posts BY the user.
    For a user's own profile, "weighting" is almost always
    reverse-chronological (newest first). A "hot" rank is not useful.
    """
    return posts_model.objects.filter(author=user).order_by('-creation_time')


def get_comment_threads_weighted_for_post(comment_threads):
    """
    Ranks comment threads based on the "hotness" of the thread itself.
    The "Likes" for a thread is the SUM of all likes on all its comments.
    Algorithm: Score = (Total_Comment_Likes + 1) / (Thread_Age_in_Hours + 2)^G

    Assumes 'comment_threads' is a queryset (e.g., CommentThread.objects.filter(...))
    """
    # Gravity constant. Higher value = time matters more.
    G = 1.8
    logger.debug("Ranking comment threads for post via hot algorithm")
    return calculate_weights(comment_threads, 'comment__commentlike', G)

def get_comments_weighted_for_thread(comments):
    """
    Ranks individual comments within a thread using the "hot" algorithm.

    Assumes 'comments' is a queryset (e.g., Comment.objects.filter(...))
    Your original code sorted in Python, which is inefficient. This does
    all the work in the database.

    If you truly just want chronological, use:
    return comments.order_by('-creation_time')
    """
    G = 1.8
    logger.debug("Ranking single comments within thread via hot algorithm")
    return calculate_weights(comments, 'commentlike', G)