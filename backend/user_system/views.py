from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password
from django.core.mail import send_mail
from django.http import JsonResponse, HttpResponseBadRequest

from .classifiers import image_classifier, text_classifier
from .constants import Patterns, Params, POST_BATCH_SIZE, MAX_BEFORE_HIDING_POST, MAX_BEFORE_HIDING_COMMENT, \
    COMMENT_BATCH_SIZE, Fields, COMMENT_THREAD_BATCH_SIZE
from .feed_algorithm import feed_algorithm
from .input_validator import is_valid_pattern
from .models import LoginCookie, Session, Post, CommentThread, PositiveOnlySocialUser, Comment
from .utils import convert_to_bool, generate_login_cookie_token, generate_management_token, generate_series_identifier, \
    generate_reset_id, get_batch


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
        if type(remember_me) is str:
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

        # Issue a response with the new session management token and, if applicable,
        # the login cookie token and series identifier.
        response_data = {
            Fields.session_management_token: new_session.management_token
        }
        if remember_me and new_login_cookie:
            response_data[Fields.series_identifier] = new_login_cookie.series_identifier
            response_data[Fields.login_cookie_token] = new_login_cookie.token

        return JsonResponse(response_data)


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

        # Issue a response with the new session management token and, if applicable,
        # the login cookie token and series identifier.
        response_data = {
            'session_management_token': new_session.management_token
        }
        if remember_me and new_login_cookie:
            response_data['series_identifier'] = new_login_cookie.series_identifier
            response_data['login_cookie_token'] = new_login_cookie.token

        return JsonResponse(response_data)
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

    # Get the user with the current session management token
    existing = get_user_with_session_management_token(session_management_token)

    # Issue a new session management token
    new_session_management_token = generate_management_token()
    new_session = existing.session_set.create(management_token=new_session_management_token, ip=ip)
    new_session.save()

    # Send back the new login cookie token and session management token
    response_data = {
        'login_cookie_token': new_login_cookie_token,
        'session_management_token': new_session_management_token
    }

    return JsonResponse(response_data)


def request_reset(request, username_or_email):
    invalid_fields = []
    if not is_valid_pattern(username_or_email, Patterns.alphanumeric) and not is_valid_pattern(username_or_email,
                                                                                               Patterns.email):
        invalid_fields.append(Params.username_or_email)

    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    user = get_user_with_username_or_email(username_or_email)

    if user is not None:
        random_number = int(generate_reset_id(6))

        # Send the user an email.
        send_mail("Password reset id", f"Your password reset id is {random_number}",
                  settings.EMAIL_HOST_USER,
                  [user.email])

        user.reset_id = random_number
        user.save()

        # We send no data back, just a successful response.
        return JsonResponse({})

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
        if reset_id == user.reset_id and reset_id >= 0:

            user.reset_id = -1
            user.save()

            # We send no data back, just a successful response.
            return JsonResponse({})
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

        # We send no data back, just a successful response.
        return JsonResponse({})
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
        logout(request)
        # We send no data back, just a successful response.
        return JsonResponse({})
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
        # We send no data back, just a successful response.
        return JsonResponse({})
    else:
        return HttpResponseBadRequest("No user with session token")


@login_required
def make_post(request, session_management_token, image_url, caption, image_classifier_class=image_classifier,
              text_classifier_class=text_classifier):
    invalid_fields = []

    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)

    if not is_valid_pattern(image_url, Patterns.image_url):
        invalid_fields.append(Params.image)

    if not is_valid_pattern(caption, Patterns.alphanumeric_with_special_chars):
        invalid_fields.append(Params.caption)

    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    existing = get_user_with_session_management_token(session_management_token)

    if existing is not None:

        if image_classifier_class.is_image_positive(image_url):

            if not text_classifier_class.is_text_positive(caption):
                return HttpResponseBadRequest("Text must be positive")

            # Create the post in a single, clean step
            new_post = existing.post_set.create(image_url=image_url, caption=caption)

            # Return the new post's identifier directly
            return JsonResponse({'post_identifier': new_post.post_identifier})
        else:
            return HttpResponseBadRequest("Image is not positive")
    else:
        return HttpResponseBadRequest("No user with session token")


