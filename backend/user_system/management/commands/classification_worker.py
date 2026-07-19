import os

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Run the RQ worker that consumes the async post-classification queue "
        "(issue #282). Requires REDIS_URL; run one (or more) of these as a "
        "long-lived service next to gunicorn. Without a running worker, posts "
        "created while REDIS_URL is set stay pending until the "
        "sweep_classifications command re-enqueues them."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--burst', action='store_true',
            help="Process the jobs currently queued, then exit (useful for cron/testing).",
        )

    def handle(self, *args, **options):
        redis_url = os.environ.get('REDIS_URL')
        if not redis_url:
            raise CommandError(
                "REDIS_URL is not set. Without it the app classifies eagerly "
                "in-process and there is no queue to consume.")

        # Imported here so the command is importable (e.g. by --help or test
        # collection) even where rq is not installed.
        from redis import Redis
        from rq import Queue, Worker

        from django.conf import settings

        connection = Redis.from_url(redis_url)
        queue = Queue(settings.CLASSIFICATION_QUEUE_NAME, connection=connection)
        worker = Worker([queue], connection=connection)
        self.stdout.write(f"Starting classification worker on queue '{queue.name}'...")
        worker.work(burst=options['burst'])
