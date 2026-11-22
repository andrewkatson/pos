package com.example.positiveonlysocial.data.auth

import android.util.Log
import com.example.positiveonlysocial.data.constants.Constants
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

private const val TAG = "AuthenticationManager"

/**
 * Thrown by [AuthenticationManager.login] when a freshly issued session could not
 * be written to secure storage (issue #503).
 *
 * Screens read the session back out of the keychain rather than from memory, so a
 * session that was never persisted can't load anything. Swallowing the failure
 * put the user inside a signed-in shell where every screen rendered blank; the
 * caller must keep them on the login screen and say what happened instead.
 */
class SessionPersistenceException(cause: Throwable) :
    Exception(Constants.SESSION_STORAGE_FAILED_MESSAGE, cause)

/**
 * Manages the user's authentication state and session data.
 *
 * This is the Kotlin equivalent of your Swift AuthenticationManager.
 * It uses StateFlow to expose the auth state to the UI (Jetpack Compose).
 *
 * This class should be treated as a singleton in your application (e.g., created
 * once in your Application class or injected with Hilt).
 *
 * @param keychainHelper An instance of your secure storage implementation.
 * @param shouldAutoLogin If true, the manager will try to load a session from
 * storage immediately upon creation.
 */

class AuthenticationManager(
    private val keychainHelper: KeychainHelperProtocol,
    shouldAutoLogin: Boolean = false
) {

    // --- Public StateFlow Properties (Equivalent to @Published) ---

    // Backing property for isLoggedIn
    private val _isLoggedIn = MutableStateFlow(false)
    /**
     * Public, read-only StateFlow for the UI to observe login state.
     */
    val isLoggedIn: StateFlow<Boolean> = _isLoggedIn.asStateFlow()

    // Backing property for session
    private val _session = MutableStateFlow<UserSession?>(null)
    /**
     * Public, read-only StateFlow for the UI to observe the session.
     */
    val session: StateFlow<UserSession?> = _session.asStateFlow()

    // Backing property for forcedLogout
    private val _forcedLogout = MutableStateFlow(false)
    /**
     * Set when the session was dropped without the user asking (the backend
     * revoked it, e.g. an account ban). The navigation layer observes this to
     * send the user back to the welcome screen from wherever they are.
     */
    val forcedLogout: StateFlow<Boolean> = _forcedLogout.asStateFlow()

    // Backing property for needsPrivacyPolicyAcceptance
    private val _needsPrivacyPolicyAcceptance = MutableStateFlow(false)
    /**
     * Whether the signed-in user still has to accept the privacy policy before
     * using the app (issue #620).
     *
     * For now this is unconditional: nothing records which version of the policy
     * a user accepted, so every launch that restores a session, and every fresh
     * login, asks again. It lives in memory only, so reopening the app counts as
     * "opening the app" and re-prompts. Once the backend records an acceptance
     * timestamp, this is the flag to drive from it.
     */
    val needsPrivacyPolicyAcceptance: StateFlow<Boolean> = _needsPrivacyPolicyAcceptance.asStateFlow()

    // --- Private Properties ---

    // Identifiers for secure storage
    private val keychainService = "positive-only-social.Positive-Only-Social"
    private val sessionAccount = "userSessionToken"

    // A coroutine-based Mutex to replicate NSLock for thread-safety.
    // This ensures login() and logout() cannot run at the same time.
    private val mutex = Mutex()

    // Property for testing
    var logoutCallCount = 0
        private set // Makes the 'setter' private

    /**
     * Automatically checks for a saved session upon initialization.
     */
    init {
        if (shouldAutoLogin) {
            checkInitialState()
        } else {
            // Explicitly set to logged out
            _session.value = null
            _isLoggedIn.value = false
        }
    }

    /**
     * Tries to load a UserSession from secure storage.
     */
    private fun checkInitialState() {
        try {
            // Try to load the entire session object
            val loadedSession = keychainHelper.load(
                UserSession::class.java, // Use .java to get the Class type
                service = keychainService,
                account = sessionAccount
            )

            if (loadedSession != null) {
                // We're logged in, publish the session
                _session.value = loadedSession
                _isLoggedIn.value = true
                // Opening the app with a saved session asks again (#620).
                _needsPrivacyPolicyAcceptance.value = true
            } else {
                // No session object found
                _session.value = null
                _isLoggedIn.value = false
            }
        } catch (e: Exception) {
            // Handle errors (e.g., decryption failure, I/O error)
            Log.e(TAG, "Failed to load initial state", e)
            _session.value = null
            _isLoggedIn.value = false
        }
    }

    /**
     * Call this after your API login call succeeds.
     * This function is 'suspend' as it performs secure disk I/O.
     *
     * @param sessionData The new session to save and publish.
     * @throws SessionPersistenceException if the session could not be written to
     * secure storage. The manager stays logged out in that case, because a
     * session only this object knows about is one no screen can load with.
     *
     * A failed write clears [session] and [isLoggedIn] rather than leaving them
     * untouched, which matters if this is ever used to refresh a live session
     * rather than to establish a first one. Holding "logged in" while the store
     * that every screen reads from has just refused a write is the precise state
     * issue #503 was: signed-in shell, nothing behind it. Whatever was in the
     * keychain before is not a fallback — when the store is unopenable it can't
     * be read either, and no screen consults this object's copy.
     *
     * @param keepPrivacyPolicyAcceptance Pass true only when updating the session
     * of a user who is already signed in and using the app (identity
     * verification rewrites it in place), so they aren't asked to accept the
     * privacy policy again mid-session (#620). Every other login — a sign-in, or
     * remember-me auto-login when the app opens — asks.
     */
    suspend fun login(sessionData: UserSession, keepPrivacyPolicyAcceptance: Boolean = false) {
        // Use mutex.withLock to ensure atomic operation
        mutex.withLock {
            try {
                // Save the entire session object to secure storage
                keychainHelper.save(
                    sessionData,
                    service = keychainService,
                    account = sessionAccount
                )
            } catch (e: CancellationException) {
                // A cancelled login is not a failed one. Without this, the catch
                // below would rewrite it as a SessionPersistenceException, which
                // the login screen shows to the user as "we couldn't save your
                // login" — a report of something that never happened. Not
                // reachable while the only call in the try is a blocking write,
                // but this is a suspend function, so anything suspending added
                // in here later would make it so silently.
                throw e
            } catch (e: Exception) {
                Log.e(TAG, "Failed to save session", e)
                _session.value = null
                _isLoggedIn.value = false
                throw SessionPersistenceException(e)
            }

            // Signing in, or being signed in automatically when the app opens,
            // has to accept the privacy policy (#620). This deliberately doesn't
            // look at isLoggedIn: this manager is a process-wide singleton, so it
            // can still read "logged in" when the app is reopened in a process
            // that outlived its Activity.
            if (!keepPrivacyPolicyAcceptance || !_isLoggedIn.value) {
                _needsPrivacyPolicyAcceptance.value = true
            }

            // Publish the new session and state
            _session.value = sessionData
            _isLoggedIn.value = true
        }
    }

    /**
     * Records that the signed-in user accepted the privacy policy (#620).
     */
    fun acceptPrivacyPolicy() {
        _needsPrivacyPolicyAcceptance.value = false
    }

    /**
     * Call this to log the user out.
     * This function is 'suspend' as it performs secure disk I/O.
     */
    suspend fun logout() {
        // Drop the prompt before waiting on the lock: logging out is also how
        // the user declines the policy, and the dialog should close at once
        // rather than linger until the session is cleared.
        _needsPrivacyPolicyAcceptance.value = false

        // Use mutex.withLock to ensure atomic operation
        mutex.withLock {
            logoutCallCount += 1

            try {
                // Delete the session from secure storage
                keychainHelper.delete(keychainService, sessionAccount)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to delete session", e)
                // Even if delete fails, we log out from the app's state
            }

            // Clear the published properties
            _session.value = null
            _isLoggedIn.value = false
        }
    }

    /**
     * Logs out because the backend revoked the session (e.g. the account was
     * banned). Raises [forcedLogout] so the UI can navigate away.
     */
    suspend fun forceLogout() {
        logout()
        _forcedLogout.value = true
    }

    /**
     * Call after the UI has reacted to [forcedLogout].
     */
    fun clearForcedLogout() {
        _forcedLogout.value = false
    }
}
