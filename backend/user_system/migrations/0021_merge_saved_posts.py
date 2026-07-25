# Merge the saved-posts leaf (0019_savedpost) with the profile-photo /
# text-formatting leaf that dev already merged into 0020.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('user_system', '0020_merge_20260723_1836'),
        ('user_system', '0019_savedpost'),
    ]

    operations = [
    ]
