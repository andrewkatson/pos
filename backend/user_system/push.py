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
from urllib.parse import quote

from django.conf import settings

from .constants import (
    DEVICE_PLATFORM_IOS, DEVICE_PLATFORM_ANDROID, DEVICE_PLATFORM_WEB,
    PUSH_TYPE_POST_REJECTED, PUSH_TYPE_NEW_POST, PUSH_TYPE_NEW_COMMENT, PUSH_TYPE_NEW_LIKE,
    PUSH_TYPE_PARENTS,
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

# Android notification channels, matching the ids the app registers at launch
# (PosFirebaseMessagingService). Social activity (issue #444) has its own
# channel so a user can mute it in system settings without muting rejections.
# Named in the FCM payload because a message arriving while the app is in the
# background is displayed by the system, never reaching the app's own code.
ANDROID_CHANNEL_POST_MODERATION = "post_moderation"
ANDROID_CHANNEL_ACTIVITY = "activity"
_ACTIVITY_PUSH_TYPES = frozenset({PUSH_TYPE_NEW_POST, PUSH_TYPE_NEW_COMMENT, PUSH_TYPE_NEW_LIKE})


def android_channel_for(data):
    """The Android notification channel for a payload's data map."""
    if data.get("type") in _ACTIVITY_PUSH_TYPES:
        return ANDROID_CHANNEL_ACTIVITY
    return ANDROID_CHANNEL_POST_MODERATION


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


# Longest slice of a caption or comment quoted in an activity push body. Lock
# screens truncate long bodies anyway; this keeps the payload small and stops a
# long post from being mirrored wholesale into the notification shade.
ACTIVITY_PREVIEW_LENGTH = 100


def _preview(text):
    text = " ".join((text or "").split())
    if len(text) <= ACTIVITY_PREVIEW_LENGTH:
        return text
    return text[:ACTIVITY_PREVIEW_LENGTH - 1].rstrip() + "\u2026"


def build_activity_payload(kind, post, title, body_text):
    """Build the push payload for social activity on a post (issue #444): a new
    post from someone the recipient follows, or a comment, reply or like.

    ``kind`` is the data ``type`` the clients branch on (new_post / new_comment
    / new_like); every kind deep-links to ``post`` the same way a rejection
    does. As with build_rejection_payload, every data value is a string.
    """
    post_id = str(post.post_identifier)
    return {
        "title": title,
        "body": _preview(body_text),
        "data": {
            "type": kind,
            "post_identifier": post_id,
            "deep_link": f"{settings.FRONTEND_BASE_URL}/post/{post_id}",
        },
    }


def _push_type_chain(notification_type):
    """The type followed by each of its ancestors up to the master switch."""
    chain = []
    while notification_type is not None:
        chain.append(notification_type)
        notification_type = PUSH_TYPE_PARENTS.get(notification_type)
    return chain


def is_push_type_enabled(user, notification_type):
    """Whether the user wants push for this type: the type itself and every
    ancestor in the preference tree (issue #444) must be on, so turning off the
    master switch or a kind's switch silences everything beneath it. Defaults
    to enabled — a row exists only once the user has toggled a type off (or
    back on) in Settings, so its absence means on."""
    return not NotificationPreference.objects.filter(
        user=user, notification_type__in=_push_type_chain(notification_type), enabled=False,
    ).exists()


def disabled_push_types(user_ids):
    """{user_id: set of types they turned off} for many users in one query —
    the bulk form of is_push_type_enabled, for fan-outs. Pair with
    push_type_enabled_in."""
    disabled = {}
    for user_id, notification_type in NotificationPreference.objects.filter(
            user_id__in=user_ids, enabled=False).values_list('user_id', 'notification_type'):
        disabled.setdefault(user_id, set()).add(notification_type)
    return disabled


def push_type_enabled_in(disabled_types, notification_type):
    """is_push_type_enabled over an already-loaded set of disabled types."""
    return not any(t in disabled_types for t in _push_type_chain(notification_type))


def send_push(user, payload, notification_type, tokens=None):
    """Fan a payload out to every device the user has registered.

    Respects the user's per-type preference (Settings toggle): a type the user
    turned off is skipped entirely. Otherwise best-effort — a provider that is
    unconfigured or errors is logged and skipped, and dead tokens the providers
    report are pruned. Returns nothing; callers must not depend on delivery.

    A fan-out that has bulk-loaded its recipients' preferences and device
    tokens (see disabled_push_types) passes the user's DeviceToken rows as
    `tokens`; it has then already applied the preference, so both per-user
    queries are skipped.
    """
    if tokens is None:
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
                # Percent-encode the token as a single path segment so a token
                # containing reserved URL characters (/, ?, #, %) can never
                # reshape the request path — defense in depth over the
                # registration-time format validation.
                response = client.post(
                    f"{host}/3/device/{quote(token, safe='')}", headers=headers, content=body)
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

    Only HTTP 410 (reason "Unregistered" — the device unregistered, e.g. the app
    was uninstalled) is an unambiguous "this token is gone". A 400 is deliberately
    NOT pruned: BadDeviceToken / DeviceTokenNotForTopic can signal an environment
    or apns-topic misconfiguration (sandbox vs prod, a bad APNS_TOPIC) rather than
    a truly dead token, so pruning on it would wipe valid tokens en masse on a
    deploy misconfig. The caller logs those as warnings instead — and the token
    format is already validated at registration, so genuinely malformed tokens
    rarely reach APNs.
    """
    return response.status_code == 410


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
    # Only Android reads this block; web ignores it.
    android = {"notification": {"channel_id": android_channel_for(data)}}

    dead = []
    for token in tokens:
        message_body = {
            "token": token,
            "notification": {"title": payload["title"], "body": payload["body"]},
            "data": data,
            "android": android,
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

    Prune only on the explicit UNREGISTERED FcmError detail. Neither a bare HTTP
    404 nor a NOT_FOUND status alone is enough — a wrong project_id or URL also
    404s with status NOT_FOUND, so pruning on that would wipe every registered
    token over a config mistake (FCM's real unregistered-token response carries
    both NOT_FOUND *and* the UNREGISTERED detail). INVALID_ARGUMENT is likewise
    not treated as dead. Everything ambiguous is left registered and logged by
    the caller.
    """
    try:
        body = response.json()
    except Exception:
        return False
    # Be defensive about the shape: an unexpected body must simply not prune
    # (return False), never raise and abort the rest of the send fan-out.
    error = body.get("error", {}) if isinstance(body, dict) else {}
    details = error.get("details", []) if isinstance(error, dict) else []
    if not isinstance(details, list):
        return False
    for detail in details:
        if isinstance(detail, dict) and detail.get("errorCode") == "UNREGISTERED":
            return True
    return False