@login_required
def delete_post(request, session_management_token, post_identifier):
    invalid_fields = []

    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)

    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)

    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    existing = get_user_with_session_management_token(session_management_token)

    if existing is not None:
        try:
            post = existing.post_set.get(post_identifier=post_identifier)
        except Post.DoesNotExist:
            post = None

        if post is not None:
            post.delete()

            # We send no data back, just a successful response.
            return JsonResponse({})
        else:
            return HttpResponseBadRequest("No post with that identifier by that user")
    else:
        return HttpResponseBadRequest("No user with session token")


@login_required
def report_post(request, session_management_token, post_identifier, reason):
    invalid_fields = []

    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)

    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)

    if not is_valid_pattern(reason, Patterns.alphanumeric_with_special_chars):
        invalid_fields.append(Params.reason)

    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    existing = get_user_with_session_management_token(session_management_token)

    if existing is not None:

        post = get_post_with_identifier(post_identifier)

        if post is not None:

            if post.author != existing:
                # Use .exists() for a more efficient check for a previous report
                if post.postreport_set.filter(user=existing).exists():
                    return HttpResponseBadRequest("Cannot report post twice")

                # Create the report using the correct 'user' field
                post.postreport_set.create(user=existing, reason=reason)

                if post.postreport_set.count() > MAX_BEFORE_HIDING_POST:
                    post.hidden = True
                    post.save()

                # We send no data back, just a successful response.
                return JsonResponse({})
            else:
                return HttpResponseBadRequest("Cannot report own post")
        else:
            return HttpResponseBadRequest("No post with that identifier")
    else:
        return HttpResponseBadRequest("No user with session token")


@login_required
def like_post(request, session_management_token, post_identifier):
    invalid_fields = []

    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)

    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)

    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    existing = get_user_with_session_management_token(session_management_token)

    if existing is not None:

        post = get_post_with_identifier(post_identifier)

        if post is not None:

            if post.author != existing:
                # Use .exists() for an efficient check and the correct 'user' field
                if post.postlike_set.filter(user=existing).exists():
                    return HttpResponseBadRequest("Already liked post")

                # .create() handles saving the object
                post.postlike_set.create(user=existing)

                return JsonResponse({})
            else:
                return HttpResponseBadRequest("Cannot like own post")
        else:
            return HttpResponseBadRequest("No post with that identifier")
    else:
        return HttpResponseBadRequest("No user with session token")


@login_required
def unlike_post(request, session_management_token, post_identifier):
    invalid_fields = []

    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)

    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)

    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    existing = get_user_with_session_management_token(session_management_token)

    if existing is not None:

        post = get_post_with_identifier(post_identifier)

        if post is not None:

            if post.author != existing:
                # Filter by the 'user' field and delete in one step.
                # .delete() returns the number of objects deleted.
                deleted_count, _ = post.postlike_set.filter(user=existing).delete()

                if deleted_count > 0:
                    return JsonResponse({})
                else:
                    return HttpResponseBadRequest("Post not liked yet")
            else:
                return HttpResponseBadRequest("Cannot unlike own post")
        else:
            return HttpResponseBadRequest("No post with that identifier")
    else:
        return HttpResponseBadRequest("No user with session token")


@login_required
def get_posts_in_feed(request, session_management_token, batch, feed_algorithm_class=feed_algorithm):
    invalid_fields = []

    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)

    if batch < 0:
        return HttpResponseBadRequest("Invalid batch parameter")

    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    existing = get_user_with_session_management_token(session_management_token)

    if existing is not None:
        relevant_posts = feed_algorithm_class.get_posts_weighted(existing, Post)

        if len(relevant_posts) > 0:
            batch = get_batch(batch, POST_BATCH_SIZE, relevant_posts)

            # Build a list of dictionaries directly for a clean JSON array response
            posts_data = [
                {
                    'post_identifier': post.post_identifier,
                    'image_url': post.image_url,
                    'username': post.author.username
                }
                for post in batch
            ]

            # safe=False allows returning a list as the top-level JSON object
            return JsonResponse(posts_data, safe=False)
        else:
            # Return an empty list if there are no posts
            return JsonResponse([], safe=False)
    else:
        return HttpResponseBadRequest("No user with session token")


