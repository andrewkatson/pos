import hashlib
import ipaddress
import json
import logging
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date, timedelta

from functools import wraps

import pyotp
from django.conf import settings
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import transaction, IntegrityError
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited

from .classifiers import image_classifier, text_classifier
from .classifiers.classifier_utils import ClassificationResult
from .constants import Patterns, Params, POST_BATCH_SIZE, MAX_BEFORE_HIDING_POST, MAX_BEFORE_HIDING_COMMENT, \
    MAX_CAPTION_LENGTH, MAX_COMMENT_LENGTH, \
    COMMENT_BATCH_SIZE, Fields, COMMENT_THREAD_BATCH_SIZE, \
    VERIFY_RESET_MAX_ATTEMPTS, VERIFY_RESET_LOCKOUT_MINUTES, \
    ACCOUNT_BANNED, EMAIL_NOT_VERIFIED, EMAIL_VERIFICATION_TOKEN_HOURS, BAN_TYPE_OUTRIGHT, \
    HIDDEN_REASON_NONE, HIDDEN_REASON_REPORTS, HIDDEN_REASON_CLASSIFIER, \
    APPEAL_TARGET_POST, APPEAL_TARGET_COMMENT, APPEAL_TARGET_BAN, \
    MAX_APPEAL_REASON_LENGTH, \
    TWO_FACTOR_CHALLENGE_MINUTES, TWO_FACTOR_MAX_ATTEMPTS, NUM_RECOVERY_CODES, \
    LEN_RECOVERY_CODE_HEX, TOTP_ISSUER
from .feed_algorithm import feed_algorithm
from .input_validator import is_valid_pattern
from .models import LoginCookie, Session, Post, CommentThread, PositiveOnlySocialUser, Comment, CommentLike, UserBlock, \
    UserBan, KnownDevice, Appeal, TwoFactorChallenge, RecoveryCode
from .utils import convert_to_bool, generate_login_cookie_token, generate_management_token, generate_series_identifier, \
    get_batch, get_queryset_batch, get_compressed_image_url
from .s3 import delete_image, generate_presigned_upload, image_url_to_key
from .visibility import can_view_post, searchable_users, visible_comment_threads, visible_comments, visible_posts

image_classifier_class = image_classifier
text_classifier_class = text_classifier

# Shared, bounded thread pool for the per-request content-classification fan-out
# (a post's text and image are classified concurrently). A single module-level
# executor is reused across requests rather than creating a new one per call, so
# a traffic spike cannot spawn unbounded threads: once every worker is busy,
# further classification tasks queue, which provides backpressure. The work is
# I/O-bound (waiting on external AI APIs), so a worker count above the CPU count
# is fine; this caps the threads one gunicorn worker process can devote to
# classification.
_CLASSIFICATION_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="classify")
feed_algorithm_class = feed_algorithm

logger = logging.getLogger(__name__)


def log_and_return_json(view_name, data, **kwargs):
    status = kwargs.get('status', 200)
    if status >= 400:
        logger.warning(f"Endpoint {view_name} returned {status}: {data}")
    else:
        logger.info(f"Endpoint {view_name} succeeded.")
    return JsonResponse(data, **kwargs)


def _get_client_ip(group, request):
    """Rate limit key: real client IP from AWS ALB.

    AWS ALB appends the actual client IP to the *end* of any existing
    X-Forwarded-For header, so reading the last entry is tamper-resistant
    (a client can forge earlier entries but not the one the ALB adds).
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if x_forwarded_for:
        candidate = x_forwarded_for.split(',')[-1].strip()
        try:
            ipaddress.ip_address(candidate)
            return candidate
        except ValueError:
            pass
    return request.META.get('REMOTE_ADDR', '')


def get_user_with_username_and_email(username, email):
    try:
        existing = get_user_model().objects.get(username=username, email=email)
        return existing
    except get_user_model().DoesNotExist:
        return None


def get_user_with_username_or_email(username_or_email):
    existing = get_user_with_username(username_or_email)
    if existing is None:
        existing = get_user_with_email(username_or_email)
        return existing
    else:
        return existing


def get_user_with_username(username):
    try:
        existing = get_user_model().objects.get(username=username)
        return existing
    except get_user_model().DoesNotExist:
        return None


def get_user_with_email(email):
    try:
        existing = get_user_model().objects.get(email=email)
        return existing
    except get_user_model().DoesNotExist:
        return None


def get_user_with_id(user_id):
    try:
        existing = get_user_model().objects.get(id=user_id)
        return existing
    except get_user_model().DoesNotExist:
        return None


def get_user_with_series_identifier(series_identifier):
    try:
        existing_login_cookie = LoginCookie.objects.get(series_identifier=series_identifier)
        return existing_login_cookie.cookie_user
    except LoginCookie.DoesNotExist:
        return None


def get_user_with_session_management_token(token):
    try:
        existing_session = Session.objects.get(management_token=token)
        return existing_session.management_user
    except Session.DoesNotExist:
        return None


def has_active_outright_ban(user):
    return UserBan.objects.active().filter(user=user, ban_type=BAN_TYPE_OUTRIGHT).exists()


def get_post_with_identifier(identifier):
    try:
        existing_post = Post.objects.get(post_identifier=identifier)
        return existing_post
    except Post.DoesNotExist:
        return None


def get_comment_thread_with_identifier(identifier):
    try:
        existing_comment_thread = CommentThread.objects.get(comment_thread_identifier=identifier)
        return existing_comment_thread
    except CommentThread.DoesNotExist:
        return None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_json_body(request):
    """Parses the request body as JSON, handles errors."""
    try:
        return json.loads(request.body)
    except json.JSONDecodeError:
        return None


def api_login_required(view_func):
    """
    Custom decorator to handle API token authentication.
    Reads 'Authorization: Bearer <token>' header, validates token,
    and attaches the user and token to the request object.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if not auth_header or not auth_header.startswith('Bearer '):
            return JsonResponse({'error': 'Authorization header missing or malformed'}, status=401)

        token = auth_header.split(' ')[1]

        if not is_valid_pattern(token, Patterns.alphanumeric):
            return JsonResponse({'error': 'Invalid token format'}, status=401)

        user = get_user_with_session_management_token(token)

        if user is None:
            return JsonResponse({'error': 'Invalid session token'}, status=401)

        if has_active_outright_ban(user):
            logger.warning(f"Request rejected: Account banned for user_id: {user.id}")
            return JsonResponse({'error': ACCOUNT_BANNED}, status=403)

        # Registration issues a session before the email is verified, so the
        # verification gate must sit here too, not just on the login views.
        if not user.email_verified:
            logger.warning(f"Request rejected: Email not verified for user_id: {user.id}")
            return JsonResponse({'error': EMAIL_NOT_VERIFIED}, status=403)

        # Attach user and token to the request for the view to use
        request.user = user
        request.token = token
        try:
            return view_func(request, *args, **kwargs)
        except Ratelimited:
            raise
        except Exception as e:
            logger.exception("Unhandled exception in view %s", view_func.__name__)
            return JsonResponse({'error': 'Internal server error'}, status=500)

    return _wrapped_view


def _record_device_and_maybe_notify(user, ip, notify=True):
    """Record that ``user`` has logged in from ``ip``.

    The first time we see an IP for a user (a brand-new device) we email them
    so they are alerted to the login. ``notify`` is set False for registration,
    where the user is plainly the one establishing the account and a "new login"
    alert would only be noise. A failure to send the email must never block the
    login itself, so it is logged and swallowed.
    """
    if not ip:
        return
    _, created = KnownDevice.objects.get_or_create(user=user, ip=ip)
    if not (created and notify):
        return
    try:
        send_mail(
            "New login to your account",
            "We noticed a login to your account from a new device "
            f"(IP address {ip}).\n\nIf this was you, you can ignore this email. "
            "If you don't recognize this activity, please reset your password right away.",
            settings.EMAIL_HOST_USER,
            [user.email],
        )
    except Exception:
        logger.exception(f"Failed to send new-device login email for user_id {user.id}")


def _issue_email_verification_token(user):
    """Generate and store a fresh email-verification token for ``user``.

    Only the SHA-256 hash is persisted; the raw token is returned so it can be
    embedded in the link emailed to the user (same scheme as password reset).

    Issuing a token means the address is not yet verified, so this is also the
    single place that flips ``email_verified`` to False. The model default is
    True (grandfathered-safe), so being explicit here is what actually gates the
    account created during registration.
    """
    token = secrets.token_urlsafe(32)
    user.email_verified = False
    user.email_verification_token = hashlib.sha256(token.encode()).hexdigest()
    user.email_verification_token_expires = timezone.now() + timedelta(hours=EMAIL_VERIFICATION_TOKEN_HOURS)
    user.save()
    return token


def _email_verification_link(token):
    return f"{settings.FRONTEND_BASE_URL}/verify-email?token={token}"


_TOTP_PERIOD_SECONDS = 30


def _verify_totp_code(user, code):
    """Check a submitted TOTP code, allowing one 30-second step of clock drift
    either way.

    On success the matched time step is recorded, and any step at or before
    the last accepted one is refused, so a code observed in transit cannot be
    replayed inside its validity window.
    """
    totp = pyotp.TOTP(user.totp_secret, interval=_TOTP_PERIOD_SECONDS)
    now = timezone.now()
    for offset in (-1, 0, 1):
        step_time = now + timedelta(seconds=_TOTP_PERIOD_SECONDS * offset)
        candidate_step = int(step_time.timestamp()) // _TOTP_PERIOD_SECONDS
        if user.totp_last_used_step is not None and candidate_step <= user.totp_last_used_step:
            continue
        if secrets.compare_digest(totp.at(step_time), code):
            user.totp_last_used_step = candidate_step
            user.save(update_fields=['totp_last_used_step'])
            return True
    return False


def _consume_recovery_code(user, code):
    """Mark the matching unused recovery code as spent. Returns whether one matched.

    Codes are stored with Django's password hasher (per-code salt, deliberately
    slow), so a database leak cannot be brute-forced offline the way a fast
    unsalted digest could. That salt means there is no single hash to look up
    by, so each unused code is checked in turn — there are only a handful. The
    rows are locked FOR UPDATE so two concurrent attempts cannot both spend the
    same code; callers therefore run this inside a transaction.
    """
    for recovery in user.recovery_codes.select_for_update().filter(used_at__isnull=True):
        if check_password(code, recovery.code_hash):
            recovery.used_at = timezone.now()
            recovery.save(update_fields=['used_at'])
            return True
    return False


