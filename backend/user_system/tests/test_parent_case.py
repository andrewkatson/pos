from django.test import TestCase
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware

from .test_utils import get_response_fields
from ..classifiers.classifier_constants import POSITIVE_IMAGE_URL, POSITIVE_TEXT
from ..constants import Fields
from ..utils import convert_to_bool
from ..views import register, login_user, make_post, get_user_with_username, comment_on_post, reply_to_comment_thread
from .test_constants import username, email, password, SUCCESS, ip, LOGIN_USER, false, UserFields
from ..classifiers import image_classifier_fake, text_classifier_fake


class PositiveOnlySocialTestCase(TestCase):
    def setUp(self):
        super().setUp()

        # Every test needs access to the request factory.
        self.factory = RequestFactory()
        self.prefix = self._testMethodName
        self.user = AnonymousUser()

        # Create an instance of a POST request.
        self.register_request = self.factory.post("/user_system/register")

        # Recall that middleware are not supported. You can simulate a
        # logged-in user by setting request.user manually.
        self.register_request.user = self.user

        self.users = {
            UserFields.USERNAME: [],
            UserFields.EMAIL: [],
            UserFields.PASSWORD: [],
            UserFields.SESSION_MANAGEMENT_TOKEN: [],
            UserFields.SERIES_IDENTIFIER: [],
            UserFields.LOGIN_COOKIE_TOKEN: [],
            UserFields.POSTS: [],
        }

    def tearDown(self):
        super().tearDown()

    def setup_user_in_dict(self, username, password, email, remember_me, response, user_dict):
        fields = get_response_fields(response)

        # Store the info needed to call remember me later
        session_management_token = fields[Fields.session_management_token]

        if type(remember_me) is str:
            remember_me = convert_to_bool(remember_me)
        if remember_me:
            series_identifier = fields[Fields.series_identifier]
            login_cookie_token = fields[Fields.login_cookie_token]

            series_identifiers = user_dict.get(UserFields.SERIES_IDENTIFIER, [])
            series_identifiers.append(series_identifier)

            login_cookies = user_dict.get(UserFields.LOGIN_COOKIE_TOKEN, [])
            login_cookies.append(login_cookie_token)

        usernames = user_dict.get(UserFields.USERNAME, [])
        usernames.append(username)

        emails = user_dict.get(UserFields.EMAIL, [])
        emails.append(email)

        passwords = user_dict.get(UserFields.PASSWORD, [])
        passwords.append(password)

        session_management_tokens = user_dict.get(UserFields.SESSION_MANAGEMENT_TOKEN, [])
        session_management_tokens.append(session_management_token)

    def register_user_with_name(self, name, user_dict, remember_me=False):
        local_username = f'{name}_{username}_{self.prefix}'
        local_password = f'{name}_{password}_{self.prefix}'
        local_email = (f'{name}_{email}_{self.prefix}@email.com')

        # For this one we want to register a user with the info needed
        # to login later. All tests start with remember_me turned off on purpose.
        response = register(self.register_request, local_username, local_email, local_password, remember_me, ip)
        self.assertEqual(response.status_code, SUCCESS)

        self.setup_user_in_dict(local_username, local_password, local_email, remember_me, response, user_dict)

    def register_user(self, remember_me, num_user, user_dict):
        local_username = f'{num_user}_{username}_{self.prefix}'
        local_password = f'{num_user}_{password}_{self.prefix}'
        local_email = (f'{num_user}_{email}_{self.prefix}@email.com')

        # For this one we want to register a user with the info needed
        # to login later. All tests start with remember_me turned off on purpose.
        response = register(self.register_request, local_username, local_email, local_password, remember_me, ip)
        self.assertEqual(response.status_code, SUCCESS)

        self.setup_user_in_dict(local_username, local_password, local_email, remember_me, response, user_dict)


    def setup_local_values(self, remember_me):
        self.local_username = self.users.get(UserFields.USERNAME, [])[0]
        self.local_password = self.users.get(UserFields.PASSWORD, [])[0]
        self.local_email = self.users.get(UserFields.EMAIL, [])[0]
        self.session_management_token = self.users.get(UserFields.SESSION_MANAGEMENT_TOKEN, [])[0]

        if convert_to_bool(remember_me):
            self.series_identifier = self.users.get(UserFields.SERIES_IDENTIFIER, [])[0]
            self.login_cookie_token = self.users.get(UserFields.LOGIN_COOKIE_TOKEN, [])[0]

    def login_user_setup(self, remember_me, type_of_login=LOGIN_USER):
        self.register_user(remember_me, 0, self.users)

        # Create an instance of a POST request.
        self.login_user_request = self.factory.post(f"/user_system/{type_of_login}")

        # Also add a session
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(self.login_user_request)
        self.login_user_request.session.save()

        self.setup_local_values(remember_me)

    def login_user(self, remember_me):
        self.login_user_setup(remember_me)

        # Need to log the user in
        response = login_user(self.login_user_request, self.local_username, self.local_password, false, ip)
        self.assertEqual(response.status_code, SUCCESS)

    def make_post_and_login_user(self):
        self.login_user(false)

        return self.make_post(self.local_username, self.session_management_token)

    def make_post(self, username, session_management_token):
        self.make_post_request = self.make_post_request_obj('make_post', username)

        # Need to make a post
        response = make_post(self.make_post_request, session_management_token, POSITIVE_IMAGE_URL, POSITIVE_TEXT,
                             image_classifier_fake, text_classifier_fake)
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(username)

        post = user.post_set.first()
        return post, post.post_identifier

    def make_post_with_users(self, num=1):
        self.post, self.post_identifier = self.make_post_and_login_user()

        for i in range(num):
            # We don't need to re-register the first user.
            if i == 0:
                continue
            self.register_user(false, i, self.users)

        # Store some basic info used in these tests
        self.image_url = f'{self.prefix}.png'
        self.caption = f'This is my caption :P'

    def make_many_posts(self, num=1):
        for i in range(num):
            self.register_user(false, i, self.users)

            user_to_make_post = self.users.get(UserFields.USERNAME, [])[i]
            session_management_token = self.users.get(UserFields.SESSION_MANAGEMENT_TOKEN, [])[i]
            post, _ = self.make_post(user_to_make_post, session_management_token)
            self.users[UserFields.POSTS].append(post)

    def make_many_comments(self, num=1):

        self.post_identifier = None
        for i in range(num):
            self.register_user(false, i, self.users)
            user_to_make_comment = self.users.get(UserFields.USERNAME, [])[i]
            session_management_token = self.users.get(UserFields.SESSION_MANAGEMENT_TOKEN, [])[i]
            if i == 0:
                _, self.post_identifier = self.make_post(user_to_make_comment, session_management_token)

            self.comment_on_post_request = self.make_post_request_obj('comment_on_post', user_to_make_comment)

            response = comment_on_post(self.comment_on_post_request, session_management_token,
                                       str(self.post_identifier),
                                       POSITIVE_TEXT, text_classifier_fake)
            self.assertEqual(response.status_code, SUCCESS)

    def make_many_comments_on_thread(self, num=1):

        self.comment_thread_identifier = None
        self.post_identifier = None
        for i in range(num):
            self.register_user(false, i, self.users)
            user_to_make_comment = self.users.get(UserFields.USERNAME, [])[i]
            session_management_token = self.users.get(UserFields.SESSION_MANAGEMENT_TOKEN, [])[i]
            # The first user should make a post and comment on their own post
            if i == 0:
                _, self.post_identifier = self.make_post(user_to_make_comment, session_management_token)

                self.comment_on_post_request = self.make_post_request_obj('comment_on_post', user_to_make_comment)

                response = comment_on_post(self.comment_on_post_request, session_management_token,
                                           str(self.post_identifier),
                                           POSITIVE_TEXT, text_classifier_fake)
                self.assertEqual(response.status_code, SUCCESS)

                fields = get_response_fields(response)

                self.comment_thread_identifier = fields[Fields.comment_thread_identifier]
            else:
                self.reply_to_comment_thread_request = self.make_post_request_obj('reply_to_comment_thread',
                                                                                  user_to_make_comment)

                response = reply_to_comment_thread(self.reply_to_comment_thread_request, session_management_token,
                                                   str(self.post_identifier),
                                                   str(self.comment_thread_identifier), POSITIVE_TEXT, text_classifier_fake)
                self.assertEqual(response.status_code, SUCCESS)

    def comment_on_post_with_users(self, num=3):

        # Need at least three users so that one makes the post.
        # The other makes a comment.
        # And a third likes, unlikes, or reports the comment.
        self.make_post_with_users(num)

        other_session_management_tokens = self.users.get(UserFields.SESSION_MANAGEMENT_TOKEN, [])
        other_local_usernames = self.users.get(UserFields.USERNAME, [])
        other_local_passwords = self.users.get(UserFields.PASSWORD, [])

        self.commenter_session_management_token = other_session_management_tokens[1]
        self.commenter_local_username = other_local_usernames[1]
        self.commenter_local_password = other_local_passwords[1]

        # Login one of the users to do the commenting
        response = login_user(self.login_user_request, self.commenter_local_username, self.commenter_local_password,
                              false, ip)
        self.assertEqual(response.status_code, SUCCESS)

        self.comment_on_post_request = self.make_post_request_obj('comment_on_post', self.local_username)

        # Use comment_on_post
        response = comment_on_post(self.comment_on_post_request, self.commenter_session_management_token,
                                   str(self.post_identifier), POSITIVE_TEXT, text_classifier_fake)
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.local_username)
        post = user.post_set.first()
        self.comment_thread = post.commentthread_set.first()
        self.comment_thread_identifier = self.comment_thread.comment_thread_identifier

        self.comment = self.comment_thread.comment_set.first()
        self.comment_identifier = self.comment.comment_identifier

    def add_session_and_user_to_request(self, request, username):
        # Recall that middleware are not supported. You can simulate a
        # logged-in user by setting request.user manually.
        request.user = get_user_with_username(username)

        # Also add a session
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()

        return request

    def make_post_request_obj(self, method, username):
        # Create an instance of a POST request.
        request = self.factory.post(f"/user_system/{method}")

        return self.add_session_and_user_to_request(request, username)

    def make_delete_request_obj(self, method, username):
        # Create an instance of a POST request.
        request = self.factory.delete(f"/user_system/{method}")

        return self.add_session_and_user_to_request(request, username)

    def make_get_request_obj(self, method, username):
        # Create an instance of a POST request.
        request = self.factory.get(f"/user_system/{method}")

        return self.add_session_and_user_to_request(request, username)
