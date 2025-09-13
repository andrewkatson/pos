import uuid

from .constants import NEVER_RUN
from django.contrib.auth.models import AbstractUser
from django.db import models


# The non-admin user class
class PositiveOnlySocialUser(AbstractUser):
    # The identifier used for a reset attempt for a password or username
    reset_id = models.IntegerField(default=0)
    # The identifier used for a verification report
    report_id = models.TextField(null=True)
    # The status of a verification report
    verification_report_status = models.TextField(default=NEVER_RUN)

    identity_is_verified = models.BooleanField(default=False)

    creation_time = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    updated_time = models.DateTimeField(auto_now=True, null=True, blank=True)

    id = models.UUIDField(default=uuid.uuid4,
                          primary_key=True,
                          unique=True,
                          editable=False)

    @classmethod
    def get_default_pk(cls):
        user, created = cls.objects.get_or_create()
        return user.id


# The session information
class Session(models.Model):
    # SHA256 hashed
    management_token = models.TextField(null=True)
    management_user = models.ForeignKey(
        PositiveOnlySocialUser, on_delete=models.CASCADE, default=PositiveOnlySocialUser.get_default_pk
    )
    ip = models.TextField(null=True)


# The login cookie information
# From:
# https://stackoverflow.com/questions/244882/what-is-the-best-way-to-implement-remember-me-for-a-website
class LoginCookie(models.Model):
    series_identifier = models.UUIDField(default=uuid.uuid4,
                                         primary_key=True,
                                         unique=True,
                                         editable=False)
    # SHA256 hashed
    token = models.TextField(null=True)
    cookie_user = models.ForeignKey(PositiveOnlySocialUser, on_delete=models.CASCADE,
                                    default=PositiveOnlySocialUser.get_default_pk)


# A post on the website
class Post(models.Model):
    post_identifier = models.UUIDField(default=uuid.uuid4,
                                       primary_key=True,
                                       unique=True,
                                       editable=False)
    image_url = models.TextField(null=True)
    caption = models.TextField(null=True)
    creation_time = models.DateTimeField(auto_now=True, null=True, blank=True)
    updated_time = models.DateTimeField(auto_now=True, null=True, blank=True)
    author = models.ForeignKey(PositiveOnlySocialUser, on_delete=models.CASCADE,
                               default=PositiveOnlySocialUser.get_default_pk)
    reported = models.BooleanField(default=False)
    reported_time = models.DateTimeField(auto_now=True, null=True, blank=True)
    reported_by_username = models.TextField(null=True)
    hidden = models.BooleanField(default=False)

    @classmethod
    def get_default_pk(cls):
        post, created = cls.objects.get_or_create()
        return post.post_identifier

# A report on a post
class PostReport(models.Model):
    reported_by_username = models.TextField(null=True)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, default=Post.get_default_pk)
    creation_time = models.DateTimeField(auto_now=True, null=True, blank=True)
    reason = models.TextField(null=True)

# A like on a post
class PostLike(models.Model):
    post_liker_username = models.TextField(null=True)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, default=PositiveOnlySocialUser.get_default_pk)

# A thread of comments on a post
class CommentThread(models.Model):
    comment_thread_identifier = models.UUIDField(default=uuid.uuid4,
                                                 primary_key=True,
                                                 unique=True,
                                                 editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, default=Post.get_default_pk)
    creation_time = models.DateTimeField(auto_now=True, null=True, blank=True)
    updated_time = models.DateTimeField(auto_now=True, null=True, blank=True)

    @classmethod
    def get_default_pk(cls):
        comment_thread, created = cls.objects.get_or_create()
        return comment_thread.comment_thread_identifier


# A comment on a post
class Comment(models.Model):
    comment_identifier = models.UUIDField(default=uuid.uuid4, primary_key=True, unique=True, editable=False)
    comment_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE, default=CommentThread.get_default_pk)
    body = models.TextField(null=True)
    author_username = models.TextField(null=True)
    creation_time = models.DateTimeField(auto_now=True, null=True, blank=True)
    updated_time = models.DateTimeField(auto_now=True, null=True, blank=True)

    hidden = models.BooleanField(default=False)

    @classmethod
    def get_default_pk(cls):
        comment, created = cls.objects.get_or_create()
        return comment.comment_identifier

# A report on a comment
class CommentReport(models.Model):
    reported_by_username = models.TextField(null=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, default=Comment.get_default_pk)
    creation_time = models.DateTimeField(auto_now=True, null=True, blank=True)
    reason = models.TextField(null=True)

# A like on a comment
class CommentLike(models.Model):
    comment_liker_username = models.TextField(null=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, default=Comment.get_default_pk)

# The response sent back to the client
class Response(models.Model):
    response_identifier = models.UUIDField(default=uuid.uuid4, primary_key=True, unique=True, editable=False)

    # Info related to the current user's session
    series_identifier = models.UUIDField(default=uuid.uuid4, primary_key=False, unique=True, editable=False)
    login_cookie_token = models.TextField(null=True)
    session_management_token = models.TextField(null=True)

    # Info related to a post
    post_identifier = models.UUIDField(default=uuid.uuid4, primary_key=False, unique=True, editable=False)
    image_url = models.TextField(null=True)
    caption = models.TextField(null=True)
    post_likes = models.IntegerField(default=0)
    post_creation_time = models.DateTimeField(auto_now=True, null=True, blank=True)
    post_updated_time = models.DateTimeField(auto_now=True, null=True, blank=True)

    # Info related to a post comment thread
    comment_thread_identifier = models.UUIDField(default=uuid.uuid4, primary_key=False, unique=True, editable=False)
    comment_thread_creation_time = models.DateTimeField(auto_now=True, null=True, blank=True)
    comment_thread_updated_time = models.DateTimeField(auto_now=True, null=True, blank=True)

    # Info related to a post comment
    comment_identifier = models.UUIDField(default=uuid.uuid4, primary_key=False, unique=True, editable=False)
    author_username = models.TextField(null=True)
    body = models.TextField(null=True)
    comment_creation_time = models.DateTimeField(auto_now=True, null=True, blank=True)
    comment_updated_time = models.DateTimeField(auto_now=True, null=True, blank=True)
    comment_likes = models.IntegerField(default=0)
