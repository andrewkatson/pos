package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.CommentViewData
import com.example.positiveonlysocial.data.model.CommentThreadViewData
import com.example.positiveonlysocial.data.model.GenericResponse
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.mock
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

    private val mockUserSession = UserSession("token123", "testuser", false, null, null)
    private val postIdentifier = "post123"

    @Before
    fun setup() {
        api = mock()
        keychainHelper = mock()
        
        whenever(keychainHelper.load(any<Class<UserSession>>(), any(), any())).thenReturn(mockUserSession)

        runBlocking {
            // Mock API calls for loadAllData which is called in init
            whenever(api.getPostDetails(postIdentifier)).thenReturn(
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
            whenever(api.getCommentsForPost(postIdentifier, 0)).thenReturn(
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
        verify(api, org.mockito.kotlin.times(2)).getPostDetails(postIdentifier)
    }

    @Test
    fun `commentOnPost success clears newCommentText and reloads`() = runTest {
        viewModel.updateNewCommentText("Nice post!")
        whenever(api.commentOnPost(any(), any(), any())).thenReturn(Response.success(mock()))

        viewModel.commentOnPost("Nice post!")

        assertEquals("", viewModel.newCommentText.value)
        verify(api, org.mockito.kotlin.times(2)).getPostDetails(postIdentifier)
    }
}
