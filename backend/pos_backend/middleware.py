import os

from django.http import Http404


def _get_allowlist():
    raw = os.environ.get("ADMIN_IP_ALLOWLIST", "")
    return {ip.strip() for ip in raw.split(",") if ip.strip()}


def _get_trusted_proxies():
    raw = os.environ.get("TRUSTED_PROXY_IPS", "")
    return {ip.strip() for ip in raw.split(",") if ip.strip()}


def _client_ip(request):
    remote_addr = request.META.get("REMOTE_ADDR", "")
    if remote_addr in _get_trusted_proxies():
        # Request arrived through a known proxy (e.g. nginx on the same host).
        # Trust the X-Real-IP header it set; fall back to REMOTE_ADDR if absent.
        return request.META.get("HTTP_X_REAL_IP") or remote_addr
    return remote_addr


class AdminIPAllowlistMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/admin" or request.path.startswith("/admin/"):
            allowlist = _get_allowlist()
            if not allowlist or _client_ip(request) not in allowlist:
                raise Http404
        return self.get_response(request)
