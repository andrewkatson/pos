import json
from functools import wraps

from django.conf import settings
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.hashers import check_password
from django.core.mail import send_mail
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from .classifiers import image_classifier, text_classifier
from .constants import Patterns, Params, POST_BATCH_SIZE, MAX_BEFORE_HIDING_POST, MAX_BEFORE_HIDING_COMMENT, \
    COMMENT_BATCH_SIZE, Fields, COMMENT_THREAD_BATCH_SIZE
from .feed_algorithm import feed_algorithm
from .input_validator import is_valid_pattern
from .models import LoginCookie, Session, Post, CommentThread, PositiveOnlySocialUser, Comment
from .utils import convert_to_bool, generate_login_cookie_token, generate_management_token, generate_series_identifier, \
    generate_reset_id, get_batch

image_classifier_class = image_classifier
text_classifier_class = text_classifier
feed_algorithm_class = feed_algorithm

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

        # Attach user and token to the request for the view to use
        request.user = user
        request.token = token
        try:
            return view_func(request, *args, **kwargs)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=401)

    return _wrapped_view


# =============================================================================
# AUTHENTICATION VIEWS
# =============================================================================

@csrf_exempt
@require_POST
def register(request):
    data = _get_json_body(request)
    if data is None:
        return JsonResponse({'error': "Invalid JSON data"}, status=404)

    username = data.get(Fields.username)
    email = data.get(Fields.email)
    password = data.get(Fields.password)
    remember_me_str = data.get(Fields.remember_me)
    ip = data.get(Fields.ip)

    invalid_fields = []
    if not username or not is_valid_pattern(username, Patterns.alphanumeric):
        invalid_fields.append(Params.username)
    if not email or not is_valid_pattern(email, Patterns.email):
        invalid_fields.append(Params.email)
    if not ip or (not is_valid_pattern(ip, Patterns.ipv4) and not is_valid_pattern(ip, Patterns.ipv6)):
        invalid_fields.append(Params.ip)
    if not password or not is_valid_pattern(password, Patterns.password):
        invalid_fields.append(Params.password)

    try:
        remember_me = convert_to_bool(remember_me_str)
    except TypeError:
        remember_me = False  # Default to false if invalid
        invalid_fields.append(Params.remember_me)

    if len(invalid_fields) > 0:
        return JsonResponse({'error': f"Invalid fields {invalid_fields}"}, status=404)

    # Check no user has this email or username.
    if get_user_with_username(username) is not None or get_user_with_email(email) is not None:
        return JsonResponse({'error': "User already exists"}, status=404)

    new_user = get_user_model().objects.create_user(username=username, email=email)
    new_user.set_password(password)
    new_user.save()

    new_login_cookie = None
    if remember_me:
        new_login_cookie = new_user.logincookie_set.create(series_identifier=generate_series_identifier(),
                                                           token=generate_login_cookie_token())
        # .create() already saves

    new_session = new_user.session_set.create(management_token=generate_management_token(), ip=ip)
    # .create() already saves

    response_data = {
        Fields.session_management_token: new_session.management_token
    }
    if remember_me and new_login_cookie:
        response_data[Fields.series_identifier] = new_login_cookie.series_identifier
        response_data[Fields.login_cookie_token] = new_login_cookie.token

    return JsonResponse(response_data, status=201)


