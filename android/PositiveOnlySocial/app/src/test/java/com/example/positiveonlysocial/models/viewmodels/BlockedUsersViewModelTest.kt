package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.GenericResponse
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
class BlockedUsersViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var viewModel: BlockedUsersViewModel
    private lateinit var mockApi: PositiveOnlySocialAPI
    private lateinit var keychainHelper: KeychainHelperProtocol

    private val session = UserSession("token123", "ada", "1", false, null, null)

    private val blockedUsers = listOf(
        User(username = "alice", identityIsVerified = true),
        User(username = "bob", identityIsVerified = false)
    )

    @Before
    fun setup() {
        mockApi = mock()
        keychainHelper = mock()
        whenever(keychainHelper.load(any<Class<UserSession>>(), any(), any())).thenReturn(session)
        viewModel = BlockedUsersViewModel(mockApi, keychainHelper)
    }

    @Test
    fun `load populates blocked users and clears loading`() = runTest {
        whenever(mockApi.getBlockedUsers("token123")).thenReturn(Response.success(blockedUsers))

        viewModel.load()

        assertEquals(blockedUsers, viewModel.blockedUsers.value)
        assertFalse(viewModel.isLoading.value)
        assertNull(viewModel.errorMessage.value)
    }

    @Test
    fun `load failure extracts the backend error message`() = runTest {
        val errorBody = "{\"error\":\"Something went wrong\"}"
            .toResponseBody("application/json".toMediaTypeOrNull())
        whenever(mockApi.getBlockedUsers("token123")).thenReturn(Response.error(500, errorBody))

        viewModel.load()

        assertEquals("Something went wrong", viewModel.errorMessage.value)
        assertEquals(emptyList<User>(), viewModel.blockedUsers.value)
    }

    @Test
    fun `unblock removes the user from the list`() = runTest {
        whenever(mockApi.getBlockedUsers("token123")).thenReturn(Response.success(blockedUsers))
        whenever(mockApi.toggleBlock("token123", "alice"))
            .thenReturn(Response.success(GenericResponse("User unblocked", null)))
        viewModel.load()

        viewModel.unblock("alice")

        assertEquals(listOf(User("bob", false)), viewModel.blockedUsers.value)
        assertNull(viewModel.errorMessage.value)
        assertEquals(emptySet<String>(), viewModel.unblockingUsernames.value)
    }

    @Test
    fun `unblock failure keeps the user listed and surfaces the error`() = runTest {
        whenever(mockApi.getBlockedUsers("token123")).thenReturn(Response.success(blockedUsers))
        val errorBody = "{\"error\":\"User does not exist\"}"
            .toResponseBody("application/json".toMediaTypeOrNull())
        whenever(mockApi.toggleBlock("token123", "alice")).thenReturn(Response.error(400, errorBody))
        viewModel.load()

        viewModel.unblock("alice")

        assertEquals(blockedUsers, viewModel.blockedUsers.value)
        // The user sees the message, not the raw {"error": ...} JSON.
        assertEquals("User does not exist", viewModel.errorMessage.value)
    }
}
