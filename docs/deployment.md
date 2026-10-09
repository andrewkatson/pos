# Deploying and restarting services

The Django API runs on an EC2 host provisioned by `backend/tools/setup-django.sh`
(gunicorn behind nginx; the website is a separate S3 + CloudFront SPA published
with `website/deploy-web.sh`). Beyond gunicorn, the backend relies on several
**async background services**, all installed as systemd units by that script:

| Unit | Kind | What it does | Enabled when |
| --- | --- | --- | --- |
| `gunicorn.service` | long-lived | Serves the API (WSGI). | always |
| `classification-worker.service` | long-lived | RQ worker draining the async post/profile-photo moderation queue (`manage.py classification_worker`). | `REDIS_URL` set (queue mode) |
| `sweep-classifications.timer` | timer (15 min) | `manage.py sweep_classifications` — re-enqueues stuck-pending items and purges tombstones. | always |
| `cleanup-orphan-images.timer` | timer (daily) | `manage.py cleanup_orphan_images` — reclaims orphaned S3 images. | always |

**Restart every long-lived process on every deploy.** Both gunicorn *and* the
classification worker cache the imported source in memory, so a `git pull` alone
does not pick up new code. In issue #399 a profile photo was stuck "in review"
forever because the prod worker had been running since **before** the
profile-photo feature was committed and was never restarted after deploy — its
cached `user_system.tasks` lacked `classify_profile_photo`, so every job failed
on import and silently stranded classifications. The generated `~/update-app.sh`
therefore restarts gunicorn **and** the worker and reloads the timers after
migrating and collecting static files; use it (or replicate its steps) for every
by-hand deploy. (The timers run oneshot services that re-exec the new code on
their next fire, so they self-heal, but the units are reloaded in case their
definitions changed.)

**Queue vs eager mode.** `REDIS_URL` (set via `--redis-url`, written to
`backend/.env`) flips the app from eager in-process classification to queue mode.
Only in queue mode is a worker needed, so `setup-django.sh` installs
`classification-worker.service` unconditionally but only **enables** it when
`REDIS_URL` is present. To switch an existing eager host to queue mode: add
`REDIS_URL` to `.env`, restart gunicorn, then
`sudo systemctl enable --now classification-worker`.

**`.env` and systemd.** `manage.py` loads `.env` via `python-dotenv`, but
`wsgi.py` does not — so every systemd unit points at the `.env` with
`EnvironmentFile=$BACKEND_DIR/.env` (i.e. `backend/.env`, the same file
`setup-django.sh` generates), or the service would start without
`REDIS_URL`/DB/AWS credentials.

`backend/tools/status_check.sh` reports the health of all of the above — gunicorn,
nginx, the classification worker (active/enabled, or "stranding!" if enabled but
dead), the two timers (last/next run), and best-effort `classification` queue
depth — so a silently dead worker is visible at a glance.

## gunicorn tuning, and the keepalive that must beat the load balancer

`backend/gunicorn.conf.py` holds the gunicorn settings that are the same on every
host. **Nothing passes it with `-c`** — gunicorn auto-loads `./gunicorn.conf.py`
from its working directory, and the systemd unit's `WorkingDirectory` is
`backend/`. Reading the unit alone gives no hint the file exists, so look for it
before concluding a setting "isn't configured anywhere".

Command-line flags in `ExecStart` override the file, so the split is: per-host
wiring (`--bind`, `--workers`) in the unit, everything shared in the file.

The one setting there is `keepalive = 75`, and it needs to stay **above the ALB's
idle timeout** (60s). The API is reached through CloudFront → ALB → gunicorn, and
the ALB pools upstream connections. If gunicorn's keepalive is the shorter of the
two, the ALB reuses a connection gunicorn has already begun closing, the request
lands in a socket being torn down, and the client gets a **502** — intermittently,
under load, in a way that looks like an application fault rather than a timeout
mismatch. Gunicorn's default is 2 seconds, so this is not a value to leave unset.

