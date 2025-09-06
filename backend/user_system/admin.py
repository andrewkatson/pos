from django.contrib import admin

from django.contrib.auth.admin import UserAdmin
from .models import PositiveOnlySocialUser

admin.site.register(PositiveOnlySocialUser, UserAdmin)
