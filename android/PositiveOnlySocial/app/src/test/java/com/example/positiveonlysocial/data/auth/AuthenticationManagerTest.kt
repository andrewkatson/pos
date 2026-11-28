package com.example.positiveonlysocial.data.auth

import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.api.StatefulStubbedAPI
import com.example.positiveonlysocial.data.constants.Constants
import com.example.positiveonlysocial.data.model.AcceptPoliciesRequest
import com.example.positiveonlysocial.data.model.AcceptPoliciesResponse
import com.example.positiveonlysocial.data.model.RegisterRequest
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.doSuspendableAnswer
import org.mockito.kotlin.mock
import org.mockito.kotlin.never
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import retrofit2.Response
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
    fun `cancellation stays cancellation instead of becoming a login failure`() = runTest {
        // A cancelled login hasn't failed to persist anything — rewriting it as a
        // SessionPersistenceException would put "we couldn't save your login" in
        // front of the user for something that never happened, and would swallow
        // the cancellation on the way.
        val manager = AuthenticationManager(
            FakeKeychainHelper(saveFailure = CancellationException("scope went away"))
        )

        try {
            manager.login(session)
            fail("cancellation should propagate")
        } catch (e: SessionPersistenceException) {
            fail("cancellation was rewritten as a persistence failure")
        } catch (e: CancellationException) {
            assertEquals("scope went away", e.message)
        }
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

    // --- Privacy policy re-accept (issue #620) ---

    /** A check is pending: the backend hasn't answered yet, so no dialog. */
    private fun assertChecking(manager: AuthenticationManager) {
        assertTrue(manager.isCheckingPrivacyPolicyAcceptance.value)
        assertFalse(manager.needsPrivacyPolicyAcceptance.value)
    }

    /** Nothing to ask and nothing pending. */
    private fun assertSettledAccepted(manager: AuthenticationManager) {
        assertFalse(manager.isCheckingPrivacyPolicyAcceptance.value)
        assertFalse(manager.needsPrivacyPolicyAcceptance.value)
    }

    /** A stub backend with one signed-up account; returns it and its session token. */
    private suspend fun stubWithAccount(username: String): Pair<StatefulStubbedAPI, String> {
        val api = StatefulStubbedAPI()
        val token = api.register(
            RegisterRequest(username, "$username@test.com", "Password1", "false", "127.0.0.1", "1970-01-01")
        ).body()!!.sessionToken
        return api to token
    }

    @Test
    fun `a restored session checks the privacy policy again`() {
        val keychain = FakeKeychainHelper()
        keychain.save(session, "positive-only-social.Positive-Only-Social", "userSessionToken")

        val manager = AuthenticationManager(keychain, shouldAutoLogin = true)

        assertTrue(manager.isLoggedIn.value)
        assertChecking(manager)
    }

    @Test
    fun `nobody signed in means nobody to ask`() {
        val manager = AuthenticationManager(FakeKeychainHelper(), shouldAutoLogin = true)

        assertFalse(manager.isLoggedIn.value)
        assertSettledAccepted(manager)
    }

    @Test
    fun `a fresh login checks the privacy policy`() = runTest {
        val manager = AuthenticationManager(FakeKeychainHelper())

        manager.login(session)

        assertChecking(manager)
    }

    @Test
    fun `the check asks a member with nothing on record`() = runTest {
        val (api, token) = stubWithAccount("nothingOnRecord")
        val manager = AuthenticationManager(FakeKeychainHelper())
        manager.login(session.copy(sessionToken = token))

        manager.checkPrivacyPolicyAcceptance(api)

        assertFalse(manager.isCheckingPrivacyPolicyAcceptance.value)
        assertTrue(manager.needsPrivacyPolicyAcceptance.value)
    }

    @Test
    fun `the check does not ask a member who accepted this version`() = runTest {
        val (api, token) = stubWithAccount("currentOnRecord")
        api.acceptPolicies(token, AcceptPoliciesRequest(Constants.POLICY_VERSION))
        val manager = AuthenticationManager(FakeKeychainHelper())
        manager.login(session.copy(sessionToken = token))

        manager.checkPrivacyPolicyAcceptance(api)

        assertSettledAccepted(manager)
    }

    @Test
    fun `the check does not ask a member who accepted a newer version`() = runTest {
        val (api, token) = stubWithAccount("newerOnRecord")
        api.acceptPolicies(token, AcceptPoliciesRequest("9999-12-31"))
        val manager = AuthenticationManager(FakeKeychainHelper())
        manager.login(session.copy(sessionToken = token))

        manager.checkPrivacyPolicyAcceptance(api)

        assertSettledAccepted(manager)
    }

    @Test
    fun `the check asks a member who accepted an older version`() = runTest {
        val (api, token) = stubWithAccount("olderOnRecord")
        api.acceptPolicies(token, AcceptPoliciesRequest("2000-01-01"))
        val manager = AuthenticationManager(FakeKeychainHelper())
        manager.login(session.copy(sessionToken = token))

        manager.checkPrivacyPolicyAcceptance(api)

        assertTrue(manager.needsPrivacyPolicyAcceptance.value)
    }

    @Test
    fun `the check asks when the backend request fails`() = runTest {
        val manager = AuthenticationManager(FakeKeychainHelper())
        manager.login(session.copy(sessionToken = "not-a-real-token"))

        manager.checkPrivacyPolicyAcceptance(StatefulStubbedAPI())

        assertFalse(manager.isCheckingPrivacyPolicyAcceptance.value)
        assertTrue(manager.needsPrivacyPolicyAcceptance.value)
    }

    @Test
    fun `the check asks when the backend throws`() = runTest {
        val api = mock<PositiveOnlySocialAPI>()
        whenever(api.getCurrentUser(any())).thenThrow(RuntimeException("offline"))
        val manager = AuthenticationManager(FakeKeychainHelper())
        manager.login(session)

        manager.checkPrivacyPolicyAcceptance(api)

        assertTrue(manager.needsPrivacyPolicyAcceptance.value)
    }

    @Test
    fun `a check overtaken by a logout does not raise the dialog`() = runTest {
        val (api, token) = stubWithAccount("overtakenCheck")
        val manager = AuthenticationManager(FakeKeychainHelper())
        manager.login(session.copy(sessionToken = token))
        val slowApi = mock<PositiveOnlySocialAPI> {
            onBlocking { getCurrentUser(any()) } doSuspendableAnswer {
                // The user logs out while the request is in flight.
                manager.logout()
                api.getCurrentUser(token)
            }
        }

        manager.checkPrivacyPolicyAcceptance(slowApi)

        assertSettledAccepted(manager)
    }

    @Test
    fun `the check does nothing when nothing is pending`() = runTest {
        val api = mock<PositiveOnlySocialAPI>()
        val manager = AuthenticationManager(FakeKeychainHelper())
        manager.login(session)
        manager.acceptPrivacyPolicy()

        manager.checkPrivacyPolicyAcceptance(api)

        verify(api, never()).getCurrentUser(any())
        assertSettledAccepted(manager)
    }

    @Test
    fun `accepting clears the prompt and keeps the user signed in`() = runTest {
        val manager = AuthenticationManager(FakeKeychainHelper())
        manager.login(session)
        manager.checkPrivacyPolicyAcceptance(StatefulStubbedAPI())
        assertTrue(manager.needsPrivacyPolicyAcceptance.value)

        manager.acceptPrivacyPolicy()

        assertSettledAccepted(manager)
        assertTrue(manager.isLoggedIn.value)
    }

    @Test
    fun `recording acceptance sends the bundled version and the next check skips the dialog`() = runTest {
        val (api, token) = stubWithAccount("recordsAcceptance")
        val manager = AuthenticationManager(FakeKeychainHelper())
        manager.login(session.copy(sessionToken = token))
        manager.checkPrivacyPolicyAcceptance(api)
        assertTrue(manager.needsPrivacyPolicyAcceptance.value)

        manager.acceptPrivacyPolicy()
        assertTrue(manager.recordPrivacyPolicyAcceptance(api, token))

        assertEquals(Constants.POLICY_VERSION, api.getCurrentUser(token).body()!!.policiesAcceptedVersion)
        // The next opening finds it on record.
        manager.onAppOpened()
        assertChecking(manager)
        manager.checkPrivacyPolicyAcceptance(api)
        assertSettledAccepted(manager)
    }

    @Test
    fun `recording acceptance calls policies accept with the bundled version`() = runTest {
        val api = mock<PositiveOnlySocialAPI>()
        whenever(api.acceptPolicies(any(), any())).thenReturn(
            Response.success(AcceptPoliciesResponse(Constants.POLICY_VERSION))
        )
        val manager = AuthenticationManager(FakeKeychainHelper())

        assertTrue(manager.recordPrivacyPolicyAcceptance(api, "token123"))

        verify(api).acceptPolicies("token123", AcceptPoliciesRequest(Constants.POLICY_VERSION))
    }

    @Test
    fun `recording acceptance is best-effort when the backend fails`() = runTest {
        val api = mock<PositiveOnlySocialAPI>()
        whenever(api.acceptPolicies(any(), any())).thenThrow(RuntimeException("offline"))
        val manager = AuthenticationManager(FakeKeychainHelper())
        manager.login(session)
        manager.acceptPrivacyPolicy()

        assertFalse(manager.recordPrivacyPolicyAcceptance(api, "token123"))

        assertSettledAccepted(manager)
        assertTrue(manager.isLoggedIn.value)
    }

    @Test
    fun `policy versions compare as dates`() {
        assertFalse(AuthenticationManager.isPolicyVersionCurrent(null, "2026-11-22"))
        assertFalse(AuthenticationManager.isPolicyVersionCurrent("2026-11-21", "2026-11-22"))
        assertTrue(AuthenticationManager.isPolicyVersionCurrent("2026-11-22", "2026-11-22"))
        assertTrue(AuthenticationManager.isPolicyVersionCurrent("2027-01-01", "2026-11-22"))
    }

    @Test
    fun `updating a live session in place keeps the answer already given`() = runTest {
        // Identity verification rewrites the session of someone already using
        // the app; they shouldn't be asked, or checked, again.
        val manager = AuthenticationManager(FakeKeychainHelper())
        manager.login(session)
        manager.acceptPrivacyPolicy()

        manager.login(session.copy(isIdentityVerified = true), keepPrivacyPolicyAcceptance = true)

        assertSettledAccepted(manager)
    }

    @Test
    fun `logging in again while still marked logged in checks again`() = runTest {
        // The manager is a process-wide singleton, so reopening the app in a
        // process that outlived its Activity finds it still "logged in"; the
        // remember-me auto-login that follows must still check.
        val manager = AuthenticationManager(FakeKeychainHelper())
        manager.login(session)
        manager.acceptPrivacyPolicy()

        manager.login(session.copy(sessionToken = "rotated"))

        assertChecking(manager)
    }

    @Test
    fun `keeping acceptance has no effect when nobody was signed in`() = runTest {
        val manager = AuthenticationManager(FakeKeychainHelper())

        manager.login(session, keepPrivacyPolicyAcceptance = true)

        assertChecking(manager)
    }

    @Test
    fun `a failed login does not raise the prompt`() = runTest {
        val manager = AuthenticationManager(
            FakeKeychainHelper(saveFailure = GeneralSecurityException("keystore unavailable"))
        )

        try {
            manager.login(session)
            fail("expected SessionPersistenceException")
        } catch (_: SessionPersistenceException) {
        }

        assertSettledAccepted(manager)
    }

    @Test
    fun `logging out clears the prompt and the next login checks again`() = runTest {
        val manager = AuthenticationManager(FakeKeychainHelper())
        manager.login(session)
        manager.checkPrivacyPolicyAcceptance(StatefulStubbedAPI())
        assertTrue(manager.needsPrivacyPolicyAcceptance.value)

        manager.logout()
        assertSettledAccepted(manager)

        manager.login(session)
        assertChecking(manager)
    }

    @Test
    fun `opening the app checks a still-signed-in user again`() = runTest {
        // A fresh Activity in a process that outlived the last one finds the
        // manager signed in and already accepted.
        val manager = AuthenticationManager(FakeKeychainHelper())
        manager.login(session)
        manager.acceptPrivacyPolicy()

        manager.onAppOpened()

        assertChecking(manager)
    }

    @Test
    fun `opening the app signed out asks nobody`() {
        val manager = AuthenticationManager(FakeKeychainHelper())

        manager.onAppOpened()

        assertSettledAccepted(manager)
    }

    @Test
    fun `remember-me rotation after opening the app checks only once`() = runTest {
        val manager = AuthenticationManager(FakeKeychainHelper())
        manager.login(session)
        manager.acceptPrivacyPolicy()
        manager.onAppOpened()
        manager.acceptPrivacyPolicy() // this opening's check settled

        manager.login(session.copy(sessionToken = "rotated"), keepPrivacyPolicyAcceptance = true)

        assertSettledAccepted(manager)
    }

    @Test
    fun `a restore after process death loads the saved session and checks`() {
        // Android killed the process and is restoring the signed-in screens; the
        // new manager starts signed out though the session is still stored.
        val keychain = FakeKeychainHelper()
        keychain.save(session, "positive-only-social.Positive-Only-Social", "userSessionToken")
        val manager = AuthenticationManager(keychain)

        manager.onActivityCreated(restoringState = true)

        assertTrue(manager.isLoggedIn.value)
        assertEquals(session, manager.session.value)
        assertChecking(manager)
    }

    @Test
    fun `a configuration change keeps the answer already given`() = runTest {
        val manager = AuthenticationManager(FakeKeychainHelper())
        manager.onActivityCreated(restoringState = false)
        manager.login(session)
        manager.acceptPrivacyPolicy()

        manager.onActivityCreated(restoringState = true)

        assertTrue(manager.isLoggedIn.value)
        assertSettledAccepted(manager)
    }

    @Test
    fun `a fresh launch in a live process checks a signed-in user`() = runTest {
        val manager = AuthenticationManager(FakeKeychainHelper())
        manager.onActivityCreated(restoringState = false)
        manager.login(session)
        manager.acceptPrivacyPolicy()

        manager.onActivityCreated(restoringState = false)

        assertChecking(manager)
    }

    @Test
    fun `a restore after process death with nothing saved stays signed out`() {
        val manager = AuthenticationManager(FakeKeychainHelper())

        manager.onActivityCreated(restoringState = true)

        assertFalse(manager.isLoggedIn.value)
        assertSettledAccepted(manager)
    }
}
