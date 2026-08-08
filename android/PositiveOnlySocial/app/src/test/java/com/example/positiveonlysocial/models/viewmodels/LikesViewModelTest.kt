package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.User
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.mock
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import retrofit2.Response

/**
 * Tests for "who liked this" (issue #478): the batched liker list behind your
 * own post's or comment's like count. Only your own content is ever listed.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class LikesViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var mockApi: PositiveOnlySocialAPI
    private lateinit var keychainHelper: KeychainHelperProtocol

    private val session = UserSession("token123", "ada", "1", false, null, null)

    private val postTarget = LikesTarget.Post("post-1")
    private val commentTarget = LikesTarget.Comment("post-1", "thread-1", "comment-1")

    private val likers = listOf(
        User(username = "alice", identityIsVerified = true),
        User(username = "bob", identityIsVerified = false)
    )

    @Before
    fun setup() {
        mockApi = mock()
        keychainHelper = mock()
        whenever(keychainHelper.load(any<Class<UserSession>>(), any(), any())).thenReturn(session)
    }

    @Test
    fun `a post target loads the first batch from getPostLikers`() = runTest {
        whenever(mockApi.getPostLikers("token123", "post-1", 0)).thenReturn(Response.success(likers))
        val viewModel = LikesViewModel(postTarget, mockApi, keychainHelper)

        viewModel.load()

        assertEquals(likers, viewModel.users.value)
        assertTrue(viewModel.canLoadMore.value)
        assertFalse(viewModel.isLoading.value)
        assertNull(viewModel.errorMessage.value)
    }

    @Test
    fun `a comment target loads from getCommentLikers`() = runTest {
        whenever(mockApi.getCommentLikers("token123", "post-1", "thread-1", "comment-1", 0))
            .thenReturn(Response.success(likers))
        val viewModel = LikesViewModel(commentTarget, mockApi, keychainHelper)

        viewModel.load()

        assertEquals(likers, viewModel.users.value)
        verify(mockApi).getCommentLikers("token123", "post-1", "thread-1", "comment-1", 0)
    }

    @Test
    fun `an empty first batch means nobody liked it and there is no more to load`() = runTest {
        whenever(mockApi.getPostLikers("token123", "post-1", 0))
            .thenReturn(Response.success(emptyList()))
        val viewModel = LikesViewModel(postTarget, mockApi, keychainHelper)

        viewModel.load()

        assertEquals(emptyList<User>(), viewModel.users.value)
        assertFalse(viewModel.canLoadMore.value)
        assertNull(viewModel.errorMessage.value)
    }

    @Test
    fun `loadMore appends the next batch and stops on an empty one`() = runTest {
        val more = listOf(User(username = "carol", identityIsVerified = false))
        whenever(mockApi.getPostLikers("token123", "post-1", 0)).thenReturn(Response.success(likers))
        whenever(mockApi.getPostLikers("token123", "post-1", 1)).thenReturn(Response.success(more))
        whenever(mockApi.getPostLikers("token123", "post-1", 2))
            .thenReturn(Response.success(emptyList()))
        val viewModel = LikesViewModel(postTarget, mockApi, keychainHelper)

        viewModel.load()
        viewModel.loadMore()

        // The first batch stays listed rather than being replaced.
        assertEquals(likers + more, viewModel.users.value)
        assertTrue(viewModel.canLoadMore.value)

        viewModel.loadMore()

        assertEquals(likers + more, viewModel.users.value)
        assertFalse(viewModel.canLoadMore.value)
    }

    @Test
    fun `someone elses post is refused and the error is surfaced`() = runTest {
        val errorBody = "{\"error\":\"No post with that identifier by that user\"}"
            .toResponseBody("application/json".toMediaTypeOrNull())
        whenever(mockApi.getPostLikers("token123", "post-1", 0)).thenReturn(Response.error(400, errorBody))
        val viewModel = LikesViewModel(postTarget, mockApi, keychainHelper)

        viewModel.load()

        assertEquals("No post with that identifier by that user", viewModel.errorMessage.value)
        assertEquals(emptyList<User>(), viewModel.users.value)
        // A failed page stops paging rather than retrying into the same error.
        assertFalse(viewModel.canLoadMore.value)
    }

    @Test
    fun `a failed later batch keeps what is already listed`() = runTest {
        val errorBody = "{\"error\":\"Something went wrong\"}"
            .toResponseBody("application/json".toMediaTypeOrNull())
        whenever(mockApi.getPostLikers("token123", "post-1", 0)).thenReturn(Response.success(likers))
        whenever(mockApi.getPostLikers("token123", "post-1", 1)).thenReturn(Response.error(500, errorBody))
        val viewModel = LikesViewModel(postTarget, mockApi, keychainHelper)

        viewModel.load()
        viewModel.loadMore()

        assertEquals(likers, viewModel.users.value)
        assertEquals("Something went wrong", viewModel.errorMessage.value)
        assertFalse(viewModel.canLoadMore.value)
    }

    @Test
    fun `the target names what the dialog is listing`() {
        assertEquals("Likes", postTarget.title)
        assertEquals("Comment likes", commentTarget.title)
    }
}
