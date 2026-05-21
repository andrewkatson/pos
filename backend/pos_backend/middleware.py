import os

from django.http import Http404


def _get_allowlist():
    raw = os.environ.get("ADMIN_IP_ALLOWLIST", "")
    return {ip.strip() for ip in raw.split(",") if ip.strip()}


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class AdminIPAllowlistMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin/"):
            allowlist = _get_allowlist()
            if allowlist and _client_ip(request) not in allowlist:
                raise Http404
        return self.get_response(request)
