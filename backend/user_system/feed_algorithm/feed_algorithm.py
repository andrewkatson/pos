from django.db.models import Q, Count, F, ExpressionWrapper, FloatField, DurationField
from django.db.models.functions import Power, Now

def calculate_weights(qs, like_field, G=1.8, user=None):
    # 1. Annotate the like count for each post
    qs = qs.annotate(
        like_count=Count(like_field)
    )

    # 2. Annotate the age of the post in hours
    qs = qs.annotate(
        # 1. Calculate the duration between now and the creation time.
        #    This creates an 'interval' type in SQL.
        duration=ExpressionWrapper(
            Now() - F('creation_time'),
            output_field=DurationField()
        )
    ).annotate(
        # 2. Convert the duration (which is in microseconds) to hours.
        #    1 hour = 3,600,000,000 microseconds (3600 * 1,000,000)
        age_in_hours=ExpressionWrapper(
            F('duration') / 3600000000.0,
            output_field=FloatField()
        )
    )

    # 3. Annotate the final score using the hot rank formula
    qs = qs.annotate(
        score=ExpressionWrapper(
            (F('like_count') + 1) / Power(F('age_in_hours') + 2, G),
            output_field=FloatField()
        )
    )

    # 4. Filter out the user's own posts and order by the new score
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

    return calculate_weights(posts_model.objects.all(), 'postlike', G, user)


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

    return calculate_weights(comments, 'commentlike', G)