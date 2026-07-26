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
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever
import retrofit2.Response

@OptIn(ExperimentalCoroutinesApi::class)
class FollowListViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var mockApi: PositiveOnlySocialAPI
    private lateinit var keychainHelper: KeychainHelperProtocol

    private val session = UserSession("token123", "ada", "1", false, null, null)

    private val people = listOf(
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
    fun `followers mode loads from getFollowers`() = runTest {
        whenever(mockApi.getFollowers("token123")).thenReturn(Response.success(people))
        val viewModel = FollowListViewModel(FollowListMode.FOLLOWERS, mockApi, keychainHelper)

        viewModel.load()

        assertEquals(people, viewModel.users.value)
        assertFalse(viewModel.isLoading.value)
        assertNull(viewModel.errorMessage.value)
    }

    @Test
    fun `following mode loads from getFollowing`() = runTest {
        whenever(mockApi.getFollowing("token123")).thenReturn(Response.success(people))
        val viewModel = FollowListViewModel(FollowListMode.FOLLOWING, mockApi, keychainHelper)

        viewModel.load()

        assertEquals(people, viewModel.users.value)
    }

    @Test
    fun `load failure extracts the backend error message`() = runTest {
        val errorBody = "{\"error\":\"Something went wrong\"}"
            .toResponseBody("application/json".toMediaTypeOrNull())
        whenever(mockApi.getFollowers("token123")).thenReturn(Response.error(500, errorBody))
        val viewModel = FollowListViewModel(FollowListMode.FOLLOWERS, mockApi, keychainHelper)

        viewModel.load()

        assertEquals("Something went wrong", viewModel.errorMessage.value)
        assertEquals(emptyList<User>(), viewModel.users.value)
    }

    @Test
    fun `mode fromRoute parses the navigation argument`() {
        assertEquals(FollowListMode.FOLLOWERS, FollowListMode.fromRoute("followers"))
        assertEquals(FollowListMode.FOLLOWING, FollowListMode.fromRoute("following"))
        // An unknown/missing argument falls back to followers.
        assertEquals(FollowListMode.FOLLOWERS, FollowListMode.fromRoute(null))
    }
}
