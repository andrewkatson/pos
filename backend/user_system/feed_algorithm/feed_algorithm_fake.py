from django.db.models import Q

def get_posts_weighted(username, posts_model):
    return posts_model.objects.filter(~Q(username=username))