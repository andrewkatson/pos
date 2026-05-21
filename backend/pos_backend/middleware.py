import os

from django.http import Http404


def _get_allowlist():
    raw = os.environ.get("ADMIN_IP_ALLOWLIST", "")
    return {ip.strip() for ip in raw.split(",") if ip.strip()}


def _client_ip(request):
    # Prefer X-Real-IP set by the reverse proxy (nginx: proxy_set_header X-Real-IP $remote_addr).
    # Fall back to REMOTE_ADDR. X-Forwarded-For is not used because the leftmost
    # value is client-controlled and can be spoofed to bypass the allowlist.
    return (
        request.META.get("HTTP_X_REAL_IP")
        or request.META.get("REMOTE_ADDR", "")
    )


class AdminIPAllowlistMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Match both "/admin" and "/admin/..." — the untrailed path would otherwise
        # receive a redirect response before this guard takes effect.
        if request.path.startswith("/admin"):
            allowlist = _get_allowlist()
            if not allowlist or _client_ip(request) not in allowlist:
                raise Http404
        return self.get_response(request)
