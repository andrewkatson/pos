#!/bin/bash

# Health check for the smiling.social stack.
#   * API  : gunicorn behind nginx on THIS EC2 (CloudFront -> ALB -> nginx:80).
#   * Website: static SPA in S3 behind CloudFront (NOT served from this host) —
#     checked end-to-end over HTTPS only.
# Override the hosts/socket if yours differ.
DOMAIN="${DOMAIN:-api.smiling.social}"
FRONTEND_DOMAIN="${FRONTEND_DOMAIN:-smiling.social}"
SOCKET="${SOCKET:-/var/www/smiling-social/gunicorn.sock}"
# Django project root (manage.py + venv + .env). Matches setup-django.sh's
# nested layout; used to read REDIS_URL and inspect the classification queue.
BACKEND_DIR="${BACKEND_DIR:-/var/www/smiling-social/pos/backend}"

echo "=== Checking Gunicorn ==="
sudo systemctl status gunicorn --no-pager

echo -e "\n=== Checking Nginx ==="
sudo systemctl status nginx --no-pager

echo -e "\n=== Checking Socket ==="
ls -l "$SOCKET"

echo -e "\n=== Checking Nginx Ports ==="
# ss is present on modern Ubuntu (netstat often isn't); fall back if needed.
(sudo ss -tlnp 2>/dev/null || sudo netstat -tlnp 2>/dev/null) | grep nginx

echo -e "\n=== Recent Gunicorn Logs ==="
sudo journalctl -u gunicorn -n 10 --no-pager

echo -e "\n=== Checking Classification Worker (async moderation) ==="
# The long-lived RQ worker that drains the async post/profile-photo queue. A dead
# or never-restarted worker strands classifications in pending forever (issue
# #399), so surface its state explicitly. It only exists in queue mode; on an
# eager-mode host (no REDIS_URL) the unit is installed but intentionally disabled.
if [ -f /etc/systemd/system/classification-worker.service ]; then
  if systemctl is-enabled --quiet classification-worker 2>/dev/null; then
    if sudo systemctl is-active --quiet classification-worker; then
      echo "classification-worker: ACTIVE + enabled"
    else
      echo "classification-worker: ENABLED but NOT running — classifications are stranding!"
    fi
    sudo systemctl status classification-worker --no-pager --lines=5
  else
    echo "classification-worker: installed but DISABLED (eager mode / no REDIS_URL)."
  fi
else
  echo "classification-worker.service NOT installed — re-run setup-django.sh."
fi

echo -e "\n=== Checking Async Timers (sweep + orphan cleanup) ==="
# list-timers shows LAST/NEXT run so a timer that has silently stopped firing is
# visible. --all includes timers whose unit is inactive between runs.
sudo systemctl list-timers --all --no-pager \
  'sweep-classifications.timer' 'cleanup-orphan-images.timer' \
  || echo "Could not list timers."
for t in sweep-classifications.timer cleanup-orphan-images.timer; do
  if [ -f "/etc/systemd/system/$t" ]; then
    state=$(systemctl is-enabled "$t" 2>/dev/null || echo "unknown")
    echo "$t: $state"
  else
    echo "$t: NOT installed — re-run setup-django.sh."
  fi
done

echo -e "\n=== Classification queue depth (best-effort) ==="
# Reuse python-dotenv (a backend dependency, exactly how manage.py loads .env) to
# read REDIS_URL and report how many jobs are waiting/failed. Skipped cleanly in
# eager mode or if the venv/.env isn't where we expect.
if [ -x "$BACKEND_DIR/venv/bin/python" ] && [ -f "$BACKEND_DIR/.env" ]; then
  "$BACKEND_DIR/venv/bin/python" - "$BACKEND_DIR/.env" <<'PY' || echo "Could not read queue depth."
import sys, os
from dotenv import load_dotenv
load_dotenv(sys.argv[1])
url = os.environ.get("REDIS_URL")
if not url:
    print("REDIS_URL not set (eager mode) — no queue to inspect.")
    sys.exit(0)
try:
    from redis import Redis
    from rq import Queue
    # Name matches settings.CLASSIFICATION_QUEUE_NAME.
    q = Queue("classification", connection=Redis.from_url(url))
    print(f"'classification' queue: {q.count} queued, "
          f"{q.failed_job_registry.count} failed, "
          f"{q.deferred_job_registry.count} deferred")
except Exception as e:
    print(f"Could not reach Redis to read queue depth: {e}")
PY
else
  echo "Backend venv/.env not found under $BACKEND_DIR — skipping queue depth."
fi

echo -e "\n=== Testing API locally (gunicorn socket) ==="
curl --unix-socket "$SOCKET" \
  -H "Host: $DOMAIN" \
  -w "\nHTTP %{http_code}\n" \
  --fail-with-body \
  http://localhost/health/ \
  || echo "API local health check FAILED (see output above)"

echo -e "\n=== Testing API over HTTPS (via CloudFront -> ALB) ==="
curl -w "\nHTTP %{http_code}\n" \
  --fail-with-body \
  "https://$DOMAIN/health/" \
  || echo "API HTTPS health check FAILED (see output above)"

echo -e "\n=== Testing website over HTTPS (CloudFront -> S3) ==="
# Require BOTH a 200 status AND the SPA shell. Checking only the body is unsafe:
# error pages (403/404/500) still contain a <title>, and a piped grep's exit code
# would mask the HTTP failure. Capture the body with the status code appended, then
# assert on both.
web_resp=$(curl -s -w $'\n%{http_code}' "https://$FRONTEND_DOMAIN/")
web_code=$(printf '%s' "$web_resp" | tail -n1)
web_html=$(printf '%s' "$web_resp" | sed '$d')
if [ "$web_code" = "200" ] && printf '%s' "$web_html" | grep -Eqi 'id="root"'; then
  echo "Website HTTPS OK (HTTP 200, SPA shell served)"
else
  echo "Website HTTPS check FAILED (HTTP $web_code, or SPA shell missing)"
fi

echo -e "\n=== Testing website SPA fallback (/verify-email) ==="
# A deep client-side route must return 200 with the SPA shell, not 404 — this is
# the path the email-verification link hits. With S3+CloudFront this relies on a
# CloudFront custom error response mapping 403/404 -> /index.html (200).
code=$(curl -s -o /dev/null -w "%{http_code}" "https://$FRONTEND_DOMAIN/verify-email")
if [ "$code" = "200" ]; then
  echo "SPA fallback OK (HTTP 200 for /verify-email)"
else
  echo "SPA fallback FAILED (HTTP $code for /verify-email — check CloudFront custom error responses)"
fi
