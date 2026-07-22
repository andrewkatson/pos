import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from user_system.models import TwoFactorChallenge

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Delete two-factor login challenges whose expiry has passed. Challenges "
        "are cleaned up opportunistically when the same user logs in again, but a "
        "login that is started and abandoned leaves a row behind until then — and "
        "forever for a user who never returns. This sweep keeps the table bounded "
        "and removes dead credentials promptly. Safe to run on a schedule; it only "
        "touches rows the login flow would already refuse."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Report how many rows would be deleted without deleting anything.",
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Uses the index on `expires`.
        expired = TwoFactorChallenge.objects.filter(expires__lt=timezone.now())
        count = expired.count()

        if dry_run:
            self.stdout.write(f"Would delete {count} expired two-factor challenge(s).")
            return

        if count:
            expired.delete()
            logger.info(f"Deleted {count} expired two-factor challenge(s).")

        self.stdout.write(f"Deleted {count} expired two-factor challenge(s).")
