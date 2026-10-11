package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.api.StatefulStubbedAPI
import com.example.positiveonlysocial.data.auth.AuthenticationManager
import com.example.positiveonlysocial.data.model.CreatePostRequest
import com.example.positiveonlysocial.data.model.CurrentUserResponse
import com.example.positiveonlysocial.data.model.GenericResponse
import com.example.positiveonlysocial.data.model.ProfileDetailsResponse
import com.example.positiveonlysocial.data.model.RegisterRequest
import com.example.positiveonlysocial.data.model.SetAccountPrivacyRequest
import com.example.positiveonlysocial.data.model.SetAccountPrivacyResponse
import com.example.positiveonlysocial.data.model.User
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.mock
import org.mockito.kotlin.doSuspendableAnswer
import org.mockito.kotlin.never
import org.mockito.kotlin.stub
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import retrofit2.Response

/**
 * Private accounts & follow requests (issue #96): the profile's Follow /
 * Requested / Following states, the follow requests list, and the Settings
 * switch.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class PrivateAccountViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private fun keychainFor(token: String, username: String): KeychainHelperProtocol {
        val keychain: KeychainHelperProtocol = mock()
        whenever(keychain.load(any<Class<UserSession>>(), any(), any()))
            .thenReturn(UserSession(token, username, "1", false, null, null))
        return keychain
    }

    private suspend fun register(api: StatefulStubbedAPI, username: String): String =
        api.register(
            RegisterRequest(username, "$username@test.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        ).body()!!.sessionToken

    /** A private author with one post plus a viewer; returns (authorToken, viewerToken). */
    private suspend fun privateAuthorAndViewer(api: StatefulStubbedAPI): Pair<String, String> {
        val authorToken = register(api, "author")
        api.setAccountPrivacy(authorToken, SetAccountPrivacyRequest(true))
        api.makePost(authorToken, CreatePostRequest(imageUrl = "a.jpg", caption = "hello"))
        return authorToken to register(api, "viewer")
    }

    // --- ProfileViewModel ---

    @Test
    fun `isLocked covers only someone else's private profile you do not follow`() {
        val private = ProfileDetailsResponse("a", 0, 0, 0, isFollowing = false, isPrivate = true)
        assertTrue(ProfileViewModel.isLocked(private, isOwnProfile = false, isFollowing = false))
        assertFalse(ProfileViewModel.isLocked(private, isOwnProfile = true, isFollowing = false))
        assertFalse(ProfileViewModel.isLocked(private, isOwnProfile = false, isFollowing = true))
        assertFalse(ProfileViewModel.isLocked(private.copy(isPrivate = null), false, false))
    }

    @Test
    fun `following a private profile shows Requested and stays locked`() = runTest {
        val api = StatefulStubbedAPI()
        val (_, viewerToken) = privateAuthorAndViewer(api)
        val viewModel = ProfileViewModel(api, keychainFor(viewerToken, "viewer"))
        viewModel.fetchProfile("author")
        assertTrue(viewModel.userPosts.value.isEmpty())

        viewModel.toggleFollow("author")

        val profile = viewModel.profileDetails.value!!
        assertEquals(true, profile.followRequestPending)
        assertFalse(viewModel.isFollowing.value)
        assertEquals(0, profile.followerCount)
        assertTrue(ProfileViewModel.isLocked(profile, isOwnProfile = false, isFollowing = viewModel.isFollowing.value))
    }

    @Test
    fun `tapping Requested cancels the request`() = runTest {
        val api = StatefulStubbedAPI()
        val (authorToken, viewerToken) = privateAuthorAndViewer(api)
        api.followUser(viewerToken, "author")
        val viewModel = ProfileViewModel(api, keychainFor(viewerToken, "viewer"))
        viewModel.fetchProfile("author")
        assertEquals(true, viewModel.profileDetails.value!!.followRequestPending)

        viewModel.toggleFollow("author")

        assertEquals(false, viewModel.profileDetails.value!!.followRequestPending)
        assertTrue(api.getFollowRequests(authorToken).body()!!.isEmpty())
    }

    @Test
    fun `an approved follower sees the private profile's posts`() = runTest {
        val api = StatefulStubbedAPI()
        val (authorToken, viewerToken) = privateAuthorAndViewer(api)
        api.followUser(viewerToken, "author")
        api.approveFollowRequest(authorToken, "viewer")
        val viewModel = ProfileViewModel(api, keychainFor(viewerToken, "viewer"))

        viewModel.fetchProfile("author")

        assertTrue(viewModel.isFollowing.value)
        assertEquals(1, viewModel.userPosts.value.size)
        assertFalse(ProfileViewModel.isLocked(viewModel.profileDetails.value, false, viewModel.isFollowing.value))
    }

    @Test
    fun `a follow after the owner went private reloads the profile`() = runTest {
        // Loaded while public, then the owner goes private: the follow files a
        // request, so the cached public grid must be replaced, not just the button.
        val api = StatefulStubbedAPI()
        val authorToken = register(api, "author")
        api.makePost(authorToken, CreatePostRequest(imageUrl = "a.jpg", caption = "hello"))
        val viewerToken = register(api, "viewer")
        val viewModel = ProfileViewModel(api, keychainFor(viewerToken, "viewer"))
        viewModel.fetchProfile("author")
        assertEquals(1, viewModel.userPosts.value.size)

        api.setAccountPrivacy(authorToken, SetAccountPrivacyRequest(true))
        viewModel.toggleFollow("author")

        val profile = viewModel.profileDetails.value!!
        assertEquals(true, profile.isPrivate)
        assertEquals(true, profile.followRequestPending)
        assertFalse(viewModel.isFollowing.value)
        assertTrue(viewModel.userPosts.value.isEmpty())
    }

    @Test
    fun `answering a request refreshes the owner's profile`() = runTest {
        val api = StatefulStubbedAPI()
        val (authorToken, viewerToken) = privateAuthorAndViewer(api)
        api.followUser(viewerToken, "author")
        val keychain = keychainFor(authorToken, "author")
        val profile = ProfileViewModel(api, keychain)
        profile.fetchProfile("author")
        assertEquals(1, profile.profileDetails.value!!.followRequestCount)

        FollowRequestsViewModel(api, keychain).approve("viewer")

        assertEquals(0, profile.profileDetails.value!!.followRequestCount)
        assertEquals(1, profile.profileDetails.value!!.followerCount)
    }

    @Test
    fun `a second tap while a follow is in flight is ignored`() = runTest {
        // Without the guard the second tap would read "Requested" and send a
        // cancel before the follow it cancels had reached the server.
        val api: PositiveOnlySocialAPI = mock()
        val private = ProfileDetailsResponse("author", 0, 0, 0, isFollowing = false, isPrivate = true)
        whenever(api.getProfileDetails("token123", "author")).thenReturn(Response.success(private))
        whenever(api.getPostsForUser("token123", "author", 0)).thenReturn(Response.success(emptyList()))
        val followReply = CompletableDeferred<Response<GenericResponse>>()
        api.stub { onBlocking { followUser("token123", "author") } doSuspendableAnswer { followReply.await() } }
        val viewModel = ProfileViewModel(api, keychainFor("token123", "viewer"))
        viewModel.fetchProfile("author")

        viewModel.toggleFollow("author") // suspends awaiting followReply
        assertTrue(viewModel.isFollowBusy.value)
        viewModel.toggleFollow("author") // the quick second tap
        followReply.complete(Response.success(GenericResponse("Follow requested", null, null, followRequestPending = true)))

        assertFalse(viewModel.isFollowBusy.value)
        verify(api, never()).cancelFollowRequest(any(), any())
        assertEquals(true, viewModel.profileDetails.value!!.followRequestPending)
    }

    @Test
    fun `a cancel after the owner approved reloads as a follower`() = runTest {
        val api = StatefulStubbedAPI()
        val (authorToken, viewerToken) = privateAuthorAndViewer(api)
        api.followUser(viewerToken, "author")
        val viewModel = ProfileViewModel(api, keychainFor(viewerToken, "viewer"))
        viewModel.fetchProfile("author")
        assertEquals(true, viewModel.profileDetails.value!!.followRequestPending)

        // Approved while the profile is open; tapping Requested finds nothing to cancel.
        api.approveFollowRequest(authorToken, "viewer")
        viewModel.toggleFollow("author")

        assertTrue(viewModel.isFollowing.value)
        assertEquals(false, viewModel.profileDetails.value!!.followRequestPending)
        assertEquals(1, viewModel.userPosts.value.size)
    }

    @Test
    fun `a privacy change refreshes the owner's profile`() = runTest {
        val api = StatefulStubbedAPI()
        val token = register(api, "owner")
        val keychain = keychainFor(token, "owner")
        val profile = ProfileViewModel(api, keychain)
        profile.fetchProfile("owner")
        assertEquals(false, profile.profileDetails.value!!.isPrivate)
        val settings = SettingsViewModel(api, mock<AuthenticationManager>(), keychain)
        settings.loadCurrentUser()

        settings.setAccountPrivacy(true)

        assertEquals(true, profile.profileDetails.value!!.isPrivate)
    }

    @Test
    fun `a follow that reveals the account went private fails closed if the reload fails`() = runTest {
        val api: PositiveOnlySocialAPI = mock()
        val public = ProfileDetailsResponse("author", 3, 10, 5, isFollowing = false, isPrivate = false)
        val offline = "{\"error\":\"offline\"}".toResponseBody("application/json".toMediaTypeOrNull())
        whenever(api.getProfileDetails("token123", "author"))
            .thenReturn(Response.success(public), Response.error(500, offline))
        val post = com.example.positiveonlysocial.data.model.Post(
            postIdentifier = "p1", imageUrl = "a.jpg", authorUsername = "author", caption = "hi")
        whenever(api.getPostsForUser("token123", "author", 0))
            .thenReturn(Response.success(listOf(post)), Response.error(500, offline))
        whenever(api.followUser("token123", "author"))
            .thenReturn(Response.success(GenericResponse("Follow requested", null, null, followRequestPending = true)))
        val viewModel = ProfileViewModel(api, keychainFor("token123", "viewer"))
        viewModel.fetchProfile("author")
        assertEquals(1, viewModel.userPosts.value.size)

        viewModel.toggleFollow("author")

        val profile = viewModel.profileDetails.value!!
        assertEquals(true, profile.isPrivate)
        assertEquals(true, profile.followRequestPending)
        assertEquals(0, profile.postCount)
        assertEquals(0, profile.followerCount)
        assertTrue(viewModel.userPosts.value.isEmpty())
        assertFalse(viewModel.isFollowing.value)
    }

    // --- FollowRequestsViewModel ---

    private val requesters = listOf(User("alice", true), User("bob", false))

    @Test
    fun `follow requests load, approve and deny`() = runTest {
        val api: PositiveOnlySocialAPI = mock()
        whenever(api.getFollowRequests("token123")).thenReturn(Response.success(requesters))
        whenever(api.approveFollowRequest("token123", "alice"))
            .thenReturn(Response.success(GenericResponse("Follow request approved", null)))
        whenever(api.denyFollowRequest("token123", "bob"))
            .thenReturn(Response.success(GenericResponse("Follow request denied", null)))
        val viewModel = FollowRequestsViewModel(api, keychainFor("token123", "owner"))

        viewModel.load()
        assertEquals(requesters, viewModel.requests.value)
        assertTrue(viewModel.hasLoaded.value)

        viewModel.approve("alice")
        viewModel.deny("bob")

        assertTrue(viewModel.requests.value.isEmpty())
        assertNull(viewModel.errorMessage.value)
        assertEquals(emptySet<String>(), viewModel.decidingUsernames.value)
    }

    @Test
    fun `a failed load is not reported as loaded`() = runTest {
        val api: PositiveOnlySocialAPI = mock()
        val errorBody = "{\"error\":\"boom\"}".toResponseBody("application/json".toMediaTypeOrNull())
        whenever(api.getFollowRequests("token123")).thenReturn(Response.error(500, errorBody))
        val viewModel = FollowRequestsViewModel(api, keychainFor("token123", "owner"))

        viewModel.load()

        assertFalse(viewModel.hasLoaded.value)
        assertEquals("boom", viewModel.errorMessage.value)
    }

    @Test
    fun `a failed decision keeps the row and surfaces the error`() = runTest {
        val api: PositiveOnlySocialAPI = mock()
        whenever(api.getFollowRequests("token123")).thenReturn(Response.success(requesters))
        val errorBody = "{\"error\":\"No follow request from user\"}"
            .toResponseBody("application/json".toMediaTypeOrNull())
        whenever(api.approveFollowRequest("token123", "alice")).thenReturn(Response.error(400, errorBody))
        val viewModel = FollowRequestsViewModel(api, keychainFor("token123", "owner"))
        viewModel.load()

        viewModel.approve("alice")

        assertEquals(requesters, viewModel.requests.value)
        assertEquals("No follow request from user", viewModel.errorMessage.value)
    }

    // --- SettingsViewModel ---

    @Test
    fun `the private account switch saves and reverts on failure`() = runTest {
        val api: PositiveOnlySocialAPI = mock()
        whenever(api.getCurrentUser("token123"))
            .thenReturn(Response.success(CurrentUserResponse("owner", "owner@test.com", isPrivate = false)))
        whenever(api.setAccountPrivacy("token123", SetAccountPrivacyRequest(true)))
            .thenReturn(Response.success(SetAccountPrivacyResponse(true)))
        val viewModel = SettingsViewModel(api, mock<AuthenticationManager>(), keychainFor("token123", "owner"))
        viewModel.loadCurrentUser()

        viewModel.setAccountPrivacy(true)
        assertEquals(true, viewModel.currentUser.value!!.isPrivate)
        assertFalse(viewModel.isSavingPrivacy.value)

        val errorBody = "{\"error\":\"boom\"}".toResponseBody("application/json".toMediaTypeOrNull())
        whenever(api.setAccountPrivacy("token123", SetAccountPrivacyRequest(false)))
            .thenReturn(Response.error(500, errorBody))
        viewModel.setAccountPrivacy(false)

        assertEquals(true, viewModel.currentUser.value!!.isPrivate)
        assertTrue(viewModel.showingErrorAlert.value)
    }

    @Test
    fun `the private account switch is ignored before the setting loads`() = runTest {
        val api: PositiveOnlySocialAPI = mock()
        val viewModel = SettingsViewModel(api, mock<AuthenticationManager>(), keychainFor("token123", "owner"))

        viewModel.setAccountPrivacy(true)

        assertNull(viewModel.currentUser.value)
        assertFalse(viewModel.isSavingPrivacy.value)
    }
}
