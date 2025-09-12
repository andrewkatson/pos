from django.db.models import Q

def get_posts_weighted(username, posts_model):
    # TODO: Do some algorithm around picking up posts weighted by time posted and likes
    # For now we just get every post not by the user
    return posts_model.objects.filter(~Q(username=username))