@csrf_exempt
@require_POST
def login_user(request):
    data = _get_json_body(request)
    if data is None:
        return JsonResponse({'error': "Invalid JSON data"}, status=404)

    username_or_email = data.get(Fields.username_or_email)
    password = data.get(Fields.password)
    remember_me_str = data.get(Fields.remember_me)
    ip = data.get(Fields.ip)

    invalid_fields = []
    if not username_or_email or (
            not is_valid_pattern(username_or_email, Patterns.alphanumeric) and not is_valid_pattern(username_or_email,
                                                                                                    Patterns.email)):
        invalid_fields.append(Params.username_or_email)
    if not ip or (not is_valid_pattern(ip, Patterns.ipv4) and not is_valid_pattern(ip, Patterns.ipv6)):
        invalid_fields.append(Params.ip)
    if not password or not is_valid_pattern(password, Patterns.password):
        invalid_fields.append(Params.password)

    try:
        remember_me = convert_to_bool(remember_me_str)
    except TypeError:
        remember_me = False
        invalid_fields.append(Params.remember_me)

    if len(invalid_fields) > 0:
        return JsonResponse({'error': f"Invalid fields {invalid_fields}"}, status=404)

    existing = get_user_with_username_or_email(username_or_email)
    if existing is not None:
        if not check_password(password, existing.password):
            return JsonResponse({'error': "Password was not correct"}, status=404)

        login(request, existing)  # Logs into Django's session auth

        new_login_cookie = None
        if remember_me:
            new_login_cookie = existing.logincookie_set.create(series_identifier=generate_series_identifier(),
                                                               token=generate_login_cookie_token())

        new_session = existing.session_set.create(management_token=generate_management_token(), ip=ip)

        response_data = {
            Fields.session_management_token: new_session.management_token
        }
        if remember_me and new_login_cookie:
            response_data[Fields.series_identifier] = new_login_cookie.series_identifier
            response_data[Fields.login_cookie_token] = new_login_cookie.token

        return JsonResponse(response_data)
    else:
        return JsonResponse({'error': "No user exists with that information"}, status=404)


@csrf_exempt
@require_POST
def login_user_with_remember_me(request):
    data = _get_json_body(request)
    if data is None:
        return JsonResponse({'error': "Invalid JSON data"}, status=404)

    session_management_token = data.get(Fields.session_management_token)
    series_identifier = data.get(Fields.series_identifier)
    login_cookie_token = data.get(Fields.login_cookie_token)
    ip = data.get(Fields.ip)

    invalid_fields = []
    if not session_management_token or not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)
    if not series_identifier or not is_valid_pattern(series_identifier, Patterns.uuid4):
        invalid_fields.append(Params.series_identifier)
    if not login_cookie_token or not is_valid_pattern(login_cookie_token, Patterns.alphanumeric):
        invalid_fields.append(Params.login_cookie_token)
    if not ip or (not is_valid_pattern(ip, Patterns.ipv4) and not is_valid_pattern(ip, Patterns.ipv6)):
        invalid_fields.append(Params.ip)

    if len(invalid_fields) > 0:
        return JsonResponse({'error': f"Invalid fields {invalid_fields}"}, status=404)

    try:
        matching_login_cookie = LoginCookie.objects.get(series_identifier=series_identifier)
    except LoginCookie.DoesNotExist:
        return JsonResponse({'error': "Series identifier does not exist"}, status=404)
    except LoginCookie.MultipleObjectsReturned:
        return JsonResponse({'error': "Series identifier exists too many times"}, status=404)

    if matching_login_cookie.token != login_cookie_token:
        return JsonResponse({'error': "Login cookie token does not match"}, status=404)

    # Issue a new login cookie token (token rotation)
    new_login_cookie_token = generate_login_cookie_token()
    matching_login_cookie.token = new_login_cookie_token
    matching_login_cookie.save()

    # Get the user with the *old* session management token
    existing = get_user_with_session_management_token(session_management_token)
    if existing is None:
        return JsonResponse({'error': "Original session token is invalid"}, status=404)

    # Issue a new session management token
    new_session_management_token = generate_management_token()
    _ = existing.session_set.create(management_token=new_session_management_token, ip=ip)

    response_data = {
        Fields.login_cookie_token: new_login_cookie_token,
        Fields.session_management_token: new_session_management_token
    }
    return JsonResponse(response_data)


@csrf_exempt
@api_login_required
@require_POST
def logout_user(request):
    # request.user and request.token are added by the decorator
    try:
        # Find the specific session object and delete it to invalidate the token
        session = request.user.session_set.get(management_token=request.token)
        session.delete()
    except Session.DoesNotExist:
        # This could happen if the token is valid but the session was already deleted
        return JsonResponse({'error': 'Session not found or already logged out'}, status=404)

    logout(request)  # Also log out of the standard Django session
    return JsonResponse({'message': 'Logout successful'})


