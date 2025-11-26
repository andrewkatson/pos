from django.test import TestCase, Client
from django.urls import reverse

# Note: test_constants are no longer used for FAIL/SUCCESS
from .test_constants import ip, false, UserFields
# Note: test_utils.get_response_fields is replaced by response.json()
from ..classifiers.classifier_constants import POSITIVE_IMAGE_URL, POSITIVE_TEXT
from ..constants import Fields, testing
from ..models import Post, CommentThread, Comment

class PositiveOnlySocialTestCase(TestCase):
    """
    A parent test case for the PositiveOnlySocial app that uses the
    Django test client to make real API requests.
    """

    def setUp(self):
        super().setUp()

        # Use the built-in Django test client
        self.client = Client()

        # A prefix for each test method to ensure unique usernames/emails
        self.prefix = self._testMethodName

        # A dictionary to store data for multi-user tests
        self.users = {
            UserFields.USERNAME: [],
            UserFields.EMAIL: [],
            UserFields.PASSWORD: [],
            UserFields.TOKEN: [],  # Replaced session_management_token
            UserFields.POSTS: [],
        }

        # --- Placeholders for common test values ---
        self.local_username = None
        self.local_password = None
        self.local_email = None
        self.session_management_token = None
        self.post_identifier = None
        self.post = None
        self.comment_thread_identifier = None
        self.comment_thread = None
        self.comment_identifier = None
        self.comment = None
        self.commenter_session_management_token = None
        self.commenter_local_username = None

        # --- Testing flags ---
        testing = True 

    # =========================================================================
    # INTERNAL ("Private") CORE HELPERS
    # =========================================================================

    def _get_unique_username(self, name_base):
        """Creates a unique username for a test."""
        return f'{name_base}_{self.prefix}'

    def _store_user_in_dict(self, username, password, email, response_data):
        """Helper to populate self.users dict."""
        token = response_data.get(Fields.session_management_token)

        self.users[UserFields.USERNAME].append(username)
        self.users[UserFields.EMAIL].append(email)
        self.users[UserFields.PASSWORD].append(password)
        self.users[UserFields.TOKEN].append(token)

    def _register_user(self, username, email, password, remember_me=false):
        """
        Calls the 'register' endpoint and returns the parsed JSON response.
        Asserts that the registration was successful (201 Created).
        """
        url = reverse('register')
        data = {
            'username': username,
            'email': email,
            'password': password,
            'remember_me': remember_me,
            'ip': ip
        }
        response = self.client.post(url, data=data, content_type='application/json')

        # 201 Created is the standard for successful creation
        self.assertEqual(response.status_code, 201)

        response_data = response.json()
        self._store_user_in_dict(username, password, email, response_data)
        return response_data

    def _login_user(self, username, password, remember_me=false):
        """
        Calls the 'login_user' endpoint and returns the parsed JSON response.
        Asserts that the login was successful (200 OK).
        """
        url = reverse('login_user')
        data = {
            'username_or_email': username,
            'password': password,
            'remember_me': remember_me,
            'ip': ip
        }
        response = self.client.post(url, data=data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _make_post(self, token, image_url=POSITIVE_IMAGE_URL, caption=POSITIVE_TEXT):
        """
        Calls the 'make_post' endpoint with a valid auth token.
        Returns the parsed JSON response. Asserts 201 Created.
        NOTE: The calling test MUST patch the image/text classifiers.
        """
        url = reverse('make_post')
        header = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        data = {'image_url': image_url, 'caption': caption}

        response = self.client.post(url, data=data, content_type='application/json', **header)

        self.assertEqual(response.status_code, 201)
        return response.json()

    def _comment_on_post(self, token, post_id, comment_text=POSITIVE_TEXT):
        """
        Calls the 'comment_on_post' endpoint with a valid auth token.
        Returns the parsed JSON response. Asserts 201 Created.
        NOTE: The calling test MUST patch the text classifier.
        """
        url = reverse('comment_on_post', kwargs={'post_identifier': str(post_id)})
        header = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        data = {'comment_text': comment_text}

        response = self.client.post(url, data=data, content_type='application/json', **header)

        self.assertEqual(response.status_code, 201)
        return response.json()

    def _reply_to_comment_thread(self, token, post_id, thread_id, comment_text=POSITIVE_TEXT):
        """
        Calls the 'reply_to_comment_thread' endpoint with a valid auth token.
        Returns the parsed JSON response. Asserts 201 Created.
        NOTE: The calling test MUST patch the text classifier.
        """
        url = reverse('reply_to_comment_thread', kwargs={
            'post_identifier': str(post_id),
            'comment_thread_identifier': str(thread_id)
        })
        header = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        data = {'comment_text': comment_text}

        response = self.client.post(url, data=data, content_type='application/json', **header)

        self.assertEqual(response.status_code, 201)
        return response.json()

    def _setup_local_user(self, index=0):
        """
        Populates self.local_... attributes from the user at the given
        index in self.users.
        """
        self.local_username = self.users[UserFields.USERNAME][index]
        self.local_password = self.users[UserFields.PASSWORD][index]
        self.local_email = self.users[UserFields.EMAIL][index]
        self.session_management_token = self.users[UserFields.TOKEN][index]

    # =========================================================================
    # HIGH-LEVEL "PUBLIC" HELPERS FOR TESTS
    # =========================================================================

    def make_user(self, local_username, local_password=None, remember_me=false):
        """
        Registers a new user and returns the API response.
        This is a simple, high-level wrapper around _register_user.
        """
        local_email = f'{local_username}_email@email.com'
        if not local_password:
            local_password = f'{local_username}_Password123!'

        return self._register_user(local_username, local_email, local_password, remember_me)

    def make_user_with_prefix(self, prefix=''):
        """
        Creates and "logs in" a new, unique user (User B).
        Returns their username and token.
        """
        username = self._get_unique_username(f"{prefix}_other_user")
        password = "OtherPassword123$"
        email = f"{username}@email.com"

        data = self._register_user(username, email, password)
        return {
            'username': username,
            'password': password,
            'email': email,
            'token': data[Fields.session_management_token]
        }

    def register_user_and_setup_local_fields(self, index=0, remember_me=false):
        """
        The main setup helper for single-user tests.
        Creates one user, registers them, and populates all
        self.local_... attributes (username, token, etc.).
        """
        username = self._get_unique_username(f'testuser_{remember_me}')
        password = f'Password_{self.prefix}123!'
        email = f'{username}@email.com'

        register_fields = self._register_user(username, email, password, remember_me)

        if remember_me:
            self.series_identifier = register_fields[Fields.series_identifier]
            self.login_cookie_token = register_fields[Fields.login_cookie_token]

        self._setup_local_user(index)

    def register_and_login_user(self, prefix=''):
        """
        Registers a user and logs them in. Populates all self.local_... attributes.
        Args:
            prefix: The username prefix

        Returns:
            dictionary of values related to registering
        """

        register_fields = self.make_user_with_prefix(prefix=prefix)

        self._login_user(register_fields[Fields.username], register_fields[Fields.password])

        return register_fields

    def make_post_and_login_user(self):
        """
        Logs in one user, has them create one post, and sets
        self.post and self.post_identifier.
        NOTE: The CALLING TEST must patch the classifiers.
        """
        self.register_user_and_setup_local_fields()

        post_data = self._make_post(self.session_management_token)
        post_id = post_data[Fields.post_identifier]

        self.post_identifier = post_id
        self.post = Post.objects.get(post_identifier=post_id)
        return self.post, self.post_identifier

    def make_post_with_users(self, num=1):
        """
        Creates user 0, has them make a post, then creates num-1
        additional users.
        NOTE: The CALLING TEST must patch the classifiers.
        """
        self.make_post_and_login_user()  # Creates user 0 and post

        for i in range(1, num):
            username = self._get_unique_username(f'user{i}')
            self.make_user(username)

    def make_many_posts(self, num=1):
        """
        Creates 'num' users and has each one create one post.
        Populates self.users[UserFields.POSTS].
        NOTE: The CALLING TEST must patch the classifiers.
        """
        for i in range(num):
            username = self._get_unique_username(f'user{i}')
            password = f'Password_{i}_{self.prefix}!'
            email = f'{username}@email.com'

            data = self._register_user(username, email, password)
            token = data[Fields.session_management_token]

            post_data = self._make_post(token)
            post = Post.objects.get(post_identifier=post_data[Fields.post_identifier])
            self.users[UserFields.POSTS].append(post)

        # Set up local values for the first user
        self.register_user_and_setup_local_fields()

    def make_many_comments(self, num=1):
        """
        Creates 'num' users. User 0 makes a post. Then all 'num' users
        create one top-level comment thread on that post.
        NOTE: The CALLING TEST must patch the classifiers.
        """
        for i in range(num):
            username = self._get_unique_username(f'user{i}')
            password = f'Password_{i}_{self.prefix}!'
            email = f'{username}@email.com'

            data = self._register_user(username, email, password)
            token = data[Fields.session_management_token]

            if i == 0:
                post_data = self._make_post(token)
                self.post_identifier = post_data[Fields.post_identifier]
                self.post = Post.objects.get(post_identifier=self.post_identifier)

            self._comment_on_post(token, self.post_identifier)

        self.assertEqual(self.post.commentthread_set.count(), num)
        self.register_user_and_setup_local_fields()

    def make_many_comments_on_thread(self, num=1):
        """
        Creates 'num' users. User 0 makes a post and one comment.
        All other 'num-1' users reply to that one comment thread.
        NOTE: The CALLING TEST must patch the classifiers.
        """
        for i in range(num):
            username = self._get_unique_username(f'user{i}')
            password = f'Password_{i}_{self.prefix}!'
            email = f'{username}@email.com'

            data = self._register_user(username, email, password)
            token = data[Fields.session_management_token]

            if i == 0:
                post_data = self._make_post(token)
                self.post_identifier = post_data[Fields.post_identifier]

                comment_data = self._comment_on_post(token, self.post_identifier)
                self.comment_thread_identifier = comment_data[Fields.comment_thread_identifier]
            else:
                self._reply_to_comment_thread(token, self.post_identifier, self.comment_thread_identifier)

        self.register_user_and_setup_local_fields()

    def comment_on_post_with_users(self, num=3):
        """
        Creates 'num' users. User 0 makes a post. User 1 comments.
        Sets up self.commenter... and self.liker... attributes.
        NOTE: The CALLING TEST must patch the classifiers.
        """
        self.make_post_with_users(num)  # Creates users, user 0 makes post

        # User 1 is the commenter
        self.commenter_local_username = self.users[UserFields.USERNAME][1]
        self.commenter_session_management_token = self.users[UserFields.TOKEN][1]

        # User 1 posts the comment
        comment_data = self._comment_on_post(
            self.commenter_session_management_token,
            self.post_identifier
        )

        # Set all relevant attributes for tests
        self.comment_thread_identifier = comment_data[Fields.comment_thread_identifier]
        self.comment_identifier = comment_data[Fields.comment_identifier]

        self.comment_thread = CommentThread.objects.get(comment_thread_identifier=self.comment_thread_identifier)
        self.comment = Comment.objects.get(comment_identifier=self.comment_identifier)

    def make_user_with_posts(self, num_posts=1):
        """
        Creates 'num' users. User 0 makes num_posts number of posts.
        Args:
            num_posts: The number of posts to make for User 0.

        Returns:
            A dict of user fields
        """

        fields = self.make_user_with_prefix(prefix='poster')

        for i in range(num_posts):
            self._make_post(fields[Fields.session_management_token])
        return fields
