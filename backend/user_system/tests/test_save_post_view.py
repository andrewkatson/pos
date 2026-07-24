from django.urls import reverse

from ..constants import Fields, HIDDEN_REASON_CLASSIFIER
from .test_constants import UserFields
from .test_parent_case import PositiveOnlySocialTestCase
from ..models import Post, SavedPost
from ..views import get_user_with_username

invalid_session_management_token = '?'
invalid_post_identifier = '?'


class SavePostTests(PositiveOnlySocialTestCase):
    """Saving/unsaving posts for later revisiting (issue #193)."""

    def setUp(self):
        super().setUp()

        # User 0 posts; User 1 is the saver.
        super().make_post_with_users(2)

        self.poster_token = self.session_management_token
        self.poster_header = {'HTTP_AUTHORIZATION': f'Bearer {self.poster_token}'}

        self.saver_token = self.users.get(UserFields.TOKEN, [])[1]
        self.saver_header = {'HTTP_AUTHORIZATION': f'Bearer {self.saver_token}'}

        self.save_url = reverse('save_post', kwargs={'post_identifier': str(self.post_identifier)})
        self.unsave_url = reverse('unsave_post', kwargs={'post_identifier': str(self.post_identifier)})

        self.post = Post.objects.get(post_identifier=self.post_identifier)

    def test_invalid_session_management_token_returns_bad_response(self):
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}
        response = self.client.post(self.save_url, **invalid_header)
        self.assertEqual(response.status_code, 401)

    def test_invalid_post_identifier_returns_bad_response(self):
        invalid_url = f'posts/{invalid_post_identifier}/save/'
        response = self.client.post(invalid_url, **self.saver_header)
        self.assertEqual(response.status_code, 404)

    def test_save_post_happy_path(self):
        self.assertEqual(self.post.savedpost_set.count(), 0)

        response = self.client.post(self.save_url, **self.saver_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Post saved'})
        self.post.refresh_from_db()
        self.assertEqual(self.post.savedpost_set.count(), 1)

    def test_save_own_post_is_allowed(self):
        """Unlike a like, saving is a personal bookmark, so the author may save
        their own post."""
        response = self.client.post(self.save_url, **self.poster_header)
        self.assertEqual(response.status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.savedpost_set.count(), 1)

    def test_save_post_twice_returns_bad_response(self):
        first = self.client.post(self.save_url, **self.saver_header)
        self.assertEqual(first.status_code, 200)

        second = self.client.post(self.save_url, **self.saver_header)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.json(), {'error': 'Already saved post'})

        self.post.refresh_from_db()
        self.assertEqual(self.post.savedpost_set.count(), 1)

    def test_cannot_save_post_not_visible_to_user(self):
        """A post hidden from the saver (not its author) can't be saved — it
        would just be an empty row on the saved screen."""
        self.post.hidden = True
        self.post.hidden_reason = HIDDEN_REASON_CLASSIFIER
        self.post.save()

        response = self.client.post(self.save_url, **self.saver_header)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'No post with that identifier'})
        self.assertEqual(SavedPost.objects.count(), 0)

    def test_unsave_post_happy_path(self):
        self.client.post(self.save_url, **self.saver_header)
        self.post.refresh_from_db()
        self.assertEqual(self.post.savedpost_set.count(), 1)

        response = self.client.post(self.unsave_url, **self.saver_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Post unsaved'})
        self.post.refresh_from_db()
        self.assertEqual(self.post.savedpost_set.count(), 0)

    def test_unsave_post_not_saved_returns_bad_response(self):
        response = self.client.post(self.unsave_url, **self.saver_header)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Post not saved yet'})


class GetSavedPostsTests(PositiveOnlySocialTestCase):
    """The saved-posts listing endpoint (issue #193)."""

    def setUp(self):
        super().setUp()

        # A poster with three approved posts.
        poster = self.make_user_with_posts(num_posts=3)
        self.poster_user = get_user_with_username(poster[Fields.username])
        self.posts = list(self.poster_user.post_set.all().order_by('creation_time'))

        # The saver, who bookmarks some of them.
        saver = self.make_user_with_prefix('saver')
        self.saver_token = saver[Fields.session_management_token]
        self.saver_header = {'HTTP_AUTHORIZATION': f'Bearer {self.saver_token}'}

        self.list_url = reverse('get_saved_posts', kwargs={'batch': 0})

    def _save(self, post):
        url = reverse('save_post', kwargs={'post_identifier': str(post.post_identifier)})
        response = self.client.post(url, **self.saver_header)
        self.assertEqual(response.status_code, 200)

    def test_empty_when_nothing_saved(self):
        response = self.client.get(self.list_url, **self.saver_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_lists_only_saved_posts_marked_saved(self):
        self._save(self.posts[0])
        self._save(self.posts[2])

        response = self.client.get(self.list_url, **self.saver_header)
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        returned_ids = {p[Fields.post_identifier] for p in payload}
        self.assertEqual(
            returned_ids,
            {str(self.posts[0].post_identifier), str(self.posts[2].post_identifier)},
        )
        for row in payload:
            self.assertTrue(row[Fields.is_saved])

    def test_ordered_by_most_recently_saved_first(self):
        # Save post 0 first, then post 1, so post 1 should come back first.
        self._save(self.posts[0])
        self._save(self.posts[1])

        payload = self.client.get(self.list_url, **self.saver_header).json()
        self.assertEqual(
            [p[Fields.post_identifier] for p in payload],
            [str(self.posts[1].post_identifier), str(self.posts[0].post_identifier)],
        )

    def test_hidden_post_drops_off_saved_list(self):
        """A post saved while live silently disappears from the saved list once
        it is hidden, rather than rendering as an empty tile."""
        self._save(self.posts[0])
        self.posts[0].hidden = True
        self.posts[0].hidden_reason = HIDDEN_REASON_CLASSIFIER
        self.posts[0].save()

        payload = self.client.get(self.list_url, **self.saver_header).json()
        self.assertEqual(payload, [])