@csrf_exempt
@api_login_required
@require_POST
def delete_user(request):
    # request.user is attached by the decorator
    try:
        user_to_delete = request.user
        logout(request)  # Log out of Django session first
        user_to_delete.delete()  # This will cascade and delete sessions, posts, etc.
        return JsonResponse({'message': 'User deleted successfully'})
    except Exception as e:
        return JsonResponse({'error': f"Error deleting user {e}"}, status=404)


# =============================================================================
# PASSWORD RESET VIEWS
# =============================================================================

@csrf_exempt
@require_POST
def request_reset(request):
    data = _get_json_body(request)
    if data is None:
        return JsonResponse({'error': "Invalid JSON data"}, status=404)

    username_or_email = data.get(Fields.username_or_email)

    if not username_or_email or (
            not is_valid_pattern(username_or_email, Patterns.alphanumeric) and not is_valid_pattern(username_or_email,
                                                                                                    Patterns.email)):
        return JsonResponse({'error': f"Invalid fields {Fields.username_or_email}"}, status=404)

    user = get_user_with_username_or_email(username_or_email)
    if user is not None:
        random_number = int(generate_reset_id(6))

        send_mail("Password reset id", f"Your password reset id is {random_number}",
                  settings.EMAIL_HOST_USER,
                  [user.email])

        user.reset_id = random_number
        user.save()
        return JsonResponse({'message': 'Reset email sent'})
    else:
        return JsonResponse({'error': "No user with that username or email"}, status=404)


@require_GET
def verify_reset(request, username_or_email, reset_id):
    # Data comes from URL, not JSON body
    invalid_fields = []
    if not is_valid_pattern(username_or_email, Patterns.alphanumeric) and not is_valid_pattern(username_or_email,
                                                                                               Patterns.email):
        invalid_fields.append(Params.username_or_email)

    # reset_id is already an int from the URL path, no need to check pattern
    if reset_id is None:
        invalid_fields.append(Params.reset_id)

    if len(invalid_fields) > 0:
        return JsonResponse({'error': f"Invalid fields {invalid_fields}"}, status=404)

    user = get_user_with_username_or_email(username_or_email)
    if user is not None:
        # Ensure types match for comparison
        if user.reset_id == int(reset_id) and user.reset_id >= 0:
            user.reset_id = -1  # Invalidate the reset ID
            user.save()
            return JsonResponse({'message': 'Verification successful'})
        else:
            return JsonResponse({'error': "That reset id does not match"}, status=404)
    else:
        return JsonResponse({'error': "No user with that username or email"}, status=404)


@csrf_exempt
@require_POST
def reset_password(request):
    data = _get_json_body(request)
    if data is None:
        return JsonResponse({'error': "Invalid JSON data"}, status=404)

    username = data.get(Fields.username)
    email = data.get(Fields.email)
    password = data.get(Fields.password)

    invalid_fields = []
    if not username or not is_valid_pattern(username, Patterns.alphanumeric):
        invalid_fields.append(Params.username)
    if not email or not is_valid_pattern(email, Patterns.email):
        invalid_fields.append(Params.email)
    if not password or not is_valid_pattern(password, Patterns.password):
        invalid_fields.append(Params.password)

    if len(invalid_fields) > 0:
        return JsonResponse({'error': f"Invalid fields {invalid_fields}"}, status=404)

    user = get_user_with_username_and_email(username, email)
    if user is not None:
        user.set_password(password)  # Use set_password to hash it!
        user.save()
        return JsonResponse({'message': 'Password reset successfully'})
    else:
        return JsonResponse({'error': "No user with that username or email"}, status=404)


# =============================================================================
# POST VIEWS
# =============================================================================

