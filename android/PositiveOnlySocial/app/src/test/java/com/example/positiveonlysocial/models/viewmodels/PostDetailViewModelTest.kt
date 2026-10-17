package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.CommentDto
import com.example.positiveonlysocial.data.model.CommentThreadDto
import com.example.positiveonlysocial.data.model.CommentViewData
import com.example.positiveonlysocial.data.model.CommentThreadViewData
import com.example.positiveonlysocial.data.model.GenericResponse
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.data.model.SetCommentsDisabledResponse
import com.example.positiveonlysocial.data.model.UserSession
import java.util.Date
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.runTest
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.mock
import org.mockito.kotlin.never
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import retrofit2.Response

@OptIn(ExperimentalCoroutinesApi::class)
class PostDetailViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var viewModel: PostDetailViewModel
    private lateinit var api: PositiveOnlySocialAPI
    private lateinit var keychainHelper: KeychainHelperProtocol

    private val mockUserSession = UserSession("token123", "testuser", "1", false, null, null)
    private val postIdentifier = "post123"

    @Before
    fun setup() {
        api = mock()
        keychainHelper = mock()
        
        whenever(keychainHelper.load(any<Class<UserSession>>(), any(), any())).thenReturn(mockUserSession)

        runBlocking {
            // Mock API calls for loadAllData which is called in init
            whenever(api.getPostDetails("token123", postIdentifier)).thenReturn(
                Response.success(
                    Post(
                        postIdentifier,
                        "url",
                        "caption",
                        "user",
                        1
                    )
                )
            )
            whenever(api.getCommentsForPost("token123", postIdentifier, 0)).thenReturn(
                Response.success(
                    emptyList()
                )
            )
        }
        viewModel = PostDetailViewModel(postIdentifier, api, keychainHelper)
    }

    @Test
    fun `loadAllData success updates postDetail`() = runTest {
        // loadAllData is called in init, so we just verify the state
        assertNotNull(viewModel.postDetail.value)
        assertEquals(postIdentifier, viewModel.postDetail.value?.postIdentifier)
        assertFalse(viewModel.isLoading.value)
    }

    @Test
    fun `likePost calls api and reloads data`() = runTest {
        whenever(api.likePost("token123", postIdentifier)).thenReturn(Response.success(
            GenericResponse("Success", "None")))
        
        viewModel.likePost()

        verify(api).likePost("token123", postIdentifier)
        // Verify loadAllData is called again (getPostDetails called twice: once in init, once after like)
        verify(api, org.mockito.kotlin.times(2)).getPostDetails("token123", postIdentifier)
    }

    @Test
    fun `likePost does nothing on the user's own post`() = runTest {
        // A post authored by the signed-in user ("testuser").
        whenever(api.getPostDetails("token123", postIdentifier)).thenReturn(
            Response.success(Post(postIdentifier, "url", "caption", "testuser", 1))
        )
        val ownViewModel = PostDetailViewModel(postIdentifier, api, keychainHelper)

        ownViewModel.likePost()

        // The like request is never sent for the user's own post.
        verify(api, never()).likePost(any(), any())
    }

    @Test
    fun `likeComment does nothing on the user's own comment`() = runTest {
        val ownComment = CommentViewData("c1", "t1", "testuser", "body", 0, false, Date())

        viewModel.likeComment(ownComment, "t1")

        verify(api, never()).likeComment(any(), any(), any(), any())
    }

    @Test
    fun `likeComment calls api on another user's comment`() = runTest {
        whenever(api.likeComment(any(), any(), any(), any())).thenReturn(
            Response.success(GenericResponse("ok", null))
        )
        val otherComment = CommentViewData("c1", "t1", "someoneelse", "body", 0, false, Date())

        viewModel.likeComment(otherComment, "t1")

        verify(api).likeComment("token123", postIdentifier, "t1", "c1")
    }

    @Test
    fun `refresh reloads post details and comments`() = runTest {
        // loadAllData already ran once in init.
        viewModel.refresh()

        // getPostDetails is called again on refresh (once in init, once here).
        verify(api, org.mockito.kotlin.times(2)).getPostDetails("token123", postIdentifier)
        assertNotNull(viewModel.postDetail.value)
        assertFalse(viewModel.isRefreshing.value)
    }

    @Test
    fun `commentOnPost success clears newCommentText and reloads`() = runTest {
        viewModel.updateNewCommentText("Nice post!")
        whenever(api.commentOnPost(any(), any(), any())).thenReturn(Response.success(mock()))

        viewModel.commentOnPost("Nice post!")

        assertEquals("", viewModel.newCommentText.value)
        verify(api, org.mockito.kotlin.times(2)).getPostDetails("token123", postIdentifier)
    }

    @Test
    fun `lockComments updates postDetail optimistically and calls the api`() = runTest {
        whenever(api.lockComments("token123", postIdentifier)).thenReturn(
            Response.success(SetCommentsDisabledResponse(commentsDisabled = true))
        )

        viewModel.lockComments()

        assertEquals(true, viewModel.postDetail.value?.commentsDisabled)
        verify(api).lockComments("token123", postIdentifier)
    }

    @Test
    fun `lockComments reverts when the request fails`() = runTest {
        whenever(api.lockComments("token123", postIdentifier)).thenReturn(
            Response.error(500, "{\"error\":\"Server error\"}".toResponseBody())
        )

        viewModel.lockComments()

        assertFalse(viewModel.postDetail.value?.commentsDisabled == true)
    }

    @Test
    fun `unlockComments updates postDetail optimistically and calls the api`() = runTest {
        whenever(api.getPostDetails("token123", postIdentifier)).thenReturn(
            Response.success(Post(postIdentifier, "url", "caption", "user", 1, commentsDisabled = true))
        )
        val lockedViewModel = PostDetailViewModel(postIdentifier, api, keychainHelper)
        whenever(api.unlockComments("token123", postIdentifier)).thenReturn(
            Response.success(SetCommentsDisabledResponse(commentsDisabled = false))
        )

        lockedViewModel.unlockComments()

        assertEquals(false, lockedViewModel.postDetail.value?.commentsDisabled)
        verify(api).unlockComments("token123", postIdentifier)
    }

    @Test
    fun `retractReportPost calls api and reloads data`() = runTest {
        whenever(api.retractReportPost("token123", postIdentifier)).thenReturn(
            Response.success(GenericResponse("Post report retracted", null))
        )

        viewModel.retractReportPost()

        verify(api).retractReportPost("token123", postIdentifier)
        // The reload refreshes the server-backed isReported/reportReason state
        // (getPostDetails: once in init, once after the retraction).
        verify(api, org.mockito.kotlin.times(2)).getPostDetails("token123", postIdentifier)
    }

    @Test
    fun `retractReportComment calls api, clears the local flag, and reloads`() = runTest {
        whenever(api.retractReportComment(any(), any(), any(), any())).thenReturn(
            Response.success(GenericResponse("Comment report retracted", null))
        )
        whenever(api.reportComment(any(), any(), any(), any(), any())).thenReturn(
            Response.success(GenericResponse("Comment reported", null))
        )
        val otherComment = CommentViewData("c1", "t1", "someoneelse", "body", 0, false, Date())

        // Report first so the local reported flag is set...
        viewModel.reportComment(otherComment, "t1", "negative")
        assertEquals(setOf("c1"), viewModel.reportedCommentIds.value)

        // ...then retracting clears it again.
        viewModel.retractReportComment(otherComment, "t1")

        verify(api).retractReportComment("token123", postIdentifier, "t1", "c1")
        assertFalse(viewModel.reportedCommentIds.value.contains("c1"))
    }

    @Test
    fun `toggleCommentCollapsed adds then removes the comment id`() = runTest {
        // Starts uncollapsed.
        assertFalse(viewModel.collapsedCommentIds.value.contains("c1"))

        // First toggle collapses the thread below this comment...
        viewModel.toggleCommentCollapsed("c1")
        assertEquals(setOf("c1"), viewModel.collapsedCommentIds.value)

        // ...and a second toggle expands it again.
        viewModel.toggleCommentCollapsed("c1")
        assertFalse(viewModel.collapsedCommentIds.value.contains("c1"))
    }

    @Test
    fun `toggleCommentCollapsed tracks each comment independently`() = runTest {
        viewModel.toggleCommentCollapsed("c1")
        viewModel.toggleCommentCollapsed("c2")
        assertEquals(setOf("c1", "c2"), viewModel.collapsedCommentIds.value)

        // Expanding one leaves the other collapsed.
        viewModel.toggleCommentCollapsed("c1")
        assertEquals(setOf("c2"), viewModel.collapsedCommentIds.value)
    }

    // --- Collapse control only with replies (issue #537) ---

    @Test
    fun `commentIdsWithReplies is empty for a single comment`() {
        val only = CommentViewData("c1", "t1", "someone", "love this", 0, false, Date())

        assertEquals(emptySet<String>(), CommentThreadViewData("t1", listOf(only)).commentIdsWithReplies)
    }

    @Test
    fun `commentIdsWithReplies excludes the last reply`() {
        val root = CommentViewData("c1", "t1", "someone", "love this", 0, false, Date())
        val reply = CommentViewData("c2", "t1", "other", "totally agree", 0, false, Date())

        // Only the root has another comment below it; the last reply has nothing to fold.
        assertEquals(setOf("c1"), CommentThreadViewData("t1", listOf(root, reply)).commentIdsWithReplies)
    }

    @Test
    fun `loadAllData loads the next comment page before deciding which comments have replies`() = runTest {
        fun commentDto(index: Int, creationTime: String) =
            CommentDto("c$index", "comment $index", "someone", creationTime, creationTime, 0)
        val firstPage = (1..COMMENT_BATCH_SIZE).map { commentDto(it, "2024-01-%02dT00:00:00Z".format(it)) }
        val nextPage = listOf(commentDto(COMMENT_BATCH_SIZE + 1, "2024-02-01T00:00:00Z"))
        whenever(api.getCommentsForPost("token123", postIdentifier, 0)).thenReturn(
            Response.success(listOf(CommentThreadDto("t1")))
        )
        whenever(api.getCommentsForThread("token123", "t1", 0, null)).thenReturn(Response.success(firstPage))
        whenever(api.getCommentsForThread("token123", "t1", 1, null)).thenReturn(Response.success(nextPage))

        val pagedViewModel = PostDetailViewModel(postIdentifier, api, keychainHelper)

        verify(api).getCommentsForThread("token123", "t1", 0, null)
        verify(api).getCommentsForThread("token123", "t1", 1, null)
        val thread = pagedViewModel.commentThreads.value.single()
        assertEquals(COMMENT_BATCH_SIZE + 1, thread.comments.size)
        assertEquals("comment ${COMMENT_BATCH_SIZE + 1}", thread.comments.last().body)
        // The last comment of the first page has a reply on the second page.
        assertEquals(COMMENT_BATCH_SIZE, thread.commentIdsWithReplies.size)
        assertTrue(thread.commentIdsWithReplies.contains("c$COMMENT_BATCH_SIZE"))
    }

    private fun stubFullFirstCommentPage(): List<CommentDto> {
        val firstPage = (1..COMMENT_BATCH_SIZE).map {
            val time = "2024-01-%02dT00:00:00Z".format(it)
            CommentDto("c$it", "comment $it", "someone", time, time, 0)
        }
        runBlocking {
            whenever(api.getCommentsForPost("token123", postIdentifier, 0)).thenReturn(
                Response.success(listOf(CommentThreadDto("t1")))
            )
            whenever(api.getCommentsForThread("token123", "t1", 0, null)).thenReturn(Response.success(firstPage))
        }
        return firstPage
    }

    @Test
    fun `loadAllData skips a comment repeated on the next page`() = runTest {
        val firstPage = stubFullFirstCommentPage()
        // The ranking shifted between requests, so the last comment of the
        // first page comes back again ahead of the new one.
        val newComment = CommentDto("c31", "comment 31", "someone", "2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", 0)
        whenever(api.getCommentsForThread("token123", "t1", 1, null)).thenReturn(
            Response.success(listOf(firstPage.last(), newComment))
        )

        val pagedViewModel = PostDetailViewModel(postIdentifier, api, keychainHelper)

        val ids = pagedViewModel.commentThreads.value.single().comments.map { it.id }
        assertEquals((1..COMMENT_BATCH_SIZE + 1).map { "c$it" }, ids)
    }

    @Test
    fun `loadAllData keeps the loaded pages when a later comment page fails`() = runTest {
        stubFullFirstCommentPage()
        whenever(api.getCommentsForThread("token123", "t1", 1, null)).thenReturn(
            Response.error(429, "rate limited".toResponseBody())
        )

        val pagedViewModel = PostDetailViewModel(postIdentifier, api, keychainHelper)

        assertEquals(COMMENT_BATCH_SIZE, pagedViewModel.commentThreads.value.single().comments.size)
        // No further page is requested after the failure.
        verify(api, never()).getCommentsForThread("token123", "t1", 2, null)
    }

    @Test
    fun `loadAllData keeps the loaded pages when a later comment page throws`() = runTest {
        stubFullFirstCommentPage()
        whenever(api.getCommentsForThread("token123", "t1", 1, null)).thenAnswer {
            throw java.io.IOException("connection reset")
        }

        val pagedViewModel = PostDetailViewModel(postIdentifier, api, keychainHelper)

        assertEquals(COMMENT_BATCH_SIZE, pagedViewModel.commentThreads.value.single().comments.size)
        assertEquals(null, pagedViewModel.alertMessage.value)
    }
}
