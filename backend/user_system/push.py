"""Native push notifications (issue #342).

Best-effort, off the request path: the classification worker calls
``send_push`` on a resolved rejection so the author gets a pop-up even with the
app closed. Push is **never the source of truth** — a denied permission or a
stale token just means the user learns the outcome via in-app reconciliation
(#282) instead, so every failure here is logged and swallowed rather than
raised.

Two providers, selected by ``DeviceToken.platform``: APNs for iOS, FCM for
Android and web (issue #343 registers FCM-for-web tokens with ``platform=web``).
Each provider send returns the subset of tokens the provider reports as dead
(``Unregistered`` / ``NOT_FOUND``); ``send_push`` deletes those rows so we do not
leak or keep paying to send to them.

The provider HTTP libraries (httpx/h2 for APNs, google-auth/requests for FCM)
and the signing key are all imported/read lazily inside the send functions, and
a provider with no credentials configured is a logged no-op. That keeps this
module importable — and the test suite, which patches ``_send_apns`` /
``_send_fcm``, hermetic — on any machine or deploy that has not set push up.
"""
import json
import logging
import time

from django.conf import settings

from .constants import (
    DEVICE_PLATFORM_IOS, DEVICE_PLATFORM_ANDROID, DEVICE_PLATFORM_WEB,
    PUSH_TYPE_POST_REJECTED,
)
from .models import DeviceToken

logger = logging.getLogger(__name__)

# APNs endpoints. Development app builds register sandbox tokens that only the
# sandbox gateway will accept; production builds use the production gateway.
_APNS_HOST_PROD = "https://api.push.apple.com"
_APNS_HOST_SANDBOX = "https://api.sandbox.push.apple.com"

# Apple provider-auth JWTs are valid up to an hour; Apple rejects a token older
# than that and rate-limits minting new ones. Reuse one JWT until it is close to
# expiry rather than signing per send.
_APNS_TOKEN_TTL_SECONDS = 3000  # 50 minutes
_apns_jwt_cache = {"token": None, "minted_at": 0.0}

# FCM OAuth2 scope for the HTTP v1 send API.
_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


def build_rejection_payload(post, final):
    """Build the push payload for a post rejected by the classifier.

    ``data`` is the machine-readable contract the clients (#343) branch on to
    deep-link to the rejected post and, when appealable, its appeal UI. ``final``
    rejections are terminal (the post is a tombstone, image gone) and carry
    ``appealable=false`` so the client offers no appeal action.
    """
    post_id = str(post.post_identifier)
    appealable = not final
    if final:
        title = "Your post wasn't approved"
        body = "Automated review removed your post. This decision is final."
    else:
        title = "Your post wasn't approved"
        body = "Automated review hid your post. Tap to review or appeal it."
    return {
        "title": title,
        "body": body,
        "data": {
            "type": PUSH_TYPE_POST_REJECTED,
            "post_identifier": post_id,
            "appealable": appealable,
            # A web-openable link to the post; native clients route off
            # post_identifier + type, web opens this directly on tap.
            "deep_link": f"{settings.FRONTEND_BASE_URL}/posts/{post_id}",
        },
    }


def send_push(user, payload):
    """Fan a payload out to every device the user has registered.

    Best-effort: a provider that is unconfigured or errors is logged and
    skipped, and dead tokens the providers report are pruned so we stop sending
    to them. Returns nothing — callers must not depend on delivery.
    """
    tokens = list(DeviceToken.objects.filter(user=user))
    if not tokens:
        return

    by_platform = {}
    for row in tokens:
        by_platform.setdefault(row.platform, []).append(row.token)

    apns_tokens = by_platform.get(DEVICE_PLATFORM_IOS, [])
    # Android and FCM-for-web tokens both go through FCM.
    fcm_tokens = (by_platform.get(DEVICE_PLATFORM_ANDROID, [])
                  + by_platform.get(DEVICE_PLATFORM_WEB, []))

    dead = set()
    if apns_tokens:
        try:
            dead.update(_send_apns(apns_tokens, payload))
        except Exception:
            logger.exception("APNs push failed for user %s", user.id)
    if fcm_tokens:
        try:
            dead.update(_send_fcm(fcm_tokens, payload))
        except Exception:
            logger.exception("FCM push failed for user %s", user.id)

    if dead:
        deleted, _ = DeviceToken.objects.filter(user=user, token__in=dead).delete()
        logger.info("Pruned %d dead device token(s) for user %s", deleted, user.id)


# ---------------------------------------------------------------------------
# APNs (iOS)
# ---------------------------------------------------------------------------

def _apns_configured():
    """True when enough APNs credentials are present to attempt a send."""
    return bool(
        (getattr(settings, "APNS_AUTH_KEY", "") or getattr(settings, "APNS_AUTH_KEY_PATH", ""))
        and getattr(settings, "APNS_KEY_ID", "")
        and getattr(settings, "APNS_TEAM_ID", "")
        and getattr(settings, "APNS_TOPIC", "")
    )