@csrf_exempt
@api_login_required
@require_POST
def make_post(request):
    # user is on request.user
    data = _get_json_body(request)
    if data is None:
        return JsonResponse({'error': "Invalid JSON data"}, status=404)

    image_url = data.get(Fields.image_url)
    caption = data.get(Fields.caption)

    invalid_fields = []
    if not image_url or not is_valid_pattern(image_url, Patterns.image_url):
        invalid_fields.append(Params.image)
    if not caption or not is_valid_pattern(caption, Patterns.alphanumeric_with_special_chars):
        invalid_fields.append(Params.caption)

    if len(invalid_fields) > 0:
        return JsonResponse({'error': f"Invalid fields {invalid_fields}"}, status=404)

    if not image_classifier_class.is_image_positive(image_url):
        return JsonResponse({'error': "Image is not positive"}, status=404)

    if not text_classifier_class.is_text_positive(caption):
        return JsonResponse({'error': "Text is not positive"}, status=404)

    new_post = request.user.post_set.create(image_url=image_url, caption=caption)
    return JsonResponse({Fields.post_identifier: new_post.post_identifier}, status=201)


@csrf_exempt
@api_login_required
@require_POST  # Or @require_DELETE if you prefer
def delete_post(request, post_identifier):
    # user is on request.user
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        return JsonResponse({'error': f"Invalid fields {Fields.post_identifier}"}, status=404)

    try:
        post = request.user.post_set.get(post_identifier=post_identifier)
        post.delete()
        return JsonResponse({'message': 'Post deleted'})
    except Post.DoesNotExist:
        return JsonResponse({'error': "No post with that identifier by that user"}, status=404)


@csrf_exempt
@api_login_required
@require_POST
def report_post(request, post_identifier):
    # user is on request.user
    data = _get_json_body(request)
    if data is None:
        return JsonResponse({'error': "Invalid JSON data"}, status=404)

    reason = data.get(Fields.reason)

    invalid_fields = []
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if not reason or not is_valid_pattern(reason, Patterns.alphanumeric_with_special_chars):
        invalid_fields.append(Params.reason)

    if len(invalid_fields) > 0:
        return JsonResponse({'error': f"Invalid fields {invalid_fields}"}, status=404)

    post = get_post_with_identifier(post_identifier)
    if post is not None:
        if post.author == request.user:
            return JsonResponse({'error': "Cannot report own post"}, status=404)

        if post.postreport_set.filter(user=request.user).exists():
            return JsonResponse({'error': "Cannot report post twice"}, status=404)

        post.postreport_set.create(user=request.user, reason=reason)

        if post.postreport_set.count() > MAX_BEFORE_HIDING_POST:
            post.hidden = True
            post.save()

        return JsonResponse({'message': 'Post reported'})
    else:
        return JsonResponse({'error': "No post with that identifier"}, status=404)


@csrf_exempt
@api_login_required
@require_POST
def like_post(request, post_identifier):
    # user is on request.user
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        return JsonResponse({'error': f"Invalid fields {Fields.post_identifier}"}, status=404)

    post = get_post_with_identifier(post_identifier)
    if post is not None:
        if post.author == request.user:
            return JsonResponse({'error': "Cannot like own post"}, status=404)

        # get_or_create handles the check and creation in one step
        like, created = post.postlike_set.get_or_create(user=request.user)

        if not created:
            return JsonResponse({'error': "Already liked post"}, status=404)

        return JsonResponse({'message': 'Post liked'})
    else:
        return JsonResponse({'error': "No post with that identifier"}, status=404)


@csrf_exempt
@api_login_required
@require_POST  # Or @require_DELETE
def unlike_post(request, post_identifier):
    # user is on request.user
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        return JsonResponse({'error': f"Invalid fields {Fields.post_identifier}"}, status=404)

    post = get_post_with_identifier(post_identifier)
    if post is not None:
        if post.author == request.user:
            return JsonResponse({'error': "Cannot unlike own post"}, status=404)

        deleted_count, _ = post.postlike_set.filter(user=request.user).delete()

        if deleted_count > 0:
            return JsonResponse({'message': 'Post unliked'})
        else:
            return JsonResponse({'error': "Post not liked yet"}, status=404)
    else:
        return JsonResponse({'error': "No post with that identifier"}, status=404)


