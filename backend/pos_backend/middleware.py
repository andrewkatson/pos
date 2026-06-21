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
    # A request can reach us through a trusted reverse proxy in two ways:
    #   * Over a unix domain socket (nginx -> Gunicorn on the same host), where
    #     Gunicorn reports REMOTE_ADDR as exactly "". Only a local process can
    #     open that socket, and a direct TCP client always has a non-empty
    #     REMOTE_ADDR, so an empty string cannot be forged by a remote client and
    #     reliably identifies the local proxy. We match "" specifically rather
    #     than any falsy value so a missing/malformed REMOTE_ADDR isn't trusted.
    #   * Over TCP from a proxy whose address is listed in TRUSTED_PROXY_IPS.
    # In both cases the proxy sets X-Real-IP to the real client IP, so trust it,
    # falling back to REMOTE_ADDR if the proxy didn't set the header.
    if remote_addr == "" or remote_addr in _get_trusted_proxies():
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
