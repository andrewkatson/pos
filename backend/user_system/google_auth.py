"""Verification of the Google ID tokens behind Google sign-in (issue #10).

Clients (web, iOS, Android) each obtain an ID token from Google natively and
post it to ``login/google/``. This module is the part that decides whether such
a token is worth anything: it is kept out of ``views.py`` because it is the only
piece that talks to Google, so tests can stub one function instead of a network.

The verification itself is `google-auth`'s, which the project already depends on
for FCM push. It checks the RS256 signature against Google's published keys, the
issuer, the audience and the expiry.
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# The two issuer values Google mints ID tokens under. google-auth checks this
# itself; it is repeated here so the check cannot be silently lost if the
# verification call is ever swapped for another library.
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")


class GoogleTokenError(Exception):
    """A presented ID token is not one we are willing to trust."""


def is_google_sign_in_configured():
    """True when this deployment has at least one OAuth client ID to check against.

    With no configured audience there is no way to tell a token minted for us
    from one minted for any other Google app, so the endpoint refuses outright
    rather than accepting whatever it is handed.
    """
    return bool(getattr(settings, "GOOGLE_OAUTH_CLIENT_IDS", []))


def verify_google_id_token(raw_token):
    """Verify ``raw_token`` and return the claims we care about.

    Returns a dict with ``sub`` (Google's permanent per-account identifier),
    ``email`` (lower-cased) and ``email_verified``. Raises ``GoogleTokenError``
    for anything that is not a valid, unexpired Google ID token addressed to one
    of our OAuth clients.
    """
    client_ids = list(getattr(settings, "GOOGLE_OAUTH_CLIENT_IDS", []))
    if not client_ids:
        raise GoogleTokenError("Google sign-in is not configured")

    # Imported lazily: google-auth opens an HTTP session to fetch Google's
    # signing certificates and pulls in cryptography, and no other code path in
    # the app needs any of that at import time.
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    try:
        claims = google_id_token.verify_oauth2_token(
            raw_token,
            google_requests.Request(),
            audience=client_ids,
        )
    except Exception as exc:
        # A bad signature, an audience we don't recognize, an expired token and
        # a failure to reach Google for the certificates all land here. The
        # caller collapses them into one opaque error on purpose — telling a
        # caller which check failed only helps someone probing the endpoint.
        logger.warning("Google ID token verification failed: %s", exc)
        raise GoogleTokenError(str(exc)) from exc

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise GoogleTokenError("Unexpected token issuer")

    subject = claims.get("sub")
    email = claims.get("email")
    if not subject or not email:
        raise GoogleTokenError("Token is missing the subject or email claim")

    # Documented as a boolean, but Google has historically also serialized it as
    # the string "true", and treating that as "not verified" would lock those
    # users out for no reason.
    email_verified = claims.get("email_verified")
    if isinstance(email_verified, str):
        email_verified = email_verified.strip().lower() == "true"

    return {
        "sub": str(subject),
        "email": str(email).strip().lower(),
        "email_verified": email_verified is True,
    }
