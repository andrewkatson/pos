from django.db.models import Q

def get_posts_weighted(user, posts_model):
    return posts_model.objects.filter(~Q(author=user))

def get_posts_weighted_for_user(user, posts_model):
    return posts_model.objects.filter(author=user)

def get_comment_threads_weighted_for_post(comment_threads):
    return comment_threads

def get_comments_weighted_for_thread(comments):
    # Return the comments ordered chronologically.
    return sorted(comments, key=lambda x: x.created_datetime, reverse=True)