def _issue_recovery_codes(user):
    """Replace the user's recovery codes with a fresh batch, returning the raw codes.

    Stored with Django's password hasher (salted + slow) rather than a bare
    SHA-256, so the persisted rows resist offline brute-force if the DB leaks.
    """
    user.recovery_codes.all().delete()
    raw_codes = [secrets.token_hex(LEN_RECOVERY_CODE_HEX // 2) for _ in range(NUM_RECOVERY_CODES)]
    RecoveryCode.objects.bulk_create([
        RecoveryCode(user=user, code_hash=make_password(code))
        for code in raw_codes
    ])
    return raw_codes


def _create_authenticated_session(view_name, request, user, ip, remember_me):
    """Final step of a successful authentication: Django session login, the
    remember-me cookie (when requested), the API session token, and the
    new-device email. Shared by login_user and login_user_2fa so a login that
    went through the two-factor challenge ends in exactly the same state as a
    plain one.
    """
    login(request, user)  # Logs into Django's session auth

    new_login_cookie = None
    if remember_me:
        new_login_cookie = user.logincookie_set.create(series_identifier=generate_series_identifier(),
                                                       token=generate_login_cookie_token())

    new_session = user.session_set.create(management_token=generate_management_token(), ip=ip)

    # Alert the user by email if this login is from a device (IP) we have
    # not seen for them before.
    _record_device_and_maybe_notify(user, ip)

    response_data = {
        Fields.session_management_token: new_session.management_token,
        Fields.username: user.username,
        Fields.user_id: user.id,
    }
    if remember_me and new_login_cookie:
        response_data[Fields.series_identifier] = new_login_cookie.series_identifier
        response_data[Fields.login_cookie_token] = new_login_cookie.token

    logger.info(f"Login successful for user_id: {user.id}")
    # The body carries the session token (and remember-me credentials), so keep
    # it out of any intermediary/proxy cache.
    response = log_and_return_json(view_name, response_data)
    response['Cache-Control'] = 'no-store'
    return response


# =============================================================================
# AUTHENTICATION VIEWS
# =============================================================================

@ratelimit(key=_get_client_ip, rate='5/h', block=True)
@csrf_exempt
@require_POST
def register(request):
    logger.info("Endpoint register invoked by IP or User")
    data = _get_json_body(request)
    if data is None:
        logger.warning("Registration failed: Invalid JSON data")
        return log_and_return_json("register", {'error': "Invalid JSON data"}, status=400)

    username = data.get(Fields.username)
    email = data.get(Fields.email)
    password = data.get(Fields.password)
    remember_me_str = data.get(Fields.remember_me)
    ip = _get_client_ip(None, request)
    date_of_birth_str = data.get('date_of_birth')

    invalid_fields = []
    if not username or not is_valid_pattern(username, Patterns.alphanumeric):
        invalid_fields.append(Params.username)
    if not email or not is_valid_pattern(email, Patterns.email):
        invalid_fields.append(Params.email)
    if not password or not is_valid_pattern(password, Patterns.password):
        invalid_fields.append(Params.password)

    is_adult = False
    if date_of_birth_str:
        try:
            dob = datetime.strptime(date_of_birth_str, '%Y-%m-%d').date()
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age >= 18:
                is_adult = True
        except ValueError:
            logger.warning("Registration failed: Invalid date_of_birth format")
            invalid_fields.append('date_of_birth')
    else:
        # If date_of_birth is mandatory, uncomment the next line
        # invalid_fields.append('date_of_birth')
        pass

    try:
        remember_me = convert_to_bool(remember_me_str)
    except TypeError:
        remember_me = False  # Default to false if invalid
        invalid_fields.append(Params.remember_me)

    if len(invalid_fields) > 0:
        logger.warning(f"Registration failed: Invalid fields {invalid_fields}")
        return log_and_return_json("register", {'error': f"Invalid fields {invalid_fields}"}, status=400)

    # Check no user has this email or username.
    if get_user_with_username(username) is not None or get_user_with_email(email) is not None:
        logger.warning("Registration failed: User already exists")
        return log_and_return_json("register", {'error': "User already exists"}, status=400)

    # Classify text fields for positivity
    username_result = text_classifier_class.is_text_positive(username)
    if not username_result:
        logger.warning(f"Registration failed: Username not positive")
        return log_and_return_json("register", {
            'error': f"Username is not positive because it {username_result.public_reason()}.",
            Fields.reason_code: username_result.public_reason_code(),
            # There is no account yet to appeal from; the user can simply retry
            # with a different username, so the rejection is never appealable.
            Fields.appealable: False,
        }, status=400)

    new_user = get_user_model().objects.create_user(username=username, email=email)
    new_user.set_password(password)
    new_user.identity_is_verified = True if date_of_birth_str else False
    new_user.is_adult = is_adult
    new_user.save()
   
    verification_token = _issue_email_verification_token(new_user)
    try:
        send_mail(
        "Welcome to Good Vibes Only",
        f"Hi {new_user.username},\n\nThank you for registering. "
        "Please verify your email address by clicking the link below:\n\n"
        f"{_email_verification_link(verification_token)}\n\n"
        f"The link expires in {EMAIL_VERIFICATION_TOKEN_HOURS} hours. "
        "You won't be able to log in until your email is verified.\n\n"
        "If you didn't create this account, ignore this email — without "
        "verification the account stays unusable.",
        settings.EMAIL_HOST_USER,
        [new_user.email],
        fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send welcome email for user: %s",new_user.id)
    new_login_cookie = None
    if remember_me:
        new_login_cookie = new_user.logincookie_set.create(series_identifier=generate_series_identifier(),
                                                           token=generate_login_cookie_token())
        # .create() already saves

    new_session = new_user.session_set.create(management_token=generate_management_token(), ip=ip)
    # .create() already saves

    # Record the registering device as known so the user's first real login
    # from it is not flagged as new, but don't email them about it.
    _record_device_and_maybe_notify(new_user, ip, notify=False)

    response_data = {
        Fields.session_management_token: new_session.management_token,
        Fields.user_id: new_user.id,
    }
    if remember_me and new_login_cookie:
        response_data[Fields.series_identifier] = new_login_cookie.series_identifier
        response_data[Fields.login_cookie_token] = new_login_cookie.token

    logger.info(f"Registration successful for user_id: {new_user.id}")
    return log_and_return_json("register", response_data, status=201)


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='5/h', block=True)
@require_POST
def verify_identity(request):
    logger.info("Endpoint verify_identity invoked by IP or User")
    data = _get_json_body(request)
    if data is None:
        logger.warning(f"Identity verification failed: Invalid JSON data for user_id: {request.user.id}")
        return log_and_return_json("verify_identity", {'error': "Invalid JSON data"}, status=400)

    date_of_birth_str = data.get('date_of_birth')

    if not date_of_birth_str:
         logger.warning(f"Identity verification failed: Missing date_of_birth for user_id: {request.user.id}")
         return log_and_return_json("verify_identity", {'error': "Missing date_of_birth"}, status=400)

    try:
        dob = datetime.strptime(date_of_birth_str, '%Y-%m-%d').date()
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

        request.user.identity_is_verified = True
        if age >= 18:
            request.user.is_adult = True
        else:
            request.user.is_adult = False

        request.user.save()

        logger.info(f"Identity verification successful for user_id: {request.user.id}")
        return log_and_return_json("verify_identity", {'message': 'Identity verified'})
    except ValueError:
        logger.warning(f"Identity verification failed: Invalid date format for user_id: {request.user.id}")
        return log_and_return_json("verify_identity", {'error': "Invalid date format, expected YYYY-MM-DD"}, status=400)


@ratelimit(key=_get_client_ip, rate='10/m', block=True)
@csrf_exempt
@require_POST
def login_user(request):
    logger.info("Endpoint login_user invoked by IP or User")
    data = _get_json_body(request)
    if data is None:
        logger.warning("Login failed: Invalid JSON data")
        return log_and_return_json("login_user", {'error': "Invalid JSON data"}, status=400)

    username_or_email = data.get(Fields.username_or_email)
    password = data.get(Fields.password)
    remember_me_str = data.get(Fields.remember_me)
    ip = _get_client_ip(None, request)

    invalid_fields = []
    if not username_or_email or (
            not is_valid_pattern(username_or_email, Patterns.alphanumeric) and not is_valid_pattern(username_or_email,
                                                                                                    Patterns.email)):
        invalid_fields.append(Params.username_or_email)
    if not password or not is_valid_pattern(password, Patterns.login_password):
        invalid_fields.append(Params.password)

    try:
        remember_me = convert_to_bool(remember_me_str)
    except TypeError:
        remember_me = False
        invalid_fields.append(Params.remember_me)
    if len(invalid_fields) > 0:
        return log_and_return_json("login_user", {'error': f"Invalid fields {invalid_fields}"}, status=400)

    existing = get_user_with_username_or_email(username_or_email)
    if existing is not None:
        if not check_password(password, existing.password):
            logger.warning(f"Login failed: Password was not correct for user_id: {existing.id}")
            return log_and_return_json("login_user", {'error': "Invalid username or password"}, status=400)

        if has_active_outright_ban(existing):
            logger.warning(f"Login failed: Account banned for user_id: {existing.id}")
            return log_and_return_json("login_user", {'error': ACCOUNT_BANNED}, status=403)

        if not existing.email_verified:
            logger.warning(f"Login failed: Email not verified for user_id: {existing.id}")
            return log_and_return_json("login_user", {'error': EMAIL_NOT_VERIFIED}, status=403)

        if existing.totp_enabled:
            # The password checked out, but the account requires a second
            # factor: hand back a short-lived challenge instead of a session.
            # login_user_2fa exchanges it for the real session. Delete every
            # existing challenge for the user first, so only one is ever valid
            # at a time — otherwise the per-challenge attempt limit could be
            # multiplied by requesting several challenges at once. The
            # delete-then-create runs under a row lock so two concurrent logins
            # can't interleave and leave more than one live challenge.
            raw_challenge = secrets.token_hex(32)
            with transaction.atomic():
                locked = get_user_model().objects.select_for_update().get(pk=existing.pk)
                locked.two_factor_challenges.all().delete()
                locked.two_factor_challenges.create(
                    token_hash=hashlib.sha256(raw_challenge.encode()).hexdigest(),
                    expires=timezone.now() + timedelta(minutes=TWO_FACTOR_CHALLENGE_MINUTES),
                    remember_me=remember_me,
                )
            logger.info(f"Login requires two-factor code for user_id: {existing.id}")
            response = log_and_return_json("login_user", {
                Fields.two_factor_required: True,
                Fields.challenge_token: raw_challenge,
            })
            response['Cache-Control'] = 'no-store'
            return response

        return _create_authenticated_session("login_user", request, existing, ip, remember_me)
    else:
        logger.warning("Login failed: No user exists with that information")
        return log_and_return_json("login_user", {'error': "Invalid username or password"}, status=400)


@ratelimit(key=_get_client_ip, rate='10/m', block=True)
@csrf_exempt
@require_POST
def login_user_with_remember_me(request):
    logger.info("Endpoint login_user_with_remember_me invoked by IP or User")
    data = _get_json_body(request)
    if data is None:
        logger.warning("Login with remember me failed: Invalid JSON data")
        return log_and_return_json("login_user_with_remember_me", {'error': "Invalid JSON data"}, status=400)

    session_management_token = data.get(Fields.session_management_token)
    series_identifier = data.get(Fields.series_identifier)
    login_cookie_token = data.get(Fields.login_cookie_token)
    ip = _get_client_ip(None, request)

    invalid_fields = []
    if not session_management_token or not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)
    if not series_identifier or not is_valid_pattern(series_identifier, Patterns.uuid4):
        invalid_fields.append(Params.series_identifier)
    if not login_cookie_token or not is_valid_pattern(login_cookie_token, Patterns.alphanumeric):
        invalid_fields.append(Params.login_cookie_token)

    if len(invalid_fields) > 0:
        return log_and_return_json("login_user_with_remember_me", {'error': f"Invalid fields {invalid_fields}"}, status=400)

    try:
        matching_login_cookie = LoginCookie.objects.get(series_identifier=series_identifier)
    except LoginCookie.DoesNotExist:
        logger.warning(f"Login with remember me failed: Series identifier does not exist: {series_identifier}")
        return log_and_return_json("login_user_with_remember_me", {'error': "Series identifier does not exist"}, status=400)
    except LoginCookie.MultipleObjectsReturned:
        logger.error(f"Login with remember me failed: Series identifier exists too many times: {series_identifier}")
        return log_and_return_json("login_user_with_remember_me", {'error': "Series identifier exists too many times"}, status=400)

    if matching_login_cookie.token != login_cookie_token:
        logger.warning(f"Login with remember me failed: Login cookie token does not match for series: {series_identifier}")
        return log_and_return_json("login_user_with_remember_me", {'error': "Login cookie token does not match"}, status=400)

    # Get the user with the *old* session management token. This must be
    # validated (and match the cookie's user) before the ban check and token
    # rotation, so a cookie for one user cannot be combined with a session
    # token for another.
    existing = get_user_with_session_management_token(session_management_token)
    if existing is None:
        logger.warning("Login with remember me failed: Original session token is invalid")
        return log_and_return_json("login_user_with_remember_me", {'error': "Original session token is invalid"}, status=400)

    if existing != matching_login_cookie.cookie_user:
        logger.warning(f"Login with remember me failed: Session token does not belong to the cookie's user for series: {series_identifier}")
        return log_and_return_json("login_user_with_remember_me", {'error': "Original session token is invalid"}, status=400)

    if has_active_outright_ban(existing):
        logger.warning(f"Login with remember me failed: Account banned for user_id: {existing.id}")
        return log_and_return_json("login_user_with_remember_me", {'error': ACCOUNT_BANNED}, status=403)

    if not existing.email_verified:
        logger.warning(f"Login with remember me failed: Email not verified for user_id: {existing.id}")
        return log_and_return_json("login_user_with_remember_me", {'error': EMAIL_NOT_VERIFIED}, status=403)

    # Issue a new login cookie token (token rotation)
    new_login_cookie_token = generate_login_cookie_token()
    matching_login_cookie.token = new_login_cookie_token
    matching_login_cookie.save()

    # Issue a new session management token
    new_session_management_token = generate_management_token()
    _ = existing.session_set.create(management_token=new_session_management_token, ip=ip)

    # Alert the user by email if this remember-me login is from a device (IP)
    # we have not seen for them before.
    _record_device_and_maybe_notify(existing, ip)

    response_data = {
        Fields.login_cookie_token: new_login_cookie_token,
        Fields.session_management_token: new_session_management_token
    }
    logger.info(f"Login with remember me successful for user_id: {existing.id}")
    return log_and_return_json("login_user_with_remember_me", response_data)


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='10/m', block=True)
@require_POST
def logout_user(request):
    logger.info("Endpoint logout_user invoked by IP or User")
    # request.user and request.token are added by the decorator
    try:
        # Find the specific session object and delete it to invalidate the token
        session = request.user.session_set.get(management_token=request.token)
        session.delete()
    except Session.DoesNotExist:
        # This could happen if the token is valid but the session was already deleted
        logger.warning(f"Logout failed: Session not found or already logged out for user_id: {request.user.id}")
        return log_and_return_json("logout_user", {'error': 'Session not found or already logged out'}, status=400)

    logout(request)  # Also log out of the standard Django session
    logger.info(f"Logout successful for user_id: {request.user.id}")
    return log_and_return_json("logout_user", {'message': 'Logout successful'})


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='5/h', block=True)
@require_POST
def delete_user(request):
    logger.info("Endpoint delete_user invoked by IP or User")
    # request.user is attached by the decorator
    try:
        user_to_delete = request.user
        user_id = user_to_delete.id
        logout(request)  # Log out of Django session first
        user_to_delete.delete()  # This will cascade and delete sessions, posts, etc.
        logger.info(f"User deleted successfully: user_id: {user_id}")
        return log_and_return_json("delete_user", {'message': 'User deleted successfully'})
    except Exception as e:
        logger.error(f"Error deleting user {request.user.id}: {e}")
        return log_and_return_json("delete_user", {'error': f"Error deleting user {e}"}, status=400)


