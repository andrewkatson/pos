"""Guards the shared-log-file contract from issue #484.

Every backend process (3 gunicorn workers, the classification worker, and each
oneshot sweep/cleanup run) appends to one `user_system.log`. A handler that
renames that file from inside the process breaks the other processes: the first
one to roll over renames the file, and the rest hit logging's "Already rolled
over" early return in `doRollover` — which returns *before* reopening the stream
— so they keep writing to the renamed file forever. In production that left the
live log holding nothing but `sweep_classifications` output, because the sweep is
the only process short-lived enough to reopen the path on every run.

The fix is `WatchedFileHandler` plus out-of-process rotation by logrotate. These
tests pin both halves: no rotating handler in the config, and the handler really
does follow the file to a new inode after an external rotate.
"""

import logging
import logging.handlers
import os

import pytest

# The settings module directly, not django.conf.settings: this asserts on the
# config as checked in, and needs no configured Django (matching how
# test_admin_middleware.py imports pos_backend.middleware).
from pos_backend import settings


def _file_handler():
    return settings.LOGGING['handlers']['file']


def test_file_handler_does_not_rotate_in_process():
    """A rotating handler here is the issue #484 bug, whatever its interval."""
    handler_class = _file_handler()['class']
    assert handler_class == 'logging.handlers.WatchedFileHandler'
    assert 'Rotating' not in handler_class


def test_file_handler_has_no_rotation_options():
    """Leftover rotation keys would mean a rotating handler is being reinstated."""
    handler = _file_handler()
    for key in ('when', 'interval', 'backupCount', 'maxBytes'):
        assert key not in handler


def test_app_and_django_loggers_write_to_the_file():
    """The request path logs under `user_system`; Django's own logs matter too."""
    for name in ('user_system', 'django'):
        assert 'file' in settings.LOGGING['loggers'][name]['handlers']


def test_verbose_format_identifies_the_process():
    """Interleaved lines from 4+ processes are unattributable without a pid."""
    assert '{process' in settings.LOGGING['formatters']['verbose']['format']


def _configured_handler(log_path):
    """Build whatever handler settings.py configures, pointed at log_path.

    Derived from the config rather than hard-coding the class, so these tests
    move with the setting instead of pinning it in two places.
    """
    handler_name = _file_handler()['class'].rpartition('.')[2]
    return getattr(logging.handlers, handler_name)(str(log_path))


def test_handler_reopens_when_its_open_file_is_no_longer_the_named_one(tmp_path):
    """The contract logrotate relies on, asserted without needing a real rename.

    Invalidating the recorded inode reproduces exactly the state a rotate leaves
    the handler in — holding a descriptor that is no longer what `baseFilename`
    points at — and the next record must reopen rather than keep writing into
    the detached file. This runs everywhere; the rename-based test below is the
    end-to-end version and is Linux-only.
    """
    handler = _configured_handler(tmp_path / 'user_system.log')
    # Stated up front so a stdlib rename of these internals reads as "update this
    # test", not as "the handler stopped reopening".
    assert hasattr(handler, 'reopenIfNeeded') and hasattr(handler, 'ino'), (
        'WatchedFileHandler no longer tracks the inode under these names; '
        'rewrite this test against whatever replaced them'
    )

    logger = logging.getLogger('user_system.tests.reopen')
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    try:
        logger.info('before')
        stream_before = handler.stream

        handler.ino = -1  # "the file I have open is not the file on disk"

        logger.info('after')
        assert handler.stream is not stream_before, (
            'handler kept writing to its stale descriptor — a rotate would '
            'strand this process, which is the issue #484 failure'
        )
    finally:
        logger.removeHandler(handler)
        handler.close()

    contents = (tmp_path / 'user_system.log').read_text()
    assert 'before' in contents and 'after' in contents


@pytest.mark.skipif(
    os.name == 'nt',
    reason="Windows cannot rename a file another handle has open, so the "
           "logrotate sequence this asserts cannot be simulated there. "
           "The deployment target is Linux and CI runs Linux.",
)
@pytest.mark.parametrize('recreate_after_rename', [True, False], ids=['create', 'mid-rotate'])
def test_handler_follows_the_file_after_an_external_rotate(tmp_path, recreate_after_rename):
    """End-to-end logrotate behaviour: records land in the live file, not the rotated one.

    Two points in the rotate sequence, because logrotate's `create` is two steps
    and a record can arrive between them:

    - `create` — rename, then the new file exists. This is the steady state the
      installed config produces, and what the README documents.
    - `mid-rotate` — rename, and a record arrives before the new file is created.
      The handler must create it rather than fall back to the rotated inode.

    A `TimedRotatingFileHandler` fails both: after the rename its stream still
    points at the rotated file, which is exactly how gunicorn's records went
    missing from the live log.
    """
    log_path = tmp_path / 'user_system.log'
    rotated_path = tmp_path / 'user_system.log.1'
    logger = logging.getLogger('user_system.tests.rotation')
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = _configured_handler(log_path)
    logger.addHandler(handler)
    try:
        logger.info('before-rotate')

        # Stand in for logrotate: rename the live file, leaving the handler's
        # descriptor on the rotated one, then `create` the replacement. Note it
        # is `create` and not `copytruncate` — truncating keeps the inode, so the
        # handler's check would never fire, which is why the README forbids it.
        os.rename(log_path, rotated_path)
        if recreate_after_rename:
            log_path.touch()

        logger.info('after-rotate')
    finally:
        logger.removeHandler(handler)
        handler.close()

    assert log_path.exists(), 'handler never reopened the rotated-away path'
    assert 'after-rotate' in log_path.read_text()
    assert 'after-rotate' not in rotated_path.read_text()
    assert 'before-rotate' in rotated_path.read_text()
