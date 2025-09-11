import datetime

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password
from django.core import serializers
from django.core.mail import send_mail
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth import get_user_model

from .constants import Patterns, Params
from .input_validator import is_valid_pattern
from .utils import convert_to_bool, generate_login_cookie_token, generate_management_token, generate_series_identifier, \
    generate_reset_id
from .models import LoginCookie, Response, Session
from classifiers import image_classifier, image_classifier_fake, text_classifier_fake, text_classifier

image_classifier_class = image_classifier
text_classifier_class = text_classifier
if settings.DEBUG:
    image_classifier_class = image_classifier_fake
    text_classifier_class = text_classifier_fake

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


def get_user(username, email, password):
    try:
        existing = authenticate(username=username, email=email, password=password)
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
    except LoginCookie.DoesNotExist:
        return None


def register(request, username, email, password, remember_me, ip):
    invalid_fields = []
    if not is_valid_pattern(username, Patterns.alphanumeric):
        invalid_fields.append(Params.username)

    if not is_valid_pattern(email, Patterns.email):
        invalid_fields.append(Params.email)

    if not is_valid_pattern(ip, Patterns.ipv4) and not is_valid_pattern(ip, Patterns.ipv6):
        invalid_fields.append(Params.ip)

    if not is_valid_pattern(password, Patterns.password):
        invalid_fields.append(Params.password)

    try:
        remember_me = convert_to_bool(remember_me)
    except TypeError:
        invalid_fields.append(Params.remember_me)

    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    existing = get_user(username, email, password)
    if existing is not None:
        return HttpResponseBadRequest("User already exists")
    else:
        # We first need to check no user has this email or username.
        if get_user_with_username(username) is not None or get_user_with_email(email) is not None:
            return HttpResponseBadRequest("User already exists")

        new_user = get_user_model().objects.create_user(username=username, email=email)
        new_user.set_password(password)
        new_user.save()

        new_login_cookie = None
        if remember_me:
            new_login_cookie = new_user.logincookie_set.create(series_identifier=generate_series_identifier(),
                                                               token=generate_login_cookie_token())
            new_login_cookie.save()

        new_session = new_user.session_set.create(management_token=generate_management_token(), ip=ip)
        new_session.save()

        # Issue a response with a new session management token, login cookie token
        # and login cookie series identifier
        serialized_response_list = None
        if remember_me:
            response = Response.objects.create(series_identifier=new_login_cookie.series_identifier,
                                               login_cookie_token=new_login_cookie.token,
                                               session_management_token=new_session.management_token)

            serialized_response_list = serializers.serialize('json', [response],
                                                             fields=('series_identifier', 'login_cookie_token',
                                                                     'session_management_token'))
        else:
            response = Response.objects.create(session_management_token=new_session.management_token)

            serialized_response_list = serializers.serialize('json', [response],
                                                             fields='session_management_token')
        return JsonResponse({'response_list': serialized_response_list})


def login_user(request, username_or_email, password, remember_me, ip):
    invalid_fields = []
    if not is_valid_pattern(username_or_email, Patterns.alphanumeric) and not is_valid_pattern(username_or_email,
                                                                                               Patterns.email):
        invalid_fields.append(Params.username_or_email)

    if not is_valid_pattern(ip, Patterns.ipv4) and not is_valid_pattern(ip, Patterns.ipv6):
        invalid_fields.append(Params.ip)

    if not is_valid_pattern(password, Patterns.password):
        invalid_fields.append(Params.password)

    try:
        remember_me = convert_to_bool(remember_me)
    except TypeError:
        invalid_fields.append(Params.remember_me)

    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    existing = get_user_with_username_or_email(username_or_email)
    if existing is not None:

        if not check_password(password, existing.password):
            return HttpResponseBadRequest("Password was not correct")

        login(request, existing)

        new_login_cookie = None
        if remember_me:
            new_login_cookie = existing.logincookie_set.create(series_identifier=generate_series_identifier(),
                                                               token=generate_login_cookie_token())
            new_login_cookie.save()

        new_session = existing.session_set.create(management_token=generate_management_token(), ip=ip)
        new_session.save()

        # Issue a response with a new session management token, login cookie token
        # and login cookie series identifier
        serialized_response_list = None
        if remember_me:
            response = Response.objects.create(series_identifier=new_login_cookie.series_identifier,
                                               login_cookie_token=new_login_cookie.token,
                                               session_management_token=new_session.management_token)

            serialized_response_list = serializers.serialize('json', [response],
                                                             fields=('series_identifier', 'login_cookie_token',
                                                                     'session_management_token'))
        else:
            response = Response.objects.create(session_management_token=new_session.management_token)

            serialized_response_list = serializers.serialize('json', [response],
                                                             fields='session_management_token')

        return JsonResponse({'response_list': serialized_response_list})
    else:
        return HttpResponseBadRequest("No user exists with that information")