# =============================================================================
# FEED / POST RETRIEVAL VIEWS
# =============================================================================

@api_login_required
@require_GET
def get_posts_in_feed(request, batch):
    # user is on request.user
    if batch < 0:
        return JsonResponse({'error': "Invalid batch parameter"}, status=404)

    relevant_posts = feed_algorithm_class.get_posts_weighted(request.user, Post)

    if relevant_posts.count() > 0:
        batched_posts = get_batch(batch, POST_BATCH_SIZE, relevant_posts)
        posts_data = [
            {
                Fields.post_identifier: post.post_identifier,
                Fields.image_url: post.image_url,
                Fields.username: post.author.username,
                Fields.caption: post.caption
            }
            for post in batched_posts
        ]
        return JsonResponse(posts_data, safe=False)
    else:
        return JsonResponse([], safe=False)


@api_login_required
@require_GET
def get_posts_for_followed_users(request, batch):
    # user is on request.user
    if batch < 0:
        return JsonResponse({'error': "Invalid batch parameter"}, status=404)

    followed_users = request.user.following.all()

    if not followed_users.exists():
        return JsonResponse([], safe=False)

    posts_queryset = Post.objects.filter(author__in=followed_users).order_by('-creation_time')
    posts_batch = get_batch(batch, POST_BATCH_SIZE, posts_queryset)

    posts_data = [
        {
            Fields.post_identifier: post.post_identifier,
            Fields.image_url: post.image_url,
            Fields.author_username: post.author.username,
            Fields.caption: post.caption
        }
        for post in posts_batch
    ]
    return JsonResponse(posts_data, safe=False)


@api_login_required
@require_GET
def get_posts_for_user(request, username, batch):

    # user is on request.user (for auth), username is for target
    if not is_valid_pattern(username, Patterns.alphanumeric):
        return JsonResponse({'error': "Invalid username"}, status=404)
    if batch < 0:
        return JsonResponse({'error': "Invalid batch parameter"}, status=404)

    target_user = get_user_with_username(username)
    if not target_user:
        return JsonResponse({'error': "User not found"}, status=404)

    relevant_posts = feed_algorithm_class.get_posts_weighted_for_user(target_user, Post)

    if relevant_posts.count() > 0:
        batched_posts = get_batch(batch, POST_BATCH_SIZE, relevant_posts)
        posts_data = [
            {
                Fields.post_identifier: post.post_identifier,
                Fields.image_url: post.image_url,
                Fields.caption: post.caption,
                Fields.author_username: target_user.username
            }
            for post in batched_posts
        ]
        return JsonResponse(posts_data, safe=False)
    else:
        return JsonResponse([], safe=False)


@require_GET  # Publicly viewable, no @api_login_required
def get_post_details(request, post_identifier):
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        return JsonResponse({'error': "Invalid post identifier"}, status=404)

    post = get_post_with_identifier(post_identifier)
    if post is not None:
        total_likes = post.postlike_set.count()
        post_data = {
            Fields.post_identifier: post.post_identifier,
            Fields.image_url: post.image_url,
            Fields.caption: post.caption,
            Fields.post_likes: total_likes,
            Fields.author_username: post.author.username
        }
        return JsonResponse(post_data)
    else:
        return JsonResponse({'error': "No post with that identifier"}, status=404)


# =============================================================================
# COMMENT VIEWS
# =============================================================================