# =============================================================================
# TWO-FACTOR AUTHENTICATION VIEWS
# =============================================================================

@ratelimit(key=_get_client_ip, rate='10/m', block=True)
@csrf_exempt
@require_POST
def login_user_2fa(request):
    """Second step of a two-factor login: exchange the challenge token from
    login_user plus a TOTP code (or a recovery code) for a real session."""
    logger.info("Endpoint login_user_2fa invoked by IP or User")
    data = _get_json_body(request)
    if data is None:
        return log_and_return_json("login_user_2fa", {'error': "Invalid JSON data"}, status=400)

    challenge_token = data.get(Fields.challenge_token)
    totp_code = data.get(Fields.totp_code)
    recovery_code = data.get(Fields.recovery_code)
    ip = _get_client_ip(None, request)

    invalid_fields = []
    if (not challenge_token or not isinstance(challenge_token, str)
            or not is_valid_pattern(challenge_token, Patterns.hex_token)):
        invalid_fields.append(Params.challenge_token)
    # Exactly one of the two code kinds must be supplied.
    if bool(totp_code) == bool(recovery_code):
        invalid_fields.extend([Params.totp_code, Params.recovery_code])
    elif totp_code and not (isinstance(totp_code, str) and is_valid_pattern(totp_code, Patterns.totp_code)):
        invalid_fields.append(Params.totp_code)
    elif recovery_code and not (isinstance(recovery_code, str)
                                and is_valid_pattern(recovery_code, Patterns.recovery_code)):
        invalid_fields.append(Params.recovery_code)
    if len(invalid_fields) > 0:
        return log_and_return_json("login_user_2fa", {'error': f"Invalid fields {invalid_fields}"}, status=400)

    submitted_hash = hashlib.sha256(challenge_token.encode()).hexdigest()

    # Find the challenge unlocked first, only to learn which user it belongs to.
    # The locks are then taken in a consistent order — the user row first, then
    # the challenge row — matching login_user and disable_totp, so these flows
    # can never deadlock by grabbing the two locks in opposite orders.
    challenge_ref = TwoFactorChallenge.objects.filter(token_hash=submitted_hash).first()
    if challenge_ref is None:
        logger.warning("Two-factor login failed: Invalid or expired challenge")
        return log_and_return_json("login_user_2fa", {'error': "Invalid or expired challenge"}, status=400)

    with transaction.atomic():
        # Lock the user row first: the replay guard (totp_last_used_step) and the
        # single-use recovery codes must not race a concurrent attempt.
        user = get_user_model().objects.select_for_update().get(pk=challenge_ref.user_id)
        challenge = TwoFactorChallenge.objects.select_for_update().filter(pk=challenge_ref.pk).first()
        if challenge is None or timezone.now() > challenge.expires:
            if challenge is not None:
                challenge.delete()
            logger.warning("Two-factor login failed: Invalid or expired challenge")
            return log_and_return_json("login_user_2fa", {'error': "Invalid or expired challenge"}, status=400)

        # Re-run the account gates from login_user; the account's state may
        # have changed between the password step and this one.
        if has_active_outright_ban(user):
            logger.warning(f"Two-factor login failed: Account banned for user_id: {user.id}")
            return log_and_return_json("login_user_2fa", {'error': ACCOUNT_BANNED}, status=403)
        if not user.email_verified:
            logger.warning(f"Two-factor login failed: Email not verified for user_id: {user.id}")
            return log_and_return_json("login_user_2fa", {'error': EMAIL_NOT_VERIFIED}, status=403)

        if totp_code:
            code_ok = bool(user.totp_secret) and _verify_totp_code(user, totp_code)
        else:
            code_ok = _consume_recovery_code(user, recovery_code)

        if not code_ok:
            challenge.failed_attempts += 1
            if challenge.failed_attempts >= TWO_FACTOR_MAX_ATTEMPTS:
                challenge.delete()
                logger.warning(
                    f"Two-factor login invalidated after {TWO_FACTOR_MAX_ATTEMPTS} "
                    f"failed attempts for user_id: {user.id}"
                )
                return log_and_return_json("login_user_2fa", {
                    'error': "Too many failed attempts. Log in again."
                }, status=429)
            challenge.save(update_fields=['failed_attempts'])
            logger.warning(f"Two-factor login failed: Invalid code for user_id: {user.id}")
            return log_and_return_json("login_user_2fa", {'error': "Invalid two-factor code"}, status=400)

        remember_me = challenge.remember_me
        challenge.delete()

    return _create_authenticated_session("login_user_2fa", request, user, ip, remember_me)


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='10/h', block=True)
@require_POST
def setup_totp(request):
    """Start TOTP enrollment: generate a secret and return it with the
    otpauth:// provisioning URI. Nothing is enforced until confirm_totp
    proves the authenticator works."""
    logger.info("Endpoint setup_totp invoked by IP or User")
    user = request.user

    if user.totp_enabled:
        return log_and_return_json("setup_totp",
                                   {'error': "Two-factor authentication is already enabled"}, status=400)

    # Re-running setup before confirming simply replaces the pending secret.
    user.totp_secret = pyotp.random_base32()
    user.totp_last_used_step = None
    user.save(update_fields=['totp_secret', 'totp_last_used_step'])

    # Set the interval explicitly so the otpauth:// period matches the
    # server-side verification window in _verify_totp_code.
    uri = pyotp.totp.TOTP(user.totp_secret, interval=_TOTP_PERIOD_SECONDS).provisioning_uri(
        name=user.email, issuer_name=TOTP_ISSUER)
    response = log_and_return_json("setup_totp", {
        Fields.totp_secret: user.totp_secret,
        Fields.otpauth_uri: uri,
    })
    response['Cache-Control'] = 'no-store'
    return response


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='10/h', block=True)
@require_POST
def confirm_totp(request):
    """Finish TOTP enrollment: verify one code from the authenticator, flip
    totp_enabled, and hand back the single batch of recovery codes."""
    logger.info("Endpoint confirm_totp invoked by IP or User")
    user = request.user
    data = _get_json_body(request)
    if data is None:
        return log_and_return_json("confirm_totp", {'error': "Invalid JSON data"}, status=400)

    totp_code = data.get(Fields.totp_code)
    if not totp_code or not isinstance(totp_code, str) or not is_valid_pattern(totp_code, Patterns.totp_code):
        return log_and_return_json("confirm_totp", {'error': f"Invalid fields ['{Params.totp_code}']"}, status=400)

    # Lock the user row so the replay guard in _verify_totp_code (which reads and
    # writes totp_last_used_step) cannot race a concurrent confirm/verify.
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=user.pk)

        if user.totp_enabled:
            return log_and_return_json("confirm_totp",
                                       {'error': "Two-factor authentication is already enabled"}, status=400)
        if not user.totp_secret:
            return log_and_return_json("confirm_totp",
                                       {'error': "Two-factor setup has not been started"}, status=400)

        if not _verify_totp_code(user, totp_code):
            logger.warning(f"TOTP confirmation failed: Invalid code for user_id: {user.id}")
            return log_and_return_json("confirm_totp", {'error': "Invalid two-factor code"}, status=400)

        user.totp_enabled = True
        user.save(update_fields=['totp_enabled'])
        raw_codes = _issue_recovery_codes(user)

    logger.info(f"Two-factor authentication enabled for user_id: {user.id}")
    response = log_and_return_json("confirm_totp", {
        Fields.totp_enabled: True,
        Fields.recovery_codes: raw_codes,
    })
    response['Cache-Control'] = 'no-store'
    return response


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='10/h', block=True)
@require_POST
def disable_totp(request):
    """Turn two-factor authentication off. Requires the account password plus
    a current TOTP code or an unused recovery code, so a stolen session alone
    cannot strip the protection."""
    logger.info("Endpoint disable_totp invoked by IP or User")
    user = request.user
    data = _get_json_body(request)
    if data is None:
        return log_and_return_json("disable_totp", {'error': "Invalid JSON data"}, status=400)

    password = data.get(Fields.password)
    totp_code = data.get(Fields.totp_code)
    recovery_code = data.get(Fields.recovery_code)

    invalid_fields = []
    if not password or not is_valid_pattern(password, Patterns.login_password):
        invalid_fields.append(Params.password)
    if bool(totp_code) == bool(recovery_code):
        invalid_fields.extend([Params.totp_code, Params.recovery_code])
    elif totp_code and not (isinstance(totp_code, str) and is_valid_pattern(totp_code, Patterns.totp_code)):
        invalid_fields.append(Params.totp_code)
    elif recovery_code and not (isinstance(recovery_code, str)
                                and is_valid_pattern(recovery_code, Patterns.recovery_code)):
        invalid_fields.append(Params.recovery_code)
    if len(invalid_fields) > 0:
        return log_and_return_json("disable_totp", {'error': f"Invalid fields {invalid_fields}"}, status=400)

    # Lock the user row for the whole check-and-disable so the TOTP replay guard
    # and single-use recovery-code consumption cannot race a concurrent request.
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=user.pk)

        if not user.totp_enabled:
            return log_and_return_json("disable_totp",
                                       {'error': "Two-factor authentication is not enabled"}, status=400)

        if not check_password(password, user.password):
            logger.warning(f"TOTP disable failed: Password was not correct for user_id: {user.id}")
            return log_and_return_json("disable_totp", {'error': "Invalid password"}, status=400)

        if totp_code:
            code_ok = _verify_totp_code(user, totp_code)
        else:
            code_ok = _consume_recovery_code(user, recovery_code)
        if not code_ok:
            logger.warning(f"TOTP disable failed: Invalid code for user_id: {user.id}")
            return log_and_return_json("disable_totp", {'error': "Invalid two-factor code"}, status=400)

        user.totp_secret = None
        user.totp_enabled = False
        user.totp_last_used_step = None
        user.save(update_fields=['totp_secret', 'totp_enabled', 'totp_last_used_step'])
        user.recovery_codes.all().delete()
        user.two_factor_challenges.all().delete()

    logger.info(f"Two-factor authentication disabled for user_id: {user.id}")
    return log_and_return_json("disable_totp", {Fields.totp_enabled: False})


# =============================================================================
# EMAIL VERIFICATION VIEWS
# =============================================================================

@ratelimit(key=_get_client_ip, rate='10/h', block=True)
@csrf_exempt
@require_POST
def verify_email(request):
    logger.info("Endpoint verify_email invoked by IP or User")
    data = _get_json_body(request)
    if data is None:
        return log_and_return_json("verify_email", {'error': "Invalid JSON data"}, status=400)

    verification_token = data.get(Fields.verification_token)

    _URLSAFE_TOKEN_LEN = 43
    _URLSAFE_TOKEN_CHARS = frozenset('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-')
    if (not verification_token or not isinstance(verification_token, str)
            or len(verification_token) != _URLSAFE_TOKEN_LEN
            or not all(c in _URLSAFE_TOKEN_CHARS for c in verification_token)):
        return log_and_return_json("verify_email", {'error': f"Invalid fields ['{Params.verification_token}']"},
                                   status=400)

    submitted_hash = hashlib.sha256(verification_token.encode()).hexdigest()

    # The token is looked up by its hash rather than paired with a username, so
    # the emailed link works on its own. Guessing a 256-bit token is infeasible,
    # and the endpoint is IP rate-limited on top.
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().filter(
            email_verification_token=submitted_hash).first()
        if (user is None or user.email_verification_token_expires is None
                or timezone.now() > user.email_verification_token_expires):
            logger.warning("Email verification failed: Invalid or expired token")
            return log_and_return_json("verify_email", {'error': "Invalid or expired verification token"}, status=400)

        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_token_expires = None
        user.save()

    logger.info(f"Email verification successful for user_id: {user.id}")
    return log_and_return_json("verify_email", {'message': 'Email verified'})


