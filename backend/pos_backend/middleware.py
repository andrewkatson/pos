import os

from django.http import Http404


def _get_allowlist():
    raw = os.environ.get("ADMIN_IP_ALLOWLIST", "")
    return {ip.strip() for ip in raw.split(",") if ip.strip()}


def _client_ip(request):
    return request.META.get("REMOTE_ADDR", "")


class AdminIPAllowlistMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/admin" or request.path.startswith("/admin/"):
            allowlist = _get_allowlist()
            if not allowlist or _client_ip(request) not in allowlist:
                raise Http404
        return self.get_response(request)