@csrf_exempt
@api_login_required
@require_POST
def comment_on_post(request, post_identifier):
    # user is on request.user
    data = _get_json_body(request)
    if data is None:
        return JsonResponse({'error': "Invalid JSON data"}, status=404)

    comment_text = data.get(Fields.comment_text)

    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        return JsonResponse({'error': "Invalid post_identifier"}, status=404)
    if not comment_text or not is_valid_pattern(comment_text, Patterns.alphanumeric_with_special_chars):
        return JsonResponse({'error': "Invalid comment text"}, status=404)

    if not text_classifier_class.is_text_positive(comment_text):
        return JsonResponse({'error': "Text is not positive"}, status=404)

    post = get_post_with_identifier(post_identifier)
    if post is None:
        return JsonResponse({'error': "No post with that identifier"}, status=404)

    # Create a new thread for this top-level comment
    comment_thread = post.commentthread_set.create()
    new_comment = comment_thread.comment_set.create(author=request.user, body=comment_text)

    response_data = {
        Fields.comment_thread_identifier: comment_thread.comment_thread_identifier,
        Fields.comment_identifier: new_comment.comment_identifier
    }
    return JsonResponse(response_data, status=201)


@csrf_exempt
@api_login_required
@require_POST
def reply_to_comment_thread(request, post_identifier, comment_thread_identifier):
    # user is on request.user
    data = _get_json_body(request)
    if data is None:
        return JsonResponse({'error': "Invalid JSON data"}, status=404)

    comment_text = data.get(Fields.comment_text)

    invalid_fields = []
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if not is_valid_pattern(comment_thread_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_thread_identifier)
    if not comment_text or not is_valid_pattern(comment_text, Patterns.alphanumeric_with_special_chars):
        invalid_fields.append(Params.comment_text)

    if len(invalid_fields) > 0:
        return JsonResponse({'error': f"Invalid fields {invalid_fields}"}, status=404)

    if not text_classifier_class.is_text_positive(comment_text):
        return JsonResponse({'error': "Text is not positive"}, status=404)

    try:
        comment_thread = CommentThread.objects.get(
            comment_thread_identifier=comment_thread_identifier,
            post__post_identifier=post_identifier
        )
    except CommentThread.DoesNotExist:
        return JsonResponse({'error': "Comment thread not found for the given post"}, status=404)

    new_comment = comment_thread.comment_set.create(author=request.user, body=comment_text)
    return JsonResponse({Fields.comment_identifier: new_comment.comment_identifier}, status=201)


@csrf_exempt
@api_login_required
@require_POST
def like_comment(request, post_identifier, comment_thread_identifier, comment_identifier):
    # user is on request.user
    invalid_fields = []
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if not is_valid_pattern(comment_thread_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_thread_identifier)
    if not is_valid_pattern(comment_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_identifier)
    if len(invalid_fields) > 0:
        return JsonResponse({'error': f"Invalid fields {invalid_fields}"}, status=404)

    try:
        comment = Comment.objects.get(
            comment_identifier=comment_identifier,
            comment_thread__comment_thread_identifier=comment_thread_identifier,
            comment_thread__post__post_identifier=post_identifier
        )
    except Comment.DoesNotExist:
        return JsonResponse({'error': "Comment not found"}, status=404)

    if comment.author == request.user:
        return JsonResponse({'error': "Cannot like own comment"}, status=404)

    like, created = comment.commentlike_set.get_or_create(user=request.user)
    if not created:
        return JsonResponse({'error': "Already liked comment"}, status=404)

    return JsonResponse({'message': 'Comment liked'})


@csrf_exempt
@api_login_required
@require_POST  # Or @require_DELETE
def unlike_comment(request, post_identifier, comment_thread_identifier, comment_identifier):
    # user is on request.user
    invalid_fields = []
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if not is_valid_pattern(comment_thread_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_thread_identifier)
    if not is_valid_pattern(comment_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_identifier)
    if len(invalid_fields) > 0:
        return JsonResponse({'error': f"Invalid fields {invalid_fields}"}, status=404)

    try:
        comment = Comment.objects.get(
            comment_identifier=comment_identifier,
            comment_thread__comment_thread_identifier=comment_thread_identifier,
            comment_thread__post__post_identifier=post_identifier
        )
    except Comment.DoesNotExist:
        return JsonResponse({'error': "Comment not found"}, status=404)

    if comment.author == request.user:
        return JsonResponse({'error': "Cannot unlike own comment"}, status=404)

    deleted_count, _ = comment.commentlike_set.filter(user=request.user).delete()
    if deleted_count == 0:
        return JsonResponse({'error': "Comment not liked yet"}, status=404)

    return JsonResponse({'message': 'Comment unliked'})