@login_required
def get_posts_for_followed_users(request, session_management_token, batch):
    """
    Fetches a paginated feed of posts from all users that the current user follows.
    """
    # --- Input Validation ---
    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        return HttpResponseBadRequest("Invalid session_management_token")

    if batch < 0:
        return HttpResponseBadRequest("Invalid batch parameter")

    # --- Core Logic ---
    current_user = get_user_with_session_management_token(session_management_token)
    if current_user is None:
        return HttpResponseBadRequest("No user with that session token")

    followed_users = current_user.following.all()

    # If the user isn't following anyone, return an empty list
    if not followed_users.exists():
        return JsonResponse([], safe=False)

    # Fetch posts, ordering by the correct 'creation_time' field
    posts_queryset = Post.objects.filter(author__in=followed_users).order_by('-creation_time')

    posts_batch = get_batch(batch, POST_BATCH_SIZE, posts_queryset)

    # --- Build and Return Response ---
    posts_data = [
        {
            'post_identifier': post.post_identifier,
            'image_url': post.image_url,
            'author_username': post.author.username
        }
        for post in posts_batch
    ]
    return JsonResponse(posts_data, safe=False)


@login_required
def get_posts_for_user(request, session_management_token, username, batch, feed_algorithm_class=feed_algorithm):
    # --- Input Validation ---
    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        return HttpResponseBadRequest("Invalid session_management_token")

    if not is_valid_pattern(username, Patterns.alphanumeric):
        return HttpResponseBadRequest("Invalid username")

    if batch < 0:
        return HttpResponseBadRequest("Invalid batch parameter")

    # --- Core Logic ---
    target_user = get_user_with_username(username)
    if not target_user:
        return HttpResponseBadRequest("User not found")

    # The original function was missing this lookup and passed the wrong user
    relevant_posts = feed_algorithm_class.get_posts_weighted_for_user(target_user, Post)

    if relevant_posts:
        batch = get_batch(batch, POST_BATCH_SIZE, relevant_posts)
        posts_data = [
            {
                'post_identifier': post.post_identifier,
                'image_url': post.image_url
            }
            for post in batch
        ]
        return JsonResponse(posts_data, safe=False)
    else:
        # Return an empty list for consistency with other feed endpoints
        return JsonResponse([], safe=False)


@login_required
def get_post_details(request, post_identifier):
    # --- Input Validation ---
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        return HttpResponseBadRequest("Invalid post_identifier")

    # --- Core Logic ---
    post = get_post_with_identifier(post_identifier)

    if post is not None:
        total_likes = post.postlike_set.count()

        # Build a simple dictionary for the response
        post_data = {
            'post_identifier': post.post_identifier,
            'image_url': post.image_url,
            'caption': post.caption,
            'post_likes': total_likes,
            'author_username': post.author.username
        }
        return JsonResponse(post_data)
    else:
        return HttpResponseBadRequest("No post with that identifier")


@login_required
def comment_on_post(request, session_management_token, post_identifier, comment_text,
                    text_classifier_class=text_classifier):
    # --- Input Validation ---

    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        return HttpResponseBadRequest("Invalid session_management_token")
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        return HttpResponseBadRequest("Invalid post_identifier")
    if not is_valid_pattern(comment_text, Patterns.alphanumeric_with_special_chars):
        return HttpResponseBadRequest("Invalid comment_text")
    if not text_classifier_class.is_text_positive(comment_text):
        return HttpResponseBadRequest("Negative text is not a valid text")

    # --- Core Logic ---
    existing = get_user_with_session_management_token(session_management_token)
    if existing is None:
        return HttpResponseBadRequest("No user with session token")

    post = get_post_with_identifier(post_identifier)
    if post is None:
        return HttpResponseBadRequest("No post with that identifier")

    # Corrected logic: Create the single comment thread for the post
    comment_thread = post.commentthread_set.create()

    # Corrected logic: Create the comment using the 'author' ForeignKey
    new_comment = comment_thread.comment_set.create(author=existing, body=comment_text)

    # Build and return a simple, direct JSON response
    response_data = {
        'comment_thread_identifier': comment_thread.comment_thread_identifier,
        'comment_identifier': new_comment.comment_identifier
    }
    return JsonResponse(response_data)