@ratelimit(key=_get_client_ip, rate='3/h', block=True)
@csrf_exempt
@require_POST
def resend_verification_email(request):
    logger.info("Endpoint resend_verification_email invoked by IP or User")
    data = _get_json_body(request)
    if data is None:
        return log_and_return_json("resend_verification_email", {'error': "Invalid JSON data"}, status=400)

    username_or_email = data.get(Fields.username_or_email)
    if not username_or_email or (
            not is_valid_pattern(username_or_email, Patterns.alphanumeric) and
            not is_valid_pattern(username_or_email, Patterns.email)):
        return log_and_return_json("resend_verification_email",
                                   {'error': f"Invalid fields ['{Params.username_or_email}']"}, status=400)

    user = get_user_with_username_or_email(username_or_email)
    if user is None:
        logger.warning("Resend verification failed: No user with that username or email")
        return log_and_return_json("resend_verification_email",
                                   {'error': "No user with that username or email"}, status=400)

    if user.email_verified:
        logger.warning(f"Resend verification failed: Email already verified for user_id: {user.id}")
        return log_and_return_json("resend_verification_email", {'error': "Email already verified"}, status=400)

    token = _issue_email_verification_token(user)
    try:
        send_mail(
            "Verify your email for Good Vibes Only",
            f"Hi {user.username},\n\nPlease verify your email address by clicking the link below:\n\n"
            f"{_email_verification_link(token)}\n\n"
            f"The link expires in {EMAIL_VERIFICATION_TOKEN_HOURS} hours.\n\n"
            "If you didn't request this, ignore this email — without "
            "verification the account stays unusable.",
            settings.EMAIL_HOST_USER,
            [user.email],
        )
    except Exception:
        logger.exception("Failed to send verification email for user: %s", user.id)
    logger.info(f"Resent verification email for user_id: {user.id}")
    return log_and_return_json("resend_verification_email", {'message': 'Verification email sent'})


# =============================================================================
# PASSWORD RESET VIEWS
# =============================================================================

@ratelimit(key=_get_client_ip, rate='3/h', block=True)
@csrf_exempt
@require_POST
def request_reset(request):
    logger.info("Endpoint request_reset invoked by IP or User")
    data = _get_json_body(request)
    if data is None:
        return log_and_return_json("request_reset", {'error': "Invalid JSON data"}, status=400)

    username_or_email = data.get(Fields.username_or_email)

    if not username_or_email or (
            not is_valid_pattern(username_or_email, Patterns.alphanumeric) and not is_valid_pattern(username_or_email,
                                                                                                    Patterns.email)):
        return log_and_return_json("request_reset", {'error': f"Invalid fields {Fields.username_or_email}"}, status=400)

    user = get_user_with_username_or_email(username_or_email)
    if user is not None:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        send_mail(
            "Password Reset",
            f"Your password reset verification token is:\n\n{token}\n\nEnter this in the app to proceed. It expires in 1 hour.",
            settings.EMAIL_HOST_USER,
            [user.email],
        )

        user.verification_token = token_hash
        user.verification_token_expires = timezone.now() + timedelta(hours=1)
        user.reset_token = None
        user.reset_token_expires = None
        user.verification_failed_attempts = 0
        user.verification_lockout_until = None
        user.save()
        logger.info(f"Password reset request successful for user_id: {user.id}")
        return log_and_return_json("request_reset", {'message': 'Reset email sent'})
    else:
        logger.warning("Password reset request failed: No user with that username or email")
        return log_and_return_json("request_reset", {'error': "No user with that username or email"}, status=400)


@ratelimit(key=_get_client_ip, rate='10/h', block=True)
@csrf_exempt
@require_POST
def verify_reset(request):
    logger.info("Endpoint verify_reset invoked by IP or User")
    data = _get_json_body(request)
    if data is None:
        return log_and_return_json("verify_reset", {'error': "Invalid JSON data"}, status=400)

    username_or_email = data.get(Fields.username_or_email)
    verification_token = data.get(Fields.verification_token)

    invalid_fields = []
    if not username_or_email or (
            not is_valid_pattern(username_or_email, Patterns.alphanumeric) and
            not is_valid_pattern(username_or_email, Patterns.email)):
        invalid_fields.append(Params.username_or_email)
    _URLSAFE_TOKEN_LEN = 43
    _URLSAFE_TOKEN_CHARS = frozenset('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-')
    if (not verification_token or not isinstance(verification_token, str)
            or len(verification_token) != _URLSAFE_TOKEN_LEN
            or not all(c in _URLSAFE_TOKEN_CHARS for c in verification_token)):
        invalid_fields.append(Params.verification_token)

    if len(invalid_fields) > 0:
        return log_and_return_json("verify_reset", {'error': f"Invalid fields {invalid_fields}"}, status=400)

    submitted_hash = hashlib.sha256(verification_token.encode()).hexdigest()

    user = get_user_with_username_or_email(username_or_email)
    if user is None:
        logger.warning("Password reset verification failed: No user with that username or email")
        return log_and_return_json("verify_reset", {'error': "No user with that username or email"}, status=400)

    # Fast-path lockout check before acquiring the row lock
    if user.verification_lockout_until and timezone.now() < user.verification_lockout_until:
        logger.warning(f"Password reset verification locked out for user_id: {user.id}")
        return log_and_return_json("verify_reset", {
            'error': "Too many failed attempts. Try again later."
        }, status=429)

    try:
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=user.pk)

            # Re-check lockout inside the atomic block to guard against races
            if user.verification_lockout_until and timezone.now() < user.verification_lockout_until:
                logger.warning(f"Password reset verification locked out for user_id: {user.id}")
                return log_and_return_json("verify_reset", {
                    'error': "Too many failed attempts. Try again later."
                }, status=429)

            if (user.verification_token and
                    secrets.compare_digest(user.verification_token, submitted_hash) and
                    user.verification_token_expires is not None and
                    timezone.now() <= user.verification_token_expires):
                reset_token = secrets.token_hex(32)
                user.verification_token = None
                user.verification_token_expires = None
                user.reset_token = hashlib.sha256(reset_token.encode()).hexdigest()
                user.reset_token_expires = timezone.now() + timedelta(minutes=15)
                user.verification_failed_attempts = 0
                user.verification_lockout_until = None
                user.save()
                logger.info(f"Password reset verification successful for user_id: {user.id}")
                response = log_and_return_json("verify_reset", {'message': 'Verification successful', 'reset_token': reset_token})
                response['Cache-Control'] = 'no-store'
                return response
            else:
                user.verification_failed_attempts += 1
                if user.verification_failed_attempts >= VERIFY_RESET_MAX_ATTEMPTS:
                    user.verification_lockout_until = timezone.now() + timedelta(minutes=VERIFY_RESET_LOCKOUT_MINUTES)
                    user.verification_failed_attempts = 0
                    user.save()
                    logger.warning(
                        f"Password reset verification locked out after {VERIFY_RESET_MAX_ATTEMPTS} "
                        f"attempts for user_id: {user.id}"
                    )
                    return log_and_return_json("verify_reset", {
                        'error': "Too many failed attempts. Try again later."
                    }, status=429)
                user.save()
                logger.warning(f"Password reset verification failed for user_id: {user.id}")
                return log_and_return_json("verify_reset", {'error': "Invalid or expired verification token"}, status=400)
    except get_user_model().DoesNotExist:
        logger.warning("Password reset verification failed: No user with that username or email")
        return log_and_return_json("verify_reset", {'error': "No user with that username or email"}, status=400)


@ratelimit(key=_get_client_ip, rate='10/h', block=True)
@csrf_exempt
@require_POST
def reset_password(request):
    logger.info("Endpoint reset_password invoked by IP or User")
    data = _get_json_body(request)
    if data is None:
        return log_and_return_json("reset_password", {'error': "Invalid JSON data"}, status=400)

    username = data.get(Fields.username)
    email = data.get(Fields.email)
    password = data.get(Fields.password)
    reset_token = data.get(Fields.reset_token)

    invalid_fields = []
    if not username or not is_valid_pattern(username, Patterns.alphanumeric):
        invalid_fields.append(Params.username)
    if not email or not is_valid_pattern(email, Patterns.email):
        invalid_fields.append(Params.email)
    if not password or not is_valid_pattern(password, Patterns.password):
        invalid_fields.append(Params.password)
    _HEX_TOKEN_LEN = 64
    if (not reset_token or not isinstance(reset_token, str)
            or len(reset_token) != _HEX_TOKEN_LEN
            or not all(c in '0123456789abcdef' for c in reset_token)):
        invalid_fields.append(Params.reset_token)

    if len(invalid_fields) > 0:
        return log_and_return_json("reset_password", {'error': f"Invalid fields {invalid_fields}"}, status=400)

    submitted_digest = hashlib.sha256(reset_token.encode()).hexdigest()

    try:
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(username=username, email=email)

            if not user.reset_token or not secrets.compare_digest(user.reset_token, submitted_digest):
                logger.warning(f"Password reset failed: Invalid reset token for user_id: {user.id}")
                return log_and_return_json("reset_password", {'error': "Invalid reset token"}, status=400)

            if user.reset_token_expires is None or timezone.now() > user.reset_token_expires:
                logger.warning(f"Password reset failed: Expired reset token for user_id: {user.id}")
                return log_and_return_json("reset_password", {'error': "Reset token has expired"}, status=400)

            user.set_password(password)
            user.reset_token = None
            user.reset_token_expires = None
            user.save()
            Session.objects.filter(management_user=user).delete()
            LoginCookie.objects.filter(cookie_user=user).delete()
    except get_user_model().DoesNotExist:
        logger.warning("Password reset failed: No user with that username or email")
        return log_and_return_json("reset_password", {'error': "No user with that username or email"}, status=400)

    logger.info(f"Password reset successful for user_id: {user.id}, username: {user.username}")
    return log_and_return_json("reset_password", {'message': 'Password reset successfully'})


# =============================================================================
# POST VIEWS
# =============================================================================