Two ways it silently reverts to 2 seconds:

- **Misspelling it.** The config-file setting is `keepalive`; the *command-line
  flag* is `--keep-alive`. Gunicorn's loader skips names it does not recognize,
  so `keep_alive = 5` in this file is accepted, ignored, and never warned about.
- **Raising the ALB's idle timeout above 75** without raising this to match.

Check the ALB's current value with:

```bash
aws elbv2 describe-load-balancer-attributes --region us-east-2 \
    --load-balancer-arn <arn> \
    --query "Attributes[?Key=='idle_timeout.timeout_seconds'].Value" --output text
```

Changing this file needs only a `sudo systemctl restart gunicorn`, not a deploy.

## Backend logs (issue #484)

Every unit in the table above logs to the **same** file,
`backend/logs/user_system.log`, and also to stdout (so `journalctl -u gunicorn -f`
and `journalctl -u classification-worker -f` carry the same records).

Because the file is shared, **rotation happens out-of-process, via logrotate** —
`settings.py` configures `logging.handlers.WatchedFileHandler`, which reopens the
path whenever the inode changes. Nothing inside Django renames the log.

That is a fix, not a preference. The old config gave every process its own
`TimedRotatingFileHandler`. At the first log record after midnight one process
renamed `user_system.log` to `user_system.log.<date>` and opened a fresh file;
every other process then found the dated file already present and took logging's
"Already rolled over" early return in `doRollover`, which returns *before*
reopening the stream — so it kept its descriptor on the renamed file
indefinitely. The long-lived gunicorn workers ended up pinned to a rotated file,
while `sweep-classifications` — a new process every 15 minutes, opening the log
by path — always got the live one. The symptom was a `user_system.log` containing
nothing but sweep output: logins and every other request were still being logged,
just appended to a `user_system.log.<date>` file nobody was tailing.

Two rules follow, and breaking either brings the bug back:

- **Never configure a rotating handler in `LOGGING`.** `backend/tests/test_logging_config.py`
  fails the build if one reappears, and covers the reopen-on-rotate behavior.
- **The logrotate config must use `create`, never `copytruncate`.** Truncating
  reuses the inode, so `WatchedFileHandler`'s check never fires and every process
  keeps appending past the truncation point.

`setup-django.sh` installs `/etc/logrotate.d/smiling-social-django` (daily,
`rotate 7`). **Hosts provisioned before this change do not have it** — the old
config globbed `$APP_DIR/*.log`, a path nothing writes to, so it rotated nothing,
and `~/update-app.sh` does not install logrotate configs. Without the new one the
log now grows unbounded, so run this once per existing host:

```bash
sudo apt install -y logrotate
# Modern Ubuntu schedules logrotate with a systemd timer. Older images have no
# such unit and run /etc/cron.daily/logrotate instead, where this reports
# "Unit logrotate.timer not found" and the '|| true' keeps that harmless.
sudo systemctl enable --now logrotate.timer || true
sudo tee /etc/logrotate.d/smiling-social-django > /dev/null <<'EOF'
/var/www/smiling-social/pos/backend/logs/user_system.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    su ubuntu www-data
    create 0640 ubuntu www-data
}
EOF
sudo rm -f /etc/logrotate.d/gunicorn
sudo logrotate --debug /etc/logrotate.d/smiling-social-django
```

The install and `enable --now` are usually no-ops — Ubuntu's server images ship
logrotate already scheduled — but nothing in Django rotates this file any more,
so both are worth asserting rather than assuming. A missing binary and an
unscheduled logrotate fail the same silent way as a bad config: no rotation, no
symptom, until the disk fills. Either scheduler is fine; `setup-django.sh`
accepts `logrotate.timer` or `/etc/cron.daily/logrotate` and only warns when
neither is present.

Then restart gunicorn and the worker so they pick up the new handler. The
`user_system.log.<date>` files the old handler left behind are not managed by
logrotate's naming — delete them by hand once you have read anything you need
out of them (they hold the request logs that went missing).