@csrf_exempt
@api_login_required
@require_POST  # Or @require_DELETE
def delete_comment(request, post_identifier, comment_thread_identifier, comment_identifier):
    # user is on request.user
    invalid_fields = []
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if not is_valid_pattern(comment_thread_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_thread_identifier)
    if not is_valid_pattern(comment_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_identifier)
    if len(invalid_fields) > 0:
        return JsonResponse({'error': f"Invalid fields {invalid_fields}"}, status=404)

    try:
        comment = Comment.objects.get(
            comment_identifier=comment_identifier,
            comment_thread__comment_thread_identifier=comment_thread_identifier,
            comment_thread__post__post_identifier=post_identifier
        )
    except Comment.DoesNotExist:
        return JsonResponse({'error': "Comment not found"}, status=404)

    if comment.author != request.user:
        return JsonResponse({'error': "Not authorized to delete comment"}, status=404)

    comment.delete()
    return JsonResponse({'message': 'Comment deleted'})


@csrf_exempt
@api_login_required
@require_POST
def report_comment(request, post_identifier, comment_thread_identifier, comment_identifier):
    # user is on request.user
    data = _get_json_body(request)
    if data is None:
        return JsonResponse({'error': "Invalid JSON data"}, status=404)

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
        return JsonResponse({'error': f"Invalid fields {invalid_fields}"}, status=404)

    try:
        comment = Comment.objects.get(
            comment_identifier=comment_identifier,
            comment_thread__comment_thread_identifier=comment_thread_identifier,
            comment_thread__post__post_identifier=post_identifier
        )
    except Comment.DoesNotExist:
        return JsonResponse({'error': "Comment not found"}, status=404)

    if comment.author == request.user:
        return JsonResponse({'error': "Cannot report own comment"}, status=404)

    if comment.commentreport_set.filter(user=request.user).exists():
        return JsonResponse({'error': "Cannot report comment twice"}, status=404)

    comment.commentreport_set.create(user=request.user, reason=reason)

    if comment.commentreport_set.count() > MAX_BEFORE_HIDING_COMMENT:
        comment.hidden = True
        comment.save()

    return JsonResponse({'message': 'Comment reported'})


@api_login_required  # Original had @login_required
@require_GET
def get_comments_for_post(request, post_identifier, batch):
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        return JsonResponse({'error': "Invalid post identifier"}, status=404)
    if batch < 0:
        return JsonResponse({'error': "Invalid batch parameter"}, status=404)

    post = get_post_with_identifier(post_identifier)
    if not post:
        return JsonResponse({'error': "No post with that identifier"}, status=404)

    comment_threads = post.commentthread_set.all()

    relevant_comment_threads = feed_algorithm_class.get_comment_threads_weighted_for_post(comment_threads)

    if not relevant_comment_threads.count() > 0:
        return JsonResponse([], safe=False)

    batched_comment_threads = get_batch(batch, COMMENT_THREAD_BATCH_SIZE, relevant_comment_threads)
    data = [{Fields.comment_thread_identifier: ct.comment_thread_identifier} for ct in batched_comment_threads]
    return JsonResponse(data, safe=False)


@api_login_required  # Original had @login_required
@require_GET
def get_comments_for_thread(request, comment_thread_identifier, batch):
    if not is_valid_pattern(comment_thread_identifier, Patterns.uuid4):
        return JsonResponse({'error': "Invalid comment thread identifier"}, status=404)
    if batch < 0:
        return JsonResponse({'error': "Invalid batch parameter"}, status=404)

    comment_thread = get_comment_thread_with_identifier(comment_thread_identifier)
    if not comment_thread:
        return JsonResponse({'error': "No comment thread with that identifier"}, status=404)

    comments = comment_thread.comment_set.all().order_by('creation_time')
    relevant_comments = feed_algorithm_class.get_comments_weighted_for_thread(comments)

    if not relevant_comments.count() > 0:
        return JsonResponse([], safe=False)

    batched_comments = get_batch(batch, COMMENT_BATCH_SIZE, relevant_comments)
    comments_data = [
        {
            Fields.comment_identifier: comment.comment_identifier,
            Fields.body: comment.body,
            Fields.author_username: comment.author.username,
            Fields.creation_time: comment.creation_time,
            Fields.updated_time: comment.updated_time,
            Fields.comment_likes: comment.commentlike_set.count()
        }
        for comment in batched_comments
    ]
    return JsonResponse(comments_data, safe=False)