@login_required
def like_comment(request, session_management_token, post_identifier, comment_thread_identifier, comment_identifier):
    # --- Input Validation ---
    invalid_fields = []
    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if not is_valid_pattern(comment_thread_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_thread_identifier)
    if not is_valid_pattern(comment_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_identifier)
    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    # --- Core Logic ---
    existing = get_user_with_session_management_token(session_management_token)
    if not existing:
        return HttpResponseBadRequest("No user with session token")

    try:
        comment = Comment.objects.get(
            comment_identifier=comment_identifier,
            comment_thread__comment_thread_identifier=comment_thread_identifier,
            comment_thread__post__post_identifier=post_identifier
        )
    except Comment.DoesNotExist:
        return HttpResponseBadRequest("Comment not found with the provided identifiers.")

    if comment.author == existing:
        return HttpResponseBadRequest("Cannot like own comment")

    like, created = comment.commentlike_set.get_or_create(user=existing)

    if not created:
        return HttpResponseBadRequest("Already liked comment")

    return JsonResponse({})


@login_required
def unlike_comment(request, session_management_token, post_identifier, comment_thread_identifier, comment_identifier):
    # --- Input Validation ---
    invalid_fields = []
    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if not is_valid_pattern(comment_thread_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_thread_identifier)
    if not is_valid_pattern(comment_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_identifier)
    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    # --- Core Logic ---
    existing = get_user_with_session_management_token(session_management_token)
    if not existing:
        return HttpResponseBadRequest("No user with session token")

    try:
        comment = Comment.objects.get(
            comment_identifier=comment_identifier,
            comment_thread__comment_thread_identifier=comment_thread_identifier,
            comment_thread__post__post_identifier=post_identifier
        )
    except Comment.DoesNotExist:
        return HttpResponseBadRequest("Comment not found with the provided identifiers.")

    if comment.author == existing:
        return HttpResponseBadRequest("Cannot unlike own comment")

    deleted_count, _ = comment.commentlike_set.filter(user=existing).delete()

    if deleted_count == 0:
        return HttpResponseBadRequest("Comment not liked yet")

    return JsonResponse({})


@login_required
def delete_comment(request, session_management_token, post_identifier, comment_thread_identifier, comment_identifier):
    # --- Input Validation ---
    invalid_fields = []
    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if not is_valid_pattern(comment_thread_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_thread_identifier)
    if not is_valid_pattern(comment_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_identifier)
    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    # --- Core Logic ---
    existing = get_user_with_session_management_token(session_management_token)
    if not existing:
        return HttpResponseBadRequest("No user with session token")

    try:
        comment = Comment.objects.get(
            comment_identifier=comment_identifier,
            comment_thread__comment_thread_identifier=comment_thread_identifier,
            comment_thread__post__post_identifier=post_identifier
        )
    except Comment.DoesNotExist:
        return HttpResponseBadRequest("Comment not found with the provided identifiers.")

    if comment.author != existing:
        return HttpResponseBadRequest("You are not authorized to delete this comment.")

    comment.delete()

    return JsonResponse({})


@login_required
def report_comment(request, session_management_token, post_identifier, comment_thread_identifier, comment_identifier,
                   reason):
    # --- Input Validation ---
    invalid_fields = []
    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if not is_valid_pattern(comment_thread_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_thread_identifier)
    if not is_valid_pattern(comment_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_identifier)
    if not is_valid_pattern(reason, Patterns.alphanumeric_with_special_chars):
        invalid_fields.append(Params.reason)
    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    # --- Core Logic ---
    existing = get_user_with_session_management_token(session_management_token)
    if not existing:
        return HttpResponseBadRequest("No user with session token")

    try:
        comment = Comment.objects.get(
            comment_identifier=comment_identifier,
            comment_thread__comment_thread_identifier=comment_thread_identifier,
            comment_thread__post__post_identifier=post_identifier
        )
    except Comment.DoesNotExist:
        return HttpResponseBadRequest("Comment not found with the provided identifiers.")

    if comment.author == existing:
        return HttpResponseBadRequest("Cannot report own comment")

    if comment.commentreport_set.filter(user=existing).exists():
        return HttpResponseBadRequest("Cannot report comment twice")

    comment.commentreport_set.create(user=existing, reason=reason)

    if comment.commentreport_set.count() > MAX_BEFORE_HIDING_COMMENT:
        comment.hidden = True
        comment.save()

    return JsonResponse({})


