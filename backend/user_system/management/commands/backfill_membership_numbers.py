import logging

from django.core.management.base import BaseCommand
from django.db import transaction, IntegrityError
from django.db.models import F, Max

from user_system.models import PositiveOnlySocialUser

logger = logging.getLogger(__name__)

# Mirrors the one-time data migration (0022): update in bounded chunks so a
# large table isn't held in memory, and retry a chunk on the concurrency race
# where a live signup claims a number the chunk was about to write.
DEFAULT_BATCH_SIZE = 500
MAX_ATTEMPTS = 5


class Command(BaseCommand):
    help = (
        "Assign a sequential membership_number to every account that still has "
        "none (issue #198). New accounts are numbered at registration and the "
        "0022 data migration numbered pre-existing ones, so this is the repair "
        "path for the rare account whose registration-time assignment lost the "
        "bounded-retry race and was left null. Safe to re-run: it only touches "
        "null-numbered accounts and never renumbers an assigned one."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
            help=f"Rows updated (and committed) per chunk (default {DEFAULT_BATCH_SIZE}).",
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Report how many accounts would be numbered without writing anything.",
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        dry_run = options['dry_run']

        null_qs = PositiveOnlySocialUser.objects.filter(membership_number__isnull=True)

        if dry_run:
            count = null_qs.count()
            self.stdout.write(f"[dry-run] {count} account(s) would be numbered.")
            return

        numbered = 0
        while True:
            chunk = list(
                null_qs.order_by(F('creation_time').asc(nulls_first=True), 'id')[:batch_size]
            )
            if not chunk:
                break

            for attempt in range(MAX_ATTEMPTS):
                # Re-read the max each attempt so a concurrent registration's
                # number is accounted for; this is also what makes the command
                # safe to re-run.
                number = PositiveOnlySocialUser.objects.aggregate(
                    m=Max('membership_number'))['m'] or 0
                for user in chunk:
                    number += 1
                    user.membership_number = number
                try:
                    with transaction.atomic():
                        PositiveOnlySocialUser.objects.bulk_update(chunk, ['membership_number'])
                    numbered += len(chunk)
                    break
                except IntegrityError:
                    if attempt == MAX_ATTEMPTS - 1:
                        raise
                    for user in chunk:
                        user.membership_number = None

        logger.info("Backfilled membership numbers for %s account(s)", numbered)
        self.stdout.write(f"Numbered {numbered} account(s).")
