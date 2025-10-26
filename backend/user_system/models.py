import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from .constants import NEVER_RUN


# The model to explicitly define the "follow" relationship
class UserFollow(models.Model):
    user_from = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='following_set', on_delete=models.CASCADE)
    user_to = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='followers_set', on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user_from', 'user_to'], name='unique_followers')
        ]


# The non-admin user class (no changes needed here)
class PositiveOnlySocialUser(AbstractUser):
    reset_id = models.IntegerField(default=-1)
    report_id = models.TextField(null=True)
    verification_report_status = models.TextField(default=NEVER_RUN)
    identity_is_verified = models.BooleanField(default=False)
    creation_time = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_time = models.DateTimeField(auto_now=True, null=True, blank=True)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, unique=True, editable=False)
    following = models.ManyToManyField('self', through=UserFollow, through_fields=('user_from', 'user_to'),
                                       symmetrical=False, related_name='followers')

    def __str__(self):
        return self.username


# The session information (no changes needed here)
class Session(models.Model):
    management_token = models.TextField(null=True)
    management_user = models.ForeignKey(PositiveOnlySocialUser, on_delete=models.CASCADE)
    ip = models.TextField(null=True)


# The login cookie information (no changes needed here)
class LoginCookie(models.Model):
    series_identifier = models.UUIDField(default=uuid.uuid4, primary_key=True, unique=True, editable=False)
    token = models.TextField(null=True)
    cookie_user = models.ForeignKey(PositiveOnlySocialUser, on_delete=models.CASCADE)


# A post on the website
class Post(models.Model):
    post_identifier = models.UUIDField(default=uuid.uuid4, primary_key=True, unique=True, editable=False)
    image_url = models.TextField(null=True)
    caption = models.TextField(null=True)
    creation_time = models.DateTimeField(auto_now_add=True, null=True,
                                         blank=True)
    updated_time = models.DateTimeField(auto_now=True, null=True, blank=True)
    author = models.ForeignKey(PositiveOnlySocialUser, on_delete=models.CASCADE)
    hidden = models.BooleanField(default=False)


# A report on a post
class PostReport(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    creation_time = models.DateTimeField(auto_now_add=True, null=True,
                                         blank=True)
    reason = models.TextField(null=True)


# A like on a post
class PostLike(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'post'], name='unique_post_like')
        ]


# A thread of comments on a post
class CommentThread(models.Model):
    comment_thread_identifier = models.UUIDField(default=uuid.uuid4, primary_key=True, unique=True, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    creation_time = models.DateTimeField(auto_now_add=True, null=True,
                                         blank=True)
    updated_time = models.DateTimeField(auto_now=True, null=True, blank=True)


# A comment on a post
class Comment(models.Model):
    comment_identifier = models.UUIDField(default=uuid.uuid4, primary_key=True, unique=True, editable=False)
    comment_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE)
    body = models.TextField(null=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL,
                               on_delete=models.CASCADE)
    creation_time = models.DateTimeField(auto_now_add=True, null=True,
                                         blank=True)
    updated_time = models.DateTimeField(auto_now=True, null=True, blank=True)
    hidden = models.BooleanField(default=False)


# A report on a comment
class CommentReport(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE)
    creation_time = models.DateTimeField(auto_now_add=True, null=True,
                                         blank=True)
    reason = models.TextField(null=True)


# A like on a comment
class CommentLike(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'comment'], name='unique_comment_like')
        ]