package com.example.positiveonlysocial.data.auth

import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.security.GeneralSecurityException

/**
 * Covers what happens when secure storage refuses the write (issue #503).
 *
 * The manager used to log the failure and return normally, which let the caller
 * walk into the signed-in UI with a session that existed nowhere. Since every
 * screen loads the session back out of the keychain, that shell rendered blank
 * everywhere — so a failed write has to be loud.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class AuthenticationManagerTest {

    private val session = UserSession("token123", "testuser", "1", false, null, null)

    /** Records what was written, and can be told to fail the next write. */
    private class FakeKeychainHelper(
        private val saveFailure: Exception? = null
    ) : KeychainHelperProtocol {
        val storage = mutableMapOf<String, Any?>()

        override fun <T> save(value: T, service: String, account: String) {
            saveFailure?.let { throw it }
            storage["$service:$account"] = value
        }

        @Suppress("UNCHECKED_CAST")
        override fun <T> load(type: Class<T>, service: String, account: String): T? =
            storage["$service:$account"] as? T

        override fun delete(service: String, account: String) {
            storage.remove("$service:$account")
        }
    }

    @Test
    fun `login persists the session and reports being logged in`() = runTest {
        val keychain = FakeKeychainHelper()
        val manager = AuthenticationManager(keychain)

        manager.login(session)

        assertEquals(session, manager.session.value)
        assertTrue(manager.isLoggedIn.value)
        assertEquals(
            session,
            keychain.load(
                UserSession::class.java,
                "positive-only-social.Positive-Only-Social",
                "userSessionToken"
            )
        )
    }

    @Test
    fun `login throws when the session cannot be persisted`() = runTest {
        val cause = GeneralSecurityException("keystore is unreadable")
        val manager = AuthenticationManager(FakeKeychainHelper(saveFailure = cause))

        try {
            manager.login(session)
            fail("login should surface a failed session write")
        } catch (e: SessionPersistenceException) {
            assertSame(cause, e.cause)
        }
    }

    @Test
    fun `a session that could not be persisted leaves the manager logged out`() = runTest {
        val manager = AuthenticationManager(
            FakeKeychainHelper(saveFailure = GeneralSecurityException("keystore is unreadable"))
        )

        runCatching { manager.login(session) }

        // The critical assertion: no half-logged-in state. A session held only in
        // memory would let the UI think it is signed in while every keychain read
        // behind it comes back empty.
        assertFalse(manager.isLoggedIn.value)
        assertNull(manager.session.value)
    }

    @Test
    fun `logout clears the stored session`() = runTest {
        val keychain = FakeKeychainHelper()
        val manager = AuthenticationManager(keychain)
        manager.login(session)

        manager.logout()

        assertFalse(manager.isLoggedIn.value)
        assertNull(manager.session.value)
        assertNull(
            keychain.load(
                UserSession::class.java,
                "positive-only-social.Positive-Only-Social",
                "userSessionToken"
            )
        )
    }
}
