package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.HiddenComment
import com.example.positiveonlysocial.data.model.HiddenPost
import com.example.positiveonlysocial.data.model.MyAppeal
import com.example.positiveonlysocial.data.model.SubmitAppealResponse
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever
import retrofit2.Response

@OptIn(ExperimentalCoroutinesApi::class)
class AppealsViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var viewModel: AppealsViewModel
    private lateinit var api: PositiveOnlySocialAPI
    private lateinit var keychainHelper: KeychainHelperProtocol

    private val session = UserSession("token123", "ada", "1", false, null, null)

    @Before
    fun setup() {
        api = mock()
        keychainHelper = mock()
        whenever(keychainHelper.load(any<Class<UserSession>>(), any(), any())).thenReturn(session)
        viewModel = AppealsViewModel(api, keychainHelper)
    }

    @Test
    fun `load populates hidden content and clears loading`() = runTest {
        val posts = listOf(HiddenPost("p1", "url", "a caption", "classifier", false))
        whenever(api.getHiddenPosts("token123", 0)).thenReturn(Response.success(posts))
        whenever(api.getHiddenComments("token123", 0)).thenReturn(Response.success(emptyList<HiddenComment>()))
        whenever(api.getMyAppeals("token123", 0)).thenReturn(Response.success(emptyList<MyAppeal>()))

        viewModel.load()

        assertEquals(posts, viewModel.hiddenPosts.value)
        assertFalse(viewModel.isLoading.value)
    }

    @Test
    fun `submitAppeal success reloads and reports true`() = runTest {
        whenever(api.getHiddenPosts(any(), any())).thenReturn(Response.success(emptyList<HiddenPost>()))
        whenever(api.getHiddenComments(any(), any())).thenReturn(Response.success(emptyList<HiddenComment>()))
        whenever(api.getMyAppeals(any(), any())).thenReturn(Response.success(emptyList<MyAppeal>()))
        whenever(api.submitAppeal(any(), any())).thenReturn(Response.success(SubmitAppealResponse("a1")))

        var result: Boolean? = null
        viewModel.submitAppeal("post", "p1", "please reconsider") { result = it }

        assertEquals(true, result)
    }

    @Test
    fun `submitAppeal failure sets error and reports false`() = runTest {
        val errorBody = "{\"error\":\"This item has already been appealed\"}"
            .toResponseBody("application/json".toMediaTypeOrNull())
        whenever(api.submitAppeal(any(), any())).thenReturn(Response.error(400, errorBody))

        var result: Boolean? = null
        viewModel.submitAppeal("post", "p1", "again") { result = it }

        assertEquals(false, result)
        assertNotNull(viewModel.errorMessage.value)
    }
}
