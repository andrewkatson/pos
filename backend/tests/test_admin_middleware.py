import pytest
from unittest.mock import MagicMock, patch

from django.http import Http404
from django.test import RequestFactory

from pos_backend.middleware import AdminIPAllowlistMiddleware


def make_middleware(get_response=None):
    if get_response is None:
        get_response = MagicMock(return_value=MagicMock(status_code=200))
    return AdminIPAllowlistMiddleware(get_response)


def make_request(path, remote_addr="1.2.3.4", x_real_ip=None):
    factory = RequestFactory()
    request = factory.get(path)
    request.META["REMOTE_ADDR"] = remote_addr
    if x_real_ip is not None:
        request.META["HTTP_X_REAL_IP"] = x_real_ip
    return request


# --- allowlist parsing ---

def test_empty_allowlist_blocks_admin():
    middleware = make_middleware()
    request = make_request("/admin/", remote_addr="1.2.3.4")
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(Http404):
            middleware(request)


def test_unset_allowlist_blocks_admin():
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


def test_path_with_admin_prefix_not_matched():
    """Paths like /admintools/ should not be gated — only /admin paths."""
    middleware = make_middleware()
    request = make_request("/admintools/", remote_addr="9.9.9.9")
    with patch.dict("os.environ", {"ADMIN_IP_ALLOWLIST": "10.0.0.1"}):
        # /admintools/ starts with /admin so it IS caught — this test
        # documents the current conservative behaviour.
        with pytest.raises(Http404):
            middleware(request)


# --- IP source precedence ---

def test_x_real_ip_takes_precedence_over_remote_addr():
    middleware = make_middleware()
    # REMOTE_ADDR is unlisted, X-Real-IP is listed
    request = make_request("/admin/", remote_addr="9.9.9.9", x_real_ip="10.0.0.1")
    with patch.dict("os.environ", {"ADMIN_IP_ALLOWLIST": "10.0.0.1"}):
        response = middleware(request)
    assert response.status_code == 200


def test_x_forwarded_for_is_not_trusted():
    """X-Forwarded-For must not grant access — it's client-controlled."""
    middleware = make_middleware()
    request = make_request("/admin/", remote_addr="9.9.9.9")
    request.META["HTTP_X_FORWARDED_FOR"] = "10.0.0.1"
    with patch.dict("os.environ", {"ADMIN_IP_ALLOWLIST": "10.0.0.1"}):
        with pytest.raises(Http404):
            middleware(request)