@login_required
def get_comments_for_post(request, post_identifier, batch, feed_algorithm_class=feed_algorithm):
    # --- Input Validation ---
    invalid_fields = []
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if batch < 0:
        return HttpResponseBadRequest("Invalid batch parameter")
    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    # --- Core Logic ---
    post = get_post_with_identifier(post_identifier)
    if not post:
        return HttpResponseBadRequest("No post with that identifier")

    try:
        # Order comment threads by creation time as a sensible default
        comment_threads = post.commentthread_set.all().order_by('creation_time')

        if comment_threads.exists():
            batched_comment_threads = get_batch(batch, COMMENT_THREAD_BATCH_SIZE, comment_threads)

            # If found, return its identifier in a list, per the original function's structure.
            data = [{'comment_thread_identifier': comment_thread.comment_thread_identifier} for comment_thread in
                    batched_comment_threads]
            return JsonResponse(data, safe=False)
    except CommentThread.DoesNotExist:
        # If the post has no comment thread, return an empty list.
        return JsonResponse([], safe=False)


@login_required
def get_comments_for_thread(request, comment_thread_identifier, batch, feed_algorithm_class=feed_algorithm):
    # --- Input Validation ---
    invalid_fields = []
    if not is_valid_pattern(comment_thread_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_thread_identifier)
    if batch < 0:
        return HttpResponseBadRequest("Invalid batch parameter")
    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    # --- Core Logic ---
    comment_thread = get_comment_thread_with_identifier(comment_thread_identifier)
    if not comment_thread:
        return HttpResponseBadRequest("No comment thread with that identifier")

    # Order comments by creation time as a sensible default
    comments = comment_thread.comment_set.all().order_by('creation_time')

    if comments.exists():
        batched_comments = get_batch(batch, COMMENT_BATCH_SIZE, comments)

        comments_data = [
            {
                'comment_identifier': comment.comment_identifier,
                'body': comment.body,
                'author_username': comment.author.username,
                'creation_time': comment.creation_time,
                'updated_time': comment.updated_time,
                'comment_likes': comment.commentlike_set.count()
            }
            for comment in batched_comments
        ]
        return JsonResponse(comments_data, safe=False)
    else:
        # If the thread has no comments, return an empty list.
        return JsonResponse([], safe=False)


@login_required
def reply_to_comment_thread(request, session_management_token, post_identifier, comment_thread_identifier,
                            comment_text, text_classifier_class=text_classifier):
    # --- Input Validation ---
    invalid_fields = []
    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)
    if not is_valid_pattern(post_identifier, Patterns.uuid4):
        invalid_fields.append(Params.post_identifier)
    if not is_valid_pattern(comment_thread_identifier, Patterns.uuid4):
        invalid_fields.append(Params.comment_thread_identifier)
    if not is_valid_pattern(comment_text, Patterns.alphanumeric_with_special_chars):
        invalid_fields.append(Params.comment_text)
    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    if not text_classifier_class.is_text_positive(comment_text):
        return HttpResponseBadRequest("Text must be positive")

    # --- Core Logic ---
    existing = get_user_with_session_management_token(session_management_token)
    if not existing:
        return HttpResponseBadRequest("No user with session management token")

    try:
        # Find the specific thread belonging to the specific post
        comment_thread = CommentThread.objects.get(
            comment_thread_identifier=comment_thread_identifier,
            post__post_identifier=post_identifier
        )
    except CommentThread.DoesNotExist:
        return HttpResponseBadRequest("Comment thread not found for the given post.")

    # Create the comment with the correct fields
    new_comment = comment_thread.comment_set.create(author=existing, body=comment_text)

    # Return the new comment's ID in a simple JSON object
    return JsonResponse({'comment_identifier': new_comment.comment_identifier})