def login_user_with_remember_me(request, session_management_token, series_identifier, login_cookie_token, ip):
    invalid_fields = []

    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)

    if not is_valid_pattern(series_identifier, Patterns.uuid4):
        invalid_fields.append(Params.series_identifier)

    if not is_valid_pattern(login_cookie_token, Patterns.alphanumeric):
        invalid_fields.append(Params.login_cookie_token)

    if not is_valid_pattern(ip, Patterns.ipv4) and not is_valid_pattern(ip, Patterns.ipv6):
        invalid_fields.append(Params.ip)

    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    # Check if series identifier exists
    all_with_series_identifier = LoginCookie.objects.filter(series_identifier=series_identifier)

    if len(all_with_series_identifier) > 1:
        return HttpResponseBadRequest(f"Series identifier {series_identifier} exists too many times")

    if len(all_with_series_identifier) == 0:
        return HttpResponseBadRequest(f"Series identifier {series_identifier} does not exist")

    matching_login_cookie = all_with_series_identifier.first()

    # Check if login cookie token matches the one sent over
    if matching_login_cookie.token != login_cookie_token:
        return HttpResponseBadRequest(f"Login cookie token {login_cookie_token} does not match")

    # Issue a new login cookie token if it matches
    new_login_cookie_token = generate_login_cookie_token()
    matching_login_cookie.token = new_login_cookie_token
    matching_login_cookie.save()

    response = Response.objects.create(login_cookie_token=new_login_cookie_token)

    serialized_response_list = serializers.serialize('json', [response],
                                                     fields='login_cookie_token')
    # Send back a login cookie token only
    return JsonResponse({'response_list': serialized_response_list})


def request_reset(request, username_or_email):
    invalid_fields = []
    if not is_valid_pattern(username_or_email, Patterns.alphanumeric) and not is_valid_pattern(username_or_email,
                                                                                               Patterns.email):
        invalid_fields.append(Params.username_or_email)

    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    user = get_user_with_username_or_email(username_or_email)

    if user is not None:
        random_number = generate_reset_id(6)

        # Send the user an email.
        send_mail("Password reset id", f"Your password reset id is {random_number}",
                  settings.EMAIL_HOST_USER,
                  [user.email])

        user.reset_id = random_number
        user.save()

        response = Response.objects.create()

        # We send no data back. Just a successful response.
        serialized_response_list = serializers.serialize('json', [response],
                                                         fields=())

        return JsonResponse({'response_list': serialized_response_list})

    else:
        return HttpResponseBadRequest("No user with that username or email")


def verify_reset(request, username_or_email, reset_id):
    invalid_fields = []
    if not is_valid_pattern(username_or_email, Patterns.alphanumeric) and not is_valid_pattern(username_or_email,
                                                                                               Patterns.email):
        invalid_fields.append(Params.username_or_email)

    if not is_valid_pattern(reset_id, Patterns.reset_id):
        invalid_fields.append(Params.reset_id)

    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    user = get_user_with_username_or_email(username_or_email)

    if user is not None:
        if reset_id == user.reset_id and reset_id != 0:

            user.reset_id = 0
            user.save()

            response = Response.objects.create()

            # We send no data back. Just a successful response.
            serialized_response_list = serializers.serialize('json', [response],
                                                             fields=())

            return JsonResponse({'response_list': serialized_response_list})
        else:
            return HttpResponseBadRequest("That reset id does not match")
    else:
        return HttpResponseBadRequest("No user with that username or email")


