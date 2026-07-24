# Backfills membership_number for accounts that predate the field (issue #198).
# Existing members are numbered in join order — creation_time ascending, with id
# as a stable tie-break so the ordering is deterministic even for rows sharing a
# timestamp. Rows with a NULL creation_time (grandfathered/fixture accounts) are
# numbered first, before any timestamped account, so real join order is
# preserved. New members are numbered at registration time (see views.register).
from django.db import migrations
from django.db.models import F, Max


def backfill_membership_numbers(apps, schema_editor):
    User = apps.get_model('user_system', 'PositiveOnlySocialUser')

    # Start numbering one past whatever's already assigned, so a re-run (or a run
    # after some accounts were numbered at registration) never clobbers or
    # reuses an existing number. Only the still-null accounts are touched.
    number = User.objects.aggregate(m=Max('membership_number'))['m'] or 0
    unnumbered = (
        User.objects
        .filter(membership_number__isnull=True)
        .order_by(F('creation_time').asc(nulls_first=True), 'id')
    )

    to_update = []
    for user in unnumbered.iterator():
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
