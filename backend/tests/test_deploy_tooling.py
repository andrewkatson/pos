"""Guards the deploy scripts against drifting from the app and the real host.

Nothing runs these shell scripts in CI, and a wrong value fails quietly: a queue
missing from status_check.sh is a backlog nobody sees, and a stale path skips the
queue check or breaks a deploy partway through. So these tests pin the facts the
scripts must agree with, as checked in.
"""

import re
from pathlib import Path

# The settings module directly, not django.conf.settings: this asserts on the
# config as checked in, and needs no configured Django (matching how
# test_logging_config.py imports it).
from pos_backend import settings as backend_settings

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"


def _read(name):
    return (TOOLS_DIR / name).read_text(encoding="utf-8")


def test_status_check_reports_every_queue_the_worker_drains():
    match = re.search(r'for name in \(([^)]*)\):', _read("status_check.sh"))
    assert match, "status_check.sh no longer loops over the worker's queues"

    assert re.findall(r'"([^"]+)"', match.group(1)) == [
        backend_settings.CLASSIFICATION_QUEUE_NAME,
        backend_settings.PUSH_QUEUE_NAME,
    ]


def test_setup_script_keeps_venv_and_env_out_of_the_backend_dir():
    script = _read("setup-django.sh")

    for stale_path in ("$BACKEND_DIR/venv", "$BACKEND_DIR/.env", "source venv/bin/activate"):
        assert stale_path not in script


def test_scripts_default_to_the_same_venv_and_env_paths():
    setup = _read("setup-django.sh")
    status = _read("status_check.sh")

    app_dir = re.search(r'^APP_DIR="([^"]+)"$', setup, re.MULTILINE).group(1)

    assert 'VENV_DIR="$APP_DIR/venv"' in setup
    assert 'ENV_FILE="$APP_DIR/.env"' in setup
    assert f'VENV_DIR="${{VENV_DIR:-{app_dir}/venv}}"' in status
    assert f'ENV_FILE="${{ENV_FILE:-{app_dir}/.env}}"' in status
