# Backfills membership_number for accounts that predate the field (issue #198).
# Existing members are numbered in join order — creation_time ascending, with id
# as a stable tie-break so the ordering is deterministic even for rows sharing a
# timestamp. Rows with a NULL creation_time (grandfathered/fixture accounts) are
# numbered first, before any timestamped account, so real join order is
# preserved. New members are numbered at registration time (see views.register).
from django.db import migrations, transaction, IntegrityError
from django.db.models import F, Max

# Update in bounded chunks so a large user table isn't held entirely in memory
# (or in one long-lived write transaction). Each chunk commits on its own.
BATCH_SIZE = 500
# Retries when a concurrent signup (the live register() also hands out max+1)
# claims a number this chunk was about to write, which would otherwise raise a
# UNIQUE violation. On conflict we re-read the max and rebuild the chunk.
MAX_ATTEMPTS = 5


def _next_chunk(User):
    return list(
        User.objects
        .filter(membership_number__isnull=True)
        .order_by(F('creation_time').asc(nulls_first=True), 'id')[:BATCH_SIZE]
    )


def backfill_membership_numbers(apps, schema_editor):
    User = apps.get_model('user_system', 'PositiveOnlySocialUser')

    # Process the still-null accounts a chunk at a time. Re-querying each round
    # naturally skips rows a concurrent signup numbered in the meantime.
    while True:
        chunk = _next_chunk(User)
        if not chunk:
            break

        for attempt in range(MAX_ATTEMPTS):
            # Number one past whatever's currently assigned, re-read every
            # attempt so a racing registration's number is accounted for. This
            # also makes a re-run of the whole migration safe.
            number = User.objects.aggregate(m=Max('membership_number'))['m'] or 0
            for user in chunk:
                number += 1
                user.membership_number = number
            try:
                with transaction.atomic():
                    User.objects.bulk_update(chunk, ['membership_number'])
                break
            except IntegrityError:
                if attempt == MAX_ATTEMPTS - 1:
                    raise
                for user in chunk:
                    user.membership_number = None


class Migration(migrations.Migration):
    # Non-atomic so each chunk commits independently: bounds memory/lock time and
    # lets a chunk be retried on the concurrency race above without rolling back
    # the whole backfill.
    atomic = False

    dependencies = [
        ('user_system', '0021_positiveonlysocialuser_membership_number'),
    ]

    operations = [
        # Reverse is a deliberate noop: by the time a rollback happens, accounts
        # registered after the backfill have their own numbers, and wiping every
        # membership_number to undo this migration would destroy that
        # non-recoverable data. Dropping the column (reversing 0021) is the way
        # to fully unwind the feature.
        migrations.RunPython(backfill_membership_numbers, migrations.RunPython.noop),
    ]