@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='20/h', block=True)
@require_POST
def create_upload_url(request):
    """Issue a short-lived presigned S3 PUT URL for a new post image.

    The backend generates the object key under the authenticated user's
    `{user_id}/` prefix, so key ownership is enforced server-side and clients
    need no AWS credentials of their own (the Cognito guest-role upload path
    allowed anonymous writes to the whole bucket — issue #310). The rate is
    double make_post's 10/h so a failed upload can be retried without burning
    a post slot.
    """
    logger.info("Endpoint create_upload_url invoked by IP or User")
    key = f"{request.user.id}/{uuid.uuid4()}.jpeg"
    upload_url, image_url = generate_presigned_upload(key)
    if not upload_url:
        return log_and_return_json("create_upload_url", {'error': "Could not create an upload URL"}, status=503)
    return log_and_return_json("create_upload_url", {
        Fields.upload_url: upload_url,
        Fields.image_url: image_url,
    })


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='10/h', block=True)
@require_POST
def make_post(request):
    logger.info("Endpoint make_post invoked by IP or User")
    # user is on request.user
    data = _get_json_body(request)
    if data is None:
        return log_and_return_json("make_post", {'error': "Invalid JSON data"}, status=400)

    # The image is optional (#307): missing, null, and "" all mean a text-only
    # post. A provided image must still pass pattern and user-scoping checks.
    raw_image_url = data.get(Fields.image_url)
    
    invalid_fields = []
    
    if raw_image_url in (None, ""):
        image_url = None
    elif not isinstance(raw_image_url, str):
        image_url = None
        invalid_fields.append(Params.image)
    else:
        image_url = raw_image_url
    
    caption = data.get(Fields.caption)
    
    if image_url:
        if not is_valid_pattern(image_url, Patterns.image_url):
            invalid_fields.append(Params.image)
        # The key must be scoped to this user (clients upload to `{user_id}/...`).
        elif not image_url_to_key(image_url).startswith(f"{request.user.id}/"):
            invalid_fields.append(Params.image)
    if not caption or not is_valid_pattern(caption, Patterns.alphanumeric_with_special_chars):
        invalid_fields.append(Params.caption)

    if len(invalid_fields) > 0:
        logger.warning(f"Make post failed: Invalid fields {invalid_fields} for user_id: {request.user.id}")
        return log_and_return_json("make_post", {'error': f"Invalid fields {invalid_fields}"}, status=400)

    if len(caption) > MAX_CAPTION_LENGTH:
        logger.warning(f"Make post failed: Caption too long ({len(caption)} chars) for user_id: {request.user.id}")
        return log_and_return_json("make_post", {'error': f"Caption exceeds maximum length of {MAX_CAPTION_LENGTH} characters"}, status=400)

    # The text and image classifiers each make external AI calls, so dispatch
    # them concurrently rather than back-to-back: when both outcomes are needed
    # the request waits on the slower of the two cascades instead of their sum,
    # which keeps post creation under the gateway timeout (the cause of the 504
    # in #274). We still only block on the image result when the text result
    # doesn't already settle the request (see below). A rejection that is not
    # appealable is final: reject outright and do not create the post. An
    # appealable rejection still creates the post but hides it pending appeal
    # (handled below).
    text_future = _CLASSIFICATION_EXECUTOR.submit(text_classifier_class.is_text_positive, caption)
    image_future = (_CLASSIFICATION_EXECUTOR.submit(image_classifier_class.is_image_positive, image_url)
                    if image_url else None)
    text_result = text_future.result()

    # Text rejection takes precedence in the message shown to the user, matching
    # the previous text-first ordering. A final (non-appealable) text rejection
    # is decisive, so return immediately without blocking on the image future:
    # the image cascade is the slower of the two, and waiting on it once the
    # outcome is already settled would needlessly hold the 400 path open and risk
    # the gateway timeout from #274. The image future still runs to completion in
    # the executor, so no worker is leaked.
    if not text_result and not text_result.appealable:
        logger.warning(f"Make post failed: Caption not positive (final) for user_id: {request.user.id}")
        # The post is never created, so clean up the image the client already
        # uploaded rather than orphaning it in S3.
        if image_url:
            delete_image(image_url)
        return log_and_return_json("make_post", {
            'error': f"Text is not positive because your caption {text_result.public_reason()}. "
                     "This decision is final and cannot be appealed.",
            Fields.reason_code: text_result.public_reason_code(),
            Fields.appealable: False,
        }, status=400)

    # Text passed (or is appealable), so the image outcome is now needed to
    # decide between rejection, an appealable hidden post, or a clean post.
    # A text-only post has no image to classify, so it is treated as allowed
    # and visibility depends solely on the text result.
    image_result = image_future.result() if image_future else ClassificationResult(allowed=True)

    if not image_result and not image_result.appealable:
        logger.warning(f"Make post failed: Image not positive (final) for user_id: {request.user.id}")
        delete_image(image_url)
        return log_and_return_json("make_post", {
            'error': f"Image is not positive because it {image_result.public_reason()}. "
                     "This decision is final and cannot be appealed.",
            Fields.reason_code: image_result.public_reason_code(),
            Fields.appealable: False,
        }, status=400)

    # Any remaining rejection is appealable, so post it but hide it pending
    # appeal. The visibility layer already shows authors their own hidden posts
    # while hiding them from everyone else, so no extra visibility wiring is
    # needed here.
    hidden = not (text_result and image_result)
    new_post = request.user.post_set.create(
        image_url=image_url, caption=caption, hidden=hidden,
        hidden_reason=HIDDEN_REASON_CLASSIFIER if hidden else HIDDEN_REASON_NONE)

    response = {Fields.post_identifier: new_post.post_identifier}
    if hidden:
        logger.info(f"Post created hidden pending appeal: post_id: {new_post.post_identifier} for user_id: {request.user.id}")
        blocked_parts = []
        if not text_result:
            blocked_parts.append(f"your caption {text_result.public_reason()}")
        if not image_result:
            blocked_parts.append(f"your image {image_result.public_reason()}")
        # Text precedence for the machine-readable code, matching the final-
        # rejection paths above.
        reason_result = text_result if not text_result else image_result
        response[Fields.hidden] = True
        response[Fields.hidden_reason] = HIDDEN_REASON_CLASSIFIER
        response[Fields.reason_code] = reason_result.public_reason_code()
        response[Fields.appealable] = True
        response['message'] = (f"Your post did not pass automated review because "
                               f"{' and '.join(blocked_parts)}. It is hidden for now "
                               "but you can appeal the decision.")
    else:
        logger.info(f"Post created successfully: post_id: {new_post.post_identifier} for user_id: {request.user.id}")
    return log_and_return_json("make_post", response, status=201)


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='30/h', block=True)
@require_POST  # Or @require_DELETE if you prefer
def delete_post(request, post_identifier):
    logger.info("Endpoint delete_post invoked by IP or User")
    # user is on request.user
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        return log_and_return_json("delete_post", {'error': f"Invalid fields {Fields.post_identifier}"}, status=400)

    try:
        post = request.user.post_set.get(post_identifier=post_identifier)
        image_url = post.image_url
        post.delete()
        # Remove the backing image from both buckets so deleting a post does not
        # orphan its S3 objects.
        delete_image(image_url)
        logger.info(f"Post deleted successfully: post_id: {post_identifier} by user_id: {request.user.id}")
        return log_and_return_json("delete_post", {'message': 'Post deleted'})
    except Post.DoesNotExist:
        logger.warning(f"Delete post failed: Post {post_identifier} not found for user_id: {request.user.id}")
        return log_and_return_json("delete_post", {'error': "No post with that identifier by that user"}, status=400)


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='20/h', block=True)
@require_POST
def report_post(request, post_identifier):
    logger.info("Endpoint report_post invoked by IP or User")
    # user is on request.user
    data = _get_json_body(request)
    if data is None:
        return log_and_return_json("report_post", {'error': "Invalid JSON data"}, status=400)

    reason = data.get(Fields.reason)

    invalid_fields = []
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if not reason or not is_valid_pattern(reason, Patterns.alphanumeric_with_special_chars):
        invalid_fields.append(Params.reason)

    if len(invalid_fields) > 0:
        return log_and_return_json("report_post", {'error': f"Invalid fields {invalid_fields}"}, status=400)

    post = get_post_with_identifier(post_identifier)
    if post is not None:
        if post.author == request.user:
            logger.warning(f"Report post failed: Cannot report own post for user_id: {request.user.id}")
            return log_and_return_json("report_post", {'error': "Cannot report own post"}, status=400)

        if post.postreport_set.filter(user=request.user).exists():
            logger.warning(f"Report post failed: Post already reported by user_id: {request.user.id}")
            return log_and_return_json("report_post", {'error': "Cannot report post twice"}, status=400)

        post.postreport_set.create(user=request.user, reason=reason)
        logger.info(f"Post reported successful: post_id: {post_identifier} by user_id: {request.user.id}")

        # Only hide (and stamp the reason) if it is not already hidden, so a
        # post already hidden by the classifier keeps its original reason and
        # the appeal flow can still tell why it was hidden.
        if not post.hidden and post.postreport_set.count() > MAX_BEFORE_HIDING_POST:
            post.hidden = True
            post.hidden_reason = HIDDEN_REASON_REPORTS
            post.save()
            logger.info(f"Post hidden due to reports: post_id: {post_identifier}")

        return log_and_return_json("report_post", {'message': 'Post reported'})
    else:
        logger.warning(f"Report post failed: Post {post_identifier} not found")
        return log_and_return_json("report_post", {'error': "No post with that identifier"}, status=400)


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='20/h', block=True)
@require_POST
def retract_report_post(request, post_identifier):
    logger.info("Endpoint retract_report_post invoked by IP or User")
    # user is on request.user
    invalid_fields = []
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if len(invalid_fields) > 0:
        return log_and_return_json("retract_report_post", {'error': f"Invalid fields {invalid_fields}"}, status=400)

    post = get_post_with_identifier(post_identifier)
    if post is None:
        logger.warning(f"Retract report post failed: Post {post_identifier} not found")
        return log_and_return_json("retract_report_post", {'error': "No post with that identifier"}, status=400)

    deleted_count, _ = post.postreport_set.filter(user=request.user).delete()
    if deleted_count == 0:
        logger.warning(f"Retract report post failed: Post not reported by user_id: {request.user.id}")
        return log_and_return_json("retract_report_post", {'error': "Post not reported yet"}, status=400)

    logger.info(f"Post report retracted: post_id: {post_identifier} by user_id: {request.user.id}")

    # If the retraction takes the report count back under the hiding threshold,
    # un-hide the post — but only when reports were what hid it. Content hidden
    # by the classifier or with no recorded reason stays hidden.
    if post.hidden and post.hidden_reason == HIDDEN_REASON_REPORTS \
            and post.postreport_set.count() <= MAX_BEFORE_HIDING_POST:
        post.hidden = False
        post.hidden_reason = HIDDEN_REASON_NONE
        post.save()
        logger.info(f"Post un-hidden after report retraction: post_id: {post_identifier}")

    return log_and_return_json("retract_report_post", {'message': 'Post report retracted'})


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='60/m', block=True)
@require_POST
def like_post(request, post_identifier):
    logger.info("Endpoint like_post invoked by IP or User")
    # user is on request.user
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        return log_and_return_json("like_post", {'error': f"Invalid fields {Fields.post_identifier}"}, status=400)

    post = get_post_with_identifier(post_identifier)
    if post is not None:
        if post.author == request.user:
            logger.warning(f"Like post failed: Cannot like own post for user_id: {request.user.id}")
            return log_and_return_json("like_post", {'error': "Cannot like own post"}, status=400)

        # get_or_create handles the check and creation in one step
        like, created = post.postlike_set.get_or_create(user=request.user)

        if not created:
            logger.warning(f"Like post failed: Already liked for user_id: {request.user.id} on post: {post_identifier}")
            return log_and_return_json("like_post", {'error': "Already liked post"}, status=400)

        logger.info(f"Post liked successful: post_id: {post_identifier} by user_id: {request.user.id}")
        return log_and_return_json("like_post", {'message': 'Post liked'})
    else:
        logger.warning(f"Like post failed: Post {post_identifier} not found")
        return log_and_return_json("like_post", {'error': "No post with that identifier"}, status=400)


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='60/m', block=True)
@require_POST  # Or @require_DELETE
def unlike_post(request, post_identifier):
    logger.info("Endpoint unlike_post invoked by IP or User")
    # user is on request.user
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        return log_and_return_json("unlike_post", {'error': f"Invalid fields {Fields.post_identifier}"}, status=400)

    post = get_post_with_identifier(post_identifier)
    if post is not None:
        if post.author == request.user:
            logger.warning(f"Unlike post failed: Cannot unlike own post for user_id: {request.user.id}")
            return log_and_return_json("unlike_post", {'error': "Cannot unlike own post"}, status=400)

        deleted_count, _ = post.postlike_set.filter(user=request.user).delete()

        if deleted_count > 0:
            logger.info(f"Post unliked successful: post_id: {post_identifier} by user_id: {request.user.id}")
            return log_and_return_json("unlike_post", {'message': 'Post unliked'})
        else:
            logger.warning(f"Unlike post failed: Post not liked yet for user_id: {request.user.id} on post: {post_identifier}")
            return log_and_return_json("unlike_post", {'error': "Post not liked yet"}, status=400)
    else:
        logger.warning(f"Unlike post failed: Post {post_identifier} not found")
        return log_and_return_json("unlike_post", {'error': "No post with that identifier"}, status=400)


# =============================================================================
# FEED / POST RETRIEVAL VIEWS
# =============================================================================

@api_login_required
@ratelimit(key='user', rate='60/m', block=True)
@require_GET
def get_posts_in_feed(request, batch):
    logger.info("Endpoint get_posts_in_feed invoked by IP or User")
    # user is on request.user
    if batch < 0:
        return log_and_return_json("get_posts_in_feed", {'error': "Invalid batch parameter"}, status=400)

    relevant_posts = feed_algorithm_class.get_posts_weighted(request.user, Post)

    # Filter out posts from users the current user has blocked or who have blocked the current user
    blocked_users = request.user.blocked.all()
    blocking_users = request.user.blocked_by.all()
    relevant_posts = relevant_posts.exclude(author__in=blocked_users).exclude(author__in=blocking_users)

    relevant_posts = visible_posts(relevant_posts, request.user)

    if relevant_posts.count() > 0:
        batched_posts = get_batch(batch, POST_BATCH_SIZE, relevant_posts)
        posts_data = [
            {
                Fields.post_identifier: post.post_identifier,
                Fields.image_url: get_compressed_image_url(post.image_url),
                # Full-res original, used as a client fallback while the async
                # Lambda-generated compressed copy is still missing (#252/#254).
                Fields.original_image_url: post.image_url,
                Fields.author_username: post.author.username,
                Fields.caption: post.caption
            }
            for post in batched_posts
        ]
        return log_and_return_json("get_posts_in_feed", posts_data, safe=False)
    else:
        return log_and_return_json("get_posts_in_feed", [], safe=False)


@api_login_required
@ratelimit(key='user', rate='60/m', block=True)
@require_GET
def get_posts_for_followed_users(request, batch):
    logger.info("Endpoint get_posts_for_followed_users invoked by IP or User")
    # user is on request.user
    if batch < 0:
        return log_and_return_json("get_posts_for_followed_users", {'error': "Invalid batch parameter"}, status=400)

    followed_users = request.user.following.all()

    # Filter out users who are blocked or blocking
    blocked_users = request.user.blocked.all()
    blocking_users = request.user.blocked_by.all()
    followed_users = followed_users.exclude(pk__in=blocked_users).exclude(pk__in=blocking_users)

    if not followed_users.exists():
        return log_and_return_json("get_posts_for_followed_users", [], safe=False)

    posts_queryset = visible_posts(
        Post.objects.filter(author__in=followed_users), request.user
    ).order_by('-creation_time')
    posts_batch = get_batch(batch, POST_BATCH_SIZE, posts_queryset)

    posts_data = [
        {
            Fields.post_identifier: post.post_identifier,
            Fields.image_url: get_compressed_image_url(post.image_url),
            # Full-res original, used as a client fallback while the async
            # Lambda-generated compressed copy is still missing (#252/#254).
            Fields.original_image_url: post.image_url,
            Fields.author_username: post.author.username,
            Fields.caption: post.caption
        }
        for post in posts_batch
    ]
    logger.info(f"Get followed posts successful for user_id: {request.user.id}, batch: {batch}, count: {len(posts_data)}")
    return log_and_return_json("get_posts_for_followed_users", posts_data, safe=False)


