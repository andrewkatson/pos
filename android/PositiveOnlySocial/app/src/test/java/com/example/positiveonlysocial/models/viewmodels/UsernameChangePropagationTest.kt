package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.util.SessionEvents
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import com.example.positiveonlysocial.data.model.Post
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever

/**
 * View models kept alive in other back-stack entries cache the signed-in
 * username for ownership checks; a rename from Settings must reach them
 * (review of issue #594).
 */
@OptIn(ExperimentalCoroutinesApi::class)
class UsernameChangePropagationTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun `retained view models follow a rename`() = runTest {
        val api = mock<PositiveOnlySocialAPI>()
        val keychainHelper = mock<KeychainHelperProtocol>()
        whenever(keychainHelper.load(any<Class<UserSession>>(), any(), any()))
            .thenReturn(UserSession("token123", "before_rename", "1", false, null, null))
        val home = HomeViewModel(api, keychainHelper)
        val feed = FeedViewModel(api, keychainHelper)
        assertEquals("before_rename", feed.postActions.currentUsername.value)

        val heldUntil = System.currentTimeMillis() + 60_000
        SessionEvents.usernameChanged("after_rename", heldUntil)
        advanceUntilIdle()

        assertEquals("after_rename", home.currentUsername.value)
        assertEquals("after_rename", feed.postActions.currentUsername.value)
        // Rows fetched before the rename still carry the old name, which stays
        // reserved for this account, so they are still its own.
        assertTrue(feed.postActions.isOwnPost(Post("p1", "url", "caption", "before_rename", 0)))
        assertTrue(feed.postActions.isOwnPost(Post("p2", "url", "caption", "after_rename", 0)))
        assertFalse(feed.postActions.isOwnPost(Post("p3", "url", "caption", "someone_else", 0)))
        // Once the old name's hold ends someone else may hold it.
        assertFalse(feed.postActions.isOwnPost(Post("p1", "url", "caption", "before_rename", 0), heldUntil + 1))
    }

    @Test
    fun `a rename without a live hold does not keep the old name`() = runTest {
        val api = mock<PositiveOnlySocialAPI>()
        val keychainHelper = mock<KeychainHelperProtocol>()
        whenever(keychainHelper.load(any<Class<UserSession>>(), any(), any()))
            .thenReturn(UserSession("token123", "old_name_here", "1", false, null, null))
        val feed = FeedViewModel(api, keychainHelper)

        SessionEvents.usernameChanged("new_name_here", null)
        advanceUntilIdle()

        assertFalse(feed.postActions.isOwnPost(Post("p1", "url", "caption", "old_name_here", 0)))
    }
}
