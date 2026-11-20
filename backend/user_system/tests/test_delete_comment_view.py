from unittest.mock import patch
import os
from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..classifiers.classifier_constants import POSITIVE_TEXT
from ..constants import BAN_TYPE_SHADOW, Fields, POST_AUDIENCE_FAMILY
from ..models import Comment, UserBan
from ..views import get_user_with_username

invalid_session_management_token = '?'
invalid_post_identifier = '?'
invalid_comment_identifier = '?'
invalid_comment_thread_identifier = '?'


class DeleteCommentTests(PositiveOnlySocialTestCase):

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def setUp(self):
        super().setUp()

        # 1. Create a user, log them in, and create a post
        self.post, self.post_identifier = super().make_post_and_login_user()
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.user = get_user_with_username(self.local_username)

        # 2. Make a comment on that post using the test client
        comment_url = reverse('comment_on_post', kwargs={'post_identifier': str(self.post_identifier)})
        comment_data = {'comment_text': POSITIVE_TEXT}

        response = self.client.post(
            comment_url,
            data=comment_data,
            content_type='application/json',
            **self.valid_header
        )
        self.assertEqual(response.status_code, 201)  # 201 Created

        # 3. Get the created comment's details for testing
        fields = response.json()
        self.comment_thread_identifier = fields[Fields.comment_thread_identifier]
        self.comment_identifier = fields[Fields.comment_identifier]

        # 4. Store the created post and thread for later assertions
        self.post = self.user.post_set.first()
        self.comment_thread = self.post.commentthread_set.get(
            comment_thread_identifier=self.comment_thread_identifier
        )

        # 5. Define the URL for the delete operation
        self.delete_url = reverse('delete_comment', kwargs={
            'post_identifier': self.post_identifier,
            'comment_thread_identifier': self.comment_thread_identifier,
            'comment_identifier': self.comment_identifier
        })

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that @api_login_required rejects an invalid token.
        """
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.post(self.delete_url, **invalid_header)

        # @api_login_required should return 401 Unauthorized
        self.assertEqual(response.status_code, 401)

    def test_invalid_post_identifier_returns_bad_response(self):
        """
        Tests that a malformed post_identifier in the URL is rejected.
        """
        invalid_url = f"/user_index/posts/{invalid_post_identifier}/threads/{self.comment_thread_identifier}/comments/{self.comment_identifier}/delete/"

        response = self.client.post(invalid_url, **self.valid_header)

        # View's pattern matching should return 404 malformed url
        self.assertEqual(response.status_code, 404)

    def test_invalid_comment_thread_identifier_returns_bad_response(self):
        """
        Tests that a malformed comment_thread_identifier in the URL is rejected.
        """
        invalid_url = f"/user_index/posts/{self.post_identifier}/threads/{invalid_comment_thread_identifier}/comments/{self.comment_identifier}/delete/"

        response = self.client.post(invalid_url, **self.valid_header)

        # View's pattern matching should return 404 malformed url
        self.assertEqual(response.status_code, 404)

    def test_invalid_comment_identifier_returns_bad_response(self):
        """
        Tests that a malformed comment_identifier in the URL is rejected.
        """
        invalid_url = f"/user_index/posts/{self.post_identifier}/threads/{self.comment_thread_identifier}/comments/{invalid_comment_identifier}/delete/"

        response = self.client.post(invalid_url, **self.valid_header)

        # View's pattern matching should return 404 malformed url
        self.assertEqual(response.status_code, 404)

    def test_cannot_delete_another_users_comment(self):
        """
        Tests that a user cannot delete a comment they do not own.
        """
        # 1. Create a second user and log them in
        other_user_data = self.make_user_with_prefix(prefix='Delete_another_user_comment')
        other_header = {'HTTP_AUTHORIZATION': f'Bearer {other_user_data[Fields.session_management_token]}'}

        # 2. Try to delete the first user's comment
        response = self.client.post(self.delete_url, **other_header)

        # 3. Check for authorization failure
        self.assertEqual(response.status_code, 400)

        # 4. Verify the comment was NOT deleted
        self.comment_thread.refresh_from_db()
        self.assertEqual(self.comment_thread.comment_set.count(), 1)

    def test_delete_comment_returns_good_response_and_deletes_comment(self):
        """
        Tests that a valid request successfully deletes the comment.
        """
        # Verify comment exists before deletion
        self.assertEqual(self.comment_thread.comment_set.count(), 1)

        response = self.client.post(self.delete_url, **self.valid_header)

        # 1. Check for a successful response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Comment deleted'})

        # 2. Verify the comment is gone from the database
        self.comment_thread.refresh_from_db()
        self.assertEqual(self.comment_thread.comment_set.count(), 0)


class PostAuthorDeletesCommentTests(PositiveOnlySocialTestCase):
    """A post's author may delete other people's comments on their post so they
    can moderate their own comment section (issue #603) — but only comments they
    are actually shown there."""

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def setUp(self):
        super().setUp()

        # The post author, logged in as the local user.
        self.post, self.post_identifier = super().make_post_and_login_user()
        self.owner_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

        # Someone else who comments on that post.
        commenter_data = self.make_user_with_prefix(prefix='post_author_delete_commenter')
        self.commenter = get_user_with_username(commenter_data['username'])
        self.commenter_header = {
            'HTTP_AUTHORIZATION': f'Bearer {commenter_data[Fields.session_management_token]}'}

        self.thread = self.post.commentthread_set.create()
        self.comment = self._make_comment()

    def _make_comment(self, **overrides):
        """A live comment by the commenter, created directly so the classifier
        is not involved."""
        fields = {'author': self.commenter, 'body': POSITIVE_TEXT, 'hidden': False}
        fields.update(overrides)
        return self.thread.comment_set.create(**fields)

    def _delete_url(self, comment):
        return reverse('delete_comment', kwargs={
            'post_identifier': self.post_identifier,
            'comment_thread_identifier': self.thread.comment_thread_identifier,
            'comment_identifier': comment.comment_identifier,
        })

    def _exists(self, comment):
        return Comment.objects.filter(pk=comment.pk).exists()

    def test_post_author_can_delete_someone_elses_comment(self):
        response = self.client.post(self._delete_url(self.comment), **self.owner_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Comment deleted'})
        self.assertFalse(self._exists(self.comment))

    def test_post_author_deleting_a_reply_leaves_the_rest_of_the_thread(self):
        reply = self._make_comment()

        response = self.client.post(self._delete_url(reply), **self.owner_header)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(self._exists(reply))
        self.assertTrue(self._exists(self.comment))

    def test_commenter_can_still_delete_their_own_comment(self):
        response = self.client.post(self._delete_url(self.comment), **self.commenter_header)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(self._exists(self.comment))

    def test_third_party_cannot_delete_a_comment_on_someone_elses_post(self):
        """Neither the comment's author nor the post's author: refused, exactly
        as before — even if they have posts of their own."""
        stranger_data = self.make_user_with_prefix(prefix='post_author_delete_stranger')
        stranger = get_user_with_username(stranger_data['username'])
        stranger.post_set.create(caption=POSITIVE_TEXT, hidden=False)
        stranger_header = {
            'HTTP_AUTHORIZATION': f'Bearer {stranger_data[Fields.session_management_token]}'}

        response = self.client.post(self._delete_url(self.comment), **stranger_header)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Not authorized to delete comment'})
        self.assertTrue(self._exists(self.comment))

    def test_commenter_cannot_delete_other_comments_on_the_post(self):
        """Commenting on a post grants no say over its other comments."""
        other_comment = self.thread.comment_set.create(
            author=self.post.author, body=POSITIVE_TEXT, hidden=False)

        response = self.client.post(self._delete_url(other_comment), **self.commenter_header)

        self.assertEqual(response.status_code, 400)
        self.assertTrue(self._exists(other_comment))

    def test_post_author_cannot_delete_a_hidden_comment(self):
        """A hidden comment is out of the post author's sight (and may be under
        appeal), so it is not theirs to remove."""
        hidden = self._make_comment(hidden=True)

        response = self.client.post(self._delete_url(hidden), **self.owner_header)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Not authorized to delete comment'})
        self.assertTrue(self._exists(hidden))

    def test_post_author_cannot_delete_a_shadow_banned_users_comment(self):
        """A shadow-banned commenter's comments are invisible to the post author,
        and the refusal matches a stranger's so it reveals nothing."""
        UserBan.objects.create(user=self.commenter, ban_type=BAN_TYPE_SHADOW)

        response = self.client.post(self._delete_url(self.comment), **self.owner_header)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Not authorized to delete comment'})
        self.assertTrue(self._exists(self.comment))

    def test_post_author_cannot_delete_a_comment_whose_audience_excludes_them(self):
        """A family-only comment from someone who has not labeled the post author
        family is not shown to them, so they cannot delete it."""
        family_only = self._make_comment(audience=POST_AUDIENCE_FAMILY)

        response = self.client.post(self._delete_url(family_only), **self.owner_header)

        self.assertEqual(response.status_code, 400)
        self.assertTrue(self._exists(family_only))