@api_login_required
@ratelimit(key='user', rate='60/m', block=True)
@require_GET
def get_posts_for_user(request, username, batch):
    logger.info("Endpoint get_posts_for_user invoked by IP or User")

    # user is on request.user (for auth), username is for target
    if not is_valid_pattern(username, Patterns.alphanumeric):
        return log_and_return_json("get_posts_for_user", {'error': "Invalid username"}, status=400)
    if batch < 0:
        return log_and_return_json("get_posts_for_user", {'error': "Invalid batch parameter"}, status=400)

    target_user = get_user_with_username(username)
    if not target_user:
        return log_and_return_json("get_posts_for_user", {'error': "User not found"}, status=400)

    # Check if blocking relationship exists
    if request.user.blocked.filter(pk=target_user.pk).exists() or target_user.blocked.filter(pk=request.user.pk).exists():
        logger.info(f"Get posts for user: Blocking relationship exists for user_id: {request.user.id} and target_user_id: {target_user.id}")
        return log_and_return_json("get_posts_for_user", [], safe=False)

    relevant_posts = visible_posts(
        feed_algorithm_class.get_posts_weighted_for_user(target_user, Post), request.user
    )

    if relevant_posts.count() > 0:
        batched_posts = get_batch(batch, POST_BATCH_SIZE, relevant_posts)
        posts_data = [
            {
                Fields.post_identifier: post.post_identifier,
                Fields.image_url: get_compressed_image_url(post.image_url),
                # The full-resolution original, used by clients as a fallback when
                # the compressed copy 404s. Compression runs in an async Lambda, so
                # a just-posted (or recently hidden-pending-appeal) image can be
                # missing from the compressed bucket for a short while — without a
                # fallback those tiles render as empty grey/black boxes until the
                # user re-logs in. See issues #252 and #254.
                Fields.original_image_url: post.image_url,
                Fields.caption: post.caption,
                Fields.author_username: target_user.username
            }
            for post in batched_posts
        ]
        return log_and_return_json("get_posts_for_user", posts_data, safe=False)
    else:
        return log_and_return_json("get_posts_for_user", [], safe=False)


@api_login_required
@ratelimit(key='user', rate='60/m', block=True)
@require_GET
def get_post_details(request, post_identifier):
    logger.info("Endpoint get_post_details invoked by IP or User")
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        return log_and_return_json("get_post_details", {'error': "Invalid post identifier"}, status=400)

    post = get_post_with_identifier(post_identifier)
    if post is not None and can_view_post(post, request.user):
        total_likes = post.postlike_set.count()
        # The caller's own report (if any), so clients can offer "retract
        # report" with the original reason pre-filled instead of "report".
        my_report = post.postreport_set.filter(user=request.user).first()
        post_data = {
            Fields.post_identifier: post.post_identifier,
            Fields.image_url: get_compressed_image_url(post.image_url),
            # Full-res original, used as a client fallback while the async
            # Lambda-generated compressed copy is still missing (#252/#254).
            Fields.original_image_url: post.image_url,
            Fields.caption: post.caption,
            Fields.creation_time: post.creation_time,
            Fields.post_likes: total_likes,
            Fields.is_liked: post.postlike_set.filter(user=request.user).exists(),
            Fields.is_reported: my_report is not None,
            Fields.report_reason: my_report.reason if my_report is not None else None,
            Fields.author_username: post.author.username
        }
        return log_and_return_json("get_post_details", post_data)
    else:
        logger.warning(f"Get post details failed: Post {post_identifier} not found")
        return log_and_return_json("get_post_details", {'error': "No post with that identifier"}, status=400)


# =============================================================================
# COMMENT VIEWS
# =============================================================================

@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='20/h', block=True)
@require_POST
def comment_on_post(request, post_identifier):
    logger.info("Endpoint comment_on_post invoked by IP or User")
    # user is on request.user
    data = _get_json_body(request)
    if data is None:
        return log_and_return_json("comment_on_post", {'error': "Invalid JSON data"}, status=400)

    comment_text = data.get(Fields.comment_text)

    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        return log_and_return_json("comment_on_post", {'error': "Invalid post_identifier"}, status=400)
    if not comment_text or not is_valid_pattern(comment_text, Patterns.alphanumeric_with_special_chars):
        return log_and_return_json("comment_on_post", {'error': "Invalid comment text"}, status=400)
    if len(comment_text) > MAX_COMMENT_LENGTH:
        return log_and_return_json("comment_on_post", {'error': f"Comment exceeds maximum length of {MAX_COMMENT_LENGTH} characters"}, status=400)

    # Resolve and visibility-check the post before running the (expensive) AI
    # classifier, so a leaked/guessed UUID for a missing or hidden post cannot
    # trigger classifier calls (avoidable cost / billing amplification). Treat a
    # post the caller cannot see (hidden, or by a shadow-banned author) the same
    # as a missing one so its existence is not revealed.
    post = get_post_with_identifier(post_identifier)
    if post is None or not can_view_post(post, request.user):
        logger.warning(f"Comment on post failed: Post {post_identifier} not found or not visible")
        return log_and_return_json("comment_on_post", {'error': "No post with that identifier"}, status=400)

    # A final (non-appealable) rejection blocks the comment; an appealable one
    # creates it hidden pending appeal.
    text_result = text_classifier_class.is_text_positive(comment_text)
    if not text_result and not text_result.appealable:
        return log_and_return_json("comment_on_post", {
            'error': f"Text is not positive because your comment {text_result.public_reason()}. "
                     "This decision is final and cannot be appealed.",
            Fields.reason_code: text_result.public_reason_code(),
            Fields.appealable: False,
        }, status=400)

    hidden = not text_result

    # Create a new thread for this top-level comment
    comment_thread = post.commentthread_set.create()
    new_comment = comment_thread.comment_set.create(
        author=request.user, body=comment_text, hidden=hidden,
        hidden_reason=HIDDEN_REASON_CLASSIFIER if hidden else HIDDEN_REASON_NONE)

    response_data = {
        Fields.comment_thread_identifier: comment_thread.comment_thread_identifier,
        Fields.comment_identifier: new_comment.comment_identifier
    }
    if hidden:
        logger.info(f"Comment on post created hidden pending appeal: comment_id: {new_comment.comment_identifier} for user_id: {request.user.id}")
        response_data[Fields.hidden] = True
        response_data[Fields.hidden_reason] = HIDDEN_REASON_CLASSIFIER
        response_data[Fields.reason_code] = text_result.public_reason_code()
        response_data[Fields.appealable] = True
        response_data['message'] = (f"Your comment did not pass automated review because it "
                                    f"{text_result.public_reason()}. It is hidden for now "
                                    "but you can appeal the decision.")
    else:
        logger.info(f"Comment on post successful: post_id: {post_identifier}, comment_id: {new_comment.comment_identifier} for user_id: {request.user.id}")
    return log_and_return_json("comment_on_post", response_data, status=201)


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='20/h', block=True)
@require_POST
def reply_to_comment_thread(request, post_identifier, comment_thread_identifier):
    logger.info("Endpoint reply_to_comment_thread invoked by IP or User")
    # user is on request.user
    data = _get_json_body(request)
    if data is None:
        return log_and_return_json("reply_to_comment_thread", {'error': "Invalid JSON data"}, status=400)

    comment_text = data.get(Fields.comment_text)

    invalid_fields = []
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if not is_valid_pattern(comment_thread_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_thread_identifier)
    if not comment_text or not is_valid_pattern(comment_text, Patterns.alphanumeric_with_special_chars):
        invalid_fields.append(Params.comment_text)

    if len(invalid_fields) > 0:
        return log_and_return_json("reply_to_comment_thread", {'error': f"Invalid fields {invalid_fields}"}, status=400)

    if len(comment_text) > MAX_COMMENT_LENGTH:
        return log_and_return_json("reply_to_comment_thread", {'error': f"Comment exceeds maximum length of {MAX_COMMENT_LENGTH} characters"}, status=400)

    # Resolve and visibility-check the thread/parent post before running the
    # (expensive) AI classifier, so a leaked/guessed UUID for a missing or
    # hidden thread cannot trigger classifier calls (avoidable cost / billing
    # amplification). A caller who cannot see the parent post is treated as if
    # the thread is not there so its existence is not revealed.
    try:
        comment_thread = CommentThread.objects.get(
            comment_thread_identifier=comment_thread_identifier,
            post__post_identifier=post_identifier
        )
    except CommentThread.DoesNotExist:
        return log_and_return_json("reply_to_comment_thread", {'error': "Comment thread not found for the given post"}, status=400)

    if not can_view_post(comment_thread.post, request.user):
        return log_and_return_json("reply_to_comment_thread", {'error': "Comment thread not found for the given post"}, status=400)

    # A final (non-appealable) rejection blocks the reply; an appealable one
    # creates it hidden pending appeal.
    text_result = text_classifier_class.is_text_positive(comment_text)
    if not text_result and not text_result.appealable:
        return log_and_return_json("reply_to_comment_thread", {
            'error': f"Text is not positive because your reply {text_result.public_reason()}. "
                     "This decision is final and cannot be appealed.",
            Fields.reason_code: text_result.public_reason_code(),
            Fields.appealable: False,
        }, status=400)

    hidden = not text_result
    new_comment = comment_thread.comment_set.create(
        author=request.user, body=comment_text, hidden=hidden,
        hidden_reason=HIDDEN_REASON_CLASSIFIER if hidden else HIDDEN_REASON_NONE)

    response_data = {Fields.comment_identifier: new_comment.comment_identifier}
    if hidden:
        logger.info(f"Reply created hidden pending appeal: comment_id: {new_comment.comment_identifier} for user_id: {request.user.id}")
        response_data[Fields.hidden] = True
        response_data[Fields.hidden_reason] = HIDDEN_REASON_CLASSIFIER
        response_data[Fields.reason_code] = text_result.public_reason_code()
        response_data[Fields.appealable] = True
        response_data['message'] = (f"Your reply did not pass automated review because it "
                                    f"{text_result.public_reason()}. It is hidden for now "
                                    "but you can appeal the decision.")
    else:
        logger.info(f"Reply to comment successful: comment_thread_id: {comment_thread_identifier}, comment_id: {new_comment.comment_identifier} for user_id: {request.user.id}")
    return log_and_return_json("reply_to_comment_thread", response_data, status=201)


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='60/m', block=True)
@require_POST
def like_comment(request, post_identifier, comment_thread_identifier, comment_identifier):
    logger.info("Endpoint like_comment invoked by IP or User")
    # user is on request.user
    invalid_fields = []
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if not is_valid_pattern(comment_thread_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_thread_identifier)
    if not is_valid_pattern(comment_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_identifier)
    if len(invalid_fields) > 0:
        return log_and_return_json("like_comment", {'error': f"Invalid fields {invalid_fields}"}, status=400)

    try:
        comment = Comment.objects.get(
            comment_identifier=comment_identifier,
            comment_thread__comment_thread_identifier=comment_thread_identifier,
            comment_thread__post__post_identifier=post_identifier
        )
    except Comment.DoesNotExist:
        logger.warning(f"Like comment failed: Comment {comment_identifier} not found")
        return log_and_return_json("like_comment", {'error': "Comment not found"}, status=400)

    if comment.author == request.user:
        logger.warning(f"Like comment failed: Cannot like own comment for user_id: {request.user.id}")
        return log_and_return_json("like_comment", {'error': "Cannot like own comment"}, status=400)

    like, created = comment.commentlike_set.get_or_create(user=request.user)
    if not created:
        logger.warning(f"Like comment failed: Already liked for user_id: {request.user.id} on comment: {comment_identifier}")
        return log_and_return_json("like_comment", {'error': "Already liked comment"}, status=400)

    logger.info(f"Like comment successful: comment_id: {comment_identifier} for user_id: {request.user.id}")
    return log_and_return_json("like_comment", {'message': 'Comment liked'})


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='60/m', block=True)
@require_POST  # Or @require_DELETE
def unlike_comment(request, post_identifier, comment_thread_identifier, comment_identifier):
    logger.info("Endpoint unlike_comment invoked by IP or User")
    # user is on request.user
    invalid_fields = []
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if not is_valid_pattern(comment_thread_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_thread_identifier)
    if not is_valid_pattern(comment_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_identifier)
    if len(invalid_fields) > 0:
        return log_and_return_json("unlike_comment", {'error': f"Invalid fields {invalid_fields}"}, status=400)

    try:
        comment = Comment.objects.get(
            comment_identifier=comment_identifier,
            comment_thread__comment_thread_identifier=comment_thread_identifier,
            comment_thread__post__post_identifier=post_identifier
        )
    except Comment.DoesNotExist:
        logger.warning(f"Unlike comment failed: Comment {comment_identifier} not found")
        return log_and_return_json("unlike_comment", {'error': "Comment not found"}, status=400)

    if comment.author == request.user:
        logger.warning(f"Unlike comment failed: Cannot unlike own comment for user_id: {request.user.id}")
        return log_and_return_json("unlike_comment", {'error': "Cannot unlike own comment"}, status=400)

    deleted_count, _ = comment.commentlike_set.filter(user=request.user).delete()
    if deleted_count == 0:
        logger.warning(f"Unlike comment failed: Comment not liked yet for user_id: {request.user.id} on comment: {comment_identifier}")
        return log_and_return_json("unlike_comment", {'error': "Comment not liked yet"}, status=400)

    logger.info(f"Unlike comment successful: comment_id: {comment_identifier} for user_id: {request.user.id}")
    return log_and_return_json("unlike_comment", {'message': 'Comment unliked'})


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='30/h', block=True)
@require_POST  # Or @require_DELETE
def delete_comment(request, post_identifier, comment_thread_identifier, comment_identifier):
    logger.info("Endpoint delete_comment invoked by IP or User")
    # user is on request.user
    invalid_fields = []
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if not is_valid_pattern(comment_thread_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_thread_identifier)
    if not is_valid_pattern(comment_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_identifier)
    if len(invalid_fields) > 0:
        return log_and_return_json("delete_comment", {'error': f"Invalid fields {invalid_fields}"}, status=400)

    try:
        comment = Comment.objects.get(
            comment_identifier=comment_identifier,
            comment_thread__comment_thread_identifier=comment_thread_identifier,
            comment_thread__post__post_identifier=post_identifier
        )
    except Comment.DoesNotExist:
        logger.warning(f"Delete comment failed: Comment {comment_identifier} not found")
        return log_and_return_json("delete_comment", {'error': "Comment not found"}, status=400)

    if comment.author != request.user:
        logger.warning(f"Delete comment failed: Unauthorized for user_id: {request.user.id} on comment: {comment_identifier}")
        return log_and_return_json("delete_comment", {'error': "Not authorized to delete comment"}, status=400)

    comment.delete()
    logger.info(f"Delete comment successful: comment_id: {comment_identifier} for user_id: {request.user.id}")
    return log_and_return_json("delete_comment", {'message': 'Comment deleted'})


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='20/h', block=True)
@require_POST
def report_comment(request, post_identifier, comment_thread_identifier, comment_identifier):
    logger.info("Endpoint report_comment invoked by IP or User")
    # user is on request.user
    data = _get_json_body(request)
    if data is None:
        return log_and_return_json("report_comment", {'error': "Invalid JSON data"}, status=400)

    reason = data.get(Fields.reason)

    invalid_fields = []
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if not is_valid_pattern(comment_thread_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_thread_identifier)
    if not is_valid_pattern(comment_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_identifier)
    if not reason or not is_valid_pattern(reason, Patterns.alphanumeric_with_special_chars):
        invalid_fields.append(Params.reason)
    if len(invalid_fields) > 0:
        return log_and_return_json("report_comment", {'error': f"Invalid fields {invalid_fields}"}, status=400)

    try:
        comment = Comment.objects.get(
            comment_identifier=comment_identifier,
            comment_thread__comment_thread_identifier=comment_thread_identifier,
            comment_thread__post__post_identifier=post_identifier
        )
    except Comment.DoesNotExist:
        logger.warning(f"Report comment failed: Comment {comment_identifier} not found")
        return log_and_return_json("report_comment", {'error': "Comment not found"}, status=400)

    if comment.author == request.user:
        logger.warning(f"Report comment failed: Cannot report own comment for user_id: {request.user.id}")
        return log_and_return_json("report_comment", {'error': "Cannot report own comment"}, status=400)

    if comment.commentreport_set.filter(user=request.user).exists():
        logger.warning(f"Report comment failed: Already reported by user_id: {request.user.id}")
        return log_and_return_json("report_comment", {'error': "Cannot report comment twice"}, status=400)

    comment.commentreport_set.create(user=request.user, reason=reason)
    logger.info(f"Report comment successful: comment_id: {comment_identifier} by user_id: {request.user.id}")

    # Only hide (and stamp the reason) if it is not already hidden, so a comment
    # already hidden by the classifier keeps its original reason.
    if not comment.hidden and comment.commentreport_set.count() > MAX_BEFORE_HIDING_COMMENT:
        comment.hidden = True
        comment.hidden_reason = HIDDEN_REASON_REPORTS
        comment.save()
        logger.info(f"Comment hidden due to reports: comment_id: {comment_identifier}")

    return log_and_return_json("report_comment", {'message': 'Comment reported'})


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='20/h', block=True)
@require_POST
def retract_report_comment(request, post_identifier, comment_thread_identifier, comment_identifier):
    logger.info("Endpoint retract_report_comment invoked by IP or User")
    # user is on request.user
    invalid_fields = []
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if not is_valid_pattern(comment_thread_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_thread_identifier)
    if not is_valid_pattern(comment_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_identifier)
    if len(invalid_fields) > 0:
        return log_and_return_json("retract_report_comment", {'error': f"Invalid fields {invalid_fields}"}, status=400)

    try:
        comment = Comment.objects.get(
            comment_identifier=comment_identifier,
            comment_thread__comment_thread_identifier=comment_thread_identifier,
            comment_thread__post__post_identifier=post_identifier
        )
    except Comment.DoesNotExist:
        logger.warning(f"Retract report comment failed: Comment {comment_identifier} not found")
        return log_and_return_json("retract_report_comment", {'error': "Comment not found"}, status=400)

    deleted_count, _ = comment.commentreport_set.filter(user=request.user).delete()
    if deleted_count == 0:
        logger.warning(f"Retract report comment failed: Comment not reported by user_id: {request.user.id}")
        return log_and_return_json("retract_report_comment", {'error': "Comment not reported yet"}, status=400)

    logger.info(f"Comment report retracted: comment_id: {comment_identifier} by user_id: {request.user.id}")

    # If the retraction takes the report count back under the hiding threshold,
    # un-hide the comment — but only when reports were what hid it. Content
    # hidden by the classifier or with no recorded reason stays hidden.
    if comment.hidden and comment.hidden_reason == HIDDEN_REASON_REPORTS \
            and comment.commentreport_set.count() <= MAX_BEFORE_HIDING_COMMENT:
        comment.hidden = False
        comment.hidden_reason = HIDDEN_REASON_NONE
        comment.save()
        logger.info(f"Comment un-hidden after report retraction: comment_id: {comment_identifier}")

    return log_and_return_json("retract_report_comment", {'message': 'Comment report retracted'})


