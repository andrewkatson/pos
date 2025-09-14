from django.db.models import Q

def get_posts_weighted(username, posts_model):
    return posts_model.objects.filter(~Q(username=username))

def get_posts_weighted_for_user(username, posts_model):
    return posts_model.objects.filter(username=username)

def get_comment_threads_weighted_for_post(comment_threads):
    return comment_threads

def get_comments_weighted_for_thread(comments):
    # Return the comments ordered chronologically.
    return sorted(comments, key=lambda x: x.created_datetime, reverse=True)