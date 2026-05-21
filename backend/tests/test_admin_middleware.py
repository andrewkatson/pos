import pytest
from unittest.mock import MagicMock, patch

from django.http import Http404

from pos_backend.middleware import AdminIPAllowlistMiddleware


def make_middleware(get_response=None):
    if get_response is None:
        get_response = MagicMock(return_value=MagicMock(status_code=200))
    return AdminIPAllowlistMiddleware(get_response)


def make_request(path, remote_addr="1.2.3.4", x_real_ip=None, spoofed_xff=None):
    request = MagicMock()
    request.path = path
    request.META = {"REMOTE_ADDR": remote_addr}
    if x_real_ip is not None:
        request.META["HTTP_X_REAL_IP"] = x_real_ip
    if spoofed_xff is not None:
        request.META["HTTP_X_FORWARDED_FOR"] = spoofed_xff
    return request


# --- allowlist parsing ---

def test_empty_allowlist_blocks_admin():
    middleware = make_middleware()
    request = make_request("/admin/", remote_addr="1.2.3.4")
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(Http404):
            middleware(request)


def test_empty_string_allowlist_blocks_admin():
    middleware = make_middleware()
    request = make_request("/admin/")
    with patch.dict("os.environ", {"ADMIN_IP_ALLOWLIST": ""}, clear=False):
        with pytest.raises(Http404):
            middleware(request)


def test_listed_ip_allowed():
    middleware = make_middleware()
    request = make_request("/admin/", remote_addr="10.0.0.1")
    with patch.dict("os.environ", {"ADMIN_IP_ALLOWLIST": "10.0.0.1"}):
        response = middleware(request)
    assert response.status_code == 200


def test_unlisted_ip_blocked():
    middleware = make_middleware()
    request = make_request("/admin/", remote_addr="9.9.9.9")
    with patch.dict("os.environ", {"ADMIN_IP_ALLOWLIST": "10.0.0.1"}):
        with pytest.raises(Http404):
            middleware(request)


def test_multiple_ips_in_allowlist():
    middleware = make_middleware()
    request = make_request("/admin/", remote_addr="10.0.0.2")
    with patch.dict("os.environ", {"ADMIN_IP_ALLOWLIST": "10.0.0.1, 10.0.0.2, 10.0.0.3"}):
        response = middleware(request)
    assert response.status_code == 200


# --- path matching ---

def test_admin_without_trailing_slash_blocked():
    middleware = make_middleware()
    request = make_request("/admin", remote_addr="9.9.9.9")
    with patch.dict("os.environ", {"ADMIN_IP_ALLOWLIST": "10.0.0.1"}):
        with pytest.raises(Http404):
            middleware(request)


def test_non_admin_path_not_affected():
    middleware = make_middleware()
    request = make_request("/user_index/login/", remote_addr="9.9.9.9")
    with patch.dict("os.environ", {"ADMIN_IP_ALLOWLIST": "10.0.0.1"}):
        response = middleware(request)
    assert response.status_code == 200


def test_path_with_admin_prefix_not_blocked():
    """Paths like /admintools/ share the prefix but should not be gated."""
    middleware = make_middleware()
    request = make_request("/admintools/", remote_addr="9.9.9.9")
    with patch.dict("os.environ", {"ADMIN_IP_ALLOWLIST": "10.0.0.1"}):
        response = middleware(request)
    assert response.status_code == 200


# --- IP source: direct (no trusted proxy) ---

def test_x_real_ip_ignored_without_trusted_proxy():
    """X-Real-IP is not used when REMOTE_ADDR is not a trusted proxy."""
    middleware = make_middleware()
    request = make_request("/admin/", remote_addr="9.9.9.9", x_real_ip="10.0.0.1")
    with patch.dict("os.environ", {"ADMIN_IP_ALLOWLIST": "10.0.0.1"}, clear=False):
        with pytest.raises(Http404):
            middleware(request)


def test_x_forwarded_for_is_not_trusted():
    """X-Forwarded-For must not grant access — it's client-controlled."""
    middleware = make_middleware()
    request = make_request("/admin/", remote_addr="9.9.9.9", spoofed_xff="10.0.0.1")
    with patch.dict("os.environ", {"ADMIN_IP_ALLOWLIST": "10.0.0.1"}, clear=False):
        with pytest.raises(Http404):
            middleware(request)


# --- IP source: behind trusted proxy (nginx → Gunicorn) ---

def test_x_real_ip_used_when_remote_addr_is_trusted_proxy():
    """When REMOTE_ADDR is a trusted proxy, X-Real-IP carries the real client IP."""
    middleware = make_middleware()
    request = make_request("/admin/", remote_addr="127.0.0.1", x_real_ip="10.0.0.1")
    env = {"ADMIN_IP_ALLOWLIST": "10.0.0.1", "TRUSTED_PROXY_IPS": "127.0.0.1"}
    with patch.dict("os.environ", env, clear=False):
        response = middleware(request)
    assert response.status_code == 200


def test_unlisted_real_ip_blocked_via_trusted_proxy():
    """Client not in allowlist is blocked even when coming through a trusted proxy."""
    middleware = make_middleware()
    request = make_request("/admin/", remote_addr="127.0.0.1", x_real_ip="9.9.9.9")
    env = {"ADMIN_IP_ALLOWLIST": "10.0.0.1", "TRUSTED_PROXY_IPS": "127.0.0.1"}
    with patch.dict("os.environ", env, clear=False):
        with pytest.raises(Http404):
            middleware(request)


def test_trusted_proxy_without_x_real_ip_falls_back_to_remote_addr():
    """If the trusted proxy didn't set X-Real-IP, fall back to REMOTE_ADDR."""
    middleware = make_middleware()
    request = make_request("/admin/", remote_addr="127.0.0.1")
    env = {"ADMIN_IP_ALLOWLIST": "127.0.0.1", "TRUSTED_PROXY_IPS": "127.0.0.1"}
    with patch.dict("os.environ", env, clear=False):
        response = middleware(request)
    assert response.status_code == 200


def test_empty_trusted_proxy_ips_means_no_proxies_trusted():
    """TRUSTED_PROXY_IPS unset/empty means X-Real-IP is never used."""
    middleware = make_middleware()
    request = make_request("/admin/", remote_addr="9.9.9.9", x_real_ip="10.0.0.1")
    env = {"ADMIN_IP_ALLOWLIST": "10.0.0.1", "TRUSTED_PROXY_IPS": ""}
    with patch.dict("os.environ", env, clear=False):
        with pytest.raises(Http404):
            middleware(request)
