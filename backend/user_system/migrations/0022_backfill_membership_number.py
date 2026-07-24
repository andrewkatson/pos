# Backfills membership_number for accounts that predate the field (issue #198).
# Existing members are numbered in join order — creation_time ascending, with id
# as a stable tie-break so the ordering is deterministic even for rows sharing a
# timestamp. Rows with a NULL creation_time (grandfathered/fixture accounts) are
# numbered first, before any timestamped account, so real join order is
# preserved. New members are numbered at registration time (see views.register).
from django.db import migrations
from django.db.models import F


def backfill_membership_numbers(apps, schema_editor):
    User = apps.get_model('user_system', 'PositiveOnlySocialUser')
    ordered = User.objects.order_by(F('creation_time').asc(nulls_first=True), 'id')

    number = 0
    to_update = []
    for user in ordered.iterator():
        # Never renumber a member who already has one (re-run safety, and so a
        # future rerun after new signups doesn't clobber assigned numbers).
        if user.membership_number is not None:
            number = max(number, user.membership_number)
    for user in ordered.iterator():
        if user.membership_number is not None:
            continue
        number += 1
        user.membership_number = number
        to_update.append(user)

    if to_update:
        User.objects.bulk_update(to_update, ['membership_number'])


def unset_membership_numbers(apps, schema_editor):
    User = apps.get_model('user_system', 'PositiveOnlySocialUser')
    User.objects.update(membership_number=None)


class Migration(migrations.Migration):

    dependencies = [
        ('user_system', '0021_positiveonlysocialuser_membership_number'),
    ]

    operations = [
        migrations.RunPython(backfill_membership_numbers, unset_membership_numbers),
    ]
