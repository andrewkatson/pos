import os
from unittest.mock import patch

from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields, PROFILE_IMAGE_STATUS_APPROVED
from ..models import PositiveOnlySocialUser
from ..views import get_user_with_username


def _approved_avatar_for(user):
    url = f'https://test-bucket.s3.amazonaws.com/{user.id}/avatar.jpeg'
    PositiveOnlySocialUser.objects.filter(pk=user.pk).update(
        profile_image_url=url, profile_image_status=PROFILE_IMAGE_STATUS_APPROVED)
    return url


@patch.dict(os.environ, {"TESTING": "True"}, clear=True)
class ProfilePhotoSerializationTests(PositiveOnlySocialTestCase):
    """The approved author photo is threaded through the list/detail payloads
    next to author_username."""

    def test_profile_grid_includes_author_avatar(self):
        self.make_post_and_login_user()
        author = get_user_with_username(self.local_username)
        avatar = _approved_avatar_for(author)

        header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        url = reverse('get_posts_for_user', kwargs={'username': author.username, 'batch': 0})
        data = self.client.get(url, **header).json()

        self.assertTrue(len(data) >= 1)
        row = next(r for r in data if r[Fields.author_username] == author.username)
        self.assertEqual(row[Fields.author_profile_image_original_url], avatar)
        self.assertIsNotNone(row[Fields.author_profile_image_url])

    def test_post_details_includes_author_avatar(self):
        self.make_post_and_login_user()
        author = get_user_with_username(self.local_username)
        avatar = _approved_avatar_for(author)

        header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        url = reverse('get_post_details', kwargs={'post_identifier': str(self.post_identifier)})
        data = self.client.get(url, **header).json()

        self.assertEqual(data[Fields.author_profile_image_original_url], avatar)

    def test_comment_includes_author_avatar(self):
        self.comment_on_post_with_users(num=3)
        commenter = get_user_with_username(self.commenter_local_username)
        avatar = _approved_avatar_for(commenter)

        # Any logged-in viewer (the commenter themselves here).
        header = {'HTTP_AUTHORIZATION': f'Bearer {self.commenter_session_management_token}'}
        url = reverse('get_comments_for_thread',
                      kwargs={'comment_thread_identifier': str(self.comment_thread_identifier), 'batch': 0})
        data = self.client.get(url, **header).json()

        self.assertTrue(len(data) >= 1)
        row = next(r for r in data if r[Fields.author_username] == commenter.username)
        self.assertEqual(row[Fields.author_profile_image_original_url], avatar)

    def test_search_includes_avatar(self):
        self.register_user_and_setup_local_fields()
        searcher_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        target = self.make_user_with_prefix(prefix='searchtarget')
        target_user = get_user_with_username(target['username'])
        avatar = _approved_avatar_for(target_user)

        fragment = target_user.username[:5]
        url = reverse('get_users_matching_fragment', kwargs={'username_fragment': fragment})
        data = self.client.get(url, **searcher_header).json()

        row = next(r for r in data if r[Fields.username] == target_user.username)
        self.assertEqual(row[Fields.author_profile_image_original_url], avatar)

    def test_author_without_photo_serializes_null(self):
        self.make_post_and_login_user()
        author = get_user_with_username(self.local_username)

        header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        url = reverse('get_posts_for_user', kwargs={'username': author.username, 'batch': 0})
        data = self.client.get(url, **header).json()

        row = next(r for r in data if r[Fields.author_username] == author.username)
        self.assertIsNone(row[Fields.author_profile_image_url])
        self.assertIsNone(row[Fields.author_profile_image_original_url])