@api_login_required  # Original had @login_required
@ratelimit(key='user', rate='60/m', block=True)
@require_GET
def get_comments_for_post(request, post_identifier, batch):
    logger.info("Endpoint get_comments_for_post invoked by IP or User")
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        return log_and_return_json("get_comments_for_post", {'error': "Invalid post identifier"}, status=400)
    if batch < 0:
        return log_and_return_json("get_comments_for_post", {'error': "Invalid batch parameter"}, status=400)

    post = get_post_with_identifier(post_identifier)
    if not post or not can_view_post(post, request.user):
        logger.warning(f"Get comments for post failed: Post {post_identifier} not found or not visible")
        return log_and_return_json("get_comments_for_post", {'error': "No post with that identifier"}, status=400)

    comment_threads = visible_comment_threads(post.commentthread_set.all(), request.user)

    relevant_comment_threads = feed_algorithm_class.get_comment_threads_weighted_for_post(comment_threads)

    if not relevant_comment_threads.count() > 0:
        return log_and_return_json("get_comments_for_post", [], safe=False)

    batched_comment_threads = get_batch(batch, COMMENT_THREAD_BATCH_SIZE, relevant_comment_threads)
    data = [{Fields.comment_thread_identifier: ct.comment_thread_identifier} for ct in batched_comment_threads]
    return log_and_return_json("get_comments_for_post", data, safe=False)


@api_login_required  # Original had @login_required
@ratelimit(key='user', rate='60/m', block=True)
@require_GET
def get_comments_for_thread(request, comment_thread_identifier, batch):
    logger.info("Endpoint get_comments_for_thread invoked by IP or User")
    if not is_valid_pattern(comment_thread_identifier, Patterns.uuid4):
        return log_and_return_json("get_comments_for_thread", {'error': "Invalid comment thread identifier"}, status=400)
    if batch < 0:
        return log_and_return_json("get_comments_for_thread", {'error': "Invalid batch parameter"}, status=400)

    comment_thread = get_comment_thread_with_identifier(comment_thread_identifier)
    if not comment_thread or not can_view_post(comment_thread.post, request.user):
        logger.warning(f"Get comments for thread failed: Thread {comment_thread_identifier} not found or not visible")
        return log_and_return_json("get_comments_for_thread", {'error': "No comment thread with that identifier"}, status=400)

    comments = visible_comments(comment_thread.comment_set.all(), request.user).order_by('creation_time')
    relevant_comments = feed_algorithm_class.get_comments_weighted_for_thread(comments)

    if not relevant_comments.count() > 0:
        return log_and_return_json("get_comments_for_thread", [], safe=False)

    batched_comments = get_batch(batch, COMMENT_BATCH_SIZE, relevant_comments)
    # Single query to find which of these comments the requesting user has liked,
    # avoiding an N+1 .exists() call per comment.
    liked_comment_ids = set(
        request.user.commentlike_set
        .filter(comment__in=batched_comments)
        .values_list('comment_id', flat=True)
    )
    # The caller's own report reason per comment (single query, like the likes
    # set above), so clients can offer "retract report" with the original
    # reason pre-filled instead of "report".
    my_report_reasons = dict(
        request.user.commentreport_set
        .filter(comment__in=batched_comments)
        .values_list('comment_id', 'reason')
    )
    # Like counts for the whole batch in one grouped query, so we avoid a
    # per-comment COUNT (N+1) inside the comprehension below.
    like_counts = dict(
        CommentLike.objects
        .filter(comment__in=batched_comments)
        .values('comment_id')
        .annotate(count=Count('comment_id'))
        .values_list('comment_id', 'count')
    )
    comments_data = [
        {
            Fields.comment_identifier: comment.comment_identifier,
            Fields.body: comment.body,
            Fields.author_username: comment.author.username,
            Fields.creation_time: comment.creation_time,
            Fields.updated_time: comment.updated_time,
            Fields.comment_likes: like_counts.get(comment.comment_identifier, 0),
            Fields.is_liked: comment.comment_identifier in liked_comment_ids,
            Fields.is_reported: comment.comment_identifier in my_report_reasons,
            Fields.report_reason: my_report_reasons.get(comment.comment_identifier)
        }
        for comment in batched_comments
    ]
    return log_and_return_json("get_comments_for_thread", comments_data, safe=False)


# =============================================================================
# USER / PROFILE VIEWS
# =============================================================================

