#!/bin/bash

# Health check for the smiling.social box: the API (gunicorn behind nginx) and
# the website (static SPA served by nginx). Override the hosts if yours differ.
DOMAIN="${DOMAIN:-api.smiling.social}"
FRONTEND_DOMAIN="${FRONTEND_DOMAIN:-smiling.social}"
SOCKET="${SOCKET:-/var/www/smiling-social/gunicorn.sock}"

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

echo -e "\n=== Testing API locally (gunicorn socket) ==="
curl --unix-socket "$SOCKET" \
  -H "Host: $DOMAIN" \
  -w "\nHTTP %{http_code}\n" \
  --fail-with-body \
  http://localhost/health/ \
  || echo "API local health check FAILED (see output above)"

echo -e "\n=== Testing API over HTTPS ==="
curl -w "\nHTTP %{http_code}\n" \
  --fail-with-body \
  "https://$DOMAIN/health/" \
  || echo "API HTTPS health check FAILED (see output above)"

echo -e "\n=== Testing website locally (nginx vhost) ==="
# Confirm nginx has the website server block wired up. With the HTTPS redirect in
# place this returns 301 to https; -I keeps it to headers only.
curl -sI \
  -H "Host: $FRONTEND_DOMAIN" \
  -w "HTTP %{http_code}\n" \
  http://localhost/ \
  | tail -n 1 \
  || echo "Website local check FAILED"

echo -e "\n=== Testing website over HTTPS ==="
# The homepage must return 200 and serve the SPA shell.
curl -sw "\nHTTP %{http_code}\n" \
  --fail-with-body \
  "https://$FRONTEND_DOMAIN/" \
  | grep -Eqi '<div id="root"|<title' \
  && echo "Website HTTPS OK (index.html served)" \
  || echo "Website HTTPS check FAILED (no SPA shell in response)"

echo -e "\n=== Testing website SPA fallback (/verify-email) ==="
# A deep client-side route must fall back to index.html (200), not 404 — this is
# the path the email-verification link hits.
code=$(curl -s -o /dev/null -w "%{http_code}" "https://$FRONTEND_DOMAIN/verify-email")
if [ "$code" = "200" ]; then
  echo "SPA fallback OK (HTTP 200 for /verify-email)"
else
  echo "SPA fallback FAILED (HTTP $code for /verify-email — check try_files)"
fi
