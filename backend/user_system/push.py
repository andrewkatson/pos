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
from .models import DeviceToken, NotificationPreference

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
        # Every value is a string: FCM's data map only carries strings, so the
        # contract is uniform across providers (clients parse "true"/"false")
        # rather than a boolean on APNs and a string on FCM. See _send_apns /
        # _send_fcm, which both deliver this map verbatim under a "data" key.
        "data": {
            "type": PUSH_TYPE_POST_REJECTED,
            "post_identifier": post_id,
            "appealable": "true" if appealable else "false",
            # A web-openable link to the post (the web route is singular
            # /post/<id>); native clients route off post_identifier + type.
            "deep_link": f"{settings.FRONTEND_BASE_URL}/post/{post_id}",
        },
    }


def is_push_type_enabled(user, notification_type):
    """Whether the user wants push for this type. Defaults to enabled — a row
    exists only once the user has toggled the type off (or back on) in Settings,
    so its absence means on."""
    pref = NotificationPreference.objects.filter(
        user=user, notification_type=notification_type).first()
    return pref.enabled if pref is not None else True


def send_push(user, payload, notification_type):
    """Fan a payload out to every device the user has registered.

    Respects the user's per-type preference (Settings toggle): a type the user
    turned off is skipped entirely. Otherwise best-effort — a provider that is
    unconfigured or errors is logged and skipped, and dead tokens the providers
    report are pruned. Returns nothing; callers must not depend on delivery.
    """
    if not is_push_type_enabled(user, notification_type):
        logger.info("Push type %s disabled for user %s; skipping.", notification_type, user.id)
        return

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

    if apns_tokens:
        try:
            dead = _send_apns(apns_tokens, payload)
        except Exception:
            logger.exception("APNs push failed for user %s", user.id)
        else:
            # Scope the prune to iOS: uniqueness is on (platform, token), so the
            # same token string can legitimately exist on another platform, and
            # an APNs "gone" verdict must not delete an Android/web row.
            _prune_dead(user, [DEVICE_PLATFORM_IOS], dead)
    if fcm_tokens:
        try:
            dead = _send_fcm(fcm_tokens, payload)
        except Exception:
            logger.exception("FCM push failed for user %s", user.id)
        else:
            _prune_dead(user, [DEVICE_PLATFORM_ANDROID, DEVICE_PLATFORM_WEB], dead)


def _prune_dead(user, platforms, dead_tokens):
    """Delete the user's dead tokens, scoped to the platforms that reported them."""
    if not dead_tokens:
        return
    deleted, _ = DeviceToken.objects.filter(
        user=user, platform__in=platforms, token__in=dead_tokens).delete()
    if deleted:
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
    # PyJWT < 2 returns bytes; APNs needs a str Authorization value.
    if isinstance(token, bytes):
        token = token.decode("ascii")
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
        # httpx's content= doesn't set a content type; be explicit that the body
        # is JSON so APNs never has to guess.
        "content-type": "application/json",
    }
    # Custom keys go under "data" (not flattened to the top level) so iOS reads
    # them at userInfo["data"], matching the FCM data map exactly — including
    # coercing values to strings, so the "all-string data map" contract holds
    # even if a future caller passes a non-string.
    data = {k: str(v) for k, v in payload.get("data", {}).items()}
    body = json.dumps({
        "aps": {"alert": {"title": payload["title"], "body": payload["body"]}, "sound": "default"},
        "data": data,
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
    """Whether an APNs response means the token itself is gone (and should be
    pruned).

    A 410, or a 400 whose reason is BadDeviceToken/Unregistered — the token is
    malformed or no longer registered. DeviceTokenNotForTopic is deliberately
    NOT treated as dead: it signals an apns-topic / environment misconfiguration
    (e.g. a bad APNS_TOPIC or sandbox-vs-prod mismatch), so pruning on it would
    wipe valid tokens during a deploy misconfig; the caller logs it as a warning
    instead.
    """
    if response.status_code == 410:
        return True
    if response.status_code == 400:
        try:
            reason = response.json().get("reason", "")
        except Exception:
            reason = ""
        return reason in ("BadDeviceToken", "Unregistered")
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

    # FCM v1 data values must be strings. build_rejection_payload already emits
    # only strings; str() is a defensive coerce so a caller passing a non-string
    # never sends a JSON-typed value FCM would reject.
    data = {k: str(v) for k, v in payload.get("data", {}).items()}

    # On web the notification block is auto-displayed by the browser, so the
    # service worker's background handler never runs; webpush.fcm_options.link is
    # what carries the click through to the rejected post. Android reads the same
    # target from the data map instead, so this is harmless there.
    deep_link = data.get("deep_link")
    webpush = {"fcm_options": {"link": deep_link}} if deep_link else None

    dead = []
    for token in tokens:
        message_body = {
            "token": token,
            "notification": {"title": payload["title"], "body": payload["body"]},
            "data": data,
        }
        if webpush:
            message_body["webpush"] = webpush
        message = {"message": message_body}
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
    """Whether a token is genuinely gone (and should be pruned).

    Only an explicit UNREGISTERED errorCode / NOT_FOUND status in the response
    body means the registration token no longer exists. A bare HTTP 404 is NOT
    enough: a wrong project_id or URL 404s too, and pruning on that would wipe
    every registered token over a config mistake. INVALID_ARGUMENT is likewise
    not treated as dead — it can signal a malformed request/config rather than a
    bad token. Everything ambiguous is left registered and logged by the caller.
    """
    try:
        error = response.json().get("error", {})
    except Exception:
        return False
    if error.get("status", "") == "NOT_FOUND":
        return True
    for detail in error.get("details", []):
        if detail.get("errorCode") == "UNREGISTERED":
            return True
    return False
