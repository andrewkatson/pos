package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.StatefulStubbedAPI
import com.example.positiveonlysocial.data.model.RegisterRequest
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever

/**
 * Exercises the owner-only profile-photo set/remove flow (issue #7) against the
 * in-memory stub. The stub approves immediately (no classifier) but still
 * reports "pending" from the set response, mirroring the backend's eager mode;
 * the reload afterwards reads back the approved photo.
 *
 * The upload step is stubbed out (a no-op uploader): the real ImageUploader
 * decodes a Bitmap, which needs the Android framework unavailable in a plain
 * JVM unit test.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class ProfileViewModelPhotoTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    /** Registers a user in the stub and returns a view model bound to their session. */
    private suspend fun buildViewModelFor(
        api: StatefulStubbedAPI,
        username: String
    ): ProfileViewModel {
        val auth = api.register(
            RegisterRequest(username, "$username@test.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        ).body()!!
        val session = UserSession(auth.sessionToken, username, auth.userId!!, false, null, null)
        val keychain: KeychainHelperProtocol = mock()
        whenever(keychain.load(any<Class<UserSession>>(), any(), any())).thenReturn(session)
        // No-op uploader: the bytes never reach S3 in a unit test.
        return ProfileViewModel(api, keychain, uploadBytes = { _, _ -> })
    }

    @Test
    fun `setProfilePhoto uploads then stores an approved photo`() = runTest {
        val api = StatefulStubbedAPI()
        val viewModel = buildViewModelFor(api, "alice")

        viewModel.setProfilePhoto("alice", byteArrayOf(1, 2, 3))
        advanceUntilIdle()

        // The reload after setting reads back the now-approved photo.
        assertNotNull(viewModel.profileDetails.value?.profileImageUrl)
        assertEquals("approved", viewModel.profileDetails.value?.profileImageStatus)
        assertFalse(viewModel.isPhotoBusy.value)
        assertNull(viewModel.errorMessage.value)
    }

    @Test
    fun `removeProfilePhoto clears a previously set photo`() = runTest {
        val api = StatefulStubbedAPI()
        val viewModel = buildViewModelFor(api, "bob")

        viewModel.setProfilePhoto("bob", byteArrayOf(1, 2, 3))
        advanceUntilIdle()
        assertNotNull(viewModel.profileDetails.value?.profileImageUrl)

        viewModel.removeProfilePhoto("bob")
        advanceUntilIdle()

        assertNull(viewModel.profileDetails.value?.profileImageUrl)
        assertEquals("none", viewModel.profileDetails.value?.profileImageStatus)
        assertFalse(viewModel.isPhotoBusy.value)
    }

    @Test
    fun `onProfilePhotoReadFailed surfaces a photo error`() = runTest {
        val api = StatefulStubbedAPI()
        val viewModel = buildViewModelFor(api, "dana")

        assertNull(viewModel.photoErrorMessage.value)
        viewModel.onProfilePhotoReadFailed()
        assertNotNull(viewModel.photoErrorMessage.value)
    }

    @Test
    fun `a second photo action is a no-op while one is in flight`() = runTest {
        val api = StatefulStubbedAPI()
        // An uploader that never returns keeps the first set busy so the guard
        // can be observed.
        val auth = api.register(
            RegisterRequest("carol", "carol@test.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        ).body()!!
        val session = UserSession(auth.sessionToken, "carol", auth.userId!!, false, null, null)
        val keychain: KeychainHelperProtocol = mock()
        whenever(keychain.load(any<Class<UserSession>>(), any(), any())).thenReturn(session)
        val gate = kotlinx.coroutines.CompletableDeferred<Unit>()
        val viewModel = ProfileViewModel(api, keychain, uploadBytes = { _, _ -> gate.await() })

        viewModel.setProfilePhoto("carol", byteArrayOf(1))
        // Busy now; a second call must short-circuit.
        viewModel.removeProfilePhoto("carol")

        gate.complete(Unit)
        advanceUntilIdle()

        // The remove was ignored, so the photo set by the first call stands.
        assertNotNull(viewModel.profileDetails.value?.profileImageUrl)
        assertFalse(viewModel.isPhotoBusy.value)
    }
}