@api_login_required
@ratelimit(key='user', rate='30/m', block=True)
@require_GET
def get_users_matching_fragment(request, username_fragment):
    logger.info("Endpoint get_users_matching_fragment invoked by IP or User")
    # user is on request.user
    if not is_valid_pattern(username_fragment, Patterns.short_alphanumeric):
        return log_and_return_json("get_users_matching_fragment", {'error': "Invalid username fragment"}, status=400)

    # We only get the first 10 users because we don't support endlessly scrolling through
    # user results in the search bar.
    users = PositiveOnlySocialUser.objects.filter(
        username__istartswith=username_fragment
    ).exclude(pk=request.user.pk)

    # User B cannot search for User A if User A blocked User B.
    # request.user is B (searcher). We must exclude any user A who has blocked B.
    # We must also exclude users that B has blocked? Spec says: "If user A blocks user B then user A can search for user B"
    # So if I blocked someone, I can still search them.
    # But if someone blocked me, I cannot search them.
    users_who_blocked_me = request.user.blocked_by.all()
    users = searchable_users(users.exclude(pk__in=users_who_blocked_me))[:10]

    users_data = [
        {
            Fields.username: user.username,
            Fields.identity_is_verified: user.identity_is_verified
        }
        for user in users
    ]
    logger.info(f"User search matching fragment successful: count: {len(users_data)} for user_id: {request.user.id}")
    return log_and_return_json("get_users_matching_fragment", users_data, safe=False)


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='30/m', block=True)
@require_POST
def follow_user(request, username_to_follow):
    logger.info("Endpoint follow_user invoked by IP or User")
    # user is on request.user
    if not is_valid_pattern(username_to_follow, Patterns.alphanumeric):
        return log_and_return_json("follow_user", {'error': "Invalid username fragment"}, status=400)

    user_to_follow_obj = get_user_with_username(username_to_follow)
    if not user_to_follow_obj:
        return log_and_return_json("follow_user", {'error': "User does not exist"}, status=400)

    if request.user == user_to_follow_obj:
        return log_and_return_json("follow_user", {'error': "Cannot follow self"}, status=400)

    if request.user.following.filter(pk=user_to_follow_obj.pk).exists():
        return log_and_return_json("follow_user", {'error': "Already following user"}, status=400)

    request.user.following.add(user_to_follow_obj)
    logger.info(f"Follow user successful: target_user_id: {user_to_follow_obj.id} by user_id: {request.user.id}")
    return log_and_return_json("follow_user", {'message': 'User followed'})


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='30/m', block=True)
@require_POST  # Or @require_DELETE
def unfollow_user(request, username_to_unfollow):
    logger.info("Endpoint unfollow_user invoked by IP or User")
    # user is on request.user
    if not is_valid_pattern(username_to_unfollow, Patterns.alphanumeric):
        return log_and_return_json("unfollow_user", {'error': "Invalid username fragment"}, status=400)

    user_to_unfollow_obj = get_user_with_username(username_to_unfollow)
    if not user_to_unfollow_obj:
        return log_and_return_json("unfollow_user", {'error': "User does not exist"}, status=400)

    if not request.user.following.filter(pk=user_to_unfollow_obj.pk).exists():
        return log_and_return_json("unfollow_user", {'error': "Not following user"}, status=400)

    request.user.following.remove(user_to_unfollow_obj)
    logger.info(f"Unfollow user successful: target_user_id: {user_to_unfollow_obj.id} by user_id: {request.user.id}")
    return log_and_return_json("unfollow_user", {'message': 'User unfollowed'})


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='30/m', block=True)
@require_POST
def toggle_block(request, username_to_toggle_block):
    logger.info("Endpoint toggle_block invoked by IP or User")
    # user is on request.user
    if not is_valid_pattern(username_to_toggle_block, Patterns.alphanumeric):
        return log_and_return_json("toggle_block", {'error': "Invalid username"}, status=400)

    user_to_toggle_obj = get_user_with_username(username_to_toggle_block)
    if not user_to_toggle_obj:
        return log_and_return_json("toggle_block", {'error': "User does not exist"}, status=400)

    if request.user == user_to_toggle_obj:
        return log_and_return_json("toggle_block", {'error': "Cannot block self"}, status=400)

    if request.user.blocked.filter(pk=user_to_toggle_obj.pk).exists():
        # Unblock
        request.user.blocked.remove(user_to_toggle_obj)
        return log_and_return_json("toggle_block", {'message': 'User unblocked'})
    else:
        # Block
        request.user.blocked.add(user_to_toggle_obj)
        # Also force unfollow? Typically blocking unfollows.
        if request.user.following.filter(pk=user_to_toggle_obj.pk).exists():
            request.user.following.remove(user_to_toggle_obj)
        if user_to_toggle_obj.following.filter(pk=request.user.pk).exists():
            user_to_toggle_obj.following.remove(request.user)

        logger.info(f"User blocked successful: target_user_id: {user_to_toggle_obj.id} by user_id: {request.user.id}")
        return log_and_return_json("toggle_block", {'message': 'User blocked'})


@api_login_required
@ratelimit(key='user', rate='30/m', block=True)
@require_GET
def get_profile_details(request, username):
    logger.info("Endpoint get_profile_details invoked by IP or User")
    # user is on request.user (requesting_user)
    if not is_valid_pattern(username, Patterns.alphanumeric_with_special_chars):
        return log_and_return_json("get_profile_details", {'error': "Invalid username"}, status=400)

    profile_user = get_user_with_username(username)
    if not profile_user:
        logger.warning(f"Get profile details failed: User with username fragment not found")
        return log_and_return_json("get_profile_details", {'error': "User not found"}, status=400)

    # Count only the posts the requesting user is allowed to see, so a
    # shadow-banned profile shows no posts to others (but all to its owner).
    post_count = visible_posts(profile_user.post_set.all(), request.user).count()

    # Assuming UserFollow model or a ManyToMany 'followers' field
    # This logic depends heavily on your model structure.
    # The original code's `followers_set` and `following_set` imply a
    # ManyToMany relationship, perhaps 'following' on the User model.
    follower_count = profile_user.followers.count()
    following_count = profile_user.following.count()

    is_following = request.user.following.filter(pk=profile_user.pk).exists()
    is_blocked = request.user.blocked.filter(pk=profile_user.pk).exists()

    # If I am blocked by them, should I see details?
    # Spec: "user B cannot search for user A".
    # Typically profiles are also hidden or return 404.
    # But `get_posts_for_user` will return empty.
    # Let's hide stats if blocked by them.
    is_blocked_by = request.user.blocked_by.filter(pk=profile_user.pk).exists()

    if is_blocked_by:
        # Return limited info or error?
        # Usually it looks like the user doesn't exist or empty profile.
        # Let's return empty stats.
        post_count = 0
        follower_count = 0
        following_count = 0
        is_following = False

    data = {
        Fields.username: profile_user.username,
        Fields.post_count: post_count,
        Fields.follower_count: follower_count,
        Fields.following_count: following_count,
        Fields.is_following: is_following,
        'is_blocked': is_blocked,
        Fields.identity_is_verified: profile_user.identity_is_verified,
        Fields.is_adult: profile_user.is_adult
    }

    return log_and_return_json("get_profile_details", data, status=200)


# =============================================================================
# APPEALS
# =============================================================================

def _appeal_target_type(appeal):
    """The kind of thing an appeal targets, or None if its target was deleted
    when the appeal was resolved (e.g. a denied post)."""
    if appeal.post_id:
        return APPEAL_TARGET_POST
    if appeal.comment_id:
        return APPEAL_TARGET_COMMENT
    if appeal.ban_id:
        return APPEAL_TARGET_BAN
    return None


def _appeal_target_identifier(appeal):
    if appeal.post_id:
        return appeal.post_id
    if appeal.comment_id:
        return appeal.comment_id
    if appeal.ban_id:
        return appeal.ban_id
    return None


@api_login_required
@ratelimit(key='user', rate='60/m', block=True)
@require_GET
def get_hidden_posts(request, batch):
    """The requesting user's own hidden posts, so they can see what was hidden
    and decide whether to appeal."""
    logger.info("Endpoint get_hidden_posts invoked by IP or User")
    if batch < 0:
        return log_and_return_json("get_hidden_posts", {'error': "Invalid batch parameter"}, status=400)

    hidden = request.user.post_set.filter(hidden=True).order_by('-creation_time')
    batched = get_queryset_batch(hidden, batch, POST_BATCH_SIZE)
    appealed_ids = set(
        Appeal.objects.filter(post__in=batched).values_list('post_id', flat=True)
    )
    data = [
        {
            Fields.post_identifier: post.post_identifier,
            Fields.image_url: get_compressed_image_url(post.image_url),
            Fields.caption: post.caption,
            Fields.hidden_reason: post.hidden_reason,
            Fields.creation_time: post.creation_time,
            Fields.has_appeal: post.post_identifier in appealed_ids,
        }
        for post in batched
    ]
    return log_and_return_json("get_hidden_posts", data, safe=False)


@api_login_required
@ratelimit(key='user', rate='60/m', block=True)
@require_GET
def get_hidden_comments(request, batch):
    """The requesting user's own hidden comments."""
    logger.info("Endpoint get_hidden_comments invoked by IP or User")
    if batch < 0:
        return log_and_return_json("get_hidden_comments", {'error': "Invalid batch parameter"}, status=400)

    hidden = Comment.objects.filter(author=request.user, hidden=True).order_by('-creation_time')
    batched = get_queryset_batch(hidden, batch, COMMENT_BATCH_SIZE)
    appealed_ids = set(
        Appeal.objects.filter(comment__in=batched).values_list('comment_id', flat=True)
    )
    data = [
        {
            Fields.comment_identifier: comment.comment_identifier,
            Fields.body: comment.body,
            Fields.hidden_reason: comment.hidden_reason,
            Fields.creation_time: comment.creation_time,
            Fields.has_appeal: comment.comment_identifier in appealed_ids,
        }
        for comment in batched
    ]
    return log_and_return_json("get_hidden_comments", data, safe=False)


@api_login_required
@ratelimit(key='user', rate='60/m', block=True)
@require_GET
def get_my_appeals(request, batch):
    """The requesting user's appeals and their current status."""
    logger.info("Endpoint get_my_appeals invoked by IP or User")
    if batch < 0:
        return log_and_return_json("get_my_appeals", {'error': "Invalid batch parameter"}, status=400)

    appeals = request.user.appeals.order_by('-created')
    batched = get_queryset_batch(appeals, batch, POST_BATCH_SIZE)
    data = [
        {
            Fields.appeal_identifier: appeal.appeal_identifier,
            Fields.target_type: _appeal_target_type(appeal),
            Fields.target_identifier: _appeal_target_identifier(appeal),
            Fields.status: appeal.status,
            Fields.reason: appeal.reason,
            Fields.content_snapshot: appeal.content_snapshot,
            Fields.resolution_note: appeal.resolution_note,
            Fields.creation_time: appeal.created,
            Fields.resolved_time: appeal.resolved_time,
        }
        for appeal in batched
    ]
    return log_and_return_json("get_my_appeals", data, safe=False)


def _resolve_appeal_target(request, target_type, target_identifier):
    """Resolve and authorize the content an appeal targets. Returns
    (target_field, target_object, content_snapshot) or None if the caller may
    not appeal it (not theirs, not hidden, or not found).

    Only posts and comments are appealable in-app. Ban appeals go through the
    email-reply flow (see the suspension email) because an outright-banned user
    has no session and cannot reach an authenticated endpoint."""
    if target_type == APPEAL_TARGET_POST:
        if not is_valid_pattern(target_identifier, Patterns.uuid4):
            return None
        post = request.user.post_set.filter(post_identifier=target_identifier, hidden=True).first()
        if post is None:
            return None
        return APPEAL_TARGET_POST, post, post.caption
    if target_type == APPEAL_TARGET_COMMENT:
        if not is_valid_pattern(target_identifier, Patterns.uuid4):
            return None
        comment = Comment.objects.filter(
            author=request.user, comment_identifier=target_identifier, hidden=True
        ).first()
        if comment is None:
            return None
        return APPEAL_TARGET_COMMENT, comment, comment.body
    return None


@csrf_exempt
@api_login_required
@ratelimit(key='user', rate='10/h', block=True)
@require_POST
def submit_appeal(request):
    """File an appeal against a hidden post or a hidden comment. One appeal per
    item: an item that already has an appeal (pending or resolved) cannot be
    appealed again. Ban appeals are not handled here — an outright-banned user
    has no session, so those go through the email-reply flow in the suspension
    email instead."""
    logger.info("Endpoint submit_appeal invoked by IP or User")
    data = _get_json_body(request)
    if data is None:
        return log_and_return_json("submit_appeal", {'error': "Invalid JSON data"}, status=400)

    target_type = data.get(Fields.target_type)
    target_identifier = data.get(Fields.target_identifier)
    reason = data.get(Fields.reason)

    # JSON values can be any type; reject non-string id/reason up front so the
    # validation below can't crash on them (UUID()/len() on a non-string would
    # otherwise 500).
    if target_type not in (APPEAL_TARGET_POST, APPEAL_TARGET_COMMENT):
        return log_and_return_json("submit_appeal", {'error': "Invalid target_type"}, status=400)
    if not isinstance(target_identifier, str):
        return log_and_return_json("submit_appeal", {'error': "Invalid target_identifier"}, status=400)
    if not isinstance(reason, str) or not reason or not is_valid_pattern(reason, Patterns.alphanumeric_with_special_chars):
        return log_and_return_json("submit_appeal", {'error': "Invalid reason"}, status=400)
    if len(reason) > MAX_APPEAL_REASON_LENGTH:
        return log_and_return_json(
            "submit_appeal",
            {'error': f"Reason exceeds maximum length of {MAX_APPEAL_REASON_LENGTH} characters"},
            status=400,
        )

    resolved = _resolve_appeal_target(request, target_type, target_identifier)
    if resolved is None:
        logger.warning(f"Submit appeal failed: target not found/appealable for user_id: {request.user.id}")
        return log_and_return_json("submit_appeal", {'error': "No appealable item with that identifier"}, status=400)

    target_field, target_object, content_snapshot = resolved

    # One appeal per item, regardless of status: an approval un-hides or a denial
    # removes the item, so a second appeal should never be needed. The exists()
    # check gives a friendly error in the common case; the unique constraint on
    # Appeal.post/comment is the real guard against two concurrent submissions
    # both passing this check.
    if Appeal.objects.filter(**{target_field: target_object}).exists():
        logger.warning(f"Submit appeal failed: item already appealed for user_id: {request.user.id}")
        return log_and_return_json("submit_appeal", {'error': "This item has already been appealed"}, status=400)

    try:
        appeal = Appeal.objects.create(
            appellant=request.user,
            reason=reason,
            content_snapshot=content_snapshot,
            **{target_field: target_object},
        )
    except IntegrityError:
        logger.warning(f"Submit appeal race: item already appealed for user_id: {request.user.id}")
        return log_and_return_json("submit_appeal", {'error': "This item has already been appealed"}, status=400)

    logger.info(f"Appeal submitted: appeal_id: {appeal.appeal_identifier} ({target_type}) for user_id: {request.user.id}")
    return log_and_return_json("submit_appeal", {Fields.appeal_identifier: appeal.appeal_identifier}, status=201)
