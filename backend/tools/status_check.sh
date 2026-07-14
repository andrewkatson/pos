#!/bin/bash

# Health check for the smiling.social stack.
#   * API  : gunicorn behind nginx on THIS EC2 (CloudFront -> ALB -> nginx:80).
#   * Website: static SPA in S3 behind CloudFront (NOT served from this host) —
#     checked end-to-end over HTTPS only.
# Override the hosts/socket if yours differ.
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