def reset_password(request, username, email, password):
    invalid_fields = []
    if not is_valid_pattern(username, Patterns.alphanumeric):
        invalid_fields.append(Params.username)

    if not is_valid_pattern(email, Patterns.email):
        invalid_fields.append(Params.email)

    if not is_valid_pattern(password, Patterns.password):
        invalid_fields.append(Params.password)

    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    user = get_user_with_username_and_email(username, email)

    if user is not None:
        user.password = password
        user.save()

        response = Response.objects.create()

        # We send no data back. Just a successful response.
        serialized_response_list = serializers.serialize('json', [response],
                                                         fields=())

        return JsonResponse({'response_list': serialized_response_list})
    else:
        return HttpResponseBadRequest("No user with that username and email")


@login_required
def logout_user(request, session_management_token):
    invalid_fields = []

    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)

    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    existing = get_user_with_session_management_token(session_management_token)

    if existing is not None:
        # We send no data back. Just a successful response.
        response = Response.objects.create()
        serialized_response_list = serializers.serialize('json', [response],
                                                         fields='')
        logout(request)
        return JsonResponse({'response_list': serialized_response_list})
    else:
        return HttpResponseBadRequest("No user with session token")


@login_required
def delete_user(request, session_management_token):
    invalid_fields = []

    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)

    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    existing = get_user_with_session_management_token(session_management_token)

    if existing is not None:

        existing.delete()

        response = Response.objects.create()

        serialized_response_list = serializers.serialize('json', [response], fields=())

        return JsonResponse({'response_list': serialized_response_list})
    else:
        return HttpResponseBadRequest("No user with session token")


@login_required
def make_post(request, session_management_token, image_url, caption):
    invalid_fields = []

    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)

    if not is_valid_pattern(image_url, Patterns.image_url):
        invalid_fields.append(Params.image)

    if not is_valid_pattern(caption, Patterns.sql_injection):
        invalid_fields.append(Params.caption)

    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    existing = get_user_with_session_management_token(session_management_token)

    if existing is not None:

        if image_classifier_class.is_image_positive(image_url):

            new_post = existing.post_set.create()
            new_post.image_url = image_url
            new_post.caption = caption
            new_post.created_datetime = datetime.datetime.now()
            new_post.updated_datetime = datetime.datetime.now()
            new_post.save()

            response = Response.objects.create()

            serialized_response_list = serializers.serialize('json', [response], fields=())

            return JsonResponse({'response_list': serialized_response_list})
        else:
            return HttpResponseBadRequest("Image is not positive")
    else:
        return HttpResponseBadRequest("No user with session token")
    


@login_required
def delete_post(request, session_management_token, post_identifier):
    invalid_fields = []

    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)

    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    existing = get_user_with_session_management_token(session_management_token)
    post = existing.post_set.get(post_identifier=post_identifier)

    if existing is not None:

        if post is not None:
            post.delete()

            response = Response.objects.create()

            serialized_response_list = serializers.serialize('json', [response], fields=())

            return JsonResponse({'response_list': serialized_response_list})
        else:
            return HttpResponseBadRequest("No post with that identifier by that user")
    else:
        return HttpResponseBadRequest("No user with session token")


@login_required
def report_post(request, session_management_token, post_identifier):
    pass


@login_required
def like_post(request, session_management_token, post_identifier):
    pass


@login_required
def unlike_post(request, session_management_token, post_identifier):
    pass

@login_required
def get_posts_in_feed(request, session_management_token):
    pass

@login_required
def get_posts_for_user(request, session_management_token, username):
    pass

@login_required
def comment_on_post(request, session_management_token, post_identifier):
    pass


@login_required
def like_comment(request, session_management_token, post_identifier, comment_identifier):
    pass


@login_required
def unlike_comment(request, session_management_token, post_identifier, comment_identifier):
    pass


@login_required
def delete_comment(request, session_management_token, post_identifier, comment_identifier):
    pass


@login_required
def report_comment(request, session_management_token, post_identifier, comment_identifier):
    pass

@login_required
def get_comments_for_post(request, session_management_token, post_identifier):
    pass

@login_required
def reply_to_comment_thread(request, session_management_token, post_identifier, comment_thread_identifier):
    pass

@login_required
def get_users_matching_fragment(request, session_management_token, username_fraction):
    pass
