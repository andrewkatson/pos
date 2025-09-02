import uuid

from constants import NEVER_RUN
from django.contrib.auth.models import AbstractUser
from django.db import models
from django_cryptography.fields import encrypt


# Create your models here.

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
        ticket, created = cls.objects.get_or_create()
        return ticket.id


# The session information
class Session(models.Model):
    management_token = models.IntegerField(default=0)
    management_user = models.ForeignKey(
        PositiveOnlySocialUser, on_delete=models.CASCADE, default=PositiveOnlySocialUser.get_default_pk
    )


# The login cookie information
# From:
# https://stackoverflow.com/questions/244882/what-is-the-best-way-to-implement-remember-me-for-a-website
class LoginCookie(models.Model):
    series_identifier = models.IntegerField(default=0)
    # SHA256 hashed
    token = models.TextField(null=True)
    cookie_user = models.ForeignKey(PositiveOnlySocialUser, on_delete=models.CASCADE,
                                    default=PositiveOnlySocialUser.get_default_pk)