# =============================================================================
# USER / PROFILE VIEWS
# =============================================================================

@api_login_required
@require_GET
def get_users_matching_fragment(request, username_fragment):
    # user is on request.user
    if not is_valid_pattern(username_fragment, Patterns.short_alphanumeric):
        return JsonResponse({'error': "Invalid username fragment"}, status=404)

    # We only get the first 10 users because we don't support endlessly scrolling through
    # user results in the search bar.
    users = PositiveOnlySocialUser.objects.filter(
        username__istartswith=username_fragment
    ).exclude(pk=request.user.pk)[:10]

    users_data = [
        {
            Fields.username: user.username,
            Fields.identity_is_verified: user.identity_is_verified
        }
        for user in users
    ]
    return JsonResponse(users_data, safe=False)


@csrf_exempt
@api_login_required
@require_POST
def follow_user(request, username_to_follow):
    # user is on request.user
    if not is_valid_pattern(username_to_follow, Patterns.alphanumeric):
        return JsonResponse({'error': "Invalid username fragment"}, status=404)

    user_to_follow_obj = get_user_with_username(username_to_follow)
    if not user_to_follow_obj:
        return JsonResponse({'error': "User does not exist"}, status=404)

    if request.user == user_to_follow_obj:
        return JsonResponse({'error': "Cannot follow self"}, status=404)

    if request.user.following.filter(pk=user_to_follow_obj.pk).exists():
        return JsonResponse({'error': "Already following user"}, status=404)

    request.user.following.add(user_to_follow_obj)
    return JsonResponse({'message': 'User followed'})


@csrf_exempt
@api_login_required
@require_POST  # Or @require_DELETE
def unfollow_user(request, username_to_unfollow):
    # user is on request.user
    if not is_valid_pattern(username_to_unfollow, Patterns.alphanumeric):
        return JsonResponse({'error': "Invalid username fragment"}, status=404)

    user_to_unfollow_obj = get_user_with_username(username_to_unfollow)
    if not user_to_unfollow_obj:
        return JsonResponse({'error': "User does not exist"}, status=404)

    if not request.user.following.filter(pk=user_to_unfollow_obj.pk).exists():
        return JsonResponse({'error': "Not following user"}, status=404)

    request.user.following.remove(user_to_unfollow_obj)
    return JsonResponse({'message': 'User unfollowed'})


@api_login_required
@require_GET
def get_profile_details(request, username):
    # user is on request.user (requesting_user)
    if not is_valid_pattern(username, Patterns.alphanumeric_with_special_chars):
        return JsonResponse({'error': "Invalid username"}, status=404)

    profile_user = get_user_with_username(username)
    if not profile_user:
        return JsonResponse({'error': "User not found"}, status=404)

    post_count = profile_user.post_set.count()

    # Assuming UserFollow model or a ManyToMany 'followers' field
    # This logic depends heavily on your model structure.
    # The original code's `followers_set` and `following_set` imply a
    # ManyToMany relationship, perhaps 'following' on the User model.
    follower_count = profile_user.followers.count()
    following_count = profile_user.following.count()

    is_following = request.user.following.filter(pk=profile_user.pk).exists()

    data = {
        Fields.username: profile_user.username,
        Fields.post_count: post_count,
        Fields.follower_count: follower_count,
        Fields.following_count: following_count,
        Fields.is_following: is_following
    }

    return JsonResponse(data)