@login_required
def get_users_matching_fragment(request, session_management_token, username_fragment):
    # --- Input Validation ---
    invalid_fields = []
    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)
    if not is_valid_pattern(username_fragment, Patterns.short_alphanumeric):
        invalid_fields.append(Params.username_fragment)
    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    # --- Core Logic ---
    existing = get_user_with_session_management_token(session_management_token)
    if not existing:
        return HttpResponseBadRequest("No user with that session management token")

    # Perform a case-insensitive search, exclude the current user, and limit results
    users = PositiveOnlySocialUser.objects.filter(
        username__istartswith=username_fragment
    ).exclude(pk=existing.pk)[:10]

    # Build a list of dictionaries directly
    users_data = [
        {
            'username': user.username,
            'identity_is_verified': user.identity_is_verified
        }
        for user in users
    ]

    return JsonResponse(users_data, safe=False)


@login_required
def follow_user(request, session_management_token, username_to_follow):
    """
    Makes the current user follow the target user.
    """
    # --- Input Validation ---
    invalid_fields = []
    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)
    if not is_valid_pattern(username_to_follow, Patterns.alphanumeric):
        invalid_fields.append(Params.username_fragment)  # Note: Original code had a typo here
    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    # --- Core Logic ---
    current_user = get_user_with_session_management_token(session_management_token)
    if not current_user:
        return HttpResponseBadRequest("Invalid session token")

    user_to_follow = get_user_with_username(username_to_follow)
    if not user_to_follow:
        return HttpResponseBadRequest("Target user does not exist")

    if current_user == user_to_follow:
        return HttpResponseBadRequest("You cannot follow yourself")

    if current_user.following.filter(pk=user_to_follow.pk).exists():
        return HttpResponseBadRequest("Already following this user")

    current_user.following.add(user_to_follow)
    return JsonResponse({})


@login_required
def unfollow_user(request, session_management_token, username_to_unfollow):
    """
    Makes the current user unfollow the target user.
    """
    # --- Input Validation ---
    invalid_fields = []
    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)
    if not is_valid_pattern(username_to_unfollow, Patterns.alphanumeric):
        invalid_fields.append(Params.username_fragment)  # Note: Original code had a typo here
    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    # --- Core Logic ---
    current_user = get_user_with_session_management_token(session_management_token)
    if not current_user:
        return HttpResponseBadRequest("Invalid session token")

    user_to_unfollow = get_user_with_username(username_to_unfollow)
    if not user_to_unfollow:
        return HttpResponseBadRequest("Target user does not exist")

    # .remove() doesn't raise an error if the relationship doesn't exist,
    # so we check first to provide clear feedback to the user.
    if not current_user.following.filter(pk=user_to_unfollow.pk).exists():
        return HttpResponseBadRequest("You are not following this user")

    current_user.following.remove(user_to_unfollow)
    return JsonResponse({})

@login_required
def get_profile_details(request, session_management_token, username):
    # --- Input Validation ---
    invalid_fields = []
    if not is_valid_pattern(session_management_token, Patterns.alphanumeric):
        invalid_fields.append(Params.session_management_token)
    if not is_valid_pattern(username, Patterns.alphanumeric_with_special_chars):
        invalid_fields.append(Params.username)
    if len(invalid_fields) > 0:
        return HttpResponseBadRequest(f"Invalid fields: {invalid_fields}")

    # --- Core Logic ---
    # 1. Get the user making the request
    requesting_user = get_user_with_session_management_token(session_management_token)
    if not requesting_user:
        return HttpResponseBadRequest("Invalid session token")

    # 2. Get the user whose profile is being viewed
    profile_user = get_user_with_username(username)
    if not profile_user:
        return HttpResponseBadRequest("User not found")

    # 3. Calculate all statistics

    # Use the related_name 'post_set' from the Post model's 'author' ForeignKey
    post_count = profile_user.post_set.count()

    # Use related_name 'followers_set' from UserFollow's 'user_to' field
    follower_count = profile_user.followers_set.count()

    # Use related_name 'following_set' from UserFollow's 'user_from' field
    following_count = profile_user.following_set.count()

    # 4. Check if the requesting_user is in the profile_user's set of followers
    # We can do this by checking if a UserFollow relationship exists
    is_following = profile_user.followers_set.filter(
        user_from=requesting_user
    ).exists()

    # 5. Build the response data (matching the Swift struct)
    data = {
        "username": profile_user.username,
        "postCount": post_count,
        "followerCount": follower_count,
        "followingCount": following_count,
        "isFollowing": is_following
    }

    return JsonResponse(data)