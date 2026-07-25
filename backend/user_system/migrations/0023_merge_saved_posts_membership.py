# Merge the saved-posts leaf (0021_merge_saved_posts) with the membership-number
# leaf dev added (0022_backfill_membership_number).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('user_system', '0021_merge_saved_posts'),
        ('user_system', '0022_backfill_membership_number'),
    ]

    operations = [
    ]