def _apns_auth_key():
    """The .p8 signing key contents, from inline PEM or a mounted file."""
    inline = getattr(settings, "APNS_AUTH_KEY", "")
    if inline:
        return inline
    path = getattr(settings, "APNS_AUTH_KEY_PATH", "")
    if path:
        with open(path, "r") as handle:
            return handle.read()
    return ""


def _apns_jwt():
    """Return a cached APNs provider JWT, minting a fresh one near expiry."""
    now = time.time()
    if _apns_jwt_cache["token"] and (now - _apns_jwt_cache["minted_at"]) < _APNS_TOKEN_TTL_SECONDS:
        return _apns_jwt_cache["token"]
    import jwt  # lazy: only needed when APNs is actually configured

    token = jwt.encode(
        {"iss": settings.APNS_TEAM_ID, "iat": int(now)},
        _apns_auth_key(),
        algorithm="ES256",
        headers={"kid": settings.APNS_KEY_ID},
    )
    _apns_jwt_cache["token"] = token
    _apns_jwt_cache["minted_at"] = now
    return token


def _send_apns(tokens, payload):
    """Send to iOS tokens over APNs HTTP/2. Returns the dead ones to prune."""
    if not _apns_configured():
        logger.debug("APNs not configured; skipping %d iOS push(es).", len(tokens))
        return []

    import httpx  # lazy: pulls in the http2 (h2) stack only when sending

    host = _APNS_HOST_SANDBOX if getattr(settings, "APNS_USE_SANDBOX", False) else _APNS_HOST_PROD
    auth = _apns_jwt()
    headers = {
        "authorization": f"bearer {auth}",
        "apns-topic": settings.APNS_TOPIC,
        "apns-push-type": "alert",
    }
    body = json.dumps({
        "aps": {"alert": {"title": payload["title"], "body": payload["body"]}, "sound": "default"},
        **payload.get("data", {}),
    })

    dead = []
    with httpx.Client(http2=True, timeout=10.0) as client:
        for token in tokens:
            try:
                response = client.post(f"{host}/3/device/{token}", headers=headers, content=body)
            except Exception:
                # Transport hiccup: not evidence the token is dead, so leave it.
                logger.exception("APNs send errored for a token; leaving it registered.")
                continue
            if response.status_code == 200:
                continue
            if _apns_token_is_dead(response):
                dead.append(token)
            else:
                logger.warning("APNs send failed (%s): %s", response.status_code, response.text[:200])
    return dead


def _apns_token_is_dead(response):
    """A 410, or a 400 BadDeviceToken/Unregistered, means the token is gone."""
    if response.status_code == 410:
        return True
    if response.status_code == 400:
        try:
            reason = response.json().get("reason", "")
        except Exception:
            reason = ""
        return reason in ("BadDeviceToken", "Unregistered", "DeviceTokenNotForTopic")
    return False


# ---------------------------------------------------------------------------
# FCM (Android + web)
# ---------------------------------------------------------------------------

def _fcm_service_account():
    """Parse the FCM service-account JSON from inline env or a mounted file."""
    inline = getattr(settings, "FCM_CREDENTIALS", "")
    if inline:
        return json.loads(inline)
    path = getattr(settings, "FCM_CREDENTIALS_PATH", "")
    if path:
        with open(path, "r") as handle:
            return json.load(handle)
    return None


def _send_fcm(tokens, payload):
    """Send to Android/web tokens over FCM HTTP v1. Returns dead ones to prune."""
    service_account = None
    try:
        service_account = _fcm_service_account()
    except Exception:
        logger.exception("Failed to load FCM service account; skipping FCM push.")
        return []
    if not service_account:
        logger.debug("FCM not configured; skipping %d push(es).", len(tokens))
        return []

    # Lazy imports: google-auth + requests are only needed when actually sending.
    from google.oauth2 import service_account as google_service_account
    from google.auth.transport.requests import Request, AuthorizedSession

    credentials = google_service_account.Credentials.from_service_account_info(
        service_account, scopes=[_FCM_SCOPE])
    credentials.refresh(Request())
    session = AuthorizedSession(credentials)
    project_id = service_account["project_id"]
    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

    # FCM v1 data values must be strings.
    data = {k: (v if isinstance(v, str) else json.dumps(v)) for k, v in payload.get("data", {}).items()}

    dead = []
    for token in tokens:
        message = {
            "message": {
                "token": token,
                "notification": {"title": payload["title"], "body": payload["body"]},
                "data": data,
            }
        }
        try:
            response = session.post(url, json=message, timeout=10.0)
        except Exception:
            logger.exception("FCM send errored for a token; leaving it registered.")
            continue
        if response.status_code == 200:
            continue
        if _fcm_token_is_dead(response):
            dead.append(token)
        else:
            logger.warning("FCM send failed (%s): %s", response.status_code, response.text[:200])
    return dead


def _fcm_token_is_dead(response):
    """A 404, or an UNREGISTERED / INVALID_ARGUMENT error, means it is gone."""
    if response.status_code == 404:
        return True
    try:
        error = response.json().get("error", {})
    except Exception:
        return False
    status = error.get("status", "")
    if status == "NOT_FOUND":
        return True
    for detail in error.get("details", []):
        if detail.get("errorCode") in ("UNREGISTERED", "INVALID_ARGUMENT"):
            return True
    return False
